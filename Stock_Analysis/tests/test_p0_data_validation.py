"""
P0-1 테스트: 데이터 충분성 검증 (data_fetcher.py)
- validate_dataframe 함수 검증
- 최소 행 수, NaN 비율, 필수 컬럼, 데이터 기간 검증
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_fetcher import (
    validate_dataframe,
    InsufficientDataError,
    DataQualityWarning,
    _safe_numeric,
    MIN_ROWS,
    REQUIRED_COLUMNS,
    MAX_NAN_RATIO,
)


# ─── 헬퍼: 테스트용 DataFrame 생성 ───

def make_ohlcv(rows: int = 100, start_date: str = "2024-01-01",
               nan_cols: dict = None, zero_volume_ratio: float = 0.0) -> pd.DataFrame:
    """테스트용 OHLCV DataFrame 생성"""
    dates = pd.bdate_range(start=start_date, periods=rows)
    np.random.seed(42)
    base_price = 10.0
    prices = base_price + np.cumsum(np.random.randn(rows) * 0.3)
    prices = np.maximum(prices, 0.5)  # 음수 방지

    df = pd.DataFrame({
        "Open": prices + np.random.randn(rows) * 0.1,
        "High": prices + abs(np.random.randn(rows) * 0.3),
        "Low": prices - abs(np.random.randn(rows) * 0.3),
        "Close": prices,
        "Volume": np.random.randint(100000, 10000000, size=rows).astype(float),
    }, index=dates)

    # NaN 주입
    if nan_cols:
        for col, ratio in nan_cols.items():
            nan_count = int(rows * ratio)
            idx = np.random.choice(rows, nan_count, replace=False)
            df.iloc[idx, df.columns.get_loc(col)] = np.nan

    # 거래량 0 주입
    if zero_volume_ratio > 0:
        zero_count = int(rows * zero_volume_ratio)
        idx = np.random.choice(rows, zero_count, replace=False)
        df.iloc[idx, df.columns.get_loc("Volume")] = 0

    return df


# ─── 테스트 케이스 ───

class TestValidateDataframe:
    """validate_dataframe 함수 테스트"""

    def test_valid_data(self):
        """정상 데이터 → valid=True, 에러/경고 없음"""
        df = make_ohlcv(rows=100)
        result = validate_dataframe(df, "TEST", "6mo")
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_empty_dataframe(self):
        """빈 DataFrame → valid=False"""
        df = pd.DataFrame()
        result = validate_dataframe(df, "TEST", "6mo")
        assert result["valid"] is False
        assert any("비어있" in e for e in result["errors"])

    def test_missing_required_columns(self):
        """필수 컬럼 누락 → valid=False"""
        df = make_ohlcv(rows=50)
        df = df.drop(columns=["Volume"])
        result = validate_dataframe(df, "TEST", "6mo")
        assert result["valid"] is False
        assert any("필수 컬럼 누락" in e for e in result["errors"])

    def test_insufficient_rows_6mo(self):
        """6개월 기간에 행 수 부족 → valid=False"""
        df = make_ohlcv(rows=30)  # 6mo 최소 80행
        result = validate_dataframe(df, "TEST", "6mo")
        assert result["valid"] is False
        assert any("데이터 부족" in e for e in result["errors"])

    def test_sufficient_rows_6mo(self):
        """6개월 기간에 충분한 행 → valid=True"""
        df = make_ohlcv(rows=100)
        result = validate_dataframe(df, "TEST", "6mo")
        assert result["valid"] is True

    def test_min_rows_per_period(self):
        """각 기간별 최소 행 수 검증"""
        for period, min_row in MIN_ROWS.items():
            # 최소 미달
            df_short = make_ohlcv(rows=min_row - 5 if min_row > 5 else 1)
            result = validate_dataframe(df_short, "TEST", period)
            assert result["valid"] is False, f"{period}: {min_row - 5}행이 통과하면 안됨"

            # 최소 충족
            df_ok = make_ohlcv(rows=min_row + 10)
            result = validate_dataframe(df_ok, "TEST", period)
            assert result["valid"] is True, f"{period}: {min_row + 10}행이 실패하면 안됨"

    def test_high_nan_ratio_warning(self):
        """NaN 비율 > 10% → 경고 포함"""
        df = make_ohlcv(rows=100, nan_cols={"Close": 0.15})
        result = validate_dataframe(df, "TEST", "6mo")
        assert any("NaN 비율" in w for w in result["warnings"])

    def test_low_nan_ratio_no_warning(self):
        """NaN 비율 < 10% → 경고 없음"""
        df = make_ohlcv(rows=100, nan_cols={"Close": 0.05})
        result = validate_dataframe(df, "TEST", "6mo")
        assert not any("NaN 비율" in w for w in result["warnings"])

    def test_nan_report_stats(self):
        """NaN 리포트 통계 정확성"""
        df = make_ohlcv(rows=100, nan_cols={"Close": 0.20})
        result = validate_dataframe(df, "TEST", "6mo")
        nan_report = result["stats"]["nan_report"]
        assert "Close" in nan_report
        assert nan_report["Close"]["count"] == 20  # 100 * 0.20
        assert abs(nan_report["Close"]["ratio"] - 0.20) < 0.01

    def test_zero_volume_warning(self):
        """거래량 0 비율 > 20% → 경고"""
        df = make_ohlcv(rows=100, zero_volume_ratio=0.25)
        result = validate_dataframe(df, "TEST", "6mo")
        assert any("거래량 0" in w for w in result["warnings"])

    def test_zero_volume_no_warning(self):
        """거래량 0 비율 < 20% → 경고 없음"""
        df = make_ohlcv(rows=100, zero_volume_ratio=0.1)
        result = validate_dataframe(df, "TEST", "6mo")
        assert not any("거래량 0" in w for w in result["warnings"])

    def test_invalid_prices(self):
        """0 이하 종가 감지"""
        df = make_ohlcv(rows=100)
        df.iloc[5, df.columns.get_loc("Close")] = 0
        df.iloc[10, df.columns.get_loc("Close")] = -1.5
        result = validate_dataframe(df, "TEST", "6mo")
        assert any("유효하지 않은 종가" in w for w in result["warnings"])
        assert result["stats"]["invalid_prices"] == 2

    def test_date_range_stats(self):
        """날짜 범위 통계 포함"""
        df = make_ohlcv(rows=100)
        result = validate_dataframe(df, "TEST", "6mo")
        assert "date_range_days" in result["stats"]
        assert "start_date" in result["stats"]
        assert "end_date" in result["stats"]


class TestSafeNumeric:
    """_safe_numeric 유틸리티 테스트"""

    def test_valid_int(self):
        assert _safe_numeric(42) == 42

    def test_valid_float(self):
        assert _safe_numeric(3.14) == 3.14

    def test_none(self):
        assert _safe_numeric(None) is None

    def test_nan(self):
        assert _safe_numeric(float("nan")) is None

    def test_inf(self):
        assert _safe_numeric(float("inf")) is None

    def test_string(self):
        assert _safe_numeric("N/A") is None

    def test_default(self):
        assert _safe_numeric(None, default=0) == 0

    def test_zero(self):
        assert _safe_numeric(0) == 0

    def test_negative(self):
        assert _safe_numeric(-5.5) == -5.5


class TestConstants:
    """상수 정의 검증"""

    def test_required_columns(self):
        assert "Open" in REQUIRED_COLUMNS
        assert "High" in REQUIRED_COLUMNS
        assert "Low" in REQUIRED_COLUMNS
        assert "Close" in REQUIRED_COLUMNS
        assert "Volume" in REQUIRED_COLUMNS

    def test_min_rows_6mo(self):
        assert MIN_ROWS["6mo"] >= 60  # 6개월 최소 60 거래일

    def test_max_nan_ratio(self):
        assert 0 < MAX_NAN_RATIO < 0.5  # 합리적 범위


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
