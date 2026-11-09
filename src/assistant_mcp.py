"""계산 도구 7개를 MCP(Model Context Protocol, AI에게 도구를 알려 주는 표준 방식) 서버로 노출한다. 표준 라이브러리만 쓰고, 표준 입출력으로 한 줄씩 JSON을 주고받는다.
Claude Code(`claude -p`)가 이 서버의 도구만 쓰게 하려고 만들었다. Bash 같은 내장 도구는 끄므로 모델이 다른 명령을 실행할 방법이 없다.
실행은 Claude Code가 한다(analysis/13_어시스턴트_ClaudeCode.py). 직접 확인: 프로젝트 루트에서 python3 -m src.assistant_mcp 를 켜고 JSON 한 줄을 입력."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.assistant_tools import TOOL_SCHEMAS, TOOLS, call_tool

# fmt: off
NAME = "steelconnect"
LIST = [dict(name=n, description=TOOLS[n], inputSchema=TOOL_SCHEMAS[n]) for n in TOOLS]


def handle(msg):
    """handle = 요청 하나 처리. id가 없는 알림은 응답하지 않고(None), 모르는 메서드는 오류로 돌려준다."""
    m, i = msg.get("method"), msg.get("id")
    if i is None:
        return None
    ok = lambda r: {"jsonrpc": "2.0", "id": i, "result": r}
    if m == "initialize":
        return ok(dict(protocolVersion=(msg.get("params") or {}).get("protocolVersion", "2024-11-05"), capabilities={"tools": {}}, serverInfo=dict(name=NAME, version="1.0")))
    if m == "ping":
        return ok({})
    if m == "tools/list":
        return ok({"tools": LIST})
    if m == "tools/call":
        p = msg.get("params") or {}
        out = call_tool(str(p.get("name", "")), p.get("arguments"))
        return ok(dict(content=[dict(type="text", text=json.dumps(out, ensure_ascii=False, default=str))], isError=out["status"] == "refuse"))
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"지원하지 않는 메서드: {m}"}}


if __name__ == "__main__":
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            r = handle(json.loads(line))
        except Exception as e:  # 잘못된 요청 하나로 서버가 죽지 않게 한다
            r = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}}
        if r is not None:
            print(json.dumps(r, ensure_ascii=False), flush=True)
