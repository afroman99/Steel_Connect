"""그린 수소 vs 전력망 전기 (처음부터 끝까지 실행): 수소환원의 수소를 무엇으로 만들 때 탄소·비용이 나은지, 상황(전력배출계수·탄소 가격·PPA 단가·목표)별로 나눠 본다.
계산은 모두 src/hydrogen.py의 h2_supply(-> simulate)가 한다. 이 스크립트는 조건을 바꿔 부르고 그림만 그린다.
실행: 프로젝트 루트에서 python3 analysis/15_그린수소_전력망_추천.py  (그림은 figures/15_그린수소_전력망_추천.png)
주의: 연간 전력량 기준, 수전해 설비 투자비 제외(그린·전력망이 같은 설비라 상쇄), 탄소 가격·PPA 단가는 가정. 예측이 아니라 조건부 시나리오.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.hydrogen import EUA_KRW, KAU_NOW, h2_supply
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()
MT = 1.0  # 수소환원 연 100만 t (비교 기준 규모. 1t당 값은 규모와 무관)

# 1. 기본 조건(K-ETS 시세, 태양광 PPA 180원, 배출계수 0.4173)
r = h2_supply(MT)
o, th = {x["key"]: x for x in r["options"]}, r["thresholds"]
print(f"[기본 추천] {r['verdict']['pick']} - {r['verdict']['reason']}")
for x in r["options"]:
    print(f"  {x['name']}: 쇳물 1t당 {x['krw_per_t']:,.0f}원 (전력 {x['power_krw_per_t']:,.0f} + 탄소 {x['krw_per_t'] - x['power_krw_per_t']:,.0f}), 순 저감 {x['abate_per_t']:.2f} tCO2/t")
print(f"[전력 단가] 한전 24시간 {th['unit_grid_krw_kwh']:.1f}원/kWh, 직접PPA(부대비용 포함) {th['unit_ppa_krw_kwh']:.1f}원, 경부하만 {th['unit_offpeak_krw_kwh']:.1f}원 (경부하 = 1년의 {th['offpeak_share'] * 100:.1f}%)")
print(f"[감축 비용] 그린으로 바꿀 때 추가로 줄이는 1t당 비용 = 손익분기 탄소 가격 {th['ets_breakeven']:,.0f}원/tCO2 (K-ETS {KAU_NOW:,}원, EU ETS {EUA_KRW:,}원)")
print(f"[고로 손익분기] 전력배출계수 {th['gf_breakeven_bf']:.3f} 이상이면 전력망 수소는 고로보다 배출 증가 (Bhaskar 2020 0.456은 고로 1.688 기준)")

# 2. 상황별 추천: 탄소 가격 x 배출계수 (PPA 180원 vs 150원 = 정부 태양광 목표 발전단가)
print("\n[상황별 추천] 칸: G=그린, E=전력망, X=전력망 수소가 고로보다 나쁨(그린만 의미)")
maps = {}
for ppa in (180, 150):
    m = h2_supply(MT, ppa_krw_kwh=ppa)["map"]; maps[ppa] = m
    print(f"  PPA {ppa}원/kWh  계수 ->", " ".join(f"{g:.2f}" for g in m["gf"]))
    for p, row in zip(m["ets"], m["cells"]):
        print(f"   탄소 {p:>7,}원  ", "    ".join({"green": "G", "grid": "E", "bf": "X"}[c] for c in row))

# 3. 갈림길 곡선: 배출계수별 손익분기 탄소 가격 (PPA 단가별)
gfs = np.round(np.arange(0.20, 0.5301, 0.01), 4)
curves = {ppa: [h2_supply(MT, ppa_krw_kwh=ppa, grid_factor=float(g))["thresholds"]["ets_breakeven"] for g in gfs] for ppa in (130, 150, 180, 190)}
for ppa, c in curves.items():
    print(f"[손익분기 탄소 가격] PPA {ppa}원: 계수 0.30에서 {c[10]:,.0f}원, 0.4173 근처(0.42)에서 {c[22]:,.0f}원/tCO2")

# 4. 목표·확보량이 바꾸는 판단
for tgt in (0.4e6, 1.0e6, 1.6e6):
    v = h2_supply(MT, target_abate_t=tgt)["verdict"]
    print(f"[목표 {tgt / 1e4:.0f}만 t/년] 추천 {v['pick']} ({v['rule']}) - {v['reason']}")
v = h2_supply(MT, ets_price=EUA_KRW, green_supply_twh=1.0)
print(f"[확보량 1 TWh, EU 탄소 가격] 추천 {v['verdict']['pick']} / {' '.join(v['verdict']['notes'])}")

# 5. 그림
fig, ax = plt.subplots(1, 3, figsize=(18, 5.2))
cmap = ListedColormap(["#2e7d32", "#9e9e9e", "#c62828"])
for a, ppa in zip(ax[:2], (180, 150)):
    m = maps[ppa]
    z = np.array([[{"green": 0, "grid": 1, "bf": 2}[c] for c in row] for row in m["cells"]])
    a.imshow(z, cmap=cmap, vmin=0, vmax=2, aspect="auto", origin="lower")
    a.set_xticks(range(len(m["gf"])), [f"{g:g}" for g in m["gf"]]); a.set_yticks(range(len(m["ets"])), [f"{p / 1e4:.1f}만" for p in m["ets"]])
    a.set(title=f"상황별 추천 (직접PPA {ppa}원/kWh)", xlabel="전력배출계수 (tCO2/MWh)", ylabel="탄소 가격 (원/tCO2)")
    for i, row in enumerate(m["cells"]):
        for j, c in enumerate(row):
            a.text(j, i, {"green": "그린", "grid": "전력망", "bf": "그린만"}[c], ha="center", va="center", color="white", fontsize=8)
for ppa, c in curves.items():
    ax[2].plot(gfs, np.array(c) / 1e4, label=f"PPA {ppa}원")
ax[2].axhline(KAU_NOW / 1e4, ls="--", c="gray"); ax[2].text(0.205, KAU_NOW / 1e4 + 1, "K-ETS 시세 2.95만", color="gray")
ax[2].axhline(EUA_KRW / 1e4, ls=":", c="gray"); ax[2].text(0.205, EUA_KRW / 1e4 + 1, "EU ETS 13.2만", color="gray")
ax[2].axvline(th["gf_breakeven_bf"], c="#c62828", lw=1); ax[2].text(th["gf_breakeven_bf"] - 0.002, 5, "고로 손익분기", color="#c62828", ha="right")
ax[2].set(title="이 선보다 탄소 가격이 높으면 그린 수소가 싸다", xlabel="전력배출계수 (tCO2/MWh)", ylabel="손익분기 탄소 가격 (만 원/tCO2)", ylim=(0, 40)); ax[2].legend()
fig.savefig(ROOT / "figures/15_그린수소_전력망_추천.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/15_그린수소_전력망_추천.png")
