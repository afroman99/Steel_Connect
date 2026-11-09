"""자체발전 감소(selfgen_cut) 스윕과 손익분기 배출권 가격. 실행: 프로젝트 루트에서 python3 analysis/11_자체발전_손익분기.py
손익분기 ets_price = 전력비용 ÷ 순 저감 (원/tCO2). 이 값보다 배출권이 비싸면 전력비용을 배출권 가치가 넘는다는 뜻이다.
한계: 전력비용만 비교(설비 투자비·고로 원료비 절감 미반영), 배출권 가치는 실제 구매 회피액이 아닌 참고 가치."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.sensitivity import sweep_selfgen
from src.simulator import ETS_RANGE, SELF_SHARE, TOTAL_TWH, simulate

# fmt: off
CUTS = [0, 0.05, 0.10, 0.15, 0.20, 0.30]
CASES = {"S1 전기로(전력망)": dict(), "S4 수소환원(전력망)": dict(eaf_mt=0, h2_mt=0.3), "S4G 수소환원(무탄소)": dict(eaf_mt=0, h2_mt=0.3, h2_green=1.0)}
print(f"자체발전 = 총 {TOTAL_TWH} TWh x {SELF_SHARE:.1%} = {TOTAL_TWH*SELF_SHARE:.1f} TWh (ESG 페이지: 2024 제철소 사용 전력의 85.5% 자체 생산)")
for name, kw in CASES.items():
    df = sweep_selfgen(CUTS, **kw)
    df["배출권범위대비"] = df["breakeven_ets"].map(lambda v: "순저감 없음" if pd.isna(v) else "1만원 미만" if v < ETS_RANGE[0] else "범위 안" if v <= ETS_RANGE[1] else "3만원 초과")
    print(f"\n[{name}]"); print(df.round(2).to_string())
print(f"\n※ 배출권 허용 범위 {ETS_RANGE[0]:,}~{ETS_RANGE[1]:,}원/t. 손익분기가 이보다 높으면 배출권 수익만으로는 전력비용을 못 덮는다.")

# 참고 기준점: 고로 생산 1 t이 줄 때 자체발전도 같은 비율로 준다고 가정 (조강 약 35 Mt, 부생가스 발전이 고로 생산에 비례한다는 단순 가정. 비례 가정은 근거 약함)
print("\n[참고 기준점: 대체 생산량 ÷ 조강 35 Mt 만큼 자체발전 감소]")
for name, kw in list(CASES.items())[:2]:
    base = simulate(**kw)["power"]; c = (base["eaf_output_mt"] + base["h2_output_mt"]) / 35
    r = simulate(selfgen_cut=c, **kw); m = r["cost"]; print(f"  {name}: 감소율 {c:.1%}, 추가구매 {r['power']['add_twh']:.2f} TWh, 전력비용 {m['total_eok']:.0f}억, 순저감 {r['carbon']['abate_tco2']/1e4:.1f}만 t, 손익분기 {m['power_cost_per_tco2_krw']:,.0f}원/t")
