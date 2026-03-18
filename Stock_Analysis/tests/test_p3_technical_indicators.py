"""
P3-2 테스트: 기술적 분석 개별 지표 검증
- add_moving_averages(), add_rsi(), add_macd(), add_bollinger_bands()
- add_stochastic(), add_atr(), add_adx(), add_obv()
- run_full_analysis() min_rows 스킵 로직
- generate_signals() 신호 판단 정확성
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from technical_analysis import (
    add_moving_averages, add_rsi, add_macd, add_bollinger_bands,
    add_stochastic, add_atr, add_adx, add_obv,
    run_full_analysis, generate_signals, _get_indicator,
)


# ─── 테스트 데이터 생성 유틸 ───

def _make_ohlcv(rows=100, base_price=10.0, trend="up"):
    """OHLCV 테스트 DataFrame 생성"""
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    np.random.seed(42)

    if trend == "up":
        # 꾸준한 상승
        prices = base_price + np.cumsum(np.random.normal(0.05, 0.3, rows))
    elif trend == "down":
        # 꾸준한 하락
        prices = base_price + np.cumsum(np.random.normal(-0.05, 0.3, rows))
    else:
        # 횡보
        prices = base_price + np.random.normal(0, 0.3, rows)

    prices = np.maximum(prices, 0.5)  # 음수 방지

    return pd.DataFrame({
        "Open": prices * 0.99,
        "High": prices * 1.02,
        "Low": prices * 0.97,
        "Close": prices,
        "Volume": np.random.randint(500_000, 5_000_000, rows).astype(float),
    }, index=dates)


# ─── 개별 지표 테스트 ───

class TestAddMovingAverages:
    """add_moving_averages() 이동평균 검증"""

    def test_sma_columns_created(self):
        df = _make_ohlcv(rows=150)
        df = add_moving_averages(df)
        for w in [5, 20, 60, 120]:
            assert f"SMA_{w}" in df.columns, f"SMA_{w} 컬럼 누락"

    def test_ema_columns_created(self):
        df = _make_ohlcv(rows=50)
        df = add_moving_averages(df)
        for w in [12, 26]:
            assert f"EMA_{w}" in df.columns, f"EMA_{w} 컬럼 누락"

    def test_sma_values_are_averages(self):
        """SMA 값이 실제 이동평균인지 검증"""
        df = _make_ohlcv(rows=30)
        df = add_moving_averages(df)
        # SMA_5의 마지막 값 = 최근 5일 Close 평균
        expected = df["Close"].iloc[-5:].mean()
        actual = df["SMA_5"].iloc[-1]
        assert abs(actual - expected) < 0.01

    def test_sma_nan_at_start(self):
        """SMA는 초기 행에 NaN이 있어야 함"""
        df = _make_ohlcv(rows=30)
        df = add_moving_averages(df)
        # SMA_20은 처음 19개 행이 NaN
        assert df["SMA_20"].iloc[:19].isna().all()
        assert not np.isnan(df["SMA_20"].iloc[19])


class TestAddRSI:
    """add_rsi() RSI 검증"""

    def test_rsi_column_created(self):
        df = _make_ohlcv(rows=30)
        df = add_rsi(df)
        assert "RSI" in df.columns

    def test_rsi_in_0_100_range(self):
        """RSI 값은 0~100 사이"""
        df = _make_ohlcv(rows=100)
        df = add_rsi(df)
        valid_rsi = df["RSI"].dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_rsi_custom_window(self):
        """커스텀 윈도우 파라미터"""
        df = _make_ohlcv(rows=50)
        df = add_rsi(df, window=7)
        assert "RSI" in df.columns
        valid = df["RSI"].dropna()
        assert len(valid) > 0

    def test_uptrend_rsi_higher(self):
        """상승 추세에서 RSI가 더 높은 경향"""
        df_up = _make_ohlcv(rows=100, trend="up")
        df_down = _make_ohlcv(rows=100, trend="down")
        df_up = add_rsi(df_up)
        df_down = add_rsi(df_down)
        avg_up = df_up["RSI"].dropna().mean()
        avg_down = df_down["RSI"].dropna().mean()
        assert avg_up > avg_down


class TestAddMACD:
    """add_macd() MACD 검증"""

    def test_macd_columns_created(self):
        df = _make_ohlcv(rows=50)
        df = add_macd(df)
        assert "MACD" in df.columns
        assert "MACD_Signal" in df.columns
        assert "MACD_Hist" in df.columns

    def test_macd_hist_equals_diff(self):
        """MACD_Hist = MACD - MACD_Signal"""
        df = _make_ohlcv(rows=100)
        df = add_macd(df)
        valid = df.dropna(subset=["MACD", "MACD_Signal", "MACD_Hist"])
        diff = valid["MACD"] - valid["MACD_Signal"]
        np.testing.assert_allclose(valid["MACD_Hist"].values, diff.values, atol=1e-10)


class TestAddBollingerBands:
    """add_bollinger_bands() 볼린저 밴드 검증"""

    def test_bb_columns_created(self):
        df = _make_ohlcv(rows=30)
        df = add_bollinger_bands(df)
        for col in ["BB_Upper", "BB_Middle", "BB_Lower", "BB_Width", "BB_Pct"]:
            assert col in df.columns, f"{col} 컬럼 누락"

    def test_bb_order(self):
        """Upper > Middle > Lower 순서"""
        df = _make_ohlcv(rows=50)
        df = add_bollinger_bands(df)
        valid = df.dropna(subset=["BB_Upper", "BB_Middle", "BB_Lower"])
        assert (valid["BB_Upper"] >= valid["BB_Middle"]).all()
        assert (valid["BB_Middle"] >= valid["BB_Lower"]).all()

    def test_bb_width_positive(self):
        """밴드 폭은 양수"""
        df = _make_ohlcv(rows=50)
        df = add_bollinger_bands(df)
        valid = df["BB_Width"].dropna()
        assert (valid >= 0).all()

    def test_bb_custom_window(self):
        df = _make_ohlcv(rows=50)
        df = add_bollinger_bands(df, window=10)
        assert "BB_Upper" in df.columns


class TestAddStochastic:
    """add_stochastic() 스토캐스틱 검증"""

    def test_stoch_columns_created(self):
        df = _make_ohlcv(rows=30)
        df = add_stochastic(df)
        assert "Stoch_K" in df.columns
        assert "Stoch_D" in df.columns

    def test_stoch_in_0_100_range(self):
        """스토캐스틱 값은 0~100"""
        df = _make_ohlcv(rows=100)
        df = add_stochastic(df)
        for col in ["Stoch_K", "Stoch_D"]:
            valid = df[col].dropna()
            assert (valid >= 0).all(), f"{col} < 0"
            assert (valid <= 100).all(), f"{col} > 100"


class TestAddATR:
    """add_atr() ATR 검증"""

    def test_atr_column_created(self):
        df = _make_ohlcv(rows=30)
        df = add_atr(df)
        assert "ATR" in df.columns

    def test_atr_non_negative(self):
        """ATR은 항상 0 이상 (초기 구간은 0 가능)"""
        df = _make_ohlcv(rows=100)
        df = add_atr(df)
        valid = df["ATR"].dropna()
        assert (valid >= 0).all()
        # 충분한 데이터 이후에는 양수
        assert valid.iloc[-1] > 0

    def test_atr_custom_window(self):
        df = _make_ohlcv(rows=50)
        df = add_atr(df, window=7)
        assert "ATR" in df.columns


class TestAddADX:
    """add_adx() ADX 검증"""

    def test_adx_columns_created(self):
        df = _make_ohlcv(rows=50)
        df = add_adx(df)
        assert "ADX" in df.columns
        assert "ADX_Pos" in df.columns
        assert "ADX_Neg" in df.columns

    def test_adx_in_0_100_range(self):
        """ADX 값은 0~100"""
        df = _make_ohlcv(rows=100)
        df = add_adx(df)
        valid = df["ADX"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_adx_custom_window(self):
        df = _make_ohlcv(rows=50)
        df = add_adx(df, window=7)
        assert "ADX" in df.columns


class TestAddOBV:
    """add_obv() OBV 검증"""

    def test_obv_column_created(self):
        df = _make_ohlcv(rows=30)
        df = add_obv(df)
        assert "OBV" in df.columns

    def test_obv_no_nan(self):
        """OBV는 NaN이 없어야 함 (최소 데이터로도 계산 가능)"""
        df = _make_ohlcv(rows=10)
        df = add_obv(df)
        assert df["OBV"].isna().sum() == 0


# ─── run_full_analysis() ───

class TestRunFullAnalysis:
    """run_full_analysis() 통합 지표 적용"""

    def test_all_indicators_with_enough_data(self):
        """충분한 데이터에서 모든 지표 생성"""
        df = _make_ohlcv(rows=150)
        df = run_full_analysis(df)
        expected_cols = ["SMA_5", "SMA_20", "RSI", "MACD", "BB_Upper",
                         "Stoch_K", "ATR", "ADX", "OBV"]
        for col in expected_cols:
            assert col in df.columns, f"{col} 컬럼 누락"

    def test_short_data_skips_some_indicators(self):
        """데이터 부족 시 일부 지표 스킵"""
        df = _make_ohlcv(rows=10)
        df = run_full_analysis(df)
        # OBV는 2행만 필요하므로 존재해야 함
        assert "OBV" in df.columns
        # ADX는 30행 필요하므로 생성되지 않아야 함
        assert "ADX" not in df.columns

    def test_very_short_data_only_obv(self):
        """극소 데이터에서는 OBV만 생성"""
        df = _make_ohlcv(rows=3)
        df = run_full_analysis(df)
        assert "OBV" in df.columns
        assert "RSI" not in df.columns
        assert "MACD" not in df.columns

    def test_original_columns_preserved(self):
        """원본 OHLCV 컬럼 보존"""
        df = _make_ohlcv(rows=50)
        original_cols = list(df.columns)
        df = run_full_analysis(df)
        for col in original_cols:
            assert col in df.columns


# ─── generate_signals() 신호 정확성 ───

class TestGenerateSignalsAccuracy:
    """generate_signals() 신호 판단 정확성"""

    def test_rsi_oversold_buy_signal(self):
        """RSI < 30 → 매수 신호"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        # RSI를 강제로 25로 설정
        df.loc[df.index[-1], "RSI"] = 25.0
        signals = generate_signals(df)
        assert "RSI" in signals
        assert "매수" in signals["RSI"][1]

    def test_rsi_overbought_sell_signal(self):
        """RSI > 70 → 매도 신호"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "RSI"] = 75.0
        signals = generate_signals(df)
        assert "RSI" in signals
        assert "매도" in signals["RSI"][1]

    def test_rsi_neutral(self):
        """30 < RSI < 70 → 중립"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "RSI"] = 50.0
        signals = generate_signals(df)
        assert "RSI" in signals
        assert "중립" in signals["RSI"][1]

    def test_macd_golden_cross(self):
        """MACD > Signal → 골든크로스"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "MACD"] = 0.5
        df.loc[df.index[-1], "MACD_Signal"] = 0.3
        signals = generate_signals(df)
        if "MACD" in signals:
            assert "매수" in signals["MACD"][1]

    def test_macd_dead_cross(self):
        """MACD < Signal → 데드크로스"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "MACD"] = 0.2
        df.loc[df.index[-1], "MACD_Signal"] = 0.5
        signals = generate_signals(df)
        if "MACD" in signals:
            assert "매도" in signals["MACD"][1]

    def test_moving_avg_uptrend(self):
        """정배열: Close > SMA5 > SMA20 > SMA60"""
        df = _make_ohlcv(rows=100)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "Close"] = 20.0
        df.loc[df.index[-1], "SMA_5"] = 18.0
        df.loc[df.index[-1], "SMA_20"] = 16.0
        df.loc[df.index[-1], "SMA_60"] = 14.0
        signals = generate_signals(df)
        if "이동평균" in signals:
            assert "상승" in signals["이동평균"][1]

    def test_moving_avg_downtrend(self):
        """역배열: Close < SMA5 < SMA20 < SMA60"""
        df = _make_ohlcv(rows=100)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "Close"] = 5.0
        df.loc[df.index[-1], "SMA_5"] = 7.0
        df.loc[df.index[-1], "SMA_20"] = 9.0
        df.loc[df.index[-1], "SMA_60"] = 11.0
        signals = generate_signals(df)
        if "이동평균" in signals:
            assert "하락" in signals["이동평균"][1]

    def test_bb_below_lower(self):
        """BB_Pct < 0 → 하단 이탈"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "BB_Pct"] = -0.1
        signals = generate_signals(df)
        if "볼린저밴드" in signals:
            assert "반등" in signals["볼린저밴드"][1]

    def test_bb_above_upper(self):
        """BB_Pct > 1 → 상단 이탈"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "BB_Pct"] = 1.2
        signals = generate_signals(df)
        if "볼린저밴드" in signals:
            assert "조정" in signals["볼린저밴드"][1]

    def test_adx_strong_trend(self):
        """ADX > 25 → 강한 추세"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "ADX"] = 30.0
        signals = generate_signals(df)
        if "ADX" in signals:
            assert "강한" in signals["ADX"][0]

    def test_adx_weak_trend(self):
        """ADX < 25 → 약한 추세"""
        df = _make_ohlcv(rows=50)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "ADX"] = 20.0
        signals = generate_signals(df)
        if "ADX" in signals:
            assert "약한" in signals["ADX"][0]

    def test_buy_dominant_verdict(self):
        """매수 신호 다수 → 매수 우세"""
        df = _make_ohlcv(rows=100)
        df = run_full_analysis(df)
        # 매수 신호 강제 설정
        df.loc[df.index[-1], "RSI"] = 25.0  # 매수
        df.loc[df.index[-1], "MACD"] = 0.5
        df.loc[df.index[-1], "MACD_Signal"] = 0.1  # 매수
        df.loc[df.index[-1], "BB_Pct"] = -0.2  # 매수 (반등)
        df.loc[df.index[-1], "Close"] = 20.0
        df.loc[df.index[-1], "SMA_5"] = 18.0
        df.loc[df.index[-1], "SMA_20"] = 16.0
        df.loc[df.index[-1], "SMA_60"] = 14.0  # 매수 (정배열)
        signals = generate_signals(df)
        assert "매수" in signals["종합판단"]

    def test_sell_dominant_verdict(self):
        """매도 신호 다수 → 매도 우세"""
        df = _make_ohlcv(rows=100)
        df = run_full_analysis(df)
        df.loc[df.index[-1], "RSI"] = 80.0  # 매도
        df.loc[df.index[-1], "MACD"] = 0.1
        df.loc[df.index[-1], "MACD_Signal"] = 0.5  # 매도
        df.loc[df.index[-1], "BB_Pct"] = 1.3  # 매도 (조정)
        df.loc[df.index[-1], "Close"] = 5.0
        df.loc[df.index[-1], "SMA_5"] = 7.0
        df.loc[df.index[-1], "SMA_20"] = 9.0
        df.loc[df.index[-1], "SMA_60"] = 11.0  # 매도 (역배열)
        signals = generate_signals(df)
        assert "매도" in signals["종합판단"]

    def test_unavailable_indicators_tracked(self):
        """미계산 지표 추적"""
        df = _make_ohlcv(rows=5)
        df = run_full_analysis(df)  # 대부분의 지표가 스킵됨
        signals = generate_signals(df)
        if "미계산지표" in signals:
            assert len(signals["미계산지표"][0]) > 0


# ─── _get_indicator() ───

class TestGetIndicator:
    """_get_indicator() 안전 추출"""

    def test_valid_value(self):
        s = pd.Series({"RSI": 50.0})
        assert _get_indicator(s, "RSI") == 50.0

    def test_nan_returns_none(self):
        s = pd.Series({"RSI": np.nan})
        assert _get_indicator(s, "RSI") is None

    def test_inf_returns_none(self):
        s = pd.Series({"RSI": np.inf})
        assert _get_indicator(s, "RSI") is None

    def test_missing_key_returns_none(self):
        s = pd.Series({"RSI": 50.0})
        assert _get_indicator(s, "MACD") is None

    def test_zero_is_valid(self):
        s = pd.Series({"OBV": 0.0})
        assert _get_indicator(s, "OBV") == 0.0

    def test_negative_is_valid(self):
        s = pd.Series({"MACD": -0.5})
        assert _get_indicator(s, "MACD") == -0.5
