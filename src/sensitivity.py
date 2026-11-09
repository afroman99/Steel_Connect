"""시뮬레이터 민감도·불확실성 분석 함수: 토네이도(한 변수씩), 몬테카를로(전 변수 동시), 순위상관 기여도.
자체 발전 감소율(selfgen_cut)은 근거가 약하고 범위가 결과를 지배하므로 불확실성이 아니라 시나리오 축으로 보고 fixed로 고정해 비교한다."""

from dataclasses import asdict

import numpy as np
import pandas as pd

from src.simulator import PLANS, RANGE, RULES, Scenario, simulate

# fmt: off
METRICS = {"add_twh": ("power", "add_twh"), "add_tco2": ("carbon", "add_tco2"), "net_tco2": ("carbon", "net_tco2"), "total_eok": ("cost", "total_eok")}
PLAN_CHOICES = [p for p in PLANS if p[0] in "BC"]  # 대규모 수전(154kV 이상)에 해당하는 요금제만 불확실성 후보로 본다
CATEGORICAL = {"band_rule": list(RULES), "plan": PLAN_CHOICES}


def run(**kw):
    """run = simulate 결과에서 핵심 지표(추가 전력 TWh, Scope 2 증가·순 탄소 tCO2, 요금 억 원)만 뽑는다."""
    r = simulate(**kw)
    return {m: r[a][b] for m, (a, b) in METRICS.items()}


def tornado(base=None, drop=("eaf_mt",)):
    """tornado = 토네이도. 기준 시나리오에서 변수 하나씩 허용 범위의 양 끝으로 움직일 때 지표 변화. 범주형(band_rule, plan)은 후보 중 최소·최대. drop은 불확실성이 아닌 변수 제외."""
    base = asdict(base or Scenario())
    b0, rows = run(**base), []
    for k, (lo, hi) in RANGE.items():
        if k in drop:
            continue
        a, c = run(**{**base, k: lo}), run(**{**base, k: hi})
        rows.append(dict(var=k, lo=lo, hi=hi, **{f"{m}_lo": a[m] for m in METRICS}, **{f"{m}_hi": c[m] for m in METRICS}))
    for k, choices in CATEGORICAL.items():
        v = pd.DataFrame([run(**{**base, k: c}) for c in choices])
        rows.append(dict(var=k, lo=f"{len(choices)}개 후보", hi="", **{f"{m}_lo": v[m].min() for m in METRICS}, **{f"{m}_hi": v[m].max() for m in METRICS}))
    return b0, pd.DataFrame(rows).set_index("var")


def monte_carlo(n=10000, seed=0, fixed=None, dist="uniform"):
    """monte_carlo = 몬테카를로. 변수를 허용 범위 안에서 n번 무작위로 뽑아 시뮬레이션. dist='uniform'은 범위 균등, 'tri'는 기본값을 최빈값으로 둔 삼각분포(기본값 쪽이 더 그럴듯하다는 가정).
    fixed={'변수': 값}으로 일부 고정. (입력 표본, 결과 표)를 돌려준다. 변수끼리는 독립이라고 가정한다."""
    rng, fixed, d0 = np.random.default_rng(seed), fixed or {}, asdict(Scenario())

    def draw(k, lo, hi):
        if k in fixed:
            return np.full(n, fixed[k])
        return rng.uniform(lo, hi, n) if dist == "uniform" else rng.triangular(lo, min(max(d0[k], lo), hi), hi, n)

    X = pd.DataFrame({k: draw(k, lo, hi) for k, (lo, hi) in RANGE.items()})
    for k, choices in CATEGORICAL.items():
        X[k] = np.full(n, fixed[k]) if k in fixed else rng.choice(choices, n)
    return X, pd.DataFrame([run(**r) for r in X.to_dict("records")])


def rank_corr(X, Y, metric):
    """rank_corr = 순위상관 기여도(근사). 수치 변수별 스피어만 상관의 제곱을 합 100%로 환산(고정한 변수는 제외). 정밀한 분산분해(Sobol)가 아니라 순서를 보는 용도."""
    s = pd.Series({k: X[k].corr(Y[metric], method="spearman") for k in RANGE if X[k].nunique() > 1}).pow(2).fillna(0)
    return (s / s.sum() * 100).sort_values(ascending=False)
