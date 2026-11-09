"""UCI 부하 데이터 분석 함수: 로딩, 요금 시간대, 요금 계산, 2026 개편·부하 이동 효과. 요금표는 simulator.py 것을 씀."""

import numpy as np
import pandas as pd

from src.simulator import PLANS, REFORM

# fmt: off
IDX = {"경": 0, "중": 1, "최": 2}  # 경부하·중간부하·최대부하 -> 요금표 열 번호
LABEL = {"Light_Load": "경", "Medium_Load": "중", "Maximum_Load": "최"}


def load_uci(path):
    """load_uci = UCI 읽기. 행 시각은 구간 끝이라 15분 앞당기고, 계절·요일유형('평일/토/휴일')·요금시간대(band) 열을 붙인다.
    휴일 = 하루 종일 경부하인 날(일요일, 공휴일)."""
    d = pd.read_csv(path, encoding="utf-8-sig")
    t = pd.to_datetime(d["date"], format="%d/%m/%Y %H:%M")
    t = t.where(t.dt.strftime("%H:%M") != "00:00", t + pd.Timedelta(days=1)) - pd.Timedelta(minutes=15)  # 원본은 매일 마지막 구간(24:00)을 그날 00:00으로 적어서 하루 뒤로 바로잡는다
    out = pd.DataFrame(dict(t=t, date=t.dt.date, h=t.dt.hour, kwh=d.Usage_kWh, kw=d.Usage_kWh * 4, band=d.Load_Type.map(LABEL)))
    out["sea"] = t.dt.month.map(lambda m: "여름" if m in (6, 7, 8) else "겨울" if m in (11, 12, 1, 2) else "봄가을")
    off = (out.band == "경").groupby(out.date).transform("all")
    out["day"] = np.where(off, "휴일", np.where(t.dt.dayofweek == 5, "토", "평일"))
    return out


def hourly_profile(d):
    """hourly_profile = 시간별 평균 부하. 요일유형(평일/토/휴일) x 시각(0~23)의 평균 kW 표."""
    return d.groupby(["h", "day"]).kw.mean().unstack()


def baseload(d, hours=range(0, 6)):
    """baseload = 기저부하. 평일 새벽(기본 0~5시) kW의 중앙값. 설비가 쉬어도 켜져 있는 최소 부하의 추정치."""
    return d[(d.day == "평일") & d.h.isin(hours)].kw.median()


def reform_band(d, mid=range(9, 15), peak=range(18, 21)):
    """reform_band = 개편 후 요금시간대. 휴일이 아닌 날 mid 시각은 중간부하, peak 시각은 최대부하로 바꾼 band를 돌려준다."""
    b, work = d.band.copy(), d.day != "휴일"
    b[work & d.h.isin(mid)] = "중"
    b[work & d.h.isin(peak)] = "최"
    return b


def price(d, band, reform=False, plan="A2"):
    """price = 단가. 행마다 (계절, 시간대)에 맞는 전력량요금(원/kWh). reform=True면 2026 개편 단가 변화를 더한다. plan 기본 A2는 UCI 사업장(수백 kW)에 맞는 고압A 선택Ⅱ."""
    tariff = PLANS[plan][1]
    table = {(s, b): tariff[s][i] + REFORM[s][i] * reform for s in tariff for b, i in IDX.items()}
    return pd.Series(list(zip(d.sea, band)), index=d.index).map(table)


def annual_cost(d, band, reform=False, kwh=None, plan="A2"):
    """annual_cost = 연간 요금. 전력량요금 + 기본요금(최대수요 kW x 기본요금 단가 x 12). 한 해 자료의 연 최대를 12개월 모두에 적용(정상상태 가정, 실제는 직전 12개월 최대).
    kwh를 주면 그 사용량으로 계산(부하 이동 후 등). 기후환경·연료비조정요금·기금은 포함하지 않음."""
    kwh = d.kwh if kwh is None else kwh
    energy, basic = (kwh * price(d, band, reform, plan)).sum(), kwh.max() * 4 * PLANS[plan][0] * 12
    return dict(energy=energy, basic=basic, total=energy + basic, avg=(energy + basic) / kwh.sum())


def shift_peak(d, band, f):
    """shift_peak = 최대부하 이동. 최대부하 시간 사용량의 f 비율을 같은 날 경부하 시간으로 옮긴 사용량(kWh)을 돌려준다."""
    removed = d.kwh.where(band == "최", 0) * f
    moved = removed.groupby(d.date).transform("sum") / (band == "경").groupby(d.date).transform("sum").clip(lower=1)
    return d.kwh - removed + moved.where(band == "경", 0)


def load_duration(d):
    """load_duration = 부하지속곡선. 15분 부하(kW)를 큰 순으로 정렬한 값. x축은 전체 시간 대비 비율(%)."""
    kw = d.kw.sort_values(ascending=False).reset_index(drop=True)
    return kw.index.to_series() / len(kw) * 100, kw


def peak_shave(d, cap, band, reform=False):
    """peak_shave = 최대수요 상한 cap(kW) 적용. cap 초과분을 잘라낸 사용량(kWh)으로 요금을 다시 계산해 절감액과 잘라낸 에너지 비율을 돌려준다.
    잘라낸 에너지는 다시 쓰지 않는다고 가정하고 그 전력량요금 절감은 energy_save_upper(상한, 공짜로 충당한다는 가정)로 따로 표시한다. 설비(ESS 등) 비용은 반영하지 않는다.
    근거로 쓸 수 있는 값은 기본요금 절감(basic_save)뿐이다."""
    kwh = d.kwh.clip(upper=cap / 4)
    base, new = annual_cost(d, band, reform), annual_cost(d, band, reform, kwh)
    return dict(cap=cap, cut_kwh=d.kwh.sum() - kwh.sum(), cut_pct=(1 - kwh.sum() / d.kwh.sum()) * 100, hours=int((d.kw > cap).sum() / 4),
                basic_save=base["basic"] - new["basic"], energy_save_upper=base["energy"] - new["energy"])
