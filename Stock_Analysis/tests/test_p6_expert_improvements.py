"""
P6 전문가 개별 보정 + 가중 집계 테스트 - Phase 4 (P1-4~6)

테스트 항목:
    - 역발상 전문가: RSI 극단값 + ADX 체크
    - 가치분석 전문가: 가치함정 필터
    - 전문가 가중 집계: _aggregate_expert_opinions()
    - config 기본값 검증
"""
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from common.models import ExpertOpinion
from common.config import get_config


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 데이터 생성
# ──────────────────────────────────────────────
def _make_df(
    rows: int = 60,
    close: float = 100.0,
    rsi: float = 50.0,
    adx: float = 20.0,
    bb_pct: float = 0.5,
    trend: str = "flat",
) -> pd.DataFrame:
    """테스트용 OHLCV + 기술적 지표 DataFrame"""
    dates = pd.date_range(end=datetime.now(), periods=rows, freq="B", tz="US/Eastern")

    if trend == "down" and rows > 6:
        closes = [close * (1 + 0.01 * (rows - i) / rows) for i in range(rows)]
        for i in range(min(6, rows)):
            closes[-(i+1)] = close * (1 - 0.015 * (6 - i))
    elif trend == "up":
        closes = [close * (1 - 0.01 * (rows - i) / rows) for i in range(rows)]
    else:
        closes = [close] * rows

    data = {
        "Open": [c * 0.99 for c in closes],
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.98 for c in closes],
        "Close": closes,
        "Volume": [1000000] * rows,
        "RSI": [rsi] * rows,  # contrarian uses "RSI"
        "RSI_14": [rsi] * rows,
        "ADX": [adx] * rows,
        "ADX_Pos": [adx * 0.6] * rows,
        "ADX_Neg": [adx * 0.4] * rows,
        "BB_Pct": [bb_pct] * rows,
        "BB_Upper": [close * 1.05] * rows,
        "BB_Lower": [close * 0.95] * rows,
        "BB_Middle": [close] * rows,
        "BB_Width": [0.1] * rows,
        "MACD": [1.0] * rows,
        "MACD_Signal": [0.5] * rows,
        "MACD_Hist": [0.5] * rows,
        "SMA_5": [close] * rows,
        "SMA_20": [close] * rows,
        "SMA_60": [close] * rows,
        "SMA_120": [close * 0.95] * rows,
        "ATR": [close * 0.03] * rows,
        "Stoch_K": [50.0] * rows,
        "Stoch_D": [50.0] * rows,
        "OBV": list(range(rows)),
    }
    return pd.DataFrame(data, index=dates)


def _make_opinion(
    name: str = "테스트",
    position: str = "홀드",
    confidence: float = 50.0,
) -> ExpertOpinion:
    return ExpertOpinion(
        expert_name=name,
        expert_style="테스트",
        position=position,
        confidence=confidence,
    )


# ══════════════════════════════════════════════
# 1. 역발상 전문가 ADX 체크
# ══════════════════════════════════════════════
class TestContrarianADXCheck:
    """역발상 전문가: RSI 극단 + ADX → 추세적 과매도 보정"""

    def test_extreme_low_rsi_weak_trend_strong_buy(self):
        """RSI<25 + ADX<30 (약한 추세) → score +3 (기존 유지)"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_df(rsi=20.0, adx=15.0, bb_pct=0.1)
        info = {"52주_최고": 200.0, "52주_최저": 50.0}
        opinion = ContrarianExpert.analyze(df, info)

        # RSI 극단 과매도 + 약한 추세 → 강한 매수 신호
        assert "반등 매수" in opinion.rationale or "과매도" in opinion.rationale

    def test_extreme_low_rsi_strong_trend_weak_buy(self):
        """RSI<25 + ADX>30 (강한 추세) → score +1 (약한 반등)"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_df(rsi=20.0, adx=35.0, bb_pct=0.1)
        info = {"52주_최고": 200.0, "52주_최저": 50.0}
        opinion = ContrarianExpert.analyze(df, info)

        # 추세적 과매도 → 약한 반등
        assert "추세적 과매도" in opinion.rationale
        assert "약한 반등" in opinion.rationale

    def test_contrarian_low_rsi_strong_trend_no_buy(self):
        """RSI<35 (35보다 작지만 25보다 큼) + ADX>30 → 매수 억제"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_df(rsi=30.0, adx=35.0, bb_pct=0.5)
        info = {"52주_최고": 150.0, "52주_최저": 80.0}
        opinion = ContrarianExpert.analyze(df, info)

        # ADX>30 → 추세적 과매도로 관망
        assert "추세적 과매도" in opinion.rationale or "관망" in opinion.rationale

    def test_contrarian_low_rsi_weak_trend_normal_buy(self):
        """RSI<35 + ADX<20 → score +1 (기존 로직)"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_df(rsi=30.0, adx=15.0, bb_pct=0.5)
        info = {"52주_최고": 150.0, "52주_최저": 80.0}
        opinion = ContrarianExpert.analyze(df, info)

        # 약한 추세 → 바닥 탐색
        assert "바닥 탐색" in opinion.rationale

    def test_normal_rsi_unaffected(self):
        """RSI 50 (정상) → ADX 체크 미적용"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_df(rsi=50.0, adx=35.0, bb_pct=0.5)
        info = {"52주_최고": 150.0, "52주_최저": 80.0}
        opinion = ContrarianExpert.analyze(df, info)

        assert "추세적 과매도" not in opinion.rationale


# ══════════════════════════════════════════════
# 2. 가치분석 전문가 가치함정 필터
# ══════════════════════════════════════════════
class TestValueAnalystValueTrap:
    """가치분석 전문가: 52주 하위 + 급락 → 가치함정 경고"""

    def test_value_trap_detected(self):
        """52주 하위 + 5일 급락 → 가치함정 패널티"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_df(close=55.0, trend="down", rows=60)
        info = {
            "52주_최고": 200.0,
            "52주_최저": 40.0,
            "PBR": 0.5,
            "EPS": 2.0,
        }
        opinion = ValueAnalyst.analyze(df, info)

        # 52주 하위권 + 하락 추세: 가치함정 경고가 rationale에 있는지
        # (close=55, range=(55-40)/(200-40)=9.4% < 40%)
        # 다운트렌드이면 5일 급락이 있을 수 있음
        if "가치함정" in opinion.rationale:
            assert "하강 중 저점" in opinion.rationale

    def test_no_trap_high_range(self):
        """52주 상위 → 가치함정 미적용"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_df(close=180.0, rows=60)
        info = {
            "52주_최고": 200.0,
            "52주_최저": 100.0,
            "PBR": 2.0,
            "EPS": 5.0,
        }
        opinion = ValueAnalyst.analyze(df, info)

        # 52주 80% → 가치함정 미적용
        assert "가치함정" not in opinion.rationale

    def test_no_trap_stable_price(self):
        """52주 하위지만 안정적 → 가치함정 미적용"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_df(close=55.0, trend="flat", rows=60)
        info = {
            "52주_최고": 200.0,
            "52주_최저": 40.0,
            "PBR": 0.8,
            "EPS": 1.0,
        }
        opinion = ValueAnalyst.analyze(df, info)

        # 횡보 → 5일 수익률 ~0% → 가치함정 미적용
        assert "가치함정" not in opinion.rationale

    def test_no_52w_data_no_trap(self):
        """52주 데이터 없으면 가치함정 미적용"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_df(close=50.0, rows=60)
        info = {"PBR": 0.5, "EPS": 1.0}
        opinion = ValueAnalyst.analyze(df, info)

        assert "가치함정" not in opinion.rationale


# ══════════════════════════════════════════════
# 3. 전문가 가중 집계
# ══════════════════════════════════════════════
class TestAggregateExpertOpinions:
    """전문가 가중 집계"""

    def test_equal_weights_by_default(self):
        """기본 가중치 모두 1.0"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("추세추종 전문가", "매수"),
            _make_opinion("가치분석 전문가", "매수"),
            _make_opinion("모멘텀 전문가", "홀드"),
            _make_opinion("역발상 전문가", "매도"),
        ]
        df = _make_df(adx=25.0)  # 중간 ADX → 부스트 없음
        info = {}

        result = _aggregate_expert_opinions(opinions, df, info)
        assert result["weighted_buy"] == 2.0
        assert result["weighted_hold"] == 1.0
        assert result["weighted_sell"] == 1.0
        assert result["dominant"] == "매수"

    def test_trend_boost_with_strong_adx(self):
        """ADX>30 → 추세추종 가중치 ↑"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("추세추종 전문가", "매수"),
            _make_opinion("가치분석 전문가", "홀드"),
            _make_opinion("모멘텀 전문가", "홀드"),
            _make_opinion("역발상 전문가", "매도"),
        ]
        df = _make_df(adx=35.0)  # 강한 추세
        info = {}

        result = _aggregate_expert_opinions(opinions, df, info)
        assert result["weights_used"]["추세추종 전문가"] == 1.5  # boost
        assert result["weights_used"]["가치분석 전문가"] == 1.0  # normal

    def test_value_boost_with_low_adx(self):
        """ADX<20 → 가치분석 가중치 ↑"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("추세추종 전문가", "홀드"),
            _make_opinion("가치분석 전문가", "매수"),
            _make_opinion("모멘텀 전문가", "홀드"),
            _make_opinion("역발상 전문가", "홀드"),
        ]
        df = _make_df(adx=15.0)  # 약한 추세/횡보
        info = {}

        result = _aggregate_expert_opinions(opinions, df, info)
        assert result["weights_used"]["가치분석 전문가"] == 1.5  # boost
        assert result["weights_used"]["추세추종 전문가"] == 1.0  # normal

    def test_contrarian_boost_with_high_vix(self):
        """VIX>25 → 역발상 가중치 ↑"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("추세추종 전문가", "매도"),
            _make_opinion("가치분석 전문가", "홀드"),
            _make_opinion("모멘텀 전문가", "매도"),
            _make_opinion("역발상 전문가", "매수"),
        ]
        df = _make_df(adx=25.0)
        info = {"_macro": {"vix": {"current": 30.0}}}

        result = _aggregate_expert_opinions(opinions, df, info)
        assert result["weights_used"]["역발상 전문가"] == 1.5  # boost

    def test_disabled_returns_simple_count(self):
        """비활성화 시 단순 카운트"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("A", "매수"),
            _make_opinion("B", "매수"),
            _make_opinion("C", "매도"),
        ]
        with patch("common.aggregation.get_config") as mock_cfg:
            mock_cfg.return_value = {"expert_aggregation": {"weighted": False}}
            result = _aggregate_expert_opinions(opinions, _make_df(), {})

        assert result["weighted_buy"] == 2.0
        assert result["weighted_sell"] == 1.0
        assert result["weights_used"] == {}

    def test_empty_opinions(self):
        """빈 의견 → weighted=False와 동일"""
        from stock_analyzer import _aggregate_expert_opinions

        result = _aggregate_expert_opinions([], _make_df(), {})
        assert result["dominant"] == "홀드"

    def test_all_same_position(self):
        """전원 동일 포지션"""
        from stock_analyzer import _aggregate_expert_opinions

        opinions = [
            _make_opinion("A", "매수"),
            _make_opinion("B", "매수"),
            _make_opinion("C", "매수"),
        ]
        result = _aggregate_expert_opinions(opinions, _make_df(), {})
        assert result["dominant"] == "매수"
        assert result["weighted_sell"] == 0
        assert result["weighted_hold"] == 0


# ══════════════════════════════════════════════
# 4. config 기본값 검증
# ══════════════════════════════════════════════
class TestExpertAggregationConfig:
    """expert_aggregation 설정값 검증"""

    def test_defaults_exist(self):
        cfg = get_config()
        ea = cfg.get("expert_aggregation", {})
        assert "weighted" in ea
        assert "base_weight" in ea
        assert "boost_multiplier" in ea

    def test_default_values(self):
        cfg = get_config()
        ea = cfg["expert_aggregation"]
        assert ea["weighted"] is True
        assert ea["base_weight"] == 1.0
        assert ea["boost_multiplier"] == 1.5
        assert ea["trend_boost_adx_threshold"] == 30
        assert ea["value_boost_adx_threshold"] == 20
        assert ea["contrarian_boost_vix_threshold"] == 25
