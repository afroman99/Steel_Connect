"""UCI 부하 분석 (처음부터 끝까지 실행): 시간별 부하 프로파일, 기저부하, 2026 요금 개편 효과, 최대부하 이동 효과.
실행: 프로젝트 루트에서 python3 analysis/01_부하분석.py  (그림은 figures/에 저장)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.load_profile import (
    annual_cost,
    baseload,
    hourly_profile,
    load_uci,
    reform_band,
    shift_peak,
)
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()
d = load_uci(ROOT / "data/Steel_industry_data.csv")
VARIANTS = {"B. 11~12·13~15시 중간 + 18~21시 최대": reform_band(d, mid=(11, 13, 14))}  # 2026 개편 후 확정 시간대(한전 안내문). 기사의 9~15시 해석(A)은 폐기
M = lambda x: x / 1e6  # 원 -> 백만원

# 1. 기본 현황
print(f"[기본] {len(d):,}행, 총 {d.kwh.sum()/1e3:,.1f} MWh, 최대수요 {d.kw.max():.1f} kW, 평균 {d.kw.mean():.1f} kW, 부하율 {d.kw.mean()/d.kw.max():.2f}")
print("[요일유형] 일수:", d.groupby("day").date.nunique().to_dict(), "| 사용량 비중(%):", (d.groupby("day").kwh.sum() / d.kwh.sum() * 100).round(1).to_dict())
bl = baseload(d)
print(f"[기저부하] 평일 0~5시 중앙값 {bl:.1f} kW -> 24시간 지속 가정 시 연 {bl*8760/1e3:.0f} MWh ({bl*8760/d.kwh.sum()*100:.1f}%), 평일 낮 12시 평균 {hourly_profile(d).loc[12,'평일']:.1f} kW")

# 2. 요금 시간대별 사용량 비중과 2026 개편 효과 (UCI 2018 부하 x 2025-04 요금표 + 개편 변화). 개편 = 시간대 변경 + 단가 조정 + 봄·가을 주말 낮 50% 할인
old = annual_cost(d, d.band)
print(f"\n[요금] 2025 요금·기존 시간대: {M(old['total']):.1f}백만원 (평균 {old['avg']:.1f}원/kWh, 기본요금 {M(old['basic']):.1f})")
flat = d.assign(kwh=1.0)  # 24시간 일정 부하 (기사 비교용)
f_old = annual_cost(flat, flat.band)["avg"]
share = {"기존": d.groupby("band").kwh.sum() / d.kwh.sum()}
for name, b in VARIANTS.items():
    new, f_new = annual_cost(d, b, True), annual_cost(flat, b.rename(None), True)["avg"]
    share[name[:1]] = d.groupby(b).kwh.sum() / d.kwh.sum()
    b0 = annual_cost(d, b, False); b1 = annual_cost(d, b, True, weekend=False)  # 시간대만 / 시간대+단가
    print(f"  분해(UCI 실부하, 백만원): 시간대 변경 {M(b0['total']-old['total']):+.2f}, 단가 조정 {M(b1['total']-b0['total']):+.2f}, 주말 낮 할인 {M(new['total']-b1['total']):+.2f}, 합계 {M(new['total']-old['total']):+.2f}")
    print(f"  {name}: {M(new['total']):.1f}백만원 ({(new['total']/old['total']-1)*100:+.1f}%), 평균 {new['avg']:.1f}원/kWh ({new['avg']-old['avg']:+.2f}) | 24시간 일정 부하 {f_new-f_old:+.2f}원/kWh (기사: 약 -1.0)")

# 3. 최대부하 이동 효과 (기존 시간대와 2026 개편 후 비교)
fs = np.linspace(0, 0.5, 11)
cost = {n: [M(annual_cost(d, b, r, shift_peak(d, b, f))["total"]) for f in fs] for n, b, r in (("2025 요금", d.band, False), ("2026 개편 후", VARIANTS["B. 11~12·13~15시 중간 + 18~21시 최대"], True))}
for n, c in cost.items():
    print(f"[부하 이동] {n}: 최대부하 20% 이동 시 {c[4]-c[0]:+.1f}백만원 ({(c[4]/c[0]-1)*100:+.1f}%), 50% 이동 시 {c[-1]-c[0]:+.1f}백만원")

# 4. 그림
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
hourly_profile(d).plot(ax=ax[0], marker="o", ms=3); ax[0].set(title="요일유형별 시간별 평균 부하", xlabel="시각", ylabel="kW"); ax[0].axhline(bl, ls="--", c="gray")
ax[0].text(12.5, bl + 25, f"기저부하 {bl:.0f} kW (점선)", color="gray")
sh = (__import__("pandas").DataFrame(share).reindex(["경", "중", "최"]) * 100); sh.T.plot.bar(stacked=True, ax=ax[1], rot=0); ax[1].set(title="요금 시간대별 사용량 비중 (개편 전 vs 개편 후)", ylabel="%"); ax[1].legend(title="시간대", loc="center left", bbox_to_anchor=(1, 0.5))
for n, c in cost.items(): ax[2].plot(fs * 100, c, marker="o", label=n)
ax[2].set(title="최대부하 사용량을 경부하로 옮길 때 연 요금", xlabel="이동 비율 (%)", ylabel="백만원"); ax[2].legend()
fig.savefig(ROOT / "figures/01_부하분석.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/01_부하분석.png")
