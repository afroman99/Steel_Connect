/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState, type ReactNode } from "react"
import { X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { calc } from "@/lib/api"
import { label, leverValue, man, num, plain, TITLE } from "@/lib/format"
import type { Hit, Info, Out, ToolName } from "@/lib/types"
import { ToolForm } from "./ToolForm"

const COST_NOTE = "요금에는 전력 요금만 넣었고 설비 투자비와 원료비 절감은 넣지 않았습니다."

function Figure({ title, value, unit, sub, main }: { title: string; value: string; unit?: string; sub?: ReactNode; main?: boolean }) {
  return (
    <div className="space-y-1 p-4">
      <dt className="text-sm text-muted-foreground">{title}</dt>
      <dd className="flex items-baseline gap-1.5">
        <span className={`text-3xl font-semibold tracking-tight ${main ? "text-clean" : ""}`}>{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </dd>
      {sub && <dd className="text-sm leading-5 text-muted-foreground">{sub}</dd>}
    </div>
  )
}

function Figures({ children }: { children: ReactNode }) {
  return <dl className="grid grid-cols-1 divide-y divide-border rounded-xl border border-border sm:grid-cols-2 sm:divide-x sm:[&>*:nth-child(n+3)]:border-t sm:[&>*:nth-child(n+3)]:border-border">{children}</dl>
}

function Fold({ title, children, open }: { title: string; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group border-t border-border py-3">
      <summary className="cursor-pointer text-sm font-medium select-none marker:text-muted-foreground">{title}</summary>
      <div className="pt-3">{children}</div>
    </details>
  )
}

/** 요구 전력을 전력망 / 확보한 무탄소 / 부족분으로 나눠 보여 주는 막대. 너비만 비율로 계산하고 표시 숫자는 결과값 그대로 */
function PowerBar({ x }: { x: Out }) {
  const w = (v: number) => `${x.feasible && x.power_twh ? (v / x.power_twh) * 100 : 0}%`
  const grid = x.power_twh - (x.green_twh || 0), secured = (x.green_twh || 0) - (x.gap_twh || 0), gap = x.gap_twh || 0
  return (
    <figure className="space-y-2">
      <div
        role="img"
        aria-label={x.feasible ? `요구 전력 ${num(x.power_twh)} TWh 중 무탄소 ${num(x.green_twh)} TWh, 부족분 ${num(x.gap_twh)} TWh` : "무탄소 100%로도 목표 미달"}
        className="flex h-10 overflow-hidden rounded-xl bg-muted"
      >
        <span className="bg-grid" style={{ width: w(grid) }} />
        <span className="bg-clean" style={{ width: w(secured) }} />
        <span style={{ width: w(gap), background: "repeating-linear-gradient(135deg, var(--need) 0 6px, var(--foreground) 6px 9px)" }} />
      </div>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><i className="size-3 rounded-sm bg-grid" />전력망 전력</span>
        <span className="inline-flex items-center gap-1.5"><i className="size-3 rounded-sm bg-clean" />확보한 무탄소 전력</span>
        <span className="inline-flex items-center gap-1.5"><i className="size-3 rounded-sm bg-need" />부족분(추가로 확보할 무탄소) <b className="text-foreground">{x.feasible ? `${num(x.gap_twh)} TWh` : "-"}</b></span>
      </figcaption>
    </figure>
  )
}

/** 부족분을 메우는 조건(close_gap): 하나씩만 바꿨을 때 부족분이 0이 되는 값 */
function Levers({ levers }: { levers: Out[] }) {
  if (!levers.length) return <p className="text-sm text-muted-foreground">부족분이 없어서 바꿀 조건이 없습니다.</p>
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="px-3 py-2 font-medium">구분</th>
              <th className="px-3 py-2 font-medium">바꿀 조건</th>
              <th className="px-3 py-2 font-medium">현재 → 필요</th>
            </tr>
          </thead>
          <tbody>
            {levers.map((l) => (
              <tr key={l.lever} className="border-t border-border align-top">
                <td className="px-3 py-2"><Badge variant={l.kind === "결정" ? "default" : "secondary"} className="min-h-7 px-3 py-0.5 text-sm">{l.kind}</Badge></td>
                <td className="px-3 py-2">{l.label}</td>
                <td className="px-3 py-2">
                  {leverValue(l.lever, l.now)} → <b>{leverValue(l.lever, l.needed)}</b>
                  {l.lever === "switch_to_eaf" && l.power_twh != null && <span className="block text-muted-foreground">전력 {num(l.power_twh)} TWh, 요금 {num(l.cost_eok, 0)}억 원</span>}
                  {!l.in_range && <Badge variant="destructive" className="ml-2 min-h-7 px-3 py-0.5 text-sm">허용 범위 밖</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm leading-6 text-muted-foreground">
        <b className="text-foreground">결정</b>은 우리가 정할 수 있는 조건, <b className="text-foreground">외부</b>는 기술·정책에 달린 조건입니다. 한 번에 한 조건만 바꾼 값이며 여러 조건을 함께 바꾼 조합은 계산하지 않았습니다.
      </p>
    </div>
  )
}

function MinGreenView({ tool, input, out, spread }: { tool: ToolName; input: Out; out: Out; spread: string }) {
  const x = out.result
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">수소환원 연 {plain(input.h2_output_mt * 100)}만 t 생산, 목표 순 저감 {man(input.target_abate_t)}만 tCO2/년</p>
      {!x.feasible && (
        <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{x.reason}. 이 생산량으로는 많아야 {man(x.max_abate_t)}만 tCO2/년까지 줄일 수 있습니다.</p>
      )}
      <PowerBar x={x} />
      <Figures>
        <Figure title="요구 전력" value={num(x.power_twh)} unit="TWh/년" />
        <Figure title="무탄소 전력 비율" value={x.feasible ? num(x.green_share * 100, 1) : "-"} unit="%" main sub={x.feasible ? `요구 전력 중 무탄소 ${num(x.green_twh)} TWh/년` : undefined} />
        <Figure title="부족분 (확보 가능량 대비)" value={x.feasible ? num(x.gap_twh) : "-"} unit="TWh/년" sub={x.feasible ? (x.met ? "확보 가능량으로 충분(연간 기준)" : "확보 가능량으로는 모자람(연간 기준)") : undefined} />
        <Figure title="전력 요금" value={num(x.cost_eok, 0)} unit="억 원/년" sub="설비 투자비와 원료비 절감은 빠진 전력 요금" />
      </Figures>
      <p className="text-sm leading-6 text-muted-foreground">
        {x.note}. 무탄소 전력을 100% 쓰면 이 생산량으로 최대 {man(x.max_abate_t)}만 tCO2/년까지 줄일 수 있습니다.{spread}
      </p>
      {tool === "close_gap" && (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold">부족분을 메우려면 무엇을 바꿔야 하나</h3>
          <Levers levers={x.levers ?? []} />
        </section>
      )}
    </div>
  )
}

function SimulateView({ out }: { out: Out }) {
  const x = out.result, pw = x.power, c = x.carbon, k = x.cost, inp = x.input
  const used = Object.entries<any>(out.defaults_used ?? {})
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        전기로 {plain(inp.eaf_mt * 100)}만 t × 가동률 {plain(inp.eaf_util * 100)}%, 수소환원 {plain(inp.h2_mt * 100)}만 t(무탄소 {plain(inp.h2_green * 100)}%), 요금제 {inp.plan}
      </p>
      <Figures>
        <Figure title="추가 구매 전력" value={num(pw.add_twh)} unit="TWh/년" sub={`현재 구매 전력보다 ${num(pw.buy_increase_pct, 1)}% 늘어남`} />
        <Figure title="순 저감 (음수면 순증가)" value={man(c.abate_tco2)} unit="만 tCO2/년" main sub={`Scope 1(직접 배출) 감축 ${man(c.scope1_cut_tco2)}만 t, Scope 2(구매 전력 배출) 증가 ${man(c.add_tco2)}만 t`} />
        <Figure title="추가 전기요금" value={num(k.total_eok, 0)} unit="억 원/년" sub={`kWh당 ${num(k.unit_krw_kwh, 1)}원. 기본요금·부가요금·기금 포함`} />
        <Figure title="순 저감 1 t당 전력 비용" value={k.power_cost_per_tco2_krw == null ? "순 저감 없음" : num(k.power_cost_per_tco2_krw, 0)} unit={k.power_cost_per_tco2_krw == null ? undefined : "원/tCO2"} sub="설비 투자비와 원료비 절감은 빠진 값" />
      </Figures>
      {c.ets_value_eok != null && (
        <p className="text-sm leading-6 text-muted-foreground">
          배출권 가격을 {plain(inp.ets_price)}원/tCO2로 잡으면 순 저감의 가치는 <b className="text-foreground">{num(c.ets_value_eok, 0)}억 원/년</b>입니다. 할당량과 보유량을 모르기 때문에 참고 가치일 뿐 실제 구매 회피액과는 다릅니다.
        </p>
      )}
      <Fold title={`기본값으로 가정한 변수 (${used.length}개)`}>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {used.map(([n, v]) => <li key={n}>{label(n)} = {String(v ?? "없음")}</li>)}
        </ul>
      </Fold>
    </div>
  )
}

function CompareView({ input, out }: { input: Out; out: Out }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">순 저감 {man(input.target_abate_t)}만 tCO2/년을 경로마다 달성하려면</p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="px-3 py-2 font-medium">경로</th>
              <th className="px-3 py-2 text-right font-medium">필요 생산량<br />(만 t/년)</th>
              <th className="px-3 py-2 text-right font-medium">추가 전력<br />(TWh/년)</th>
              <th className="px-3 py-2 text-right font-medium">전력 요금<br />(억 원/년)</th>
              <th className="px-3 py-2 text-right font-medium">1 MWh당 순 저감<br />(tCO2)</th>
            </tr>
          </thead>
          <tbody>
            {out.result.map((x: Out) => (
              <tr key={x.name} className="border-t border-border">
                <td className="px-3 py-2">{x.name}</td>
                {x.feasible ? (
                  <>
                    <td className="px-3 py-2 text-right">{num(x.required_mt * 100, 1)}{x.within_capacity ? "" : " (상한 초과)"}</td>
                    <td className="px-3 py-2 text-right">{num(x.power_twh)}</td>
                    <td className="px-3 py-2 text-right">{num(x.cost_eok, 0)}</td>
                    <td className="px-3 py-2 text-right">{num(x.abate_per_mwh)}</td>
                  </>
                ) : (
                  <td colSpan={4} className="px-3 py-2 text-muted-foreground">불가능: {x.reason}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm leading-6 text-muted-foreground">{COST_NOTE} 시뮬레이터가 다루는 생산 능력은 250만 t/년까지입니다.</p>
    </div>
  )
}

const LIMITS: Record<ToolName, (out: Out) => string[]> = {
  min_green: (o) => [o.result.note, "확보 가능한 무탄소 전력은 직접 넣는 가정값입니다. 사내 공급 계획은 알 수 없습니다.", "전력 원단위는 수전해 수소까지 포함한 문헌값(Vogl·Bhaskar)으로, 포스코가 실측한 값이 아닙니다.", COST_NOTE],
  close_gap: (o) => [o.result.note, "확보 가능한 무탄소 전력은 직접 넣는 가정값입니다. 사내 공급 계획은 알 수 없습니다.", "조건을 한 번에 하나씩만 바꾼 값입니다. 전환 비용과 시점은 반영하지 않았습니다.", COST_NOTE],
  simulate: (o) => ["신뢰도가 낮은 가정 (시뮬레이터 LOW_CONF)", ...o.result.assumptions],
  compare_paths: () => ["필요 생산량은 100만 t 기준 결과를 비례로 환산했습니다(target.required_output).", "'상한 초과'가 붙은 경로는 필요 생산량이 시뮬레이터 상한인 250만 t/년보다 큽니다.", COST_NOTE],
}

const H2_KWH_SPREAD = [3480, 3720] // 원단위 문헌값 양 끝(Vogl 2018, Bhaskar 2020)

export function ResultPanel({ hit, info, onClose }: { hit: Hit; info: Info | null; onClose: () => void }) {
  const [cur, setCur] = useState({ input: hit.input, output: hit.output })
  const [msg, setMsg] = useState<Out | null>(null)
  const [spread, setSpread] = useState("")
  const run = async (args: Out) => {
    try {
      const r = await calc(hit.name, args)
      if (r.status === "ok") { setCur({ input: args, output: r }); setMsg(null) } else setMsg(r)
    } catch (e) {
      setMsg({ status: "refuse", reason: `서버에 연결하지 못했습니다 (${(e as Error).message}).` })
    }
  }

  // 전력 원단위를 문헌값 양 끝으로 바꾼 결과(sweep_green)를 덧붙인다
  const { input, output } = cur
  const wantSpread = (hit.name === "min_green" || hit.name === "close_gap") && output.result.feasible && input.h2_kwh_t === undefined
  const key = JSON.stringify(input)
  const lastKey = useRef("")
  useEffect(() => {
    if (!wantSpread || lastKey.current === key) return
    lastKey.current = key
    const { h2_output_mt, target_abate_t, green_supply_twh, grid_factor, h2_resid_t } = input
    calc("sweep_green", { h2_output_mt, target_abate_t, green_supply_twh, grid_factor, h2_resid_t, vary: "h2_kwh_t", values: H2_KWH_SPREAD }).then((r) => {
      if (r.status !== "ok") return setSpread("")
      const rows = r.result.map((x: Out) => `${plain(x.h2_kwh_t)} kWh/t일 때 ${x.feasible ? `${num(x.green_twh)} TWh(${num(x.green_share * 100, 1)}%)` : "100%로도 부족"}`)
      setSpread(` 전력 원단위를 문헌값 양 끝으로 바꿔 보면 무탄소 전력은 ${rows.join(", ")}입니다.`)
    })
  }, [wantSpread, key, input])

  return (
    <Card className="h-fit">
      <CardHeader className="border-b border-border">
        <CardTitle className="text-2xl font-semibold">{TITLE[hit.name]}</CardTitle>
        <CardAction><Button variant="ghost" size="icon" onClick={onClose} aria-label="결과 창 닫기"><X aria-hidden strokeWidth={2} /></Button></CardAction>
      </CardHeader>
      <CardContent className="space-y-5">
        {msg && (
          <div role="alert" className="space-y-1 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {msg.status === "ask" ? <><b>이 값을 넣어 주세요</b><p>{(msg.missing ?? []).map(label).join(", ")}</p></> : <><b>근거가 있는 범위를 벗어나 계산하지 않았습니다</b><p>{msg.reason}</p></>}
          </div>
        )}
        <div className={msg ? "opacity-50" : ""}>
          {hit.name === "simulate" ? <SimulateView out={output} /> : hit.name === "compare_paths" ? <CompareView input={input} out={output} /> : <MinGreenView tool={hit.name} input={input} out={output} spread={spread} />}
        </div>
        <details open className="border-t border-border py-3">
          <summary className="cursor-pointer text-sm font-medium select-none">조건 바꾸기</summary>
          <div className="pt-4"><ToolForm tool={hit.name} info={info} input={input} onRun={run} /></div>
        </details>
        <Fold title="출처">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {Object.entries<any>(output.sources ?? {}).map(([k, s]) => <li key={k}><b className="text-foreground">{k}</b>: {s}</li>)}
          </ul>
        </Fold>
        <Fold title="한계와 가정">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{LIMITS[hit.name](output).map((s) => <li key={s}>{s}</li>)}</ul>
        </Fold>
      </CardContent>
    </Card>
  )
}
