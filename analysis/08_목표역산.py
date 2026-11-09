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

# 4. 대안 검토: 한 조건만 바꿔가며 다시 비교 (연간 전력량 기준, 시간대별 공급·저장 미반영)
from src.target import sweep_green
print("\n[확보 가능한 무탄소 전력량을 바꿔 가면] 수소환원 50만 t/년, 목표 순 저감 50만 t")
for r in sweep_green(0.5, 50e4, "green_supply_twh", [0, 0.25, 0.5, 0.75]): print(f"  확보 {r['green_supply_twh']:.2f} TWh -> 부족 {r['gap_twh']:.2f} TWh ({'충족' if r['met'] else '부족'})")
print("[수소환원 전력 원단위를 바꿔 가면] 필요 무탄소 비율")
for r in sweep_green(0.5, 50e4, "h2_kwh_t", [2700, 3480, 3720, 4000]): print(f"  {r['h2_kwh_t']} kWh/t -> {r['green_share']:.0%} (전력 {r['power_twh']:.2f} TWh, 무탄소 {r['green_twh']:.2f} TWh)")
print("[전력배출계수를 바꿔 가면] 필요 무탄소 비율")
for r in sweep_green(0.5, 50e4, "grid_factor", [0.30, 0.4173, 0.50]): print(f"  {r['grid_factor']} -> {r['green_share']:.0%}")
print(f"  ※ {r['note']}")

# 5. 부족할 때 무엇을 바꿔야 메워지나: 조건을 하나씩만 바꿔 부족분을 0으로 만드는 값 (조합은 계산하지 않음)
from src.target import close_gap
g = close_gap(0.5, 50e4, 0.3)
print(f"\n[수소환원 50만 t/년, 목표 50만 t, 무탄소 확보 0.3 TWh] 필요 {g['green_twh']:.2f} TWh, 부족 {g['gap_twh']:.2f} TWh -> 하나씩 바꾼다면")
for l in g["levers"]: print(f"  [{l['kind']}] {l['label']}: {l['now']:,.4g} -> {l['needed']:,.4g} {l['unit']}" + ("" if l["in_range"] else " (허용 범위 밖)"))
