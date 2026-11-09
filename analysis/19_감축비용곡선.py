"""감축 비용 곡선 (처음부터 끝까지 실행): 탄소 1t을 줄이는 데 드는 전력비용을 조치별로 구해 싼 순서로 쌓고, 탄소 가격과 비교한다.
계산은 모두 src/abatement.py(-> simulate, h2_supply)가 한다. 이 스크립트는 결과를 출력하고 그림만 그린다.
실행: 프로젝트 루트에서 python3 analysis/19_감축비용곡선.py  (그림은 figures/19_감축비용곡선.png)
주의: 전력비용만 비교(설비 투자비·고로 원료비 절감 미반영). '전부' 방식 값은 원료비 절감만큼 실제보다 높은 상한 쪽 값. 예측이 아니라 조건부 시나리오.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.abatement import ASSUMPTIONS, GF_2030_LOW, RANGES, curve, option_ranges, options, pays_at
from src.hydrogen import EUA_KRW, KAU_NOW, KETS_1Y
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()

# 1. 감축 비용 곡선 (기본 조건: 배출계수 0.4173, 태양광 PPA 180원, 전기로 175만 t, 수소환원 100만 t)
c = curve()
print("[감축 비용 곡선] 싼 순서. 범위 = PPA 130~190원 x 배출계수 0.245(2030 낙관)~0.4524(한계 기준)")
for k, r in c.iterrows():
    print(f"  {r['name']}: 감축 1t당 {r.krw_per_tco2:,.0f}원 (범위 {r.lo:,.0f}~{r.hi:,.0f}), 연 {r.abate_mt:.2f}백만 tCO2, 전력비용 {r.cost_eok:,.0f}억 원/년, 재생에너지 {r.re_twh:.2f} TWh ({r.way})")
print(f"[재생에너지 필요량] 곡선 전체 {c.re_twh.sum():.2f} TWh/년 (2024 구매 전력 3.05 TWh의 {c.re_twh.sum() / 3.05:.1f}배)")

# 2. 탄소 가격별로 전력비용이 덮이는 감축량
for name, p in (("K-ETS 1년 최고", KETS_1Y["max"]), ("K-ETS 시세", KAU_NOW), ("EU ETS 시세", EUA_KRW)):
    print(f"[탄소 가격 {p:,}원 ({name})] 전력비용이 탄소 비용 절감으로 덮이는 감축 {pays_at(p, c):.2f}백만 t / 전체 {c.abate_mt.sum():.2f}백만 t")
cheap = curve(ppa_krw_kwh=RANGES["ppa_krw_kwh"][0])
print(f"[PPA {RANGES['ppa_krw_kwh'][0]}원이면] 직접PPA 전환 감축 1t당 {cheap.loc['ppa', 'krw_per_tco2']:,.0f}원: 한전보다 싸서 탄소를 줄이면서 전력비용도 준다")
low = curve(grid_factor=GF_2030_LOW)
print(f"[전력망이 깨끗해지면(계수 {GF_2030_LOW})] 직접PPA 전환 1t당 {low.loc['ppa', 'krw_per_tco2']:,.0f}원, 전기로 {low.loc['eaf', 'krw_per_tco2']:,.0f}원: 같은 할증으로 줄일 탄소가 적어 PPA 쪽이 비싸진다")

# 3. 수소환원을 한다면 어떤 전력으로 (쌓지 않는 비교)
h = options().loc[["h2_grid", "h2_green", "h2_full"]].join(option_ranges())
print("\n[수소환원 전력 조달별] 쇳물 1t당 전력비용은 전력망이 가장 싸지만, 감축 1t당으로는 가장 비싸다")
for k, r in h.iterrows():
    print(f"  {r['name']}: 감축 1t당 {r.krw_per_tco2:,.0f}원 (범위 {r.lo:,.0f}~{r.hi:,.0f}), 쇳물 1t당 전력비용 {r.krw_per_t_steel:,.0f}원, 순 저감 {r.abate_per_t_steel:.2f} t/t")
print(f"[비교] 전력망 수소의 감축 1t당 비용은 그린 수소의 {h.loc['h2_grid', 'krw_per_tco2'] / h.loc['h2_green', 'krw_per_tco2']:.1f}배")
print("[가정]", *ASSUMPTIONS, sep="\n  ")

# 4. 그림
fig, ax = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw=dict(width_ratios=[1.6, 1]))
color = {"전부": "#5b7fa6", "추가": "#2e7d32"}
short = {"eaf": "전기로 전환", "ppa": "한전 전력 → 직접PPA", "h2": "수소환원\n(전력 100% PPA)"}
a = ax[0]
for k, r in c.iterrows():
    y = r.krw_per_tco2 / 1e4
    a.bar(r.x0, y, width=r.abate_mt, align="edge", color=color[r.way], edgecolor="white")
    mid = (r.x0 + r.x1) / 2
    a.errorbar(mid, y, yerr=[[y - r.lo / 1e4], [r.hi / 1e4 - y]], color="black", capsize=4, lw=1)
    a.text(mid, max(y, r.hi / 1e4) + 1.5, f"{short[k]}\n{y:.1f}만 원/t", ha="center", va="bottom", fontsize=9)
for p, ls, label in ((KAU_NOW, "--", f"K-ETS 시세 {KAU_NOW / 1e4:.2f}만"), (EUA_KRW, ":", f"EU ETS 시세 {EUA_KRW / 1e4:.1f}만")):
    a.axhline(p / 1e4, ls=ls, c="gray"); a.text(0.05, p / 1e4 + 0.8, label, color="dimgray", ha="left", fontsize=9, bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
a.axhline(0, c="black", lw=0.6)
a.set(title="감축 비용 곡선: 싼 조치부터 (막대 폭 = 연 감축량)", xlabel="누적 감축량 (백만 tCO2/년)", ylabel="감축 1t당 전력비용 (만 원/tCO2)", ylim=(-10, 55), xlim=(0, c.x1.iloc[-1] * 1.02))
a.legend(handles=[Patch(color=color["전부"], label="전부: 전력비용 전체 / 순 저감 (원료비 절감 미반영, 상한)"), Patch(color=color["추가"], label="추가: PPA 할증 / 줄어든 Scope 2")], loc="upper left", fontsize=9)
b = ax[1]
names = ["전력망 전기", "수전해만 PPA\n(그린 수소)", "전력 100% PPA"]
ys = h.krw_per_tco2 / 1e4
b.bar(names, ys, color=["#9e9e9e", "#66bb6a", "#2e7d32"], yerr=[ys - h.lo / 1e4, h.hi / 1e4 - ys], capsize=4)
for i, (k, r) in enumerate(h.iterrows()):
    b.text(i, r.hi / 1e4 + 3, f"{r.krw_per_tco2 / 1e4:.1f}만 원/tCO2\n쇳물 1t당 {r.krw_per_t_steel / 1e4:.1f}만 원\n순 저감 {r.abate_per_t_steel:.2f} t/t", ha="center", va="bottom", fontsize=9)
b.axhline(EUA_KRW / 1e4, ls=":", c="gray"); b.text(-0.45, EUA_KRW / 1e4 + 2, f"EU ETS {EUA_KRW / 1e4:.1f}만", color="dimgray", ha="left", fontsize=9)
b.set(title="수소환원을 한다면: 전력 조달별 감축 1t당 비용", ylabel="감축 1t당 전력비용 (만 원/tCO2)", ylim=(0, h.hi.max() / 1e4 * 1.35))
fig.text(0.5, -0.02, "기본: 배출계수 0.4173, 직접PPA 180원/kWh, 전기로 175만 t, 수소환원 100만 t. 범위 막대: PPA 130~190원 x 배출계수 0.245~0.4524. 설비 투자비·고로 원료비 절감 미반영", ha="center", fontsize=9, color="dimgray")
fig.savefig(ROOT / "figures/19_감축비용곡선.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/19_감축비용곡선.png")
