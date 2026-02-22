"""
P2-2 테스트: 크로스 플랫폼 폰트 핸들링 + 차트 config 연동
- _find_korean_font() 동작 검증
- config에서 차트 설정 로드 검증
- 폰트 폴백 동작
- 차트 함수의 config 파라미터 사용 검증
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFindKoreanFont:
    """_find_korean_font() 동작 검증"""

    def test_returns_string(self):
        from visualizer import _find_korean_font
        result = _find_korean_font()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_not_empty_on_current_os(self):
        """현재 OS에서 어떤 폰트든 반환해야 함 (sans-serif 포함)"""
        from visualizer import _find_korean_font
        result = _find_korean_font()
        assert result is not None

    def test_font_applied_to_rcparams(self):
        """폰트가 matplotlib rcParams에 적용되었는지 확인"""
        import matplotlib.pyplot as plt
        # visualizer import 시 자동 적용됨
        import visualizer
        font_family = plt.rcParams["font.family"]
        assert len(font_family) > 0

    def test_unicode_minus_disabled(self):
        """axes.unicode_minus가 False인지 확인"""
        import matplotlib.pyplot as plt
        import visualizer
        assert plt.rcParams["axes.unicode_minus"] == False


class TestFontPlatformCoverage:
    """OS별 폰트 후보 커버리지 검증"""

    def test_macos_candidates_exist(self):
        """macOS 후보 폰트 경로가 코드에 포함되어 있는지"""
        import visualizer
        source = open(visualizer.__file__).read()
        assert "AppleGothic" in source
        assert "AppleSDGothicNeo" in source

    def test_windows_candidates_exist(self):
        """Windows 후보 폰트가 코드에 포함되어 있는지"""
        import visualizer
        source = open(visualizer.__file__).read()
        assert "malgun.ttf" in source
        assert "gulim.ttc" in source

    def test_linux_candidates_exist(self):
        """Linux 후보 폰트가 코드에 포함되어 있는지"""
        import visualizer
        source = open(visualizer.__file__).read()
        assert "NanumGothic.ttf" in source
        assert "NotoSansCJK" in source

    def test_fallback_sans_serif(self):
        """폴백이 sans-serif인지 확인"""
        import visualizer
        source = open(visualizer.__file__).read()
        assert 'return "sans-serif"' in source


class TestGetCurrentFont:
    """get_current_font() 디버깅 함수"""

    def test_returns_string(self):
        from visualizer import get_current_font
        result = get_current_font()
        assert isinstance(result, str)

    def test_matches_rcparams(self):
        """get_current_font()이 실제 적용된 폰트와 일치"""
        import matplotlib.pyplot as plt
        from visualizer import get_current_font
        font = get_current_font()
        # rcParams["font.family"]는 리스트 또는 문자열
        rc_family = plt.rcParams["font.family"]
        if isinstance(rc_family, list):
            assert font in rc_family
        else:
            assert font == rc_family


class TestChartConfigIntegration:
    """차트 설정이 config.yaml에서 로드되는지 검증"""

    def test_dpi_from_config(self):
        from visualizer import _DPI
        from common.config import get_config
        cfg = get_config()
        assert _DPI == cfg["chart"]["dpi"]

    def test_candlestick_figsize_from_config(self):
        from visualizer import _CANDLE_FIGSIZE
        from common.config import get_config
        cfg = get_config()
        assert _CANDLE_FIGSIZE == tuple(cfg["chart"]["candlestick_figsize"])

    def test_dashboard_figsize_from_config(self):
        from visualizer import _DASHBOARD_FIGSIZE
        from common.config import get_config
        cfg = get_config()
        assert _DASHBOARD_FIGSIZE == tuple(cfg["chart"]["dashboard_figsize"])

    def test_performance_figsize_from_config(self):
        from visualizer import _PERFORMANCE_FIGSIZE
        from common.config import get_config
        cfg = get_config()
        assert _PERFORMANCE_FIGSIZE == tuple(cfg["chart"]["performance_figsize"])

    def test_sma_colors_from_config(self):
        from visualizer import _SMA_COLORS
        from common.config import get_config
        cfg = get_config()
        assert _SMA_COLORS == cfg["chart"]["sma_colors"]

    def test_candle_colors_from_config(self):
        from visualizer import _CANDLE_UP, _CANDLE_DOWN
        from common.config import get_config
        cfg = get_config()
        assert _CANDLE_UP == cfg["chart"]["candle_up"]
        assert _CANDLE_DOWN == cfg["chart"]["candle_down"]


class TestVisualizerImports:
    """visualizer.py가 올바른 모듈을 import하는지"""

    def test_imports_config(self):
        import visualizer
        source = open(visualizer.__file__).read()
        assert "from common.config import" in source

    def test_no_hardcoded_font_path_only(self):
        """하드코딩된 폰트 경로만 사용하지 않고 크로스 플랫폼 탐색을 수행"""
        import visualizer
        source = open(visualizer.__file__).read()
        assert "sys.platform" in source
        assert "_find_korean_font" in source

    def test_mpf_rc_uses_found_font(self):
        """mplfinance rc가 감지된 폰트를 사용"""
        from visualizer import _mpf_rc, _font_name
        assert _mpf_rc["font.family"] == _font_name
        assert _mpf_rc["axes.unicode_minus"] == False
