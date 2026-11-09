"""시뮬레이터 검증 (처음부터 끝까지 실행): 내부 정합성 assert + 외부 수치 대조.
주의: assert 통과는 계산이 서로 맞는지(환산·비례·합산·입력 거절)를 확인한 것이며, 입력 가정과 출처의 외부 타당성을 보증하지 않는다. 일부 기대값(S1 요금 등)은 현재 구현값을 고정한 회귀 확인이다.
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
assert near(c["total_eok"], (c["energy_eok"] + c["basic_eok"] + c["adder_eok"]) * 1.027), "총 요금 = (전력량+기본+부가) x 1.027(기금 2.7%, 2025-07~)"
for k, (lo, hi) in RANGE.items():  # 범위 밖은 모두 거절
    for v in (lo - 1e-6 - abs(lo) * 0.01, hi + 1e-6 + abs(hi) * 0.01):
        assert rejects(**{k: v}), f"{k}={v} 거절돼야 함"
for k, v in (("plan", "Z9"), ("band_rule", "C")):
    assert rejects(**{k: v}), f"{k}={v} 거절돼야 함"
assert S(eaf_util=0.3)["power"]["add_twh"] < S()["power"]["add_twh"] < S(eaf_util=1)["power"]["add_twh"], "단조성"
# 수소환원(S4) 정합성
s4, s4g, s5, s1, s1o = (S(**{k: v for k, v in vars(SCENARIOS[n]).items()}) for n in ("S4", "S4G", "S5", "S1", "S1O"))
assert near(s4["power"]["add_twh"], 0.3 * 0.7 * 3.72), "S4 전력 = 0.3Mt x 0.7 x 3.72 MWh/t = 0.7812 TWh"
assert s4g["carbon"]["add_tco2"] == 0, "무탄소 100%면 Scope 2 증가 0"
assert near(s4["carbon"]["scope1_cut_tco2"], 0.21e6 * 1.99), "S4 Scope 1 감축 = 21만 t x 1.99"
assert near(s5["power"]["add_twh"], s1["power"]["add_twh"] + s4["power"]["add_twh"]) and near(s5["carbon"]["abate_tco2"], s1["carbon"]["abate_tco2"] + s4["carbon"]["abate_tco2"]), "S5 = S1 + S4 (전력·순 저감 덧셈)"
assert near(s1o["cost"]["total_eok"], 1413.80, 1e-4), "개편 전(2025) S1 요금 회귀"
assert near(s1["cost"]["total_eok"], 1401.78, 1e-4), "개편 후(B, 주말 낮 할인 포함) S1 요금 회귀"
assert s1["cost"]["total_eok"] < s1o["cost"]["total_eok"], "개편 후가 더 싸다"
assert abs(breakeven_grid(3720, 1.688) - 0.456) < 0.005, "Bhaskar 2020 논문의 손익분기 0.456 재현"
assert near(S(eaf_mt=0, h2_mt=1, h2_util=1)["carbon"]["abate_tco2"], 1e6 * (1.99 - 3.72 * 0.4173)), "수소환원 1Mt 순 저감 = 1.99 - 3.72 x 0.4173 (t/t)"
g = green_needed(0.4173)  # 필요 무탄소 비율로 수소환원을 돌리면 순 저감이 전기로(1 Mt)와 같아야 함
assert near(S(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=g)["carbon"]["abate_tco2"], S(eaf_mt=1, eaf_util=1, h2_mt=0)["carbon"]["abate_tco2"]), "green_needed가 simulate와 일치"
from src.emission_factor import GRID
assert abs(GRID.loc[2021:2023].mean() - 0.4330) < 1e-3, "연도별 값 검산: 2021~23 평균 0.4330(공식)"
assert near(S(eaf_util=1, h2_mt=0)["carbon"]["abate_tco2"], 2.5e6 * (1.99 - 0.08 - 0.45 * 0.4173)), "전기로 순 저감 = 고로 1.99 - 직접 0.08 - 전력 0.45 x 계수 (같은 경계)"
assert near(S(eaf_util=1, eaf_basis="posco_net")["carbon"]["abate_tco2"], 2.5e6 * 1.4), "포스코 순감축 옵션: 순 저감 = 1.4 t/t (전력 배출 재차감 없음)"
assert near(S(eaf_util=1, eaf_basis="posco_net", grid_factor=0.3)["carbon"]["abate_tco2"], 2.5e6 * 1.4), "posco_net은 계수와 무관"
assert rejects(eaf_basis="typo"), "경계 옵션 오타 거절"
assert near(S(fund=0.037, band_rule="2025")["cost"]["total_eok"], 1427.56, 1e-4), "기금 3.7%·개편 전 요금(2025) 재현"
for bad in ({"eaf_mt": True}, {"eaf_mt": None}, {"plan": 3}, {"fund": 0.05}, {"grid_factor": float("nan")}):
    assert rejects(**bad), f"{bad} 거절돼야 함"
assert not rejects(grid_factor=0.245) and not rejects(grid_factor=0.5404), "미래·2018 계수 허용"
for f, a in ((green_needed, (0,)), (breakeven_grid, (0,))):
    try: f(*a); raise AssertionError("0 입력은 거절돼야 함")
    except ValueError: pass
assert green_needed(0.1, eaf_net_t=0.5) == 0, "수소환원 순 저감이 이미 전기로 이상이면 0(음수 자름)"
from src.target import compare_paths, min_green, required_output
T = 100e4
r = required_output(T, "eaf"); assert near(S(eaf_mt=r["required_mt"], eaf_util=1, h2_mt=0)["carbon"]["abate_tco2"], T), "역산한 전기로 생산량으로 순방향 계산하면 목표와 일치"
r = required_output(T, "h2", h2_green=0.5); assert near(S(eaf_mt=0, h2_mt=r["required_mt"], h2_util=1, h2_green=0.5)["carbon"]["abate_tco2"], T) and near(r["power_twh"], S(eaf_mt=0, h2_mt=r["required_mt"], h2_util=1)["power"]["add_twh"]), "수소환원 역산 일치"
m = min_green(0.5, 50e4); assert near(S(eaf_mt=0, h2_mt=0.5, h2_util=1, h2_green=m["green_share"])["carbon"]["abate_tco2"], 50e4), "min_green이 순방향과 일치"
assert not min_green(0.5, 150e4)["feasible"] and not required_output(T, "h2", grid_factor=0.56, h2_kwh_t=4000)["feasible"], "불가능 조건은 feasible=False"
assert len(compare_paths(T)) == 4
for bad in (lambda: required_output(0), lambda: required_output(True), lambda: required_output(T, "x"), lambda: required_output(T, selfgen_cut=0.1), lambda: min_green(0, T)):
    try: bad(); raise AssertionError("거절돼야 함")
    except ValueError: pass
assert S()["carbon"]["ets_value_eok"] is None, "배출권 가격 없으면 환산하지 않음"
assert near(S(ets_price=20000)["carbon"]["ets_value_eok"], S()["carbon"]["abate_tco2"] * 2e4 / 1e8), "참고 가치 = 순 저감 x 가정 가격"
for bad in (5000, 40000, True, "2만"):
    assert rejects(ets_price=bad), f"ets_price={bad!r} 거절돼야 함"
from src.assistant_tools import call_tool
assert call_tool("simulate", {})["status"] == "ask" and call_tool("simulate", {"eaf_mt": 1, "eaf_util": 2})["status"] == "refuse" and call_tool("simulate", {"eaf_mt": 1, "x": 1})["status"] == "refuse" and call_tool("nope")["status"] == "refuse", "도구 래퍼: 되묻기·거절"
assert call_tool("simulate", {"eaf_mt": 1})["status"] == "ok" and "eaf_util" in call_tool("simulate", {"eaf_mt": 1})["defaults_used"], "기본값 사용 변수 표시"
from src.load_profile import load_uci, price, reform_band
from src.simulator import DATA
u = load_uci(DATA); ub = reform_band(u, mid=(11, 13, 14)); pr = price(u, ub, True, "A2")
pick = lambda sea, day, h: pr[(u.sea == sea) & (u.day == day) & (u.h == h)].iloc[0]
assert near(pick("봄가을", "휴일", 12), 0.5 * (110.9 + 5.1)), "봄가을 일·공휴일 11~14시: 경부하 단가(개편 후)의 50%"
assert near(pick("봄가을", "토", 12), 0.5 * 133.4), "봄가을 토요일 11~14시: 중간부하 단가의 50%"
assert near(pick("봄가을", "휴일", 14), 116.0) and near(pick("여름", "휴일", 12), 116.0 - 5.1 + 5.1) and near(pick("봄가을", "평일", 12), 133.4), "할인은 봄가을 주말·공휴일 11~14시에만"
assert near(price(u, ub, True, "A2", weekend=False)[(u.sea == "봄가을") & (u.day == "휴일") & (u.h == 12)].iloc[0], 116.0), "weekend=False면 할인 없음"
from src.target import sweep_green
sw = sweep_green(0.5, 50e4, "green_supply_twh", [0, 0.5, 1.0])
assert [near(r["gap_twh"], min_green(0.5, 50e4, green_supply_twh=v)["gap_twh"]) for r, v in zip(sw, (0, 0.5, 1.0))] == [True] * 3 and sw[-1]["met"] and "연간" in sw[0]["note"], "sweep이 min_green과 일치, 한계 note 포함"
assert [r["green_share"] for r in sweep_green(0.5, 50e4, "h2_kwh_t", [3000, 4000])][0] < sweep_green(0.5, 50e4, "h2_kwh_t", [3000, 4000])[1]["green_share"], "전력 원단위가 클수록 필요 무탄소 비율이 큼"
for bad in (lambda: sweep_green(0.5, 50e4, "plan", [1]), lambda: sweep_green(0.5, 50e4, "h2_kwh_t", []), lambda: sweep_green(0.5, 50e4, "h2_kwh_t", [99999])):
    try: bad(); raise AssertionError("거절돼야 함")
    except ValueError: pass
assert call_tool("sweep_green", {"h2_output_mt": 0.5, "target_abate_t": 50e4, "vary": "green_supply_twh", "values": [0, 0.5]})["status"] == "ok" and call_tool("sweep_green", {"vary": "x"})["status"] == "ask", "도구 래퍼 sweep"
from src.target import close_gap
cg = close_gap(0.5, 50e4, 0.3)
assert not cg["met"] and len(cg["levers"]) == 6 and all(l["check_gap_twh"] is not None and abs(l["check_gap_twh"]) < 1e-9 for l in cg["levers"] if l["lever"] != "switch_to_eaf" and l["in_range"]), "close_gap 각 레버를 다시 넣으면 부족분 0"
assert close_gap(0.5, 50e4, 5.0)["levers"] == [] and close_gap(0.5, 150e4, 0.3)["levers"] == [], "부족분 없음/불가능이면 레버 없음"
assert call_tool("close_gap", {"h2_output_mt": 0.5, "target_abate_t": 50e4})["status"] == "ask" and call_tool("close_gap", {"h2_output_mt": 0.5, "target_abate_t": 50e4, "green_supply_twh": 0.3})["status"] == "ok", "도구 래퍼 close_gap"
from src.assistant_tools import TOOL_SCHEMAS, TOOLS, VARS
assert set(TOOL_SCHEMAS) == set(TOOLS) and set(TOOL_SCHEMAS["simulate"]["properties"]) == set(VARS), "도구 스키마와 도구 목록·변수 일치"
import pandas as pd
from src.load_profile import shift_peak
tiny = pd.DataFrame(dict(date=["a"] * 4, kwh=[1.0] * 4))
try: shift_peak(tiny, pd.Series(["최", "최", "중", "중"]), 0.5); raise AssertionError("경부하 없는 날은 거절돼야 함")
except ValueError: pass
assert near(shift_peak(u, u.band, 0.5).sum(), u.kwh.sum(), rel=1e-9), "실제 UCI에서 최대부하 이동은 에너지를 보존"
print("[내부 정합성] 통과")

# 2. 외부 수치 대조 (일치 여부와 차이를 그대로 보고)
s1 = S()
unit = s1["cost"]["unit_krw_kwh"]
print(f"[요금] S1 kWh당 총요금 {unit:.1f}원 (기본·부가·기금 포함) vs 산업용 평균 판매단가 2025년 181.9원(스마트비즈): 차이 {unit-181.9:+.1f}원. 요금제별 범위 {min(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}~{max(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}원")
cut = S(eaf_util=1.0)["carbon"]["scope1_cut_tco2"]
print(f"[전기로 감축] 가동률 100% 상향식 Scope 1 감축 {cut/1e4:.0f}만 t(전력 배출 전), 포스코 주장 연 최대 350만 t은 경계 미확인이라 S1P(posco_net)로 따로 계산. Factbook Scope 1 {SCOPE1_T/1e4:.0f}만 t의 {cut/SCOPE1_T*100:.1f}%")
print(f"[Scope 2 역산] Factbook 1.40Mt ÷ 구매 {BUY_TWH} TWh = {SCOPE2_T/1e6/BUY_TWH:.3f} t/MWh (공식 2020~22 평균 0.4541과 같은 기준, 현재 기본값 0.4173과는 {0.4173/ (SCOPE2_T/1e6/BUY_TWH)-1:+.0%})")
print(f"[총 전력] 2024: 3.05÷(1-0.855)={3.05/0.145:.1f} TWh, 2021: 3.8÷(1-0.85)={3.8/0.15:.1f} TWh -> total_twh 범위 {RANGE['total_twh']}")
print(f"[전기로 전력] 100% 가동 구매전력 증가 {full['power']['buy_increase_pct']:.0f}% (현재 구매전력 대비)")
print("\n검증 완료")
