export const num = (v: number, d = 2) => Number(v).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d })
export const man = (v: number) => num(v / 1e4, 1) // tCO2 -> 만 tCO2 (표시 단위 변환)
export const plain = (v: number) => Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 4 })

export const LABEL: Record<string, string> = {
  eaf_mt: "전기로 생산 능력(백만 t/년)", eaf_kwh_t: "전기로 전력 원단위(kWh/t)", eaf_util: "전기로 가동률", selfgen_cut: "자체발전 감소 비율", grid_factor: "전력배출계수(tCO2/MWh)",
  price_change: "요금 변동률", band_rule: "요금 시간대 규칙", load_factor: "부하율", plan: "요금제", fund: "전력산업기반기금 요율", ets_price: "배출권 가격 가정(원/tCO2)",
  adder: "기후환경·연료비조정요금(원/kWh)", total_twh: "제철소 총 전력(TWh)", bf_replace: "고로 대체 비율", bf_tco2_t: "고로 Scope 1 배출(tCO2/t)", eaf_direct_t: "전기로 직접 배출(tCO2/t)",
  eaf_basis: "전기로 감축 경계", h2_mt: "수소환원 생산 능력(백만 t/년)", h2_util: "수소환원 가동률", h2_kwh_t: "수소환원 전력 원단위(kWh/t)", h2_green: "수소환원 무탄소 전력 비율",
  h2_bf_t: "대체 고로 배출(tCO2/t)", h2_resid_t: "수소환원 잔여 배출(tCO2/t)", h2_output_mt: "수소환원 연 생산량", target_abate_t: "목표 순 저감", green_supply_twh: "확보 가능한 무탄소 전력",
  path: "경로", vary: "바꿀 조건", values: "값 목록", "eaf_mt 또는 h2_mt": "전기로 또는 수소환원 생산 능력",
  ppa_krw_kwh: "직접PPA 계약 단가(원/kWh)", h2_kg_t: "쇳물 1t당 수소(kg)", elec_kwh_kg: "수전해 전력(kWh/kg)", green_h2_krw_kg: "구매 그린수소 단가(원/kg)",
  eaf_output_mt: "전기로 연 생산량(백만 t)",
}
export const label = (k: string) => LABEL[k] ?? k
export const TITLE = { min_green: "필요 무탄소 전력", close_gap: "부족분을 메우려면", simulate: "전환 시나리오", compare_paths: "경로 비교", h2_supply: "그린 수소 vs 전력망 전기", abatement_curve: "감축 비용 곡선" } as const

// close_gap 레버의 값을 사람이 읽는 단위로 바꾼다(표시용 변환만, 계산 아님)
export function leverValue(name: string, v: number | null | undefined) {
  if (v == null) return "-"
  if (name === "target_abate_t") return `${man(v)}만 t`
  if (name === "h2_output_mt" || name === "switch_to_eaf") return `${num(v * 100, 1)}만 t/년`
  if (name === "green_supply_twh") return `${num(v)} TWh`
  if (name === "h2_kwh_t") return `${plain(Math.round(v))} kWh/t`
  if (name === "grid_factor") return `${num(v, 4)}`
  return plain(v)
}

export const LLM_NAME: Record<string, string> = { api: "Anthropic API", bedrock: "Amazon Bedrock", gemini: "Google Gemini", groq: "Groq", ollama: "내 PC의 Ollama", custom: "OpenAI 호환 API", claude_code: "Claude Code" }
