# COMPASS 도입 기록 (Steel Connect 웹 화면)

- 설치 버전: **0.1.0** (고정). 레지스트리: https://compass.designcompass.org
- 설치 명령 (`web/`에서, 패키지 관리자 npm):
  `npx shadcn@4.21.0 add https://compass.designcompass.org/r/0.1.0/foundations.json https://compass.designcompass.org/r/0.1.0/compass.json -y`
- 적용일: 2026-11-09. 대상: `web/` (브랜치 `compass-ui`). 이전 프로젝트(WannaOne_END_react)의 같은 도입 기록을 따랐다.

## 설치 전 상태와 이관

이 프로젝트의 화면은 파이썬 서버(`src/web.py`)가 내주는 **HTML 한 장**(React·Tailwind·shadcn 없음)이어서 COMPASS와 호환되지 않았다. 호환되지 않는 환경이라 팀장 확인 뒤(2026-11-09) 화면을 React로 이관했다.

| 항목 | 값 |
|---|---|
| 프레임워크 | Vite 7 + React 19 + TypeScript 5.8 (`npm create vite@7.1.3 viteapp -- --template react-ts`로 만든 뼈대를 `web/`에 복사) |
| Tailwind | v4.3 (`@tailwindcss/vite`) |
| shadcn | `npx shadcn@4.21.0 init -t vite -b radix -p nova -y` → style `radix-nova`, baseColor `neutral`, cssVariables, iconLibrary `lucide` |
| 경로 별칭 | `@/*` → `web/src/*` (`tsconfig.json`, `tsconfig.app.json`, `vite.config.ts`) |
| 패키지 관리자 | npm (pnpm 없음) |

- 기존 화면은 지우지 않고 `web/legacy.html`로 보존했다. 빌드(`web/dist`)가 없으면 서버가 이 파일을 내준다.
- 초기화가 만든 `button.tsx`(수정 이력 없는 생성본)와 Geist 글꼴 설정은 지우고 COMPASS 것으로 교체했다(덮어쓰기 옵션 없이). 글꼴은 COMPASS의 Pretendard Variable 한 번만 불러온다(`src/index.css`).

## 설치된 것

- 토큰: `web/src/index.css` (색, Pretendard, 반지름, 그림자, squircle, primary-hover). Primary·Accent `#007AFF`.
- 컴포넌트 15개: `web/src/components/ui/` alert-dialog, avatar, badge, button, card, dialog, input, pagination, progress, select, sheet, slider, tabs, toggle-group, toggle (화면에서 쓰는 것: Badge, Button, Card, Input, Select, Slider)
- `web/src/components/theme-provider.tsx` → `web/src/main.tsx`에서 앱 최상위에 연결(기본 `system`, 라이트·다크 둘 다, `d` 키로 전환). 화면 오른쪽 위에 해/달 아이콘 버튼(Lucide, 선 두께 2)도 둠.
- 사용 문서: `web/docs/compass.md`
- 의존성: class-variance-authority, cn, lucide-react, next-themes, pretendard, radix-ui, tw-animate-css, shadcn

## 프로젝트에서 더한 것 (COMPASS 원본과 다른 점)

- 계산 결과 색 `--grid`(전력망 전력), `--clean`(무탄소 전력), `--need`(부족분)를 `index.css` 끝에 더했다(라이트·다크 값 따로). 원본 토큰은 바꾸지 않았다.
- `--radius`는 COMPASS 기본(2.5rem)을 그대로 썼다.
- COMPASS에 없는 것은 시맨틱 HTML로 만들었다: 질문 입력은 `Input`(한 줄, 최대 500자), 표는 `<table>`, 접는 영역은 `<details>`, 3색 막대는 `<div>`(데이터 시각화).
- AI 답변은 `react-markdown` + `remark-gfm`으로 그린다(표를 지원. 이전 화면은 표가 깨졌다).
- eslint: `src/components/ui/**`만 `react-refresh/only-export-components`를 끔(COMPASS 파일이 변형 함수를 같이 내보내는 원래 구조).

## 연결

- 개발: 파이썬 서버 `python3 -m src.web --llm claude_code`(8000번)를 켠 채 `cd web && npm run dev` → http://localhost:5173 (`/api`는 8000번으로 넘김, `vite.config.ts`).
- 실행: `cd web && npm install && npm run build` 후 `python3 -m src.web --llm claude_code` → http://127.0.0.1:8000. 서버는 `web/dist`를 내주고 `/assets/` 밖과 `dist` 밖 경로는 막는다.

## 검증 (2026-11-09)

- `npx tsc -b`, `npm run lint`, `npm run build` 통과. 빌드 경고: JS 묶음 569kB > 500kB, Pretendard 전체 글꼴 2MB.
- 라이트·다크 화면 확인(헤드리스 Chrome 스크린샷): 첫 화면, 부족분 해소(`close_gap`), 전환 시나리오, 경로 비교, 폭 500px.
- 서버가 `web/dist`를 내주는 것, `/assets/` 서빙, 경로 탈출 시도(404), `/api/*` 동작 확인. "다시 계산"이 실제 `/api/calc`로 값을 갱신하는 것 확인.

## 남은 제한

- 위 화면 확인은 AI 응답 부분을 **가짜 응답(실제 계산 도구 결과를 담음)** 으로 대신한 것이다. 실제 Claude Code 응답을 이 React 화면에서 끝까지 받아 보는 시험은 따로 해야 한다(서버 쪽 `/api/ask`는 이전에 실제 호출로 확인함).
- 키보드 포커스 이동과 스크린 리더는 컴포넌트가 가진 기본 동작에 의존하고, 직접 조작해 검증하지 않았다.
- COMPASS의 ThemeToggle·LocaleProvider(한/영 전환)는 설치되지 않아(`compass.json` 묶음에 없음) 쓰지 않았다.
- 개발자 PC에서 `npm install`과 `npm run build`가 필요하다(`web/dist`는 git에 올리지 않는다). 빌드가 없으면 옛 화면이 뜬다.
