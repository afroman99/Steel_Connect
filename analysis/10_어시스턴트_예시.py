"""어시스턴트 연결 예시: Claude가 계산 도구(src/assistant_tools.py)를 호출해 질문에 답하는 최소 루프.
계산은 call_tool(코드), 해석·설명은 LLM. 준비: pip install anthropic, 환경변수 ANTHROPIC_API_KEY. 실행: 프로젝트 루트에서
python3 analysis/10_어시스턴트_예시.py "수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?"
질문을 안 주면 질문 세트(N11, M01, R03)로 시연한다. 모델·옵션은 바꿔도 된다(MODEL). 계산 규칙은 reports/결과보고서.md 부록 E-5."""

import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.assistant_tools import SYSTEM_PROMPT, TOOL_SCHEMAS, TOOLS, call_tool

# fmt: off
MODEL = "claude-opus-5-5"
API_TOOLS = [dict(name=n, description=TOOLS[n], input_schema=TOOL_SCHEMAS[n]) for n in TOOLS]


def ask(question, client=None, max_turns=8):
    """ask = 질문 하나에 답한다. 모델이 도구를 부르면 call_tool로 계산해 결과를 돌려주고, 도구를 더 안 부르면 최종 답을 반환한다."""
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    for _ in range(max_turns):
        r = client.beta.messages.create(model=MODEL, max_tokens=16000, system=SYSTEM_PROMPT, tools=API_TOOLS, messages=messages, output_config={"effort": "medium"},
                                        betas=["server-side-fallback-2026-07-01"], fallbacks="default")  # 안전 필터에 걸리면 서버가 다른 모델로 다시 시도
        if r.stop_reason == "refusal":
            return "(안전 필터로 답변이 거절됐습니다. 질문을 바꿔 보세요.)"
        messages.append({"role": "assistant", "content": r.content})  # thinking 블록 포함 응답 전체를 그대로 이어 붙인다
        uses = [b for b in r.content if b.type == "tool_use"]
        if not uses:
            return "".join(b.text for b in r.content if b.type == "text")
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(call_tool(b.name, b.input), ensure_ascii=False, default=str)} for b in uses]})  # 도구 결과는 한 메시지에 모아서
    return "(도구 호출이 너무 많아 중단했습니다.)"


if __name__ == "__main__":
    qs = sys.argv[1:] or ["수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?", "수소환원을 하면 탄소가 얼마나 줄어?", "수소환원 설비 투자비와 투자 회수 기간은?"]
    for q in qs:
        print(f"\nQ. {q}\nA. {ask(q)}")
