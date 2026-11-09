"""어시스턴트 연결(Claude Code 방식, API 키 불필요): `claude -p`가 src/assistant_cli.py 하나만 호출해 계산하고 답한다.
계산은 코드, 해석은 LLM. 내 컴퓨터의 Claude Code 로그인을 쓰므로 구독 사용량이 차감된다(질문 1개 = 여러 번 호출). 실행: 프로젝트 루트에서
python3 analysis/13_어시스턴트_ClaudeCode.py "질문". API 키가 생기면 ask()만 analysis/10 방식으로 바꾸면 된다."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.assistant_tools import SYSTEM_PROMPT

# fmt: off
CMD_RULE = "도구는 Bash로 `python3 -m src.assistant_cli 도구이름 '{JSON}'` 형태만 호출할 수 있다. 결과는 JSON 한 줄이다."
MODEL = "claude-sonnet-5-5"  # 사용자 결정(한도 절약): Sonnet 5.5로 고정. 별칭(sonnet)은 버전이 바뀔 수 있어 쓰지 않는다
ALLOWED = "Bash(python3 -m src.assistant_cli:*)"  # 이 명령만 허용. 파일 읽기·수정, 다른 명령은 막는다


def ask(question, model=MODEL, timeout=300):
    """ask = 질문 하나를 claude -p로 보내 최종 답을 문자열로 받는다. 도구 호출은 Claude Code가 알아서 반복한다."""
    cmd = ["claude", "-p", question, "--append-system-prompt", f"{SYSTEM_PROMPT}\n\n{CMD_RULE}", "--allowedTools", ALLOWED,
           "--disallowedTools", "Edit", "Write", "WebFetch", "WebSearch", "--no-session-persistence", "--output-format", "text"]
    if model: cmd += ["--model", model]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 else f"(오류 {r.returncode}) {r.stderr.strip()[:300]}"


if __name__ == "__main__":
    for q in sys.argv[1:] or ["수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?"]:
        print(f"\nQ. {q}\nA. {ask(q)}")
