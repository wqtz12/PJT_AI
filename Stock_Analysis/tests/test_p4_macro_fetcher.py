"""
P4 테스트: 거시경제 지표 수집 모듈
- _compute_trend() 추세 판단
- _classify_vix_level() VIX 분류
- _fetch_single_indicator() 단일 지표 (mocked)
- fetch_macro_indicators() 전체 수집 (mocked)
- compute_macro_summary() 환경 종합 판단
- enrich_company_info_with_macro() 주입
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from macro_fetcher import (
    _compute_trend, _classify_vix_level, _fetch_single_indicator,
    fetch_macro_indicators, compute_macro_summary, enrich_company_info_with_macro,
)


# ─── _compute_trend() ───

class TestComputeTrend:
    def test_uptrend(self):
        s = pd.Series([10, 10.5, 11, 11.5, 12, 12.5])
        assert _compute_trend(s, window=5) == "상승"

    def test_downtrend(self):
        s = pd.Series([12, 11.5, 11, 10.5, 10, 9.5])
        assert _compute_trend(s, window=5) == "하락"

    def test_stable(self):
        s = pd.Series([10, 10.01, 9.99, 10.02, 10, 10.01])
        assert _compute_trend(s, window=5) == "안정"

    def test_short_series(self):
        s = pd.Series([10, 11])
        assert _compute_trend(s, window=5) == "안정"

    def test_empty_series(self):
        s = pd.Series([], dtype=float)
        assert _compute_trend(s) == "안정"


# ─── _classify_vix_level() ───

class TestClassifyVixLevel:
    def test_low(self):
        assert _classify_vix_level(12.0) == "저변동"

    def test_normal(self):
        assert _classify_vix_level(18.0) == "보통"

    def test_elevated(self):
        assert _classify_vix_level(23.0) == "경계"

    def test_high(self):
        assert _classify_vix_level(30.0) == "고변동"

    def test_extreme(self):
        assert _classify_vix_level(40.0) == "극단"

    def test_boundary_low(self):
        assert _classify_vix_level(15.0) == "저변동"

    def test_boundary_high(self):
        assert _classify_vix_level(35.0) == "고변동"


# ─── _fetch_single_indicator() (mocked) ───

class TestFetchSingleIndicator:
    def _mock_history(self, values):
        dates = pd.date_range("2024-01-01", periods=len(values), freq="B")
        return pd.DataFrame({"Close": values, "Open": values, "High": values,
                             "Low": values, "Volume": [1000]*len(values)}, index=dates)

    @patch("macro_fetcher.yf.Ticker")
    def test_returns_dict_on_success(self, mock_ticker):
        mock_ticker.return_value.history.return_value = self._mock_history([100, 101, 102, 103, 104])
        result = _fetch_single_indicator("^GSPC", "S&P 500")
        assert result is not None
        assert "current" in result
        assert "change_pct" in result
        assert "avg_20d" in result
        assert "trend" in result

    @patch("macro_fetcher.yf.Ticker")
    def test_returns_none_on_failure(self, mock_ticker):
        mock_ticker.return_value.history.side_effect = Exception("Network error")
        result = _fetch_single_indicator("^GSPC", "S&P 500")
        assert result is None

    @patch("macro_fetcher.yf.Ticker")
    def test_returns_none_on_empty(self, mock_ticker):
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        result = _fetch_single_indicator("^GSPC", "S&P 500")
        assert result is None

    @patch("macro_fetcher.yf.Ticker")
    def test_vix_has_level(self, mock_ticker):
        mock_ticker.return_value.history.return_value = self._mock_history([18, 19, 20, 21, 22])
        result = _fetch_single_indicator("^VIX", "VIX")
        assert result is not None
        assert "level" in result

    @patch("macro_fetcher.yf.Ticker")
    def test_non_vix_no_level(self, mock_ticker):
        mock_ticker.return_value.history.return_value = self._mock_history([100, 101, 102, 103, 104])
        result = _fetch_single_indicator("^GSPC", "S&P 500")
        assert result is not None
        assert "level" not in result


# ─── fetch_macro_indicators() (mocked) ───

class TestFetchMacroIndicators:
    @patch("macro_fetcher._fetch_single_indicator")
    def test_returns_all_keys(self, mock_fetch):
        mock_fetch.return_value = {"current": 100, "change_pct": 0.5, "avg_20d": 99, "trend": "상승"}
        result = fetch_macro_indicators()
        assert "_fetch_time" in result
        assert "_available_count" in result
        assert result["_available_count"] == 6

    @patch("macro_fetcher._fetch_single_indicator")
    def test_partial_failure(self, mock_fetch):
        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 3:
                return {"current": 100, "change_pct": 0, "avg_20d": 100, "trend": "안정"}
            return None
        mock_fetch.side_effect = side_effect
        result = fetch_macro_indicators()
        assert result["_available_count"] == 3

    @patch("macro_fetcher._fetch_single_indicator")
    def test_total_failure(self, mock_fetch):
        mock_fetch.return_value = None
        result = fetch_macro_indicators()
        assert result["_available_count"] == 0


# ─── compute_macro_summary() ───

class TestComputeMacroSummary:
    def test_empty_returns_neutral(self):
        result = compute_macro_summary({})
        assert result["시장_환경"] == "판단 불가"
        assert result["환경_점수"] == 0

    def test_none_returns_neutral(self):
        result = compute_macro_summary(None)
        assert result["시장_환경"] == "판단 불가"

    def test_risk_on(self):
        """저VIX + S&P상승 + 금리하락 = 위험선호"""
        data = {
            "vix": {"current": 12, "level": "저변동", "trend": "하락"},
            "sp500": {"current": 5500, "trend": "상승"},
            "treasury_10y": {"current": 3.5, "trend": "하락"},
            "dollar": {"current": 100, "trend": "하락"},
            "gold": {"current": 2000, "trend": "하락"},
            "_available_count": 5,
        }
        result = compute_macro_summary(data)
        assert result["시장_환경"] == "위험선호"
        assert result["환경_점수"] > 0

    def test_risk_off(self):
        """고VIX + S&P하락 + 금리상승 = 위험회피"""
        data = {
            "vix": {"current": 32, "level": "고변동", "trend": "상승"},
            "sp500": {"current": 4500, "trend": "하락"},
            "treasury_10y": {"current": 5.0, "trend": "상승"},
            "dollar": {"current": 110, "trend": "상승"},
            "gold": {"current": 2100, "trend": "상승"},
            "_available_count": 5,
        }
        result = compute_macro_summary(data)
        assert result["시장_환경"] == "위험회피"
        assert result["환경_점수"] < 0

    def test_score_clamped(self):
        """환경 점수 -5 ~ +5 범위 제한"""
        data = {
            "vix": {"current": 10, "level": "저변동"},
            "sp500": {"current": 5500, "trend": "상승"},
            "treasury_10y": {"current": 3.0, "trend": "하락"},
            "dollar": {"current": 95, "trend": "하락"},
            "gold": {"current": 1800, "trend": "하락"},
            "_available_count": 5,
        }
        result = compute_macro_summary(data)
        assert -5 <= result["환경_점수"] <= 5

    def test_has_all_keys(self):
        data = {
            "vix": {"current": 20, "level": "보통"},
            "sp500": {"current": 5000, "trend": "안정"},
            "_available_count": 2,
        }
        result = compute_macro_summary(data)
        for key in ("시장_환경", "환경_점수", "VIX_상태", "금리_방향", "달러_방향", "시장_추세"):
            assert key in result


# ─── enrich_company_info_with_macro() ───

class TestEnrichCompanyInfo:
    def test_adds_macro_key(self):
        info = {"이름": "Test"}
        macro = {
            "vix": {"current": 20, "level": "보통"},
            "sp500": {"current": 5000, "trend": "안정"},
            "_available_count": 2,
        }
        result = enrich_company_info_with_macro(info, macro)
        assert "_macro" in result

    def test_none_macro_no_change(self):
        info = {"이름": "Test"}
        result = enrich_company_info_with_macro(info, None)
        assert "_macro" not in result

    def test_empty_count_no_change(self):
        info = {"이름": "Test"}
        result = enrich_company_info_with_macro(info, {"_available_count": 0})
        assert "_macro" not in result

    def test_preserves_existing_keys(self):
        info = {"이름": "Test", "섹터": "Tech"}
        macro = {"vix": {"current": 20, "level": "보통"}, "_available_count": 1}
        result = enrich_company_info_with_macro(info, macro)
        assert result["이름"] == "Test"
        assert result["섹터"] == "Tech"

    def test_macro_has_vix(self):
        info = {}
        macro = {"vix": {"current": 25, "level": "경계"}, "_available_count": 1}
        enrich_company_info_with_macro(info, macro)
        assert info["_macro"]["vix"]["current"] == 25

    def test_macro_has_environment(self):
        info = {}
        macro = {"vix": {"current": 20, "level": "보통"}, "_available_count": 1}
        enrich_company_info_with_macro(info, macro)
        assert "환경_점수" in info["_macro"]
        assert "시장_환경" in info["_macro"]
