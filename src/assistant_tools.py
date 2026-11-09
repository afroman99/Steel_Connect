"""AI 어시스턴트가 호출하는 계산 도구 (JSON 입출력). 계산은 코드, 해석은 LLM.
call_tool(이름, 인자 dict) -> {"status": "ok"|"ask"|"refuse", ...}. 어시스턴트 규칙:
- ask: 필수 입력이 없음 -> missing을 사용자에게 되묻는다. refuse: 허용 범위 밖·모르는 변수 -> 이유와 함께 답변을 유보한다.
- ok: result의 숫자만 인용한다. defaults_used는 사용자가 안 정해 기본값으로 계산한 변수이므로 답변에 가정으로 밝힌다. sources로 출처를 붙인다."""

from dataclasses import fields

from src.simulator import SOURCES, Scenario, breakeven_grid, simulate
from src.target import compare_paths, min_green, required_output

# fmt: off
VARS = [f.name for f in fields(Scenario)]
REQUIRED = {"simulate": ["eaf_mt 또는 h2_mt"], "required_output": ["target_abate_t", "path"], "min_green": ["h2_output_mt", "target_abate_t"], "compare_paths": ["target_abate_t"], "breakeven_grid": []}
TOOLS = {  # LLM 도구 정의용 설명. 변수 의미·단위·허용 범위는 reports/시나리오_변수표.md
 "simulate": "시나리오 계산: 추가 전력(TWh)·탄소(tCO2)·요금(억 원). 인자는 Scenario 변수(eaf_mt, h2_mt, eaf_util, grid_factor, plan, ets_price 등).",
 "required_output": "목표 순 저감(target_abate_t, tCO2/년)을 달성하는 필요 생산량·전력·요금. path는 'eaf' 또는 'h2'(h2_green 등 추가 가능).",
 "min_green": "수소환원 생산량(h2_output_mt)으로 목표 순 저감을 달성하는 최소 무탄소 비율·전력량·부족분(green_supply_twh는 사용자 가정).",
 "compare_paths": "같은 목표 순 저감을 전기로·수소환원(전력망·무탄소 50%·100%)으로 달성할 때 비교.",
 "breakeven_grid": "수소환원이 고로보다 배출을 늘리기 시작하는 전력배출계수. 인자: h2_kwh_t, bf_t, resid_t.",
}
FUNCS = {"simulate": simulate, "required_output": required_output, "min_green": min_green, "compare_paths": compare_paths, "breakeven_grid": breakeven_grid}


def call_tool(name, args=None):
    args = dict(args or {})
    if name not in FUNCS:
        return dict(status="refuse", reason=f"알 수 없는 도구 {name!r}", tools=list(FUNCS))
    if name == "simulate" and not {"eaf_mt", "h2_mt"} & args.keys():
        return dict(status="ask", missing=REQUIRED[name])
    miss = [k for k in REQUIRED[name] if " " not in k and k not in args]
    if miss:
        return dict(status="ask", missing=miss)
    if name == "simulate" and (bad := [k for k in args if k not in VARS]):
        return dict(status="refuse", reason=f"알 수 없는 변수 {bad}", variables=VARS)
    try:
        res = FUNCS[name](**args)
    except TypeError as e:
        return dict(status="refuse", reason=f"인자 오류: {e}")
    except ValueError as e:
        return dict(status="refuse", reason=str(e))
    out = dict(status="ok", tool=name, result=res, sources=SOURCES)
    if name == "simulate":
        out["defaults_used"] = {k: v for k, v in res["input"].items() if k not in args}
    return out
