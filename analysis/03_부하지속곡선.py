"""UCI 부하지속곡선과 최대수요 관리(peak shaving) 가치 (처음부터 끝까지 실행).
실행: 프로젝트 루트에서 python3 analysis/03_부하지속곡선.py  (그림은 figures/에 저장)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.load_profile import annual_cost, load_duration, load_uci, peak_shave, tou_band
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()
d = load_uci(ROOT / "data/Steel_industry_data.csv")
band = tou_band(d, "B")  # 2026 개편 후 공식 시간대. 요금적용전력은 중간·최대부하 시간의 최대수요(경부하 피크 제외)
M = lambda x: x / 1e6
x, kw = load_duration(d)

# 1. 부하지속곡선: 최대 부하는 얼마나 드물게 나오나
print(f"[지속곡선] 최대 {kw.iloc[0]:.0f} kW")
for p in (0.5, 1, 5, 10):
    print(f"  상위 {p}% 시간의 문턱: {kw.iloc[int(len(kw)*p/100)]:.0f} kW (최대의 {kw.iloc[int(len(kw)*p/100)]/kw.iloc[0]*100:.0f}%)")
print("[월별 최대수요 kW]", d.groupby(d.t.dt.month).kw.max().round(0).astype(int).to_dict())

# 2. 상한(cap)을 낮추면: 기본요금 절감 vs 잘라야 하는 에너지
base = annual_cost(d, band, True)
caps = range(620, 299, -20)
res = pd.DataFrame([peak_shave(d, c, band, True) for c in caps]).set_index("cap")
print(f"\n[peak shaving] 2026 개편 후 요금 기준선 {M(base['total']):.1f}백만원 (기본요금 {M(base['basic']):.1f})")
print((res.assign(cut_kwh=res.cut_kwh.round(0), cut_pct=res.cut_pct.round(2), basic_save=(res.basic_save/1e6).round(2), energy_save_upper=(res.energy_save_upper/1e6).round(2))).loc[[600, 560, 500, 460, 400, 340]].to_string())
r = res.loc[500]; print(f"  -> 상한 500 kW: 기본요금 {M(r.basic_save):.1f}백만원 절감(기본요금의 {r.basic_save/base['basic']*100:.0f}%), 잘라낼 에너지는 연 사용량의 {r.cut_pct:.2f}%, {r.hours}시간")

# 3. 그림
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
ax[0].plot(x, kw); ax[0].set(title="부하지속곡선 (큰 순 정렬)", xlabel="전체 시간 중 비율 (%)", ylabel="kW"); ax[0].axhline(500, ls="--", c="gray"); ax[0].text(40, 510, "상한 500 kW 예시", color="gray")
ax[1].plot(res.cut_pct, res.basic_save / 1e6, marker="o"); ax[1].set(title="상한을 낮출 때 기본요금 절감 vs 잘라낼 에너지", xlabel="잘라낼 에너지 (연 사용량 %)", ylabel="기본요금 절감 (백만원)")
for c in (600, 500, 400): ax[1].annotate(f"{c} kW", (res.cut_pct[c], res.basic_save[c] / 1e6), textcoords="offset points", xytext=(6, -12))
fig.savefig(ROOT / "figures/03_부하지속곡선.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/03_부하지속곡선.png")
