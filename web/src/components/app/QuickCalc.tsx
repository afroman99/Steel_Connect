import { useState } from "react"
import { Calculator } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { calc } from "@/lib/api"
import { label, TITLE } from "@/lib/format"
import type { Hit, Info, Out, ToolName } from "@/lib/types"

// 처음 계산할 입력 가정. 예시 질문과 같은 값이며 결과는 계산 도구(/api/calc)가 낸다
const PRESETS: { tool: ToolName; desc: string; args: Out; wide?: boolean }[] = [
  { tool: "h2_supply", desc: "수소환원 100만 t의 수소를 그린 수소(재생에너지 PPA)로 만들지 전력망 전기로 만들지, 어떤 상황에서 무엇이 나은지", args: { h2_output_mt: 1 }, wide: true },
  { tool: "simulate", desc: "전기로 250만 t, 가동률 70%로 돌릴 때 추가 전력·순 저감·전기요금", args: { eaf_mt: 2.5, eaf_util: 0.7 } },
  { tool: "min_green", desc: "수소환원 50만 t으로 순 저감 50만 tCO2를 하려면 필요한 무탄소 전력", args: { h2_output_mt: 0.5, target_abate_t: 500000 } },
  { tool: "close_gap", desc: "무탄소 전력을 0.3 TWh만 확보했을 때 부족분을 메우는 조건", args: { h2_output_mt: 0.5, target_abate_t: 500000, green_supply_twh: 0.3 } },
  { tool: "compare_paths", desc: "순 저감 50만 tCO2를 전기로와 수소환원으로 각각 낼 때 비교", args: { target_abate_t: 500000 } },
]

export function QuickCalc({ info, onOpen }: { info: Info | null; onOpen: (hit: Hit) => void }) {
  const [busy, setBusy] = useState<ToolName | null>(null)
  const [err, setErr] = useState("")

  const run = async (tool: ToolName, args: Out) => {
    setBusy(tool)
    setErr("")
    try {
      const r = await calc(tool, args)
      if (r.status === "ok") onOpen({ name: tool, input: args, output: r })
      else setErr(r.status === "ask" ? `값이 더 필요합니다: ${(r.missing ?? []).map(label).join(", ")}` : `근거가 있는 범위를 벗어나 계산하지 않았습니다. ${r.reason}`)
    } catch (e) {
      setErr(`서버에 연결하지 못했습니다 (${(e as Error).message}). python3 -m src.web 이 실행 중인지 확인하세요.`)
    } finally { setBusy(null) }
  }

  return (
    <section aria-labelledby="quick-h" className="space-y-3">
      <div className="space-y-1">
        <h3 id="quick-h" className="flex items-center gap-2 text-lg font-semibold"><Calculator aria-hidden className="size-5" strokeWidth={2} />AI 없이 바로 계산하기</h3>
        <p className="text-sm text-muted-foreground">AI 연결이 없어도 계산 도구로 결과 그래프와 표를 볼 수 있습니다. 결과 창의 '조건 바꾸기'에서 값을 바꿔 다시 계산하세요.</p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {PRESETS.map((p) => (
          <li key={p.tool} className={p.wide ? "sm:col-span-2" : undefined}>
            <button type="button" disabled={!info || busy !== null} onClick={() => void run(p.tool, p.args)} className="h-full w-full rounded-xl text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60">
              <Card className="h-full transition-colors hover:bg-muted/50">
                <CardContent className="space-y-1">
                  <p className="font-semibold">{TITLE[p.tool]}{busy === p.tool && <span className="ml-2 animate-pulse text-sm font-normal text-muted-foreground">계산 중</span>}</p>
                  <p className="text-sm text-muted-foreground">{p.desc}</p>
                </CardContent>
              </Card>
            </button>
          </li>
        ))}
      </ul>
      {!info && <p className="text-sm text-muted-foreground">계산 도구 정보를 불러오지 못했습니다. python3 -m src.web 이 실행 중인지 확인하세요.</p>}
      {err && <p role="alert" className="text-sm text-destructive">{err}</p>}
    </section>
  )
}
