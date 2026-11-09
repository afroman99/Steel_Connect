"""matplotlib 한글 폰트 및 기본 스타일 설정."""
import platform

import matplotlib.pyplot as plt
from matplotlib import font_manager

# OS별로 먼저 시도할 한글 폰트 후보
_FONT_CANDIDATES = {
    "Darwin": ["AppleGothic", "Apple SD Gothic Neo"],
    "Windows": ["Malgun Gothic"],
    "Linux": ["NanumGothic", "Noto Sans CJK KR"],
}


def setup_korean_font(font: str | None = None) -> str:
    """한글 폰트를 설정하고 실제로 적용된 폰트 이름을 반환.

    font를 지정하지 않으면 OS에 맞는 후보 중 설치된 첫 번째 폰트를 쓴다.
    """
    installed = {f.name for f in font_manager.fontManager.ttflist}
    candidates = [font] if font else _FONT_CANDIDATES.get(platform.system(), [])
    chosen = next((name for name in candidates if name in installed), None)
    if chosen is None:
        raise RuntimeError(f"한글 폰트를 찾지 못했습니다. 후보: {candidates}")

    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False  # 음수 부호 깨짐 방지
    plt.rcParams["figure.figsize"] = (8, 4)
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    return chosen
