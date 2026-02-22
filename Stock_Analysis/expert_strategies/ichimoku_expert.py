"""
전문가 5: 일목균형표 전문가 (Ichimoku Expert)
- 일목균형표 구름 위치, TK 크로스, 후행스팬, 구름 두께로 판단
- 삼역호전/삼역역전 (3조건 동시 충족 보너스) - v2 추가
- 빗각이론으로 추세 강도 평가
- 3분할 매수/매도가 산출
- 매크로/감성 컨텍스트 반영
"""
import pandas as pd
import numpy as np
from common.models import ExpertOpinion
from common.constants import (
    SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD,
    ATR_SELL_MULTIPLIER, ATR_STOP_MULTIPLIER, ATR_DEFAULT_RATIO,
    ICHIMOKU_CLOUD_THICK_RATIO, ICHIMOKU_CLOUD_THIN_RATIO,
    ICHIMOKU_ANGLE_STRONG, ICHIMOKU_ANGLE_FLAT,
    calc_confidence,
    get_macro_context, get_sentiment_context,
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


class IchimokuExpert:
    """일목균형표 분석가 - 구름/TK크로스/후행스팬/빗각 기반"""

    NAME = "일목균형표 전문가"
    STYLE = "일목균형표 구름·전환선·기준선·후행스팬 + 빗각이론 기반 추세·전환 판단"

    @staticmethod
    def analyze(df: pd.DataFrame, company_info: dict) -> ExpertOpinion:
        latest = df.iloc[-1]
        price = latest["Close"]

        # 필요 지표 추출
        tenkan = _safe_get(latest, "Ichimoku_Tenkan")
        kijun = _safe_get(latest, "Ichimoku_Kijun")
        senkou_a = _safe_get(latest, "Ichimoku_SenkouA")
        senkou_b = _safe_get(latest, "Ichimoku_SenkouB")
        cloud_top = _safe_get(latest, "Ichimoku_CloudTop")
        cloud_bottom = _safe_get(latest, "Ichimoku_CloudBottom")
        atr = _safe_get(latest, "ATR")

        # 빗각
        tenkan_angle = _safe_get(latest, "Ichimoku_Tenkan_Angle")
        kijun_angle = _safe_get(latest, "Ichimoku_Kijun_Angle")
        senkou_a_angle = _safe_get(latest, "Ichimoku_SenkouA_Angle")

        # 후행스팬 비교용 (26일 전 가격)
        chikou_ref_price = None
        if len(df) > 26:
            chikou_ref_price = df.iloc[-27]["Close"]

        score = 0
        reasons = []
        indicators = []
        analyzed_count = 0

        # ─── 1) 구름 대비 가격 위치 (±3) ───
        if cloud_top is not None and cloud_bottom is not None:
            analyzed_count += 1
            if price > cloud_top:
                score += 3
                reasons.append("가격 > 구름 상단 → 강한 상승 추세")
            elif price < cloud_bottom:
                score -= 3
                reasons.append("가격 < 구름 하단 → 강한 하락 추세")
            elif price > (cloud_top + cloud_bottom) / 2:
                score += 1
                reasons.append("구름 상단부 → 상승 우위")
            else:
                score -= 1
                reasons.append("구름 하단부 → 하락 우위")
            indicators.append(f"CloudTop={cloud_top:.2f} CloudBot={cloud_bottom:.2f}")
        else:
            reasons.append("[일목:구름] 데이터 부족 → 미분석")

        # ─── 2) TK 크로스 (전환선 vs 기준선) (±2) ───
        if tenkan is not None and kijun is not None:
            analyzed_count += 1
            if tenkan > kijun:
                score += 2
                reasons.append(f"전환선({tenkan:.2f}) > 기준선({kijun:.2f}) → 매수 크로스")
            elif tenkan < kijun:
                score -= 2
                reasons.append(f"전환선({tenkan:.2f}) < 기준선({kijun:.2f}) → 매도 크로스")
            else:
                reasons.append("전환선 = 기준선 → 전환점")
            indicators.append(f"Tenkan={tenkan:.2f} Kijun={kijun:.2f}")
        else:
            reasons.append("[일목:TK] 데이터 부족 → 미분석")

        # ─── 3) 후행스팬 (Chikou vs 26일전 가격) (±1) ───
        if chikou_ref_price is not None:
            analyzed_count += 1
            # 후행스팬 = 현재 종가를 26일 전에 배치
            # 현재 종가가 26일 전 종가보다 높으면 상승 확인
            if price > chikou_ref_price:
                score += 1
                reasons.append(f"후행스팬 확인: 현재가 > 26일전({chikou_ref_price:.2f})")
            elif price < chikou_ref_price:
                score -= 1
                reasons.append(f"후행스팬 확인: 현재가 < 26일전({chikou_ref_price:.2f})")
        else:
            reasons.append("[일목:후행] 데이터 부족 → 미분석")

        # ─── 4) 구름 두께 (추세 강도) (±1) ───
        if cloud_top is not None and cloud_bottom is not None and price > 0:
            cloud_thickness = (cloud_top - cloud_bottom) / price
            if cloud_thickness > ICHIMOKU_CLOUD_THICK_RATIO:
                # 두꺼운 구름 = 강한 지지/저항
                if price > cloud_top:
                    score += 1
                    reasons.append(f"두꺼운 구름({cloud_thickness*100:.1f}%) → 강한 지지")
                elif price < cloud_bottom:
                    score -= 1
                    reasons.append(f"두꺼운 구름({cloud_thickness*100:.1f}%) → 강한 저항")
            elif cloud_thickness < ICHIMOKU_CLOUD_THIN_RATIO:
                reasons.append(f"얇은 구름({cloud_thickness*100:.2f}%) → 전환 임박 가능")

        # ─── 5) 전환선 빗각 (단기 모멘텀) (±2) ───
        if tenkan_angle is not None:
            analyzed_count += 1
            if tenkan_angle > ICHIMOKU_ANGLE_STRONG:
                score += 2
                reasons.append(f"전환선 빗각 {tenkan_angle:.1f}° → 강한 상승 모멘텀")
            elif tenkan_angle > ICHIMOKU_ANGLE_FLAT:
                score += 1
                reasons.append(f"전환선 빗각 {tenkan_angle:.1f}° → 완만한 상승")
            elif tenkan_angle < -ICHIMOKU_ANGLE_STRONG:
                score -= 2
                reasons.append(f"전환선 빗각 {tenkan_angle:.1f}° → 강한 하락 모멘텀")
            elif tenkan_angle < -ICHIMOKU_ANGLE_FLAT:
                score -= 1
                reasons.append(f"전환선 빗각 {tenkan_angle:.1f}° → 완만한 하락")
            else:
                reasons.append(f"전환선 빗각 {tenkan_angle:.1f}° → 횡보/전환 임박")
            indicators.append(f"TenkanAngle={tenkan_angle:.1f}°")

        # ─── 6) 기준선 빗각 (중기 추세) (±1) ───
        if kijun_angle is not None:
            if abs(kijun_angle) > ICHIMOKU_ANGLE_STRONG:
                if kijun_angle > 0:
                    score += 1
                    reasons.append(f"기준선 빗각 {kijun_angle:.1f}° → 강한 중기 상승")
                else:
                    score -= 1
                    reasons.append(f"기준선 빗각 {kijun_angle:.1f}° → 강한 중기 하락")
            indicators.append(f"KijunAngle={kijun_angle:.1f}°")

        # ─── 매크로 환경 반영 (최대 ±1점) ───
        macro = get_macro_context(company_info)
        if macro is not None:
            vix = macro.get("vix")
            if vix and vix.get("level") in ("고변동", "극단"):
                if score > 0:
                    score -= 1
                    reasons.append(f"[매크로] VIX {vix.get('level')} → 상승 신뢰도 ↓")
                elif score < 0:
                    score += 1
                    reasons.append(f"[매크로] VIX {vix.get('level')} → 하락 신뢰도 ↓")

        # ─── 감성 반영 (최대 ±1점) ───
        sentiment = get_sentiment_context(company_info)
        if sentiment is not None and sentiment.get("confidence", 0) >= SENTIMENT_MIN_CONFIDENCE:
            sent_score = sentiment.get("score", 0)
            if sent_score >= SENTIMENT_BULLISH_THRESHOLD and score > 0:
                score += 1
                reasons.append(f"[감성] 뉴스 긍정({sent_score:.2f}) → 상승 확인")
            elif sent_score <= SENTIMENT_BEARISH_THRESHOLD and score < 0:
                score -= 1
                reasons.append(f"[감성] 뉴스 부정({sent_score:.2f}) → 하락 확인")

        # ─── 7) 삼역호전 / 삼역역전 (3조건 동시 충족 보너스 ±3) ───
        if cloud_top is not None and cloud_bottom is not None and tenkan is not None and kijun is not None and chikou_ref_price is not None:
            # 삼역호전: ① 가격>구름상단 ② 전환선>기준선 ③ 후행스팬>26봉전가격
            bullish_3 = (price > cloud_top) and (tenkan > kijun) and (price > chikou_ref_price)
            # 삼역역전: ① 가격<구름하단 ② 전환선<기준선 ③ 후행스팬<26봉전가격
            bearish_3 = (price < cloud_bottom) and (tenkan < kijun) and (price < chikou_ref_price)

            if bullish_3:
                score += 3
                reasons.append("★ 삼역호전 (구름위+TK매수+후행확인) → 최강 매수 신호")
            elif bearish_3:
                score -= 3
                reasons.append("★ 삼역역전 (구름아래+TK매도+후행확인) → 최강 매도 신호")

        # ─── 포지션 결정 ───
        atr_val = atr if atr is not None else price * ATR_DEFAULT_RATIO

        if analyzed_count == 0:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count=0)
            buy_price = price * 0.95
            sell_price = price * 1.05
            stop_loss = price * 0.90
            reasons.append("⚠ 일목균형표 지표 부재 → 판단 보류")
        elif score >= SCORE_BUY_THRESHOLD:
            position = "매수"
            confidence = calc_confidence(score, "매수", analyzed_count)
            buy_price = price * 0.98
            sell_price = price + atr_val * ATR_SELL_MULTIPLIER
            stop_loss = price - atr_val * ATR_STOP_MULTIPLIER
        elif score <= SCORE_SELL_THRESHOLD:
            position = "매도"
            confidence = calc_confidence(score, "매도", analyzed_count)
            buy_price = None
            sell_price = price * 1.02
            stop_loss = price + atr_val * ATR_STOP_MULTIPLIER
        else:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count)
            buy_price = kijun if kijun is not None else price * 0.95
            sell_price = cloud_top if cloud_top is not None else price * 1.05
            stop_loss = price - atr_val * 2.5

        # ─── 3분할 매수/매도가 산출 ───
        ichimoku_levels = extract_ichimoku_levels(df)
        ichimoku_angles = extract_ichimoku_angles(df)

        split_buy = calc_split_buy_prices(price, atr, ichimoku_levels, ichimoku_angles)
        split_sell = calc_split_sell_prices(price, atr, ichimoku_levels, ichimoku_angles)

        return ExpertOpinion(
            expert_name=IchimokuExpert.NAME,
            expert_style=IchimokuExpert.STYLE,
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
