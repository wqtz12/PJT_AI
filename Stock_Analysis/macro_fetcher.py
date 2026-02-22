"""
거시경제 지표 수집 모듈

yfinance를 통해 주요 매크로 지표를 수집하고
시장 환경 분석 결과를 제공합니다.

수집 대상: VIX, 10Y 국채, S&P500, WTI 유가, 금, 달러 인덱스
"""
import logging
from datetime import datetime
from typing import Optional, Dict

import numpy as np
import pandas as pd
import yfinance as yf

from common.config import get_config

logger = logging.getLogger(__name__)

_cfg = get_config()
_macro_cfg = _cfg.get("macro", {})
_VIX_LEVELS = _macro_cfg.get("vix_levels", {"low": 15, "normal": 20, "elevated": 25, "high": 35})
_TREND_WINDOW = _macro_cfg.get("trend_window", 5)
_TREND_THRESHOLD = _macro_cfg.get("trend_threshold_pct", 1.0)
_FETCH_PERIOD = _macro_cfg.get("fetch_period", "3mo")
_INDICATORS_CFG = _macro_cfg.get("indicators", {
    "vix": {"ticker": "^VIX", "name": "VIX (변동성지수)"},
    "treasury_10y": {"ticker": "^TNX", "name": "10년 국채금리"},
    "sp500": {"ticker": "^GSPC", "name": "S&P 500"},
    "oil": {"ticker": "CL=F", "name": "WTI 원유"},
    "gold": {"ticker": "GC=F", "name": "금"},
    "dollar": {"ticker": "DX-Y.NYB", "name": "달러 인덱스"},
})


def _compute_trend(series: pd.Series, window: int = None) -> str:
    """
    최근 N일 추세 판단

    Returns: "상승" / "하락" / "안정"
    """
    window = window or _TREND_WINDOW
    if len(series) < window + 1:
        return "안정"

    recent = series.iloc[-window:]
    first_val = recent.iloc[0]
    last_val = recent.iloc[-1]

    if first_val == 0:
        return "안정"

    change_pct = (last_val - first_val) / abs(first_val) * 100
    threshold = _TREND_THRESHOLD

    if change_pct > threshold:
        return "상승"
    elif change_pct < -threshold:
        return "하락"
    return "안정"


def _classify_vix_level(vix_value: float) -> str:
    """
    VIX 수준 분류

    Returns: "저변동" / "보통" / "경계" / "고변동" / "극단"
    """
    if vix_value <= _VIX_LEVELS.get("low", 15):
        return "저변동"
    elif vix_value <= _VIX_LEVELS.get("normal", 20):
        return "보통"
    elif vix_value <= _VIX_LEVELS.get("elevated", 25):
        return "경계"
    elif vix_value <= _VIX_LEVELS.get("high", 35):
        return "고변동"
    return "극단"


def _fetch_single_indicator(ticker: str, name: str, period: str = None) -> Optional[dict]:
    """
    단일 매크로 지표 수집

    Returns:
        dict with {current, change_pct, avg_20d, deviation_from_avg, trend}
        or None on failure
    """
    period = period or _FETCH_PERIOD
    try:
        data = yf.Ticker(ticker).history(period=period)
        if data is None or data.empty or len(data) < 2:
            logger.warning(f"매크로 지표 [{name}] 데이터 없음: {ticker}")
            return None

        close = data["Close"]
        current = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        change_pct = (current - prev_close) / prev_close * 100 if prev_close != 0 else 0

        # 20일 이동평균
        avg_window = min(20, len(close) - 1)
        avg_20d = float(close.iloc[-avg_window:].mean()) if avg_window > 0 else current
        deviation = (current - avg_20d) / avg_20d * 100 if avg_20d != 0 else 0

        trend = _compute_trend(close)

        result = {
            "current": current,
            "prev_close": prev_close,
            "change_pct": round(change_pct, 2),
            "avg_20d": round(avg_20d, 2),
            "deviation_from_avg": round(deviation, 2),
            "trend": trend,
            "name": name,
        }

        # VIX에만 level 추가
        if "VIX" in ticker.upper():
            result["level"] = _classify_vix_level(current)

        return result

    except Exception as e:
        logger.warning(f"매크로 지표 [{name}] 수집 실패: {e}")
        return None


def fetch_macro_indicators() -> Dict[str, Optional[dict]]:
    """
    전체 매크로 지표 수집

    Returns:
        {
            "vix": {...}, "treasury_10y": {...}, "sp500": {...},
            "oil": {...}, "gold": {...}, "dollar": {...},
            "_fetch_time": str, "_available_count": int,
        }
    """
    result = {}
    available = 0

    for key, cfg in _INDICATORS_CFG.items():
        ticker = cfg.get("ticker", "")
        name = cfg.get("name", key)
        data = _fetch_single_indicator(ticker, name)
        result[key] = data
        if data is not None:
            available += 1

    result["_fetch_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["_available_count"] = available

    logger.info(f"매크로 지표 수집 완료: {available}/{len(_INDICATORS_CFG)}개")
    return result


def compute_macro_summary(macro_data: dict) -> dict:
    """
    매크로 환경 종합 판단

    Returns:
        {
            "시장_환경": "위험선호" / "중립" / "위험회피",
            "환경_점수": int (-5 ~ +5),
            "VIX_상태": str,
            "금리_방향": str,
            "달러_방향": str,
            "시장_추세": str,
        }
    """
    if not macro_data or macro_data.get("_available_count", 0) == 0:
        return {
            "시장_환경": "판단 불가",
            "환경_점수": 0,
            "VIX_상태": "N/A",
            "금리_방향": "N/A",
            "달러_방향": "N/A",
            "시장_추세": "N/A",
        }

    score = 0  # 양수 = 위험선호(risk-on), 음수 = 위험회피(risk-off)

    # VIX 판단
    vix = macro_data.get("vix")
    vix_status = "N/A"
    if vix:
        level = vix.get("level", "보통")
        vix_status = f"{level}({vix['current']:.1f})"
        level_scores = {"저변동": 2, "보통": 1, "경계": -1, "고변동": -2, "극단": -3}
        score += level_scores.get(level, 0)

    # S&P500 추세
    sp = macro_data.get("sp500")
    market_trend = "N/A"
    if sp:
        trend = sp.get("trend", "안정")
        market_trend = f"{trend}({sp['current']:,.0f})"
        trend_scores = {"상승": 1, "안정": 0, "하락": -1}
        score += trend_scores.get(trend, 0)

    # 금리 방향
    rate = macro_data.get("treasury_10y")
    rate_dir = "N/A"
    if rate:
        trend = rate.get("trend", "안정")
        rate_dir = f"{trend}({rate['current']:.2f}%)"
        # 금리 상승 = 위험 회피, 하락 = 위험 선호
        rate_scores = {"상승": -1, "안정": 0, "하락": 1}
        score += rate_scores.get(trend, 0)

    # 달러 방향
    dollar = macro_data.get("dollar")
    dollar_dir = "N/A"
    if dollar:
        trend = dollar.get("trend", "안정")
        dollar_dir = f"{trend}({dollar['current']:.1f})"
        # 달러 강세 = 신흥시장/원자재 부정, 약세 = 위험 선호
        dollar_scores = {"상승": -1, "안정": 0, "하락": 1}
        score += dollar_scores.get(trend, 0)

    # 금 (안전자산)
    gold = macro_data.get("gold")
    if gold:
        trend = gold.get("trend", "안정")
        gold_scores = {"상승": -1, "안정": 0, "하락": 1}
        score += gold_scores.get(trend, 0)

    # 점수 클램핑
    score = max(-5, min(5, score))

    if score >= 2:
        env = "위험선호"
    elif score <= -2:
        env = "위험회피"
    else:
        env = "중립"

    return {
        "시장_환경": env,
        "환경_점수": score,
        "VIX_상태": vix_status,
        "금리_방향": rate_dir,
        "달러_방향": dollar_dir,
        "시장_추세": market_trend,
    }


def enrich_company_info_with_macro(company_info: dict, macro_data: dict) -> dict:
    """
    company_info에 _macro 키 주입

    전문가 전략이 company_info.get("_macro")로 접근
    macro_data가 None이거나 비어있으면 주입하지 않음
    """
    if not macro_data or macro_data.get("_available_count", 0) == 0:
        return company_info

    summary = compute_macro_summary(macro_data)

    company_info["_macro"] = {
        "vix": macro_data.get("vix"),
        "treasury_10y": macro_data.get("treasury_10y"),
        "sp500": macro_data.get("sp500"),
        "oil": macro_data.get("oil"),
        "gold": macro_data.get("gold"),
        "dollar": macro_data.get("dollar"),
        "환경_점수": summary["환경_점수"],
        "시장_환경": summary["시장_환경"],
    }

    return company_info
