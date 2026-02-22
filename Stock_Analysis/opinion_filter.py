"""
전문가 의견 후처리 필터 모듈 (P1-3)

개별 전문가 코드를 수정하지 않고, 전문가 결과물(ExpertOpinion)을 후처리하여
하락추세 매수 경고, 가치함정 탐지, 과매도 반등 검증을 수행합니다.

사용법:
    from opinion_filter import apply_opinion_filters
    filtered = apply_opinion_filters(expert_opinions, df, company_info)
"""
import logging
from dataclasses import replace
from typing import Optional

import pandas as pd
import numpy as np

from common.models import ExpertOpinion
from common.config import get_config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 내부 분석 함수
# ──────────────────────────────────────────────

def _safe_get(row, col, default=None):
    """DataFrame row에서 안전하게 값 추출"""
    try:
        val = row.get(col, default) if hasattr(row, 'get') else row[col]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return val
    except (KeyError, IndexError, TypeError):
        return default


def _check_downtrend(df: pd.DataFrame, cfg: dict) -> dict:
    """
    하락추세 판별

    Returns:
        dict: {
            "is_downtrend": bool,
            "macd_dead_cross": bool,
            "below_sma20": bool,
            "return_5d": float | None,
            "consec_down_days": int,
        }
    """
    result = {
        "is_downtrend": False,
        "macd_dead_cross": False,
        "below_sma20": False,
        "return_5d": None,
        "consec_down_days": 0,
    }

    if len(df) < 5:
        return result

    latest = df.iloc[-1]

    # MACD 데드크로스 체크
    macd = _safe_get(latest, "MACD")
    macd_signal = _safe_get(latest, "MACD_Signal")
    if macd is not None and macd_signal is not None:
        result["macd_dead_cross"] = bool(macd < macd_signal)

    # SMA_20 아래 체크
    sma20 = _safe_get(latest, "SMA_20")
    close = _safe_get(latest, "Close")
    if sma20 is not None and close is not None:
        result["below_sma20"] = bool(close < sma20)

    # 5일 수익률
    if len(df) > 5:
        close_now = df.iloc[-1]["Close"]
        close_5d = df.iloc[-6]["Close"]
        if close_5d > 0:
            ret_5d = (close_now / close_5d - 1) * 100
            result["return_5d"] = round(ret_5d, 2)

    # 연속 하락일수
    consec = 0
    for i in range(1, min(len(df), 10)):
        if df.iloc[-i]["Close"] < df.iloc[-(i+1)]["Close"]:
            consec += 1
        else:
            break
    result["consec_down_days"] = consec

    # 하락추세 종합 판단
    ret_threshold = cfg.get("downtrend_return_5d_threshold", -5.0)
    consec_threshold = cfg.get("consec_down_days_threshold", 3)

    downtrend_signals = 0
    if result["macd_dead_cross"]:
        downtrend_signals += 1
    if result["below_sma20"]:
        downtrend_signals += 1
    if result["return_5d"] is not None and result["return_5d"] < ret_threshold:
        downtrend_signals += 1
    if result["consec_down_days"] >= consec_threshold:
        downtrend_signals += 1

    # 2개 이상 하락 신호 → 하락추세
    result["is_downtrend"] = downtrend_signals >= 2

    return result


def _check_value_trap(df: pd.DataFrame, company_info: dict, cfg: dict) -> dict:
    """
    가치함정 위험 판별

    Returns:
        dict: {
            "is_trap_risk": bool,
            "range_52w": float | None,
            "falling_into_low": bool,
            "return_5d": float | None,
        }
    """
    result = {
        "is_trap_risk": False,
        "range_52w": None,
        "falling_into_low": False,
        "return_5d": None,
    }

    if len(df) < 5:
        return result

    # 52주 범위 위치
    high_52w = company_info.get("52주_최고")
    low_52w = company_info.get("52주_최저")
    close = df.iloc[-1]["Close"]

    if high_52w and low_52w and high_52w > low_52w:
        range_pct = (close - low_52w) / (high_52w - low_52w)
        result["range_52w"] = round(range_pct, 4)
    else:
        return result  # 52주 데이터 없으면 스킵

    # 5일 수익률
    if len(df) > 5:
        close_5d = df.iloc[-6]["Close"]
        if close_5d > 0:
            ret_5d = (close / close_5d - 1) * 100
            result["return_5d"] = round(ret_5d, 2)

    # 가치함정 판단
    range_threshold = cfg.get("range_52w_threshold", 0.30)
    falling_threshold = cfg.get("falling_return_threshold", -5.0)

    if result["range_52w"] is not None and result["range_52w"] < range_threshold:
        if result["return_5d"] is not None and result["return_5d"] < falling_threshold:
            result["is_trap_risk"] = True
            result["falling_into_low"] = True

    return result


def _check_oversold_trend(df: pd.DataFrame, cfg: dict) -> dict:
    """
    추세적 과매도 판별 (반등X, 추세 하락)

    Returns:
        dict: {
            "is_trend_oversold": bool,
            "rsi": float | None,
            "adx": float | None,
            "rsi_rising": bool,
        }
    """
    result = {
        "is_trend_oversold": False,
        "rsi": None,
        "adx": None,
        "rsi_rising": False,
    }

    if len(df) < 3:
        return result

    latest = df.iloc[-1]

    # RSI
    rsi = _safe_get(latest, "RSI_14")
    result["rsi"] = float(rsi) if rsi is not None else None

    # ADX
    adx = _safe_get(latest, "ADX")
    result["adx"] = float(adx) if adx is not None else None

    # RSI 상승 추세 (최근 3일)
    if len(df) >= 3 and "RSI_14" in df.columns:
        rsi_vals = df["RSI_14"].iloc[-3:].dropna()
        if len(rsi_vals) >= 2:
            result["rsi_rising"] = bool(rsi_vals.iloc[-1] > rsi_vals.iloc[0])

    # 추세적 과매도 판단
    rsi_threshold = cfg.get("rsi_threshold", 30)
    adx_threshold = cfg.get("adx_strong_threshold", 25)

    if result["rsi"] is not None and result["rsi"] < rsi_threshold:
        if result["adx"] is not None and result["adx"] > adx_threshold:
            # RSI 과매도 + 강한 추세 = 추세적 하락
            result["is_trend_oversold"] = True

    return result


# ──────────────────────────────────────────────
# 메인 필터 함수
# ──────────────────────────────────────────────

def apply_opinion_filters(
    opinions: list,
    df: pd.DataFrame,
    company_info: dict,
) -> list:
    """
    전문가 의견에 후처리 필터 적용

    필터 1: 하락추세 매수 경고 (Trend Confirmation)
    필터 2: 가치함정 경고 (Value Trap)
    필터 3: 과매도 반등 검증 (Oversold Bounce)

    Args:
        opinions: ExpertOpinion 리스트
        df: OHLCV + 기술적 지표 데이터프레임
        company_info: 기업 정보 dict

    Returns:
        list[ExpertOpinion]: 필터 적용된 의견 (새 객체, 원본 불변)
    """
    cfg = get_config().get("opinion_filters", {})
    if not cfg.get("enabled", True):
        return opinions

    if not opinions or df.empty:
        return opinions

    # 사전 분석 (모든 의견에 공통)
    trend_cfg = cfg.get("trend_confirmation", {})
    trap_cfg = cfg.get("value_trap", {})
    oversold_cfg = cfg.get("oversold_bounce", {})

    downtrend = _check_downtrend(df, trend_cfg) if trend_cfg.get("enabled", True) else None
    value_trap = _check_value_trap(df, company_info, trap_cfg) if trap_cfg.get("enabled", True) else None
    oversold = _check_oversold_trend(df, oversold_cfg) if oversold_cfg.get("enabled", True) else None

    filtered = []
    for opinion in opinions:
        new_opinion = _apply_filters_to_opinion(
            opinion, downtrend, value_trap, oversold,
        )
        filtered.append(new_opinion)

    return filtered


def _apply_filters_to_opinion(
    opinion: ExpertOpinion,
    downtrend: Optional[dict],
    value_trap: Optional[dict],
    oversold: Optional[dict],
) -> ExpertOpinion:
    """
    개별 의견에 필터 적용

    매수 의견만 필터 대상 (홀드/매도는 그대로 통과)
    """
    if opinion.position != "매수":
        return opinion

    downgrades = []

    # 필터 1: 하락추세 매수 경고
    if downtrend and downtrend["is_downtrend"]:
        reasons = []
        if downtrend["macd_dead_cross"]:
            reasons.append("MACD 데드크로스")
        if downtrend["below_sma20"]:
            reasons.append("20일선 하향")
        if downtrend["return_5d"] is not None and downtrend["return_5d"] < -5:
            reasons.append(f"5일 {downtrend['return_5d']:.1f}%")
        if downtrend["consec_down_days"] >= 3:
            reasons.append(f"{downtrend['consec_down_days']}일 연속하락")

        downgrades.append(f"[필터:하락추세] {', '.join(reasons)} → 매수 보류")

    # 필터 2: 가치함정 경고
    if value_trap and value_trap["is_trap_risk"]:
        range_str = f"52주 {value_trap['range_52w']*100:.0f}%" if value_trap["range_52w"] else ""
        ret_str = f"5일 {value_trap['return_5d']:.1f}%" if value_trap["return_5d"] else ""
        downgrades.append(f"[필터:가치함정] {range_str} + {ret_str} → 하강 중 저점 주의")

    # 필터 3: 추세적 과매도
    if oversold and oversold["is_trend_oversold"]:
        rsi_str = f"RSI {oversold['rsi']:.1f}" if oversold["rsi"] else ""
        adx_str = f"ADX {oversold['adx']:.1f}" if oversold["adx"] else ""
        downgrades.append(f"[필터:추세과매도] {rsi_str} + {adx_str}>25 → 추세적 하락, 반등 미확인")

    if not downgrades:
        return opinion

    # 다운그레이드 적용
    filter_text = " | ".join(downgrades)
    new_rationale = f"{opinion.rationale}\n⚠ {filter_text}\n(원래: {opinion.position}, 확신도 {opinion.confidence:.0f}%)"

    # 확신도 감소 (다운그레이드당 -10)
    confidence_penalty = len(downgrades) * 10
    new_confidence = max(10, opinion.confidence - confidence_penalty)

    logger.info(
        f"  🔽 [{opinion.expert_name}] 매수→홀드 다운그레이드: {filter_text}"
    )

    return replace(
        opinion,
        position="홀드",
        confidence=new_confidence,
        rationale=new_rationale,
    )
