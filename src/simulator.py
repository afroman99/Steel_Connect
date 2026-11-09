"""전환 시나리오 시뮬레이터 v0.5. 변수·출처·신뢰도는 reports/시나리오_변수표.md 참고.

입력: simulate(**변수) 또는 SCENARIOS[이름]. 허용 범위 밖 값은 ValueError (어시스턴트가 "근거 없음"으로 거절하는 근거).
출력: dict {input, power, carbon, cost, assumptions, sources}
v0.5: 수소환원(S4) 경로와 탄소 저감 효율 지표 추가. v0.4: 요금제(고압A/B/C 선택Ⅰ~Ⅲ) 변수화, 기후환경·연료비조정요금·기금 반영, Scope 1 감축(전기로가 고로를 대체) 반영, 총 전력(total_twh) 변수화.
시간대 비중은 UCI 분석(src/load_profile.py)에서 계산해 가져온다. 실행: 프로젝트 루트에서 python3 -m src.simulator
"""

from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

# 아래 fmt: off는 자동 포맷터가 한 줄을 여러 줄로 풀어쓰지 못하게 하는 표시
# fmt: off
# 한전 2025-04 산업용(을) 요금표 (원문 10페이지 확인). 요금제 -> (기본요금 원/kW·월, {계절: (경부하, 중간부하, 최대부하) 원/kWh})
# 고압A = 3.3~66kV, 고압B = 154kV, 고압C = 345kV 이상. 선택Ⅰ(월 200시간 이하)·Ⅱ(200~500)·Ⅲ(500 초과 가동)
PLANS = {
    "A1": (7220, {"여름": (116.4, 169.3, 251.4), "봄가을": (116.4, 138.9, 169.6), "겨울": (123.4, 169.5, 227.0)}),
    "A2": (8320, {"여름": (110.9, 163.8, 245.9), "봄가을": (110.9, 133.4, 164.1), "겨울": (117.9, 164.0, 221.5)}),
    "A3": (9810, {"여름": (110.0, 163.2, 233.5), "봄가을": (110.0, 132.1, 155.8), "겨울": (117.3, 163.4, 210.3)}),
    "B1": (6630, {"여름": (126.3, 178.6, 259.8), "봄가을": (126.3, 148.6, 178.9), "겨울": (133.3, 178.6, 234.8)}),
    "B2": (7380, {"여름": (122.5, 174.8, 256.0), "봄가을": (122.5, 144.8, 175.1), "겨울": (129.5, 174.8, 231.0)}),
    "B3": (8190, {"여름": (120.8, 173.1, 254.4), "봄가을": (120.8, 143.2, 173.5), "겨울": (127.9, 173.1, 229.3)}),
    "C1": (6590, {"여름": (125.8, 178.7, 259.6), "봄가을": (125.8, 148.7, 179.1), "겨울": (132.7, 178.3, 234.9)}),
    "C2": (7520, {"여름": (121.1, 174.0, 254.9), "봄가을": (121.1, 144.0, 174.4), "겨울": (128.0, 173.6, 230.2)}),
    "C3": (8090, {"여름": (120.0, 172.9, 253.8), "봄가을": (120.0, 142.9, 173.3), "겨울": (126.9, 172.5, 229.1)}),
}
REFORM = {"여름": (5.1, 0, -16.9), "봄가을": (5.1, 0, -13.2), "겨울": (5.1, 0, -16.9)}  # 2026 개편 단가 변화 (중간부하 미확인 = 0, 모든 요금제에 같은 변화 적용은 가정)
RULES = {"2025": None, "B": {"mid": (11, 13, 14)}}  # 시간대 규칙: 2025(개편 전, 비교용) / B(2026 개편 후 = 확정. 11~12·13~15시 중간, 18~21시 최대, 한전 안내문 2026-03-16). 기사의 "9~15시 통일" 해석(A)은 폐기
DATA = Path(__file__).resolve().parent.parent / "data/Steel_industry_data.csv"
FUNDS = (0.037, 0.032, 0.027)  # 전력산업기반기금 요율: 3.7%(한전 요금표 2023-05 원문) / 3.2%(2024-07~2025-06) / 2.7%(2025-07~, 정부 안내, 원문 재확인 필요). 부가가치세 10%는 사업자 환급 대상이라 제외(가정)
ETS_RANGE = (10_000, 30_000)  # 배출권 가격 허용 범위 (원/tCO2). 시장 변동이 커서(1만 원대~3만 원 안팎 보도) 넓게 잡음, KRX 원문 미확인
EAF_CLAIM_T = 1.4  # 포스코 주장 350만 t ÷ 250만 t (경계 미확인)
TOTAL_TWH, SELF_SHARE, BUY_TWH, SCOPE2_T, SCOPE1_T = 21.0, 0.855, 3.05, 1_399_825, 69_665_353  # 제철소 총전력(역산), 자체생산비율, 2024 구매전력, 2024 Scope 2, Scope 1
RANGE = dict(eaf_mt=(0, 2.5), eaf_kwh_t=(300, 500), eaf_util=(0.3, 1), selfgen_cut=(0, 0.3), grid_factor=(0.20, 0.56),
             price_change=(-0.1, 0.2), load_factor=(0.6, 1), total_twh=(20, 26), adder=(4, 14), bf_replace=(0, 1), bf_tco2_t=(1.0, 2.1), eaf_direct_t=(0.04, 0.15),
             h2_mt=(0, 2.5), h2_util=(0.3, 1), h2_kwh_t=(2700, 4000), h2_green=(0, 1), h2_bf_t=(1.6, 2.1), h2_resid_t=(0, 0.4))  # 변수별 허용 범위
LOW_CONF = ["scope2_기준선(0.4541 기반)과 증분(grid_factor) 계수 불일치", "plan(수전 전압·선택요금 미확인)", "eaf_kwh_t", "eaf_util", "selfgen_cut", "price_change", "load_factor",
            "total_twh(역산, 2021년 3.8÷0.15=25와 2024년 3.05÷0.145=21 두 점)", "adder(기후환경 9원은 2023-01 기준, 연료비조정 ±5원)", "bf_tco2_t(포스코 평균 Scope 1 1.99, 고로 단독값 아님. BF 자체 Scope 2 약 0.04는 양쪽 경로 모두 제외)", "eaf_direct_t(전기로 직접 배출 0.08, 2차 출처 IPCC 2006·JRC 인용, 원문 미확인)", "bf_replace(대체 비율 가정)", "h2_mt(실증 30만t 보도, 상용 규모 근거 없음)", "h2_kwh_t(문헌 2.7~4.0, 포스코 실측 아님)", "h2_green(청정전력 조달 비율 가정)", "h2_bf_t(포스코 평균 Scope 1 원단위, 고로 단독값 아님)", "h2_resid_t(수소환원 잔여 배출, 논문은 0, IEA 근접 제로 0.4 이하)", "요금 개편 중간부하 단가(안내문에 조정 항목으로 없음, 변화 없음으로 해석)", "ets_price(사용자 가정, 시장 변동 큼, KRX 원문 미확인)"]
SOURCES = {"tariff": "한전 요금표 2025-04 산업용(을)", "buy_twh": "Factbook 2024 p.6", "scope1_2": "Factbook 2024 p.5", "grid_factor": "기후부 보도자료 2025-12-18, 2023 전력배출계수 0.4173(소비단)",
           "eaf_mt": "뉴스룸 광양 전기로 준공", "self_share": "ESG 에너지 페이지", "adder_fund": "한전 요금표 2023-05 (기후환경 9원, 연료비조정 5원 ±5, 기금 3.7·3.2·2.7%)", "bf_tco2_t": "Factbook 2024 Scope 1 69.67Mt ÷ 조강 약 35Mt = 1.99 t/t (역산)", "eaf_direct_t": "전기로 직접 배출 0.06~0.1 t/t (JRC 2012, IPCC 2006 0.08; 2차 출처)", "eaf_claim": "전자신문 2026-05-10 연 최대 350만 t 감축(경계 미명시), 뉴스룸 최대 약 75% 감축(Scope 1&2, 2017~19 평균 대비)",
           "h2_kwh_t": "Vogl 2018 3.48 MWh/tLS, Bhaskar 2020 3.72 MWh/tls (원문 확인)", "h2_mt": "포스코 HyREX 포항 실증 30만 t, 2028 목표 (보도)", "h2_bf_t": "Factbook 2024 Scope 1 69.67Mt ÷ 조강 약 35Mt = 1.99 t/t (역산)", "breakeven": "Bhaskar 2020: 전력배출계수 0.456 초과 시 수소환원 배출 증가"}


@dataclass
class Scenario:
    """시나리오(Scenario) = 사용자가 바꿀 수 있는 입력 변수 묶음. 기본값은 S1(전기로 70% 가동)."""
    eaf_mt: float = 2.5          # 신규 전기로 생산 능력 (백만 t/년)
    eaf_kwh_t: float = 450       # 전력 원단위 (kWh/t)
    eaf_util: float = 0.7        # 가동률
    selfgen_cut: float = 0.0     # 고로 축소로 자체 발전이 줄어드는 비율 (줄어든 만큼 구매로 대체). 불확실성이 아니라 시나리오 축으로 다룬다
    grid_factor: float = 0.4173  # 전력배출계수 (tCO2eq/MWh), 2023 확정 소비단 값(기후부 2025-12-18). 2024 Scope2 기준선은 0.4541(2020~22 평균) 기반이라 증분과 계수가 다름
    price_change: float = 0.0    # 전력량·기본요금 변동률
    band_rule: str = "B"         # 요금 시간대 규칙: "B"(2026 개편 후, 기본. 산업용(을)은 2026-10-01부터 전체 적용), "2025"(개편 전 시간대·단가, 비교용)
    load_factor: float = 0.8     # 부하율 (계약전력 = 평균전력 / 부하율)
    plan: str = "B3"             # 요금제: 고압A/B/C(수전 전압) + 선택Ⅰ~Ⅲ. 광양 규모는 154kV 이상(B/C)·월 500시간 초과 가동(Ⅲ)으로 가정
    fund: float = 0.027          # 전력산업기반기금 요율. 2025-07 이후 2.7%, 과거 기준 비교용으로 0.032·0.037 허용
    ets_price: float | None = None  # 배출권 가격 가정 (원/tCO2). 없으면 환산 가치를 계산하지 않음. 참고 가치일 뿐 실제 구매 회피액이 아님(할당량·보유량 필요)
    adder: float = 9.0           # 기후환경요금+연료비조정요금 (원/kWh). 기본은 기후환경 9원, 연료비조정은 0
    total_twh: float = TOTAL_TWH  # 제철소 총 전력 사용 (TWh). 자체 발전 감소분 계산의 바탕
    bf_replace: float = 1.0      # 전기로 생산이 고로 생산을 대체하는 비율 (Scope 1 감축 계산용)
    bf_tco2_t: float = 1.99      # 고로 대체 1 t당 고로의 Scope 1 배출 (tCO2/t). 포스코 평균 Scope 1 원단위(수소환원 h2_bf_t와 같은 경계)
    eaf_direct_t: float = 0.08   # 전기로 직접 배출 (tCO2/t). 전기로 감축 = bf_tco2_t - eaf_direct_t, 전력 배출은 구매 전력으로 따로 계산(상향식)
    eaf_basis: str = "bottom_up"  # "bottom_up" 같은 경계 상향식(기본) / "posco_net" 포스코 주장 순감축 1.4 t/t(경계 미확인, 전력 배출 포함으로 보고 재차감하지 않음)
    h2_mt: float = 0.0           # 수소환원제철 생산 능력 (백만 t/년). 0이면 없음. 포항 HyREX 실증 규모는 0.3
    h2_util: float = 0.7         # 수소환원 가동률
    h2_kwh_t: float = 3720       # 수소환원 전력 원단위 (kWh/t 쇳물, 수전해 포함). Vogl 3480, Bhaskar 3720
    h2_green: float = 0.0        # 수소환원 전력 중 무탄소(재생 등) 전력 비율. 이만큼은 배출계수 0으로 계산(요금은 같게 가정)
    h2_bf_t: float = 1.99        # 수소환원이 대체하는 고로 1 t당 Scope 1 배출 (tCO2/t). 포스코 평균 1.99, 논문 EU 고로 1.69
    h2_resid_t: float = 0.0      # 수소환원 잔여 직접 배출 (tCO2/t). 논문은 0으로 가정


SCENARIOS = {"S0": Scenario(eaf_mt=0), "S1": Scenario(), "S1P": Scenario(eaf_basis="posco_net"), "S1O": Scenario(band_rule="2025"), "S2": Scenario(selfgen_cut=0.15),
             "S4": Scenario(eaf_mt=0, h2_mt=0.3), "S4G": Scenario(eaf_mt=0, h2_mt=0.3, h2_green=1.0), "S5": Scenario(h2_mt=0.3)}  # S4 수소환원(전력망 전력), S4G 수소환원(무탄소 전력), S5 전기로(S1)+수소환원(S4)


def check_range(s):
    """check_range = 범위 확인. 변수가 허용 범위를 벗어나면 '근거 없음'으로 거절(ValueError)한다."""
    for k, (lo, hi) in RANGE.items():
        v = getattr(s, k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{k}={v!r}: 숫자가 아님 (근거 없음)")
        if not lo <= v <= hi:
            raise ValueError(f"{k}={getattr(s, k)}: 허용 범위 {lo}~{hi} 밖 (근거 없음)")
    if s.ets_price is not None:
        v = s.ets_price
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not ETS_RANGE[0] <= v <= ETS_RANGE[1]:
            raise ValueError(f"ets_price={v!r}: 허용 범위 {ETS_RANGE[0]}~{ETS_RANGE[1]}원/t 밖 (근거 없음)")
    if s.eaf_basis not in ("bottom_up", "posco_net"):
        raise ValueError(f"eaf_basis={s.eaf_basis!r}: bottom_up 또는 posco_net (근거 없음)")
    if s.fund not in FUNDS:
        raise ValueError(f"fund={s.fund}: {FUNDS} 중 하나 (근거 없음)")
    for k, ok in (("band_rule", RULES), ("plan", PLANS)):
        if not isinstance(getattr(s, k), str) or getattr(s, k) not in ok:
            raise ValueError(f"{k}={getattr(s, k)}: {list(ok)} 중 하나 (근거 없음)")


@cache
def avg_price(rule, plan="A2"):
    """avg_price = 평균 요금. 24시간 일정 부하의 전력량요금 평균(원/kWh). UCI 달력(분석 결과)의 계절·시간대 비중으로 가중하고, 개편 규칙(B)이면 단가 변화와 봄·가을 주말 낮 50% 할인도 반영. B는 공식 시간표로 직접 계산한 값과 일치 확인."""
    from src.load_profile import (  # 순환 import를 피하려고 함수 안에서 불러옴
        load_uci,
        price,
        reform_band,
    )
    d = load_uci(DATA)
    return float(price(d, d.band if rule == "2025" else reform_band(d, **RULES[rule]), rule != "2025", plan).mean())


def simulate(**kw):
    """simulate = 모의실험. 시나리오 변수를 받아 추가 전력(TWh)·탄소(tCO2, Scope 2 증가와 Scope 1 감축)·요금(억 원)을 계산해 dict로 돌려준다.
    scope2_after_t·scope1_after_t는 2024 공시 기준선에 증분을 더한 혼합 기준 참고값이다(같은 연도 재산정 배출량이 아님)."""
    s = Scenario(**kw)
    check_range(s)
    out_mt = s.eaf_mt * s.eaf_util                                       # 전기로 실제 생산량 (백만 t)
    eaf = out_mt * 1e6 * s.eaf_kwh_t / 1e9                                 # 전기로가 새로 구매하는 전력 (TWh). 전량 구매로 고정(자가발전 배출·비용 분리 전까지)
    h2_mt = s.h2_mt * s.h2_util                                          # 수소환원 실제 생산량 (백만 t)
    h2 = h2_mt * 1e6 * s.h2_kwh_t / 1e9                                    # 수소환원이 새로 구매하는 전력 (TWh)
    loss = s.total_twh * SELF_SHARE * s.selfgen_cut                      # 자체 발전 감소분 (TWh)
    add = eaf + h2 + loss                                                # 추가 구매 전력 (TWh)
    kwh, up = add * 1e9, 1 + s.price_change
    price = avg_price(s.band_rule, s.plan) * up                          # 평균 전력량요금 (원/kWh)
    energy = price * kwh                                                 # 전력량요금 (원)
    basic = PLANS[s.plan][0] * 12 * kwh / 8760 / s.load_factor * up      # 기본요금 (원)
    adder = s.adder * kwh                                                # 기후환경+연료비조정요금 (원)
    fund = (energy + basic + adder) * s.fund                              # 전력산업기반기금 (원)
    tco2 = (add - h2 * s.h2_green) * 1e6 * s.grid_factor                 # Scope 2 증가 (tCO2): 무탄소 전력분은 0
    share = out_mt * 1e6 * s.bf_replace                                  # 고로를 대체하는 전기로 생산량 (t)
    eaf_cut = share * (s.bf_tco2_t - s.eaf_direct_t) if s.eaf_basis == "bottom_up" else share * (EAF_CLAIM_T + s.eaf_kwh_t / 1000 * s.grid_factor)  # 전기로 감축(tCO2). posco_net은 순감축 1.4에 전기로 전력 배출을 더해 총감축으로 바꿔 둠(아래에서 전력 배출을 빼면 순감축 1.4)
    cut = eaf_cut + h2_mt * 1e6 * (s.h2_bf_t - s.h2_resid_t)  # Scope 1 감축 (tCO2): 전기로 + 수소환원
    abate = cut - tco2                                                   # 순 저감 (tCO2, 음수면 순증가)
    return dict(
        input=asdict(s),
        power=dict(eaf_output_mt=out_mt, h2_output_mt=h2_mt, eaf_buy_twh=eaf, h2_buy_twh=h2, selfgen_loss_twh=loss, add_twh=add, buy_after_twh=BUY_TWH + add, buy_increase_pct=add / BUY_TWH * 100),
        carbon=dict(add_tco2=tco2, scope1_cut_tco2=cut, net_tco2=tco2 - cut, abate_tco2=abate, abate_per_mwh=abate / (add * 1e6) if add else 0, scope2_after_t=SCOPE2_T + tco2, scope1_after_t=SCOPE1_T - cut, ets_value_eok=None if s.ets_price is None else abate * s.ets_price / 1e8,
                    scope2_increase_pct=tco2 / SCOPE2_T * 100, scope1_cut_pct=cut / SCOPE1_T * 100),
        cost=dict(avg_price_krw_kwh=price, energy_eok=energy / 1e8, basic_eok=basic / 1e8, adder_eok=adder / 1e8, fund_eok=fund / 1e8,
                  total_eok=(energy + basic + adder + fund) / 1e8, unit_krw_kwh=(energy + basic + adder + fund) / kwh if kwh else 0,
                  power_cost_per_tco2_krw=(energy + basic + adder + fund) / abate if abate > 0 else None),  # 전력비용 기준(설비 투자비 미포함), 순 저감이 없으면 None
        assumptions=LOW_CONF, sources=SOURCES)


if __name__ == "__main__":
    for n, sc in SCENARIOS.items():
        r = simulate(**asdict(sc))
        print(n, {k: None if v is None else round(v, 2) for d in ("power", "carbon", "cost") for k, v in r[d].items()})


def breakeven_grid(h2_kwh_t=3720, bf_t=1.99, resid_t=0.0):
    """breakeven_grid = 손익분기 전력배출계수(t/MWh). 이 값보다 전력이 더러우면 수소환원이 고로보다 배출을 늘린다. = (고로 배출 - 잔여 배출) / 전력 원단위(MWh/t)."""
    if h2_kwh_t <= 0:
        raise ValueError("h2_kwh_t는 0보다 커야 함")
    return (bf_t - resid_t) / (h2_kwh_t / 1000)


def green_needed(gf, h2_kwh_t=3720, eaf_kwh_t=450, bf_t=1.99, resid_t=0.0, eaf_direct_t=0.08, eaf_net_t=None):
    """green_needed = 필요한 무탄소 전력 비율. 같은 1 t당 수소환원의 순 저감이 전기로(고철) 이상이 되려면 수소환원 전력 중 무탄소가 얼마(0~1)여야 하는지.
    수소환원 순 저감 = (bf_t - resid_t) - h2_kwh_t/1000 x gf x (1-g), 전기로 순 저감 = bf_t - eaf_direct_t - eaf_kwh_t/1000 x gf (같은 고로 기준, 상향식)를 같게 놓고 g를 푼다.
    eaf_net_t를 주면 전기로 순 저감을 그 값(예: 포스코 주장 1.4)으로 고정한다. 0이면 전력망 전력만으로도 충분(이미 충족, 음수는 0으로 자름), 1을 넘으면 무탄소 100%로도 전기로에 못 미친다. gf<=0이면 계산 불가(ValueError)."""
    if gf <= 0 or h2_kwh_t <= 0:
        raise ValueError("gf와 h2_kwh_t는 0보다 커야 함")
    eaf = eaf_net_t if eaf_net_t is not None else bf_t - eaf_direct_t - eaf_kwh_t / 1000 * gf
    return max(0.0, 1 - (bf_t - resid_t - eaf) / (h2_kwh_t / 1000 * gf))
