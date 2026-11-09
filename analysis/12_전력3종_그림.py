"""전력 3종(자체발전·전력망·무탄소) 구성이 전환 시나리오에서 어떻게 바뀌는지 그린다. 실행: 프로젝트 루트에서 python3 analysis/12_전력3종_그림.py -> figures/12_전력3종_구성.png
자체발전 감소율은 대체 생산량 ÷ 조강 35 Mt 비례 가정(근거 약함). 연간 전력량 기준, 시간대별 공급은 반영하지 않음."""

import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.plot_setup import setup_korean_font
from src.simulator import BUY_TWH, SELF_SHARE, TOTAL_TWH, simulate

# fmt: off
setup_korean_font()
CASES = {"현재(2024)": None, "전기로 S1": dict(), "수소환원 S4\n(전력망 전력)": dict(eaf_mt=0, h2_mt=0.3), "수소환원 S4G\n(무탄소 전력)": dict(eaf_mt=0, h2_mt=0.3, h2_green=1.0)}
rows = []
for kw in CASES.values():
    if kw is None: rows.append((TOTAL_TWH * SELF_SHARE, BUY_TWH, 0.0)); continue
    p = simulate(**kw)["power"]; c = (p["eaf_output_mt"] + p["h2_output_mt"]) / 35; r = simulate(selfgen_cut=c, **kw)["power"]
    green = r["h2_buy_twh"] * kw.get("h2_green", 0)
    rows.append((TOTAL_TWH * SELF_SHARE - r["selfgen_loss_twh"], BUY_TWH + r["add_twh"] - green, green))
COL = [("자체발전 (부생가스·LNG)", "#8c8c8c"), ("전력망 전력 (한전 구매)", "#d9822b"), ("무탄소 전력", "#2e8b57")]
fig, (ax, tx) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw=dict(width_ratios=[1.5, 1]))
x, bottom = range(len(CASES)), [0] * len(CASES)
for i, (lab, col) in enumerate(COL):
    v = [r[i] for r in rows]; ax.bar(x, v, bottom=bottom, color=col, label=lab, width=0.6)
    for j, (b, h) in enumerate(zip(bottom, v)):
        if h > 0.25: ax.text(j, b + h / 2, f"{h:.1f}", ha="center", va="center", color="white", fontsize=11, fontweight="bold")
    bottom = [b + h for b, h in zip(bottom, v)]
for j, t in enumerate(bottom): ax.text(j, t + 0.3, f"{t:.1f} TWh", ha="center", fontsize=10)
ax.set_xticks(list(x)); ax.set_xticklabels(list(CASES)); ax.set_ylabel("연간 전력 사용 (TWh)"); ax.set_ylim(0, 29); ax.legend(loc="upper left", fontsize=9, frameon=False, ncol=3)
ax.set_title("전환하면 전력 구성이 어떻게 바뀌나", loc="left", fontweight="bold"); ax.spines[["top", "right"]].set_visible(False)
tx.axis("off")
tx.text(0, 1, "전력 3종, 무엇이 다른가", fontsize=13, fontweight="bold", va="top")
for k, (t, d) in enumerate([("자체발전", "고로·코크스로 부생가스와 LNG를 태워\n제철소가 직접 만든 전력. 2024년 사용 전력의 85.5%.\n고로가 줄면 같이 줄어든다."),
                           ("전력망 전력", "한전에서 사 오는 전력. 요금이 붙고\n배출계수 0.4173 tCO2/MWh를 적용한다."),
                           ("무탄소 전력", "재생에너지·원전 등 배출이 거의 없는 전력.\n수소환원이 필요로 하는 목표 물량.")]):
    y = 0.88 - k * 0.27; tx.add_patch(plt.Rectangle((0, y - 0.19), 0.03, 0.21, color=COL[k][1], transform=tx.transAxes)); tx.text(0.06, y, t, fontsize=11, fontweight="bold", va="top"); tx.text(0.06, y - 0.045, d, fontsize=9.5, va="top", linespacing=1.5)
fig.text(0.01, 0.01, "출처: 포스코 ESG 에너지 페이지(자체 생산 85.5%), 한전 요금표, 기후부 2023 배출계수. 시뮬레이터 S1·S4·S4G(생산 능력 전기로 2.5 Mt·가동률 70%, 수소환원 0.3 Mt·가동률 70%).\n자체발전 감소는 대체 생산량÷조강 35 Mt 비례 가정(근거 약함). 연간 전력량 기준.", fontsize=8, color="#555")
fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(ROOT / "figures/12_전력3종_구성.png", dpi=150); print("저장:", rows)
