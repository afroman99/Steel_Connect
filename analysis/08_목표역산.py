"""목표 역산 데모 (처음부터 끝까지 실행): 순 저감 목표를 주면 필요한 생산량·전력·무탄소 비율을 계산한다.
실행: 프로젝트 루트에서 python3 analysis/08_목표역산.py. 목표·공급 가정은 사용자 입력이며 사내 공급 계획은 모른다."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.target import compare_paths, min_green

# fmt: off
T = 100e4  # 예시 목표: 연 순 저감 100만 tCO2
df = pd.DataFrame(compare_paths(T)).set_index("name")
print(f"[목표 순 저감 {T/1e4:.0f}만 t/년을 달성하려면]"); print(df[["feasible", "required_mt", "power_twh", "cost_eok", "within_capacity"]].round(2).to_string())
for supply in (0.0, 0.5):
    r = min_green(0.5, 50e4, green_supply_twh=supply)
    print(f"[수소환원 50만 t/년, 순 저감 50만 t 목표, 무탄소 확보 {supply} TWh] 전력 {r['power_twh']:.2f} TWh 중 무탄소 {r['green_share']:.0%}({r['green_twh']:.2f} TWh) 필요, 부족 {r['gap_twh']:.2f} TWh")
print(f"[불가능 사례] 수소환원 50만 t/년, 목표 150만 t: {min_green(0.5, 150e4)}")
