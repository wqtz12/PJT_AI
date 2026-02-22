"""
전문가 전략 공통 상수 및 확신도 계산 통합 모듈

[설정 소스]
  config.yaml → common/config.py → 이 모듈에서 모듈-레벨 상수로 바인딩
  config.yaml 없으면 내장 기본값 사용 (하위 호환)

[임계값 통일 근거]
- RSI: 전통적 과매수/과매도 기준 (30/70) + 극단값 (25/75)
  - 모멘텀: 방향성 모멘텀이므로 45-60 중립 구간
  - 역발상: 극단 반전이므로 25/35/65/75
  → 역할별 차이는 유지하되, 과매수/과매도 기준선은 통일

- 볼린저밴드: %B 기준
  - 하단 이탈: < 0, 하단 근접: < 0.15
  - 상단 이탈: > 1.0, 상단 근접: > 0.85

- ADX 추세 강도: 20 (약한 추세) / 30 (강한 추세) - 업계 표준

- 포지션 결정: score >= 3 매수, score <= -3 매도 (전문가 공통)

[확신도 공식 통일]
  - 매수: min(MAX_CONFIDENCE, BASE + |score| * WEIGHT)
  - 매도: min(MAX_CONFIDENCE, BASE + |score| * WEIGHT)
  - 홀드: BASE_HOLD + |score| * WEIGHT_HOLD
  - 데이터 부족: MIN_CONFIDENCE (10%)
"""
from common.config import get_config

_cfg = get_config()
_t = _cfg.get("thresholds", {})
_c = _cfg.get("confidence", {})

# ─── RSI 임계값 ───
_rsi = _t.get("rsi", {})
RSI_OVERBOUGHT = _rsi.get("overbought", 70)
RSI_OVERSOLD = _rsi.get("oversold", 30)
RSI_EXTREME_HIGH = _rsi.get("extreme_high", 75)
RSI_EXTREME_LOW = _rsi.get("extreme_low", 25)
RSI_MOMENTUM_HIGH = _rsi.get("momentum_high", 60)
RSI_MOMENTUM_LOW = _rsi.get("momentum_low", 45)
RSI_CONTRARIAN_HIGH = _rsi.get("contrarian_high", 65)
RSI_CONTRARIAN_LOW = _rsi.get("contrarian_low", 35)

# ─── 볼린저밴드 임계값 ───
_bb = _t.get("bollinger", {})
BB_UPPER_BREACH = _bb.get("upper_breach", 1.0)
BB_UPPER_NEAR = _bb.get("upper_near", 0.85)
BB_LOWER_BREACH = _bb.get("lower_breach", 0.0)
BB_LOWER_NEAR = _bb.get("lower_near", 0.15)
BB_SQUEEZE_RATIO = _bb.get("squeeze_ratio", 0.6)
BB_EXPAND_RATIO = _bb.get("expand_ratio", 1.5)

# ─── ADX 추세 강도 ───
_adx = _t.get("adx", {})
ADX_STRONG = _adx.get("strong", 30)
ADX_MODERATE = _adx.get("moderate", 20)

# ─── 이동평균 ───
_ind = _cfg.get("indicators", {})
MA_SHORT_WINDOWS = _ind.get("sma_windows", [5, 20, 60])[:3]
MA_LONG_WINDOW = _ind.get("sma_windows", [5, 20, 60, 120])[-1] if len(_ind.get("sma_windows", [])) >= 4 else 120

# ─── 스토캐스틱 ───
_stoch = _t.get("stochastic", {})
STOCH_OVERBOUGHT = _stoch.get("overbought", 80)
STOCH_OVERSOLD = _stoch.get("oversold", 20)

# ─── 포지션 결정 임계값 (전문가 공통) ───
_score = _t.get("score", {})
SCORE_BUY_THRESHOLD = _score.get("buy_threshold", 3)
SCORE_SELL_THRESHOLD = _score.get("sell_threshold", -3)
SCORE_SELL_THRESHOLD_VALUE = _score.get("sell_threshold_value", -2)

# ─── 확신도 공식 (통일) ───
CONFIDENCE_MAX = _c.get("max", 90)
CONFIDENCE_BASE_BUY = _c.get("base_buy", 50)
CONFIDENCE_BASE_SELL = _c.get("base_sell", 50)
CONFIDENCE_BASE_HOLD = _c.get("base_hold", 35)
CONFIDENCE_WEIGHT_BUY = _c.get("weight_buy", 7)
CONFIDENCE_WEIGHT_SELL = _c.get("weight_sell", 7)
CONFIDENCE_WEIGHT_HOLD = _c.get("weight_hold", 5)
CONFIDENCE_NO_DATA = _c.get("no_data", 10)

# ─── ATR 배수 (목표가/손절가 계산용) ───
_atr = _t.get("atr", {})
ATR_SELL_MULTIPLIER = _atr.get("sell_multiplier", 3.0)
ATR_STOP_MULTIPLIER = _atr.get("stop_multiplier", 2.0)
ATR_DEFAULT_RATIO = _atr.get("default_ratio", 0.05)

# ─── 거래량 ───
_vol = _t.get("volume", {})
VOLUME_SURGE_RATIO = _vol.get("surge_ratio", 2.0)
VOLUME_ACTIVE_RATIO = _vol.get("active_ratio", 1.3)
VOLUME_DRY_RATIO = _vol.get("dry_ratio", 0.5)

# ─── 52주 범위 ───
_r52 = _t.get("range_52w", {})
RANGE_52W_LOW_ZONE = _r52.get("low_zone", 0.25)
RANGE_52W_MID_LOW = _r52.get("mid_low", 0.40)
RANGE_52W_HIGH_ZONE = _r52.get("high_zone", 0.80)

# ─── 수익률 ───
_ret = _t.get("return_5d", {})
RETURN_5D_STRONG = _ret.get("strong", 5.0)
RETURN_5D_MODERATE = _ret.get("moderate", 2.0)
RETURN_5D_DECLINE = _ret.get("decline", -2.0)
RETURN_5D_CRASH = _ret.get("crash", -5.0)


# ─── 일목균형표 임계값 ───
_ichimoku = _t.get("ichimoku", {})
ICHIMOKU_CLOUD_THICK_RATIO = _ichimoku.get("cloud_thick_ratio", 0.02)
ICHIMOKU_CLOUD_THIN_RATIO = _ichimoku.get("cloud_thin_ratio", 0.005)
ICHIMOKU_ANGLE_STRONG = _ichimoku.get("angle_strong", 26)
ICHIMOKU_ANGLE_FLAT = _ichimoku.get("angle_flat", 10)
ICHIMOKU_ANGLE_WINDOW = _ichimoku.get("angle_window", 5)

# ─── 매크로/감성 통합 임계값 ───
_macro_cfg = _cfg.get("macro", {})
MACRO_SCORE_IMPACT_MAX = _macro_cfg.get("score_impact_max", 3)

_sent_cfg = _cfg.get("sentiment", {})
SENTIMENT_SCORE_IMPACT_MAX = _sent_cfg.get("score_impact_max", 2)
SENTIMENT_BULLISH_THRESHOLD = _sent_cfg.get("bullish_threshold", 0.3)
SENTIMENT_BEARISH_THRESHOLD = _sent_cfg.get("bearish_threshold", -0.3)
SENTIMENT_EXTREME_BULLISH = _sent_cfg.get("extreme_bullish", 0.6)
SENTIMENT_EXTREME_BEARISH = _sent_cfg.get("extreme_bearish", -0.6)
SENTIMENT_MIN_CONFIDENCE = 0.3  # 감성 신뢰도 최소치 (이하는 무시)


def get_macro_context(company_info: dict):
    """company_info에서 _macro 추출 (없으면 None)"""
    if not company_info:
        return None
    return company_info.get("_macro")


def get_sentiment_context(company_info: dict):
    """company_info에서 _sentiment 추출 (없으면 None)"""
    if not company_info:
        return None
    return company_info.get("_sentiment")


def calc_confidence(score: int, position: str, analyzed_count: int = 1) -> float:
    """
    통일된 확신도 계산 공식

    Args:
        score: 전문가 점수 (양수=매수, 음수=매도)
        position: "매수" / "매도" / "홀드"
        analyzed_count: 분석에 사용된 지표 수 (0이면 데이터 부족)

    Returns:
        float: 확신도 (0-100%)
    """
    if analyzed_count == 0:
        return CONFIDENCE_NO_DATA

    abs_score = abs(score)

    if position == "매수":
        return min(CONFIDENCE_MAX, CONFIDENCE_BASE_BUY + abs_score * CONFIDENCE_WEIGHT_BUY)
    elif position == "매도":
        return min(CONFIDENCE_MAX, CONFIDENCE_BASE_SELL + abs_score * CONFIDENCE_WEIGHT_SELL)
    else:  # 홀드
        return CONFIDENCE_BASE_HOLD + abs_score * CONFIDENCE_WEIGHT_HOLD
