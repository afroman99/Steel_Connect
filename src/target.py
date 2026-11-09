"""역방향 계산(목표 -> 필요 조건). simulator가 "전환하면 얼마?"라면 여기는 "목표를 맞추려면 무엇이 얼마나 필요?"에 답한다.
입력은 simulate와 같은 변수(**kw)이고 허용 범위 밖은 ValueError. 생산량에 비례하는 값만 다루므로 selfgen_cut은 받지 않는다."""

from src.simulator import RANGE, Scenario, check_range, simulate

# fmt: off
PATHS = ("eaf", "h2")
LIMIT_NOTE = "연간 전력량 기준. 시간대별 공급·저장은 반영하지 않아 생산 지속 여부를 판단하는 결과가 아님"
SWEEP_VARS = ("green_supply_twh", "h2_kwh_t", "grid_factor", "h2_resid_t", "target_abate_t", "h2_output_mt")


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
    필요 비율이 1을 넘으면 무탄소 100%로도 불가능(feasible=False). 확보 가능량은 사용자가 가정으로 넣는다(우리는 사내 공급 계획을 모른다).
    주의: 모두 연간 전력량 기준이다. 시간대별 공급·저장은 반영하지 않아 부족분만으로 생산 지속 여부를 판단할 수 없다(결과 note에 항상 포함)."""
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
    out = dict(note=LIMIT_NOTE, power_twh=power, feasible=g <= 1, max_abate_t=h2_output_mt * 1e6 * (s.h2_bf_t - s.h2_resid_t), cost_eok=cost)
    if g > 1:
        return {**out, "reason": "무탄소 100%로도 목표 순 저감에 못 미침"}
    return {**out, "green_share": g, "green_twh": g * power, "gap_twh": max(0.0, g * power - green_supply_twh), "met": g * power <= green_supply_twh}


def compare_paths(target_abate_t, **kw):
    """compare_paths = 같은 목표 순 저감을 전기로·수소환원(전력망·무탄소 50%·100%)으로 달성할 때 필요 생산량·전력·요금 비교(dict 리스트)."""
    opts = (("전기로", "eaf", {}), ("수소환원(전력망)", "h2", {}), ("수소환원(무탄소 50%)", "h2", dict(h2_green=0.5)), ("수소환원(무탄소 100%)", "h2", dict(h2_green=1.0)))
    return [dict(name=n, **required_output(target_abate_t, p, **{**kw, **o})) for n, p, o in opts]


def sweep_green(h2_output_mt, target_abate_t, vary, values, green_supply_twh=0.0, **kw):
    """sweep_green = 한 조건만 바꿔가며 min_green을 반복. vary는 SWEEP_VARS 중 하나(확보량·전력 원단위·전력배출계수·잔여 배출·목표·생산량), values는 그 값 목록.
    "확보량이나 효율 조건을 바꿔 다시 비교"용. 값마다 한 줄(dict)이고 범위 밖 값이 있으면 ValueError."""
    if vary not in SWEEP_VARS:
        raise ValueError(f"vary={vary!r}: {SWEEP_VARS} 중 하나 (근거 없음)")
    if not isinstance(values, (list, tuple)) or not values or len(values) > 50:
        raise ValueError("values는 1~50개의 목록")
    rows = []
    for v in values:
        a = dict(h2_output_mt=h2_output_mt, target_abate_t=target_abate_t, green_supply_twh=green_supply_twh, **kw)
        a[vary] = v
        rows.append(dict(**{vary: v}, **min_green(a.pop("h2_output_mt"), a.pop("target_abate_t"), **a)))
    return rows


def close_gap(h2_output_mt, target_abate_t, green_supply_twh, **kw):
    """close_gap = 무탄소 전력이 부족할 때, 조건을 하나씩만 바꿔 부족분(gap_twh)을 0으로 만드는 값을 역산한다(나머지는 그대로). 부족분이 없으면 levers는 빈 목록.
    레버: 확보량 늘리기, 목표 낮추기, 생산량 조정, 전력 원단위 개선, 전력배출계수 하락, 전기로로 전환. kind는 우리가 정할 수 있는 '결정'인지 바깥 조건인 '외부'인지.
    in_range=False면 시뮬레이터 허용 범위 밖이라 현실적이지 않다는 뜻이고, check_gap_twh는 그 값을 min_green에 다시 넣어 확인한 부족분(범위 밖이면 None).
    주의: 연간 전력량 기준(note). 레버를 동시에 바꾸는 조합은 계산하지 않는다. 전환 비용·시점은 반영하지 않는다."""
    base = min_green(h2_output_mt, target_abate_t, green_supply_twh=green_supply_twh, **kw)
    if not base["feasible"] or base["met"]:
        return {**base, "levers": [], **({"reason": base["reason"]} if not base["feasible"] else {})}
    s = Scenario(**{**kw, "eaf_mt": 0, "h2_mt": h2_output_mt, "h2_util": 1})
    m, T, S, K, gf, D = h2_output_mt, target_abate_t, green_supply_twh, s.h2_kwh_t / 1000, s.grid_factor, s.h2_bf_t - s.h2_resid_t
    B, G = D - T / (m * 1e6), base["green_twh"]                               # B = 1 t당 전력 배출로 쓸 수 있는 여유, G = 필요 무탄소 전력량

    def check(**over):  # 바뀐 조건을 min_green에 다시 넣어 부족분 확인. 범위 밖이면 None
        a = dict(h2_output_mt=m, target_abate_t=T, green_supply_twh=S, **kw); a.update(over)
        try: return min_green(a.pop("h2_output_mt"), a.pop("target_abate_t"), **a).get("gap_twh")
        except ValueError: return None

    def lever(name, label, kind, unit, now, new, **over):
        rng = RANGE.get(name) if name in RANGE else None
        ok = new is not None and new > 0 and (rng is None or rng[0] <= new <= rng[1])
        return dict(lever=name, label=label, kind=kind, unit=unit, now=now, needed=new, in_range=bool(ok), check_gap_twh=check(**{name: new}) if ok else None)

    Tmax = m * 1e6 * (D - K * gf * (1 - S / (m * K)))                         # 확보량 S로 달성 가능한 최대 목표
    a = K - D / gf                                                           # 생산량 1 Mt 늘 때 필요 무탄소 전력의 변화(음수면 생산을 늘릴수록 필요량이 준다)
    m2 = (S - T / (1e6 * gf)) / a if a else None
    den = m * K - S
    L = [lever("green_supply_twh", "무탄소 전력 확보량 늘리기", "결정", "TWh", S, G),
         lever("target_abate_t", "목표 순 저감 낮추기", "결정", "tCO2/년", T, Tmax),
         lever("h2_output_mt", "수소환원 생산량 조정(같은 목표를 더 큰/작은 규모로)", "결정", "백만 t", m, m2),
         lever("h2_kwh_t", "전력 원단위 개선(기술)", "외부", "kWh/t", s.h2_kwh_t, 1000 * (S / m + B / gf)),
         lever("grid_factor", "전력배출계수 하락(전력 믹스 개선)", "외부", "tCO2/MWh", gf, m * B / den if B > 0 and den > 0 else None)]
    eaf = required_output(T, "eaf", **{k: v for k, v in kw.items() if k == "grid_factor"})
    L.append(dict(lever="switch_to_eaf", label="같은 목표를 전기로로 달성(무탄소 전력 불필요)", kind="결정", unit="백만 t", now=m, needed=eaf.get("required_mt"), in_range=bool(eaf.get("within_capacity")), power_twh=eaf.get("power_twh"), cost_eok=eaf.get("cost_eok")))
    return {**base, "levers": L}
