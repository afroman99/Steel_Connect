"""외부 공개 데이터 분석 (처음부터 끝까지 실행): 2025 시간대별 전력 믹스로 본 배출계수, 태양광·풍력 시간 일치율, 탄소 가격 1년 범위, 산업용 판매단가.
계산은 src/ext_data.py가 하고, 결과는 src/emission_factor.py(TOU_GF_RATIO 등)·src/hydrogen.py(HOURLY_MATCH, KETS_1Y, EUETS_1Y)에 상수로 들어가 있다. 이 스크립트는 그 상수를 다시 계산해 보여 준다.
원본(data/ 에 둔다. icap_systems.json만 약관상 git 제외) 내려받기:
  - 공공데이터포털 원본은 CP949라 받은 뒤 UTF-8(BOM)로 바꿔 저장한다(에디터·git에서 한글이 깨지지 않게)
  - 공공데이터포털(로그인 불필요) 한국전력거래소_연료원별 시간대별 설비용량 및 전력거래량(15127395) -> kpx_fuel_hourly_2025.csv
  - 한국전력거래소_신재생 발전량 및 설비용량(15069337) -> kpx_renewable_hourly_capacity_2025.csv  (참고: 지역별 시간별 태양광 및 풍력 발전량(15065269))
  - ICAP Allowance Price Explorer API https://allowancepriceexplorer.icapcarbonaction.com/api/systems -> icap_systems.json
  - EPSIS 연도별 판매단가 화면의 표 -> epsis_sales_price_by_use.json
실행: 프로젝트 루트에서 python3 analysis/16_외부데이터_시간대배출_재생.py  (그림은 figures/16_외부데이터_시간대배출_재생.png)
주의: 거래소 자료는 시장 거래 발전기만(지붕 태양광·한전 PPA 제외). 배출은 평균 믹스 기준이며 한계 배출이 아니다. 예측이 아니라 2025년 실적으로 본 시나리오 근거.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import ext_data as X
from src.emission_factor import TOU_GF_RATIO
from src.hydrogen import EUETS_1Y, HOURLY_MATCH, KETS_1Y
from src.plot_setup import setup_korean_font

# fmt: off
if not X.available():
    sys.exit(f"원본 데이터가 없습니다: {X.DATA} 에 {list(X.FILES.values())}. 맨 위 설명대로 내려받으세요.")
setup_korean_font()

# 1. 시간대별 배출계수 (2025 시장 발전기, 연료원 배출계수)
g = X.hourly_grid()
print(f"[믹스 집약도] 2025 시장 발전기 연평균 {(g.intensity * g.mwh).sum() / g.mwh.sum():.4f} tCO2/MWh (발전량 가중, 직접배출) vs 공식 2023 소비단 0.4173 (기준이 달라 크기는 공식값을 쓰고 비율만 씀)")
tou = X.tou_ratio(g)
print("[요금시간대별 배출 비율] (24시간 일정 부하 = 1)", {k: round(v, 4) for k, v in tou.items()}, "| 상수 TOU_GF_RATIO", TOU_GF_RATIO)
hour = g.groupby("h").ratio.mean()
print(f"[시각별] 가장 깨끗한 시각 {hour.idxmin()}시 {hour.min():.3f}, 가장 높은 시각 {hour.idxmax()}시 {hour.max():.3f}. 계절: {g.groupby('sea').ratio.mean().round(3).to_dict()}")
print("  -> 경부하(밤·휴일)에 수전해를 몰아도 탄소는 줄지 않는다. 낮(10~15시)이 태양광 덕분에 가장 깨끗하다(2026 요금 개편으로 3~10월 낮이 중간부하로 싸진 것과 같은 방향)")

# 2. 태양광·풍력 시간 일치율
rp = X.re_profiles()
mt = X.match_table(rp, g)
for k, v in mt.items():
    c = HOURLY_MATCH[k]
    print(f"[시간 일치] {c['name']}: 이용률 {'' if v['cf'] is None else f'{v['cf'] * 100:.1f}%, '}같은 시간에 채우는 비율 {v['share'] * 100:.1f}% (상수 {c['share'] * 100:.1f}%), "
          f"남는 재생 {v['surplus'] * 100:.1f}%, 모자란 시간 배출계수 {v['backfill_ratio']:.3f}배, 100% 맞추는 저장 {v['storage_h']:.0f}시간분({v['storage_h'] / 24:.0f}일)")
ks = np.round(np.arange(1.0, 3.01, 0.25), 2)
over = {k: [X.hourly_match((rp.solar / rp.solar.mean() if k == "solar" else rp.wind / rp.wind.mean() if k == "wind" else 0.5 * rp.solar / rp.solar.mean() + 0.5 * rp.wind / rp.wind.mean()),
                           g.ratio, kk)["share"] for kk in ks] for k in ("solar", "wind", "mix")}
print("[과대 설치] 연간 재생 발전량 = k x 부하일 때 시간 일치율:", {k: {float(kk): round(s, 3) for kk, s in zip(ks, v) if kk in (1.0, 1.5, 2.0, 3.0)} for k, v in over.items()})

# 3. 탄소 가격 1년 범위 (ICAP)
e = X.ets_stats()
print(f"[K-ETS] 2025-11-10~{e['kets']['last_date']}: 최저 {e['kets']['min']:,.0f} 평균 {e['kets']['mean']:,.0f} 최고 {e['kets']['max']:,.0f}원/t (상수 {KETS_1Y}), 2015~ 최저 {e['kets_all']['min']:,.0f} 최고 {e['kets_all']['max']:,.0f}원")
print(f"[EU ETS] 같은 기간 원화 환산: 최저 {e['euets']['min']:,.0f} 평균 {e['euets']['mean']:,.0f} 최고 {e['euets']['max']:,.0f}원/t (상수 {EUETS_1Y})")

# 4. 산업용 판매단가 (EPSIS, 한국전력통계)
sp = X.sales_price()
print("[산업용 판매단가]", {y: sp[y] for y in range(2020, max(sp) + 1)}, "원/kWh -> 시뮬레이터 S1 177.1원(기본·부가요금·기금 포함, VAT 제외)과 대조")

# 5. 그림
import json, pandas as pd
d = json.loads((X.DATA / X.FILES["icap"]).read_text(encoding="utf-8")); s = {x["id"]: x for x in d}
k = pd.Series({pd.Timestamp(t): v[2] for t, v in s[8]["values"]["secondary"].items()}).sort_index()
eu = pd.Series({pd.Timestamp(t): v[1] for t, v in s[34]["values"]["secondary"].items()}).sort_index()
fx = pd.Series({pd.Timestamp(t): v[2] / v[1] for t, v in s[8]["values"]["secondary"].items() if v[1]}).sort_index().reindex(eu.index, method="ffill")
fig, ax = plt.subplots(1, 3, figsize=(18, 4.8))
for sea, c in (("여름", "#c62828"), ("봄가을", "#2e7d32"), ("겨울", "#1565c0")):
    ax[0].plot(range(24), g[g.sea == sea].groupby("h").ratio.mean(), marker="o", ms=3, c=c, label=sea)
ax[0].plot(range(24), hour, c="black", lw=2, label="1년 평균"); ax[0].axhline(1, ls="--", c="gray")
ax[0].set(title="시각별 전력 배출계수 (24시간 일정 부하 = 1, 2025)", xlabel="시각", ylabel="배출계수 비율"); ax[0].legend()
day = rp.groupby("h")[["solar", "wind"]].mean()
ax[1].plot(day.index, day.solar / rp.solar.mean(), label="태양광"); ax[1].plot(day.index, day.wind / rp.wind.mean(), label="풍력"); ax[1].axhline(1, ls="--", c="gray")
ax[1].text(0.5, 1.1, "수전해 부하(24시간 일정)", color="gray")
ax[1].set(title="재생에너지 시각별 출력 (연간량 = 부하, 2025 평균)", xlabel="시각", ylabel="부하 대비 배수"); ax[1].legend()
ax[2].plot(k[k.index >= "2021"].index, k[k.index >= "2021"] / 1e4, label="K-ETS (KAU)"); ax[2].plot(eu[eu.index >= "2021"].index, (eu * fx)[eu.index >= "2021"] / 1e4, label="EU ETS (원화 환산)")
ax[2].set(title="탄소 가격 (ICAP)", ylabel="만 원/tCO2"); ax[2].legend()
fig.savefig(ROOT / "figures/16_외부데이터_시간대배출_재생.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/16_외부데이터_시간대배출_재생.png")
