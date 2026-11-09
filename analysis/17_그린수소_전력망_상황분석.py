"""그린 수소 vs 전력망 전기 상황 분석 (처음부터 끝까지 실행): 무엇이 판단을 흔드는가, 여러 조건이 함께 불확실하면 어떤가, 탄소 가격 x PPA 단가 조합, 시점별(전력망이 깨끗해지는 경로) 갈림길.
계산은 src/h2_analysis.py(-> src/hydrogen.py h2_supply -> simulate). 이 스크립트는 부르고 그림만 그린다.
실행: 프로젝트 루트에서 python3 analysis/17_그린수소_전력망_상황분석.py  (그림은 figures/17_그린수소_전력망_상황분석.png)
주의: 수전해 설비비 제외(두 방법이 같은 설비), 범위·분포는 근거 범위 안의 가정, 몬테카를로 비율은 현실의 확률이 아니다. 시점별 배출계수는 예측이 아니라 시나리오(src/emission_factor.scenario).
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import h2_analysis as A
from src.hydrogen import EUA_KRW, KAU_NOW, KETS_1Y, h2_supply
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()
pd.set_option("display.width", 200, "display.max_columns", 20)

# 1. 대표 상황 정리
sit = A.situations()
print("[대표 상황] (그린 - 전력망 1t당 비용, 음수면 그린이 쌈)")
print(sit.round({"그린_빼기_전력망_원per_t": 0, "손익분기_탄소가격": 0, "그린_순저감": 2, "전력망_순저감": 2}).to_string())

# 2. 무엇이 판단을 흔드나 (토네이도, 기준: K-ETS 29,500원, PPA 180원, 배출계수 0.4173)
tor = A.tornado()
print("\n[토네이도] 변수 하나씩 범위 양 끝으로 바꿀 때 1t당 비용 차(그린 - 전력망), flip = 그 변수 하나로 추천이 바뀜")
print(tor.round(0).to_string())
th = h2_supply(1.0)["thresholds"]
print(f"  -> 추천을 뒤집는 것: PPA 단가({th['ppa_breakeven']:.0f}원/kWh 이하면 그린)와 한전 요금 인상({th['price_change_breakeven'] * 100:.1f}% 이상이면 그린). "
      f"K-ETS 범위 안의 탄소 가격·배출계수 기준(평균/한계)·요금제·부가요금은 뒤집지 못함")
a, b = A.gap_scales_with_h2(); print(f"[수소 원단위] 40 kg/t {a:,.0f}원, 60 kg/t {b:,.0f}원 -> 비용 차의 크기만 바뀌고 부호(추천)는 같음")

# 3. 여러 조건이 함께 불확실할 때 (몬테카를로 2,000회)
mc = {w: A.monte_carlo(w, n=2000) for w in ("kets", "eu")}
for w, X in mc.items():
    print(f"[몬테카를로 {'국내(K-ETS 최근 1년)' if w == 'kets' else 'EU 수준 탄소 가격'}] 그린이 싼 비율 {(X.pick == 'green').mean() * 100:.1f}%, "
          f"1t당 비용 차 중앙값 {X.gap.median():,.0f}원 (5~95% {X.gap.quantile(0.05):,.0f} ~ {X.gap.quantile(0.95):,.0f}원)")
k = mc["kets"]
print("  국내에서 그린이 이긴 표본의 조건(중앙값):", k[k.pick == "green"][["ppa_krw_kwh", "price_change"]].median().round(3).to_dict(),
      "| 전력망이 이긴 표본:", k[k.pick == "grid"][["ppa_krw_kwh", "price_change"]].median().round(3).to_dict())

# 4. 탄소 가격 x PPA 단가 추천 지도 (배출계수 0.4173)
ets_axis, ppa_axis = (KETS_1Y["min"], KETS_1Y["mean"], KAU_NOW, 45_000, 60_000, 90_000, EUA_KRW), list(range(130, 191, 10))
vm = A.verdict_map("ppa_krw_kwh", ppa_axis, "ets_price", ets_axis)
print("\n[탄소 가격(행) x PPA 단가(열)]"); print(vm.to_string())

# 5. 시점별 갈림길 (전력배출계수 시나리오)
tl = A.timeline()
print("\n[시점별] K-ETS 29,500원·PPA 180원 기준"); print(tl.round({"손익분기_탄소가격": 0, "손익분기_PPA": 1, "전력망_1t당_순저감": 2}).to_string(index=False))
tle = A.timeline(ets_price=EUA_KRW)
print("[시점별] EU 수준 탄소 가격이면 추천:", tle.set_index(["연도", "계수_시나리오"]).추천.unstack().to_dict("index"))
print("  -> 전력망이 빨리 깨끗해질수록 그린이 정당화되는 탄소 가격이 오른다(2030 낙관 약 14.9만 원). PPA 갈림길은 151~157원으로 거의 그대로")

# 6. 그림
fig, ax = plt.subplots(2, 2, figsize=(15, 10))
t = tor.iloc[::-1]
for i, (name, r) in enumerate(t.iterrows()):
    ax[0, 0].barh(i, r.gap_높음 - r.gap_낮음, left=r.gap_낮음, color="#c62828" if r.flip else "#9e9e9e")
    ax[0, 0].text(max(r.gap_낮음, r.gap_높음) + 3000, i, f"{r.낮은값} ~ {r.높은값}", va="center", fontsize=8)
NAME = {"ppa_krw_kwh": "PPA 단가 (원/kWh)", "price_change": "한전 요금 변동률", "adder": "기후환경·연료비조정 (원/kWh)", "ets_price": "탄소 가격 (K-ETS 1년)", "plan": "요금제 (B/C)", "grid_factor": "배출계수 (평균~한계)"}
ax[0, 0].axvline(0, c="black"); ax[0, 0].axvline(A.gap(), ls="--", c="gray")
ax[0, 0].set(yticks=range(len(t)), yticklabels=[NAME[n] for n in t.index], title="무엇이 판단을 흔드나 (빨강 = 혼자서 추천을 뒤집음)", xlabel="쇳물 1t당 그린 - 전력망 (원, 음수면 그린이 쌈)")
for w, c, nm in (("kets", "#9e9e9e", "국내(K-ETS)"), ("eu", "#2e7d32", "EU 수준")):
    ax[0, 1].hist(mc[w].gap / 1e4, bins=50, alpha=0.7, color=c, label=f"{nm}: 그린이 싼 비율 {(mc[w].pick == 'green').mean() * 100:.0f}%")
ax[0, 1].axvline(0, c="black"); ax[0, 1].set(title="여러 조건이 함께 불확실할 때 (2,000회)", xlabel="쇳물 1t당 그린 - 전력망 (만 원)", ylabel="표본 수"); ax[0, 1].legend()
z = vm.replace({"green": 0, "grid": 1, "bf": 2}).to_numpy(dtype=float)
ax[1, 0].imshow(z, cmap=ListedColormap(["#2e7d32", "#9e9e9e", "#c62828"]), vmin=0, vmax=2, aspect="auto"); ax[1, 0].grid(False)
ax[1, 0].set(xticks=range(len(ppa_axis)), xticklabels=ppa_axis, yticks=range(len(ets_axis)), yticklabels=[f"{e / 1e4:.1f}만" for e in ets_axis],
             title="탄소 가격 x PPA 단가 (초록 = 그린, 회색 = 전력망)", xlabel="직접PPA 계약 단가 (원/kWh)", ylabel="탄소 가격 (원/tCO2)")
for i in range(z.shape[0]):
    for j in range(z.shape[1]):
        ax[1, 0].text(j, i, {0: "그린", 1: "전력망", 2: "그린만"}[int(z[i, j])], ha="center", va="center", color="white", fontsize=8)
for kind, c in zip(tl.계수_시나리오.unique(), ("#455a64", "#1565c0", "#2e7d32")):
    s = tl[tl.계수_시나리오 == kind]; ax[1, 1].plot(s.연도, s.손익분기_탄소가격 / 1e4, marker="o", c=c, label=f"전력망 계수: {kind}")
ax[1, 1].axhline(KAU_NOW / 1e4, ls="--", c="gray"); ax[1, 1].text(2026, KAU_NOW / 1e4 + 0.6, "K-ETS 지금 2.95만", color="gray")
ax[1, 1].axhline(EUA_KRW / 1e4, ls=":", c="gray"); ax[1, 1].text(2026, EUA_KRW / 1e4 + 0.6, "EU ETS 13.2만", color="gray")
ax[1, 1].set(title="그린이 유리해지는 탄소 가격 (PPA 180원, 시나리오)", xlabel="연도", ylabel="만 원/tCO2", ylim=(0, 20)); ax[1, 1].legend()
fig.tight_layout()
fig.savefig(ROOT / "figures/17_그린수소_전력망_상황분석.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/17_그린수소_전력망_상황분석.png")
