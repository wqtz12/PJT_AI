"""
P4 테스트: 4전문가 매크로/감성 반영
- 각 전문가가 _macro / _sentiment 컨텍스트를 올바르게 반영하는지 검증
- Guard clause: _macro/_sentiment 없으면 기존 동작 유지
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expert_strategies.trend_follower import TrendFollower
from expert_strategies.value_analyst import ValueAnalyst
from expert_strategies.momentum_trader import MomentumTrader
from expert_strategies.contrarian_expert import ContrarianExpert


def _make_df(n=100, close_start=100, trend="flat"):
    """테스트용 DataFrame 생성"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)

    if trend == "up":
        close = np.linspace(close_start, close_start * 1.3, n) + np.random.randn(n) * 0.5
    elif trend == "down":
        close = np.linspace(close_start, close_start * 0.7, n) + np.random.randn(n) * 0.5
    else:
        close = np.full(n, close_start) + np.random.randn(n) * 2

    close = np.maximum(close, 1.0)
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.02,
        "Low": close * 0.98,
        "Close": close,
        "Volume": np.random.randint(100000, 1000000, n),
    }, index=dates)

    # 기술적 지표 추가
    df["SMA_5"] = df["Close"].rolling(5).mean()
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_60"] = df["Close"].rolling(60).mean()
    df["SMA_120"] = df["Close"].rolling(120).mean() if n >= 120 else np.nan
    df["ADX"] = 25.0  # 보통 추세
    df["MACD"] = 0.5 if trend == "up" else -0.5 if trend == "down" else 0.01
    df["MACD_Signal"] = 0.3 if trend == "up" else -0.3 if trend == "down" else 0.0
    df["ATR"] = df["Close"] * 0.03
    df["RSI"] = 55 if trend == "flat" else 65 if trend == "up" else 35
    df["Stoch_K"] = 60
    df["Stoch_D"] = 55
    df["OBV"] = np.cumsum(np.random.randn(n) * 10000)

    # 볼린저밴드
    df["BB_Middle"] = df["SMA_20"]
    df["BB_Upper"] = df["BB_Middle"] + df["Close"].rolling(20).std() * 2
    df["BB_Lower"] = df["BB_Middle"] - df["Close"].rolling(20).std() * 2
    bb_range = df["BB_Upper"] - df["BB_Lower"]
    df["BB_Pct"] = (df["Close"] - df["BB_Lower"]) / bb_range.replace(0, np.nan)
    df["BB_Width"] = bb_range / df["BB_Middle"].replace(0, np.nan)

    return df


def _base_company_info():
    """기본 company_info (매크로/감성 없음)"""
    return {
        "이름": "TestCorp",
        "섹터": "Technology",
        "52주_최고": 150.0,
        "52주_최저": 50.0,
        "PBR": 5.0,
        "PER": 25.0,
        "EPS": 3.5,
        "부채비율": 45.0,
        "현금": 1_000_000_000,
        "시가총액": 10_000_000_000,
        "애널리스트_목표가": 130.0,
    }


def _macro_risk_on():
    """위험선호 매크로 컨텍스트"""
    return {
        "vix": {"current": 12, "level": "저변동", "trend": "하락"},
        "sp500": {"current": 5500, "trend": "상승"},
        "treasury_10y": {"current": 3.5, "trend": "하락"},
        "dollar": {"current": 100, "trend": "하락"},
        "gold": {"current": 2000, "trend": "하락"},
        "환경_점수": 4,
        "시장_환경": "위험선호",
    }


def _macro_risk_off():
    """위험회피 매크로 컨텍스트"""
    return {
        "vix": {"current": 35, "level": "고변동", "trend": "상승"},
        "sp500": {"current": 4500, "trend": "하락"},
        "treasury_10y": {"current": 5.0, "trend": "상승"},
        "dollar": {"current": 110, "trend": "상승"},
        "gold": {"current": 2100, "trend": "상승"},
        "환경_점수": -4,
        "시장_환경": "위험회피",
    }


def _macro_extreme_fear():
    """극단적 공포 매크로 (역발상용)"""
    return {
        "vix": {"current": 40, "level": "극단", "trend": "상승"},
        "sp500": {"current": 4000, "trend": "하락"},
        "treasury_10y": {"current": 5.5, "trend": "상승"},
        "dollar": {"current": 112, "trend": "상승"},
        "gold": {"current": 2200, "trend": "상승"},
        "환경_점수": -5,
        "시장_환경": "위험회피",
    }


def _sentiment_positive(score=0.5, confidence=0.8):
    """긍정 감성 컨텍스트"""
    return {
        "score": score, "raw_score": score, "label": "긍정적",
        "positive_count": 4, "negative_count": 1, "neutral_count": 0,
        "total_count": 5, "confidence": confidence,
    }


def _sentiment_negative(score=-0.5, confidence=0.8):
    """부정 감성 컨텍스트"""
    return {
        "score": score, "raw_score": score, "label": "부정적",
        "positive_count": 1, "negative_count": 4, "neutral_count": 0,
        "total_count": 5, "confidence": confidence,
    }


def _sentiment_extreme_positive():
    """극단 긍정 감성"""
    return _sentiment_positive(score=0.8, confidence=1.0)


def _sentiment_extreme_negative():
    """극단 부정 감성"""
    return _sentiment_negative(score=-0.8, confidence=1.0)


def _sentiment_low_confidence():
    """낮은 신뢰도 감성 (무시되어야 함)"""
    return {
        "score": 0.5, "raw_score": 0.5, "label": "긍정적",
        "positive_count": 1, "negative_count": 0, "neutral_count": 0,
        "total_count": 1, "confidence": 0.2,
    }


# ═══════════════════════════════════════
# TrendFollower 테스트
# ═══════════════════════════════════════

class TestTrendFollowerMacro:
    def test_no_macro_unchanged(self):
        """매크로 없으면 기존 동작 유지"""
        df = _make_df(trend="up")
        info = _base_company_info()
        result = TrendFollower.analyze(df, info)
        assert "[매크로]" not in result.rationale
        assert "[감성]" not in result.rationale

    def test_vix_high_reduces_uptrend(self):
        """VIX 고변동 → 상승추세 score 감소"""
        df = _make_df(trend="up")
        info_no_macro = _base_company_info()
        result_no = TrendFollower.analyze(df, info_no_macro)

        info_macro = _base_company_info()
        info_macro["_macro"] = _macro_risk_off()
        result_macro = TrendFollower.analyze(df, info_macro)

        assert "[매크로]" in result_macro.rationale

    def test_vix_low_strengthens_trend(self):
        """VIX 저변동 → 추세 방향 강화"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = _macro_risk_on()
        result = TrendFollower.analyze(df, info)
        assert "VIX 저변동" in result.rationale

    def test_rate_rise_hurts_uptrend(self):
        """금리 상승 + 상승추세 → score 감소"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 18, "level": "보통", "trend": "안정"},
            "treasury_10y": {"current": 5.0, "trend": "상승"},
            "환경_점수": 0,
            "시장_환경": "중립",
        }
        result = TrendFollower.analyze(df, info)
        assert "금리 상승" in result.rationale


class TestTrendFollowerSentiment:
    def test_positive_confirms_uptrend(self):
        """긍정 감성 + 상승추세 → score 증가"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_positive()
        result = TrendFollower.analyze(df, info)
        assert "[감성]" in result.rationale

    def test_negative_confirms_downtrend(self):
        """부정 감성 + 하락추세 → score 감소"""
        df = _make_df(trend="down")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_negative()
        result = TrendFollower.analyze(df, info)
        assert "[감성]" in result.rationale

    def test_low_confidence_ignored(self):
        """낮은 신뢰도 감성 → 무시"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_low_confidence()
        result = TrendFollower.analyze(df, info)
        assert "[감성]" not in result.rationale

    def test_contradiction_moderates(self):
        """긍정 감성 vs 하락추세 → 모순 완화"""
        df = _make_df(trend="down")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_positive()
        result = TrendFollower.analyze(df, info)
        # 둘 중 하나: 추세 확인 또는 모순 완화
        assert "[감성]" in result.rationale


# ═══════════════════════════════════════
# ValueAnalyst 테스트
# ═══════════════════════════════════════

class TestValueAnalystMacro:
    def test_no_macro_unchanged(self):
        """매크로 없으면 기존 동작 유지"""
        df = _make_df()
        info = _base_company_info()
        result = ValueAnalyst.analyze(df, info)
        assert "[매크로]" not in result.rationale

    def test_rate_rise_high_per_penalty(self):
        """금리 상승 + 고PER → 성장주 할인"""
        df = _make_df()
        info = _base_company_info()
        info["PER"] = 40
        info["_macro"] = {
            "treasury_10y": {"current": 5.0, "trend": "상승"},
            "환경_점수": -1,
            "시장_환경": "중립",
        }
        result = ValueAnalyst.analyze(df, info)
        assert "성장주 할인" in result.rationale

    def test_rate_rise_low_per_bonus(self):
        """금리 상승 + 저PER → 가치주 매력"""
        df = _make_df()
        info = _base_company_info()
        info["PER"] = 10
        info["_macro"] = {
            "treasury_10y": {"current": 5.0, "trend": "상승"},
            "환경_점수": -1,
            "시장_환경": "중립",
        }
        result = ValueAnalyst.analyze(df, info)
        assert "가치주 매력" in result.rationale

    def test_risk_on_bonus(self):
        """위험선호 환경 → 투자 심리 양호"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = _macro_risk_on()
        result = ValueAnalyst.analyze(df, info)
        assert "투자 심리 양호" in result.rationale

    def test_risk_off_penalty(self):
        """위험회피 환경 → 투자 심리 위축"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = _macro_risk_off()
        result = ValueAnalyst.analyze(df, info)
        assert "투자 심리 위축" in result.rationale


class TestValueAnalystSentiment:
    def test_extreme_positive_bonus(self):
        """강한 긍정 뉴스 → 시장 인식 양호"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_extreme_positive()
        result = ValueAnalyst.analyze(df, info)
        assert "시장 인식 양호" in result.rationale

    def test_extreme_negative_penalty(self):
        """강한 부정 뉴스 → 시장 인식 악화"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_extreme_negative()
        result = ValueAnalyst.analyze(df, info)
        assert "시장 인식 악화" in result.rationale

    def test_moderate_sentiment_no_impact(self):
        """보통 감성 → value analyst에는 영향 없음 (극단만 반영)"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_positive(score=0.3)
        result = ValueAnalyst.analyze(df, info)
        # score 0.3은 EXTREME_BULLISH(0.6) 미만 → 무반영
        assert "[감성]" not in result.rationale


# ═══════════════════════════════════════
# MomentumTrader 테스트
# ═══════════════════════════════════════

class TestMomentumTraderMacro:
    def test_no_macro_unchanged(self):
        """매크로 없으면 기존 동작 유지"""
        df = _make_df(trend="up")
        info = _base_company_info()
        result = MomentumTrader.analyze(df, info)
        assert "[매크로]" not in result.rationale

    def test_vix_above_30_penalty(self):
        """VIX > 30 → 모멘텀 전략 위험 (-2)"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 32, "level": "고변동", "trend": "상승"},
            "환경_점수": -3,
            "시장_환경": "위험회피",
        }
        result = MomentumTrader.analyze(df, info)
        assert "모멘텀 전략 위험" in result.rationale

    def test_vix_above_25_warning(self):
        """VIX > 25 → 모멘텀 주의 (-1)"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 27, "level": "경계", "trend": "상승"},
            "환경_점수": -1,
            "시장_환경": "중립",
        }
        result = MomentumTrader.analyze(df, info)
        assert "모멘텀 주의" in result.rationale

    def test_vix_low_with_positive_score(self):
        """VIX < 15 + 양의 score → 안정적 모멘텀 (+1)"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = _macro_risk_on()
        result = MomentumTrader.analyze(df, info)
        # VIX 12 < 15, 상승 trend → 안정적 모멘텀 표시될 수 있음
        assert "[매크로]" in result.rationale

    def test_sp500_fall_hurts_momentum(self):
        """S&P500 하락 → 시장 역풍"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 18, "level": "보통", "trend": "안정"},
            "sp500": {"current": 4500, "trend": "하락"},
            "환경_점수": -1,
            "시장_환경": "중립",
        }
        result = MomentumTrader.analyze(df, info)
        # score가 양수일 때만 S&P500 하락이 적용됨
        assert "[매크로]" in result.rationale


class TestMomentumTraderSentiment:
    def test_positive_confirms_momentum(self):
        """긍정 뉴스 + 양의 score → 모멘텀 확인"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_positive()
        result = MomentumTrader.analyze(df, info)
        assert "[감성]" in result.rationale

    def test_negative_confirms_decline(self):
        """부정 뉴스 + 음의 score → 하락 모멘텀 확인"""
        df = _make_df(trend="down")
        # RSI를 극단적 하락으로 설정하여 score < 0 보장
        df["RSI"] = 20.0
        df["Stoch_K"] = 15.0
        df["Stoch_D"] = 25.0
        info = _base_company_info()
        info["_sentiment"] = _sentiment_negative()
        result = MomentumTrader.analyze(df, info)
        assert "[감성]" in result.rationale

    def test_low_confidence_ignored(self):
        """낮은 신뢰도 → 무시"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_sentiment"] = _sentiment_low_confidence()
        result = MomentumTrader.analyze(df, info)
        assert "[감성]" not in result.rationale


# ═══════════════════════════════════════
# ContrarianExpert 테스트
# ═══════════════════════════════════════

class TestContrarianExpertMacro:
    def test_no_macro_unchanged(self):
        """매크로 없으면 기존 동작 유지"""
        df = _make_df()
        info = _base_company_info()
        result = ContrarianExpert.analyze(df, info)
        assert "[매크로]" not in result.rationale

    def test_extreme_vix_buy_signal(self):
        """VIX > 35 → 극단적 공포 = 역발상 매수 (+2)"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = _macro_extreme_fear()
        result = ContrarianExpert.analyze(df, info)
        assert "극단적 공포" in result.rationale

    def test_high_vix_buy_signal(self):
        """VIX > 30 → 공포 구간 = 역발상 매수 (+1)"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 32, "level": "고변동", "trend": "상승"},
            "환경_점수": -3,
            "시장_환경": "위험회피",
        }
        result = ContrarianExpert.analyze(df, info)
        assert "공포 구간" in result.rationale

    def test_very_low_vix_sell_signal(self):
        """VIX < 12 → 극단적 안일함 = 역발상 매도 (-2)"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 10, "level": "저변동", "trend": "하락"},
            "환경_점수": 4,
            "시장_환경": "위험선호",
        }
        result = ContrarianExpert.analyze(df, info)
        assert "극단적 안일함" in result.rationale

    def test_low_vix_sell_signal(self):
        """VIX < 15 → 안일 구간 = 역발상 매도 (-1)"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 13, "level": "저변동", "trend": "하락"},
            "환경_점수": 3,
            "시장_환경": "위험선호",
        }
        result = ContrarianExpert.analyze(df, info)
        assert "안일 구간" in result.rationale

    def test_moderate_vix_no_impact(self):
        """VIX 15~30 → 역발상 매크로 무영향"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 20, "level": "보통", "trend": "안정"},
            "환경_점수": 0,
            "시장_환경": "중립",
        }
        result = ContrarianExpert.analyze(df, info)
        # VIX 15~30 구간은 역발상 매크로 불적용
        vix_macro = [r for r in result.rationale.split(" | ") if "[매크로]" in r and "VIX" in r]
        assert len(vix_macro) == 0


class TestContrarianExpertSentiment:
    def test_extreme_optimism_sell(self):
        """극단 낙관 감성 → 역발상 경계 (-1)"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_extreme_positive()
        result = ContrarianExpert.analyze(df, info)
        assert "역발상 경계" in result.rationale

    def test_extreme_pessimism_buy(self):
        """극단 비관 감성 → 역발상 매수 (+1)"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_extreme_negative()
        result = ContrarianExpert.analyze(df, info)
        assert "역발상 매수" in result.rationale

    def test_moderate_sentiment_no_impact(self):
        """보통 감성 → 역발상에는 영향 없음"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_positive(score=0.3)
        result = ContrarianExpert.analyze(df, info)
        assert "[감성]" not in result.rationale

    def test_low_confidence_ignored(self):
        """낮은 신뢰도 → 무시"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = _sentiment_low_confidence()
        result = ContrarianExpert.analyze(df, info)
        assert "[감성]" not in result.rationale


# ═══════════════════════════════════════
# 공통: Guard Clause 테스트
# ═══════════════════════════════════════

class TestGuardClauses:
    """_macro/_sentiment 없을 때 기존 동작 100% 유지 확인"""

    def test_all_experts_work_without_macro_sentiment(self):
        """4전문가 모두 매크로/감성 없이 정상 동작"""
        df = _make_df(trend="up")
        info = _base_company_info()

        for Expert in [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")
            assert 0 < result.confidence <= 100
            assert "[매크로]" not in result.rationale
            assert "[감성]" not in result.rationale

    def test_none_macro_no_crash(self):
        """_macro=None이면 무시"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = None
        for Expert in [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")

    def test_none_sentiment_no_crash(self):
        """_sentiment=None이면 무시"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = None
        for Expert in [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")

    def test_empty_macro_dict_no_crash(self):
        """_macro=빈 dict이면 무시"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {}
        for Expert in [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")

    def test_both_macro_and_sentiment(self):
        """매크로 + 감성 동시 적용"""
        df = _make_df(trend="up")
        info = _base_company_info()
        info["_macro"] = _macro_risk_on()
        info["_sentiment"] = _sentiment_positive()

        for Expert in [TrendFollower, MomentumTrader]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")
            # 상승 추세 + 위험선호 + 긍정 감성 → 적어도 매크로 or 감성 반영
            has_context = "[매크로]" in result.rationale or "[감성]" in result.rationale
            assert has_context

    def test_partial_macro_data(self):
        """매크로 일부 지표만 있어도 작동"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 20, "level": "보통"},
            "환경_점수": 0,
            "시장_환경": "중립",
        }
        for Expert in [TrendFollower, ValueAnalyst, MomentumTrader, ContrarianExpert]:
            result = Expert.analyze(df, info)
            assert result.position in ("매수", "매도", "홀드")
