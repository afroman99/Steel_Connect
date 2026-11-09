"""전력배출계수 추세와 수소환원 손익분기 지도 (처음부터 끝까지 실행).
질문: 수소환원이 고로보다, 그리고 전기로(고철)보다 탄소를 더 줄이려면 전력이 얼마나 깨끗해야 하나? 한국 전력은 그 방향으로 가고 있나?
실행: 프로젝트 루트에서 python3 analysis/07_배출계수_손익분기지도.py  (그림은 figures/에 저장)
주의: 2010~2022 단년도 값은 참고용 산출이고 그림 라벨을 읽은 값이다. 추세 직선은 점이 적어 예측이 아니라 시나리오 범위로만 쓴다.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.emission_factor import GRID, scenario, trend
from src.plot_setup import setup_korean_font
from src.simulator import breakeven_grid, green_needed

# fmt: off
setup_korean_font()
BE, BE_PAPER = breakeven_grid(), breakeven_grid(3720, 1.688)  # 손익분기: 포스코 평균 고로 1.99 기준 / 논문 EU 고로 기준
KINDS = ("정체", "14년 추세", "2018 기준 하락 속도")

# 1. 한국 전력은 깨끗해지고 있나 (소비단 배출계수 2010~2023)
print(f"[검산] 2021~23 평균 {GRID.loc[2021:2023].mean():.4f} (공식 0.4330), 2018(온실가스 배출 정점 연도) {GRID.loc[2018]:.4f} -> 2023 {GRID.loc[2023]:.4f} ({(GRID.loc[2023]/GRID.loc[2018]-1)*100:.0f}%)")
for st in (2010, 2018):
    t = trend(st); print(f"[추세 {st}~2023, 점 {t['n']}개] 연 {t['slope']:+.4f} (회귀 가정하 기울기 95% 구간 {t['lo']:+.4f} ~ {t['hi']:+.4f}, 예측구간 아님)")

# 2. 시나리오: 수소환원 실증(2028)·상용화 기술(2030) 시점의 전력배출계수, 그리고 손익분기와의 거리
print(f"\n[손익분기] 고로 1.99 기준 {BE:.3f}, 논문 조건 {BE_PAPER:.3f}. 지금(2023) {GRID.loc[2023]:.4f}는 둘 다 아래")
print(f"[수소환원이 전기로(고철) 이상으로 저감하려면 필요한 무탄소 전력 비율] (전기로 순 저감: 상향식 같은 경계 / 포스코 주장 순감축 1.4 고정)")
for y in (2023, 2028, 2030, 2035):
    cols = [f"{k} {scenario(y, k):.3f} -> {green_needed(scenario(y, k)):.0%} (포스코 1.4: {green_needed(scenario(y, k), eaf_net_t=1.4):.0%})" for k in KINDS]
    print(f"  {y}년:", " | ".join(cols))
print(f"  2023 계수에서 상향식 {green_needed(0.4173):.0%} vs 포스코 순감축 1.4 기준 {green_needed(0.4173, eaf_net_t=1.4):.0%}. 두 값은 신뢰구간이 아니라 경계 가정에 따른 두 시나리오")

# 3. 그림
fig, ax = plt.subplots(1, 2, figsize=(14, 5.2))
gf, gr = np.linspace(0.1, 0.6, 101), np.linspace(0, 1, 101)
G, R = np.meshgrid(gf, gr)
net = 1.99 - 3.72 * G * (1 - R)  # 수소환원 1 t당 순 저감 (tCO2/t)
im = ax[0].contourf(G, R * 100, net, levels=np.linspace(-0.5, 2.0, 11), cmap="RdYlGn"); fig.colorbar(im, ax=ax[0], label="수소환원 순 저감 (tCO2/t)")
ax[0].contour(G, R * 100, net, levels=[0], colors="k", linewidths=2)
ax[0].contour(G, R * 100, net - (1.99 - 0.08 - 0.45 * G), levels=[0], colors="navy", linestyles="--", linewidths=2)
ax[0].contour(G, R * 100, net - 1.4, levels=[0], colors="purple", linestyles="-.", linewidths=1.5)
ax[0].plot(GRID.values, [0] * len(GRID), "|", c="k", ms=10)
for v, t in ((GRID.loc[2023], "2023"), (0.4541, "2020~22 평균")): ax[0].axvline(v, c="gray", ls=":", lw=1); ax[0].text(v - 0.004, 97, t, color="k", rotation=90, va="top", ha="right", fontsize=9, bbox=dict(fc="white", ec="none", alpha=0.7))
ax[0].text(0.56, 14, "검은 선: 고로와 같음\n(손익분기)", fontsize=9, ha="right", bbox=dict(fc="white", ec="none", alpha=0.7)); ax[0].text(0.58, 60, "파란 점선: 전기로(상향식)와 같음\n보라 일점쇄선: 포스코 순감축 1.4와 같음", color="navy", fontsize=9, ha="right")
ax[0].set(title="수소환원 손익분기 지도", xlabel="전력배출계수 (tCO2/MWh)", ylabel="무탄소 전력 비율 (%)", xlim=(0.1, 0.6))
yrs = np.arange(2023, 2036)
for k, c in zip(KINDS, ("C7", "C0", "C2")): ax[1].plot(yrs, [green_needed(scenario(y, k)) * 100 for y in yrs], marker="o", ms=3, c=c, label=f"전력배출계수 시나리오: {k}")
for k, c in zip(KINDS, ("C7", "C0", "C2")): ax[1].plot(yrs, [green_needed(scenario(y, k), eaf_net_t=1.4) * 100 for y in yrs], ls="--", c=c, alpha=0.6)
ax[1].plot([], [], ls="--", c="gray", label="점선: 포스코 순감축 1.4 기준")
for y in (2028, 2030): ax[1].axvline(y, ls=":", c="k", lw=0.8)
ax[1].text(2027.9, 5, "HyREX 실증 2028", fontsize=9, ha="right"); ax[1].text(2030.1, 5, "상용화 기술 2030", fontsize=9)
ax[1].set(title="수소환원이 전기로(고철)만큼 줄이려면 필요한 무탄소 전력 비율", xlabel="연도", ylabel="필요한 무탄소 비율 (%)", ylim=(0, 100)); ax[1].legend(fontsize=8, loc="upper right")
fig.savefig(ROOT / "figures/07_배출계수_손익분기지도.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/07_배출계수_손익분기지도.png")
