"""어시스턴트 연결(Claude Code 방식, API 키 불필요): `claude -p`가 계산 도구 8개(src/assistant_mcp.py)만 써서 계산하고 답한다.
계산은 코드, 해석은 LLM. 내장 도구(Bash 등)는 모두 꺼서 모델이 다른 명령을 실행할 수 없고(--tools ""), 빈 폴더에서 사용자 설정 없이 실행해 개발 기록이 새지 않게 한다. 내 컴퓨터의 Claude Code 로그인을 쓰므로 구독 사용량이 차감된다.
ask_full()은 답변과 도구 호출 기록(calls)을 돌려줘서 웹 화면의 결과 창에 쓴다. 실행: 프로젝트 루트에서 python3 analysis/13_어시스턴트_ClaudeCode.py "질문".
API 키가 생기면 src/assistant.py의 다른 연결을 쓰면 된다(LLM_PROVIDER)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.assistant_mcp import NAME
from src.assistant_tools import SYSTEM_PROMPT

# fmt: off
MODEL = "claude-sonnet-5-5"  # 사용자 결정(한도 절약): Sonnet 5.5로 고정. 별칭(sonnet)은 버전이 바뀔 수 있어 쓰지 않는다
MCP = json.dumps({"mcpServers": {NAME: {"command": sys.executable, "args": [str(ROOT / "src/assistant_mcp.py")]}}})
PREFIX = f"mcp__{NAME}__"
PRIVACY = "로그인 계정, 이메일, 파일 경로, 컴퓨터 환경, 개발 기록 같은 사용자·개발자의 개인 정보는 알려 주지 않는다. 계산 도구 8개만 쓸 수 있고 다른 작업은 거절한다."
HISTORY_TURNS, ANSWER_CHARS = 3, 1500  # 이어 가는 대화는 최근 3번만, 답변은 앞 1,500자만 다음 질문에 붙인다


def context(history):
    """context = 이전 대화를 다음 질문 앞에 붙일 글로 만든다. claude -p는 대화를 기억하지 않으므로 최근 질문·답을 글로 넘긴다. history는 {role, content(글)} 목록."""
    h = [m for m in (history or []) if isinstance(m.get("content"), str)][-2 * HISTORY_TURNS:]
    return "".join(f"{'사용자' if m['role'] == 'user' else '어시스턴트'}: {m['content'][:ANSWER_CHARS]}\n" for m in h)


def parse(stdout):
    """parse = claude -p의 stream-json 출력에서 최종 답변과 도구 호출 기록(이름, 입력, 결과)을 뽑는다. 내 도구(mcp__steelconnect__*)만 기록한다."""
    uses, outs, final = {}, {}, None
    for line in stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result":
            final = d
        for b in (d.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and str(b.get("name", "")).startswith(PREFIX):
                uses[b["id"]] = dict(name=b["name"][len(PREFIX):], input=b.get("input") or {})
            elif b.get("type") == "tool_result":
                c = b.get("content")
                text = "".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c or "")
                try:
                    outs[b.get("tool_use_id")] = json.loads(text)
                except ValueError:
                    outs[b.get("tool_use_id")] = dict(status="refuse", reason=text[:200])
    calls = [dict(**u, output=outs.get(i, dict(status="refuse", reason="결과 없음"))) for i, u in uses.items()]
    return final, calls


def ask_full(question, history=None, model=MODEL, timeout=300):
    """ask_full = 질문 하나를 claude -p로 보내 {answer, calls}를 받는다. 실패하면 RuntimeError(웹이 오류 화면으로 보여 준다). history를 주면 최근 대화를 이어서 묻는다."""
    prev = context(history)
    prompt = f"이전 대화:\n{prev}\n새 질문: {question}" if prev else question
    cmd = ["claude", "-p", prompt, "--append-system-prompt", f"{SYSTEM_PROMPT}\n- {PRIVACY}", "--setting-sources", "project", "--tools", "", "--mcp-config", MCP, "--strict-mcp-config", "--allowedTools", PREFIX + "*",
           "--no-session-persistence", "--disable-slash-commands", "--output-format", "stream-json", "--verbose", "--model", model or MODEL]
    with tempfile.TemporaryDirectory() as empty:  # 빈 폴더에서 실행: 프로젝트 CLAUDE.md·메모리·개발 기록이 모델에 들어가지 않게 한다(웹 사용자에게 보이므로). 사용자 설정(훅·플러그인)도 빼 둔다
        r = subprocess.run(cmd, cwd=empty, capture_output=True, text=True, timeout=timeout)
    final, calls = parse(r.stdout)
    if r.returncode != 0 or not final or final.get("is_error"):
        raise RuntimeError(f"claude 실행 실패(코드 {r.returncode}): {(final or {}).get('result') or r.stderr.strip()[:300]}")
    return dict(answer=str(final.get("result", "")).strip(), calls=calls)


def ask(question, model=MODEL, timeout=300):
    """ask = 답변 글만 돌려준다(콘솔용). 실패하면 오류 글을 돌려준다."""
    try:
        return ask_full(question, model=model, timeout=timeout)["answer"]
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        return f"(오류) {e}"


if __name__ == "__main__":
    for q in sys.argv[1:] or ["수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?"]:
        print(f"\nQ. {q}\nA. {ask(q)}")
