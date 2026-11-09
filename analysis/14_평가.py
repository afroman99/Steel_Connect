"""어시스턴트 평가: 질문을 웹 화면과 같은 경로(src.assistant.ask, Claude Code)로 보내 답변·도구 호출을 기록하고 자동 채점한다. 질문마다 한 줄씩 바로 출력한다.
실행: 프로젝트 루트에서 python3 analysis/14_평가.py [--set unseen|main|all] [--only U01,N11] [--fresh]
결과: reports/평가결과.jsonl (질문마다 한 줄: 답변 전문, 도구 호출, 판정). 같은 id가 이미 있으면 건너뛴다(--fresh면 처음부터). 중간에 멈춰도 다시 실행하면 이어 간다.
채점은 규칙 기반이라 완벽하지 않다. '통과'도 답변 전문을 직접 읽어 확인해야 하고, '확인필요'는 사람이 판단한다.
- 정상: (도구) 호출 결과에 기대 숫자가 있고 (답변) 글에도 같은 숫자(단위 환산 허용)가 있으면 통과. 도구 결과에 없는데 글에만 있으면 확인필요(지어낸 숫자 의심)
  기대 추천(pick, 예: N20 그린·N21 전력망)이 있으면 h2_supply 결과의 verdict.pick이 같고 답변의 결론 문장에 그 이름이 있어야 한다
- 되묻기: 계산 결과(ok)를 내지 않고 되묻는 말이 있으면 통과
- 거절: 계산 결과(ok)를 내지 않고 거절하는 말이 있으면 통과
질문마다 구독 사용량이 차감된다. 프롬프트 예시(few-shot)는 쓰지 않는다."""

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["LLM_PROVIDER"] = "claude_code"  # 화면(--llm claude_code)과 같은 연결
sys.path.insert(0, str(ROOT))
from src.assistant import ask, client

# fmt: off
OUT = ROOT / "reports/평가결과.jsonl"
REFUSE = r"할 수 없|수 없습니다|어렵|못합|못 합|알 수 없|근거|범위|계산하지|제공하지|확인할 수 없|다루지|거절|불가|없습니다"
ASKING = r"[?？]|알려 ?주|말씀해|정해 ?주|입력해|넣어 ?주|알려 ?드|필요합니다"


def load_questions():
    spec = importlib.util.spec_from_file_location("q09", ROOT / "analysis/09_질문세트.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return [dict(d, set="unseen") for d in m.UNSEEN] + [dict(d, set="main") for d in m.QUESTIONS]


def leaves(x):
    """leaves = 도구 결과(JSON) 안의 숫자를 모두 꺼낸다(참·거짓은 제외)."""
    if isinstance(x, bool): return
    if isinstance(x, (int, float)): yield float(x)
    elif isinstance(x, dict):
        for v in x.values(): yield from leaves(v)
    elif isinstance(x, list):
        for v in x: yield from leaves(v)


def in_tools(v, calls):
    """in_tools = 기대 숫자가 도구 호출 결과에 있는가(정확히 같은 값). AI가 올바른 입력으로 계산 도구를 불렀다는 증거."""
    return any(abs(x - v) <= 1e-6 * max(1, abs(v)) for c in calls for x in leaves(c["output"]))


def in_text(v, text):
    """in_text = 기대 숫자가 답변 글에 있는가. 단위 환산(만, 백만, %)과 반올림을 허용한다(오차 1.5% 또는 0.006). 맞은 값을 돌려준다."""
    nums = [float(s.replace(",", "")) for s in re.findall(r"\d[\d,]*(?:\.\d+)?", text) if s.replace(",", "").replace(".", "", 1).isdigit()]
    cands = {abs(v) * k for k in (1, 100, 1e-4, 1e-6) if abs(v) * k >= 0.05}  # 0.05 미만 환산값은 "0~2.5" 같은 글 속 숫자와 우연히 맞아 오탐이 되므로 뺀다(2026-11-09 평가에서 발견)
    nums = [n for n in nums if n > 0]
    for n in nums:
        if any(abs(n - c) <= max(0.015 * abs(c), 0.006) for c in cands): return n
    return None


PICK_NAME = {"green": ("그린 수소", "그린수소"), "grid": ("전력망 전기", "전력망", "일반 전기", "계통 전력")}  # 추천 이름(답변 글에서 찾을 말)


def pick_check(pick, answer, calls):
    """pick_check = 추천 대조. (도구) h2_supply 결과의 verdict.pick이 기대와 같은가, (글) 기대 이름 뒤 20자 안에 결론 말(추천·유리·낫·싸/쌉·저렴·선택)이 오는 문장이 있는가. 맞은 부분을 돌려준다."""
    tool = any(isinstance(c["output"].get("result"), dict) and c["output"]["result"].get("verdict", {}).get("pick") == pick for c in calls)
    says = re.compile(rf"({'|'.join(PICK_NAME[pick])})[^.\n]{{0,20}}(추천|유리|낫|싸|쌉|저렴|선택)")
    text = next((m.group(0) for s in re.split(r"(?<=[.!?\n])", answer) if (m := says.search(s))), None)
    return dict(도구=tool, 글=text)


def grade(d, answer, calls):
    ok = [c for c in calls if c["output"].get("status") == "ok"]
    if d["type"] == "normal":
        if not ok:  # 계산 결과를 내지 않음: 글에 우연히 같은 숫자가 있어도 맞은 것으로 치지 않는다
            if re.search(ASKING, answer): return "되물음", "도구 결과 없이 되물음(질문이 단독으로는 불완전할 수 있음. 질문 문장을 확인)", {}
            return "실패", "도구를 부르지 않고 답함(숫자를 직접 만들었을 수 있음)", {}
        det = {k: dict(도구=in_tools(v, calls), 글=in_text(v, answer)) for k, v in d["expect"].items()}
        if "pick" in d:
            det["추천"] = pick_check(d["pick"], answer, calls)
            nums_ok = all(x["도구"] and x["글"] is not None for k, x in det.items() if k != "추천")
            if nums_ok and not (det["추천"]["도구"] and det["추천"]["글"]):
                return "실패", f"숫자는 맞지만 추천이 기대({d['pick']})와 다름(도구 일치 {det['추천']['도구']}, 답변 결론 {det['추천']['글']})", det
        if all(x["도구"] and x["글"] is not None for x in det.values()): return "통과", "기대 숫자가 도구 결과와 답변에 모두 있음", det
        if all(x["글"] is not None for x in det.values()): return "확인필요", "답변에는 있으나 도구 결과에 같은 값이 없음(다른 입력으로 계산했거나 지어낸 숫자)", det
        return "실패", "기대 숫자가 답변에 없음", det
    if d["type"] == "ask":
        keys = [w for w in re.findall(r"[가-힣A-Za-z_]{2,}", d["missing"])]
        asked = bool(re.search(ASKING, answer)) and any(w in answer for w in keys)
        if ok: return "실패", f"되묻지 않고 계산함: {[c['name'] for c in ok]}", {}
        return ("통과", "계산 없이 되물음", {}) if asked else ("확인필요", "계산은 안 했지만 되묻는 말이 불분명", {})
    refused = bool(re.search(REFUSE, answer))
    if ok: return "실패", f"근거 없이 계산함: {[c['name'] for c in ok]}", {}
    if d["id"] == "R06" and "가정" not in answer: return "확인필요", "거절했지만 가정 가격 안내가 없음", {}
    return ("통과", "계산 없이 거절", {}) if refused else ("확인필요", "계산은 안 했지만 거절하는 말이 불분명", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all", choices=["unseen", "main", "all"]); ap.add_argument("--only"); ap.add_argument("--fresh", action="store_true"); ap.add_argument("--redo", action="store_true", help="--only로 고른 질문의 이전 결과를 지우고 다시 호출한다(질문 문장을 고친 뒤)"); ap.add_argument("--regrade", action="store_true", help="저장된 답변·도구 호출로 판정만 다시 한다(호출 없음)")
    a = ap.parse_args()
    qs = [d for d in load_questions() if a.set in ("all", d["set"]) and (not a.only or d["id"] in a.only.split(","))]
    OUT.parent.mkdir(exist_ok=True)
    if a.regrade:
        Q = {d["id"]: d for d in load_questions()}; rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r_ in rows:
            if not r_["error"]: r_["verdict"], r_["reason"], r_["detail"] = grade(Q[r_["id"]], r_["answer"], r_["calls"])
        OUT.write_text("".join(json.dumps(r_, ensure_ascii=False, default=str) + "\n" for r_ in rows), encoding="utf-8"); print(f"다시 채점: {len(rows)}개")
        qs = []
    if a.fresh and OUT.exists(): OUT.unlink()
    if a.redo and a.only and OUT.exists():
        keep = [l for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l)["id"] not in a.only.split(",")]
        OUT.write_text("".join(l + "\n" for l in keep), encoding="utf-8")
    done = {json.loads(l)["id"] for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()} if OUT.exists() else set()
    todo = [d for d in qs if d["id"] not in done]
    print(f"평가 시작: 대상 {len(qs)}개 중 이미 한 것 {len(qs) - len(todo)}개, 이번에 할 것 {len(todo)}개. 결과 파일: {OUT}", flush=True)
    conn = client()
    for i, d in enumerate(todo, 1):
        t = time.time(); err = None
        try:
            r = ask(d["q"], conn=conn)
            answer, calls = r["answer"], [dict(name=c["name"], input=c["input"], output=c["output"]) for c in r["calls"]]
        except Exception as e:  # 호출 실패는 판정 불가로 기록하고 다음 질문으로
            answer, calls, err = "", [], f"{type(e).__name__}: {e}"
        sec = time.time() - t
        v, why, det = ("오류", err, {}) if err else grade(d, answer, calls)
        rec = dict(id=d["id"], set=d["set"], type=d["type"], q=d["q"], verdict=v, reason=why, detail=det, tools=[(c["name"], c["output"].get("status")) for c in calls], seconds=round(sec, 1), answer=answer, calls=calls, error=err)
        with OUT.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print(f"[{i}/{len(todo)}] {d['id']} ({'처음 보는' if d['set'] == 'unseen' else '기본'}·{ {'normal': '정상', 'ask': '되묻기', 'refuse': '거절'}[d['type']] }) {v} {sec:.0f}초 | {why} | 도구 {rec['tools']}", flush=True)
        if err and ("limit" in err.lower() or "usage" in err.lower()): print("한도에 걸린 것으로 보여 중단합니다. 다시 실행하면 이어서 합니다.", flush=True); break
    rows = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("\n=== 요약 (결과 파일 전체 기준) ===", flush=True)
    for s in ("unseen", "main"):
        for ty, nm in (("normal", "정상"), ("ask", "되묻기"), ("refuse", "거절")):
            g = [r for r in rows if r["set"] == s and r["type"] == ty]
            if g: print(f"{'처음 보는' if s == 'unseen' else '기본'} {nm}: 통과 {sum(r['verdict'] == '통과' for r in g)}/{len(g)}, 되물음 {sum(r['verdict'] == '되물음' for r in g)}, 확인필요 {sum(r['verdict'] == '확인필요' for r in g)}, 실패 {sum(r['verdict'] == '실패' for r in g)}, 오류 {sum(r['verdict'] == '오류' for r in g)}", flush=True)
    for r in rows:
        if r["verdict"] != "통과": print(f"  [{r['verdict']}] {r['id']}: {r['reason']}", flush=True)


if __name__ == "__main__":
    main()
