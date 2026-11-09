import { useCallback, useEffect, useRef, useState } from "react"
import { Moon, Send, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Markdown } from "@/components/app/Markdown"
import { QuickCalc } from "@/components/app/QuickCalc"
import { ResultPanel } from "@/components/app/ResultPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { calc, getInfo, getStatus } from "@/lib/api"
import { label, LLM_NAME, TITLE } from "@/lib/format"
import { suggest } from "@/lib/suggest"
import { isResult, type Call, type Hit, type Info, type Out, type ToolName } from "@/lib/types"

type Msg = { id: number; role: "user" | "ai"; text?: string; wait?: boolean; err?: boolean; calls?: Call[]; hit?: Hit; note?: string }

const EXAMPLES = [
  "수소환원 100만 t의 수소를 그린 수소로 만들지 전력망 전기로 만들지, 어떤 상황에서 무엇이 나아?",
  "광양 전기로 250만 t을 가동률 70%로 돌리면 추가로 필요한 전력은?",
  "수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?",
  "무탄소 전력을 0.3 TWh만 확보했는데, 부족분을 메우려면 무엇을 바꿔야 해?",
  "수소환원을 하면 탄소가 얼마나 줄어?",
  "수소환원 설비 투자비와 투자 회수 기간은?",
]
const LIMITS = [
  "예측이 아니라 조건부 시나리오입니다. 사내 실제 에너지 데이터 없이 공개 자료로만 계산했습니다.",
  "숫자는 모두 계산 도구가 냅니다. AI는 질문을 읽고 결과를 풀어 설명할 뿐입니다.",
  "부족분은 1년 전력량으로 따진 값입니다. 시간대별 공급과 저장은 넣지 않았으므로 생산을 이어갈 수 있는지는 이 값으로 판단하지 않습니다.",
  "요금은 전력 요금만 셌습니다. 설비 투자비와 원료비 절감은 들어 있지 않습니다.",
  "배출권 가치는 입력한 가격으로 환산한 참고 가치입니다. 실제 구매 회피액과는 다릅니다.",
]
const callText = (o: Out) => (o.status === "ok" ? "계산 완료" : o.status === "ask" ? `되묻기: ${(o.missing ?? []).map(label).join(", ")}` : `거절: ${o.reason}`)

function ThemeButton() {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === "dark"
  return (
    <Button variant="ghost" size="icon" className="text-white hover:bg-white/10 hover:text-white dark:hover:bg-white/10" aria-label={dark ? "라이트 모드로 바꾸기" : "다크 모드로 바꾸기"} onClick={() => setTheme(dark ? "light" : "dark")}>
      {dark ? <Sun aria-hidden strokeWidth={2} /> : <Moon aria-hidden strokeWidth={2} />}
    </Button>
  )
}

export default function App() {
  const [info, setInfo] = useState<Info | null>(null)
  const [llm, setLlm] = useState<string | null | undefined>(undefined)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [result, setResult] = useState<{ id: number; hit: Hit } | null>(null)
  const [q, setQ] = useState("")
  const [busy, setBusy] = useState(false)
  const session = useRef("")
  const seq = useRef(0)
  const end = useRef<HTMLDivElement>(null)
  const resultRef = useRef<HTMLElement>(null)

  useEffect(() => {
    getInfo().then(setInfo).catch(() => setInfo(null))
    getStatus().then((s) => setLlm(s.llm)).catch(() => setLlm(null))
  }, [])
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }) }, [msgs])
  useEffect(() => { if (result) resultRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }) }, [result])

  const add = (m: Omit<Msg, "id">) => { const id = ++seq.current; setMsgs((l) => [...l, { ...m, id }]); return id }
  const patch = (id: number, m: Partial<Msg>) => setMsgs((l) => l.map((x) => (x.id === id ? { ...x, ...m } : x)))
  const open = useCallback((hit: Hit) => setResult({ id: ++seq.current, hit }), [])

  const ask = async (text: string) => {
    setBusy(true)
    add({ role: "user", text })
    const id = add({ role: "ai", wait: true, text: "계산 중입니다. 답이 나오기까지 몇 초에서 십수 초 걸립니다." })
    try {
      const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text, session: session.current }) })
      const d: Out = await res.json()
      if (!res.ok) return patch(id, { wait: false, err: true, text: d.error })
      session.current = d.session
      const ok = (d.calls as Call[]).filter(isResult)  // close_gap은 min_green 결과를 포함하는 상위 결과라 있으면 그것을 열고, 없으면 마지막 결과를 연다
      const hit = (ok.find((c) => c.name === "close_gap") ?? ok[ok.length - 1]) as Hit | undefined
      patch(id, { wait: false, text: d.answer, calls: d.calls, hit })
      if (hit) open(hit)
    } catch (e) {
      patch(id, { wait: false, err: true, text: `서버에 연결하지 못했습니다 (${(e as Error).message}). python3 -m src.web 이 실행 중인지 확인하세요.` })
    } finally { setBusy(false) }
  }

  // AI를 거치지 않고 계산 도구를 바로 부른다(빠르고 AI 연결이 없어도 동작)
  const followup = async (text: string, tool: ToolName, args: Out) => {
    add({ role: "user", text })
    const id = add({ role: "ai", wait: true, text: "계산 중입니다." })
    try {
      const r = await calc(tool, args)
      if (r.status !== "ok") return patch(id, { wait: false, err: true, text: r.status === "ask" ? `값이 더 필요합니다: ${(r.missing ?? []).map(label).join(", ")}` : `근거가 있는 범위를 벗어나 계산하지 않았습니다. ${r.reason}` })
      const hit: Hit = { name: tool, input: args, output: r }
      patch(id, { wait: false, text: "조건을 바꿔 계산 도구로 바로 다시 계산했습니다. 결과 창에서 확인하세요.", hit, note: "direct" })
      open(hit)
    } catch (e) { patch(id, { wait: false, err: true, text: `서버에 연결하지 못했습니다 (${(e as Error).message}).` }) }
  }

  const newChat = () => { session.current = ""; setMsgs([]); setResult(null); setQ("") }
  const submit = () => { const t = q.trim(); if (t && !busy) { setQ(""); void ask(t) } }
  const chatting = msgs.length > 0

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b-4 border-brand-accent bg-brand text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-8">
          <h1 className="text-xl font-semibold">제철공정의 저탄소 전환을 돕는 AI 어시스턴트 <span className="ml-1 text-sm font-normal text-white/70">스틸커넥트 · Steel Connect</span></h1>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-2 border-white/30 text-white" role="status">
              <i aria-hidden className={`size-2 rounded-full ${llm ? "bg-clean" : "bg-white/50"}`} />
              {llm === undefined ? "AI 연결 확인 중" : llm ? `AI 연결됨 (${LLM_NAME[llm] ?? llm})` : "AI 연결 안 됨. 지금은 질문에 답할 수 없습니다"}
            </Badge>
            {chatting && <Button variant="outline" size="sm" className="border-white/40 text-white hover:bg-white/10 hover:text-white hover:[&:not([data-size^=icon])]:text-white dark:border-white/40 dark:hover:bg-white/10" onClick={newChat}>새 대화</Button>}
            <ThemeButton />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8">
        <section aria-labelledby="ask-h" className="min-w-0 space-y-6">
          {!chatting && <h2 id="ask-h" className="pt-12 text-4xl font-semibold tracking-tight">얼마나 만들고 탄소를 얼마나 줄일지 물어보세요.</h2>}
          <ol aria-live="polite" className="space-y-4">
            {msgs.map((m) => m.role === "user" ? (
              <li key={m.id} className="border-l-2 border-primary pl-4 text-base font-medium">{m.text}</li>
            ) : (
              <li key={m.id}>
                <Card className={m.err ? "ring-destructive/40" : ""}>
                  <CardContent className="space-y-4">
                    {m.wait ? <p className="animate-pulse text-muted-foreground">{m.text}</p> : m.err ? <p className="text-destructive">{m.text}</p> : m.note ? <p>{m.text}</p> : <Markdown>{m.text ?? ""}</Markdown>}
                    {!!m.calls?.length && (
                      <p className="border-t border-border pt-3 text-sm text-muted-foreground">
                        계산 도구 호출: {m.calls.map((c, i) => <span key={i}>{i > 0 && " / "}<code className="font-mono font-medium text-foreground">{c.name}</code> {callText(c.output)}</span>)}
                      </p>
                    )}
                    {m.hit && (
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => open(m.hit!)}>계산 결과 보기 ({TITLE[m.hit.name]})</Button>
                        {suggest(m.hit, info).map(([text, tool, args]) => <Button key={text} size="sm" variant="outline" disabled={busy} onClick={() => void followup(text, tool, args)}>{text}</Button>)}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
          <div ref={end} />
          {result && info && (
            <section ref={resultRef} aria-label="계산 결과" className="scroll-mt-4">
              <ResultPanel key={result.id} hit={result.hit} info={info} onClose={() => setResult(null)} />
            </section>
          )}
          {!chatting && llm === null && <QuickCalc info={info} onOpen={open} />}
          <form onSubmit={(e) => { e.preventDefault(); submit() }} className="space-y-3">
            <label htmlFor="q" className="sr-only">질문</label>
            <div className="flex gap-2">
              <Input id="q" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault() }} maxLength={500}
                placeholder={chatting ? "이어서 물어보세요. 예: 확보 가능한 무탄소 전력이 0.3 TWh면?" : EXAMPLES[2]} autoComplete="off" />
              <Button type="submit" className="bg-brand text-white hover:bg-[color-mix(in_oklch,var(--brand),white_15%)] disabled:opacity-100" disabled={busy || !q.trim()}><Send aria-hidden strokeWidth={2} />질문하기</Button>
            </div>
            <p className="text-sm text-muted-foreground">답은 몇 초에서 십수 초 걸립니다.</p>
          </form>
          {!chatting && (
            <ul aria-label="예시 질문" className="flex flex-col items-start gap-2">
              {EXAMPLES.map((t) => <li key={t}><Button variant="outline" size="sm" className="h-auto whitespace-normal py-2 text-left" onClick={() => setQ(t)}>{t}</Button></li>)}
            </ul>
          )}
          {!chatting && llm !== null && <QuickCalc info={info} onOpen={open} />}
        </section>
      </main>

      <footer className="mx-auto max-w-4xl border-t border-border px-4 py-6 sm:px-8">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{LIMITS.map((t) => <li key={t}>{t}</li>)}</ul>
      </footer>
    </div>
  )
}

