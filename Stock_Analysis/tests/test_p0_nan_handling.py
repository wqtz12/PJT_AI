"""
P0-2 테스트: NaN 전파 방지
- generate_signals()에서 NaN 지표 스킵 검증
- 4개 전문가 전략에서 NaN 처리 검증
- _safe_get / _safe_info 유틸리티 검증
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from technical_analysis import generate_signals, _get_indicator, run_full_analysis
from expert_strategies.trend_follower import TrendFollower
from expert_strategies.value_analyst import ValueAnalyst
from expert_strategies.momentum_trader import MomentumTrader
from expert_strategies.contrarian_expert import ContrarianExpert


# ─── 헬퍼 ───

def make_ohlcv_with_indicators(rows=100, include_indicators=True):
    """기술적 지표가 포함된 테스트 DataFrame"""
    dates = pd.bdate_range(start="2024-01-01", periods=rows)
    np.random.seed(42)
    prices = 10.0 + np.cumsum(np.random.randn(rows) * 0.3)
    prices = np.maximum(prices, 1.0)

    df = pd.DataFrame({
        "Open": prices + np.random.randn(rows) * 0.1,
        "High": prices + abs(np.random.randn(rows) * 0.3),
        "Low": prices - abs(np.random.randn(rows) * 0.3),
        "Close": prices,
        "Volume": np.random.randint(100000, 10000000, size=rows).astype(float),
    }, index=dates)

    if include_indicators:
        df = run_full_analysis(df)

    return df


def make_ohlcv_no_indicators(rows=100):
    """지표 없는 순수 OHLCV DataFrame (NaN 지표 시뮬레이션)"""
    return make_ohlcv_with_indicators(rows=rows, include_indicators=False)


def make_company_info_full():
    """정상적인 company_info"""
    return {
        "이름": "TestCorp",
        "섹터": "Technology",
        "산업": "Software",
        "시가총액": 1000000000,
        "52주_최고": 15.0,
        "52주_최저": 5.0,
        "PER": 25.0,
        "PBR": 2.5,
        "EPS": 0.85,
        "배당수익률": 0.02,
        "베타": 1.2,
        "애널리스트_목표가": 14.0,
        "추천": "buy",
        "총매출": 500000000,
        "영업이익": 50000000,
        "부채비율": 45.0,
        "현금": 200000000,
        "직원수": 1000,
        "홈페이지": "https://test.com",
        "설명": "A test corporation",
    }


def make_company_info_empty():
    """모든 필드가 None인 company_info"""
    return {
        "이름": "TestCorp",
        "섹터": None,
        "산업": None,
        "시가총액": None,
        "52주_최고": None,
        "52주_최저": None,
        "PER": None,
        "PBR": None,
        "EPS": None,
        "배당수익률": None,
        "베타": None,
        "애널리스트_목표가": None,
        "추천": None,
        "총매출": None,
        "영업이익": None,
        "부채비율": None,
        "현금": None,
        "직원수": None,
        "홈페이지": None,
        "설명": None,
    }


# ─── generate_signals 테스트 ───

class TestGenerateSignals:
    """generate_signals의 NaN 처리 검증"""

    def test_normal_data(self):
        """정상 데이터 → 종합판단 포함"""
        df = make_ohlcv_with_indicators()
        signals = generate_signals(df)
        assert "종합판단" in signals
        assert "판단 불가" not in signals["종합판단"]

    def test_no_indicators(self):
        """지표 없는 데이터 → 미계산지표 기록 + 판단 불가"""
        df = make_ohlcv_no_indicators()
        signals = generate_signals(df)
        assert "종합판단" in signals
        # 지표가 없으므로 미계산지표가 있어야 함
        assert "미계산지표" in signals

    def test_partial_nan_indicators(self):
        """일부 지표만 NaN → 해당 지표만 스킵"""
        df = make_ohlcv_with_indicators()
        # RSI를 NaN으로 설정
        df["RSI"] = np.nan
        signals = generate_signals(df)
        assert "RSI" not in signals  # RSI 신호 없어야 함
        assert "미계산지표" in signals
        assert "RSI" in signals["미계산지표"][0]  # 미계산 목록에 포함

    def test_empty_df(self):
        """빈 DataFrame → 종합판단만 반환"""
        df = pd.DataFrame()
        signals = generate_signals(df)
        assert "종합판단" in signals

    def test_all_indicators_present(self):
        """모든 지표 있을 때 → 미계산지표 없음"""
        df = make_ohlcv_with_indicators()
        signals = generate_signals(df)
        assert "미계산지표" not in signals


class TestGetIndicator:
    """_get_indicator 유틸리티 테스트"""

    def test_valid_value(self):
        """정상 값 → 그대로 반환"""
        row = pd.Series({"RSI": 55.0})
        assert _get_indicator(row, "RSI") == 55.0

    def test_nan_value(self):
        """NaN → None"""
        row = pd.Series({"RSI": np.nan})
        assert _get_indicator(row, "RSI") is None

    def test_missing_key(self):
        """존재하지 않는 키 → None"""
        row = pd.Series({"Close": 10.0})
        assert _get_indicator(row, "RSI") is None

    def test_inf_value(self):
        """Inf → None"""
        row = pd.Series({"RSI": np.inf})
        assert _get_indicator(row, "RSI") is None


# ─── 전문가 전략 NaN 처리 테스트 ───

class TestTrendFollowerNaN:

    def test_normal_data(self):
        """정상 데이터 → 유효한 ExpertOpinion"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()
        opinion = TrendFollower.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")
        assert opinion.confidence > 0

    def test_no_indicators(self):
        """지표 없음 → 판단 보류 (홀드, 낮은 확신도)"""
        df = make_ohlcv_no_indicators()
        info = make_company_info_full()
        opinion = TrendFollower.analyze(df, info)
        assert opinion.position == "홀드"
        assert opinion.confidence == 10
        assert "판단 보류" in opinion.rationale

    def test_partial_nan(self):
        """일부 지표 NaN → 해당 부분만 스킵, 나머지로 분석"""
        df = make_ohlcv_with_indicators()
        df["MACD"] = np.nan
        df["MACD_Signal"] = np.nan
        info = make_company_info_full()
        opinion = TrendFollower.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")
        assert "[MACD] 데이터 부족" in opinion.rationale


class TestValueAnalystNaN:

    def test_normal_data(self):
        """정상 company_info → 유효한 분석"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()
        opinion = ValueAnalyst.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")
        assert opinion.confidence > 0

    def test_empty_company_info(self):
        """모든 필드 None → 판단 보류"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_empty()
        opinion = ValueAnalyst.analyze(df, info)
        assert opinion.position == "홀드"
        assert opinion.confidence == 10
        assert "판단 보류" in opinion.rationale

    def test_partial_info(self):
        """일부 필드만 있음 → 해당 부분만 분석"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_empty()
        info["52주_최고"] = 15.0
        info["52주_최저"] = 5.0
        opinion = ValueAnalyst.analyze(df, info)
        assert opinion.confidence > 10  # 최소 1개 분석 → 보류보다 높음
        assert "52주" in opinion.rationale


class TestMomentumTraderNaN:

    def test_normal_data(self):
        """정상 데이터"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()
        opinion = MomentumTrader.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")

    def test_no_indicators(self):
        """지표 없음 → 판단 보류"""
        df = make_ohlcv_no_indicators(rows=30)  # 짧은 데이터
        info = make_company_info_full()
        opinion = MomentumTrader.analyze(df, info)
        assert "[RSI] 데이터 부족" in opinion.rationale

    def test_short_dataframe_no_crash(self):
        """짧은 DataFrame (21행 이하) → iloc[-21] 크래시 없음 (버그 수정 검증)"""
        # 21행 = len > 21 조건 미충족 → 수익률 분석 스킵 (정상)
        # ta 라이브러리가 최소 30행 필요하므로 지표 없이 테스트
        df = make_ohlcv_no_indicators(rows=21)
        info = make_company_info_full()
        opinion = MomentumTrader.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")
        # 5일/20일 수익률이 계산되지 않아야 함 (len=21, 조건 len > 21)
        assert "5일 수익률" not in opinion.rationale


class TestContrarianExpertNaN:

    def test_normal_data(self):
        """정상 데이터"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()
        opinion = ContrarianExpert.analyze(df, info)
        assert opinion.position in ("매수", "매도", "홀드")

    def test_no_indicators_no_info(self):
        """지표/정보 모두 없음 → 판단 보류"""
        df = make_ohlcv_no_indicators()
        info = make_company_info_empty()
        opinion = ContrarianExpert.analyze(df, info)
        assert opinion.position == "홀드"
        assert opinion.confidence == 10

    def test_nan_bollinger(self):
        """볼린저밴드 NaN → 해당 항목 스킵"""
        df = make_ohlcv_with_indicators()
        df["BB_Pct"] = np.nan
        info = make_company_info_full()
        opinion = ContrarianExpert.analyze(df, info)
        assert "[볼린저밴드] 데이터 부족" in opinion.rationale


# ─── 전문가 일관성 테스트 ───

class TestExpertConsistency:
    """모든 전문가가 NaN 데이터에서 크래시 없이 동작하는지 검증"""

    def test_all_experts_with_nan_data(self):
        """4명 전문가 모두 NaN-only 데이터에서 정상 동작"""
        df = make_ohlcv_no_indicators()
        info = make_company_info_empty()

        experts = [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]
        for Expert in experts:
            opinion = Expert.analyze(df, info)
            assert opinion.position in ("매수", "매도", "홀드"), \
                f"{Expert.NAME}: 잘못된 포지션 '{opinion.position}'"
            assert 0 <= opinion.confidence <= 100, \
                f"{Expert.NAME}: 확신도 범위 이탈 {opinion.confidence}"
            assert opinion.rationale, \
                f"{Expert.NAME}: 근거 비어있음"

    def test_all_experts_with_full_data(self):
        """4명 전문가 모두 정상 데이터에서 정상 동작"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()

        experts = [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]
        for Expert in experts:
            opinion = Expert.analyze(df, info)
            assert opinion.position in ("매수", "매도", "홀드")
            assert opinion.confidence > 0
            assert opinion.rationale

    def test_expert_opinion_fields_not_none(self):
        """정상 데이터에서 buy/sell/stop 필드가 None이 아님 (매도 시 buy_price 제외)"""
        df = make_ohlcv_with_indicators()
        info = make_company_info_full()

        experts = [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]
        for Expert in experts:
            opinion = Expert.analyze(df, info)
            assert opinion.sell_price is not None, f"{Expert.NAME}: sell_price is None"
            assert opinion.stop_loss is not None, f"{Expert.NAME}: stop_loss is None"
            if opinion.position != "매도":
                assert opinion.buy_price is not None, f"{Expert.NAME}: buy_price is None for {opinion.position}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
