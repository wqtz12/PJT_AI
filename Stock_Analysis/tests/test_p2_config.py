"""
P2-1 테스트: config.yaml 분리 및 설정 로더
- config.yaml 로드/폴백 동작
- 딥 머지 로직
- 각 모듈이 config에서 값을 읽는지 검증
- config 변경 시 상수 반영 확인
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigLoader:
    """config.py 로더 기본 동작"""

    def test_get_config_returns_dict(self):
        from common.config import get_config
        cfg = get_config()
        assert isinstance(cfg, dict)

    def test_config_has_all_sections(self):
        from common.config import get_config
        cfg = get_config()
        expected_sections = ["defaults", "data", "indicators", "thresholds", "confidence", "sentiment", "chart", "report"]
        for section in expected_sections:
            assert section in cfg, f"섹션 누락: {section}"

    def test_defaults_section(self):
        from common.config import get_config
        cfg = get_config()
        d = cfg["defaults"]
        assert "ticker" in d
        assert "period" in d
        assert "output_dir" in d
        assert "log_level" in d

    def test_data_section_min_rows(self):
        from common.config import get_config
        cfg = get_config()
        mr = cfg["data"]["min_rows"]
        assert mr["6mo"] == 80
        assert mr["1y"] == 180

    def test_indicators_section(self):
        from common.config import get_config
        cfg = get_config()
        ind = cfg["indicators"]
        assert ind["rsi_window"] == 14
        assert ind["bb_window"] == 20
        assert ind["adx_window"] == 14
        assert 5 in ind["sma_windows"]
        assert 120 in ind["sma_windows"]

    def test_thresholds_rsi(self):
        from common.config import get_config
        cfg = get_config()
        rsi = cfg["thresholds"]["rsi"]
        assert rsi["overbought"] == 70
        assert rsi["oversold"] == 30

    def test_confidence_section(self):
        from common.config import get_config
        cfg = get_config()
        c = cfg["confidence"]
        assert c["max"] == 90
        assert c["no_data"] == 10
        assert c["base_buy"] == 50

    def test_sentiment_keywords(self):
        from common.config import get_config
        cfg = get_config()
        s = cfg["sentiment"]
        assert "surge" in s["positive_keywords"]
        assert "drop" in s["negative_keywords"]

    def test_chart_section(self):
        from common.config import get_config
        cfg = get_config()
        ch = cfg["chart"]
        assert ch["dpi"] == 150
        assert "candle_up" in ch
        assert "candle_down" in ch


class TestDeepMerge:
    """딥 머지 동작 검증"""

    def test_simple_override(self):
        from common.config import _deep_merge
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 99

    def test_nested_override(self):
        from common.config import _deep_merge
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 99}}
        result = _deep_merge(base, override)
        assert result["x"]["a"] == 1
        assert result["x"]["b"] == 99

    def test_new_key_added(self):
        from common.config import _deep_merge
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_base_not_modified(self):
        from common.config import _deep_merge
        base = {"a": {"b": 1}}
        override = {"a": {"b": 99}}
        _deep_merge(base, override)
        assert base["a"]["b"] == 1  # 원본 불변


class TestConfigFallback:
    """config.yaml 없을 때 폴백 동작"""

    def teardown_method(self):
        """테스트 후 config 캐시 복원"""
        from common.config import reload_config
        reload_config()

    def test_load_nonexistent_file(self):
        from common.config import load_config
        cfg = load_config("/tmp/nonexistent_config_12345.yaml")
        assert isinstance(cfg, dict)
        assert "defaults" in cfg

    def test_fallback_values_match_defaults(self):
        from common.config import load_config, _DEFAULTS
        cfg = load_config("/tmp/nonexistent_config_12345.yaml")
        assert cfg["defaults"]["period"] == _DEFAULTS["defaults"]["period"]
        assert cfg["confidence"]["max"] == _DEFAULTS["confidence"]["max"]


class TestConfigYamlLoad:
    """실제 config.yaml 파일 로드 검증"""

    def test_config_yaml_exists(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )
        assert os.path.exists(config_path), "config.yaml 파일이 존재해야 함"

    def test_config_yaml_parseable(self):
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "defaults" in data

    def test_reload_config(self):
        from common.config import reload_config
        cfg = reload_config()
        assert isinstance(cfg, dict)
        assert "thresholds" in cfg


class TestConstantsFromConfig:
    """constants.py 상수가 config 값과 일치하는지 검증"""

    def test_rsi_constants_match_config(self):
        from common.config import get_config
        from common.constants import RSI_OVERBOUGHT, RSI_OVERSOLD
        cfg = get_config()
        assert RSI_OVERBOUGHT == cfg["thresholds"]["rsi"]["overbought"]
        assert RSI_OVERSOLD == cfg["thresholds"]["rsi"]["oversold"]

    def test_confidence_constants_match_config(self):
        from common.config import get_config
        from common.constants import CONFIDENCE_MAX, CONFIDENCE_NO_DATA
        cfg = get_config()
        assert CONFIDENCE_MAX == cfg["confidence"]["max"]
        assert CONFIDENCE_NO_DATA == cfg["confidence"]["no_data"]

    def test_adx_constants_match_config(self):
        from common.config import get_config
        from common.constants import ADX_STRONG, ADX_MODERATE
        cfg = get_config()
        assert ADX_STRONG == cfg["thresholds"]["adx"]["strong"]
        assert ADX_MODERATE == cfg["thresholds"]["adx"]["moderate"]

    def test_score_constants_match_config(self):
        from common.config import get_config
        from common.constants import SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD
        cfg = get_config()
        assert SCORE_BUY_THRESHOLD == cfg["thresholds"]["score"]["buy_threshold"]
        assert SCORE_SELL_THRESHOLD == cfg["thresholds"]["score"]["sell_threshold"]


class TestModulesUseConfig:
    """각 모듈이 config에서 설정을 읽는지 검증"""

    def test_data_fetcher_imports_config(self):
        import data_fetcher
        source = open(data_fetcher.__file__).read()
        assert "from common.config import" in source

    def test_technical_analysis_imports_config(self):
        import technical_analysis
        source = open(technical_analysis.__file__).read()
        assert "from common.config import" in source

    def test_scraper_adapter_imports_config(self):
        import scraper_adapter
        source = open(scraper_adapter.__file__).read()
        assert "from common.config import" in source

    def test_constants_imports_config(self):
        import common.constants
        source = open(common.constants.__file__).read()
        assert "from common.config import" in source

    def test_data_fetcher_min_rows_from_config(self):
        from common.config import get_config
        import data_fetcher
        cfg = get_config()
        assert data_fetcher.MIN_ROWS["6mo"] == cfg["data"]["min_rows"]["6mo"]

    def test_data_fetcher_max_nan_ratio_from_config(self):
        from common.config import get_config
        import data_fetcher
        cfg = get_config()
        assert data_fetcher.MAX_NAN_RATIO == cfg["data"]["max_nan_ratio"]


class TestCustomYamlOverride:
    """커스텀 yaml로 값 오버라이드 검증"""

    def teardown_method(self):
        """테스트 후 config 캐시 복원 (다른 테스트에 영향 방지)"""
        from common.config import reload_config
        reload_config()

    def test_override_rsi_threshold(self):
        import yaml
        from common.config import load_config

        custom = {"thresholds": {"rsi": {"overbought": 80}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(custom, f)
            tmp_path = f.name

        try:
            cfg = load_config(tmp_path)
            # 오버라이드된 값
            assert cfg["thresholds"]["rsi"]["overbought"] == 80
            # 나머지는 기본값 유지
            assert cfg["thresholds"]["rsi"]["oversold"] == 30
            assert cfg["confidence"]["max"] == 90
        finally:
            os.unlink(tmp_path)

    def test_override_confidence(self):
        import yaml
        from common.config import load_config

        custom = {"confidence": {"max": 95, "no_data": 5}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(custom, f)
            tmp_path = f.name

        try:
            cfg = load_config(tmp_path)
            assert cfg["confidence"]["max"] == 95
            assert cfg["confidence"]["no_data"] == 5
            # 나머지는 기본값 유지
            assert cfg["confidence"]["base_buy"] == 50
        finally:
            os.unlink(tmp_path)

    def test_add_new_sentiment_keyword(self):
        import yaml
        from common.config import load_config

        custom = {"sentiment": {"positive_keywords": ["surge", "rally", "moon"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(custom, f)
            tmp_path = f.name

        try:
            cfg = load_config(tmp_path)
            # 오버라이드로 리스트 전체 교체됨
            assert "moon" in cfg["sentiment"]["positive_keywords"]
        finally:
            os.unlink(tmp_path)
