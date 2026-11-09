"""평가용 질문 세트 33개와 기대 답 (처음부터 끝까지 실행). 정상 18 · 정보 부족 8 · 범위 밖/근거 없음 7.
기대 답 = 시뮬레이터·역산 함수 결과. hand가 있는 항목은 시뮬레이터를 쓰지 않은 손계산 식으로 한 번 더 대조한다(독립 검증).
어시스턴트 평가는 이 QUESTIONS를 import해서 쓴다: 숫자 일치(정상), 되묻기(정보 부족), 거절(범위 밖) 여부를 본다.
규칙: 규모(생산량)나 목표가 없으면 되묻는다. 가동률·요금제 같은 보조 변수는 기본값을 쓰되 답변에 가정으로 밝힌다.
실행: 프로젝트 루트에서 python3 analysis/09_질문세트.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.simulator import breakeven_grid, simulate
from src.target import close_gap, min_green, required_output

# fmt: off
GF, E, H = 0.4173, 450 / 1000, 3.72  # 계수, 전기로 MWh/t, 수소환원 MWh/t
S1 = dict(eaf_mt=2.5, eaf_util=0.7)  # 광양 전기로 기본(simulate 기본값과 같음)
c = lambda **k: simulate(**k)["carbon"]; p = lambda **k: simulate(**k)["power"]; k_ = lambda **k: simulate(**k)["cost"]
mg = lambda **k: min_green(0.5, 50e4, **k)
cg = close_gap(0.5, 50e4, 0.3); lv = lambda n: next(x for x in cg['levers'] if x['lever'] == n)['needed']  # 부족 레버 역산(수소환원 50만 t, 목표 50만 t, 확보 0.3 TWh)
G = 1 - (1.99 - 1.0) / (H * GF)  # 수소환원 0.5 Mt, 순 저감 1.0 t/t일 때 필요한 무탄소 비율(손계산)
N = [  # (id, 질문, 기대 값 dict, 손계산 dict 또는 None)
 ("N01", "광양 전기로 250만 t을 가동률 70%로 돌리면 추가로 필요한 전력은 몇 TWh야?", dict(add_twh=p()["add_twh"]), dict(add_twh=2.5 * 0.7 * E)),
 ("N02", "N01 조건이면 전력 사용으로 늘어나는 탄소(Scope 2)는 몇 tCO2야?", dict(add_tco2=c()["add_tco2"]), dict(add_tco2=2.5 * 0.7 * E * 1e6 * GF)),
 ("N03", "전기로를 가동률 100%로 돌리면 전기요금은 연 몇 억 원이야? (요금제 B3)", dict(total_eok=k_(eaf_util=1)["total_eok"]), None),
 ("N04", "전력배출계수가 0.30이면 전기로(가동률 70%) 순 저감은 몇 tCO2야?", dict(abate_tco2=c(grid_factor=0.3)["abate_tco2"]), dict(abate_tco2=1.75e6 * (1.99 - 0.08) - 1.75e6 * E * 0.3)),
 ("N05", "수소환원 30만 t을 가동률 70%, 전력망 전력으로 돌리면 추가 전력과 순 저감은?", dict(add_twh=p(eaf_mt=0, h2_mt=0.3)["add_twh"], abate_tco2=c(eaf_mt=0, h2_mt=0.3)["abate_tco2"]), dict(add_twh=0.21 * H, abate_tco2=0.21e6 * (1.99 - H * GF))),
 ("N06", "N05의 수소환원 전력을 전부 무탄소로 바꾸면 순 저감은?", dict(abate_tco2=c(eaf_mt=0, h2_mt=0.3, h2_green=1)["abate_tco2"]), dict(abate_tco2=0.21e6 * 1.99)),
 ("N08", "전기로(가동률 70%, 개편 후 요금)를 요금제 A2로 계약하면 전기요금은 연 몇 억 원이야?", dict(total_eok=k_(plan="A2")["total_eok"]), None),
 ("N09", "연 순 저감 100만 t을 전기로로 달성하려면 몇 백만 t을 만들어야 해?", dict(required_mt=required_output(1e6, "eaf")["required_mt"]), dict(required_mt=1e6 / (1.99 - 0.08 - E * GF) / 1e6)),
 ("N10", "연 순 저감 100만 t을 무탄소 50% 수소환원으로 달성하려면 필요한 생산량과 전력은?", dict(required_mt=required_output(1e6, "h2", h2_green=0.5)["required_mt"], power_twh=required_output(1e6, "h2", h2_green=0.5)["power_twh"]), dict(required_mt=1 / (1.99 - H * GF * 0.5), power_twh=H / (1.99 - H * GF * 0.5))),
 ("N11", "수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?", dict(green_share=mg()["green_share"]), dict(green_share=1 - (1.99 - 0.5 / 0.5) / (H * GF))),
 ("N12", "N11에서 무탄소 전력을 0.5 TWh만 확보하면 몇 TWh가 부족해?", dict(gap_twh=mg(green_supply_twh=0.5)["gap_twh"]), dict(gap_twh=G * 0.5 * H - 0.5)),
 ("N13", "수소환원이 고로보다 배출을 늘리기 시작하는 전력배출계수는? (3,720 kWh/t, 고로 1.99 t/t)", dict(breakeven=breakeven_grid()), dict(breakeven=1.99 / H)),
 ("N14", "전력 1MWh당 순 저감은 전기로와 수소환원(전력망) 중 어느 쪽이 얼마나 커?", dict(eaf=c(eaf_util=1, h2_mt=0)["abate_per_mwh"], h2=c(eaf_mt=0, h2_mt=1, h2_util=1)["abate_per_mwh"]), dict(eaf=(1.99 - 0.08 - E * GF) / E, h2=(1.99 - H * GF) / H)),
 ("N15", "배출권 가격을 t당 2만 원으로 가정하면 S1(전기로 70%)의 순 저감 참고 가치는 몇 억 원이야?", dict(ets_value_eok=c(ets_price=2e4)["ets_value_eok"]), dict(ets_value_eok=(1.75e6 * (1.99 - 0.08) - 1.75e6 * E * GF) * 2e4 / 1e8)),
 ("N16", "포스코가 말한 순감축 1.4 t/t를 그대로 쓰면 S1 순 저감은 몇 tCO2야?", dict(abate_tco2=c(eaf_basis="posco_net")["abate_tco2"]), dict(abate_tco2=1.75e6 * 1.4)),
 ("N17", "2026년 요금 개편 전(2025년 시간대·단가)으로 계산하면 S1 요금은 연 몇 억 원이야?", dict(total_eok=k_(band_rule="2025")["total_eok"]), None),
 ("N18", "수소환원 50만 t/년으로 순 저감 50만 t을 하려는데 무탄소 전력을 0.3 TWh만 확보했어. 부족분을 메우려면 확보량을 얼마로 늘려야 해?", dict(green_supply_twh=lv("green_supply_twh")), dict(green_supply_twh=G * 0.5 * H)),
 ("N19", "N18에서 확보량을 0.3 TWh에서 늘릴 수 없다면, 순 저감 목표를 얼마까지 낮춰야 부족이 없어?", dict(target_abate_t=lv("target_abate_t")), dict(target_abate_t=0.5e6 * (1.99 - H * GF) + 0.3e6 * GF)),
]
M = [  # 정보 부족: 되물어야 하는 항목
 ("M01", "수소환원을 하면 탄소가 얼마나 줄어?", "생산 규모(h2_mt)"),
 ("M02", "전기로를 돌리면 전기요금이 얼마야?", "생산 규모(eaf_mt)"),
 ("M03", "탄소를 줄이고 싶은데 전력이 얼마나 필요해?", "목표 순 저감량과 공정 경로"),
 ("M04", "무탄소 전력은 얼마나 확보해야 해?", "수소환원 생산량과 목표 순 저감량"),
 ("M05", "전력 요금이 오르면 어떻게 돼?", "변동률과 대상 시나리오"),
 ("M06", "전기로랑 수소환원 중 뭐가 더 나아?", "비교 기준(같은 생산량 또는 같은 감축 목표)과 규모"),
 ("M07", "배출권으로 환산하면 가치가 얼마야?", "배출권 가격 가정(ets_price)과 시나리오"),
 ("M08", "무탄소 전력이 부족하면 뭘 바꿔야 해?", "수소환원 생산량, 목표 순 저감량, 확보 가능한 무탄소 전력량(green_supply_twh)"),
]
R = [  # 범위 밖/근거 없음: 거절. kw가 있으면 simulate가 ValueError를 내는지 코드로 검증
 ("R01", "2035년 한국 전력배출계수는 정확히 얼마가 돼?", None, "미래 예측 불가(가정 경로만 제시)"),
 ("R02", "광양제철소의 실제 계약전력과 지난달 전기요금 고지서 금액은?", None, "사내 데이터 없음"),
 ("R03", "수소환원 설비 투자비와 투자 회수 기간은?", None, "투자비 미반영"),
 ("R04", "전기로 가동률을 150%로 돌리면 어떻게 돼?", dict(eaf_util=1.5), "허용 범위 밖"),
 ("R05", "수소환원을 3,000만 t으로 늘리면?", dict(h2_mt=30), "허용 범위 밖"),
 ("R06", "배출권을 실제로 얼마나 덜 사도 되는지 알려줘.", None, "할당량·보유량 없음. 거절하되 가정 가격을 주면 참고 가치는 계산할 수 있다고 안내"),
 ("R07", "이 무탄소 전력 확보량이면 시간대별로도 부족 없이 생산이 멈추지 않고 돌아가?", None, "연간 전력량 기준만 가능, 시간대별 공급·저장 미반영이라 생산 지속 여부 판단 불가"),
]
QUESTIONS = [dict(id=i, type="normal", q=q, expect=e, hand=h) for i, q, e, h in N] + [dict(id=i, type="ask", q=q, missing=m) for i, q, m in M] + [dict(id=i, type="refuse", q=q, kw=kw, reason=r) for i, q, kw, r in R]

if __name__ == "__main__":
    near = lambda a, b: abs(a - b) <= 1e-6 * max(1, abs(b))
    for d in QUESTIONS:
        if d["type"] == "normal":
            ok = "손계산 없음" if d["hand"] is None else ("손계산 일치" if all(near(d["expect"][k], v) for k, v in d["hand"].items()) else "손계산 불일치!")
            print(d["id"], ok, {k: round(v, 4) for k, v in d["expect"].items()}, "|", d["q"])
            assert ok != "손계산 불일치!", d["id"]
        elif d["type"] == "ask": print(d["id"], "되묻기:", d["missing"], "|", d["q"])
        else:
            if d["kw"]:
                try: simulate(**d["kw"]); raise AssertionError(f"{d['id']} 거절돼야 함")
                except ValueError as e: print(d["id"], "거절(코드 확인):", e)
            else: print(d["id"], "거절(근거 없음):", d["reason"], "|", d["q"])
    print(f"\n질문 {len(QUESTIONS)}개: 정상 {len(N)}, 정보 부족 {len(M)}, 범위 밖 {len(R)}")
