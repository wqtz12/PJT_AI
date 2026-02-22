"""
전문가 3: 모멘텀 트레이더 (Momentum Trader)
- RSI, 스토캐스틱, 거래량 폭증, 단기 수익률 기반
- 상대강도(RS) 시장 대비 비교 (O'Neil CANSLIM 원칙) - v2 추가
- 강한 모멘텀에 올라타는 전략
- NaN 명시적 처리 + len(df) > 21 인덱싱 버그 수정
- 매크로/감성 컨텍스트 반영 (Phase 4)
"""
import pandas as pd
import numpy as np
from common.models import ExpertOpinion
from common.constants import (
    RSI_MOMENTUM_HIGH, RSI_EXTREME_HIGH, RSI_EXTREME_LOW, RSI_MOMENTUM_LOW,
    RSI_CONTRARIAN_LOW,
    STOCH_OVERBOUGHT, STOCH_OVERSOLD,
    VOLUME_SURGE_RATIO, VOLUME_ACTIVE_RATIO, VOLUME_DRY_RATIO,
    RETURN_5D_STRONG, RETURN_5D_MODERATE, RETURN_5D_DECLINE, RETURN_5D_CRASH,
    SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD,
    ATR_DEFAULT_RATIO,
    ICHIMOKU_ANGLE_STRONG,
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


class MomentumTrader:
    """모멘텀 트레이더 - RSI/스토캐스틱/거래량/수익률 기반"""

    NAME = "모멘텀 트레이더"
    STYLE = "RSI + 스토캐스틱 + 거래량 급증 + 단기 수익률 기반 모멘텀 매매"

    @staticmethod
    def analyze(df: pd.DataFrame, company_info: dict) -> ExpertOpinion:
        latest = df.iloc[-1]
        price = latest["Close"]

        score = 0
        reasons = []
        indicators = []
        analyzed_count = 0

        # 1) RSI 모멘텀
        rsi = _safe_get(latest, "RSI")
        if rsi is not None:
            analyzed_count += 1
            if RSI_MOMENTUM_HIGH < rsi < RSI_EXTREME_HIGH:
                score += 2
                reasons.append(f"RSI {rsi:.1f} → 상승 모멘텀 구간")
            elif rsi >= RSI_EXTREME_HIGH:
                score -= 1
                reasons.append(f"RSI {rsi:.1f} → 과열 구간, 차익실현 고려")
            elif rsi < RSI_CONTRARIAN_LOW:
                score -= 2
                reasons.append(f"RSI {rsi:.1f} → 하락 모멘텀/과매도")
            elif rsi < RSI_MOMENTUM_LOW:
                score -= 1
                reasons.append(f"RSI {rsi:.1f} → 약한 모멘텀")
            else:
                reasons.append(f"RSI {rsi:.1f} → 중립 모멘텀")
            indicators.append(f"RSI={rsi:.1f}")
        else:
            reasons.append("[RSI] 데이터 부족 → 미분석")

        # 2) 스토캐스틱 %K/%D 크로스
        stoch_k = _safe_get(latest, "Stoch_K")
        stoch_d = _safe_get(latest, "Stoch_D")
        if stoch_k is not None and stoch_d is not None:
            analyzed_count += 1
            if stoch_k > stoch_d and stoch_k < STOCH_OVERBOUGHT:
                score += 1
                reasons.append(f"스토캐스틱 %K>{stoch_k:.0f} > %D{stoch_d:.0f} → 상승 크로스")
            elif stoch_k < stoch_d and stoch_k > STOCH_OVERSOLD:
                score -= 1
                reasons.append(f"스토캐스틱 %K{stoch_k:.0f} < %D{stoch_d:.0f} → 하락 크로스")
            elif stoch_k < STOCH_OVERSOLD and stoch_k > stoch_d:
                score += 2
                reasons.append("스토캐스틱 과매도 반전 → 강한 매수 신호")
            indicators.append(f"Stoch_K={stoch_k:.1f} Stoch_D={stoch_d:.1f}")
        else:
            reasons.append("[스토캐스틱] 데이터 부족 → 미분석")

        # 3) 거래량 폭증 여부
        if "Volume" in df.columns and len(df) >= 20:
            vol_20d = df["Volume"].tail(20).mean()
            vol_today = latest["Volume"]
            if vol_20d > 0 and not np.isnan(vol_today):
                analyzed_count += 1
                vol_ratio = vol_today / vol_20d
                if vol_ratio > VOLUME_SURGE_RATIO:
                    score += 2
                    reasons.append(f"거래량 {vol_ratio:.1f}배 → 대량거래 폭증")
                elif vol_ratio > VOLUME_ACTIVE_RATIO:
                    score += 1
                    reasons.append(f"거래량 {vol_ratio:.1f}배 → 거래 활발")
                elif vol_ratio < VOLUME_DRY_RATIO:
                    score -= 1
                    reasons.append(f"거래량 {vol_ratio:.1f}배 → 거래 부진")
                else:
                    reasons.append(f"거래량 {vol_ratio:.1f}배 → 보통 수준")
                indicators.append(f"거래량비율={vol_ratio:.1f}x")

        # 4) 5일/20일 수익률 모멘텀 (버그 수정: len > 21 필요)
        if len(df) > 21:
            analyzed_count += 1
            close_5d_ago = df.iloc[-6]["Close"]
            close_20d_ago = df.iloc[-21]["Close"]

            if close_5d_ago > 0 and close_20d_ago > 0:
                ret_5d = (price / close_5d_ago - 1) * 100
                ret_20d = (price / close_20d_ago - 1) * 100

                if ret_5d > RETURN_5D_STRONG:
                    score += 2
                    reasons.append(f"5일 수익률 +{ret_5d:.1f}% → 강한 단기 상승")
                elif ret_5d > RETURN_5D_MODERATE:
                    score += 1
                    reasons.append(f"5일 수익률 +{ret_5d:.1f}% → 양호한 단기 흐름")
                elif ret_5d < RETURN_5D_CRASH:
                    score -= 2
                    reasons.append(f"5일 수익률 {ret_5d:.1f}% → 급락")
                elif ret_5d < RETURN_5D_DECLINE:
                    score -= 1
                    reasons.append(f"5일 수익률 {ret_5d:.1f}% → 하락 흐름")

                indicators.append(f"5일수익률={ret_5d:+.1f}% 20일수익률={ret_20d:+.1f}%")

        # 5) OBV 추세
        if "OBV" in df.columns and len(df) > 11:
            obv_now = _safe_get(latest, "OBV")
            obv_10d_val = df.iloc[-11].get("OBV", None)
            obv_10d = None
            if obv_10d_val is not None:
                try:
                    if not np.isnan(obv_10d_val):
                        obv_10d = obv_10d_val
                except (TypeError, ValueError):
                    obv_10d = obv_10d_val

            if obv_now is not None and obv_10d is not None:
                analyzed_count += 1
                if obv_now > obv_10d * 1.05:
                    score += 1
                    reasons.append("OBV 상승 → 매집 진행")
                elif obv_now < obv_10d * 0.95:
                    score -= 1
                    reasons.append("OBV 하락 → 매도 물량 출회")

        # ─── 일목균형표 보조 확인 (TK크로스 + 전환선 빗각 ±1) ───
        tenkan = _safe_get(latest, "Ichimoku_Tenkan")
        kijun = _safe_get(latest, "Ichimoku_Kijun")
        tenkan_angle = _safe_get(latest, "Ichimoku_Tenkan_Angle")
        if tenkan is not None and kijun is not None:
            if tenkan > kijun and tenkan_angle is not None and tenkan_angle > ICHIMOKU_ANGLE_STRONG:
                score += 1
                reasons.append(f"[일목] TK 상승크로스 + 빗각 {tenkan_angle:.0f}° → 모멘텀 확인 (+1)")
            elif tenkan < kijun and tenkan_angle is not None and tenkan_angle < -ICHIMOKU_ANGLE_STRONG:
                score -= 1
                reasons.append(f"[일목] TK 하락크로스 + 빗각 {tenkan_angle:.0f}° → 하락 모멘텀 (-1)")

        # ─── 6) 상대강도 RS - O'Neil CANSLIM (시장 대비 성과 비교 ±2) ───
        macro = get_macro_context(company_info)
        if macro is not None and len(df) > 21:
            sp = macro.get("sp500")
            if sp and sp.get("change_pct") is not None:
                sp_ret = sp["change_pct"]  # S&P500 20일 수익률 %
                close_20d_ago = df.iloc[-21]["Close"]
                if close_20d_ago > 0:
                    stock_ret_20d = (price / close_20d_ago - 1) * 100
                    if sp_ret != 0:
                        rs_ratio = stock_ret_20d / abs(sp_ret) if sp_ret != 0 else 1.0
                    else:
                        rs_ratio = 1.0 if stock_ret_20d >= 0 else -1.0

                    if stock_ret_20d > sp_ret + 5:
                        score += 2
                        reasons.append(f"[상대강도] 종목 {stock_ret_20d:+.1f}% vs S&P {sp_ret:+.1f}% → 시장 대비 강세 (O'Neil)")
                    elif stock_ret_20d > sp_ret:
                        score += 1
                        reasons.append(f"[상대강도] 종목 {stock_ret_20d:+.1f}% vs S&P {sp_ret:+.1f}% → 시장 대비 우수")
                    elif stock_ret_20d < sp_ret - 5:
                        score -= 2
                        reasons.append(f"[상대강도] 종목 {stock_ret_20d:+.1f}% vs S&P {sp_ret:+.1f}% → 시장 대비 약세")
                    elif stock_ret_20d < sp_ret:
                        score -= 1
                        reasons.append(f"[상대강도] 종목 {stock_ret_20d:+.1f}% vs S&P {sp_ret:+.1f}% → 시장 대비 열위")
                    indicators.append(f"RS={stock_ret_20d:+.1f}%vsSP{sp_ret:+.1f}%")

        # ─── 매크로 환경 반영 (최대 ±3점) ───
        if macro is None:
            macro = get_macro_context(company_info)
        if macro is not None:
            vix = macro.get("vix")
            sp = macro.get("sp500")

            if vix and vix.get("current"):
                vix_val = vix["current"]
                if vix_val > 30:
                    score -= 2
                    reasons.append(f"[매크로] VIX {vix_val:.0f} > 30 → 모멘텀 전략 위험 (-2)")
                elif vix_val > 25:
                    score -= 1
                    reasons.append(f"[매크로] VIX {vix_val:.0f} > 25 → 모멘텀 주의 (-1)")
                elif vix_val < 15 and score > 0:
                    score += 1
                    reasons.append(f"[매크로] VIX {vix_val:.0f} < 15 → 안정적 모멘텀 (+1)")

            if sp and sp.get("trend"):
                sp_trend = sp["trend"]
                if sp_trend == "상승" and score > 0:
                    score += 1
                    reasons.append("[매크로] S&P500 상승 → 시장 모멘텀 동조 (+1)")
                elif sp_trend == "하락" and score > 0:
                    score -= 1
                    reasons.append("[매크로] S&P500 하락 → 시장 역풍 (-1)")

        # ─── 감성 반영 (최대 ±1점) ───
        sentiment = get_sentiment_context(company_info)
        if sentiment is not None and sentiment.get("confidence", 0) >= SENTIMENT_MIN_CONFIDENCE:
            sent_score = sentiment.get("score", 0)
            if sent_score >= SENTIMENT_BULLISH_THRESHOLD and score > 0:
                score += 1
                reasons.append(f"[감성] 긍정 뉴스({sent_score:.2f}) → 모멘텀 확인 (+1)")
            elif sent_score <= SENTIMENT_BEARISH_THRESHOLD and score < 0:
                score -= 1
                reasons.append(f"[감성] 부정 뉴스({sent_score:.2f}) → 하락 모멘텀 확인 (-1)")

        # 포지션 결정 (ATR NaN 처리)
        atr = _safe_get(latest, "ATR")
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
            confidence = calc_confidence(score, "매수", analyzed_count)
            buy_price = price * 0.99
            sell_price = price + atr_val * 2.5
            stop_loss = price - atr_val * 1.5
        elif score <= SCORE_SELL_THRESHOLD:
            position = "매도"
            confidence = calc_confidence(score, "매도", analyzed_count)
            buy_price = None
            sell_price = price * 1.01
            stop_loss = price + atr_val * 1.5
        else:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count)
            buy_price = price - atr_val * 1.5
            sell_price = price + atr_val * 2
            stop_loss = price - atr_val * 2

        # ─── 3분할 매수/매도가 산출 ───
        ichimoku_levels = extract_ichimoku_levels(df)
        ichimoku_angles_data = extract_ichimoku_angles(df)
        split_buy = calc_split_buy_prices(price, atr, ichimoku_levels, ichimoku_angles_data)
        split_sell = calc_split_sell_prices(price, atr, ichimoku_levels, ichimoku_angles_data)

        return ExpertOpinion(
            expert_name=MomentumTrader.NAME,
            expert_style=MomentumTrader.STYLE,
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
