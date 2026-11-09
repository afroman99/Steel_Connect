"""전력배출계수 연도별 값과 추세 시나리오. 값은 기후에너지환경부 보도자료(2025-12-18) 그림의 라벨을 읽은 것이다."""

import numpy as np
import pandas as pd

# fmt: off
# 소비단 전력배출계수 (tCO2eq/MWh). 2023만 확정값, 2010~2022 단년도는 참고용 산출(공식 3년 평균 0.4541과 기준이 다름). 2021~23 평균 0.4330과 일치하는지로 라벨 판독을 검산함
GRID = pd.Series([0.5439, 0.5435, 0.5401, 0.5515, 0.5177, 0.5167, 0.5037, 0.5151, 0.5404, 0.5060, 0.4484, 0.4509, 0.4312, 0.4173], index=range(2010, 2024), name="grid_factor")


def trend(start=2010):
    """trend = 추세. start년부터 2023년까지 직선을 맞춰 연간 변화(기울기)와 95% 신뢰구간, 데이터 점 수를 돌려준다. 점이 적어 신뢰구간이 넓다."""
    y = GRID.loc[start:]; x = y.index.values.astype(float)
    b, a = np.polyfit(x, y.values, 1)
    n = len(y); se = np.sqrt(((y.values - (a + b * x)) ** 2).sum() / (n - 2) / ((x - x.mean()) ** 2).sum())
    t = {4: 2.776, 12: 2.179}.get(n - 2, 2.0)  # t 분포 95% 임계값 (표본 6개, 14개일 때)
    return dict(slope=b, lo=b - t * se, hi=b + t * se, n=n, intercept=a)


def scenario(year, kind, floor=0.15):
    """scenario = 전력배출계수 시나리오(예측이 아니라 범위). kind: '정체'(2023 유지), '14년 추세'(2010~2023 직선), '최근 5년 속도'(2018 정점→2023, 정점 기준이라 낙관 쪽 상한). floor 아래로는 내려가지 않게 자른다."""
    g23, k = GRID.loc[2023], year - 2023
    v = {"정체": g23, "14년 추세": g23 + trend(2010)["slope"] * k, "최근 5년 속도": g23 + (GRID.loc[2023] - GRID.loc[2018]) / 5 * k}[kind]
    return max(v, floor)
