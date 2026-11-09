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
assert near(s1o["cost"]["total_eok"], 1403.44, 1e-4), "개편 전(2025, 공식 시간표) S1 요금 회귀"
assert near(s1["cost"]["total_eok"], 1394.60, 1e-4), "개편 후(B, 공식 시간표·주말 낮 할인 포함) S1 요금 회귀"
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
assert near(S(fund=0.037, band_rule="2025")["cost"]["total_eok"], 1417.11, 1e-4), "기금 3.7%·개편 전 요금(2025) 재현"
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
for bad in (5000, 200000, True, "2만"):
    assert rejects(ets_price=bad), f"ets_price={bad!r} 거절돼야 함"
assert not rejects(ets_price=29500) and not rejects(ets_price=157625), "K-ETS 현재 시세·EU ETS 1년 최고(ICAP) 허용"
from src.assistant_tools import call_tool
assert call_tool("simulate", {})["status"] == "ask" and call_tool("simulate", {"eaf_mt": 1, "eaf_util": 2})["status"] == "refuse" and call_tool("simulate", {"eaf_mt": 1, "x": 1})["status"] == "refuse" and call_tool("nope")["status"] == "refuse", "도구 래퍼: 되묻기·거절"
assert call_tool("simulate", {"eaf_mt": 1})["status"] == "ok" and "eaf_util" in call_tool("simulate", {"eaf_mt": 1})["defaults_used"], "기본값 사용 변수 표시"
from src.load_profile import annual_cost, load_uci, price, tou_band
from src.simulator import DATA, PPA_ADD, REFORM, RULES, avg_price, band_share, ppa_unit
u = load_uci(DATA); ub = tou_band(u, "B"); pr = price(u, ub, True, "A2")
# 요금 시간대 = 한전 공식표 (UCI 원본 라벨은 2018 옛 시간대라 쓰지 않음)
for rule in RULES:
    for sea, day in RULES[rule].items():
        assert len(day) == 24 and (day.count("경"), day.count("중"), day.count("최")) == (10, 8, 6), f"{rule} {sea}: 평일 경부하 10·중간 8·최대 6시간(한전 안내)"
assert all(ub[(u.day == "평일") & (u.sea == s) & (u.h == h)].eq(RULES["B"][s][h]).all() for s in RULES["B"] for h in range(24)), "평일은 공식 시간표 그대로"
assert not (ub[u.day == "토"] == "최").any() and (ub[u.day == "휴일"] == "경").all(), "토요일 최대부하 없음(중간으로 계량), 일·공휴일 종일 경부하"
assert RULES["2025"]["겨울"] == RULES["B"]["겨울"] and [h for h in range(24) if RULES["2025"]["여름"][h] != RULES["B"]["여름"][h]] == [11, 13, 14, 18, 19, 20], "개편은 3~10월 11·13·14시(최대->중간), 18~20시(중간->최대)만 바꿈"
days = u.groupby("day").date.nunique()
assert near(band_share("B"), (days["평일"] * 10 + days["토"] * 10 + days["휴일"] * 24) / (len(u) / 4)), "경부하 비중 = (평일·토 10시간 + 휴일 24시간) / 연 시간"
assert near(avg_price("B", "B3", "경"), price(u, ub, True, "B3")[ub == "경"].mean()), "경부하 평균 단가 = 경부하 행의 단가 평균"
tiny = u.assign(kwh=1.0); tiny.loc[(ub == "경") & (u.h == 3), "kwh"] = 9.0
assert near(annual_cost(tiny, ub)["basic"], 1.0 * 4 * PLANS["A2"][0] * 12), "요금적용전력은 중간·최대부하 최대수요(경부하 피크 제외)"
LOCAL = ROOT / "data/kepco_industrial_eul_tou_2026.json"  # 로컬 참고자료(git 미추적). 있으면 공식 요금표와 대조
if LOCAL.exists():
    import json
    off = json.loads(LOCAL.read_text(encoding="utf-8")); KEY = {"off_peak": "경", "mid_peak": "중", "on_peak": "최"}; SEA = {"summer": "여름", "spring_fall": "봄가을", "winter": "겨울"}
    assert all("".join(KEY[x] for x in off["hourly_map_weekday"][s]) == RULES["B"][k] for s, k in SEA.items()), "시간표 = 한전 2026 공식표(json)"
    for v in "ABC":
        for o, n in (("I", 1), ("II", 2), ("III", 3)):
            p = off["rates"][f"high_voltage_{v}"]["options"][o]
            assert p["basic_charge"] == PLANS[f"{v}{n}"][0] and all(abs(p["energy_charge"][s][b] - (PLANS[f"{v}{n}"][1][k][i] + REFORM[k][i])) < 1e-9 for s, k in SEA.items() for b, i in (("off_peak", 0), ("mid_peak", 1), ("on_peak", 2))), f"{v}{n} 2026 단가 = 2025 + 개편 변화"
    print("[요금표] 로컬 한전 2026 공식표(json)와 시간대·단가 9종 일치")
# 직접PPA 단가와 무탄소 전력 비용
assert near(ppa_unit(150), (150 * (1 + PPA_ADD["loss"]) + PPA_ADD["net"] + PPA_ADD["settle"] + PPA_ADD["fee"]) * 1.027), "PPA 부담 단가 = (계약가 x (1+손실) + 망이용료 + 부가정산금 + 수수료) x (1+기금)"
s4p = S(eaf_mt=0, h2_mt=0.3, h2_green=1.0, ppa_krw_kwh=180)
assert s4p["carbon"]["add_tco2"] == 0 and near(s4p["cost"]["total_eok"], s4["power"]["h2_buy_twh"] * 1e9 * ppa_unit(180) / 1e8) and s4p["cost"]["energy_eok"] == 0, "무탄소 100% + PPA면 요금은 전부 PPA 단가"
assert S(eaf_mt=0, h2_mt=0.3, h2_green=1.0)["cost"]["total_eok"] == s4["cost"]["total_eok"], "ppa_krw_kwh가 없으면 기존처럼 무탄소도 한전 요금"
h5 = S(eaf_mt=0, h2_mt=0.3, h2_green=0.5, ppa_krw_kwh=150)
assert near(h5["cost"]["total_eok"], s4["cost"]["total_eok"] / 2 + s4["power"]["h2_buy_twh"] * 0.5e9 * ppa_unit(150) / 1e8), "절반 PPA = 한전 요금 절반 + PPA 절반"
assert rejects(ppa_krw_kwh=100) and rejects(ppa_krw_kwh=250), "PPA 단가 범위 밖 거절"
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
assert near(shift_peak(u, ub, 0.5).sum(), u.kwh.sum(), rel=1e-9), "실제 UCI에서 최대부하 이동은 에너지를 보존"
# 그린 수소 vs 전력망 전기 (src/hydrogen.py): 숫자는 simulate와 일치해야 함
from src.hydrogen import h2_supply
hs = h2_supply(1.0); o = {x["key"]: x for x in hs["options"]}; th = hs["thresholds"]; sh = hs["split"]["elec_share"]
assert near(hs["split"]["elec_kwh_t"], 51 * 52.5) and near(hs["split"]["process_kwh_t"], 3720 - 51 * 52.5), "수전해 = 51 kg x 52.5 kWh, 공정 = 3720 - 수전해"
assert near(o["grid"]["scope2_tco2"], S(eaf_mt=0, h2_mt=1, h2_util=1)["carbon"]["add_tco2"]) and near(o["grid"]["power_cost_eok"], S(eaf_mt=0, h2_mt=1, h2_util=1)["cost"]["total_eok"]), "전력망 선택지 = simulate(수소환원 1Mt)"
assert near(o["green"]["scope2_tco2"], S(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=sh)["carbon"]["add_tco2"]) and near(o["green"]["scope2_tco2"], 1e6 * (3720 - 51 * 52.5) / 1000 * 0.4173), "그린 선택지 배출 = 공정 전력 x 계수"
assert near(o["green"]["krw_per_t"] - o["grid"]["krw_per_t"], 51 * 52.5 * (th["premium_krw_kwh"] - 29500 * 0.4173 / 1000)), "1t당 비용 차 = 수전해 kWh x (PPA 할증 - 탄소 가격 x 계수)"
assert near(o["green"]["abate_per_t"] - o["grid"]["abate_per_t"], th["extra_abate_per_t"]), "그린 추가 저감 = 수전해 MWh x 계수"
eq = {x["key"]: x for x in h2_supply(1.0, ets_price=th["ets_breakeven"])["options"]}
assert near(eq["green"]["krw_per_t"], eq["grid"]["krw_per_t"], 1e-9), "손익분기 탄소 가격에서 두 비용이 같다"
eq = {x["key"]: x for x in h2_supply(1.0, ppa_krw_kwh=th["ppa_breakeven"])["options"]} if 130 <= th["ppa_breakeven"] <= 190 else None
assert eq is None or near(eq["green"]["krw_per_t"], eq["grid"]["krw_per_t"], 1e-9), "손익분기 PPA 단가에서 두 비용이 같다"
assert near(th["gf_breakeven_bf"], breakeven_grid(3720, 1.99)), "고로 손익분기 = breakeven_grid"
for gi, gfv in enumerate(hs["map"]["gf"]):
    for pi, p in enumerate(hs["map"]["ets"]):
        v = h2_supply(1.0, grid_factor=gfv, ets_price=p)["verdict"]
        assert hs["map"]["cells"][pi][gi] == ("bf" if v["rule"] == "grid_worse_than_bf" else v["pick"]), f"추천 지도 칸({gfv}, {p}) = h2_supply 추천"
assert h2_supply(1.0, grid_factor=0.55)["verdict"]["rule"] == "grid_worse_than_bf" and h2_supply(1.0, ets_price=131595)["verdict"]["pick"] == "green", "계수가 손익분기 초과면 그린, EU 수준 탄소 가격이면 그린"
tg = h2_supply(1.0, target_abate_t=1.0e6)["verdict"]; assert tg["pick"] == "green" and tg["rule"] == "target" and tg["target_met"], "전력망으로 못 맞추는 목표면 그린"
mx = h2_supply(1.0, ets_price=131595, green_supply_twh=1.0)
assert not mx["supply_ok"] and any(x["key"] == "mix" for x in mx["options"]) and mx["verdict"]["notes"], "확보량 부족이면 혼합안과 경고"
assert near(next(x for x in mx["options"] if x["key"] == "mix")["green_twh"], 1.0), "혼합안의 그린 전력 = 확보량"
for bad in (dict(h2_kg_t=70), dict(elec_kwh_kg=40), dict(ppa_krw_kwh=100), dict(ets_price=5000), dict(h2_green=1), dict(h2_kwh_t=2800, h2_kg_t=60, elec_kwh_kg=58)):
    try: h2_supply(1.0, **bad); raise AssertionError(f"{bad} 거절돼야 함")
    except ValueError: pass
from src.emission_factor import HOUR_GF_RATIO, TOU_GF_RATIO
from src.hydrogen import HOURLY_MATCH
assert near(o["offpeak"]["scope2_tco2"], (1e6 * 51 * 52.5 * TOU_GF_RATIO["경"] + 1e6 * (3720 - 51 * 52.5)) / 1000 * 0.4173), "경부하 운전 배출 = 수전해 x 계수 x 경부하 비율 + 공정 x 계수"
sol = hs["hourly"]["rows"]["solar"]
assert near(sol["scope2_tco2"], (1e6 * 51 * 52.5 * (1 - HOURLY_MATCH["solar"]["share"]) * HOURLY_MATCH["solar"]["backfill_ratio"] + 1e6 * (3720 - 51 * 52.5)) / 1000 * 0.4173), "시간 일치 배출 = 못 채운 수전해 x 그 시간 계수 + 공정"
assert o["green"]["abate_per_t"] > hs["hourly"]["rows"]["mix"]["abate_per_t"] > sol["abate_per_t"] > o["grid"]["abate_per_t"], "순 저감: 연간 계약 그린 > 시간 일치 반반 > 시간 일치 태양광 > 전력망"
assert abs(sum(HOUR_GF_RATIO) / 24 - 1) < 0.01 and min(HOUR_GF_RATIO) == HOUR_GF_RATIO[12], "시각별 비율 평균 1, 정오가 가장 낮음(2025)"
from src.ext_data import hourly_match
assert hourly_match([1, 1, 1, 1], [1] * 4) == dict(share=1.0, surplus=0.0, backfill_ratio=0.0, storage_h=0.0) and near(hourly_match([2, 0], [1, 1])["share"], 0.5), "시간 일치 함수 손계산"
assert call_tool("h2_supply", {})["status"] == "ask" and call_tool("h2_supply", {"h2_output_mt": 1})["status"] == "ok" and call_tool("h2_supply", {"h2_output_mt": 1, "x": 1})["status"] == "refuse", "도구 래퍼 h2_supply"
from src import ext_data
if ext_data.available():  # 외부 원본(data/의 kpx_*·epsis_*·icap_*, ICAP만 git 제외)이 있으면 코드 상수를 다시 계산해 대조
    from src.hydrogen import EUETS_1Y, KETS_1Y
    gg = ext_data.hourly_grid(); tr = ext_data.tou_ratio(gg); mt = ext_data.match_table(None, gg); es = ext_data.ets_stats()
    assert all(abs(tr[b] - TOU_GF_RATIO[b]) < 1e-4 for b in tr) and all(abs(v - c) < 2e-3 for v, c in zip(gg.groupby("h").ratio.mean(), HOUR_GF_RATIO)), "시간대 배출 비율 상수 = 2025 거래소 자료 재계산"
    assert all(abs(mt[k][f] - HOURLY_MATCH[k][f]) < 1e-3 * max(1, HOURLY_MATCH[k][f]) for k in mt for f in ("share", "surplus", "backfill_ratio", "storage_h")), "시간 일치 상수 = 재계산"
    assert all(abs(es["kets"][f] - KETS_1Y[f]) < 1 and abs(es["euets"][f] - EUETS_1Y[f]) < 1 for f in ("min", "mean", "max")), "탄소 가격 1년 통계 상수 = ICAP 재계산"
    assert ext_data.sales_price()[2025] == 181.9, "2025 산업용 판매단가 181.9원(EPSIS)"
    mall = ext_data.marginal_ef(); avg_i = float((gg.intensity * gg.mwh).sum() / gg.mwh.sum())
    assert 0.9 < sum(mall["share"].values()) < 1.05 and mall["share"]["LNG"] > 0.5 and mall["mef"] > avg_i, "한계 배출: 주요 연료 반응 합 약 1, LNG가 한계 연료, 한계 > 평균"
    ms = ext_data.marginal_scenario()
    assert near(ms.loc["한계 기준", "배출계수"], round(0.4173 * mall["mef"] / avg_i, 4)) and (ms["추천"] == "grid").all(), "한계 기준 = 공식 계수 x 한계/평균, 현재 K-ETS에서 추천 그대로"
    assert near(ext_data.fuel_share().sum(), 100) and ext_data.data_checks().loc["kpx_fuel_hourly_2025.csv", "빈칸"] == 0, "연료 비중 합 100%, 거래소 자료 빈칸 없음"
    print("[외부 데이터] 시간대 배출 비율·시간 일치율·탄소 가격·판매단가 상수가 원본 재계산과 일치")
from src import eda
uraw = eda.read_csv(eda.UCI)
assert near(eda.implied_co2_factor(uraw), uraw["CO2(tCO2)"].sum() / uraw.Usage_kWh.sum() * 1000) and 0.42 < eda.implied_co2_factor(uraw) < 0.422, "UCI CO2 열 = 사용량 x 약 0.4208"
assert all(0 < v < 1 for v in eda.label_agreement(u).values()), "UCI 라벨은 공식 시간대와 일부만 일치(옛 시간대)"
fm = eda.factbook_metrics()
assert abs(fm.loc["구매 전력 TWh", "2024"] - BUY_TWH) < 0.01 and near(fm.loc["Scope 2 / 구매 전력 t/MWh", "2024"], SCOPE2_T / (fm.loc["구매 전력 TWh", "2024"] * 1e6)), "Factbook 구매 전력·Scope 2 원단위 = 시뮬레이터 상수와 일치"
qq = eda.quality(pd.DataFrame(dict(a=[0, 1, None], b=[-1, 2, 2])), key="b")
assert qq.loc["a", "결측"] == 1 and qq.loc["b", "음수"] == 1 and qq.attrs["중복"] == 1 and qq.loc["a", "0비율_%"] == 33.3, "품질 점검표 손계산"
assert eda.inventory().set_index("파일").loc["icap_systems.json", "git"] == "제외", "ICAP 원본은 git 제외로 표시"
print("[내부 정합성] 통과")

# 2. 외부 수치 대조 (일치 여부와 차이를 그대로 보고)
s1 = S()
unit = s1["cost"]["unit_krw_kwh"]
print(f"[요금] S1 kWh당 총요금 {unit:.1f}원 (기본·부가·기금 포함) vs 산업용 평균 판매단가 2025년 181.9원(EPSIS 한국전력통계, 2024년 168.2원): 차이 {unit-181.9:+.1f}원. 요금제별 범위 {min(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}~{max(S(plan=p)['cost']['unit_krw_kwh'] for p in PLANS):.0f}원")
cut = S(eaf_util=1.0)["carbon"]["scope1_cut_tco2"]
print(f"[전기로 감축] 가동률 100% 상향식 Scope 1 감축 {cut/1e4:.0f}만 t(전력 배출 전), 포스코 주장 연 최대 350만 t은 경계 미확인이라 S1P(posco_net)로 따로 계산. Factbook Scope 1 {SCOPE1_T/1e4:.0f}만 t의 {cut/SCOPE1_T*100:.1f}%")
print(f"[Scope 2 역산] Factbook 1.40Mt ÷ 구매 {BUY_TWH} TWh = {SCOPE2_T/1e6/BUY_TWH:.3f} t/MWh (공식 2020~22 평균 0.4541과 같은 기준, 현재 기본값 0.4173과는 {0.4173/ (SCOPE2_T/1e6/BUY_TWH)-1:+.0%})")
print(f"[총 전력] 2024: 3.05÷(1-0.855)={3.05/0.145:.1f} TWh, 2021: 3.8÷(1-0.85)={3.8/0.15:.1f} TWh -> total_twh 범위 {RANGE['total_twh']}")
print(f"[전기로 전력] 100% 가동 구매전력 증가 {full['power']['buy_increase_pct']:.0f}% (현재 구매전력 대비)")
print(f"[수소 조달] 쇳물 1t당 수소 51 kg x 52.5 kWh = {51*52.5:.0f} kWh vs Bhaskar 2020 수전해 2,680 kWh/t, 포스코 HyREX 추정 2,500~3,500 kWh/t(로컬 자료, 쇳물 기준·추정치)")
print(f"[그린 vs 전력망] 기본 조건 추천 {hs['verdict']['pick']}, 손익분기 탄소 가격 {th['ets_breakeven']:,.0f}원/t vs K-ETS 29,500원·EU ETS 131,595원 (2026-11-09)")
print("\n검증 완료")
