"""시뮬레이터 민감도·불확실성 분석 (처음부터 끝까지 실행): 토네이도 + 몬테카를로.
자체 발전 감소율(selfgen_cut)은 근거가 약해 불확실성으로 섞지 않고 시나리오 축(0, 15, 30%)으로 나눠 본다.
실행: 프로젝트 루트에서 python3 analysis/04_민감도분석.py  (그림은 figures/에 저장)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.plot_setup import setup_korean_font
from src.sensitivity import monte_carlo, rank_corr, tornado
from src.simulator import Scenario

# fmt: off
setup_korean_font()
NAME = {"add_tco2": "Scope 2 증가(tCO2)", "net_tco2": "순 탄소(Scope 2 증가 - Scope 1 감축, tCO2)", "total_eok": "요금(억 원)"}

# 1. 토네이도: 자체 발전 감소 0%(S1)와 15%(S2) 두 기준에서 변수를 하나씩 허용 범위 끝으로. eaf_mt는 사업 규모라 제외
tor = {}
for n, sc in (("S1(감소 0%)", Scenario()), ("S2(감소 15%)", Scenario(selfgen_cut=0.15))):
    b0, t = tor[n] = tornado(sc, drop=('eaf_mt', 'h2_mt', 'h2_util', 'h2_kwh_t', 'h2_green', 'h2_bf_t', 'h2_resid_t'))
    print(f"[기준 {n}] Scope 2 증가 {b0['add_tco2']/1e4:.1f}만 t, 순 탄소 {b0['net_tco2']/1e4:.1f}만 t, 요금 {b0['total_eok']:,.0f}억")
    for m in ("net_tco2", "total_eok"):
        sw = (t[f"{m}_hi"] - t[f"{m}_lo"]).abs().sort_values(ascending=False)
        print(f"  토네이도 {NAME[m]} 변동폭 큰 순:", {k: round(v / (1e4 if m != 'total_eok' else 1), 1) for k, v in sw.head(6).items()})

# 2. 몬테카를로 (1만 회, 전기로 규모 2.5Mt 고정). 자체 발전 감소율을 시나리오 축으로 나누고, 분포 가정(균등/삼각)도 바꿔 본다
runs = {}
for cut in (0.0, 0.15, 0.30):
    for dist in ("uniform", "tri"):
        X, Y = runs[(cut, dist)] = monte_carlo(fixed={"eaf_mt": 2.5, "selfgen_cut": cut, "h2_mt": 0.0}, dist=dist)
        q = Y.quantile([0.05, 0.5, 0.95])
        print(f"\n[몬테카를로 감소 {cut:.0%}, {dist}] 5/50/95% 순 탄소 {(q.net_tco2/1e4).round(0).tolist()}만 t, 요금 {q.total_eok.round(0).tolist()}억, 가정한 분포에서 순 탄소가 0보다 큰 표본 비율 {(Y.net_tco2>0).mean():.0%}")
        if dist == "uniform":
            print("  순 탄소 순위상관 점수(%, 분산 기여도 아님):", rank_corr(X, Y, "net_tco2").round(1).head(4).to_dict())
            print("  요금 순위상관 점수(%, 분산 기여도 아님):", rank_corr(X, Y, "total_eok").round(1).head(4).to_dict())

# 2-2. 수소환원(S4, 포항 실증 30만 t) 기준: 전기로·자체 발전 감소 없이 수소환원 변수만 흔든다
b4, t4 = tornado(Scenario(eaf_mt=0, h2_mt=0.3), drop=("eaf_mt", "h2_mt", "eaf_kwh_t", "eaf_util", "selfgen_cut", "bf_replace", "bf_tco2_t", "eaf_direct_t"))
sw = (t4.net_tco2_hi - t4.net_tco2_lo).abs().sort_values(ascending=False)
print(f"\n[토네이도 S4] 기준 순 저감 {-b4['net_tco2']/1e4:.1f}만 t, 변동폭(만 t) 큰 순:", {k: round(v / 1e4, 1) for k, v in sw.head(5).items()})
for g in (0.0, 0.5, 1.0):  # 무탄소 전력 비율은 불확실성이 아니라 정책 선택이라 시나리오 축으로 나눈다
    X4, Y4 = monte_carlo(fixed={"eaf_mt": 0.0, "h2_mt": 0.3, "selfgen_cut": 0.0, "bf_replace": 0.0, "h2_green": g}, dist="uniform")
    q = (-Y4.net_tco2 / 1e4).quantile([0.05, 0.5, 0.95]).round(1).tolist()
    print(f"[몬테카를로 S4, 무탄소 {g:.0%}] 순 저감 5/50/95% {q}만 t, 가정한 분포에서 배출이 늘어난 표본 비율 {(Y4.net_tco2 >= 0).mean():.0%}, 순위상관 점수(%):", rank_corr(X4, Y4, "net_tco2").round(1).head(4).to_dict())

# 3. 그림
fig, ax = plt.subplots(1, 3, figsize=(18, 5))
b0, t = tor["S1(감소 0%)"]
o = (t.total_eok_hi - t.total_eok_lo).abs().sort_values().index
ax[0].barh(o, [t.total_eok_hi[k] - b0["total_eok"] for k in o], left=b0["total_eok"], label="범위 상한 쪽"); ax[0].barh(o, [t.total_eok_lo[k] - b0["total_eok"] for k in o], left=b0["total_eok"], label="범위 하한 쪽")
ax[0].axvline(b0["total_eok"], c="k", lw=1); ax[0].set(title="토네이도: 기준 S1 요금(억 원)", xlabel="억 원"); ax[0].legend()
for c, col in zip((0.0, 0.15, 0.30), ("C0", "C1", "C2")):
    ax[1].hist(runs[(c, "uniform")][1].net_tco2 / 1e4, bins=50, alpha=0.6, color=col, label=f"자체 발전 감소 {c:.0%}")
    ax[2].hist(runs[(c, "uniform")][1].total_eok, bins=50, alpha=0.6, color=col, label=f"자체 발전 감소 {c:.0%}")
ax[1].axvline(0, c="k", lw=1); ax[1].set(title="몬테카를로 순 탄소 (Scope 2 증가 - Scope 1 감축)", xlabel="만 tCO2"); ax[1].legend()
ax[2].set(title="몬테카를로 요금", xlabel="억 원"); ax[2].legend()
fig.savefig(ROOT / "figures/04_민감도분석.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/04_민감도분석.png")
