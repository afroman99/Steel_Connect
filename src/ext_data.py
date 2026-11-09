"""외부 공개 데이터(data/ 의 kpx_*·epsis_*·icap_*, ICAP 원본만 git 제외) 계산 함수: 2025 시간대별 전력 믹스 -> 시간대별 배출계수 비율, 태양광·풍력 시간 프로필 -> 시간 일치율, ICAP -> 탄소 가격 통계.
결과 숫자는 src/emission_factor.py(TOU_GF_RATIO)와 src/hydrogen.py(HOURLY_MATCH, ETS 통계)에 상수로 옮겨 두고, analysis/05_검증.py가 원본이 있을 때 다시 계산해 대조한다.
내려받기(공공데이터포털은 로그인 없이 가능): analysis/16_외부데이터_시간대배출_재생.py 맨 위 설명 참고.
주의: 거래소 자료는 전력시장 거래 발전기만 포함(한전 PPA·자가용·지붕 태양광 제외)이라 낮 시간 태양광이 덜 잡혀 낮 배출계수가 실제보다 높게 나올 수 있다.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.simulator import RULES

# fmt: off
DATA = Path(__file__).resolve().parent.parent / "data"
FILES = dict(fuel="kpx_fuel_hourly_2025.csv", re_cap="kpx_renewable_hourly_capacity_2025.csv", icap="icap_systems.json", sales="epsis_sales_price_by_use.json")
# 연료원별 직접 배출계수 (tCO2/MWh). 석탄·LNG·원전은 제10차 전력수급기본계획(발전기별 '19~'21 실적), IGCC 0.650(태안), 석유 0.777, 무연탄 1.109, 기타는 국가 평균 0.4434를 쓴 대한환경공학회지 논문(전과정평가 기반 배출계수 변화)의 방식을 따름.
# 재생·원전·바이오는 0(IPCC 직접배출 기준). 양수·저장장치는 충전 때 배출이 생기므로 0은 단순화. LPG는 근거가 없어 석유 값(가정). 시간대별 '모양'에만 쓰고 크기는 공식 연평균 계수에 맞춘다.
FUEL_EF = {"유연탄": 0.8362, "LNG": 0.3779, "원자력": 0.0, "무연탄": 1.109, "IGCC": 0.650, "중유": 0.777, "경유": 0.777, "LPG": 0.777,
           "부생가스": 0.4434, "폐기물": 0.4434, "연료전지": 0.4434, "기타": 0.4434}
# 2025 관공서 공휴일(임시공휴일 1/27·6/3 제외, 대체공휴일 포함). 한전 계량 규칙은 「관공서의 공휴일에 관한 규정」의 공휴일(임시공휴일 제외)
HOLIDAYS_2025 = {"2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-03", "2025-05-05", "2025-05-06", "2025-06-06", "2025-08-15",
                 "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25"}


def available():
    """available = 원본 파일이 모두 있는지."""
    return all((DATA / f).exists() for f in FILES.values())


def _calendar(dates, hours):
    """_calendar = 달력 열. 거래시간 h(1~24)는 h-1시에 시작하는 1시간이라 시작 시각으로 바꾸고 계절·요일유형·2026 요금시간대(B)를 붙인다."""
    d = pd.DataFrame(dict(date=pd.to_datetime(dates), h=hours - 1))
    d["sea"] = d.date.dt.month.map(lambda m: "여름" if m in (6, 7, 8) else "겨울" if m in (11, 12, 1, 2) else "봄가을")
    hol = d.date.dt.strftime("%Y-%m-%d").isin(HOLIDAYS_2025) | (d.date.dt.dayofweek == 6)
    d["day"] = np.where(hol, "휴일", np.where(d.date.dt.dayofweek == 5, "토", "평일"))
    band = pd.Series([RULES["B"][s][h] for s, h in zip(d.sea, d.h)], index=d.index)
    band[(d.day == "토") & (band == "최")] = "중"
    band[d.day == "휴일"] = "경"
    d["band"] = band
    return d


def hourly_grid():
    """hourly_grid = 2025 시간별 전력 믹스와 배출 집약도. 시간마다 (발전량 x 연료원 배출계수) 합 / 발전량 합 = intensity(tCO2/MWh, 시장 발전기 기준), ratio = intensity / 1년 시간 평균(일정 부하 기준 1)."""
    f = pd.read_csv(DATA / FILES["fuel"], encoding="utf-8-sig")
    f["ef"] = f["연료원별"].map(FUEL_EF).fillna(0.0)
    f["co2"] = f["전력거래량(MWh)"] * f["ef"]
    g = f.groupby(["거래일자", "거래시간"]).agg(mwh=("전력거래량(MWh)", "sum"), co2=("co2", "sum")).reset_index()
    out = _calendar(g["거래일자"], g["거래시간"].to_numpy())
    out["mwh"], out["intensity"] = g.mwh.to_numpy(), (g.co2 / g.mwh).to_numpy()
    out["ratio"] = out.intensity / out.intensity.mean()
    return out


def marginal_ef(by=None):
    """marginal_ef = 한계 배출계수(tCO2/MWh). 새 수요가 늘 때 실제로 출력을 올리는 발전기의 배출. Hawkes 2010·Siler-Evans 2012 방식:
    시간마다 순부하(전체 - 태양광 - 풍력, 바람·햇빛은 수요에 맞춰 늘지 않으므로 뺌)의 변화 dNL과 배출 변화 dE를 dE = a + b x dNL로 회귀한 기울기 b.
    by(예: 'sea', 'band', ['sea', 'band'])로 나누면 묶음마다 따로 회귀한다. 연료원별 반응(dG_연료를 dNL에 회귀한 기울기, 합 1)도 같이 돌려준다.
    주의: 시장 발전기만, 연료원 평균 배출계수(같은 연료 안의 효율 차이 미반영), 양수·저장장치는 배출 0으로 둬서 그만큼 낮게 나올 수 있다. 1시간 차이는 하루 부하 곡선의 오르내림이 대부분이다."""
    f = pd.read_csv(DATA / FILES["fuel"], encoding="utf-8-sig")
    f["co2"] = f["전력거래량(MWh)"] * f["연료원별"].map(FUEL_EF).fillna(0.0)
    gen = f.pivot_table(index=["거래일자", "거래시간"], columns="연료원별", values="전력거래량(MWh)", aggfunc="sum").fillna(0.0).sort_index()
    co2 = f.groupby(["거래일자", "거래시간"]).co2.sum().reindex(gen.index)
    nl = gen.sum(axis=1) - gen.get("태양광", 0) - gen.get("풍력", 0)
    cal = _calendar(gen.index.get_level_values(0), gen.index.get_level_values(1).to_numpy())
    d = pd.DataFrame(dict(dE=co2.diff().to_numpy(), dNL=nl.diff().to_numpy()), index=cal.index).join(cal)
    dg = gen.diff().reset_index(drop=True)
    d, dg = d.iloc[1:], dg.iloc[1:]
    main = ["원자력", "유연탄", "LNG", "양수", "무연탄", "부생가스", "연료전지", "IGCC"]

    def fit(m):
        x, y = d.dNL[m], d.dE[m]
        b = float(np.cov(x, y)[0, 1] / x.var()); r2 = float(np.corrcoef(x, y)[0, 1] ** 2)
        share = {k: float(np.cov(x, dg.loc[m, k])[0, 1] / x.var()) for k in main if k in dg}
        return dict(mef=b, r2=r2, n=int(m.sum()), share=share)

    all_ = fit(pd.Series(True, index=d.index))
    if by is None:
        return all_
    keys = [by] if isinstance(by, str) else list(by)
    return {k if len(keys) > 1 else k[0]: fit((d[keys] == pd.Series(k, index=keys)).all(axis=1)) for k in d.groupby(keys).size().index.map(lambda v: v if isinstance(v, tuple) else (v,))}


def marginal_table(by="band"):
    """marginal_table = marginal_ef(by)를 표로. 묶음마다 한계 배출계수, 24시간 한계 대비 비율, 석탄·LNG·양수 반응 비율, R2(설명력)."""
    base, r = marginal_ef(), marginal_ef(by)
    return pd.DataFrame({k: dict(한계=v["mef"], 한계_비율=v["mef"] / base["mef"], 석탄=v["share"]["유연탄"], LNG=v["share"]["LNG"], 양수=v["share"]["양수"], R2=v["r2"]) for k, v in r.items()}).T


def marginal_scenario(official=0.4173, h2_output_mt=1.0):
    """marginal_scenario = 계산기(h2_supply)를 평균 배출계수(공식값)와 한계 배출계수(공식값 x 한계/평균)로 각각 돌린 비교표.
    전력망 수소의 1t당 순 저감, 그린으로 바꾸는 손익분기 탄소 가격, 추천. 한계/평균 비율은 2025 시장 발전기 기준."""
    from src.hydrogen import h2_supply  # hydrogen이 이 모듈을 부르지 않지만 무거운 계산은 필요할 때만 불러온다
    g = hourly_grid()
    gf_m = official * marginal_ef()["mef"] / float((g.intensity * g.mwh).sum() / g.mwh.sum())
    row = lambda r: dict(배출계수=r["applied_input"]["grid_factor"], 전력망_1t당_순저감=r["thresholds"]["max_grid_abate_per_t"],
                         손익분기_탄소가격=r["thresholds"]["ets_breakeven"], 고로_손익분기=r["thresholds"]["gf_breakeven_bf"], 추천=r["verdict"]["pick"])
    return pd.DataFrame({"평균 기준(지금 계산기)": row(h2_supply(h2_output_mt, grid_factor=official)),
                         "한계 기준": row(h2_supply(h2_output_mt, grid_factor=round(gf_m, 4)))}).T


def fuel_share():
    """fuel_share = 2025 연료원별 연간 전력거래량 비중(%), 큰 순서."""
    f = pd.read_csv(DATA / FILES["fuel"], encoding="utf-8-sig")
    s = f.groupby("연료원별")["전력거래량(MWh)"].sum().sort_values(ascending=False)
    return s / s.sum() * 100


def ets_series(since=None):
    """ets_series = ICAP 일별 탄소 가격(원/tCO2) 표. 열 kets(K-ETS 2차 시장), euets(EU ETS를 같은 날 원/유로 환산, 거래일이 다르면 직전 환율). since(날짜) 이후만."""
    d = {x["id"]: x for x in json.loads((DATA / FILES["icap"]).read_text(encoding="utf-8"))}
    k = pd.DataFrame.from_dict(d[8]["values"]["secondary"], orient="index", columns=["usd", "eur", "krw"]).astype(float)
    e = pd.DataFrame.from_dict(d[34]["values"]["secondary"], orient="index", columns=["usd", "eur", "local"]).astype(float)
    k.index, e.index = pd.to_datetime(k.index), pd.to_datetime(e.index)
    fx = (k.krw / k.eur).reindex(e.index, method="ffill")
    out = pd.concat([k.krw.rename("kets"), (e.eur * fx).rename("euets")], axis=1).sort_index()
    return out if since is None else out[out.index >= since]


def data_checks():
    """data_checks = 외부 데이터 품질 점검표. 파일마다 빈칸, (일자·시각·항목) 중복, 8,760시간이 다 차지 않은 항목, 음수 거래량, EPSIS의 '0 = 통계 없음' 연도."""
    rows = []
    for key, cols in (("fuel", ["거래일자", "거래시간", "연료원별"]), ("re_cap", ["거래일자", "시간", "연료원"])):
        f = pd.read_csv(DATA / FILES[key], encoding="utf-8-sig")
        cov = f.groupby(cols[2]).size()
        neg = f[f["전력거래량(MWh)"] < 0].groupby(cols[2])["전력거래량(MWh)"].agg(["count", "sum"])
        rows.append(dict(파일=FILES[key], 빈칸=int(f.isna().sum().sum()), 중복=int(f.duplicated(cols).sum()), 시각수=int(f.groupby(cols[:2]).ngroups),
                         시간_빠진_항목={k: int(v) for k, v in cov[cov < 8760].items()}, 음수={k: f"{int(r['count'])}건, 합 {r['sum']:.1f} MWh" for k, r in neg.iterrows()}))
    sp = {int(r["year"]): r.get("산업용") for r in json.loads((DATA / FILES["sales"]).read_text(encoding="utf-8"))["rows"]}
    rows.append(dict(파일=FILES["sales"], 빈칸=sum(v is None for v in sp.values()), 중복=0, 시각수=None, 시간_빠진_항목={}, 음수={},
                     통계_없음_연도=f"산업용 0: {min(y for y, v in sp.items() if v == 0)}~{max(y for y, v in sp.items() if v == 0)}"))
    return pd.DataFrame(rows).set_index("파일")


def tou_ratio(g=None):
    """tou_ratio = 요금시간대별 배출계수 비율. 그 시간대에만 일정하게 쓰는 부하의 평균 집약도 / 24시간 일정 부하의 평균. 경부하만 돌리는 수전해 배출 = 계수 x ratio['경']."""
    g = hourly_grid() if g is None else g
    return {b: float(g.loc[g.band == b, "ratio"].mean()) for b in ("경", "중", "최")}


def re_profiles():
    """re_profiles = 2025 시간별 태양광·풍력 이용률(발전량 / 설비용량, 시장 참여 설비 전국 합). 8,760행, 열은 solar, wind, 달력."""
    r = pd.read_csv(DATA / FILES["re_cap"], encoding="utf-8-sig")
    r = r[r["연료원"].isin(["태양광", "풍력"])].copy()
    r["h"] = r["시간"].str.slice(0, 2).astype(int)
    p = r.pivot_table(index=["거래일자", "h"], columns="연료원", values=["전력거래량(MWh)", "설비용량"], aggfunc="sum").sort_index()
    cf = (p["전력거래량(MWh)"] / p["설비용량"]).rename(columns={"태양광": "solar", "풍력": "wind"}).reset_index()
    cal = _calendar(cf["거래일자"], cf["h"].to_numpy())
    return pd.concat([cal, cf[["solar", "wind"]]], axis=1)


def hourly_match(profile, ratio, k=1.0):
    """hourly_match = 시간 일치율. 24시간 일정한 수전해 부하(1)를 재생에너지 profile로 맞출 때, 연간 재생 발전량 = k x 연간 부하가 되게 키운다.
    share = 같은 시간에 재생으로 채운 부하 비율, surplus = 그 시간에 못 쓰고 남는 재생 비율(저장·판매 필요), backfill_ratio = 모자란 시간에 산 전력망 배출계수 / 연평균,
    storage_h = 저장 손실 없이 100% 시간 일치에 필요한 저장 용량(부하 몇 시간분, k=1 기준)."""
    p = np.asarray(profile, float); w = np.asarray(ratio, float)
    s = k * p / p.mean()
    used = np.minimum(s, 1.0); gap = 1.0 - used
    cum = np.cumsum(p / p.mean() - 1.0)
    return dict(share=float(used.mean()), surplus=float((s - used).sum() / s.sum()), backfill_ratio=float((gap * w).sum() / gap.sum()) if gap.sum() else 0.0,
                storage_h=float(cum.max() - cum.min()))


def match_table(rp=None, g=None):
    """match_table = 태양광·풍력·반반(에너지 기준) 각각의 시간 일치 결과(k=1). 배출 비율은 같은 시각의 시간별 집약도를 쓴다."""
    rp = re_profiles() if rp is None else rp
    g = hourly_grid() if g is None else g
    m = rp.merge(g[["date", "h", "ratio"]], on=["date", "h"], how="left")
    mix = 0.5 * m.solar / m.solar.mean() + 0.5 * m.wind / m.wind.mean()
    return {"solar": dict(cf=float(m.solar.mean()), **hourly_match(m.solar, m.ratio)), "wind": dict(cf=float(m.wind.mean()), **hourly_match(m.wind, m.ratio)),
            "mix": dict(cf=None, **hourly_match(mix, m.ratio))}


def ets_stats(since="2025-11-10"):
    """ets_stats = ICAP 탄소 가격 통계(원/tCO2). K-ETS 2차 시장 가격(원)과 EU ETS(유로를 같은 날 K-ETS의 원/유로 환산으로 원화로). since 이후의 최저·최고·평균·마지막 값."""
    d = json.loads((DATA / FILES["icap"]).read_text(encoding="utf-8"))
    sys_ = {s["id"]: s for s in d}
    k = pd.DataFrame.from_dict(sys_[8]["values"]["secondary"], orient="index", columns=["usd", "eur", "krw"]).astype(float)
    e = pd.DataFrame.from_dict(sys_[34]["values"]["secondary"], orient="index", columns=["usd", "eur", "local"]).astype(float)
    k.index, e.index = pd.to_datetime(k.index), pd.to_datetime(e.index)
    fx = (k.krw / k.eur).reindex(e.index, method="ffill")                  # 원/유로 (ICAP 환산 비율)
    e["krw"] = e.eur * fx
    pick = lambda s: dict(min=float(s.min()), max=float(s.max()), mean=float(s.mean()), last=float(s.iloc[-1]), last_date=str(s.index[-1].date()), n=int(len(s)))
    return dict(kets=pick(k.krw[k.index >= since]), euets=pick(e.krw[e.index >= since].dropna()), kets_all=pick(k.krw))


def sales_price(use="산업용"):
    """sales_price = EPSIS 연도별 판매단가(원/kWh). {연도: 값}."""
    d = json.loads((DATA / FILES["sales"]).read_text(encoding="utf-8"))
    return {int(r["year"]): r[use] for r in d["rows"] if r.get(use)}
