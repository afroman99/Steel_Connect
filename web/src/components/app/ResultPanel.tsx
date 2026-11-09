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

const R = 15.9155 // 둘레가 100이 되는 반지름. 조각 길이를 %로 바로 쓴다

/** 요구 전력을 전력망 / 확보한 무탄소 / 부족분으로 나눈 원그래프(도넛). 조각 크기만 비율로 계산하고 표시 숫자는 결과값 그대로 */
function PowerDonut({ x }: { x: Out }) {
  const total = x.feasible && x.power_twh ? x.power_twh : 0
  const green = x.green_twh || 0, gap = x.gap_twh || 0
  const parts = [
    { key: "grid", v: x.power_twh - green, stroke: "var(--grid)" },
    { key: "secured", v: green - gap, stroke: "var(--clean)" },
    { key: "gap", v: gap, stroke: "url(#need-hatch)" },
  ]
  let start = 0
  return (
    <figure className="flex flex-wrap items-center gap-6">
      <div className="relative size-44 shrink-0">
        <svg
          viewBox="0 0 42 42"
          className="size-full -rotate-90"
          role="img"
          aria-label={x.feasible ? `요구 전력 ${num(x.power_twh)} TWh 중 무탄소 ${num(x.green_twh)} TWh, 부족분 ${num(x.gap_twh)} TWh` : "무탄소 100%로도 목표 미달"}
        >
          <defs>
            <pattern id="need-hatch" width="2.2" height="2.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="2.2" height="2.2" style={{ fill: "var(--need)" }} />
              <rect width="0.7" height="2.2" style={{ fill: "var(--foreground)" }} />
            </pattern>
          </defs>
          <circle cx="21" cy="21" r={R} fill="none" strokeWidth="6" style={{ stroke: "var(--muted)" }} />
          {total > 0 && parts.map((p) => {
            const pct = (p.v / total) * 100
            const el = <circle key={p.key} cx="21" cy="21" r={R} fill="none" strokeWidth="6" strokeDasharray={`${pct} ${100 - pct}`} strokeDashoffset={-start} style={{ stroke: p.stroke }} className="motion-safe:transition-all motion-safe:duration-500" />
            start += pct
            return el
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-muted-foreground">요구 전력</span>
          <span className="text-2xl font-semibold tracking-tight">{num(x.power_twh)}</span>
          <span className="text-xs text-muted-foreground">TWh/년</span>
        </div>
      </div>
      <figcaption className="space-y-2 text-sm text-muted-foreground">
        <p className="flex items-center gap-2"><i className="size-3 rounded-sm bg-grid" />전력망 전력</p>
        <p className="flex items-center gap-2"><i className="size-3 rounded-sm bg-clean" />확보한 무탄소 전력</p>
        <p className="flex items-center gap-2"><i className="size-3 rounded-sm" style={{ background: "repeating-linear-gradient(135deg, var(--need) 0 3px, var(--foreground) 3px 4.5px)" }} />부족분(추가로 확보할 무탄소) <b className="text-foreground">{x.feasible ? `${num(x.gap_twh)} TWh` : "-"}</b></p>
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
      <PowerDonut x={x} />
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
        <Figure title="순 저감 (음수면 순증가)" value={man(c.abate_tco2)} unit="만 tCO2/년" main sub={`Scope 1(직접 배출) 감축 ${c.scope1_cut_tco2 == null ? "이 모델에서는 별도 산정하지 않음" : `${man(c.scope1_cut_tco2)}만 t`}, Scope 2(구매 전력 배출) 증가 ${man(c.add_tco2)}만 t`} />
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

const PICK: Record<string, string> = { green: "그린 수소", grid: "전력망 전기" }
const CELL: Record<string, { text: string; cls: string }> = {
  green: { text: "그린", cls: "bg-clean text-white" },
  grid: { text: "전력망", cls: "bg-grid text-white" },
  bf: { text: "그린만", cls: "bg-destructive text-white" },
}

/** 그린 수소 vs 전력망 전기(h2_supply): 추천, 갈림길 값, 선택지 비교, 상황별 추천 지도. 숫자는 모두 결과값 그대로 */
function H2SupplyView({ out }: { out: Out }) {
  const x = out.result, v = x.verdict, th = x.thresholds, a = x.applied_input, m = x.map
  const green = v.pick === "green"
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        수소환원 연 {plain(a.h2_output_mt * 100)}만 t, 탄소 가격 {plain(a.ets_price)}원/tCO2, 직접PPA {plain(a.ppa_krw_kwh)}원/kWh, 전력배출계수 {plain(a.grid_factor)}, 요금제 {a.plan}
        {x.target_abate_t != null && `, 목표 순 저감 ${man(x.target_abate_t)}만 tCO2/년`}
      </p>
      <div className={`space-y-1 rounded-xl border-l-4 p-4 ${green ? "border-clean bg-clean/10" : "border-grid bg-grid/10"}`}>
        <p className="text-sm text-muted-foreground">지금 조건에서 추천</p>
        <p className={`text-3xl font-semibold tracking-tight ${green ? "text-clean" : ""}`}>{PICK[v.pick]}</p>
        <p className="text-sm leading-6">{v.reason}</p>
        {v.notes.map((n: string) => <p key={n} className="text-sm leading-6 text-muted-foreground">{n}</p>)}
      </div>
      <Figures>
        <Figure title="갈림길 탄소 가격" value={num(th.ets_breakeven, 0)} unit="원/tCO2" main sub="이보다 비싸면 그린 수소가 싸다. 그린으로 바꿔 추가로 줄이는 1 t의 비용과 같다" />
        <Figure title="갈림길 직접PPA 단가" value={num(th.ppa_breakeven, 0)} unit="원/kWh" sub={`이보다 싸면 그린 수소가 싸다. 한전 전력 kWh당 ${num(th.unit_grid_krw_kwh, 1)}원, PPA는 부대비용 포함 ${num(th.unit_ppa_krw_kwh, 1)}원`} />
        <Figure title="고로 손익분기 전력배출계수" value={num(th.gf_breakeven_bf, 3)} unit="tCO2/MWh" sub="이보다 높으면 전력망 전기로 만든 수소는 고로보다 탄소를 더 낸다" />
        <Figure title="그린 수소에 필요한 재생에너지" value={num(th.green_twh_needed)} unit="TWh/년"
          sub={x.supply_ok == null ? "확보 가능량을 넣으면 부족분을 확인합니다" : x.supply_ok ? "확보 가능량으로 충분(연간 기준)" : `확보 가능량 ${plain(x.green_supply_twh)} TWh로는 모자람`} />
      </Figures>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="px-3 py-2 font-medium">선택지</th>
              <th className="px-3 py-2 text-right font-medium">쇳물 1t당 비용<br />(전력 + 탄소, 원)</th>
              <th className="px-3 py-2 text-right font-medium">1t당 순 저감<br />(tCO2)</th>
              <th className="px-3 py-2 text-right font-medium">Scope 2 배출<br />(만 t/년)</th>
              <th className="px-3 py-2 text-right font-medium">재생에너지<br />(TWh/년)</th>
            </tr>
          </thead>
          <tbody>
            {x.options.map((o: Out) => (
              <tr key={o.key} className={`border-t border-border align-top ${o.key === v.pick ? "bg-muted/60 font-medium" : ""}`}>
                <td className="px-3 py-2">
                  {o.name}{!o.compared && <Badge variant="secondary" className="ml-2 h-5 px-2 text-xs">참고</Badge>}
                  <span className="block text-xs font-normal text-muted-foreground">{o.note}</span>
                </td>
                <td className="px-3 py-2 text-right">{num(o.krw_per_t, 0)}<span className="block text-xs font-normal text-muted-foreground">{num(o.power_krw_per_t, 0)} + {num(o.krw_per_t - o.power_krw_per_t, 0)}</span></td>
                <td className="px-3 py-2 text-right">{num(o.abate_per_t)}</td>
                <td className="px-3 py-2 text-right">{man(o.scope2_tco2)}</td>
                <td className="px-3 py-2 text-right">{num(o.green_twh)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="space-y-3">
        <h3 className="text-lg font-semibold">어떤 상황에서 무엇이 좋은가</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {([["green", "그린 수소가 좋은 경우", "border-clean"], ["grid", "전력망 전기가 좋은 경우", "border-grid"]] as const).map(([k, title, cls]) => (
            <div key={k} className={`space-y-2 rounded-xl border-t-4 border-x border-b border-border p-4 ${cls}`}>
              <p className="font-semibold">{title}</p>
              <ul className="list-disc space-y-1 pl-5 text-sm leading-6">{x.conditions[k].map((c: string) => <li key={c}>{c}</li>)}</ul>
            </div>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">각 조건은 다른 값은 지금 그대로 두고 하나만 바꿨을 때의 갈림길입니다.</p>
      </section>
      <section className="space-y-3">
        <h3 className="text-lg font-semibold">시간 일치로 보면 (참고)</h3>
        <p className="text-sm leading-6 text-muted-foreground">위 추천은 1년 물량으로 재생에너지를 계약한 기준입니다. 같은 시간에 난 재생에너지만 그린으로 인정하면 아래처럼 줄어듭니다(2025 전력거래소 시간별 실적).</p>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="px-3 py-2 font-medium">재생에너지</th>
                <th className="px-3 py-2 text-right font-medium">같은 시간에<br />채우는 비율</th>
                <th className="px-3 py-2 text-right font-medium">남는<br />재생에너지</th>
                <th className="px-3 py-2 text-right font-medium">1t당 순 저감<br />(tCO2)</th>
                <th className="px-3 py-2 text-right font-medium">100% 맞추는 저장<br />(부하 일수)</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-border">
                <td className="px-3 py-2">연간 계약 기준 (추천 계산)</td>
                <td className="px-3 py-2 text-right">100%</td><td className="px-3 py-2 text-right">-</td>
                <td className="px-3 py-2 text-right">{num(x.options.find((o: Out) => o.key === "green").abate_per_t)}</td><td className="px-3 py-2 text-right">-</td>
              </tr>
              {Object.entries<any>(x.hourly.rows).map(([k, h]) => (
                <tr key={k} className="border-t border-border">
                  <td className="px-3 py-2">{h.name}{h.cf != null && <span className="block text-xs text-muted-foreground">이용률 {num(h.cf * 100, 1)}%</span>}</td>
                  <td className="px-3 py-2 text-right">{num(h.share * 100, 0)}%</td>
                  <td className="px-3 py-2 text-right">{num(h.surplus * 100, 0)}%</td>
                  <td className="px-3 py-2 text-right">{num(h.abate_per_t)}</td>
                  <td className="px-3 py-2 text-right">{num(h.storage_h / 24, 0)}일</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">{x.hourly.note}. 전력망 전기의 1t당 순 저감은 {num(x.options.find((o: Out) => o.key === "grid").abate_per_t)} t입니다.</p>
      </section>
      <section className="space-y-3">
        <h3 className="text-lg font-semibold">상황별 추천 지도</h3>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full border-collapse text-center text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="px-2 py-2 text-left font-medium">탄소 가격 ↓ / 전력배출계수 →</th>
                {m.gf.map((g: number) => <th key={g} className="px-2 py-2 font-medium">{plain(g)}</th>)}
              </tr>
            </thead>
            <tbody>
              {[...m.ets].map((p: number, i: number) => [p, i] as const).reverse().map(([p, i]) => (
                <tr key={p} className="border-t border-border">
                  <th className="px-2 py-2 text-left font-medium text-muted-foreground">{plain(p)}원</th>
                  {m.cells[i].map((c: string, j: number) => {
                    const here = m.gf[j] === a.grid_factor && p === a.ets_price
                    return <td key={j} className={`border border-background px-2 py-2 ${CELL[c].cls} ${here ? "font-bold outline-3 outline-foreground -outline-offset-3" : ""}`}>{CELL[c].text}{here && " ●"}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          {Object.entries<string>(m.legend).map(([k, t]) => <span key={k} className="mr-3 inline-flex items-center gap-1.5"><i className={`size-3 rounded-sm ${CELL[k].cls}`} />{t}</span>)}
          <br />지금 PPA 단가({plain(a.ppa_krw_kwh)}원)·요금제 기준입니다. ●는 지금 조건. {m.note}.
          <br />탄소 가격 참고(ICAP, 최근 1년): K-ETS {plain(x.ets_ref.kets_1y.min)}~{plain(x.ets_ref.kets_1y.max)}원(평균 {plain(x.ets_ref.kets_1y.mean)}원), EU ETS {plain(x.ets_ref.euets_1y.min)}~{plain(x.ets_ref.euets_1y.max)}원(원화 환산).
        </p>
      </section>
    </div>
  )
}

const SHORT: Record<string, string> = { eaf: "전기로 전환", ppa: "직접PPA 전환", h2: "수소환원 (100% PPA)" }
const STEPS = [10000, 20000, 50000, 100000, 200000, 500000]

/** 감축 비용 곡선 그래프. 막대 폭 = 연 감축량, 높이 = 감축 1t당 전력비용, 검은 선 = 범위. 좌표 변환만 하고 숫자는 결과값 그대로 */
function MaccChart({ rows, lines }: { rows: Out[]; lines: { label: string; v: number }[] }) {
  const W = 640, H = 280, L = 52, RT = 10, T = 34, B = 34
  const total = rows.reduce((s, r) => s + r.abate_mt, 0)
  const vals = [...rows.flatMap((r) => [r.lo, r.hi, r.krw_per_tco2]), ...lines.map((l) => l.v)]
  const max = Math.max(...vals) * 1.08, min = Math.min(0, ...vals) * 1.15
  const step = STEPS.find((s) => (max - min) / s <= 6) ?? 1000000
  const ticks: number[] = []
  for (let t = Math.ceil(min / step) * step; t <= max; t += step) ticks.push(t || 0) // -0 대신 0
  const x = (v: number) => L + (v / total) * (W - L - RT)
  const y = (v: number) => T + ((max - v) / (max - min)) * (H - T - B)
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full text-foreground" role="img" aria-label={rows.map((r) => `${SHORT[r.key]} 감축 1t당 ${num(r.krw_per_tco2, 0)}원, 연 ${num(r.abate_mt)}백만 t`).join(", ")}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - RT} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity={t === 0 ? 0.6 : 0.1} />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="currentColor" fillOpacity={0.6}>{num(t / 1e4, 0)}</text>
          </g>
        ))}
        {rows.map((r) => {
          const v = r.krw_per_tco2, mid = (x(r.x0) + x(r.x1)) / 2
          return (
            <g key={r.key}>
              <rect x={x(r.x0) + 1} width={Math.max(x(r.x1) - x(r.x0) - 2, 1)} y={y(Math.max(v, 0))} height={Math.abs(y(v) - y(0))} rx="3" style={{ fill: r.way === "추가" ? "var(--clean)" : "var(--grid)" }} />
              <line x1={mid} x2={mid} y1={y(r.lo)} y2={y(r.hi)} stroke="currentColor" strokeWidth="1.5" />
              <line x1={mid - 5} x2={mid + 5} y1={y(r.lo)} y2={y(r.lo)} stroke="currentColor" strokeWidth="1.5" />
              <line x1={mid - 5} x2={mid + 5} y1={y(r.hi)} y2={y(r.hi)} stroke="currentColor" strokeWidth="1.5" />
              <text x={mid} y={y(Math.max(r.hi, v)) - 18} textAnchor="middle" fontSize="12" fontWeight="600" fill="currentColor">{SHORT[r.key]}</text>
              <text x={mid} y={y(Math.max(r.hi, v)) - 5} textAnchor="middle" fontSize="11" fill="currentColor" fillOpacity={0.7}>{num(v / 1e4, 1)}만 원</text>
              <text x={x(r.x1)} y={H - B + 14} textAnchor={r.x1 >= total - 1e-9 ? "end" : "middle"} fontSize="11" fill="currentColor" fillOpacity={0.6}>{num(r.x1, 1)}</text>
            </g>
          )
        })}
        {lines.map((l) => (
          <g key={l.label}>
            <line x1={L} x2={W - RT} y1={y(l.v)} y2={y(l.v)} stroke="currentColor" strokeOpacity={0.55} strokeDasharray="5 4" />
            <text x={L + 4} y={y(l.v) - 4} fontSize="11" fill="currentColor" fillOpacity={0.75} paintOrder="stroke" stroke="var(--background)" strokeWidth="3">{l.label}</text>
          </g>
        ))}
        <text x={L} y={H - 4} fontSize="11" fill="currentColor" fillOpacity={0.6}>누적 감축량 (백만 tCO2/년) →</text>
        <text x={4} y={14} fontSize="11" fill="currentColor" fillOpacity={0.6}>감축 1t당 전력비용 (만 원)</text>
      </svg>
      <figcaption className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><i className="size-3 rounded-sm bg-grid" />전부: 전력비용 전체 ÷ 순 저감 (원료비 절감 미반영, 상한 쪽)</span>
        <span className="inline-flex items-center gap-1.5"><i className="size-3 rounded-sm bg-clean" />추가: PPA 할증 ÷ 줄어든 Scope 2</span>
      </figcaption>
    </figure>
  )
}

/** 감축 비용 곡선(abatement_curve): 조치별 감축 1t당 전력비용, 탄소 가격별로 덮이는 감축량, 수소환원 전력 조달별 비교. 숫자는 모두 결과값 그대로 */
function AbatementView({ out }: { out: Out }) {
  const x = out.result, a = x.applied_input, th = x.thresholds, first = x.curve[0]
  const lines = x.pays.map((p: Out) => ({ label: `${p.name} ${num(p.price / 1e4, 2)}만`, v: p.price }))
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        전기로 연 {plain(a.eaf_output_mt * 100)}만 t, 수소환원 연 {plain(a.h2_output_mt * 100)}만 t, 직접PPA {plain(a.ppa_krw_kwh)}원/kWh, 전력배출계수 {plain(a.grid_factor)}, 요금제 {a.plan}
      </p>
      <div className="space-y-1 rounded-xl border-l-4 border-clean bg-clean/10 p-4">
        <p className="text-sm text-muted-foreground">탄소 1t을 가장 싸게 줄이는 조치</p>
        <p className="text-3xl font-semibold tracking-tight">{SHORT[first.key]} <span className="text-lg font-normal text-muted-foreground">{num(first.krw_per_tco2, 0)}원/tCO2</span></p>
        <p className="text-sm leading-6 text-muted-foreground">{x.summary[x.summary.length - 2]}</p>
      </div>
      <MaccChart rows={x.curve} lines={lines} />
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="px-3 py-2 font-medium">조치 (싼 순서)</th>
              <th className="px-3 py-2 text-right font-medium">감축 1t당 전력비용<br />(원, 범위)</th>
              <th className="px-3 py-2 text-right font-medium">연 감축량<br />(백만 tCO2)</th>
              <th className="px-3 py-2 text-right font-medium">전력비용<br />(억 원/년)</th>
              <th className="px-3 py-2 text-right font-medium">재생에너지<br />(TWh/년)</th>
            </tr>
          </thead>
          <tbody>
            {x.curve.map((r: Out) => (
              <tr key={r.key} className="border-t border-border align-top">
                <td className="px-3 py-2">{r.name}<Badge variant="secondary" className="ml-2 h-5 px-2 text-xs">{r.way}</Badge></td>
                <td className="px-3 py-2 text-right">{num(r.krw_per_tco2, 0)}<span className="block text-xs text-muted-foreground">{num(r.lo, 0)} ~ {num(r.hi, 0)}</span></td>
                <td className="px-3 py-2 text-right">{num(r.abate_mt)}</td>
                <td className="px-3 py-2 text-right">{num(r.cost_eok, 0)}</td>
                <td className="px-3 py-2 text-right">{num(r.re_twh)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Figures>
        {x.pays.map((p: Out) => (
          <Figure key={p.name} title={`${p.name} ${plain(p.price)}원/tCO2에서 덮이는 감축`} value={num(p.abate_mt)} unit="백만 tCO2/년" main={p.abate_mt > 0}
            sub={p.measures.length ? `${p.measures.map((k: string) => SHORT[k]).join(", ")}까지` : "전력비용을 덮는 조치 없음"} />
        ))}
        <Figure title="직접PPA가 한전보다 싸지는 계약 단가" value={num(th.ppa_parity_krw_kwh, 0)} unit="원/kWh" sub={`한전 kWh당 ${num(th.unit_grid_krw_kwh, 1)}원, 직접PPA 부대비용 포함 ${num(th.unit_ppa_krw_kwh, 1)}원. 이보다 싸면 감축 비용이 음수`} />
        <Figure title="곡선 전체에 필요한 재생에너지" value={num(th.re_twh_total)} unit="TWh/년" sub="연간 계약 물량 기준. 확보량이 곡선을 쌓을 수 있는 상한" />
      </Figures>
      <section className="space-y-3">
        <h3 className="text-lg font-semibold">수소환원을 한다면: 전력 조달별 비교</h3>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="px-3 py-2 font-medium">전력 조달</th>
                <th className="px-3 py-2 text-right font-medium">감축 1t당 전력비용<br />(원, 범위)</th>
                <th className="px-3 py-2 text-right font-medium">쇳물 1t당 전력비용<br />(원)</th>
                <th className="px-3 py-2 text-right font-medium">1t당 순 저감<br />(tCO2)</th>
              </tr>
            </thead>
            <tbody>
              {x.h2_compare.map((r: Out) => (
                <tr key={r.key} className="border-t border-border align-top">
                  <td className="px-3 py-2">{r.name.replace("수소환원: ", "")}</td>
                  <td className="px-3 py-2 text-right">{num(r.krw_per_tco2, 0)}<span className="block text-xs text-muted-foreground">{num(r.lo, 0)} ~ {num(r.hi, 0)}</span></td>
                  <td className="px-3 py-2 text-right">{num(r.krw_per_t_steel, 0)}</td>
                  <td className="px-3 py-2 text-right">{num(r.abate_per_t_steel)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">{x.summary[x.summary.length - 1]}. 쇳물 1t 기준 비교(탄소 비용 포함)는 '그린 수소 vs 전력망 전기'에서 볼 수 있습니다.</p>
      </section>
      <p className="text-sm leading-6 text-muted-foreground">범위: {x.range_basis.note}. PPA {x.range_basis.ppa_krw_kwh.join("~")}원, 배출계수 {x.range_basis.grid_factor.join("~")}.</p>
    </div>
  )
}

const LIMITS: Record<ToolName, (out: Out) => string[]> = {
  min_green: (o) => [o.result.note, "확보 가능한 무탄소 전력은 직접 넣는 가정값입니다. 사내 공급 계획은 알 수 없습니다.", "전력 원단위는 수전해 수소까지 포함한 문헌값(Vogl·Bhaskar)으로, 포스코가 실측한 값이 아닙니다.", COST_NOTE],
  close_gap: (o) => [o.result.note, "확보 가능한 무탄소 전력은 직접 넣는 가정값입니다. 사내 공급 계획은 알 수 없습니다.", "조건을 한 번에 하나씩만 바꾼 값입니다. 전환 비용과 시점은 반영하지 않았습니다.", COST_NOTE],
  simulate: (o) => ["신뢰도가 낮은 가정 (시뮬레이터 LOW_CONF)", ...o.result.assumptions],
  compare_paths: () => ["필요 생산량은 100만 t 기준 결과를 비례로 환산했습니다(target.required_output).", "'상한 초과'가 붙은 경로는 필요 생산량이 시뮬레이터 상한인 250만 t/년보다 큽니다.", COST_NOTE],
  h2_supply: (o) => [o.result.note, ...o.result.assumptions],
  abatement_curve: (o) => [o.result.note, ...o.result.assumptions, o.result.range_basis.note],
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
          {hit.name === "simulate" ? <SimulateView out={output} /> : hit.name === "compare_paths" ? <CompareView input={input} out={output} /> : hit.name === "h2_supply" ? <H2SupplyView out={output} /> : hit.name === "abatement_curve" ? <AbatementView out={output} /> : <MinGreenView tool={hit.name} input={input} out={output} spread={spread} />}
        </div>
        <details open className="border-t border-border py-3">
          <summary className="cursor-pointer text-sm font-medium select-none">조건 바꾸기</summary>
          <div className="pt-4"><ToolForm tool={hit.name} info={info} input={input} onRun={run} /></div>
        </details>
        <Fold title="출처">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {Object.entries<any>({ ...(output.sources ?? {}), ...(hit.name === "h2_supply" || hit.name === "abatement_curve" ? output.result.sources : {}) }).map(([k, s]) => <li key={k}><b className="text-foreground">{k}</b>: {s}</li>)}
          </ul>
        </Fold>
        <Fold title="한계와 가정">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{LIMITS[hit.name](output).map((s) => <li key={s}>{s}</li>)}</ul>
        </Fold>
      </CardContent>
    </Card>
  )
}
