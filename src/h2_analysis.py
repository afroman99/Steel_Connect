"""그린 수소 vs 전력망 전기 상황 분석 함수: 무엇이 판단을 흔드는가(토네이도), 여러 조건이 함께 불확실할 때 그린이 이기는 비율(몬테카를로),
탄소 가격 x PPA 단가 추천 지도, 시점별(전력망이 깨끗해지는 경로) 갈림길. 숫자는 모두 src/hydrogen.py의 h2_supply(-> simulate)에서 나온다.
실행: analysis/17_그린수소_전력망_상황분석.py
주의: 수전해 설비비는 두 방법이 같다고 보고 뺐다. 범위·분포는 근거 범위 안에서 고른 가정이며 몬테카를로 비율은 현실의 확률이 아니라 가정한 분포에서의 비율이다.
"""

import numpy as np
import pandas as pd

from src.emission_factor import MEF_AVG_RATIO
from src.hydrogen import EUA_KRW, EUETS_1Y, KAU_NOW, KETS_1Y, PPA_DEFAULT, h2_supply
from src.simulator import PLANS, PPA_RANGE, RANGE

# fmt: off
GF_AVG = 0.4173                                   # 공식 연평균 (2023 확정 소비단)
GF_MARGINAL = round(GF_AVG * MEF_AVG_RATIO, 4)    # 한계 기준 = 공식 x 한계/평균(2025 거래소 자료, src/ext_data.marginal_ef)
BC_PLANS = [p for p in PLANS if p[0] in "BC"]  # 대규모 수전(154kV 이상) 요금제만 후보 (src/sensitivity.py와 같음)
# 토네이도 범위(근거 범위 안): 탄소 가격은 K-ETS 최근 1년, PPA는 근거 범위, 배출계수는 평균~한계 기준, 부가요금·요금 변동률은 시뮬레이터 허용 범위
TORNADO = dict(ets_price=(KETS_1Y["min"], KETS_1Y["max"]), ppa_krw_kwh=PPA_RANGE, grid_factor=(GF_AVG, GF_MARGINAL), adder=RANGE["adder"], price_change=RANGE["price_change"])


def gap(**kw):
    """gap = 쇳물 1t당 (그린 - 전력망) 비용(원, 탄소 비용 포함). 음수면 그린이 싸다. kw는 h2_supply 인자(h2_output_mt 기본 1)."""
    r = h2_supply(kw.pop("h2_output_mt", 1.0), **kw)
    o = {x["key"]: x for x in r["options"]}
    return o["green"]["krw_per_t"] - o["grid"]["krw_per_t"]


def pick(**kw):
    """pick = 추천. 'green'·'grid', 전력망 수소가 고로보다 나쁘면 'bf'(그린만 의미)."""
    v = h2_supply(kw.pop("h2_output_mt", 1.0), **kw)["verdict"]
    return "bf" if v["rule"] == "grid_worse_than_bf" else v["pick"]


def tornado(ranges=None, **base):
    """tornado = 토네이도. 기준 조건에서 변수 하나씩 범위 양 끝으로 바꿀 때 1t당 비용 차(gap)와 추천. 요금제는 B/C 6종 중 최소·최대.
    flip=True면 그 변수 하나만으로 추천이 바뀐다. swing(양 끝 차이)이 큰 순서로 정렬."""
    rows = []
    for k, (lo, hi) in (ranges or TORNADO).items():
        a, b = gap(**{**base, k: lo}), gap(**{**base, k: hi})
        rows.append(dict(변수=k, 낮은값=lo, 높은값=hi, gap_낮음=a, gap_높음=b))
    g = [gap(**{**base, "plan": p}) for p in BC_PLANS]
    rows.append(dict(변수="plan", 낮은값=BC_PLANS[int(np.argmin(g))], 높은값=BC_PLANS[int(np.argmax(g))], gap_낮음=min(g), gap_높음=max(g)))
    t = pd.DataFrame(rows).set_index("변수")
    t["swing"] = (t.gap_높음 - t.gap_낮음).abs()
    t["flip"] = np.sign(t.gap_낮음) != np.sign(t.gap_높음)
    return t.sort_values("swing", ascending=False)


def monte_carlo(world="kets", n=2000, seed=0, basis="both"):
    """monte_carlo = 여러 조건이 함께 불확실할 때 그린이 이기는 비율. world='kets'(탄소 가격 = K-ETS 최근 1년 최저·평균·최고 삼각분포) 또는 'eu'(EU ETS 최근 1년).
    PPA는 130~190원 삼각분포(최빈 180 = 2025 태양광 체감가), 요금제는 B/C 6종 균등, 부가요금·요금 변동률은 허용 범위 균등,
    배출계수는 basis='avg'(0.4173)·'marginal'(0.4525)·'both'(둘 사이 균등). 수소 원단위는 넣지 않는다(비용 차의 크기만 바꾸고 부호는 안 바꿈, gap_scales_with_h2 참고).
    돌려주는 값: 표본별 입력·gap·추천 DataFrame. 비율은 가정한 분포에서의 비율이며 현실의 확률이 아니다."""
    rng = np.random.default_rng(seed)
    e = KETS_1Y if world == "kets" else EUETS_1Y
    X = pd.DataFrame(dict(ets_price=rng.triangular(e["min"], e["mean"], e["max"], n), ppa_krw_kwh=rng.triangular(PPA_RANGE[0], PPA_DEFAULT, PPA_RANGE[1], n),
                          plan=rng.choice(BC_PLANS, n), adder=rng.uniform(*RANGE["adder"], n), price_change=rng.uniform(*RANGE["price_change"], n),
                          grid_factor={"avg": np.full(n, GF_AVG), "marginal": np.full(n, GF_MARGINAL)}.get(basis, rng.uniform(GF_AVG, GF_MARGINAL, n))))
    X["gap"] = [gap(**{k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()}) for r in X.to_dict("records")]
    X["pick"] = np.where(X.gap < 0, "green", "grid")
    return X


def verdict_map(x_var, x_vals, y_var, y_vals, **kw):
    """verdict_map = 두 변수(x, y)를 바꿔 가며 본 추천 표(green·grid·bf). 행 y, 열 x."""
    return pd.DataFrame([[pick(**{**kw, x_var: x, y_var: y}) for x in x_vals] for y in y_vals], index=list(y_vals), columns=list(x_vals))


def timeline(years=(2026, 2028, 2030, 2035), kinds=("정체", "14년 추세", "2018 기준 하락 속도"), ets_price=KAU_NOW, ppa_krw_kwh=PPA_DEFAULT):
    """timeline = 시점별 갈림길. 전력배출계수 시나리오(src/emission_factor.scenario, 예측이 아님)마다 그린이 유리해지는 탄소 가격과,
    주어진 탄소 가격에서 그린이 유리해지는 PPA 단가, 그 조건의 추천. 시뮬레이터 허용 범위(0.20~0.56)를 벗어나는 계수는 끝값으로 자른다."""
    from src.emission_factor import scenario
    lo, hi = RANGE["grid_factor"]
    rows = []
    for y in years:
        for k in kinds:
            gf = round(min(max(scenario(y, k), lo), hi), 4)
            r = h2_supply(1.0, grid_factor=gf, ets_price=ets_price, ppa_krw_kwh=ppa_krw_kwh)
            rows.append(dict(연도=y, 계수_시나리오=k, 배출계수=gf, 손익분기_탄소가격=r["thresholds"]["ets_breakeven"], 손익분기_PPA=r["thresholds"]["ppa_breakeven"],
                             전력망_1t당_순저감=r["thresholds"]["max_grid_abate_per_t"], 추천=pick(grid_factor=gf, ets_price=ets_price, ppa_krw_kwh=ppa_krw_kwh)))
    return pd.DataFrame(rows)


def gap_scales_with_h2(**kw):
    """gap_scales_with_h2 = 수소 원단위(h2_kg_t)를 근거 범위 양 끝(40, 60 kg/t)으로 바꿔도 비용 차의 부호(추천)는 같은지. (40, 60) 각각의 gap을 돌려준다.
    1t당 비용 차 = 수전해 MWh/t x (PPA 할증 - 탄소 가격 x 계수 / 1000)이라 수소량은 크기만 바꾼다."""
    return gap(**{**kw, "h2_kg_t": 40}), gap(**{**kw, "h2_kg_t": 60})


def situations(**kw):
    """situations = 상황 정리표. 대표 상황마다 조건과 추천·1t당 비용 차. 국내 지금 / 한계 기준 / PPA 하락 / EU 수준 탄소 가격 / 큰 감축 목표 / 전력망 개선(2030 낙관)."""
    cases = [("국내 지금 (K-ETS, 태양광 PPA 180원)", {}), ("배출계수를 한계 기준으로", dict(grid_factor=GF_MARGINAL)),
             ("PPA 150원 (정부 태양광 목표 발전단가)", dict(ppa_krw_kwh=150)), ("탄소 가격 K-ETS 1년 최고 30,850원", dict(ets_price=KETS_1Y["max"])),
             ("탄소 가격 EU 수준 131,595원", dict(ets_price=EUA_KRW)), ("감축 목표 쇳물 1t당 1.0 t", dict(target_abate_t=1.0e6)),
             ("전력망 2030 낙관(계수 0.245) + K-ETS", dict(grid_factor=0.245)), ("전력망 2030 낙관 + EU 수준 탄소 가격", dict(grid_factor=0.245, ets_price=EUA_KRW))]
    rows = []
    for name, c in cases:
        r = h2_supply(1.0, **{**kw, **c})
        o = {x["key"]: x for x in r["options"]}
        rows.append(dict(상황=name, 추천=r["verdict"]["pick"], 근거=r["verdict"]["rule"], 그린_빼기_전력망_원per_t=o["green"]["krw_per_t"] - o["grid"]["krw_per_t"],
                         손익분기_탄소가격=r["thresholds"]["ets_breakeven"], 그린_순저감=o["green"]["abate_per_t"], 전력망_순저감=o["grid"]["abate_per_t"]))
    return pd.DataFrame(rows).set_index("상황")


def uncertainty(world="kets", n=2000, basis="both", seed=0, h2_output_mt=1.0):
    """uncertainty = 어시스턴트용 요약. 토네이도(변수 하나씩 바꿨을 때 추천이 뒤집히는가)와 몬테카를로(여러 조건이 함께 불확실할 때 그린이 싼 비율)를 JSON으로 돌려준다.
    world='kets'(국내 탄소 가격 최근 1년) 또는 'eu'. n 최대 2000. 비율은 가정한 분포에서의 표본 비율이며 현실의 확률이 아니다."""
    if world not in ("kets", "eu") or basis not in ("avg", "marginal", "both") or not 100 <= n <= 2000:
        raise ValueError("world는 'kets'|'eu', basis는 'avg'|'marginal'|'both', n은 100~2000")
    t = tornado(h2_output_mt=h2_output_mt).reset_index()
    X = monte_carlo(world, int(n), seed, basis)
    win = X[X.pick == "green"]
    q = lambda c: [float(v) for v in X.gap.quantile([.05, .5, .95]).round(0)]
    return dict(h2_output_mt=h2_output_mt, world=world, basis=basis, n=int(n),
                tornado=[dict(var=r.변수, low=r.낮은값, high=r.높은값, gap_low=float(r.gap_낮음), gap_high=float(r.gap_높음), swing=float(r.swing), flip=bool(r.flip)) for r in t.itertuples()],
                flips=[r.변수 for r in t.itertuples() if r.flip],
                mc=dict(green_cheaper_pct=float((X.pick == "green").mean() * 100), gap_p5_median_p95=q(None),
                        green_win_median=dict(ppa_krw_kwh=float(win.ppa_krw_kwh.median()), price_change=float(win.price_change.median())) if len(win) else None),
                note="gap = 쇳물 1t당 (그린 - 전력망) 비용(원, 탄소 비용 포함, 음수면 그린이 쌈). 토네이도 범위: 탄소 가격 K-ETS 최근 1년, PPA 130~190원, 배출계수 평균~한계, 부가요금·요금 변동률 허용 범위. 수전해 설비비 제외. 가정한 분포에서의 비율이지 확률이 아니다.")
