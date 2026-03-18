"""
전문가 1: 추세추종 전문가 (Trend Follower)
- 이동평균 배열, ADX 추세 강도, MACD 방향으로 판단
- 거래량 확인 돌파 (Livermore 원칙) - v2 추가
- 추세 방향에 순응하는 전략
- NaN 명시적 처리: 지표 미계산 시 해당 항목 스킵
- 매크로/감성 컨텍스트 반영 (Phase 4)
"""
import pandas as pd
import numpy as np
from common.models import ExpertOpinion
from common.constants import (
    ADX_STRONG, ADX_MODERATE,
    SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD,
    ATR_SELL_MULTIPLIER, ATR_STOP_MULTIPLIER, ATR_DEFAULT_RATIO,
    VOLUME_SURGE_RATIO, VOLUME_ACTIVE_RATIO,
    calc_confidence,
    get_macro_context, get_sentiment_context,
    MACRO_SCORE_IMPACT_MAX,
    SENTIMENT_SCORE_IMPACT_MAX,
    SENTIMENT_BULLISH_THRESHOLD, SENTIMENT_BEARISH_THRESHOLD,
    SENTIMENT_MIN_CONFIDENCE,
)
from common.split_calculator import (
    calc_split_buy_prices, calc_split_sell_prices,
    extract_ichimoku_levels, extract_ichimoku_angles,
)


def _safe_get(row, name):
    """지표값 안전 추출 - NaN/None → None 반환"""
    val = row.get(name, None)
    if val is None:
        return None
    try:
        if np.isnan(val) or np.isinf(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


class TrendFollower:
    """추세추종 분석가 - 이동평균/ADX/MACD 기반"""

    NAME = "추세추종 전문가"
    STYLE = "이동평균 배열 + ADX 추세 강도 + MACD 방향 기반 순추세 매매"
    EXPECTED_COUNT = 4  # MA배열, ADX, MACD, 120일선

    @staticmethod
    def analyze(df: pd.DataFrame, company_info: dict) -> ExpertOpinion:
        latest = df.iloc[-1]
        price = latest["Close"]

        # 필요 지표 추출 (NaN → None)
        sma5 = _safe_get(latest, "SMA_5")
        sma20 = _safe_get(latest, "SMA_20")
        sma60 = _safe_get(latest, "SMA_60")
        sma120 = _safe_get(latest, "SMA_120")
        adx = _safe_get(latest, "ADX")
        macd = _safe_get(latest, "MACD")
        macd_sig = _safe_get(latest, "MACD_Signal")
        atr = _safe_get(latest, "ATR")

        score = 0
        reasons = []
        indicators = []
        analyzed_count = 0  # 실제 분석에 사용된 지표 수

        # 1) 이동평균 배열 판정 (+/-3)
        if all(v is not None for v in [sma5, sma20, sma60]):
            analyzed_count += 1
            if price > sma5 > sma20 > sma60:
                score += 3
                reasons.append("정배열(5>20>60) → 강한 상승 추세")
            elif price > sma5 > sma20:
                score += 2
                reasons.append("단기 정배열(5>20) → 상승 추세 초입")
            elif price < sma5 < sma20 < sma60:
                score -= 3
                reasons.append("역배열(5<20<60) → 강한 하락 추세")
            elif price < sma5 < sma20:
                score -= 2
                reasons.append("단기 역배열(5<20) → 하락 추세 초입")
            else:
                reasons.append("이동평균 혼조 → 뚜렷한 추세 없음")
            indicators.append(f"SMA5={sma5:.2f} SMA20={sma20:.2f} SMA60={sma60:.2f}")
        else:
            reasons.append("[이동평균] 데이터 부족 → 미분석")

        # 2) 거래량 확인 돌파 - Livermore 원칙 (추세 보정)
        vol = _safe_get(latest, "Volume")
        obv = _safe_get(latest, "OBV")
        if vol is not None and "Volume" in df.columns and len(df) >= 20:
            vol_sma20 = df["Volume"].iloc[-20:].mean()
            if vol_sma20 > 0:
                vol_ratio = vol / vol_sma20
                if score >= 2 and vol_ratio >= VOLUME_SURGE_RATIO:
                    score += 1
                    reasons.append(f"[거래량] 상승돌파 + 거래량 {vol_ratio:.1f}배 급증 → 진짜 돌파 (Livermore)")
                elif score >= 2 and vol_ratio < VOLUME_ACTIVE_RATIO:
                    score -= 1
                    reasons.append(f"[거래량] 상승돌파 + 거래량 {vol_ratio:.1f}배 부족 → 가짜 돌파 주의")
                elif score <= -2 and vol_ratio >= VOLUME_SURGE_RATIO:
                    score -= 1
                    reasons.append(f"[거래량] 하락 + 거래량 {vol_ratio:.1f}배 급증 → 투매 가속")
                indicators.append(f"거래량비={vol_ratio:.1f}x")

        # 3) ADX 추세 강도 (+/-2)
        if adx is not None:
            analyzed_count += 1
            if adx > ADX_STRONG:
                score += 2 if score > 0 else -2
                reasons.append(f"ADX {adx:.1f} → 매우 강한 추세")
            elif adx > ADX_MODERATE:
                score += 1 if score > 0 else -1
                reasons.append(f"ADX {adx:.1f} → 추세 형성 중")
            else:
                reasons.append(f"ADX {adx:.1f} → 추세 약함/횡보")
            indicators.append(f"ADX={adx:.1f}")
        else:
            reasons.append("[ADX] 데이터 부족 → 미분석")

        # 4) MACD 크로스 (+/-2)
        if macd is not None and macd_sig is not None:
            analyzed_count += 1
            if macd > macd_sig and macd > 0:
                score += 2
                reasons.append("MACD 골든크로스 + 양수 영역 → 강한 매수")
            elif macd > macd_sig:
                score += 1
                reasons.append("MACD 골든크로스 → 매수 전환")
            elif macd < macd_sig and macd < 0:
                score -= 2
                reasons.append("MACD 데드크로스 + 음수 영역 → 강한 매도")
            elif macd < macd_sig:
                score -= 1
                reasons.append("MACD 데드크로스 → 매도 전환")
            indicators.append(f"MACD={macd:.4f} Signal={macd_sig:.4f}")
        else:
            reasons.append("[MACD] 데이터 부족 → 미분석")

        # 5) 120일선 대비 위치 (+/-1)
        if sma120 is not None:
            analyzed_count += 1
            if price > sma120:
                score += 1
                reasons.append("120일선 위 → 장기 상승 추세")
            else:
                score -= 1
                reasons.append("120일선 아래 → 장기 하락 추세")

        # ─── 일목균형표 보조 확인 (구름 위/아래 ±1) ───
        cloud_top = _safe_get(latest, "Ichimoku_CloudTop")
        cloud_bottom = _safe_get(latest, "Ichimoku_CloudBottom")
        if cloud_top is not None and cloud_bottom is not None:
            if price > cloud_top:
                score += 1
                reasons.append("[일목] 구름 위 → 추세 상승 확인 (+1)")
            elif price < cloud_bottom:
                score -= 1
                reasons.append("[일목] 구름 아래 → 추세 하락 확인 (-1)")

        # ─── 매크로 환경 반영 (최대 ±2점) ───
        macro = get_macro_context(company_info)
        if macro is not None:
            vix = macro.get("vix")
            rate = macro.get("treasury_10y")

            if vix and vix.get("level") in ("고변동", "극단"):
                # VIX 고변동/극단 → 추세 신뢰도 하락 (0 방향으로 축소)
                if score > 0:
                    score -= 1
                    reasons.append(f"[매크로] VIX {vix.get('level')} → 추세 신뢰도 ↓ (-1)")
                elif score < 0:
                    score += 1
                    reasons.append(f"[매크로] VIX {vix.get('level')} → 추세 신뢰도 ↓ (+1)")
            elif vix and vix.get("level") == "저변동":
                # VIX 저변동 → 기존 추세 방향 강화
                if score > 0:
                    score += 1
                    reasons.append("[매크로] VIX 저변동 → 추세 안정 강화 (+1)")
                elif score < 0:
                    score -= 1
                    reasons.append("[매크로] VIX 저변동 → 추세 안정 강화 (-1)")

            if rate and rate.get("trend") == "상승" and score > 0:
                score -= 1
                reasons.append("[매크로] 금리 상승 + 상승추세 → 상승 부담 (-1)")

        # ─── 감성 반영 (최대 ±1점) ───
        sentiment = get_sentiment_context(company_info)
        if sentiment is not None and sentiment.get("confidence", 0) >= SENTIMENT_MIN_CONFIDENCE:
            sent_score = sentiment.get("score", 0)
            if sent_score >= SENTIMENT_BULLISH_THRESHOLD and score > 0:
                score += 1
                reasons.append(f"[감성] 뉴스 긍정({sent_score:.2f}) → 추세 확인 (+1)")
            elif sent_score <= SENTIMENT_BEARISH_THRESHOLD and score < 0:
                score -= 1
                reasons.append(f"[감성] 뉴스 부정({sent_score:.2f}) → 추세 확인 (-1)")
            elif sent_score >= SENTIMENT_BULLISH_THRESHOLD and score < 0:
                score += 1
                reasons.append(f"[감성] 뉴스 긍정({sent_score:.2f}) vs 하락추세 → 모순 완화 (+1)")
            elif sent_score <= SENTIMENT_BEARISH_THRESHOLD and score > 0:
                score -= 1
                reasons.append(f"[감성] 뉴스 부정({sent_score:.2f}) vs 상승추세 → 모순 완화 (-1)")

        # 포지션 결정 (ATR 없으면 가격 기반 대체)
        atr_val = atr if atr is not None else price * ATR_DEFAULT_RATIO

        if analyzed_count == 0:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count=0)
            buy_price = price * 0.90
            sell_price = price * 1.10
            stop_loss = price * 0.85
            reasons.append("⚠ 분석 가능한 지표 없음 → 판단 보류")
        elif score >= SCORE_BUY_THRESHOLD:
            position = "매수"
            confidence = calc_confidence(score, "매수", analyzed_count, TrendFollower.EXPECTED_COUNT)
            buy_price = price * 0.98
            sell_price = price + atr_val * ATR_SELL_MULTIPLIER
            stop_loss = price - atr_val * ATR_STOP_MULTIPLIER
        elif score <= SCORE_SELL_THRESHOLD:
            position = "매도"
            confidence = calc_confidence(score, "매도", analyzed_count, TrendFollower.EXPECTED_COUNT)
            buy_price = None
            sell_price = price * 1.02
            stop_loss = price + atr_val * ATR_STOP_MULTIPLIER
        else:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count, TrendFollower.EXPECTED_COUNT)
            buy_price = sma60 if sma60 is not None else price * 0.90
            sell_price = (sma20 * 1.1) if sma20 is not None else price * 1.10
            stop_loss = price - atr_val * 2.5

        # ─── 3분할 매수/매도가 산출 ───
        ichimoku_levels = extract_ichimoku_levels(df)
        ichimoku_angles_data = extract_ichimoku_angles(df)
        split_buy = calc_split_buy_prices(price, atr, ichimoku_levels, ichimoku_angles_data)
        split_sell = calc_split_sell_prices(price, atr, ichimoku_levels, ichimoku_angles_data)

        return ExpertOpinion(
            expert_name=TrendFollower.NAME,
            expert_style=TrendFollower.STYLE,
            position=position,
            confidence=confidence,
            buy_price=buy_price,
            sell_price=sell_price,
            stop_loss=stop_loss,
            rationale=" | ".join(reasons),
            key_indicators=indicators,
            buy_prices=split_buy,
            sell_prices=split_sell,
        )
