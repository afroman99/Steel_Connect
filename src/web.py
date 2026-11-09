"""웹 화면 v0.2: 제철공정의 저탄소 전환을 돕는 AI 어시스턴트. 숫자는 src/assistant_tools.call_tool이 내고, 질문은 LLM 어시스턴트(src/assistant.py)가 해석한다.

실행: 프로젝트 루트에서 python -m src.web  -> 브라우저로 http://127.0.0.1:8000  (--port, --host 0.0.0.0 으로 바꿈)
API: POST /api/calc {tool, args} -> call_tool 결과 그대로({status: ok|ask|refuse, ...}, AI 없이) | POST /api/ask {question, session} -> {answer, calls, session}
     GET /api/tools -> 도구 설명·입력 형식·허용 범위(화면 슬라이더 범위용) | GET /api/status -> AI 연결 여부
주의: 표준 라이브러리 http.server만 쓴다(새 패키지 없음). 화면(web/ React 앱, 빌드 결과 web/dist)은 질문 하나만 보여 주고, 답변에 계산 결과가 있을 때만 오른쪽 결과 창을 연다. 숫자를 다시 계산하지 않는다. /api/calc는 AI 없이도 동작한다(결과 창의 '다시 계산').
공개 주소로 열 때 걸려 있는 보호는 IP당 질문 횟수 제한(RATE)뿐이다. 비밀번호는 앞단(프록시 등)에서 건다. 대화 기록은 서버 메모리에만 두고 재시작하면 사라진다.
"""

import argparse
import json
import mimetypes
import os
import shutil
import threading
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.assistant import ask, client, provider
from src.assistant_tools import REQUIRED, TOOL_SCHEMAS, TOOLS, call_tool
from src.simulator import ETS_RANGE, PLANS, RANGE, Scenario

# fmt: off
WEB = Path(__file__).resolve().parent.parent / "web"
DIST, LEGACY = WEB / "dist", WEB / "legacy.html"  # 화면: React 빌드 결과(web/dist, cd web && npm run build). 없으면 옛 단일 HTML(legacy.html)로 대신한다
RATE, MAX_Q, MAX_SESSIONS, MAX_BODY = (20, 3600), 500, 200, 20_000  # IP당 질문 20회/시간, 질문 500자, 보관 대화 200개, 요청 본문 20KB
SESSIONS, HITS, CONN, LOCK = OrderedDict(), {}, {}, threading.Lock()  # 세션별 대화, IP별 질문 시각, LLM 연결(첫 질문 때 한 번 만듦)
INFO = dict(tools=TOOLS, schemas=TOOL_SCHEMAS, required=REQUIRED, ranges={**RANGE, "ets_price": ETS_RANGE}, plans=list(PLANS), defaults=asdict(Scenario()))  # GET /api/tools 응답. 화면 슬라이더 범위·초기값


def llm_status():
    """llm_status = AI 연결 상태. 이미 연결됐으면 그 종류, 아니면 provider()가 고른 종류(api·gemini·groq·custom·ollama·claude_code). bedrock은 AWS 자격증명이, claude_code는 claude 명령이 보일 때만, 없으면 None. LLM을 실제로 호출하지는 않는다."""
    if "conn" in CONN:
        return CONN["conn"][0]
    kind = provider()
    if kind == "claude_code":
        return kind if shutil.which("claude") else None
    if kind != "bedrock":
        return kind
    try:
        import botocore.session
        return "bedrock" if botocore.session.get_session().get_credentials() else None
    except Exception:
        return None


def allowed(ip):
    """allowed = 질문 허용 여부. 최근 RATE[1]초 안에 이 IP의 질문이 RATE[0]회 미만이면 기록하고 True."""
    now = time.time()
    with LOCK:
        q = HITS.setdefault(ip, deque())
        while q and q[0] < now - RATE[1]:
            q.popleft()
        if len(q) >= RATE[0]:
            return False
        q.append(now)
        return True


def answer(question, session):
    """answer = 질문 처리. 세션의 이전 대화를 이어 ask를 부르고, 화면에 보낼 답변·도구 호출 기록을 돌려준다. 오래된 세션은 MAX_SESSIONS를 넘으면 지운다."""
    with LOCK:
        if "conn" not in CONN:
            CONN["conn"] = client()
        history = SESSIONS.get(session)
    r = ask(question, history, CONN["conn"])
    with LOCK:
        SESSIONS[session] = r["messages"]
        SESSIONS.move_to_end(session)
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)
    return dict(answer=r["answer"], calls=r["calls"], session=session, model=r["model"])


class Handler(BaseHTTPRequestHandler):
    """Handler = 요청 처리. 화면(GET /), 상태(GET /api/status), 도구 정보(GET /api/tools), 질문(POST /api/ask), 직접 계산(POST /api/calc)."""

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            page = DIST / "index.html" if (DIST / "index.html").exists() else LEGACY
            return self.send(200, page.read_bytes(), "text/html; charset=utf-8")
        f = (DIST / path.lstrip("/")).resolve()
        if path.startswith("/assets/") and f.is_file() and DIST.resolve() in f.parents:  # 빌드된 JS·CSS·글꼴. DIST 밖(../)은 막는다
            return self.send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        if self.path == "/api/status":
            return self.send(200, {"llm": llm_status()})
        if self.path == "/api/tools":
            return self.send(200, INFO)
        self.send(404, {"error": f"{self.path}: 없는 주소"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self.send(413, {"error": f"요청이 {MAX_BODY}바이트를 넘습니다"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send(400, {"error": "요청 본문이 JSON이 아닙니다"})
        if not isinstance(body, dict):
            return self.send(400, {"error": "요청 본문은 JSON 객체여야 합니다"})
        if self.path == "/api/calc":
            if not isinstance(body.get("args", {}), dict):
                return self.send(400, {"error": "args는 JSON 객체여야 합니다"})
            return self.send(200, call_tool(str(body.get("tool", "")), body.get("args")))
        if self.path == "/api/ask":
            q = str(body.get("question", "")).strip()
            if not 0 < len(q) <= MAX_Q:
                return self.send(400, {"error": f"질문은 1~{MAX_Q}자로 입력하세요"})
            if not llm_status():
                return self.send(503, {"error": "AI가 연결돼 있지 않아 답할 수 없습니다. 연결 방법은 src/assistant.py 맨 위 설명을 보세요"})
            if not allowed(self.client_address[0]):
                return self.send(429, {"error": f"질문은 1시간에 {RATE[0]}번까지입니다. 잠시 뒤 다시 보내세요"})
            try:
                return self.send(200, answer(q, str(body.get("session") or uuid.uuid4())[:64]))
            except Exception as e:
                return self.send(502, {"error": f"AI에 연결하지 못했습니다 ({type(e).__name__}: {e})"})
        self.send(404, {"error": f"{self.path}: 없는 주소"})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="제철공정의 저탄소 전환을 돕는 AI 어시스턴트 웹 화면")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--llm", help="AI 연결 종류(api, gemini, groq, claude_code ...). 없으면 LLM_PROVIDER 환경변수나 키로 자동 선택. Claude Code 로그인으로 쓰려면 --llm claude_code")
    a = p.parse_args()
    if a.llm:
        os.environ["LLM_PROVIDER"] = a.llm
    print(f"http://{a.host}:{a.port} 에서 실행 중 (AI 연결: {llm_status() or '없음, 질문에 답할 수 없음'}). Ctrl+C로 끝냅니다.")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
