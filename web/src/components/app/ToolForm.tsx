import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { label, plain } from "@/lib/format"
import type { Info, Out, ToolName } from "@/lib/types"

// 입력칸 정의. scale은 화면 단위 -> 계산 단위 변환(예: 만 t -> 백만 t은 0.01). 값은 입력 가정이며 결과는 항상 계산 도구가 낸다
type Num = { kind: "num"; name: string; label: string; scale?: number; range?: string; rangeScale?: number; rangeUnit?: string; note?: string; blank?: string }
type Sld = { kind: "slider"; name: string; label: string; step: number; fmt: "mt" | "pct" | "gf"; range: string; note?: string }
type Sel = { kind: "select"; name: string; label: string; note?: string }
type Field = Num | Sld | Sel

const MIN_GREEN: Field[] = [
  { kind: "num", name: "h2_output_mt", label: "수소환원 연 생산량 (만 t)", scale: 0.01, range: "h2_mt", rangeScale: 100, rangeUnit: "만 t" },
  { kind: "num", name: "target_abate_t", label: "목표 순 저감 (만 tCO2/년)", scale: 10000, note: "고로 대비 순 저감" },
  { kind: "num", name: "green_supply_twh", label: "확보 가능한 무탄소 전력 (TWh/년)", note: "직접 넣는 가정값. 사내 공급 계획은 모름" },
  { kind: "num", name: "grid_factor", label: "전력배출계수 (tCO2/MWh)", range: "grid_factor", blank: "기본" },
  { kind: "num", name: "h2_kwh_t", label: "수소환원 전력 원단위 (kWh/t)", range: "h2_kwh_t", blank: "기본" },
  { kind: "num", name: "h2_resid_t", label: "수소환원 잔여 배출 (tCO2/t)", range: "h2_resid_t", blank: "기본" },
]
const FIELDS: Record<ToolName, Field[]> = {
  min_green: MIN_GREEN,
  close_gap: MIN_GREEN,
  simulate: [
    { kind: "slider", name: "eaf_mt", label: "전기로 생산 능력", step: 0.05, fmt: "mt", range: "eaf_mt" },
    { kind: "slider", name: "eaf_util", label: "전기로 가동률", step: 0.05, fmt: "pct", range: "eaf_util" },
    { kind: "slider", name: "h2_mt", label: "수소환원 생산 능력", step: 0.05, fmt: "mt", range: "h2_mt" },
    { kind: "slider", name: "h2_green", label: "수소환원 무탄소 전력 비율", step: 0.05, fmt: "pct", range: "h2_green" },
    { kind: "slider", name: "grid_factor", label: "전력배출계수", step: 0.0001, fmt: "gf", range: "grid_factor" },
    { kind: "slider", name: "selfgen_cut", label: "자체발전 감소 비율", step: 0.01, fmt: "pct", range: "selfgen_cut", note: "고로 축소로 줄어드는 자체발전" },
    { kind: "select", name: "plan", label: "요금제", note: "고압A/B/C + 선택Ⅰ~Ⅲ" },
    { kind: "num", name: "ets_price", label: "배출권 가격 가정 (원/tCO2)", range: "ets_price", blank: "비우면 계산 안 함" },
  ],
  compare_paths: [
    { kind: "num", name: "target_abate_t", label: "목표 순 저감 (만 tCO2/년)", scale: 10000 },
    { kind: "num", name: "grid_factor", label: "전력배출계수 (tCO2/MWh)", range: "grid_factor", blank: "기본" },
  ],
  h2_supply: [
    { kind: "num", name: "h2_output_mt", label: "수소환원 연 생산량 (만 t)", scale: 0.01, range: "h2_mt", rangeScale: 100, rangeUnit: "만 t" },
    { kind: "num", name: "ets_price", label: "탄소(배출권) 가격 (원/tCO2)", range: "ets_price", blank: "기본", note: "K-ETS 2.95만 원, EU ETS 13.2만 원 (2026-11-09). 최근 1년 K-ETS 1.0~3.1만 원(ICAP)" },
    { kind: "num", name: "ppa_krw_kwh", label: "재생에너지 직접PPA 단가 (원/kWh)", range: "ppa_krw_kwh", blank: "기본", note: "계약 단가. 망이용료 등 부대비용은 계산에서 더함" },
    { kind: "num", name: "grid_factor", label: "전력배출계수 (tCO2/MWh)", range: "grid_factor", blank: "기본" },
    { kind: "num", name: "green_supply_twh", label: "확보 가능한 재생에너지 (TWh/년)", blank: "비우면 제한 없음", note: "직접 넣는 가정값" },
    { kind: "num", name: "target_abate_t", label: "목표 순 저감 (만 tCO2/년)", scale: 10000, blank: "비우면 목표 없음", note: "고로 대비 순 저감" },
    { kind: "num", name: "h2_kg_t", label: "쇳물 1t당 수소 (kg)", range: "h2_kg_t", blank: "기본" },
    { kind: "num", name: "elec_kwh_kg", label: "수전해 전력 (kWh/kg)", range: "elec_kwh_kg", blank: "기본" },
    { kind: "select", name: "plan", label: "한전 요금제", note: "고압A/B/C + 선택Ⅰ~Ⅲ" },
  ],
  abatement_curve: [
    { kind: "num", name: "eaf_output_mt", label: "전기로 연 생산량 (만 t)", scale: 0.01, blank: "비우면 기본 175만 t", note: "실제 생산량. 기본은 광양 250만 t x 가동률 70%. 감축량(폭)만 바뀜" },
    { kind: "num", name: "h2_output_mt", label: "수소환원 연 생산량 (만 t)", scale: 0.01, range: "h2_mt", rangeScale: 100, rangeUnit: "만 t", blank: "비우면 기본 100만 t", note: "감축량(폭)만 바뀜" },
    { kind: "num", name: "ppa_krw_kwh", label: "재생에너지 직접PPA 단가 (원/kWh)", range: "ppa_krw_kwh", blank: "기본", note: "계약 단가. 망이용료 등 부대비용은 계산에서 더함" },
    { kind: "num", name: "ets_price", label: "탄소(배출권) 가격 (원/tCO2)", range: "ets_price", blank: "비우면 K-ETS·EU 시세만", note: "넣으면 그 가격에서 덮이는 감축량을 더 계산" },
    { kind: "num", name: "grid_factor", label: "전력배출계수 (tCO2/MWh)", range: "grid_factor", blank: "기본" },
    { kind: "select", name: "plan", label: "한전 요금제", note: "고압A/B/C + 선택Ⅰ~Ⅲ" },
  ],
}
const FMT = { mt: (v: number) => `${plain(v * 100)}만 t/년`, pct: (v: number) => `${plain(v * 100)}%`, gf: (v: number) => `${plain(v)} tCO2/MWh` }
const rangeText = (info: Info | null, f: Num | Sld) => {
  const r = f.range ? info?.ranges[f.range] : undefined
  if (!r) return ""
  const k = "rangeScale" in f ? (f.rangeScale ?? 1) : f.kind === "slider" && f.fmt !== "gf" ? 100 : 1
  const u = "rangeUnit" in f ? (f.rangeUnit ?? "") : f.kind === "slider" ? (f.fmt === "mt" ? "만 t" : f.fmt === "pct" ? "%" : "") : ""
  return `허용 ${plain(r[0] * k)}~${plain(r[1] * k)}${u ? " " + u : ""}`
}

export function ToolForm({ tool, info, input, onRun }: { tool: ToolName; info: Info | null; input: Out; onRun: (args: Out) => void }) {
  const fields = FIELDS[tool]
  const dflt = (name: string) => (tool === "h2_supply" || tool === "abatement_curve" ? info?.h2_defaults?.[name] : undefined) ?? info?.defaults[name] // h2_supply·abatement_curve는 기본값이 simulate와 다르다(PPA 단가 등)
  const initial = () => {
    const v: Record<string, string> = {}
    for (const f of fields) {
      const x = input[f.name]
      if (f.kind === "num") v[f.name] = x == null ? (f.name === "green_supply_twh" && tool !== "h2_supply" ? "0" : "") : String(+(x / (f.scale ?? 1)).toFixed(6))
      else v[f.name] = String(x ?? dflt(f.name) ?? "")
    }
    return v
  }
  const [vals, setVals] = useState(initial)
  const [err, setErr] = useState("")
  const timer = useRef<number | undefined>(undefined)
  const names = new Set(fields.map((f) => f.name))
  const extra = Object.fromEntries(Object.entries(input).filter(([k]) => !names.has(k))) // AI가 정했지만 입력칸이 없는 인자: 다시 계산할 때도 그대로 넘긴다

  const build = (v: Record<string, string>): Out | null => {
    const args: Out = {}
    for (const f of fields) {
      const s = (v[f.name] ?? "").trim()
      if (s === "") continue
      if (f.kind === "select") { args[f.name] = s; continue }
      const n = Number(s.replace(/,/g, ""))
      if (!Number.isFinite(n)) { setErr(`${f.label}: 숫자를 입력하세요.`); return null }
      args[f.name] = f.kind === "num" ? n * (f.scale ?? 1) : n
    }
    setErr("")
    return { ...extra, ...args }
  }
  const submit = (v = vals) => { const a = build(v); if (a) onRun(a) }
  const set = (name: string, value: string, run = false) => {
    const next = { ...vals, [name]: value }
    setVals(next)
    if (run) { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => submit(next), 250) }
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit() }} className="space-y-4">
      {Object.keys(extra).length > 0 && (
        <p className="text-sm text-muted-foreground">AI가 넣은 조건(입력칸에는 없고 다시 계산할 때도 씀): {Object.entries(extra).map(([k, v]) => `${label(k)} = ${JSON.stringify(v)}`).join(", ")}</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((f) => {
          const id = `f-${tool}-${f.name}`
          return (
            <div key={f.name} className="space-y-2">
              {f.kind === "slider" ? (
                <>
                  <div className="flex items-baseline justify-between gap-2 text-sm font-medium"><label htmlFor={id}>{f.label}</label><output className="text-muted-foreground">{FMT[f.fmt](Number(vals[f.name]))}</output></div>
                  <Slider id={id} aria-label={f.label} min={info?.ranges[f.range]?.[0] ?? 0} max={info?.ranges[f.range]?.[1] ?? 1} step={f.step} value={[Number(vals[f.name])]} onValueChange={([v]) => set(f.name, String(v), true)} />
                </>
              ) : f.kind === "select" ? (
                <>
                  <label htmlFor={id} className="text-sm font-medium">{f.label}</label>
                  <Select value={vals[f.name]} onValueChange={(v) => { const next = { ...vals, [f.name]: v }; setVals(next); submit(next) }}>
                    <SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>{(info?.plans ?? []).map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select>
                </>
              ) : (
                <>
                  <label htmlFor={id} className="text-sm font-medium">{f.label}</label>
                  <Input id={id} inputMode="decimal" value={vals[f.name]} placeholder={f.blank ? (f.blank === "기본" && info ? `비우면 기본 ${plain(dflt(f.name))}` : f.blank) : undefined} onChange={(e) => set(f.name, e.target.value)} />
                </>
              )}
              <p className="text-sm text-muted-foreground">{[f.note, "range" in f ? rangeText(info, f) : ""].filter(Boolean).join(". ")}</p>
            </div>
          )
        })}
      </div>
      <Button type="submit" variant="outline">다시 계산</Button>
      {err && <p role="alert" className="text-sm text-destructive">{err}</p>}
    </form>
  )
}
