"""
전문가 4: 역발상 전문가 (Contrarian Expert)
- 볼린저밴드 이탈, RSI 극단값, 공포/탐욕 역이용
- 과매도에서 매수, 과매수에서 매도하는 역발상 전략
- NaN 명시적 처리: 지표 미계산 시 해당 항목 스킵
- 매크로/감성 컨텍스트 반영 (Phase 4)
"""
import pandas as pd
import numpy as np
from common.models import ExpertOpinion
from common.constants import (
    BB_UPPER_BREACH, BB_UPPER_NEAR, BB_LOWER_BREACH, BB_LOWER_NEAR,
    BB_SQUEEZE_RATIO, BB_EXPAND_RATIO,
    RSI_EXTREME_LOW, RSI_CONTRARIAN_LOW, RSI_EXTREME_HIGH, RSI_CONTRARIAN_HIGH,
    ADX_STRONG,
    SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD,
    ATR_DEFAULT_RATIO,
    calc_confidence,
    get_macro_context, get_sentiment_context,
    SENTIMENT_EXTREME_BULLISH, SENTIMENT_EXTREME_BEARISH,
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


def _safe_info(info: dict, key: str):
    """company_info에서 숫자값 안전 추출 - None/"N/A" → None"""
    val = info.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return None
    if isinstance(val, (int, float)):
        try:
            if np.isnan(val) or np.isinf(val):
                return None
        except (TypeError, ValueError):
            pass
        return val
    return None


class ContrarianExpert:
    """역발상 전문가 - 볼린저밴드/RSI 극단/거래량 급변 역이용"""

    NAME = "역발상 전문가"
    STYLE = "볼린저밴드 이탈 + RSI 극단값 + 거래량 클라이맥스 역이용 반전매매"

    @staticmethod
    def analyze(df: pd.DataFrame, company_info: dict) -> ExpertOpinion:
        latest = df.iloc[-1]
        price = latest["Close"]

        score = 0
        reasons = []
        indicators = []
        analyzed_count = 0

        # 1) 볼린저밴드 위치 (역발상 → 밴드 이탈 시 반전 기대)
        bb_pct = _safe_get(latest, "BB_Pct")
        bb_upper = _safe_get(latest, "BB_Upper")
        bb_lower = _safe_get(latest, "BB_Lower")
        bb_mid = _safe_get(latest, "BB_Middle")

        if bb_pct is not None:
            analyzed_count += 1
            if bb_pct < BB_LOWER_BREACH:
                score += 3
                reasons.append(f"볼린저 하단 이탈 ({bb_pct:.2f}) → 과도한 매도, 반등 예상")
            elif bb_pct < BB_LOWER_NEAR:
                score += 2
                reasons.append(f"볼린저 하단 근접 ({bb_pct:.2f}) → 반등 가능성")
            elif bb_pct > BB_UPPER_BREACH:
                score -= 3
                reasons.append(f"볼린저 상단 이탈 ({bb_pct:.2f}) → 과도한 매수, 조정 예상")
            elif bb_pct > BB_UPPER_NEAR:
                score -= 2
                reasons.append(f"볼린저 상단 근접 ({bb_pct:.2f}) → 조정 가능성")
            else:
                reasons.append(f"볼린저 밴드 내 정상 ({bb_pct:.2f})")
            indicators.append(f"BB%B={bb_pct:.2f}")
        else:
            reasons.append("[볼린저밴드] 데이터 부족 → 미분석")

        # 2) RSI 극단 역이용 (ADX 기반 추세 과매도 체크)
        rsi = _safe_get(latest, "RSI")
        adx_val = _safe_get(latest, "ADX")
        if rsi is not None:
            analyzed_count += 1
            if rsi < RSI_EXTREME_LOW:
                # ADX 체크: 강한 하락추세에서는 반등 기대 약화
                if adx_val is not None and adx_val > ADX_STRONG:
                    score += 1  # 강한 하락추세 → 약한 매수만
                    reasons.append(f"RSI {rsi:.1f} + ADX {adx_val:.1f}>30 → 추세적 과매도, 약한 반등 기대")
                else:
                    score += 3  # 기존 로직 유지
                    reasons.append(f"RSI {rsi:.1f} → 극심한 과매도, 반등 매수 기회")
            elif rsi < RSI_CONTRARIAN_LOW:
                if adx_val is not None and adx_val > ADX_STRONG:
                    # 추세적 과매도 → 매수 억제
                    reasons.append(f"RSI {rsi:.1f} + ADX {adx_val:.1f}>30 → 추세적 과매도, 관망")
                else:
                    score += 1
                    reasons.append(f"RSI {rsi:.1f} → 과매도 접근, 바닥 탐색")
            elif rsi > RSI_EXTREME_HIGH:
                score -= 3
                reasons.append(f"RSI {rsi:.1f} → 극심한 과매수, 차익실현 매도")
            elif rsi > RSI_CONTRARIAN_HIGH:
                score -= 1
                reasons.append(f"RSI {rsi:.1f} → 과매수 접근, 주의 필요")
            else:
                reasons.append(f"RSI {rsi:.1f} → 중립 구간")
            indicators.append(f"RSI={rsi:.1f}")
        else:
            reasons.append("[RSI] 데이터 부족 → 미분석")

        # 3) 볼린저밴드 폭 (변동성 수축/확장)
        bb_width = _safe_get(latest, "BB_Width")
        if bb_width is not None and bb_width > 0:
            # 최근 60일 평균 밴드폭 비교
            if "BB_Width" in df.columns:
                recent_widths = df["BB_Width"].tail(60).dropna()
                if len(recent_widths) > 10:
                    avg_width = recent_widths.mean()
                    if bb_width < avg_width * BB_SQUEEZE_RATIO:
                        score += 1
                        reasons.append("밴드 수축 → 큰 움직임 임박 (스퀴즈)")
                    elif bb_width > avg_width * BB_EXPAND_RATIO:
                        reasons.append("밴드 확장 → 변동성 클라이맥스 후 안정화 기대")
            indicators.append(f"BB_Width={bb_width:.4f}")

        # 4) 52주 최저 대비 위치 (역발상 가치)
        low_52w = _safe_info(company_info, "52주_최저")
        high_52w = _safe_info(company_info, "52주_최고")
        if high_52w is not None and low_52w is not None and high_52w > low_52w > 0:
            analyzed_count += 1
            dist_from_low = (price - low_52w) / low_52w
            if dist_from_low < 0.15:
                score += 2
                reasons.append(f"52주 최저가 근접 (+{dist_from_low*100:.0f}%) → 바닥 매수 기회")
            elif dist_from_low < 0.30:
                score += 1
                reasons.append(f"52주 최저 대비 +{dist_from_low*100:.0f}% → 저점 매수 영역")

            dist_from_high = (high_52w - price) / high_52w
            if dist_from_high < 0.10:
                score -= 2
                reasons.append(f"52주 최고가 근접 (-{dist_from_high*100:.0f}%) → 고점 매도 기회")
            indicators.append(f"52주저점대비=+{dist_from_low*100:.1f}%")

        # 5) 연속 하락/상승일 카운트
        if len(df) >= 7:
            recent_returns = df["Close"].pct_change().tail(7).dropna()
            consec_down = 0
            consec_up = 0
            for r in recent_returns:
                if np.isnan(r):
                    continue
                if r < 0:
                    consec_down += 1
                    consec_up = 0
                elif r > 0:
                    consec_up += 1
                    consec_down = 0

            if consec_down >= 4:
                score += 2
                reasons.append(f"연속 {consec_down}일 하락 → 기술적 반등 기대")
            elif consec_up >= 4:
                score -= 1
                reasons.append(f"연속 {consec_up}일 상승 → 단기 과열 주의")

        # ─── 일목균형표 보조 확인 (후행스팬 괴리 ±1) ───
        if len(df) > 26:
            chikou_ref = df.iloc[-27]["Close"]
            if price < chikou_ref * 0.90:
                # 현재가가 26일전 대비 10%+ 하락 → 과도한 하락, 반전 기대
                score += 1
                reasons.append(f"[일목] 후행스팬 괴리: 현재 < 26일전({chikou_ref:.2f})×0.9 → 과도 하락, 반등 기대 (+1)")
            elif price > chikou_ref * 1.10:
                # 현재가가 26일전 대비 10%+ 상승 → 과도한 상승, 조정 기대
                score -= 1
                reasons.append(f"[일목] 후행스팬 괴리: 현재 > 26일전({chikou_ref:.2f})×1.1 → 과도 상승, 조정 기대 (-1)")

        # ─── 매크로 환경 반영 (역발상 핵심: 극단에서 반대 포지션) ───
        macro = get_macro_context(company_info)
        if macro is not None:
            vix = macro.get("vix")
            if vix and vix.get("current"):
                vix_val = vix["current"]
                if vix_val > 35:
                    score += 2
                    reasons.append(f"[매크로] VIX {vix_val:.0f} > 35 → 극단적 공포 = 역발상 매수 (+2)")
                elif vix_val > 30:
                    score += 1
                    reasons.append(f"[매크로] VIX {vix_val:.0f} > 30 → 공포 구간 = 역발상 매수 (+1)")
                elif vix_val < 12:
                    score -= 2
                    reasons.append(f"[매크로] VIX {vix_val:.0f} < 12 → 극단적 안일함 = 역발상 매도 (-2)")
                elif vix_val < 15:
                    score -= 1
                    reasons.append(f"[매크로] VIX {vix_val:.0f} < 15 → 안일 구간 = 역발상 매도 (-1)")

        # ─── 감성 반영 (역발상: 극단적 감성의 반대 방향) ───
        sentiment = get_sentiment_context(company_info)
        if sentiment is not None and sentiment.get("confidence", 0) >= SENTIMENT_MIN_CONFIDENCE:
            sent_score = sentiment.get("score", 0)
            if sent_score >= SENTIMENT_EXTREME_BULLISH:
                score -= 1
                reasons.append(f"[감성] 극단 낙관({sent_score:.2f}) → 역발상 경계 (-1)")
            elif sent_score <= SENTIMENT_EXTREME_BEARISH:
                score += 1
                reasons.append(f"[감성] 극단 비관({sent_score:.2f}) → 역발상 매수 (+1)")

        # 포지션 결정 (ATR NaN 처리)
        atr = _safe_get(latest, "ATR")
        atr_val = atr if atr is not None else price * ATR_DEFAULT_RATIO

        # 볼린저밴드 기반 목표가용 대체값
        _bb_lower = bb_lower if bb_lower is not None else price * 0.90
        _bb_upper = bb_upper if bb_upper is not None else price * 1.10
        _bb_mid = bb_mid if bb_mid is not None else price

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
            buy_price = _bb_lower
            sell_price = _bb_mid
            stop_loss = _bb_lower * 0.92
        elif score <= SCORE_SELL_THRESHOLD:
            position = "매도"
            confidence = calc_confidence(score, "매도", analyzed_count)
            buy_price = None
            sell_price = _bb_upper
            stop_loss = _bb_upper * 1.05
        else:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count)
            buy_price = _bb_lower
            sell_price = _bb_upper
            stop_loss = price - atr_val * 3

        # ─── 3분할 매수/매도가 산출 ───
        ichimoku_levels = extract_ichimoku_levels(df)
        ichimoku_angles_data = extract_ichimoku_angles(df)
        split_buy = calc_split_buy_prices(price, atr_val, ichimoku_levels, ichimoku_angles_data)
        split_sell = calc_split_sell_prices(price, atr_val, ichimoku_levels, ichimoku_angles_data)

        return ExpertOpinion(
            expert_name=ContrarianExpert.NAME,
            expert_style=ContrarianExpert.STYLE,
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
