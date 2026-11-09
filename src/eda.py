"""EDA(탐색적 데이터 분석) 함수: 데이터 목록, 품질 점검(결측·숨은 결측), UCI 부하 요약, 공식 요금시간대와의 일치, Factbook 파생 지표, 히트맵 그리기.
analysis/00_EDA.ipynb가 부른다. 외부 데이터(전력거래소·ICAP·EPSIS) 계산은 src/ext_data.py에 있다.
실행: 프로젝트 루트에서 python -m src.eda  (요약 출력)
주의: UCI는 광양 소규모 사업장(2018) 자료라 포스코 제철소를 대표하지 않는다. 결과는 예측이 아니라 시나리오의 근거다.
"""

from pathlib import Path

import pandas as pd

from src.load_profile import load_uci, tou_band

# fmt: off
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UCI = DATA / "Steel_industry_data.csv"
GIT_EXCLUDED = {"icap_systems.json"}  # ICAP 약관상 재배포 금지라 git 제외(.gitignore)
LABEL = {"Light_Load": "경", "Medium_Load": "중", "Maximum_Load": "최"}  # UCI Load_Type -> 요금시간대
SEASONS = ("여름", "봄가을", "겨울")


def read_csv(path):
    """read_csv = CSV 읽기. data/의 CSV는 모두 UTF-8(BOM)이다(전력거래소 원본 CP949는 받은 뒤 변환)."""
    return pd.read_csv(path, encoding="utf-8-sig")


def inventory(data=DATA):
    """inventory = 데이터 목록. data/의 CSV와 데이터셋 JSON(epsis_*, icap_*)마다 크기(MB)·행 수·git 추적 여부."""
    rows = []
    for f in sorted(data.glob("*.csv")) + sorted(data.glob("*.json")):
        if f.suffix == ".json" and not f.name.startswith(("epsis_", "icap_")):
            continue
        rows.append(dict(파일=f.name, 크기_MB=round(f.stat().st_size / 2**20, 2), 행=len(read_csv(f)) if f.suffix == ".csv" else None,
                         git="제외" if f.name in GIT_EXCLUDED else "추적"))
    return pd.DataFrame(rows).astype({"행": "Int64"})


def quality(df, key=None):
    """quality = 열별 품질 점검표. 결측 수, 0 비율(%), 음수 수, 고유값 수, 최솟값·최댓값. key(열 이름 또는 목록)를 주면 그 조합의 중복 행 수를 attrs['중복']에 담는다."""
    num = df.select_dtypes("number")
    out = pd.DataFrame(dict(결측=df.isna().sum(), 고유값=df.nunique()))
    out["0비율_%"] = (num == 0).mean().mul(100).round(1)
    out["음수"] = (num < 0).sum()
    out["최솟값"], out["최댓값"] = num.min(), num.max()
    if key is not None:
        out.attrs["중복"] = int(df.duplicated(key).sum())
    return out


def hidden_missing_uci(raw):
    """hidden_missing_uci = UCI에서 빈칸은 아니지만 결측처럼 봐야 할 값. 사용량 0, CO2 0(0.01 t 반올림), 지상역률 0, 진상역률 100(진상 무효전력 0일 때 정의상 100)."""
    checks = {"사용량 0 kWh": raw.Usage_kWh == 0, "CO2 = 0 (반올림)": raw["CO2(tCO2)"] == 0,
              "지상역률 = 0": raw.Lagging_Current_Power_Factor == 0, "진상역률 = 100 (정의상)": raw.Leading_Current_Power_Factor == 100}
    return pd.DataFrame({k: dict(행=int(m.sum()), 비율_퍼센트=round(m.mean() * 100, 1)) for k, m in checks.items()}).T


def implied_co2_factor(raw):
    """implied_co2_factor = UCI CO2 열이 쓴 배출계수(tCO2/MWh) = CO2 합 / 사용량 합. 측정값이 아니라 사용량 x 고정 계수라는 근거."""
    return float(raw["CO2(tCO2)"].sum() / (raw.Usage_kWh.sum() / 1000))


def month_hour(d, col="kw", agg="mean"):
    """month_hour = 월(1~12) x 시각(0~23) 표. load_uci 결과처럼 t(시각)·h 열이 있는 표에서 col을 agg로 묶는다."""
    return d.groupby([d.t.dt.month, "h"])[col].agg(agg).unstack()


def label_agreement(d):
    """label_agreement = UCI 원본 시간대 라벨(2018, 경부하 23~09시)이 한전 공식 시간대와 같은 구간의 비율(0~1). 규칙별(2025 개편 전, B 2026 개편 후)."""
    return {rule: float((d.band == tou_band(d, rule)).mean()) for rule in ("2025", "B")}


def label_strings(d, day="평일"):
    """label_strings = 계절별 0~23시 시간대를 글자로 이어 붙인 표(경·중·최). UCI 라벨과 2026 공식(B)을 나란히 본다. day는 평일·토·휴일."""
    w, b = d[d.day == day], tou_band(d, "B")
    mode = lambda s: s.mode()[0]
    return pd.DataFrame({s: {"UCI 라벨": "".join(w[w.sea == s].groupby("h").band.agg(mode)),
                             "2026 공식": "".join(b[w[w.sea == s].index].groupby(w[w.sea == s].h).agg(mode))} for s in SEASONS}).T


def factbook(path=None):
    """factbook = 포스코 ESG Factbook 2024 표(src/posco_factbook.py가 PDF에서 뽑은 CSV)."""
    return read_csv(path or next(DATA.glob("*Factbook*.csv")))


def factbook_metrics(fb=None):
    """factbook_metrics = Factbook 파생 지표(연도별). 구매 전력(TWh = 전기 GJ / 3.6백만), Scope 2 / 구매 전력(tCO2/MWh),
    부생가스 / 직접에너지(%), 천연가스(백만 GJ), 조강 역산(Mt = Scope 1&2 / 집약도). 2022는 포항·광양 한정이라 경계가 다르다."""
    v = (factbook() if fb is None else fb).set_index("항목")[["2022", "2023", "2024"]]
    buy = v.loc["전기"] / 3.6e6
    return pd.DataFrame({"구매 전력 TWh": buy, "Scope 2 / 구매 전력 t/MWh": v.loc["간접 배출(Scope 2)"] / (buy * 1e6),
                         "부생가스 / 직접에너지 %": v.loc["부생가스"] / v.loc["직접에너지 사용량"] * 100, "천연가스 백만 GJ": v.loc["천연가스"] / 1e6,
                         "조강 역산 Mt": v.loc["직/간접 배출량(Scope 1&2)"] / v.loc["직/간접 배출량 집약도(조강생산량 기준, Scope 1&2)"] / 1e6}).T


def heatmap(ax, table, title="", cbar="", cmap="viridis", fmt=None):
    """heatmap = 표를 색 칸으로 그린다(matplotlib imshow). 행·열 이름을 눈금으로 쓰고, fmt(예: '{:.2f}')를 주면 칸마다 값을 적는다. 색 막대를 돌려준다."""
    im = ax.imshow(table.to_numpy(dtype=float), aspect="auto", cmap=cmap)
    ax.set_xticks(range(table.shape[1]), table.columns); ax.set_yticks(range(table.shape[0]), table.index)
    ax.set_title(title); ax.grid(False)
    if fmt:
        for i in range(table.shape[0]):
            for j in range(table.shape[1]):
                ax.text(j, i, fmt.format(table.iat[i, j]), ha="center", va="center", fontsize=8)
    return ax.figure.colorbar(im, ax=ax, label=cbar)


if __name__ == "__main__":
    raw, d = read_csv(UCI), load_uci(UCI)
    print("[데이터 목록]\n", inventory().to_string(index=False))
    print(f"[UCI] 결측 {int(raw.isna().sum().sum())}, 중복 시각 {int(raw.date.duplicated().sum())}, CO2 열 계수 {implied_co2_factor(raw):.4f} tCO2/MWh")
    print("[UCI 숨은 결측]\n", hidden_missing_uci(raw).to_string())
    print("[UCI 라벨과 공식 시간대 일치]", {k: f"{v * 100:.1f}%" for k, v in label_agreement(d).items()})
    print("[Factbook 지표]\n", factbook_metrics().round(3).to_string())
