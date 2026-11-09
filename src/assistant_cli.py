"""어시스턴트 계산 도구의 단일 진입점. Claude Code가 이 명령 하나만 부르도록 허용해서 다른 명령은 못 쓰게 한다.
실행: 프로젝트 루트에서 python3 -m src.assistant_cli 도구이름 '{"인자": 값}' -> 결과 JSON 한 줄을 출력."""

import json
import sys

from src.assistant_tools import call_tool

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        if not isinstance(args, dict): raise ValueError
    except ValueError:
        sys.exit(print(json.dumps(dict(status="refuse", reason="인자는 JSON 객체여야 함"), ensure_ascii=False)))
    print(json.dumps(call_tool(sys.argv[1] if len(sys.argv) > 1 else "", args), ensure_ascii=False, default=str))
