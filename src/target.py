"""역방향 계산(목표 -> 필요 조건). simulator가 "전환하면 얼마?"라면 여기는 "목표를 맞추려면 무엇이 얼마나 필요?"에 답한다.
입력은 simulate와 같은 변수(**kw)이고 허용 범위 밖은 ValueError. 생산량에 비례하는 값만 다루므로 selfgen_cut은 받지 않는다."""

from src.simulator import Scenario, check_range, simulate

# fmt: off
PATHS = ("eaf", "h2")


def _check(target, **kw):
    if isinstance(target, bool) or not isinstance(target, (int, float)) or not target > 0:
        raise ValueError(f"target_abate_t={target!r}: 0보다 큰 숫자가 아님 (근거 없음)")
    if kw.get("selfgen_cut", 0):
        raise ValueError("selfgen_cut은 생산량에 비례하지 않아 역산에서 제외 (근거 없음)")
    check_range(Scenario(**kw))


def required_output(target_abate_t, path="eaf", **kw):
    """required_output = 목표 순 저감량(tCO2/년)을 달성하는 데 필요한 생산량·전력·요금. path는 'eaf'(전기로) 또는 'h2'(수소환원, h2_green 등은 kw로).
    1 Mt 기준 결과를 비례 환산한다. 순 저감이 0 이하(계수가 손익분기 초과 등)면 feasible=False. within_capacity는 필요 생산량이 시뮬레이터 상한(2.5 Mt) 이내인지."""
    if path not in PATHS:
        raise ValueError(f"path={path!r}: {PATHS} 중 하나 (근거 없음)")
    _check(target_abate_t, **kw)
    one = simulate(**kw, **(dict(eaf_mt=1, eaf_util=1, h2_mt=0) if path == "eaf" else dict(eaf_mt=0, h2_mt=1, h2_util=1)))
    per_mt = one["carbon"]["abate_tco2"]
    if per_mt <= 0:
        return dict(path=path, feasible=False, reason="1 t당 순 저감이 0 이하(전력배출계수가 손익분기보다 높거나 무탄소 비율 부족)")
    mt = target_abate_t / per_mt
    return dict(path=path, feasible=True, required_mt=mt, power_twh=mt * one["power"]["add_twh"], cost_eok=mt * one["cost"]["total_eok"],
                abate_per_t=per_mt / 1e6, abate_per_mwh=one["carbon"]["abate_per_mwh"], within_capacity=mt <= 2.5)


def min_green(h2_output_mt, target_abate_t, green_supply_twh=0.0, **kw):
    """min_green = 수소환원 생산 목표(h2_output_mt, 실제 생산량 백만 t)로 목표 순 저감을 달성하는 데 필요한 최소 무탄소 전력 비율·전력량(TWh)과, 확보 가능량(green_supply_twh) 대비 부족분.
    필요 비율이 1을 넘으면 무탄소 100%로도 불가능(feasible=False). 확보 가능량은 사용자가 가정으로 넣는다(우리는 사내 공급 계획을 모른다)."""
    _check(target_abate_t, **kw)
    if isinstance(h2_output_mt, bool) or not isinstance(h2_output_mt, (int, float)) or not 0 < h2_output_mt <= 2.5:
        raise ValueError(f"h2_output_mt={h2_output_mt!r}: 0 초과 2.5 이하 (근거 없음)")
    if green_supply_twh < 0:
        raise ValueError("green_supply_twh는 0 이상")
    s = Scenario(**{**kw, "eaf_mt": 0, "h2_mt": h2_output_mt, "h2_util": 1})
    power = h2_output_mt * s.h2_kwh_t / 1000                               # 전력 TWh (= Mt x MWh/t)
    need_per_t = target_abate_t / (h2_output_mt * 1e6)                     # 목표 순 저감 (t/t)
    g = max(0.0, 1 - ((s.h2_bf_t - s.h2_resid_t) - need_per_t) / (s.h2_kwh_t / 1000 * s.grid_factor))
    cost = simulate(**{**kw, "eaf_mt": 0, "h2_mt": h2_output_mt, "h2_util": 1})["cost"]["total_eok"]
    out = dict(power_twh=power, feasible=g <= 1, max_abate_t=h2_output_mt * 1e6 * (s.h2_bf_t - s.h2_resid_t), cost_eok=cost)
    if g > 1:
        return {**out, "reason": "무탄소 100%로도 목표 순 저감에 못 미침"}
    return {**out, "green_share": g, "green_twh": g * power, "gap_twh": max(0.0, g * power - green_supply_twh), "met": g * power <= green_supply_twh}


def compare_paths(target_abate_t, **kw):
    """compare_paths = 같은 목표 순 저감을 전기로·수소환원(전력망·무탄소 50%·100%)으로 달성할 때 필요 생산량·전력·요금 비교(dict 리스트)."""
    opts = (("전기로", "eaf", {}), ("수소환원(전력망)", "h2", {}), ("수소환원(무탄소 50%)", "h2", dict(h2_green=0.5)), ("수소환원(무탄소 100%)", "h2", dict(h2_green=1.0)))
    return [dict(name=n, **required_output(target_abate_t, p, **{**kw, **o})) for n, p, o in opts]
