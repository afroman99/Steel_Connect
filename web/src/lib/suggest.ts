import { man, plain } from "./format"
import type { Hit, Info, ToolName, Out } from "./types"

export type Suggestion = [label: string, tool: ToolName, args: Out]
const GF_WHATIF = 0.3 // 전력배출계수 가정값. 허용 범위(0.2~0.56) 안의 둥근 값

// 이어서 해 볼 조건. 바꾸는 값은 입력 가정이고, 결과는 다시 계산 도구(/api/calc)가 낸다
export function suggest(hit: Hit, info: Info | null): Suggestion[] {
  const a = hit.input, x = hit.output.result, out: Suggestion[] = []
  const gf = !(a.grid_factor <= GF_WHATIF), gfArgs = a.grid_factor === undefined ? {} : { grid_factor: a.grid_factor }
  if (hit.name === "min_green" || hit.name === "close_gap") {
    const cur = a.green_supply_twh || 0 // 처음엔 필요량의 절반쯤, 이미 확보량이 있으면 필요량(0.1 TWh 단위 올림)까지
    const s = cur > 0 ? Math.ceil(x.green_twh * 10) / 10 : Math.max(0.1, Math.round(x.green_twh * 5) / 10)
    if (x.feasible && x.gap_twh > 0 && s !== cur) out.push([cur > 0 ? `무탄소 전력을 ${plain(s)} TWh까지 늘리면?` : `무탄소 전력 ${plain(s)} TWh를 확보했다면?`, "min_green", { ...a, green_supply_twh: s }])
    if (hit.name === "min_green" && x.feasible && x.gap_twh > 0 && cur > 0) out.push(["부족분을 메우려면 무엇을 바꿔야 해?", "close_gap", { ...a }])
    if (gf) out.push([`전력배출계수 ${GF_WHATIF}을 가정하면?`, hit.name, { ...a, grid_factor: GF_WHATIF }])
    out.push(["같은 목표를 전기로와 비교하면?", "compare_paths", { target_abate_t: a.target_abate_t, ...gfArgs }])
    out.push([`목표를 ${man(a.target_abate_t * 2)}만 t로 두 배 올리면?`, hit.name, { ...a, target_abate_t: a.target_abate_t * 2 }])
  }
  if (hit.name === "simulate") {
    if (a.eaf_mt > 0 && (a.eaf_util ?? info?.defaults.eaf_util) < 1) out.push(["전기로 가동률이 100%면?", "simulate", { ...a, eaf_util: 1 }])
    if (!(a.h2_mt > 0)) out.push(["수소환원 30만 t(무탄소 전력 100%)을 더하면?", "simulate", { ...a, h2_mt: 0.3, h2_green: 1 }])
    if (a.ets_price == null) out.push(["배출권 가격을 2만 원/t로 가정하면?", "simulate", { ...a, ets_price: 20000 }])
    if (gf) out.push([`전력배출계수 ${GF_WHATIF}을 가정하면?`, "simulate", { ...a, grid_factor: GF_WHATIF }])
  }
  if (hit.name === "h2_supply") {
    const eua = info?.h2_defaults?.eua_krw, base = { ...a }
    if (eua && a.ets_price !== eua) out.push([`탄소 가격이 EU 수준(${plain(eua)}원/t)이면?`, "h2_supply", { ...base, ets_price: eua }])
    if (gf) out.push([`전력배출계수 ${GF_WHATIF}을 가정하면?`, "h2_supply", { ...base, grid_factor: GF_WHATIF }])
    if (a.ppa_krw_kwh !== 150) out.push(["재생에너지 PPA가 150원/kWh(정부 태양광 목표 발전단가)이면?", "h2_supply", { ...base, ppa_krw_kwh: 150 }])
    if (a.target_abate_t == null) out.push([`순 저감 목표 ${man(a.h2_output_mt * 1e6)}만 t(쇳물 1t당 1t)를 두면?`, "h2_supply", { ...base, target_abate_t: a.h2_output_mt * 1e6 }])
  }
  if (hit.name === "compare_paths") {
    if (gf) out.push([`전력배출계수 ${GF_WHATIF}을 가정하면?`, "compare_paths", { ...a, grid_factor: GF_WHATIF }])
    out.push(["수소환원 50만 t으로 이 목표를 내려면 무탄소 전력은?", "min_green", { h2_output_mt: 0.5, target_abate_t: a.target_abate_t, ...gfArgs }])
    out.push([`목표를 ${man(a.target_abate_t / 2)}만 t로 절반 줄이면?`, "compare_paths", { ...a, target_abate_t: a.target_abate_t / 2 }])
  }
  return out.slice(0, 3)
}
