"""시뮬레이터 검증 (처음부터 끝까지 실행): 내부 정합성 assert + 외부 수치 대조.
실행: 프로젝트 루트에서 python3 analysis/05_검증.py  (실패하면 AssertionError)
"""

import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.simulator import BUY_TWH, PLANS, RANGE, SCENARIOS, SCOPE1_T, SCOPE2_T, Scenario, breakeven_grid, green_needed, simulate

# fmt: off
S = lambda **k: simulate(**k)
near = lambda a, b, rel=1e-6: abs(a - b) <= rel * max(abs(a), abs(b), 1e-12)  # 거의 같다 (pytest 없이 쓰려고 직접 정의)


def rejects(**k):
    """rejects = 거절 확인. 시뮬레이터가 '근거 없음' ValueError를 내면 True."""
    try: S(**k)
    except ValueError as e: return "근거 없음" in str(e)
    return False

# 1. 내부 정합성
r0 = S(eaf_mt=0)
assert r0["power"]["add_twh"] == 0 and r0["carbon"]["net_tco2"] == 0 and r0["cost"]["total_eok"] == 0, "S0은 모두 0"
full = S(eaf_util=1.0, plan="A2")
assert near(full["power"]["add_twh"], 1.125), "2.5Mt x 450kWh/t = 1.125 TWh"
assert near(full["carbon"]["add_tco2"], 1.125e6 * 0.4173), "탄소 = 전력(MWh) x 계수"
assert near(S(eaf_util=0.5)["power"]["add_twh"], S(eaf_util=1.0)["power"]["add_twh"] / 2), "가동률에 비례"
assert near(S(selfgen_cut=0.15)["power"]["selfgen_loss_twh"], 21 * 0.855 * 0.15), "자체 발전 감소 = 총전력 x 자체비율 x 감소율"
a, b = S(adder=4)["cost"], S(adder=14)["cost"]
assert near((b["adder_eok"] - a["adder_eok"]), 10 * S()["power"]["add_twh"] * 10, rel=1e-6), "부가요금 10원/kWh 차이 = 0.7875 TWh x 10원 = 78.75억"
c = S()["cost"]
assert near(c["total_eok"], (c["energy_eok"] + c["basic_eok"] + c["adder_eok"]) * 1.037), "총 요금 = (전력량+기본+부가) x 1.037(기금)"
for k, (lo, hi) in RANGE.items():  # 범위 밖은 모두 거절
    for v in (lo - 1e-6 - abs(lo) * 0.01, hi + 1e-6 + abs(hi) * 0.01):
        assert rejects(**{k: v}), f"{k}={v} 거절돼야 함"
for k, v in (("plan", "Z9"), ("band_rule", "C")):
    assert rejects(**{k: v}), f"{k}={v} 거절돼야 함"
assert S(eaf_util=0.3)["power"]["add_twh"] < S()["power"]["add_twh"] < S(eaf_util=1)["power"]["add_twh"], "단조성"
# 수소환원(S4) 정합성
s4, s4g, s5, s1 = (S(**{k: v for k, v in vars(SCENARIOS[n]).items()}) for n in ("S4", "S4G", "S5", "S1"))
assert near(s4["power"]["add_twh"], 0.3 * 0.7 * 3.72), "S4 전력 = 0.3Mt x 0.7 x 3.72 MWh/t = 0.7812 TWh"
assert s4g["carbon"]["add_tco2"] == 0, "무탄소 100%면 Scope 2 증가 0"
assert near(s4["carbon"]["scope1_cut_tco2"], 0.21e6 * 1.99), "S4 Scope 1 감축 = 21만 t x 1.99"
assert near(s5["power"]["add_twh"], s1["power"]["add_twh"] + s4["power"]["add_twh"]) and near(s5["carbon"]["abate_tco2"], s1["carbon"]["abate_tco2"] + s4["carbon"]["abate_tco2"]), "S5 = S1 + S4 (전력·순 저감 덧셈)"
assert near(s1["cost"]["total_eok"], 1427.56, 1e-4), "수소환원 추가가 기존 S1 결과를 바꾸지 않음(회귀)"
assert abs(breakeven_grid(3720, 1.688) - 0.456) < 0.005, "Bhaskar 2020 논문의 손익분기 0.456 재현"
assert near(S(eaf_mt=0, h2_mt=1, h2_util=1)["carbon"]["abate_tco2"], 1e6 * (1.99 - 3.72 * 0.4173)), "수소환원 1Mt 순 저감 = 1.99 - 3.72 x 0.4173 (t/t)"
g = green_needed(0.4173)  # 필요 무탄소 비율로 수소환원을 돌리면 순 저감이 전기로(1 Mt)와 같아야 함
assert near(S(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=g)["carbon"]["abate_tco2"], S(eaf_mt=1, eaf_util=1, h2_mt=0)["carbon"]["abate_tco2"]), "green_needed가 simulate와 일치"
from src.emission_factor import GRID
assert abs(GRID.loc[2021:2023].mean() - 0.4330) < 1e-3, "연도별 값 검산: 2021~23 평균 0.4330(공식)"
print("[내부 정합성] 통과")

# 2. 외부 수치 대조 (일치 여부와 차이를 그대로 보고)
s1 = S()
unit = s1["cost"]["unit_krw_kwh"]
print(f"[요금] S1 kWh당 총요금 {unit:.1f}원 (기본·부가·기금 포함) vs 산업용 평균 판매단가 2025년 181.9원(스마트비즈): 차이 {unit-181.9:+.1f}원. 요금제별 범위 {min(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}~{max(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}원")
cut = S(eaf_util=1.0)["carbon"]["scope1_cut_tco2"]
print(f"[Scope 1 감축] 가동률 100% {cut/1e4:.0f}만 t = 포스코 주장 연 최대 350만 t와 같게 설정(순환 확인용). Factbook Scope 1 {SCOPE1_T/1e4:.0f}만 t의 {cut/SCOPE1_T*100:.1f}%")
print(f"[Scope 2 역산] Factbook 1.40Mt ÷ 구매 {BUY_TWH} TWh = {SCOPE2_T/1e6/BUY_TWH:.3f} t/MWh (공식 2020~22 평균 0.4541과 같은 기준, 현재 기본값 0.4173과는 {0.4173/ (SCOPE2_T/1e6/BUY_TWH)-1:+.0%})")
print(f"[총 전력] 2024: 3.05÷(1-0.855)={3.05/0.145:.1f} TWh, 2021: 3.8÷(1-0.85)={3.8/0.15:.1f} TWh -> total_twh 범위 {RANGE['total_twh']}")
print(f"[전기로 전력] 100% 가동 구매전력 증가 {full['power']['buy_increase_pct']:.0f}% (현재 구매전력 대비)")
print("\n검증 완료")
