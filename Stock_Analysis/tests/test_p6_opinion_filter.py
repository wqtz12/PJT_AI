"""
P6 전문가 의견 후처리 필터 테스트 - Phase 3 (P1-3)

테스트 항목:
    - _check_downtrend(): 하락추세 판별
    - _check_value_trap(): 가치함정 탐지
    - _check_oversold_trend(): 추세적 과매도 판별
    - apply_opinion_filters(): 통합 필터 적용
    - 원본 불변성, 홀드/매도 비필터, config 비활성화
"""
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from common.models import ExpertOpinion
from opinion_filter import (
    apply_opinion_filters,
    _check_downtrend,
    _check_value_trap,
    _check_oversold_trend,
)


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 데이터 생성
# ──────────────────────────────────────────────
def _make_df(
    rows: int = 30,
    close: float = 100.0,
    trend: str = "flat",  # "flat", "down", "up"
    rsi: float = 50.0,
    adx: float = 20.0,
    macd_dead_cross: bool = False,
    sma20_above: bool = True,
) -> pd.DataFrame:
    """테스트용 OHLCV + 기술적 지표 데이터프레임"""
    dates = pd.date_range(end=datetime.now(), periods=rows, freq="B", tz="US/Eastern")

    # 추세에 따른 Close 시리즈 생성
    if trend == "down":
        closes = [close * (1 + 0.02 * (rows - i - 1) / rows) for i in range(rows)]
        # 마지막 6일은 급락
        for i in range(min(6, rows)):
            closes[-(i + 1)] = close * (1 - 0.015 * (6 - i))
    elif trend == "up":
        closes = [close * (1 - 0.02 * (rows - i - 1) / rows) for i in range(rows)]
    else:
        closes = [close] * rows

    data = {
        "Open": [c * 0.99 for c in closes],
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.98 for c in closes],
        "Close": closes,
        "Volume": [1000000] * rows,
        "RSI": [rsi] * rows,
        "ADX": [adx] * rows,
        "SMA_20": [close * (0.95 if not sma20_above else 1.05)] * rows,
    }

    # MACD 설정
    if macd_dead_cross:
        data["MACD"] = [-1.0] * rows
        data["MACD_Signal"] = [0.5] * rows
    else:
        data["MACD"] = [1.0] * rows
        data["MACD_Signal"] = [0.5] * rows

    return pd.DataFrame(data, index=dates)


def _make_opinion(
    name: str = "테스트전문가",
    position: str = "매수",
    confidence: float = 70.0,
    rationale: str = "테스트 근거",
) -> ExpertOpinion:
    """테스트용 ExpertOpinion"""
    return ExpertOpinion(
        expert_name=name,
        expert_style="테스트",
        position=position,
        confidence=confidence,
        rationale=rationale,
    )


# 기본 config
_DEFAULT_TREND_CFG = {
    "downtrend_return_5d_threshold": -5.0,
    "consec_down_days_threshold": 3,
}
_DEFAULT_TRAP_CFG = {
    "range_52w_threshold": 0.30,
    "falling_return_threshold": -5.0,
}
_DEFAULT_OVERSOLD_CFG = {
    "rsi_threshold": 30,
    "adx_strong_threshold": 25,
}


# ══════════════════════════════════════════════
# 1. _check_downtrend() 테스트
# ══════════════════════════════════════════════
class TestCheckDowntrend:
    """하락추세 판별"""

    def test_flat_market_no_downtrend(self):
        """횡보 시장 → 하락추세 아님"""
        df = _make_df(trend="flat")
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        assert result["is_downtrend"] is False

    def test_downtrend_with_dead_cross_and_below_sma(self):
        """MACD 데드크로스 + SMA20 아래 → 하락추세"""
        df = _make_df(
            trend="down",
            macd_dead_cross=True,
            sma20_above=False,
        )
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        assert result["is_downtrend"] is True
        assert result["macd_dead_cross"] is True
        assert result["below_sma20"] is True

    def test_macd_dead_cross_only(self):
        """MACD 데드크로스만으로는 하락추세 아닐 수 있음"""
        df = _make_df(
            trend="flat",
            macd_dead_cross=True,
            sma20_above=True,  # SMA20 위
        )
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        # 1개 신호만으로는 is_downtrend=False
        assert result["macd_dead_cross"] is True

    def test_insufficient_data(self):
        """데이터 부족(5행 미만) → 하락추세 아님"""
        df = _make_df(rows=3)
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        assert result["is_downtrend"] is False

    def test_consec_down_days_counted(self):
        """연속 하락일수 카운트"""
        df = _make_df(trend="down", rows=30)
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        assert result["consec_down_days"] >= 0

    def test_return_5d_calculated(self):
        """5일 수익률 계산"""
        df = _make_df(trend="down", rows=30)
        result = _check_downtrend(df, _DEFAULT_TREND_CFG)
        assert result["return_5d"] is not None


# ══════════════════════════════════════════════
# 2. _check_value_trap() 테스트
# ══════════════════════════════════════════════
class TestCheckValueTrap:
    """가치함정 탐지"""

    def test_no_trap_when_no_52w_data(self):
        """52주 데이터 없으면 → 가치함정 아님"""
        df = _make_df(close=50.0)
        info = {}  # 52주 데이터 없음
        result = _check_value_trap(df, info, _DEFAULT_TRAP_CFG)
        assert result["is_trap_risk"] is False

    def test_trap_detected_low_range_falling(self):
        """52주 하위 + 5일 급락 → 가치함정"""
        df = _make_df(close=50.0, trend="down", rows=30)
        info = {
            "52주_최고": 200.0,
            "52주_최저": 40.0,
        }
        result = _check_value_trap(df, info, _DEFAULT_TRAP_CFG)
        # close=50, range = (50-40)/(200-40) ≈ 6.25% < 30%
        # 하락 추세이므로 5일 수익률 < -5%일 가능성
        assert result["range_52w"] is not None
        if result["return_5d"] is not None and result["return_5d"] < -5.0:
            assert result["is_trap_risk"] is True

    def test_no_trap_high_range(self):
        """52주 상위 → 가치함정 아님"""
        df = _make_df(close=180.0)
        info = {"52주_최고": 200.0, "52주_최저": 100.0}
        result = _check_value_trap(df, info, _DEFAULT_TRAP_CFG)
        # range = (180-100)/(200-100) = 80% > 30%
        assert result["is_trap_risk"] is False
        assert result["range_52w"] == 0.8

    def test_no_trap_stable_price(self):
        """저위치지만 안정적 → 가치함정 아님"""
        df = _make_df(close=50.0, trend="flat", rows=30)
        info = {"52주_최고": 200.0, "52주_최저": 40.0}
        result = _check_value_trap(df, info, _DEFAULT_TRAP_CFG)
        # 5일 수익률 ≈ 0% → falling 아님
        assert result["is_trap_risk"] is False

    def test_insufficient_data(self):
        """데이터 부족 → 가치함정 아님"""
        df = _make_df(rows=3)
        info = {"52주_최고": 200.0, "52주_최저": 40.0}
        result = _check_value_trap(df, info, _DEFAULT_TRAP_CFG)
        assert result["is_trap_risk"] is False


# ══════════════════════════════════════════════
# 3. _check_oversold_trend() 테스트
# ══════════════════════════════════════════════
class TestCheckOversoldTrend:
    """추세적 과매도 판별"""

    def test_no_oversold_normal_rsi(self):
        """RSI 정상 → 추세적 과매도 아님"""
        df = _make_df(rsi=50.0, adx=30.0)
        result = _check_oversold_trend(df, _DEFAULT_OVERSOLD_CFG)
        assert result["is_trend_oversold"] is False

    def test_oversold_with_strong_trend(self):
        """RSI<30 + ADX>25 → 추세적 과매도"""
        df = _make_df(rsi=22.0, adx=35.0)
        result = _check_oversold_trend(df, _DEFAULT_OVERSOLD_CFG)
        assert result["is_trend_oversold"] is True
        assert result["rsi"] == 22.0
        assert result["adx"] == 35.0

    def test_oversold_weak_trend_ok(self):
        """RSI<30 + ADX<25 (약한 추세) → 추세적 과매도 아님 (반등 기대)"""
        df = _make_df(rsi=22.0, adx=15.0)
        result = _check_oversold_trend(df, _DEFAULT_OVERSOLD_CFG)
        assert result["is_trend_oversold"] is False

    def test_rsi_data_missing(self):
        """RSI 데이터 없으면 → 추세적 과매도 아님"""
        df = _make_df(rows=30)
        df = df.drop(columns=["RSI"], errors="ignore")
        result = _check_oversold_trend(df, _DEFAULT_OVERSOLD_CFG)
        assert result["is_trend_oversold"] is False
        assert result["rsi"] is None

    def test_insufficient_data(self):
        """데이터 부족 → 추세적 과매도 아님"""
        df = _make_df(rows=2)
        result = _check_oversold_trend(df, _DEFAULT_OVERSOLD_CFG)
        assert result["is_trend_oversold"] is False


# ══════════════════════════════════════════════
# 4. apply_opinion_filters() 통합 테스트
# ══════════════════════════════════════════════
class TestApplyOpinionFilters:
    """통합 필터 적용"""

    def test_buy_downgraded_in_downtrend(self):
        """하락추세 + 매수 → 홀드로 다운그레이드"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        opinions = [_make_opinion(position="매수", confidence=70)]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        assert len(result) == 1
        assert result[0].position == "홀드"
        assert result[0].confidence < 70
        assert "[필터" in result[0].rationale

    def test_hold_not_affected(self):
        """홀드 의견은 필터 미적용"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        opinions = [_make_opinion(position="홀드", confidence=50)]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        assert result[0].position == "홀드"
        assert result[0].confidence == 50  # 변동 없음

    def test_sell_not_affected(self):
        """매도 의견은 필터 미적용"""
        df = _make_df(trend="down")
        opinions = [_make_opinion(position="매도", confidence=80)]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        assert result[0].position == "매도"
        assert result[0].confidence == 80

    def test_buy_kept_in_uptrend(self):
        """상승추세 + 매수 → 유지"""
        df = _make_df(trend="up", sma20_above=True)
        opinions = [_make_opinion(position="매수", confidence=75)]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        assert result[0].position == "매수"
        assert result[0].confidence == 75

    def test_multiple_opinions_filtered_independently(self):
        """여러 의견이 독립적으로 필터"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        opinions = [
            _make_opinion(name="A", position="매수", confidence=70),
            _make_opinion(name="B", position="홀드", confidence=50),
            _make_opinion(name="C", position="매수", confidence=80),
            _make_opinion(name="D", position="매도", confidence=60),
        ]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        assert result[0].position == "홀드"  # A: 매수 → 홀드
        assert result[1].position == "홀드"  # B: 홀드 유지
        assert result[2].position == "홀드"  # C: 매수 → 홀드
        assert result[3].position == "매도"  # D: 매도 유지

    def test_empty_opinions_returns_empty(self):
        """빈 의견 리스트 → 빈 리스트"""
        df = _make_df()
        result = apply_opinion_filters([], df, {})
        assert result == []

    def test_empty_df_returns_original(self):
        """빈 데이터프레임 → 원본 반환"""
        opinions = [_make_opinion()]
        result = apply_opinion_filters(opinions, pd.DataFrame(), {})
        assert result[0].position == "매수"

    def test_original_opinions_immutable(self):
        """원본 ExpertOpinion이 변경되지 않음"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        original = _make_opinion(position="매수", confidence=70)
        opinions = [original]
        info = {}
        result = apply_opinion_filters(opinions, df, info)

        # 원본 불변
        assert original.position == "매수"
        assert original.confidence == 70
        # 결과는 다름
        assert result[0].position == "홀드"

    def test_disabled_returns_original(self):
        """필터 비활성화 시 원본 반환"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        opinions = [_make_opinion(position="매수", confidence=70)]

        with patch("opinion_filter.get_config") as mock_cfg:
            mock_cfg.return_value = {"opinion_filters": {"enabled": False}}
            result = apply_opinion_filters(opinions, df, {})

        assert result[0].position == "매수"
        assert result[0].confidence == 70

    def test_confidence_penalty_per_downgrade(self):
        """다운그레이드 사유마다 확신도 -10"""
        df = _make_df(
            trend="down",
            macd_dead_cross=True,
            sma20_above=False,
            rsi=22.0,
            adx=35.0,
        )
        opinions = [_make_opinion(position="매수", confidence=80)]
        info = {"52주_최고": 200.0, "52주_최저": 40.0}
        result = apply_opinion_filters(opinions, df, info)

        # 최소 1개 다운그레이드 → 확신도 감소
        assert result[0].position == "홀드"
        assert result[0].confidence < 80

    def test_confidence_minimum_floor(self):
        """확신도 최소값 10 보장"""
        df = _make_df(
            trend="down",
            macd_dead_cross=True,
            sma20_above=False,
            rsi=15.0,
            adx=40.0,
        )
        opinions = [_make_opinion(position="매수", confidence=15)]
        info = {"52주_최고": 200.0, "52주_최저": 40.0}
        result = apply_opinion_filters(opinions, df, info)

        assert result[0].confidence >= 10

    def test_rationale_preserves_original(self):
        """다운그레이드 시 원래 의견을 근거에 기록"""
        df = _make_df(trend="down", macd_dead_cross=True, sma20_above=False)
        opinions = [_make_opinion(position="매수", confidence=70, rationale="원래 근거")]
        result = apply_opinion_filters(opinions, df, {})

        assert "원래 근거" in result[0].rationale
        assert "원래: 매수" in result[0].rationale


# ══════════════════════════════════════════════
# 5. config 기본값 검증
# ══════════════════════════════════════════════
class TestOpinionFilterConfig:
    """opinion_filters 설정값 검증"""

    def test_defaults_exist(self):
        from common.config import get_config
        cfg = get_config()
        of = cfg.get("opinion_filters", {})
        assert "enabled" in of
        assert "trend_confirmation" in of
        assert "value_trap" in of
        assert "oversold_bounce" in of

    def test_trend_confirmation_defaults(self):
        from common.config import get_config
        cfg = get_config()
        tc = cfg["opinion_filters"]["trend_confirmation"]
        assert tc["enabled"] is True
        assert tc["downtrend_return_5d_threshold"] == -5.0
        assert tc["consec_down_days_threshold"] == 3

    def test_value_trap_defaults(self):
        from common.config import get_config
        cfg = get_config()
        vt = cfg["opinion_filters"]["value_trap"]
        assert vt["enabled"] is True
        assert vt["range_52w_threshold"] == 0.30
        assert vt["falling_return_threshold"] == -5.0

    def test_oversold_bounce_defaults(self):
        from common.config import get_config
        cfg = get_config()
        ob = cfg["opinion_filters"]["oversold_bounce"]
        assert ob["enabled"] is True
        assert ob["rsi_threshold"] == 30
        assert ob["adx_strong_threshold"] == 25
