"""평가용 질문 세트 35개와 기대 답 (처음부터 끝까지 실행). 정상 20 · 정보 부족 8 · 범위 밖/근거 없음 7.
기대 답 = 시뮬레이터·역산 함수 결과. hand가 있는 항목은 시뮬레이터를 쓰지 않은 손계산 식으로 한 번 더 대조한다(독립 검증).
N20(그린 수소가 나은 상황)·N21(전력망 전기가 나은 상황)은 h2_supply 질문이라 숫자 외에 추천(pick)도 맞아야 한다(PICK, analysis/14 채점).
어시스턴트 평가는 이 QUESTIONS를 import해서 쓴다: 숫자 일치(정상), 되묻기(정보 부족), 거절(범위 밖) 여부를 본다.
규칙: 질문은 단독으로 읽혀야 한다(앞 문항이나 "S1" 같은 약칭을 가리키지 않는다. 2026-11-09 평가에서 11개가 이 때문에 되물음이 나와 문장을 고침, 정답은 그대로). 규모(생산량)나 목표가 없으면 되묻는다. 가동률·요금제 같은 보조 변수는 기본값을 쓰되 답변에 가정으로 밝힌다.
실행: 프로젝트 루트에서 python3 analysis/09_질문세트.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.hydrogen import h2_supply
from src.simulator import breakeven_grid, simulate
from src.target import close_gap, min_green, required_output

# fmt: off
GF, E, H = 0.4173, 450 / 1000, 3.72  # 계수, 전기로 MWh/t, 수소환원 MWh/t
S1 = dict(eaf_mt=2.5, eaf_util=0.7)  # 광양 전기로 기본(simulate 기본값과 같음)
c = lambda **k: simulate(**k)["carbon"]; p = lambda **k: simulate(**k)["power"]; k_ = lambda **k: simulate(**k)["cost"]
mg = lambda **k: min_green(0.5, 50e4, **k)
cg = close_gap(0.5, 50e4, 0.3); lv = lambda n: next(x for x in cg['levers'] if x['lever'] == n)['needed']  # 부족 레버 역산(수소환원 50만 t, 목표 50만 t, 확보 0.3 TWh)
G = 1 - (1.99 - 1.0) / (H * GF)  # 수소환원 0.5 Mt, 순 저감 1.0 t/t일 때 필요한 무탄소 비율(손계산)
# 그린 수소 vs 전력망 전기(h2_supply): 수소환원 100만 t, PPA 180원/kWh. 그린이 나은 상황 = EU 수준 탄소 가격, 전력망이 나은 상황 = 현재 K-ETS
EUA, KAU, ELEC = 131_595, 29_500, 51 * 52.5 / 1000                    # 원/tCO2, 원/tCO2, 수전해 MWh/t(수소 51 kg x 52.5 kWh)
hs_g, hs_e = h2_supply(1.0, ets_price=EUA), h2_supply(1.0, ets_price=KAU)
hv = lambda r, key, f: next(o for o in r["options"] if o["key"] == key)[f]
PPA_U = (180 * 1.0352 + 9.79 + 11.682 + 0.12) * 1.027                  # 손계산 PPA 부담 단가: (계약가 x (1+손실 3.52%) + 망이용료 + 부가정산금 + 수수료) x (1+기금 2.7%)
GRID_U = simulate(eaf_mt=0, h2_mt=1, h2_util=1)["cost"]["unit_krw_kwh"]  # 전력망 단가(원/kWh)는 요금표·달력 가중이라 손계산 대신 시뮬레이터 값
PICK = {"N20": "green", "N21": "grid"}                                 # 기대 추천
N = [  # (id, 질문, 기대 값 dict, 손계산 dict 또는 None)
 ("N01", "광양 전기로 250만 t을 가동률 70%로 돌리면 추가로 필요한 전력은 몇 TWh야?", dict(add_twh=p()["add_twh"]), dict(add_twh=2.5 * 0.7 * E)),
 ("N02", "광양 전기로 250만 t을 가동률 70%로 돌릴 때, 전력 사용으로 늘어나는 탄소(Scope 2)는 몇 tCO2야?", dict(add_tco2=c()["add_tco2"]), dict(add_tco2=2.5 * 0.7 * E * 1e6 * GF)),
 ("N03", "광양 전기로 250만 t을 가동률 100%로 돌리면 전기요금은 연 몇 억 원이야? (요금제 B3)", dict(total_eok=k_(eaf_util=1)["total_eok"]), None),
 ("N04", "전력배출계수가 0.30이면 광양 전기로 250만 t(가동률 70%)의 순 저감은 몇 tCO2야?", dict(abate_tco2=c(grid_factor=0.3)["abate_tco2"]), dict(abate_tco2=1.75e6 * (1.99 - 0.08) - 1.75e6 * E * 0.3)),
 ("N05", "수소환원 30만 t을 가동률 70%, 전력망 전력으로 돌리면 추가 전력과 순 저감은?", dict(add_twh=p(eaf_mt=0, h2_mt=0.3)["add_twh"], abate_tco2=c(eaf_mt=0, h2_mt=0.3)["abate_tco2"]), dict(add_twh=0.21 * H, abate_tco2=0.21e6 * (1.99 - H * GF))),
 ("N06", "전기로 없이 수소환원 30만 t만 가동률 70%로 돌리고 그 전력을 전부 무탄소로 바꾸면 순 저감은 몇 tCO2야?", dict(abate_tco2=c(eaf_mt=0, h2_mt=0.3, h2_green=1)["abate_tco2"]), dict(abate_tco2=0.21e6 * 1.99)),
 ("N08", "광양 전기로 250만 t을 가동률 70%로 돌릴 때(개편 후 요금), 요금제 A2로 계약하면 전기요금은 연 몇 억 원이야?", dict(total_eok=k_(plan="A2")["total_eok"]), None),
 ("N09", "연 순 저감 100만 t을 전기로로 달성하려면 몇 백만 t을 만들어야 해?", dict(required_mt=required_output(1e6, "eaf")["required_mt"]), dict(required_mt=1e6 / (1.99 - 0.08 - E * GF) / 1e6)),
 ("N10", "연 순 저감 100만 t을 무탄소 50% 수소환원으로 달성하려면 필요한 생산량과 전력은?", dict(required_mt=required_output(1e6, "h2", h2_green=0.5)["required_mt"], power_twh=required_output(1e6, "h2", h2_green=0.5)["power_twh"]), dict(required_mt=1 / (1.99 - H * GF * 0.5), power_twh=H / (1.99 - H * GF * 0.5))),
 ("N11", "수소환원 50만 t/년으로 순 저감 50만 t을 하려면 무탄소 전력이 몇 %나 필요해?", dict(green_share=mg()["green_share"]), dict(green_share=1 - (1.99 - 0.5 / 0.5) / (H * GF))),
 ("N12", "수소환원 50만 t/년으로 순 저감 50만 t을 하려는데 무탄소 전력을 0.5 TWh만 확보하면 몇 TWh가 부족해?", dict(gap_twh=mg(green_supply_twh=0.5)["gap_twh"]), dict(gap_twh=G * 0.5 * H - 0.5)),
 ("N13", "수소환원이 고로보다 배출을 늘리기 시작하는 전력배출계수는? (3,720 kWh/t, 고로 1.99 t/t)", dict(breakeven=breakeven_grid()), dict(breakeven=1.99 / H)),
 ("N14", "연 순 저감 100만 t을 목표로 전기로와 수소환원(전력망 전력)을 비교하면, 전력 1MWh당 순 저감은 어느 쪽이 얼마나 커?", dict(eaf=c(eaf_util=1, h2_mt=0)["abate_per_mwh"], h2=c(eaf_mt=0, h2_mt=1, h2_util=1)["abate_per_mwh"]), dict(eaf=(1.99 - 0.08 - E * GF) / E, h2=(1.99 - H * GF) / H)),
 ("N15", "배출권 가격을 t당 2만 원으로 가정하면, 광양 전기로 250만 t을 가동률 70%로 돌렸을 때 순 저감의 참고 가치는 몇 억 원이야?", dict(ets_value_eok=c(ets_price=2e4)["ets_value_eok"]), dict(ets_value_eok=(1.75e6 * (1.99 - 0.08) - 1.75e6 * E * GF) * 2e4 / 1e8)),
 ("N16", "포스코가 말한 순감축 1.4 t/t를 그대로 쓰면, 광양 전기로 250만 t을 가동률 70%로 돌렸을 때 순 저감은 몇 tCO2야?", dict(abate_tco2=c(eaf_basis="posco_net")["abate_tco2"]), dict(abate_tco2=1.75e6 * 1.4)),
 ("N17", "2026년 요금 개편 전(2025년 시간대·단가) 기준으로 광양 전기로 250만 t을 가동률 70%로 돌리면 전기요금은 연 몇 억 원이야?", dict(total_eok=k_(band_rule="2025")["total_eok"]), None),
 ("N18", "수소환원 50만 t/년으로 순 저감 50만 t을 하려는데 무탄소 전력을 0.3 TWh만 확보했어. 부족분을 메우려면 확보량을 얼마로 늘려야 해?", dict(green_supply_twh=lv("green_supply_twh")), dict(green_supply_twh=G * 0.5 * H)),
 ("N19", "수소환원 50만 t/년으로 순 저감 50만 t을 하려는데 무탄소 확보량을 0.3 TWh에서 늘릴 수 없다면, 순 저감 목표를 얼마까지 낮춰야 부족이 없어?", dict(target_abate_t=lv("target_abate_t")), dict(target_abate_t=0.5e6 * (1.99 - H * GF) + 0.3e6 * GF)),
 ("N20", "수소환원 100만 t/년의 수소를 만들 때, 탄소 가격이 EU 수준인 t당 131,595원이고 재생에너지 직접PPA가 180원/kWh라면 그린 수소와 전력망 전기 중 어느 쪽이 나아? 두 방법의 쇳물 1t당 비용(탄소 비용 포함)과 순 저감도 알려줘.",
  dict(green_krw_per_t=hv(hs_g, "green", "krw_per_t"), grid_krw_per_t=hv(hs_g, "grid", "krw_per_t"), green_abate_per_t=hv(hs_g, "green", "abate_per_t"), grid_abate_per_t=hv(hs_g, "grid", "abate_per_t")),
  dict(green_abate_per_t=1.99 - (H - ELEC) * GF, grid_abate_per_t=1.99 - H * GF,  # 순 저감 = 고로 1.99 - 전력망에서 산 전력 x 계수 (그린은 공정 전력만)
       green_krw_per_t=(ELEC * PPA_U + (H - ELEC) * GRID_U) * 1000 + EUA * (H - ELEC) * GF, grid_krw_per_t=H * GRID_U * 1000 + EUA * H * GF)),  # 1t당 = 전력비 + 탄소 가격 x Scope 2
 ("N21", "수소환원 100만 t/년의 수소를 만들 때, 탄소 가격이 지금 K-ETS 수준인 t당 29,500원이고 재생에너지 직접PPA가 180원/kWh라면 그린 수소와 전력망 전기 중 어느 쪽이 나아? 두 방법의 쇳물 1t당 비용과, 그린 수소가 유리해지는 탄소 가격도 알려줘.",
  dict(grid_krw_per_t=hv(hs_e, "grid", "krw_per_t"), green_krw_per_t=hv(hs_e, "green", "krw_per_t"), ets_breakeven=hs_e["thresholds"]["ets_breakeven"]),
  dict(grid_krw_per_t=H * GRID_U * 1000 + KAU * H * GF, green_krw_per_t=(ELEC * PPA_U + (H - ELEC) * GRID_U) * 1000 + KAU * (H - ELEC) * GF,
       ets_breakeven=(PPA_U - GRID_U) / GF * 1000)),  # 손익분기 탄소 가격 = (PPA 단가 - 전력망 단가) / 배출계수 (원/kWh ÷ t/MWh x 1000)
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
QUESTIONS = [dict(id=i, type="normal", q=q, expect=e, hand=h, **({"pick": PICK[i]} if i in PICK else {})) for i, q, e, h in N] + [dict(id=i, type="ask", q=q, missing=m) for i, q, m in M] + [dict(id=i, type="refuse", q=q, kw=kw, reason=r) for i, q, kw, r in R]

# 처음 보는 질문 3개(2026-11-09 추가). 위 33개와 섞지 않고 따로 평가한다: 프롬프트·도구를 고치는 데 쓰지 않은 문항이라 점수가 부풀려지지 않는다.
# 단, 계산기를 만든 쪽(Claude)이 쓴 질문이라 "작성자와 독립"은 아니다. 팀원이 쓴 질문을 더하면 더 좋다.
UNSEEN = [
    dict(id="U01", type="normal", q="수소환원 50만 t/년으로 순 저감 50만 t을 하려는데 확보한 무탄소 전력이 0.3 TWh야. 전력 원단위를 몇 kWh/t까지 낮추면 부족이 없어져?",
         expect=dict(h2_kwh_t=lv("h2_kwh_t")), hand=dict(h2_kwh_t=1000 * (0.3 / 0.5 + (1.99 - 0.5e6 / 0.5e6) / GF))),  # 손계산: 원단위 = 1000 x (확보량/생산량 + 여유/배출계수)
    dict(id="U02", type="ask", q="전력배출계수가 낮아지면 얼마나 유리해져?", missing="대상 시나리오(전기로 또는 수소환원 규모와 목표)와 얼마나 낮아지는지(계수 값)"),
    dict(id="U03", type="refuse", q="내년 한국 산업용 전기요금이 몇 % 오를지 알려줘.", kw=None, reason="미래 요금 인상률 예측 불가"),
]

if __name__ == "__main__":
    near = lambda a, b: abs(a - b) <= 1e-6 * max(1, abs(b))
    for d in QUESTIONS:
        if d["type"] == "normal":
            ok = "손계산 없음" if d["hand"] is None else ("손계산 일치" if all(near(d["expect"][k], v) for k, v in d["hand"].items()) else "손계산 불일치!")
            print(d["id"], ok, {k: round(v, 4) for k, v in d["expect"].items()}, "|", d["q"])
            assert ok != "손계산 불일치!", d["id"]
            if "pick" in d:
                got = {"N20": hs_g, "N21": hs_e}[d["id"]]["verdict"]["pick"]
                print(f"  추천: 기대 {d['pick']}, 계산기 {got}")
                assert got == d["pick"], d["id"]
        elif d["type"] == "ask": print(d["id"], "되묻기:", d["missing"], "|", d["q"])
        else:
            if d["kw"]:
                try: simulate(**d["kw"]); raise AssertionError(f"{d['id']} 거절돼야 함")
                except ValueError as e: print(d["id"], "거절(코드 확인):", e)
            else: print(d["id"], "거절(근거 없음):", d["reason"], "|", d["q"])
    print(f"\n질문 {len(QUESTIONS)}개: 정상 {len(N)}, 정보 부족 {len(M)}, 범위 밖 {len(R)}")
    for d in UNSEEN:
        ok = "" if d["type"] != "normal" else ("손계산 일치" if all(near(d["expect"][k], v) for k, v in d["hand"].items()) else "손계산 불일치!")
        assert ok != "손계산 불일치!", d["id"]
        print(d["id"], "(처음 보는 질문)", ok, {k: round(v, 4) for k, v in d.get("expect", {}).items()}, "|", d["q"])
