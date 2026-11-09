"""감축 비용 곡선(MACC, Marginal Abatement Cost Curve: 탄소 1t을 줄이는 데 드는 비용을 싼 조치부터 늘어놓은 그림)을 만든다. 숫자는 모두 simulate·h2_supply에서 나온다.
쌓는 선택지(서로 겹치지 않음):
  eaf   전기로(고철) 전환: 고로 생산을 전기로로 대체, 전력은 한전. 1t당 비용 = 전기로 전력비용 전부 / 순 저감
  ppa   한전 전력을 직접PPA로: 기존 구매 전력(2024 Factbook 3.05 TWh) + 전기로 전력. 1t당 비용 = 추가 전력비용(PPA 할증) / 줄어든 Scope 2
  h2    수소환원(전력 100% 직접PPA): 수전해·공정 전력 모두 재생에너지. 1t당 비용 = 전력비용 전부 / 순 저감
수소환원 비교(쌓지 않음): 같은 수소환원을 전력망 전기 / 수전해만 직접PPA(h2_supply의 green) / 전부 직접PPA로 할 때의 1t당 비용.
주의: 전력비용만 본다(설비 투자비·고로 원료비 절감 미반영). '전부' 방식(eaf, h2)은 고로 원료비 절감이 빠져 실제보다 높게 나오는 상한 쪽 값이고,
'추가' 방식(ppa)은 같은 설비에서 전력 조달만 바꾸므로 그 문제가 없다. 폭(감축량)은 규모 가정에 비례하고 높이(원/tCO2)는 규모와 무관하다.
어시스턴트 도구: abatement_curve(JSON 결과, src/assistant_tools.py에 등록). 그림은 analysis/19_감축비용곡선.py
실행: 프로젝트 루트에서 python -m src.abatement
"""

from itertools import product
import math

import pandas as pd

from src.emission_factor import scenario
from src.h2_analysis import GF_MARGINAL
from src.hydrogen import EUA_KRW, KAU_NOW, PASS, PPA_DEFAULT, h2_supply
from src.simulator import BUY_TWH, ETS_RANGE, PPA_ADD, PPA_RANGE, SOURCES as SIM_SOURCES, finite_number, ppa_unit, simulate

# fmt: off
EAF_OUT, H2_OUT = 1.75, 1.0  # 규모 가정 (백만 t/년, 실제 생산량): 전기로 = 광양 250만 t x 가동률 70%(S1), 수소환원 = 비교 기준 100만 t(analysis/15와 같음, 상용 규모 근거 없음)
GF_2030_LOW = round(float(scenario(2030, "2018 기준 하락 속도")), 4)  # 전력망이 빨리 깨끗해지는 경우 2030 배출계수 0.245 (src/emission_factor.scenario, 예측 아님)
RANGES = dict(ppa_krw_kwh=PPA_RANGE, grid_factor=(GF_2030_LOW, GF_MARGINAL))  # 범위 막대: PPA 근거 범위 130~190원 x 배출계수 2030 낙관 0.245 ~ 한계 기준 0.4524
ASSUMPTIONS = ["전력비용만 비교: 설비 투자비, 고로 원료비(석탄·코크스) 절감, 고철 조달비는 넣지 않았다. '전부' 방식 값은 원료비 절감만큼 실제보다 높다",
               "직접PPA로 바꾼 전력만큼 한전 기본요금도 준다고 가정(simulate와 같음). 예비 계약전력이 남으면 PPA 할증이 더 커진다",
               "기존 구매 전력(3.05 TWh)의 실제 계약 단가는 모른다. 전환 전력과 같은 시뮬레이터 평균 단가를 썼다",
               "재생에너지는 연간 계약 물량 기준(시간 일치·저장 미반영). 필요한 재생에너지 확보량이 곡선 폭의 상한이다",
               "감축량 폭은 규모 가정(전기로 175만 t, 수소환원 100만 t)에 비례한다. 1t당 비용(높이)은 규모와 무관하다"]
NOTE = "전력비용 기준 감축 비용. 설비 투자비·고로 원료비 절감은 넣지 않았고, 재생에너지는 연간 계약 물량 기준이다"
SOURCES = {"scale": "전기로 175만 t = 광양 전기로 250만 t(뉴스룸) x 가동률 70%(S1 가정), 수소환원 100만 t = 비교 기준(상용 규모 근거 없음)", "buy_twh": SIM_SOURCES["buy_twh"],
           "ppa": SIM_SOURCES["ppa"], "ets_price": SIM_SOURCES["ets_price"], "range": "배출계수 2030 낙관 0.245(src/emission_factor.scenario, 2018~2023 하락 속도 연장), 한계 기준 0.4524(2025 전력거래소 자료, src/ext_data.marginal_ef)"}


def options(eaf_output_mt=EAF_OUT, h2_output_mt=H2_OUT, ppa_krw_kwh=PPA_DEFAULT, **kw):
    """options = 감축 선택지 표. 행마다 연 감축량(abate_mt, 백만 tCO2), 전력비용(cost_eok, 억 원), 감축 1t당 비용(krw_per_tco2), 필요 재생에너지(re_twh).
    stacked=True는 곡선에 쌓는 선택지, False는 수소환원 전력 조달 비교용. kw는 h2_supply와 같은 simulate 변수(grid_factor, h2_kwh_t, plan 등)."""
    finite_number("eaf_output_mt", eaf_output_mt, 0, 2.5, positive=True)
    if bad := sorted(set(kw) - PASS):
        raise ValueError(f"알 수 없는 인자 {bad}: {sorted(PASS)}만 받음 (근거 없음)")
    hs = h2_supply(h2_output_mt, ppa_krw_kwh=ppa_krw_kwh, **kw)
    o = {x["key"]: x for x in hs["options"]}
    e = simulate(**kw, eaf_mt=eaf_output_mt, eaf_util=1)
    full = simulate(**kw, eaf_mt=0, h2_mt=h2_output_mt, h2_util=1, h2_green=1, ppa_krw_kwh=ppa_krw_kwh)
    gf = e["input"]["grid_factor"]
    prem = ppa_unit(ppa_krw_kwh, e["input"]["fund"]) - e["cost"]["unit_krw_kwh"]  # 직접PPA가 한전보다 1 kWh당 비싼 정도 (원/kWh)
    ppa_twh = BUY_TWH + e["power"]["add_twh"]                                      # 직접PPA로 바꾸는 한전 전력 = 기존 구매 + 전기로 (TWh)
    t = h2_output_mt * 1e6

    def row(key, name, way, stacked, abate_t, cost_krw, re_twh, steel_t=None):
        return dict(key=key, name=name, way=way, stacked=stacked, abate_mt=abate_t / 1e6, cost_eok=cost_krw / 1e8, krw_per_tco2=cost_krw / abate_t if abate_t > 0 else None,
                    re_twh=re_twh, krw_per_t_steel=None if steel_t is None else cost_krw / steel_t, abate_per_t_steel=None if steel_t is None else abate_t / steel_t)

    rows = [row("eaf", f"전기로(고철) 전환 {eaf_output_mt * 100:g}만 t", "전부", True, e["carbon"]["abate_tco2"], e["cost"]["total_eok"] * 1e8, 0.0, eaf_output_mt * 1e6),
            row("ppa", f"한전 전력 {ppa_twh:.2f} TWh를 직접PPA로 (기존 구매 {BUY_TWH:g} + 전기로)", "추가", True, ppa_twh * 1e6 * gf, ppa_twh * 1e9 * prem, ppa_twh),
            row("h2", f"수소환원 {h2_output_mt * 100:g}만 t (전력 100% 직접PPA)", "전부", True, full["carbon"]["abate_tco2"], full["cost"]["total_eok"] * 1e8, full["power"]["h2_buy_twh"], t),
            row("h2_grid", "수소환원: 전력망 전기", "전부", False, o["grid"]["abate_tco2"], o["grid"]["power_cost_eok"] * 1e8, 0.0, t),
            row("h2_green", "수소환원: 수전해만 직접PPA (그린 수소)", "전부", False, o["green"]["abate_tco2"], o["green"]["power_cost_eok"] * 1e8, o["green"]["green_twh"], t),
            row("h2_full", "수소환원: 전력 100% 직접PPA", "전부", False, full["carbon"]["abate_tco2"], full["cost"]["total_eok"] * 1e8, full["power"]["h2_buy_twh"], t)]
    return pd.DataFrame(rows).set_index("key")


def option_ranges(ranges=None, **kw):
    """option_ranges = 범위 조합(기본 RANGES: PPA 양 끝 x 배출계수 양 끝, 4가지)마다 options를 다시 계산한 감축 1t당 비용의 최소(lo)·최대(hi). 기준값은 범위 안에 있다고 보장하지 않는다."""
    ranges = ranges or RANGES
    vals = [options(**{**kw, **dict(zip(ranges, combo))})["krw_per_tco2"] for combo in product(*ranges.values())]
    v = pd.concat(vals, axis=1)
    return pd.DataFrame(dict(lo=v.min(axis=1), hi=v.max(axis=1)))


def curve(**kw):
    """curve = 감축 비용 곡선. 쌓는 선택지(stacked)만 감축 1t당 비용이 싼 순서로 정렬하고, 누적 감축량 구간(x0~x1, 백만 tCO2)과 범위(lo, hi)를 붙인다."""
    c = options(**kw)
    c = c[c.stacked].join(option_ranges(**kw)).sort_values("krw_per_tco2")
    c["x1"] = c.abate_mt.cumsum()
    c["x0"] = c.x1 - c.abate_mt
    return c


def pays_at(price, c=None, **kw):
    """pays_at = 탄소 가격 price(원/tCO2)에서 전력비용이 탄소 비용 절감으로 덮이는 감축량(백만 tCO2/년). 곡선에서 1t당 비용이 price 이하인 선택지의 합."""
    finite_number("price", price, positive=True)
    c = curve(**kw) if c is None else c
    return float(c.loc[c.krw_per_tco2 <= price, "abate_mt"].sum())


def _records(df, cols):
    """_records = 표를 JSON에 바로 넣을 수 있는 dict 목록으로. NaN은 None, numpy 수는 파이썬 수."""
    out = []
    for k, r in df.iterrows():
        d = {"key": k}
        for col in cols:
            v = r[col]
            d[col] = None if v is None or (isinstance(v, float) and math.isnan(v)) else (bool(v) if col == "stacked" else v if isinstance(v, str) else float(v))
        out.append(d)
    return out


def abatement_curve(eaf_output_mt=EAF_OUT, h2_output_mt=H2_OUT, ppa_krw_kwh=PPA_DEFAULT, ets_price=None, **kw):
    """abatement_curve = 감축 비용 곡선(어시스턴트 도구용, JSON). 조치별 감축 1t당 전력비용을 싼 순서로(curve), 수소환원 전력 조달별 비교(h2_compare),
    탄소 가격별로 전력비용이 덮이는 감축량(pays), 직접PPA가 한전보다 싸지는 계약 단가(thresholds), 요약 문장(summary)을 돌려준다.
    ets_price를 주면 그 가격에서 덮이는 감축량도 계산한다. kw는 h2_supply와 같은 simulate 변수(grid_factor, h2_kwh_t, plan 등)."""
    if ets_price is not None:
        finite_number("ets_price", ets_price, *ETS_RANGE)
    args = dict(eaf_output_mt=eaf_output_mt, h2_output_mt=h2_output_mt, ppa_krw_kwh=ppa_krw_kwh, **kw)
    c = curve(**args)
    h = options(**args).loc[["h2_grid", "h2_green", "h2_full"]].join(option_ranges(**args))
    e = simulate(**kw, eaf_mt=eaf_output_mt, eaf_util=1)
    inp, unit_grid = e["input"], e["cost"]["unit_krw_kwh"]
    parity = (unit_grid / (1 + inp["fund"]) - PPA_ADD["net"] - PPA_ADD["settle"] - PPA_ADD["fee"]) / (1 + PPA_ADD["loss"])  # 이 계약 단가 이하면 직접PPA가 한전보다 싸다(감축 비용 음수)
    prices = [("K-ETS 시세", KAU_NOW), ("EU ETS 시세", EUA_KRW)] + ([("입력한 탄소 가격", ets_price)] if ets_price is not None else [])
    pays = [dict(name=n, price=p, abate_mt=pays_at(p, c), measures=[k for k, r in c.iterrows() if r.krw_per_tco2 <= p]) for n, p in prices]
    first, g, gr = c.iloc[0], h.loc["h2_green"], h.loc["h2_grid"]
    summary = [f"감축 1t당 전력비용이 가장 싼 조치는 {first['name']}({first.krw_per_tco2:,.0f}원/tCO2)",
               *[f"{r['name']}: 감축 1t당 {r.krw_per_tco2:,.0f}원 (범위 {r.lo:,.0f}~{r.hi:,.0f}), 연 {r.abate_mt:.2f}백만 tCO2" for _, r in c.iterrows()],
               *[f"탄소 가격 {p['price']:,.0f}원({p['name']})이면 전력비용이 탄소 비용 절감으로 덮이는 감축은 연 {p['abate_mt']:.2f}백만 tCO2 (전체 {c.abate_mt.sum():.2f})" for p in pays],
               f"직접PPA 계약 단가가 {parity:.0f}원/kWh 이하면 한전보다 싸서 탄소를 줄이면서 전력비용도 준다" + ("" if parity >= PPA_RANGE[0] else f" (근거 범위 {PPA_RANGE[0]}원보다 낮아 현재 PPA 시장에서는 해당 없음)"),
               f"수소환원은 쇳물 1t당 전력비용이 전력망 {gr.krw_per_t_steel:,.0f}원 < 그린 수소 {g.krw_per_t_steel:,.0f}원이지만, 감축 1t당으로는 전력망 {gr.krw_per_tco2:,.0f}원으로 그린 수소({g.krw_per_tco2:,.0f}원)의 {gr.krw_per_tco2 / g.krw_per_tco2:.1f}배"]
    cols = ["name", "way", "stacked", "abate_mt", "cost_eok", "krw_per_tco2", "lo", "hi", "re_twh", "krw_per_t_steel", "abate_per_t_steel"]
    applied = dict(eaf_output_mt=eaf_output_mt, h2_output_mt=h2_output_mt, ppa_krw_kwh=ppa_krw_kwh, **{k: inp[k] for k in sorted(PASS)})
    return dict(note=NOTE, curve=_records(c, cols + ["x0", "x1"]), h2_compare=_records(h, cols), pays=pays, summary=summary,
                thresholds=dict(ppa_parity_krw_kwh=parity, unit_grid_krw_kwh=unit_grid, unit_ppa_krw_kwh=ppa_unit(ppa_krw_kwh, inp["fund"]), re_twh_total=float(c.re_twh.sum())),
                range_basis=dict(ppa_krw_kwh=list(RANGES["ppa_krw_kwh"]), grid_factor=list(RANGES["grid_factor"]), note="범위 막대는 PPA 단가 양 끝 x 배출계수 양 끝 4가지 조합의 최소~최대(입력한 PPA·배출계수 대신 이 범위를 씀)"),
                ets_ref=dict(kau_now=KAU_NOW, eua_now=EUA_KRW), applied_input=applied, sources=dict(SOURCES), assumptions=list(ASSUMPTIONS))


if __name__ == "__main__":
    c = curve()
    for k, r in c.iterrows():
        print(f"[{r['name']}] 감축 1t당 {r.krw_per_tco2:,.0f}원 (범위 {r.lo:,.0f}~{r.hi:,.0f}), 연 {r.abate_mt:.2f}백만 t, 전력비용 {r.cost_eok:,.0f}억 원, 재생에너지 {r.re_twh:.2f} TWh ({r.way})")
    print(f"[탄소 가격별] K-ETS {KAU_NOW:,}원에서 {pays_at(KAU_NOW, c):.2f}백만 t, EU ETS {EUA_KRW:,}원에서 {pays_at(EUA_KRW, c):.2f}백만 t (전체 {c.abate_mt.sum():.2f})")
    for k, r in options().loc[["h2_grid", "h2_green", "h2_full"]].iterrows():
        print(f"[{r['name']}] 감축 1t당 {r.krw_per_tco2:,.0f}원, 쇳물 1t당 전력비용 {r.krw_per_t_steel:,.0f}원, 순 저감 {r.abate_per_t_steel:.2f} t/t")
