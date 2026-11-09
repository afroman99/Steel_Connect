"""탄소 저감 경로 비교 (처음부터 끝까지 실행): 같은 1백만 t을 전기로 vs 수소환원으로 만들 때 전력·탄소·비용, 그리고 전력배출계수가 바뀌면 어떻게 달라지나.
실행: 프로젝트 루트에서 python3 analysis/06_경로비교.py  (그림은 figures/에 저장)
경계: 두 경로 모두 고로 Scope 1 1.99 t/t 대비(전기로는 직접 배출 0.08 + 구매 전력 배출, 수소환원은 논문 전력 원단위). 포스코 주장 순감축 1.4 t/t는 참고 행으로 따로 표시. 고철 공급 한계와 설비 투자비는 반영하지 않았다.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.plot_setup import setup_korean_font
from src.simulator import Scenario, breakeven_grid, simulate

# fmt: off
setup_korean_font()
GF = Scenario().grid_factor  # 0.4173 (2023 확정)
PATHS = {"전기로(고철)": dict(eaf_mt=1, eaf_util=1, h2_mt=0), "수소환원(전력망)": dict(eaf_mt=0, h2_mt=1, h2_util=1),
         "수소환원(무탄소 50%)": dict(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=0.5), "수소환원(무탄소 100%)": dict(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=1.0),
         "전기로(포스코 주장 순감축 1.4)": dict(eaf_mt=1, eaf_util=1, h2_mt=0, eaf_basis="posco_net")}

# 1. 같은 1백만 t을 만들 때 (전력배출계수 0.4173)
rows = {}
for n, kw in PATHS.items():
    r = simulate(**kw); p, c, k = r["power"], r["carbon"], r["cost"]
    rows[n] = {"전력 TWh": p["add_twh"], "Scope 2 증가 만t": c["add_tco2"] / 1e4, "Scope 1 감축 만t": (c["scope1_cut_tco2"] or float("nan")) / 1e4, "순 저감 만t": c["abate_tco2"] / 1e4,
               "전력 1MWh당 저감 t": c["abate_per_mwh"], "전력비용 억원": k["total_eok"], "저감 1t당 전력비용 만원": (k["power_cost_per_tco2_krw"] or float("nan")) / 1e4}
tab = pd.DataFrame(rows).T
print(f"[경로 비교: 1백만 t, 전력배출계수 {GF}]"); print(tab.round(2).to_string())
e, h = tab.loc["전기로(고철)"], tab.loc["수소환원(전력망)"]
print(f"  -> 전력 1MWh당 저감: 전기로 {e['전력 1MWh당 저감 t']:.2f} t vs 수소환원 {h['전력 1MWh당 저감 t']:.2f} t (전기로가 {e['전력 1MWh당 저감 t']/h['전력 1MWh당 저감 t']:.0f}배)")

# 2. 손익분기 전력배출계수: 이보다 더러운 전력이면 수소환원이 배출을 늘린다
print(f"\n[손익분기 배출계수] 기본(3720 kWh/t, 고로 1.99) {breakeven_grid():.3f} | 논문 조건(3720, EU 고로 1.688) {breakeven_grid(3720, 1.688):.3f} (논문 0.456) | 현재 한국 {GF}, 2020~22 평균 0.4541")
grid = pd.DataFrame({f"고로 {b}": {f"{k}": breakeven_grid(k, b) for k in (2700, 3100, 3500, 3720, 4000)} for b in (1.6, 1.69, 1.99, 2.1)}).round(3)
grid.index.name = "전력 원단위 kWh/t"; print(grid.to_string())

# 3. 그림: 전력배출계수에 따른 순 저감 (시뮬레이터 결과의 전력·감축량을 가져와 계수만 바꿔 계산)
b = {n: (simulate(**kw)["power"]["add_twh"], simulate(**kw)["carbon"]["scope1_cut_tco2"]) for n, kw in list(PATHS.items())[:2]}
gf = np.linspace(0, 0.6, 61)
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
for n, (twh, cut) in b.items(): ax[0].plot(gf, (cut - twh * 1e6 * gf) / 1e4, label=n)
ax[0].axhline(0, c="k", lw=0.8); ax[0].axvline(GF, ls="--", c="gray"); ax[0].text(GF + 0.005, ax[0].get_ylim()[1] * 0.9, f"한국 2023 {GF}", color="gray")
ax[0].axvline(breakeven_grid(), ls=":", c="C1"); ax[0].set(title="전력배출계수에 따른 순 저감 (1백만 t)", xlabel="전력배출계수 (tCO2/MWh)", ylabel="순 저감 (만 tCO2)"); ax[0].legend()
gr = np.linspace(0, 1, 11); ax[1].plot(gr * 100, [simulate(eaf_mt=0, h2_mt=1, h2_util=1, h2_green=g)["carbon"]["abate_tco2"] / 1e4 for g in gr], marker="o")
ax[1].axhline(tab.loc["전기로(고철)", "순 저감 만t"], ls="--", c="C0", label="전기로(고철) 1백만 t"); ax[1].set(title="수소환원 전력 중 무탄소 비율에 따른 순 저감 (1백만 t)", xlabel="무탄소 전력 비율 (%)", ylabel="순 저감 (만 tCO2)"); ax[1].legend()
fig.savefig(ROOT / "figures/06_경로비교.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/06_경로비교.png")
