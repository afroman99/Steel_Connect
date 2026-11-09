"""AI 어시스턴트가 호출하는 계산 도구 (JSON 입출력). 계산은 코드, 해석은 LLM.
call_tool(이름, 인자 dict) -> {"status": "ok"|"ask"|"refuse", ...}. 어시스턴트 규칙:
- ask: 필수 입력이 없음 -> missing을 사용자에게 되묻는다. refuse: 허용 범위 밖·모르는 변수 -> 이유와 함께 답변을 유보한다.
- ok: result의 숫자만 인용한다. defaults_used는 사용자가 안 정해 기본값으로 계산한 변수이므로 답변에 가정으로 밝힌다. sources로 출처를 붙인다."""

from dataclasses import fields

from src.abatement import abatement_curve
from src.hydrogen import h2_supply
from src.simulator import PLANS, RANGE, SOURCES, Scenario, breakeven_grid, simulate
from src.target import SWEEP_VARS, close_gap, compare_paths, min_green, required_output, sweep_green

# fmt: off
VARS = [f.name for f in fields(Scenario)]
REQUIRED = {"simulate": ["eaf_mt 또는 h2_mt"], "required_output": ["target_abate_t", "path"], "min_green": ["h2_output_mt", "target_abate_t"], "sweep_green": ["h2_output_mt", "target_abate_t", "vary", "values"], "close_gap": ["h2_output_mt", "target_abate_t", "green_supply_twh"], "compare_paths": ["target_abate_t"], "breakeven_grid": [], "h2_supply": ["h2_output_mt"], "abatement_curve": []}
TOOLS = {  # LLM 도구 정의용 설명. 변수 의미·단위·허용 범위는 reports/결과보고서.md 부록 E-1
 "simulate": "시나리오 계산: 추가 전력(TWh)·탄소(tCO2)·요금(억 원). 인자는 Scenario 변수(eaf_mt, h2_mt, eaf_util, grid_factor, plan, ets_price 등).",
 "required_output": "목표 순 저감(target_abate_t, tCO2/년)을 달성하는 필요 생산량·전력·요금. path는 'eaf' 또는 'h2'(h2_green 등 추가 가능).",
 "min_green": "수소환원 생산량(h2_output_mt)으로 목표 순 저감을 달성하는 최소 무탄소 비율·전력량·부족분(green_supply_twh는 사용자 가정).",
 "sweep_green": "min_green을 한 조건만 바꿔가며 반복(vary: green_supply_twh, h2_kwh_t, grid_factor, h2_resid_t, target_abate_t, h2_output_mt 중 하나, values: 값 목록). 확보량·효율 조건 비교용.",
 "close_gap": "무탄소 전력이 부족할 때, 조건을 하나씩만 바꿔 부족분을 0으로 만드는 값을 역산: 확보량·목표·생산량·전력 원단위·배출계수·전기로 전환. 인자: h2_output_mt, target_abate_t, green_supply_twh(사용자 가정, 필수). levers 각 항목의 now(현재)→needed(필요), in_range(허용 범위 안인지), kind(결정/외부).",
 "compare_paths": "같은 목표 순 저감을 전기로·수소환원(전력망·무탄소 50%·100%)으로 달성할 때 비교.",
 "breakeven_grid": "수소환원이 고로보다 배출을 늘리기 시작하는 전력배출계수. 인자: h2_kwh_t, bf_t, resid_t.",
 "h2_supply": "수소환원에 쓸 수소를 그린 수소(재생에너지 직접PPA 수전해)로 만들지 전력망 전기로 만들지 비교·추천. 인자: h2_output_mt(필수), ets_price(탄소 가격 가정, 기본 KAU26 시세 29,500), ppa_krw_kwh(직접PPA 단가, 기본 180), grid_factor, green_supply_twh, target_abate_t 등. verdict(추천·이유), conditions(그린/전력망이 유리한 경우), thresholds(갈림길 값), map(배출계수 x 탄소 가격 추천 지도).",
 "abatement_curve": "감축 비용 곡선: 탄소 1t을 줄이는 데 드는 전력비용(원/tCO2)을 조치별로 싼 순서로. 조치: 전기로 전환, 한전 전력(기존 구매 + 전기로)을 직접PPA로 전환, 수소환원(전력 100% 직접PPA). 수소환원 전력 조달별(전력망·그린 수소·100% PPA) 비교 포함. 인자: eaf_output_mt(전기로 실제 생산량, 기본 1.75), h2_output_mt(수소환원 실제 생산량, 기본 1.0), ppa_krw_kwh(기본 180), ets_price(그 탄소 가격에서 덮이는 감축량), grid_factor, plan 등. curve, h2_compare, pays(탄소 가격별 덮이는 감축량), thresholds, summary.",
}
_ENUM = {"band_rule": ["2025", "B"], "plan": list(PLANS), "eaf_basis": ["bottom_up", "posco_net"]}
_NUM = lambda d: dict(type="number", description=d)
_SIM = {f.name: (dict(type="string", enum=_ENUM[f.name]) if f.name in _ENUM else dict(type="number", **({"description": f"허용 범위 {RANGE[f.name][0]}~{RANGE[f.name][1]}"} if f.name in RANGE else {}))) for f in fields(Scenario)}
TOOL_SCHEMAS = {  # JSON Schema(입력 형식). 어떤 LLM SDK에서든 도구 정의의 input_schema로 쓸 수 있다
 "simulate": dict(type="object", properties=_SIM),
 "required_output": dict(type="object", required=["target_abate_t", "path"], properties=dict(target_abate_t=_NUM("목표 순 저감 tCO2/년"), path=dict(type="string", enum=["eaf", "h2"]),
                         h2_green=_NUM("수소환원 무탄소 전력 비율 0~1"), grid_factor=_NUM("전력배출계수"), plan=_SIM["plan"], ets_price=_NUM("배출권 가격 가정 원/t"))),
 "min_green": dict(type="object", required=["h2_output_mt", "target_abate_t"], properties=dict(h2_output_mt=_NUM("수소환원 연 생산량 백만 t"), target_abate_t=_NUM("목표 순 저감 tCO2/년"),
                   green_supply_twh=_NUM("확보 가능한 무탄소 전력 TWh(사용자 가정)"), h2_kwh_t=_NUM("전력 원단위 kWh/t"), grid_factor=_NUM("전력배출계수"), h2_resid_t=_NUM("잔여 직접 배출 t/t"))),
 "sweep_green": dict(type="object", required=["h2_output_mt", "target_abate_t", "vary", "values"], properties=dict(h2_output_mt=_NUM("백만 t"), target_abate_t=_NUM("tCO2/년"), vary=dict(type="string", enum=list(SWEEP_VARS)),
                     values=dict(type="array", items=dict(type="number"), description="vary에 넣을 값 목록(최대 50)"), green_supply_twh=_NUM("TWh"))),
 "close_gap": dict(type="object", required=["h2_output_mt", "target_abate_t", "green_supply_twh"], properties=dict(h2_output_mt=_NUM("수소환원 연 생산량 백만 t"), target_abate_t=_NUM("목표 순 저감 tCO2/년"),
                    green_supply_twh=_NUM("확보 가능한 무탄소 전력 TWh(사용자 가정)"), h2_kwh_t=_NUM("전력 원단위 kWh/t"), grid_factor=_NUM("전력배출계수"), h2_resid_t=_NUM("잔여 직접 배출 t/t"))),
 "compare_paths": dict(type="object", required=["target_abate_t"], properties=dict(target_abate_t=_NUM("목표 순 저감 tCO2/년"), grid_factor=_NUM("전력배출계수"))),
 "breakeven_grid": dict(type="object", properties=dict(h2_kwh_t=_NUM("kWh/t"), bf_t=_NUM("고로 배출 t/t"), resid_t=_NUM("잔여 배출 t/t"))),
 "h2_supply": dict(type="object", required=["h2_output_mt"], properties=dict(h2_output_mt=_NUM("수소환원 연 생산량 백만 t"), ets_price=_NUM("탄소(배출권) 가격 가정 원/tCO2, 허용 7,000~160,000"),
                   ppa_krw_kwh=_NUM("직접PPA 계약 단가 원/kWh, 허용 130~190"), grid_factor=_NUM("전력배출계수"), green_supply_twh=_NUM("확보 가능한 재생에너지 TWh(사용자 가정)"), target_abate_t=_NUM("목표 순 저감 tCO2/년"),
                   h2_kg_t=_NUM("쇳물 1t당 수소 kg, 허용 40~60"), elec_kwh_kg=_NUM("수전해 전력 kWh/kg, 허용 45~58"), green_h2_krw_kg=_NUM("구매 그린수소 단가 원/kg(참고 비교용)"), h2_kwh_t=_NUM("수소환원 전력 원단위 kWh/t"), plan=_SIM["plan"])),
 "abatement_curve": dict(type="object", properties=dict(eaf_output_mt=_NUM("전기로 연 실제 생산량 백만 t(기본 1.75 = 250만 t x 가동률 70%)"), h2_output_mt=_NUM("수소환원 연 실제 생산량 백만 t(기본 1.0)"),
                         ppa_krw_kwh=_NUM("직접PPA 계약 단가 원/kWh, 허용 130~190"), ets_price=_NUM("탄소(배출권) 가격 가정 원/tCO2, 허용 7,000~160,000. 주면 그 가격에서 덮이는 감축량 계산"),
                         grid_factor=_NUM("전력배출계수"), h2_kwh_t=_NUM("수소환원 전력 원단위 kWh/t"), plan=_SIM["plan"])),
}
SYSTEM_PROMPT = """너는 '제철공정의 저탄소 전환을 돕는 AI 어시스턴트'(팀 스틸커넥트)다. 전기로·수소환원제철로 전환할 때의 전력·요금·탄소 시나리오를 다룬다. 자기소개를 요청받으면 이 이름과 역할로 소개한다. 모든 숫자는 도구로 계산하고, 직접 계산하거나 추정하지 않는다.
- 도구 결과 status가 ask면 missing을 사용자에게 한 번에 되묻는다. 추측해서 채우지 않는다. 생산 규모나 목표 감축량이 없으면 반드시 묻는다.
- refuse면 reason을 설명하고 답변을 유보한다. 범위 밖 값을 임의로 바꿔 다시 계산하지 않는다.
- ok면 result의 숫자만 인용한다. null은 0이 아니라 해당 모델에서 분해하지 않은 값이다. feasible은 수학적 계산 가능 여부이며 실제 실행 가능성을 보장하지 않는다. status와 within_capacity를 함께 확인한다. defaults_used(사용자가 정하지 않아 기본값으로 계산한 변수)는 가정으로 밝히고, sources 중 쓴 것을 출처로 붙인다.
- 도구가 없는 질문은 도구를 부르지 않고 근거 부족으로 거절한다: 미래 예측, 사내 실제 데이터, 투자비·회수기간, 실제 배출권 회피액, 미래 요금 인상률, 시간대별 공급으로 생산이 멈추는지 여부.
  실제 회피액 질문에는 가정 가격(ets_price)을 주면 참고 가치는 계산할 수 있다고 안내한다.
- 부족분이 있으면(met=false) 되묻지 말고 close_gap으로 "무엇을 얼마나 바꾸면 메워지는가"를 보여 준다. 확보량(green_supply_twh)을 모르면 먼저 묻는다. levers를 결정(우리가 정함)·외부(바깥 조건)로 나눠 설명하고, in_range=false는 현재 모델 지원 범위 밖이라고 밝힌다. category가 goal_change이면 원래 목표를 낮춘 별도 안이고, production_change이면 생산량을 바꾼 안이라고 설명한다. technical_target은 달성 여부를 기술 검토할 목표이며 external_scenario는 직접 결정할 수 없는 외부 조건이다. 한 번에 한 조건만 바꾼 값이며 조합은 계산하지 않았음을 밝힌다. 생산량 레버는 같은 목표를 더 큰 규모로 나누면 톤당 필요 감축이 줄어서 필요량이 준다는 뜻이다.
- 그린 수소와 전력망 전기 중 무엇이 나은지 물으면 h2_supply를 부른다. 생산량을 모르면 묻는다. verdict.reason을 결론으로, conditions.green·conditions.grid를 "그린 수소가 좋은 경우/전력망 전기가 좋은 경우"로 인용한다. 각 조건은 다른 값은 그대로 두고 하나만 바꿨을 때의 갈림길이다. 탄소 가격·PPA 단가 기본값(K-ETS 시세, 태양광 PPA 175~185원 구간)은 가정으로 밝힌다. offpeak·buy는 참고 선택지라 추천 비교에서 빠졌고 설비비·저장비가 없다는 점을 밝힌다. 추천은 연간 계약 기준 그린이고, hourly는 시간 일치(같은 시간 재생에너지만 인정) 기준 참고값이라는 점을 구분해 말한다.
- 어떤 감축 수단이 탄소 1t당 싼지, 탄소 가격으로 어디까지 감당되는지 물으면 abatement_curve를 부른다. 1t당 비용은 규모와 무관하므로 규모를 몰라도 기본값으로 계산하되, 감축량(백만 tCO2)은 규모 가정(전기로 175만 t, 수소환원 100만 t)에 따른 값이라고 밝힌다. summary를 결론으로 인용하고, way가 '전부'인 값(전기로·수소환원)은 고로 원료비 절감이 빠진 상한 쪽 값이고 '추가'(직접PPA 전환)는 같은 설비에서 전력 조달만 바꾼 값이라고 구분한다. 범위(lo~hi)는 PPA 130~190원 x 배출계수 0.245~0.4524 조합이다. "쇳물 1t당 비용"(h2_supply)과 "감축 1t당 비용"(abatement_curve)은 순위가 다를 수 있으니 어느 기준인지 밝힌다.
- 항상 밝힌다: 조건부 시나리오이며 예측이 아니다. 부족분은 연간 전력량 기준이라 시간대별 공급·저장은 반영하지 않았고 생산 지속 여부를 판단하지 않는다. 요금은 전력 요금만이다. 배출권 가치는 참고 가치다.
- 한국어로 답한다. 숫자에는 단위를 붙이고, 전문용어 뒤에는 짧은 설명을 붙인다."""
FUNCS = {"simulate": simulate, "required_output": required_output, "min_green": min_green, "sweep_green": sweep_green, "close_gap": close_gap, "compare_paths": compare_paths, "breakeven_grid": breakeven_grid, "h2_supply": h2_supply, "abatement_curve": abatement_curve}


def call_tool(name, args=None):
    args = dict(args or {})
    if name not in FUNCS:
        return dict(status="refuse", reason=f"알 수 없는 도구 {name!r}", tools=list(FUNCS))
    if name == "simulate" and not {"eaf_mt", "h2_mt"} & args.keys():
        return dict(status="ask", missing=REQUIRED[name])
    miss = [k for k in REQUIRED[name] if " " not in k and k not in args]
    if miss:
        return dict(status="ask", missing=miss)
    if name == "simulate" and (bad := [k for k in args if k not in VARS]):
        return dict(status="refuse", reason=f"알 수 없는 변수 {bad}", variables=VARS)
    try:
        res = FUNCS[name](**args)
    except TypeError as e:
        return dict(status="refuse", reason=f"인자 오류: {e}")
    except ValueError as e:
        return dict(status="refuse", reason=str(e))
    out = dict(status="ok", tool=name, result=res, sources=SOURCES)
    if name == "simulate":
        out["defaults_used"] = {k: v for k, v in res["input"].items() if k not in args}
    elif isinstance(res, dict) and "applied_input" in res:
        out["effective_input"] = res["applied_input"]
        # These are effective calculation conditions, including values solved by the tool.
        out["defaults_used"] = {k: v for k, v in res["applied_input"].items()
                                if k not in args and k not in ("eaf_mt", "h2_mt", "h2_util", "eaf_util", "h2_green") }
    return out
