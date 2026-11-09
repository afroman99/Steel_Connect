"""포스코 ESG Factbook(국문) PDF의 '항목 단위 2022 2023 2024' 표를 DataFrame/CSV로 뽑는 코드. pypdf 필요(pip install pypdf)."""

import re

import pandas as pd
import pypdf

# fmt: off
ROW = re.compile(r"^(.+?)\s+(GJ/ton|tCO2e/ton|GJ|tCO2e)\s+(\S+)\s+(\S+)\s+(\S+)$")  # 예: "천연가스 GJ 30,750,384 45,697,279 60,987,933"


def clean(item):
    """clean = 항목명 정리. 끝의 각주 번호(' 1)')만 지운다. 지웠을 때 괄호가 안 맞으면(예: '직접 배출(Scope 1)') 원래 이름을 유지한다."""
    t = re.sub(r"\s\d\)$", "", item)
    return t if t.count("(") == t.count(")") else item


def extract_rows(pdf, pages):
    """extract_rows = 표 행 추출. 지정한 쪽에서 (항목, 단위, 2022, 2023, 2024) 형태의 줄만 뽑아 쪽 번호와 함께 돌려준다. '-'는 결측(NaN)."""
    rows = []
    for p in pages:
        for line in pypdf.PdfReader(pdf).pages[p - 1].extract_text().splitlines():
            m = ROW.match(line.strip())
            if m:
                item, unit, *v = m.groups()
                vals = [float(x.replace(",", "")) if re.fullmatch(r"[\d,.]+", x) else float("nan") for x in v]
                rows.append([p, clean(item.strip()), unit, *vals])
    return pd.DataFrame(rows, columns=["쪽", "항목", "단위", "2022", "2023", "2024"])


if __name__ == "__main__":  # 프로젝트 루트에서: python3 -m src.posco_factbook (pypdf가 있는 파이썬으로)
    pdf = "data/근거_포스코_ESG_Factbook2024_국내사업장.pdf"
    df = extract_rows(pdf, [5, 6])
    df.to_csv("data/포스코_Factbook2024_국내_에너지·온실가스.csv", index=False, encoding="utf-8-sig")
    print(df.shape, df.groupby("쪽").size().to_dict())
