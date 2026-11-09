"""EDA 그림 (처음부터 끝까지 실행): 노트북(analysis/00_EDA.ipynb, git 제외)에서 본 것을 그림 파일로 남긴다. 계산은 src/eda.py·src/ext_data.py.
  figures/18_EDA_UCI.png        UCI 부하 분포, 월 x 시각 부하, 요일유형별 부하, UCI 시간대 라벨 vs 2026 공식 시간대
  figures/18_EDA_Factbook.png   포스코 에너지 구성·배출·파생 지표 추이(2022~2024)
  figures/18_한계배출_시간일치.png  평균 vs 한계 배출계수(시각별), 수요 변화를 맡는 연료, 한계 기준이 판단에 주는 영향, 재생에너지 과대 설치와 시간 일치율
실행: 프로젝트 루트에서 python3 analysis/18_EDA_그림.py  (외부 데이터 data/kpx_* 등이 없으면 세 번째 그림은 건너뛴다)
주의: UCI는 소규모 사업장(2018)이라 포스코를 대표하지 않는다. 거래소 자료는 시장 발전기만이며 한계 배출은 평균 믹스가 아닌 회귀 추정이다.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import eda as E
from src import ext_data as X
from src.load_profile import hourly_profile, load_uci
from src.plot_setup import setup_korean_font

# fmt: off
setup_korean_font()
BAND_CMAP = ListedColormap(["#90caf9", "#ffcc80", "#ef5350"])  # 경·중·최
CODE = {"경": 0, "중": 1, "최": 2}

# 1. UCI
raw, d = E.read_csv(E.UCI), load_uci(E.UCI)
fig, ax = plt.subplots(2, 2, figsize=(15, 9))
ax[0, 0].hist(np.log10(d.kw.clip(lower=1)), bins=80); ax[0, 0].set(title="15분 평균 전력 분포 (log10 kW): 쉬는 시간과 가동 시간이 갈림", xlabel="log10(kW)", ylabel="구간 수")
E.heatmap(ax[0, 1], E.month_hour(d), "월 x 시각 평균 부하", "평균 kW"); ax[0, 1].set(xlabel="시각", ylabel="월")
hourly_profile(d).plot(ax=ax[1, 0], marker="o", ms=3); ax[1, 0].set(title="요일유형별 시각별 평균 부하", xlabel="시각", ylabel="kW"); ax[1, 0].legend(title="요일유형")
ls = E.label_strings(d)
rows = [(f"{s} UCI", ls.loc[s, "UCI 라벨"]) for s in ls.index] + [(f"{s} 2026", ls.loc[s, "2026 공식"]) for s in ls.index]
rows = sorted(rows, key=lambda r: (list(ls.index).index(r[0].split()[0]), r[0].endswith("2026")))
ax[1, 1].imshow([[CODE[c] for c in r[1]] for r in rows], cmap=BAND_CMAP, vmin=0, vmax=2, aspect="auto"); ax[1, 1].grid(False)
for i, (_, s) in enumerate(rows):
    for j, ch in enumerate(s):
        ax[1, 1].text(j, i, ch, ha="center", va="center", fontsize=7)
agree = E.label_agreement(d)
ax[1, 1].set(yticks=range(len(rows)), yticklabels=[r[0] for r in rows], xticks=range(0, 24, 2), xlabel="시각 (평일)",
             title=f"UCI 라벨(2018 옛 시간대) vs 2026 공식: 일치 {agree['B'] * 100:.0f}%")
fig.tight_layout(); fig.savefig(ROOT / "figures/18_EDA_UCI.png", dpi=150, bbox_inches="tight"); plt.close(fig)
print(f"[UCI] 결측 {int(raw.isna().sum().sum())}, CO2 열 계수 {E.implied_co2_factor(raw):.4f}, 공식 시간대 일치 {agree} -> figures/18_EDA_UCI.png")

# 2. Factbook
fb = E.factbook(); v = fb.set_index("항목")[["2022", "2023", "2024"]]; m = E.factbook_metrics(fb)
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
(v.loc[["부생가스", "천연가스", "전기"]] / 1e6).T.plot.bar(ax=ax[0], rot=0); ax[0].set(title="에너지 사용 (백만 GJ): 부생가스 감소, 천연가스 증가", ylabel="백만 GJ", ylim=(0, 380))
ax[0].legend(title="", ncol=3, loc="upper center")
(v.loc[["직접 배출(Scope 1)", "간접 배출(Scope 2)"]] / 1e6).T.plot(ax=ax[1], marker="o"); ax[1].set(title="배출 (백만 tCO2e)", ylabel="백만 tCO2e")
ax2 = ax[2].twinx()
ax[2].plot(m.columns, m.loc["부생가스 / 직접에너지 %"], marker="o", c="#6d4c41", label="부생가스 / 직접에너지 (%)")
ax2.plot(m.columns, m.loc["Scope 2 / 구매 전력 t/MWh"], marker="s", c="#1565c0", label="Scope 2 / 구매 전력 (t/MWh)")
ax[2].set(title="파생 지표 (2022은 포항·광양 한정)", ylabel="%"); ax2.set_ylabel("t/MWh"); ax2.axhline(0.4541, ls=":", c="#1565c0"); ax2.text(0.05, 0.4542, "공식 2020~22 평균 0.4541", color="#1565c0", fontsize=8); ax2.grid(False)
h1, l1 = ax[2].get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax[2].legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right")
fig.tight_layout(); fig.savefig(ROOT / "figures/18_EDA_Factbook.png", dpi=150, bbox_inches="tight"); plt.close(fig)
print("[Factbook]", m.round(3).to_dict(), "-> figures/18_EDA_Factbook.png")

# 3. 한계 배출과 시간 일치 (외부 데이터)
if not X.available():
    sys.exit("외부 데이터가 없어 세 번째 그림은 건너뜀 (analysis/16 맨 위 설명대로 받기)")
g, rp = X.hourly_grid(), X.re_profiles()
hh, mb, ms = X.marginal_table("h"), X.marginal_table("band"), X.marginal_scenario()
fig, ax = plt.subplots(2, 2, figsize=(15, 9))
ax[0, 0].plot(hh.index, hh.한계_비율, marker="o", label="한계 (24시간 한계 = 1)"); ax[0, 0].plot(range(24), g.groupby("h").ratio.mean(), marker="s", label="평균 (24시간 평균 = 1)")
ax[0, 0].axhline(1, ls="--", c="gray"); ax[0, 0].set(title="시각별 배출계수: 평균 vs 한계 (2025)", xlabel="시각", ylabel="비율"); ax[0, 0].legend()
(mb[["LNG", "석탄", "양수"]] * 100).plot.bar(ax=ax[0, 1], stacked=True, rot=0, color=["#ffa726", "#5d4037", "#42a5f5"])
for i, (b, r) in enumerate(mb.iterrows()):
    ax[0, 1].text(i, 102, f"한계 {r.한계:.3f}", ha="center", fontsize=9)
ax[0, 1].set(title="요금시간대별 수요 변화를 맡는 연료 (%)", xlabel="요금시간대", ylabel="%", ylim=(0, 115))
x = np.arange(len(ms))
b1 = ax[1, 0].bar(x - 0.18, ms.전력망_1t당_순저감, width=0.32, color="#1565c0", label="전력망 수소 1t당 순 저감 (tCO2/t, 왼쪽 축)")
axb = ax[1, 0].twinx(); b2 = axb.bar(x + 0.18, ms.손익분기_탄소가격 / 1e4, width=0.32, color="#2e7d32", label="그린이 유리해지는 탄소 가격 (만 원/t, 오른쪽 축)")
ax[1, 0].bar_label(b1, fmt="%.2f"); axb.bar_label(b2, fmt="%.1f만")
ax[1, 0].set(xticks=x, xticklabels=[f"{i}\n(계수 {r.배출계수})" for i, r in ms.iterrows()], ylabel="tCO2/t", ylim=(0, 0.6)); axb.set(ylabel="만 원/tCO2", ylim=(0, 12)); axb.grid(False)
ax[1, 0].set_title(f"평균 vs 한계 기준: 판단에 주는 영향 (추천은 둘 다 {', '.join(ms.추천.unique())})")
ax[1, 0].legend([b1, b2], [b1.get_label(), b2.get_label()], fontsize=8, loc="upper right")
ks = np.round(np.arange(1.0, 3.01, 0.1), 2)
profiles = {"태양광": rp.solar / rp.solar.mean(), "풍력": rp.wind / rp.wind.mean(), "반반": 0.5 * rp.solar / rp.solar.mean() + 0.5 * rp.wind / rp.wind.mean()}
for (name, p), c in zip(profiles.items(), ("#fbc02d", "#1e88e5", "#2e7d32")):
    ax[1, 1].plot(ks, [X.hourly_match(p, g.ratio, k)["share"] * 100 for k in ks], marker="o", ms=3, c=c, label=name)
ax[1, 1].set(title="재생에너지를 연간 부하의 k배 계약할 때 같은 시간에 채우는 비율", xlabel="k (연간 재생 발전량 / 연간 수전해 부하)", ylabel="시간 일치율 (%)", ylim=(0, 100)); ax[1, 1].legend()
fig.tight_layout(); fig.savefig(ROOT / "figures/18_한계배출_시간일치.png", dpi=150, bbox_inches="tight"); plt.close(fig)
print("[한계 배출] 요금시간대별", mb.한계.round(3).to_dict(), "| 판단:", ms.추천.to_dict(), "-> figures/18_한계배출_시간일치.png")
