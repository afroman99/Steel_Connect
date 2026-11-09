"""그린 수소 vs 전력망 전기: 수소환원제철에 쓸 수소를 무엇으로 만들지 비교하고, 조건에 따라 어느 쪽이 나은지 추천한다. 숫자는 모두 simulate(전력·탄소·요금)에서 나온다.
수소환원 전력 원단위 h2_kwh_t를 '수전해 = h2_kg_t x elec_kwh_kg'와 '공정 전력(가열·용융 등) = 나머지'로 나눠 선택지를 만든다.
  green   그린 수소: 수전해 전력을 재생에너지 직접PPA로 조달(배출 0). 공정 전력은 전력망.
  grid    전력망 전기: 수전해·공정 전력을 모두 한전 전력망에서 24시간 구매.
  offpeak 전력망 전기 경부하 운전(참고): 수전해만 경부하 시간에 몰아 돌린다. 설비 증설·수소 저장 비용이 빠져 추천 비교에서 제외.
  buy     구매 그린수소(참고): 국내 수전해 평균 생산원가로 사 온다. 생산자 설비비가 들어간 값이라 설비비가 빠진 green·grid와 같은 줄에서 비교하지 않는다.
  mix     확보량만큼 그린 + 나머지 전력망(확보 가능량 green_supply_twh가 필요량보다 적을 때만).
추천은 green과 grid만 비교한다(같은 수전해 설비를 같은 시간 돌리므로 설비비가 상쇄된다). 순서: 전력망 수소가 고로보다 배출이 많으면 그린 -> 목표 감축을 전력망으로 못 맞추면 그린 -> 그 밖에는 '전력 비용 + 탄소 비용(배출권 가격 x Scope 2)'이 작은 쪽.
시간 일치(hourly): 같은 시간에 난 재생에너지만 그린으로 인정하면 얼마나 채워지는지(2025 전력거래소 시간별 태양광·풍력)와 그때의 배출을 참고로 덧붙인다. 경부하 운전 배출은 2025 시간별 믹스 비율로 보정한다.
주의: 추천은 연간 계약(물량) 기준, 설비 투자비 제외, 탄소 가격·PPA 단가는 가정. 예측이 아니라 조건부 시나리오.
실행: 프로젝트 루트에서 python -m src.hydrogen
"""

from src.emission_factor import TOU_GF_RATIO
from src.simulator import ETS_RANGE, PPA_ADD, PPA_RANGE, avg_price, band_share, breakeven_grid, finite_number, ppa_unit, simulate

# fmt: off
H2_KG_T, ELEC_KWH_KG = 51.0, 52.5  # 쇳물 1t당 수소 (kg/t, Vogl 2018 51) / 수전해 전력 (kWh/kg, IEA GHR 2025 효율 63%(LHV) = 52.9). 51 x 52.5 = 2,678 kWh/t로 Bhaskar 2020 수전해 2,680 kWh/t와 맞춤
H2_KG_RANGE, ELEC_RANGE = (40, 60), (45, 58)  # 수소: 포스코 40~50(전기 가열, worldsteel 2025 구두)·Bhaskar 59·국회 토론회 60 / 수전해: Bhaskar 가정 45 ~ IEA 중국 효율 58%(= 57.5)
KAU_NOW, EUA_KRW = 29_500, 131_595  # K-ETS KAU26 시세(배출권시장협의회 2026-11-09) / EU ETS 86.6유로 원화 환산(SK증권 2026-11-09). 원/tCO2
PPA_DEFAULT = 180                   # 2025 태양광 직접PPA 체감가 175~185원 구간의 가운데 (CREF 조사, 전기신문 2026)
GREEN_H2_KRW_KG, BUY_RANGE = 18_163, (3_500, 21_201)  # 국내 수전해 생산기지 평균 생산원가(이종배 의원실, 머니투데이 2026-10-14) / 정부 2030 목표 3,500 ~ 운반비 포함 21,201
KETS_1Y, EUETS_1Y = dict(min=9_980, mean=18_581, max=30_850), dict(min=109_388, mean=135_325, max=157_625)  # ICAP Allowance Price Explorer 2차 시장, 2025-11-10~2026-09-30 (EU는 같은 날 원/유로 환산). analysis/16 산출
GF_AXIS = (0.20, 0.25, 0.30, 0.35, 0.40, 0.4173, 0.45, 0.50, 0.55)  # 추천 지도의 전력배출계수 축 (시뮬레이터 허용 0.20~0.56 안)
ETS_AXIS = (KETS_1Y["min"], KETS_1Y["mean"], KAU_NOW, 60_000, 90_000, EUA_KRW)  # 추천 지도의 탄소 가격 축: K-ETS 1년 최저·평균·현재 ~ EU ETS 현재
# 시간 일치(같은 시간에 난 재생에너지만 그린으로 인정) 결과. 24시간 일정한 수전해 부하를 연간 발전량이 같은 재생에너지로 맞출 때(k=1). 2025 전력거래소 시간별 태양광·풍력 발전량/설비용량(전국, 시장 참여 설비), src/ext_data.py
# share 같은 시간에 채운 비율, surplus 남는 재생 비율, backfill_ratio 모자란 시간 전력망 배출계수/연평균, storage_h 손실 없는 저장으로 100% 맞추는 데 필요한 용량(부하 몇 시간분), cf 이용률
HOURLY_MATCH = {"solar": dict(name="태양광 PPA", cf=0.1410, share=0.4713, surplus=0.5287, backfill_ratio=1.0354, storage_h=930.7),
                "wind": dict(name="풍력 PPA", cf=0.1960, share=0.6947, surplus=0.3053, backfill_ratio=1.0300, storage_h=1502.8),
                "mix": dict(name="태양광·풍력 반반", cf=None, share=0.7205, surplus=0.2795, backfill_ratio=1.0621, storage_h=654.7)}
PASS = {"grid_factor", "h2_kwh_t", "h2_bf_t", "h2_resid_t", "plan", "band_rule", "load_factor", "adder", "fund", "price_change"}  # simulate로 그대로 넘기는 변수
NOTE = "연간 전력량 기준. 재생에너지는 계약상 연간 물량으로 보고(시간 일치·저장 미반영), 수전해 설비 투자비는 넣지 않았다"
SOURCES = {"h2_kg_t": "Vogl 2018 수소 51 kg/t(원문), 포스코 HyREX 40~50 kg/t(worldsteel 2025 질의응답, 구두)", "elec_kwh_kg": "IEA Global Hydrogen Review 2025 부록: 수전해 효율 63%(LHV, 세계)·58%(중국)",
           "split": "Bhaskar 2020: 총 3,720 kWh/t 중 수전해 2,680 kWh/t", "ets_price": "K-ETS KAU26 29,500원/t(배출권시장협의회 2026-11-09), EU ETS 131,595원/t(SK증권 2026-11-09)",
           "ppa": "직접PPA 태양광 175~185원(전기신문 2026, CREF 조사), 육상풍력 180원 중반(인사이트에너지뉴스 2026), 파주 130원(전기신문 2026). 부대비용: 망이용료 9.79원(KSES 논문 예시), 부가정산금 11.682원(전력거래소)",
           "green_h2_krw_kg": "국내 수전해 평균 생산원가 18,163원/kg, 운반비 포함 21,201원, 정부 2030 목표 3,500원 (머니투데이 2026-10-14, 이종배 의원실)", "tou": "한전 2026 시간대표·요금표, 요금적용전력은 중간·최대부하 최대수요(경부하 제외)",
           "hourly": "전력거래소 2025 연료원별 시간대별 전력거래량, 시간별 신재생 발전량·설비용량(공공데이터포털). 연료원 배출계수: 제10차 전력수급기본계획 석탄 0.8362·LNG 0.3779(대한환경공학회지 논문 인용)",
           "ets_range": "ICAP Allowance Price Explorer 2차 시장 가격(K-ETS, EU ETS), 2025-11-10~2026-09-30"}
ASSUMPTIONS = ["수전해 설비 투자비 제외: green·grid는 같은 설비를 같은 시간 돌린다고 보고 비교(설비비 상쇄)", "그린 수소 배출 0(설비 제조·운송 배출 제외)",
               "탄소 비용 = 배출권 가격 x 구매 전력 배출(Scope 2). 실제 부담은 할당량에 따라 달라 참고값", "직접PPA 망이용료는 위치·전압마다 다름(논문 예시값 사용)",
               "경부하 운전(offpeak)은 설비 용량을 1/경부하 비중배로 늘리고 수소 저장이 필요하지만 그 비용은 넣지 않았다", "구매 그린수소(buy)는 생산자 설비비가 들어간 값이라 green·grid와 직접 비교하지 않는다",
               "24시간 운전은 공식 연평균 배출계수, 경부하 운전은 2025 시간별 평균 믹스 비율(경부하 1.007배)로 보정. 한계 배출(추가 수요에 반응하는 발전기)은 반영하지 않았다",
               "추천은 연간 계약(물량) 기준 그린. 시간 일치 기준 결과(hourly)는 참고로 따로 보여 주며 비용은 계산하지 않았다", "H2 원단위는 문헌·발표값이며 포스코 실측이 아니다"]


def h2_supply(h2_output_mt, ets_price=KAU_NOW, ppa_krw_kwh=PPA_DEFAULT, h2_kg_t=H2_KG_T, elec_kwh_kg=ELEC_KWH_KG, green_h2_krw_kg=GREEN_H2_KRW_KG,
              green_supply_twh=None, target_abate_t=None, **kw):
    """h2_supply = 수소 조달 비교·추천. 수소환원 연 생산량 h2_output_mt(백만 t, 실제 생산량)의 수소를 그린 수소(직접PPA)로 만들지 전력망 전기로 만들지 비교한다.
    ets_price는 탄소 가격 가정(원/tCO2, 기본 KAU26 시세), ppa_krw_kwh는 직접PPA 계약 단가(원/kWh). green_supply_twh(확보 가능한 재생에너지 TWh)·target_abate_t(목표 순 저감 tCO2/년)는 있으면 반영.
    나머지(grid_factor, h2_kwh_t, plan 등)는 simulate 변수. 돌려주는 값: options(선택지별 전력·배출·비용), verdict(추천과 이유), thresholds(갈림길 값), conditions(그린/전력망이 유리한 경우), map(배출계수 x 탄소 가격 추천 지도)."""
    finite_number("h2_output_mt", h2_output_mt, 0, 2.5, positive=True)
    finite_number("ets_price", ets_price, *ETS_RANGE)
    finite_number("ppa_krw_kwh", ppa_krw_kwh, *PPA_RANGE)
    finite_number("h2_kg_t", h2_kg_t, *H2_KG_RANGE)
    finite_number("elec_kwh_kg", elec_kwh_kg, *ELEC_RANGE)
    finite_number("green_h2_krw_kg", green_h2_krw_kg, *BUY_RANGE)
    if green_supply_twh is not None:
        finite_number("green_supply_twh", green_supply_twh, 0)
    if target_abate_t is not None:
        finite_number("target_abate_t", target_abate_t, positive=True)
    if bad := sorted(set(kw) - PASS):
        raise ValueError(f"알 수 없는 인자 {bad}: {sorted(PASS)}만 받음 (근거 없음)")
    base = dict(kw, eaf_mt=0, h2_mt=h2_output_mt, h2_util=1)
    grid = simulate(**base)
    inp = grid["input"]
    gf, total_t, t = inp["grid_factor"], inp["h2_kwh_t"], h2_output_mt * 1e6
    elec_t = h2_kg_t * elec_kwh_kg                                        # 수전해 전력 (kWh/t)
    proc_t = total_t - elec_t                                             # 공정 전력 (kWh/t)
    if proc_t < 0:
        raise ValueError(f"수전해 전력 {elec_t:.0f} kWh/t가 전력 원단위 h2_kwh_t {total_t:.0f}보다 큼: 수소·전력 원단위가 서로 맞지 않음 (근거 없음)")
    share = elec_t / total_t                                              # 수전해가 차지하는 전력 비율
    green = simulate(**base, h2_green=share, ppa_krw_kwh=ppa_krw_kwh)
    unit_grid, unit_ppa = grid["cost"]["unit_krw_kwh"], ppa_unit(ppa_krw_kwh, inp["fund"])
    elec_kwh, proc_kwh = t * elec_t, t * proc_t
    off_share = band_share(inp["band_rule"])
    unit_off = (avg_price(inp["band_rule"], inp["plan"], "경") * (1 + inp["price_change"]) + inp["adder"]) * (1 + inp["fund"])  # 경부하 운전 단가: 기본요금 없음(요금적용전력에서 경부하 제외)

    def option(key, name, grid_twh, green_twh, cost, scope2, abate, compared, note):
        carbon = ets_price * scope2
        return dict(key=key, name=name, compared=compared, grid_twh=grid_twh, green_twh=green_twh, scope2_tco2=scope2, abate_tco2=abate, abate_per_t=abate / t,
                    power_cost_eok=cost / 1e8, carbon_cost_eok=carbon / 1e8, total_eok=(cost + carbon) / 1e8, power_krw_per_t=cost / t, krw_per_t=(cost + carbon) / t, note=note)

    g, e = green["carbon"], grid["carbon"]
    off_s2 = (elec_kwh * TOU_GF_RATIO["경"] + proc_kwh) / 1000 * gf                # 경부하 운전 Scope 2: 수전해 전력만 경부하 배출 비율 적용
    opts = [option("green", "그린 수소 (재생에너지 직접PPA 수전해)", green["power"]["add_twh"] - green["power"]["h2_buy_twh"] * share, green["power"]["h2_buy_twh"] * share,
                   green["cost"]["total_eok"] * 1e8, g["add_tco2"], g["abate_tco2"], True, f"수전해 전력은 직접PPA {ppa_krw_kwh}원/kWh(부대비용 포함 {unit_ppa:.1f}원), 공정 전력은 한전"),
            option("grid", "전력망 전기 (한전 전력으로 수전해, 24시간)", grid["power"]["add_twh"], 0.0, grid["cost"]["total_eok"] * 1e8, e["add_tco2"], e["abate_tco2"], True,
                   f"모든 전력을 한전 요금으로 구매 (평균 {unit_grid:.1f}원/kWh, 기본·부가요금·기금 포함)"),
            option("offpeak", "전력망 전기, 수전해는 경부하 시간만 (참고)", grid["power"]["add_twh"], 0.0, elec_kwh * unit_off + proc_kwh * unit_grid, off_s2, e["abate_tco2"] - (off_s2 - e["add_tco2"]), False,
                   f"경부하 단가 {unit_off:.1f}원/kWh, 배출계수는 연평균의 {TOU_GF_RATIO['경']:.3f}배(2025 시간별 믹스). 경부하는 1년의 {off_share * 100:.1f}%라 수전해 설비가 {1 / off_share:.2f}배 필요하고 수소 저장도 필요(비용 미포함)"),
            option("buy", "구매 그린수소 (국내 평균 생산원가, 참고)", proc_kwh / 1e9, 0.0, t * h2_kg_t * green_h2_krw_kg + proc_kwh * unit_grid, g["add_tco2"], g["abate_tco2"], False,
                   f"수소 {green_h2_krw_kg:,}원/kg x {h2_kg_t:g} kg/t. 생산자 설비비가 들어간 값이라 위 두 줄과 직접 비교하지 않는다")]
    need_twh = elec_kwh / 1e9
    supply_ok = None if green_supply_twh is None else green_supply_twh >= need_twh - 1e-9
    if supply_ok is False:
        mix = simulate(**base, h2_green=green_supply_twh / grid["power"]["h2_buy_twh"], ppa_krw_kwh=ppa_krw_kwh)
        opts.append(option("mix", f"확보량 {green_supply_twh:g} TWh만 그린 + 나머지 전력망", mix["power"]["add_twh"] - green_supply_twh, green_supply_twh, mix["cost"]["total_eok"] * 1e8,
                           mix["carbon"]["add_tco2"], mix["carbon"]["abate_tco2"], False, f"그린 수소에 필요한 {need_twh:.2f} TWh 중 {green_supply_twh:g} TWh만 확보"))
    by = {o["key"]: o for o in opts}
    G, E = by["green"], by["grid"]

    be_bf = breakeven_grid(total_t, inp["h2_bf_t"], inp["h2_resid_t"])
    prem = unit_ppa - unit_grid                                           # 그린 전력이 1 kWh당 더 비싼 정도 (원/kWh, 음수면 더 쌈)
    ets_star = max(prem, 0) / gf * 1000                                   # 이 탄소 가격(원/tCO2)을 넘으면 그린이 싸다
    gf_star = prem * 1000 / ets_price if prem > 0 else 0.0                # 이 배출계수를 넘으면 그린이 싸다
    ppa_star = ((unit_grid + ets_price * gf / 1000) / (1 + inp["fund"]) - PPA_ADD["net"] - PPA_ADD["settle"] - PPA_ADD["fee"]) / (1 + PPA_ADD["loss"])  # 이 계약 단가 이하면 그린이 싸다
    need_t = None if target_abate_t is None else target_abate_t / t
    cheaper = "green" if G["krw_per_t"] < E["krw_per_t"] else "grid"
    if E["abate_tco2"] <= 0:
        pick, rule, why = "green", "grid_worse_than_bf", f"전력배출계수 {gf:g}가 손익분기 {be_bf:.3f}보다 높아, 전력망 전기로 만든 수소는 고로보다 탄소를 더 낸다"
    elif need_t is not None and E["abate_per_t"] < need_t:
        pick, rule = "green", "target"
        why = (f"목표 순 저감(쇳물 1t당 {need_t:.2f} t)을 전력망 전기로는 못 맞춘다(최대 {E['abate_per_t']:.2f} t). 그린 수소는 {G['abate_per_t']:.2f} t까지 가능" if G["abate_per_t"] >= need_t else
               f"목표 순 저감(쇳물 1t당 {need_t:.2f} t)은 둘 다 못 맞추지만 그린 수소가 더 가깝다(그린 최대 {G['abate_per_t']:.2f} t, 전력망 {E['abate_per_t']:.2f} t). 생산량을 늘리거나 목표를 조정해야 한다")
    else:
        pick, rule = cheaper, "cost"
        why = (f"탄소 비용까지 더한 쇳물 1t당 비용이 그린 {G['krw_per_t']:,.0f}원 < 전력망 {E['krw_per_t']:,.0f}원" if pick == "green" else
               f"탄소 비용까지 더한 쇳물 1t당 비용이 전력망 {E['krw_per_t']:,.0f}원 < 그린 {G['krw_per_t']:,.0f}원")
    cut1 = g["abate_tco2"] + g["add_tco2"]                                # Scope 1 감축 (선택지와 무관하게 같음)
    hourly = {}
    for key, hm in HOURLY_MATCH.items():
        s2 = (elec_kwh * (1 - hm["share"]) * hm["backfill_ratio"] + proc_kwh) / 1000 * gf
        hourly[key] = dict(hm, scope2_tco2=s2, abate_per_t=(cut1 - s2) / t, green_twh_matched=need_twh * hm["share"])
    extra = []
    if pick == "green":
        sm = hourly["solar"]
        extra.append(f"시간 일치 기준(같은 시간의 재생에너지만 그린으로 인정)이면 태양광 PPA는 수전해 전력의 {sm['share'] * 100:.0f}%만 채워 1t당 순 저감이 {G['abate_per_t']:.2f} t에서 {sm['abate_per_t']:.2f} t로 준다(풍력 {hourly['wind']['share'] * 100:.0f}%, 반반 {hourly['mix']['share'] * 100:.0f}%)")
    if pick == "green" and supply_ok is False:
        extra.append(f"그린 수소에 필요한 재생에너지 {need_twh:.2f} TWh 중 {green_supply_twh:g} TWh만 확보: 부족분 {need_twh - green_supply_twh:.2f} TWh는 전력망으로 채워야 한다(혼합안 참고)")
    if pick == "grid":
        extra.append(f"전력망을 쓰면 그린보다 연 {(E['scope2_tco2'] - G['scope2_tco2']) / 1e4:,.1f}만 tCO2를 더 낸다. 순 저감은 쇳물 1t당 {E['abate_per_t']:.2f} t(그린 {G['abate_per_t']:.2f} t)")
    verdict = dict(pick=pick, rule=rule, reason=why, notes=extra, cheaper_on_cost=cheaper, target_met=None if need_t is None else by[pick]["abate_per_t"] >= need_t)

    thresholds = dict(gf_breakeven_bf=be_bf, ets_breakeven=ets_star, gf_breakeven_cost=gf_star, ppa_breakeven=ppa_star, unit_grid_krw_kwh=unit_grid, unit_ppa_krw_kwh=unit_ppa, premium_krw_kwh=prem,
                      unit_offpeak_krw_kwh=unit_off, offpeak_share=off_share, green_twh_needed=need_twh, extra_abate_per_t=(elec_t / 1000) * gf, max_grid_abate_per_t=E["abate_per_t"], max_green_abate_per_t=G["abate_per_t"])
    green_if = [f"전력배출계수가 {be_bf:.3f} tCO2/MWh 이상: 전력망 수소는 고로보다 배출이 많아 그린 수소만 의미가 있다",
                (f"탄소 가격이 {ets_star:,.0f}원/tCO2 이상 (지금 가정 {ets_price:,.0f}원)" if prem > 0 else "직접PPA 전력이 한전 전력보다 싸서 탄소 가격과 무관하게 그린 수소가 싸다"),
                f"직접PPA 계약 단가가 {ppa_star:.0f}원/kWh 이하 (지금 가정 {ppa_krw_kwh:g}원)" if PPA_RANGE[0] <= ppa_star else f"직접PPA 계약 단가가 {ppa_star:.0f}원/kWh 이하 (근거 범위 {PPA_RANGE[0]}원보다 낮아 현재 PPA 시장에서는 해당 없음)",
                f"전력배출계수가 {gf_star:.3f} 이상 (지금 {gf:g})" if 0 < gf_star < be_bf else "",
                f"쇳물 1t당 목표 순 저감이 {E['abate_per_t']:.2f} t보다 클 때 (전력망 최대 {E['abate_per_t']:.2f} t, 그린 최대 {G['abate_per_t']:.2f} t)" if E["abate_per_t"] > 0 else ""]
    grid_if = [f"탄소 가격이 {ets_star:,.0f}원/tCO2 미만 (지금 가정 {ets_price:,.0f}원)" if prem > 0 else "",
               f"직접PPA 계약 단가가 {ppa_star:.0f}원/kWh 초과" if prem > 0 else "",
               f"전력배출계수가 {min(gf_star, be_bf):.3f} 미만 (전력망이 깨끗할수록 전력망 수소의 탄소 불리함이 줄어든다)" if prem > 0 else "",
               f"재생에너지 확보량이 부족할 때 (필요 {need_twh:.2f} TWh/년) - 부족분은 전력망으로 채운다",
               f"요금을 더 줄이려면 수전해를 경부하에 몰아 돌린다: {unit_off:.1f}원/kWh (24시간 평균 {unit_grid:.1f}원), 대신 설비 {1 / off_share:.2f}배와 수소 저장 필요. 탄소는 줄지 않는다(경부하 배출계수 연평균의 {TOU_GF_RATIO['경']:.3f}배)",
               f"재생에너지를 시간 단위로 맞춰야 하면(시간 일치) 태양광만으로는 {hourly['solar']['share'] * 100:.0f}%, 풍력 {hourly['wind']['share'] * 100:.0f}%, 반반 {hourly['mix']['share'] * 100:.0f}%만 채워진다. 나머지는 전력망이나 저장(반반도 부하 {hourly['mix']['storage_h']:.0f}시간분)이 필요하다"]
    cell = lambda f, p: "bf" if f >= be_bf else ("green" if prem - p * f / 1000 < 0 else "grid")
    mp = dict(gf=list(GF_AXIS), ets=list(ETS_AXIS), cells=[[cell(f, p) for f in GF_AXIS] for p in ETS_AXIS],
              legend=dict(green="그린 수소가 유리", grid="전력망 전기가 유리", bf="전력망 수소는 고로보다 배출 증가 - 그린만 의미"), note="목표 감축·확보량 조건은 지도에 넣지 않았다")
    applied = dict(h2_output_mt=h2_output_mt, ets_price=ets_price, ppa_krw_kwh=ppa_krw_kwh, h2_kg_t=h2_kg_t, elec_kwh_kg=elec_kwh_kg, green_h2_krw_kg=green_h2_krw_kg,
                   **{k: inp[k] for k in sorted(PASS)})
    return dict(note=NOTE, options=opts, verdict=verdict, thresholds=thresholds, conditions=dict(green=[c for c in green_if if c], grid=[c for c in grid_if if c]), map=mp,
                split=dict(elec_kwh_t=elec_t, process_kwh_t=proc_t, elec_share=share), green_supply_twh=green_supply_twh,
                hourly=dict(rows=hourly, note="2025 전력거래소 시간별 태양광·풍력 이용률로, 연간 발전량이 수전해 전력과 같은 재생에너지를 같은 시간에만 쓸 때. 모자란 시간은 전력망(그 시각의 배출계수), 남는 재생에너지는 계산에서 뺐다. 비용은 계산하지 않았다"),
                ets_ref=dict(kets_1y=KETS_1Y, euets_1y=EUETS_1Y, kau_now=KAU_NOW, eua_now=EUA_KRW), supply_ok=supply_ok, target_abate_t=target_abate_t,
                applied_input=applied, sources=dict(SOURCES), assumptions=list(ASSUMPTIONS))


if __name__ == "__main__":
    r = h2_supply(1.0)
    print("[추천]", r["verdict"]["pick"], "-", r["verdict"]["reason"])
    for o in r["options"]:
        print(f"  {o['name']}: 쇳물 1t당 {o['krw_per_t']:,.0f}원 (전력 {o['power_krw_per_t']:,.0f} + 탄소 {o['krw_per_t'] - o['power_krw_per_t']:,.0f}), 순 저감 {o['abate_per_t']:.2f} t/t")
    for k, v in r["thresholds"].items():
        print(f"  {k} = {v:,.4f}")
    print("[그린이 유리]", *r["conditions"]["green"], sep="\n  ")
    print("[전력망이 유리]", *r["conditions"]["grid"], sep="\n  ")
