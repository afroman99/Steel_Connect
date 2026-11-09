"""목표 역산 데모 (처음부터 끝까지 실행): 순 저감 목표를 주면 필요한 생산량·전력·무탄소 비율을 계산한다.
실행: 프로젝트 루트에서 python3 analysis/08_목표역산.py (그림은 figures/08_목표역산.png). 목표·공급 가정은 사용자 입력이며 사내 공급 계획은 모른다."""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.plot_setup import setup_korean_font
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

# 6. 그림
setup_korean_font()
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
ok = df[df.feasible.astype(bool)]
ax[0, 0].bar(ok.index, ok.required_mt * 100, color=["#1565c0", "#9e9e9e", "#66bb6a", "#2e7d32"][:len(ok)])
for i, (n, r) in enumerate(ok.iterrows()):
    ax[0, 0].text(i, r.required_mt * 100, f"{r.required_mt * 100:.0f}만 t\n{r.power_twh:.2f} TWh", ha="center", va="bottom", fontsize=8)
ax[0, 0].axhline(250, ls="--", c="gray"); ax[0, 0].text(-0.4, 255, "시뮬레이터 상한 250만 t", color="gray", fontsize=8)
ax[0, 0].set(title=f"순 저감 {T / 1e4:.0f}만 tCO2/년에 필요한 생산량 (위: 생산량, 전력)", ylabel="만 t/년"); ax[0, 0].tick_params(axis="x", labelsize=8)
sup = sweep_green(0.5, 50e4, "green_supply_twh", [x / 20 for x in range(0, 21)])
ax[0, 1].plot([r["green_supply_twh"] for r in sup], [r["gap_twh"] for r in sup], marker="o", ms=3)
ax[0, 1].axvline(sup[0]["green_twh"], ls="--", c="#2e7d32"); ax[0, 1].text(sup[0]["green_twh"] + 0.01, 0.5, f"필요 {sup[0]['green_twh']:.2f} TWh", color="#2e7d32")
ax[0, 1].set(title="수소환원 50만 t, 목표 50만 t: 확보량별 부족분 (연간 기준)", xlabel="확보한 무탄소 전력 (TWh/년)", ylabel="부족분 (TWh/년)")
for var, vals, lab in (("h2_kwh_t", list(range(2700, 4001, 100)), "전력 원단위 (kWh/t)"), ("grid_factor", [round(0.20 + 0.02 * i, 2) for i in range(19)], "전력배출계수 (tCO2/MWh)")):
    rows = [r for r in sweep_green(0.5, 50e4, var, vals) if r["feasible"]]
    a_ = ax[1, 0] if var == "h2_kwh_t" else ax[1, 0].twiny()
    a_.plot([r[var] for r in rows], [r["green_share"] * 100 for r in rows], marker="o", ms=3, c="#1565c0" if var == "h2_kwh_t" else "#c62828", label=lab)
    a_.set_xlabel(lab, color="#1565c0" if var == "h2_kwh_t" else "#c62828")
ax[1, 0].set(title="필요 무탄소 비율: 원단위(파랑, 아래 축)·배출계수(빨강, 위 축)", ylabel="필요 무탄소 비율 (%)")
lv = [l for l in g["levers"] if l["lever"] != "switch_to_eaf" and l["needed"] is not None]
ratio = [l["needed"] / l["now"] * 100 - 100 for l in lv]
fmt = lambda v: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.4g}"
ax[1, 1].barh([l["label"].split("(")[0] for l in lv], ratio, color=["#2e7d32" if l["kind"] == "결정" else "#9e9e9e" for l in lv])
for i, (l, r) in enumerate(zip(lv, ratio)):
    ax[1, 1].text(r, i, f" {fmt(l['now'])} -> {fmt(l['needed'])} {l['unit']}" + ("" if l["in_range"] else " (범위 밖)"), va="center", fontsize=8)
ax[1, 1].axvline(0, c="black"); ax[1, 1].set(title="확보 0.3 TWh일 때 부족을 메우는 조건 (하나씩, 초록 = 결정 / 회색 = 외부)", xlabel="지금 대비 바꿔야 하는 정도 (%)")
fig.tight_layout(h_pad=3)
fig.savefig(ROOT / "figures/08_목표역산.png", dpi=150, bbox_inches="tight")
print("\n그림 저장: figures/08_목표역산.png")
