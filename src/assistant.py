"""LLM 어시스턴트 v0.4: 질문 -> LLM이 도구 인자로 바꿈 -> src/assistant_tools.call_tool 계산 -> 근거 인용 답변. 계산은 코드, 해석은 LLM.
v0.4: 도구·스키마·시스템 프롬프트를 src/assistant_tools.py(TOOLS, TOOL_SCHEMAS, SYSTEM_PROMPT, call_tool) 하나로 통일. 여기서는 LLM 연결과 도구 호출 반복만 한다.
도구 결과는 항상 status(ok·ask·refuse)를 가진다. 웹 화면은 src/web.py.

연결(provider 순서): ANTHROPIC_API_KEY -> Anthropic API, GEMINI_API_KEY -> Gemini, GROQ_API_KEY -> Groq, LLM_BASE_URL(+LLM_API_KEY) -> 그 OpenAI 호환 주소,
그 밖 -> Amazon Bedrock(AWS 자격증명, AWS_REGION 기본 ap-northeast-2). LLM_PROVIDER로 직접 고른다. 모델은 Claude는 CLAUDE_MODEL, 나머지는 LLM_MODEL.
LLM_PROVIDER=ollama -> 내 PC의 Ollama(자동으로 고르지 않음). LLM_PROVIDER=claude_code -> analysis/13_어시스턴트_ClaudeCode.py의 ask()(claude -p, Claude Code 로그인 사용). 도구는 src/assistant_mcp.py(MCP)로만 쓰고 Bash 등 내장 도구는 꺼져 있다.
실행: 프로젝트 루트에서 python -m src.assistant "질문"  |  인자 없이 실행하면 대화 모드  |  --tools 는 도구 정의만 출력(네트워크 없음)
"""

import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from src.assistant_tools import SYSTEM_PROMPT, TOOL_SCHEMAS, TOOLS, call_tool

# fmt: off
ROOT = Path(__file__).resolve().parent.parent
MODEL = {"api": "claude-haiku-5-5", "bedrock": "global.anthropic.claude-haiku-5-5", "gemini": "gemini-flash-latest", "groq": "openai/gpt-oss-120b", "ollama": "qwen3:8b", "custom": "", "claude_code": ""}  # 기본 모델. 서울 리전 Bedrock은 global 교차 리전 ID만 지원. claude_code는 analysis/13의 MODEL
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
COMPAT = {"gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"), "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
          "ollama": (OLLAMA + "/v1", None), "custom": (None, "LLM_API_KEY")}  # OpenAI 호환 연결: (주소, 키 환경변수). custom 주소는 LLM_BASE_URL

def tools():
    """tools = 도구 정의. assistant_tools의 도구 7개(simulate, required_output, min_green, sweep_green, close_gap, compare_paths, breakeven_grid)를 Claude 도구 형식으로 돌려준다."""
    return [dict(name=n, description=TOOLS[n], input_schema=TOOL_SCHEMAS[n]) for n in TOOLS]


def to_openai(m):
    """to_openai = Anthropic 형식 메시지 하나를 OpenAI chat 메시지 목록으로 바꾼다. 도구 결과(user의 tool_result 목록)는 role 'tool' 메시지 여러 개가 된다."""
    c = m["content"]
    if isinstance(c, str):
        return [{"role": m["role"], "content": c}]
    if m["role"] == "user":
        return [{"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]} for b in c]
    calls = [{"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(b.input, ensure_ascii=False)}} for b in c if b.type == "tool_use"]
    return [{"role": "assistant", "content": "".join(b.text for b in c if b.type == "text"), **({"tool_calls": calls} if calls else {})}]


class Compat:
    """Compat = OpenAI 호환 API(Gemini·Groq·Ollama 등 무료 경로)를 Anthropic의 client.messages.create처럼 쓰게 하는 변환기. 표준 라이브러리 urllib만 쓴다.
    응답의 tool_calls는 tool_use 블록으로, <think> 생각 과정은 지우고 돌려준다. 로컬 모델은 느릴 수 있어 요청 제한 시간은 10분."""

    def __init__(self, kind):
        base, key = COMPAT[kind]
        self.url, self.key, self.messages = (base or os.environ["LLM_BASE_URL"]).rstrip("/") + "/chat/completions", os.environ.get(key or "", ""), self
        self.reasoning = os.environ.get("LLM_REASONING", "none" if kind == "ollama" else "")  # 생각 과정 길이. PC 모델은 꺼야(none) 답이 몇 배 빠르다

    def create(self, model, max_tokens, system, tools, messages):
        body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "system", "content": system}] + [x for m in messages for x in to_openai(m)],
                "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools],
                **({"reasoning_effort": self.reasoning} if self.reasoning else {})}
        req = urllib.request.Request(self.url, json.dumps(body, ensure_ascii=False).encode(), {"Content-Type": "application/json", **({"Authorization": f"Bearer {self.key}"} if self.key else {})})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                m = json.load(r)["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.url} {e.code}: {e.read().decode(errors='replace')[:300]}") from None
        text = re.sub(r"<think>.*?</think>", "", m.get("content") or "", flags=re.S).strip()
        args = lambda a: a if isinstance(a, dict) else json.loads(a or "{}")
        calls = [SimpleNamespace(type="tool_use", id=c.get("id") or f"call_{i}", name=c["function"]["name"], input=args(c["function"].get("arguments"))) for i, c in enumerate(m.get("tool_calls") or [])]
        return SimpleNamespace(content=([SimpleNamespace(type="text", text=text)] if text else []) + calls, stop_reason="tool_use" if calls else "end_turn")


def claude_code():
    """claude_code = analysis/13_어시스턴트_ClaudeCode.py 모듈. 파일 이름이 숫자·한글이라 import 문 대신 경로로 불러온다. claude 명령(Claude Code)이 설치·로그인돼 있어야 한다."""
    spec = importlib.util.spec_from_file_location("claude_code_adapter", ROOT / "analysis/13_어시스턴트_ClaudeCode.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def provider():
    """provider = 연결 종류 고르기. LLM_PROVIDER가 있으면 그것, 아니면 키가 있는 순서대로 api > gemini > groq > custom, 모두 없으면 bedrock(AWS 자격증명이 없으면 웹은 AI 미연결로 본다).
    ollama·claude_code는 자동으로 고르지 않는다. 로컬 소형 모델은 값을 지어내 답이 틀렸고(qwen3:8b), claude_code는 구독 사용량이 차감되므로 LLM_PROVIDER로 직접 고를 때만 쓴다. 네트워크는 쓰지 않는다."""
    if p := os.environ.get("LLM_PROVIDER"):
        return p
    for kind, env in (("api", "ANTHROPIC_API_KEY"), ("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"), ("custom", "LLM_BASE_URL")):
        if os.environ.get(env):
            return kind
    return "bedrock"


def client():
    """client = LLM 연결. provider()가 고른 종류로 (연결 종류, 클라이언트)를 돌려준다. Anthropic SDK는 Claude를 쓸 때만 여기서 불러와 검증 스크립트가 네트워크·SDK 없이 돌게 한다."""
    kind = provider()
    if kind == "claude_code":
        return kind, claude_code()
    if kind in COMPAT:
        return kind, Compat(kind)
    import anthropic
    if kind == "api":
        return "api", anthropic.Anthropic()
    return "bedrock", anthropic.AnthropicBedrock(aws_region=os.environ.get("AWS_REGION", "ap-northeast-2"))


def ask(question, history=None, conn=None, model=None, max_turns=8):
    """ask = 질문하기. LLM이 도구를 부르면 call_tool로 계산해 돌려주기를 반복하고, 최종 답변(answer)·도구 호출 기록(calls)·대화(messages)를 돌려준다.
    calls는 숫자 일치율·인용 정확도·거절률 평가에 쓴다. history에 이전 messages를 넣으면 대화를 이어간다. claude_code는 최근 3번의 대화를 글로 이어 붙이고, calls는 claude -p 출력에서 뽑는다."""
    kind, c = conn or client()
    if kind == "claude_code":  # claude -p는 대화를 기억하지 않아 history의 최근 글을 질문 앞에 붙여 넘기고, 도구 호출 기록은 stream-json에서 뽑는다
        model = model or os.environ.get("CLAUDE_MODEL") or c.MODEL
        r = c.ask_full(question, history=history, model=model)
        return dict(answer=r["answer"], calls=r["calls"], messages=list(history or []) + [{"role": "user", "content": question}, {"role": "assistant", "content": r["answer"]}], model=model)
    model = model or os.environ.get("LLM_MODEL" if kind in COMPAT else "CLAUDE_MODEL") or MODEL[kind]
    messages, calls = list(history or []) + [{"role": "user", "content": question}], []
    for _ in range(max_turns):
        r = c.messages.create(model=model, max_tokens=2048, system=SYSTEM_PROMPT, tools=tools(), messages=messages)
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            return dict(answer="".join(b.text for b in r.content if b.type == "text"), calls=calls, messages=messages, model=model)
        results = []
        for b in r.content:
            if b.type == "tool_use":
                out = call_tool(b.name, b.input)
                calls.append(dict(name=b.name, input=b.input, output=out))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False, default=str), "is_error": out["status"] == "refuse"})
        messages.append({"role": "user", "content": results})
    return dict(answer=f"도구 호출이 {max_turns}회를 넘어 중단했습니다.", calls=calls, messages=messages, model=model)


def show(r):
    """show = 결과 출력. 답변과 도구 호출 요약(도구, 입력, status)을 콘솔에 찍는다."""
    print(r["answer"])
    for k in r["calls"]:
        o = k["output"]
        print(f"  [도구] {k['name']}({json.dumps(k['input'], ensure_ascii=False)}) -> {o['status']}" + {"ask": f" 되묻기 {o.get('missing')}", "refuse": f" 거절: {o.get('reason')}"}.get(o["status"], ""))


if __name__ == "__main__":
    if sys.argv[1:] == ["--tools"]:
        print(json.dumps(tools(), ensure_ascii=False, indent=2)); sys.exit()
    conn = client()
    if sys.argv[1:]:
        show(ask(" ".join(sys.argv[1:]), conn=conn)); sys.exit()
    history = None
    print(f"Steel_Connect 어시스턴트 ({conn[0]}). 빈 줄을 입력하면 끝냅니다.")
    while q := input("\n질문> ").strip():
        r = ask(q, history, conn); show(r); history = r["messages"]
