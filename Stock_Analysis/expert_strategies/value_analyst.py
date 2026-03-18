"""
전문가 2: 가치분석 전문가 (Value Analyst)
- PBR, EPS, 부채비율, 현금보유 등 펀더멘털 기반
- ROE, PEG, 영업이익률 (Buffett/Lynch 원칙) - v2 추가
- 52주 범위 내 위치, 애널리스트 목표가 괴리율 분석
- 섹터별 밸류에이션 기준 적용 (config.yaml에서 로드)
- NaN 명시적 처리: company_info에서 None이면 해당 항목 스킵
- 매크로/감성 컨텍스트 반영 (Phase 4)
"""
import pandas as pd
import numpy as np
from common.models import ExpertOpinion
from common.constants import (
    RANGE_52W_LOW_ZONE, RANGE_52W_MID_LOW, RANGE_52W_HIGH_ZONE,
    SCORE_BUY_THRESHOLD, SCORE_SELL_THRESHOLD_VALUE,
    ATR_DEFAULT_RATIO,
    calc_confidence,
    get_macro_context, get_sentiment_context,
    SENTIMENT_BULLISH_THRESHOLD, SENTIMENT_BEARISH_THRESHOLD,
    SENTIMENT_EXTREME_BULLISH, SENTIMENT_EXTREME_BEARISH,
    SENTIMENT_MIN_CONFIDENCE,
)
from common.sector_valuation import get_sector_criteria
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
        return None  # "N/A" 등 문자열
    if isinstance(val, (int, float)):
        try:
            if np.isnan(val) or np.isinf(val):
                return None
        except (TypeError, ValueError):
            pass
        return val
    return None


class ValueAnalyst:
    """가치분석 전문가 - 펀더멘털/밸류에이션 기반 (섹터별 기준 적용)"""

    NAME = "가치분석 전문가"
    STYLE = "PBR/EPS/ROE/PEG/영업이익률 + 52주 범위 + 애널리스트 목표가 (Buffett/Lynch 원칙)"
    EXPECTED_COUNT = 9  # 52주, PBR, EPS, ROE, PEG, 영업이익률, 부채, 현금, 목표가

    @staticmethod
    def analyze(df: pd.DataFrame, company_info: dict) -> ExpertOpinion:
        latest = df.iloc[-1]
        price = latest["Close"]

        score = 0
        reasons = []
        indicators = []
        analyzed_count = 0

        # 섹터별 밸류에이션 기준 로드
        sector = company_info.get("섹터") if company_info else None
        criteria = get_sector_criteria(sector)
        sector_label = criteria["sector_matched"]

        if sector:
            reasons.append(f"[섹터: {sector} → {sector_label} 기준 적용]")

        # 1) 52주 범위 위치
        high_52w = _safe_info(company_info, "52주_최고")
        low_52w = _safe_info(company_info, "52주_최저")
        if high_52w is not None and low_52w is not None and high_52w > low_52w > 0:
            analyzed_count += 1
            range_pct = (price - low_52w) / (high_52w - low_52w)
            if range_pct < RANGE_52W_LOW_ZONE:
                score += 3
                reasons.append(f"52주 하위 {range_pct*100:.0f}% → 저평가 구간")
            elif range_pct < RANGE_52W_MID_LOW:
                score += 1
                reasons.append(f"52주 하위 {range_pct*100:.0f}% → 비교적 저점")
            elif range_pct > RANGE_52W_HIGH_ZONE:
                score -= 2
                reasons.append(f"52주 상위 {range_pct*100:.0f}% → 고평가 구간")
            else:
                reasons.append(f"52주 중간 {range_pct*100:.0f}% → 적정 구간")
            indicators.append(f"52주범위={range_pct*100:.1f}%")

            # 가치함정 필터: 52주 하위권 + 최근 급락 = 하강 중 저점 진입
            if range_pct < RANGE_52W_MID_LOW and len(df) > 5:
                close_5d_ago = df.iloc[-6]["Close"] if len(df) > 5 else None
                if close_5d_ago and close_5d_ago > 0:
                    ret_5d = (price / close_5d_ago - 1) * 100
                    if ret_5d < -5.0:
                        score -= 2
                        reasons.append(f"⚠ 가치함정 주의: 52주 {range_pct*100:.0f}% + 5일 {ret_5d:.1f}% 급락 → 하강 중 저점")
        else:
            reasons.append("[52주 범위] 데이터 없음 → 미분석")

        # 2) PBR (섹터별 기준 적용)
        pbr = _safe_info(company_info, "PBR")
        pbr_low = criteria["pbr_low"]
        pbr_high = criteria["pbr_high"]
        if pbr is not None and pbr > 0:
            analyzed_count += 1
            if pbr < pbr_low:
                score += 2
                reasons.append(f"PBR {pbr:.2f} < {pbr_low} ({sector_label}) → 섹터 대비 저평가")
            elif pbr < pbr_high:
                reasons.append(f"PBR {pbr:.2f} ({sector_label} 적정: {pbr_low}~{pbr_high})")
            else:
                score -= 1
                reasons.append(f"PBR {pbr:.2f} > {pbr_high} ({sector_label}) → 섹터 대비 고평가")
            indicators.append(f"PBR={pbr:.2f}")
        else:
            reasons.append("[PBR] 데이터 없음 → 미분석")

        # 3) EPS (주당순이익)
        eps = _safe_info(company_info, "EPS")
        if eps is not None:
            analyzed_count += 1
            if eps > 0:
                score += 2
                reasons.append(f"EPS ${eps:.2f} → 흑자 기업")
            elif eps > -1:
                score -= 1
                reasons.append(f"EPS ${eps:.2f} → 소폭 적자")
            else:
                score -= 2
                reasons.append(f"EPS ${eps:.2f} → 대규모 적자")
            indicators.append(f"EPS={eps:.2f}")
        else:
            reasons.append("[EPS] 데이터 없음 → 미분석")

        # 4) ROE - 자기자본이익률 (Buffett: 15%+ 지속 = 경쟁우위)
        roe = _safe_info(company_info, "ROE")
        if roe is not None:
            analyzed_count += 1
            roe_pct = roe * 100 if abs(roe) < 1 else roe  # 0.25 → 25%
            if roe_pct > 20:
                score += 2
                reasons.append(f"ROE {roe_pct:.1f}% > 20% → 탁월한 수익성 (Buffett)")
            elif roe_pct > 15:
                score += 1
                reasons.append(f"ROE {roe_pct:.1f}% > 15% → 우수한 수익성")
            elif roe_pct > 0:
                reasons.append(f"ROE {roe_pct:.1f}% → 양호")
            else:
                score -= 1
                reasons.append(f"ROE {roe_pct:.1f}% → 자본 효율성 저조")
            indicators.append(f"ROE={roe_pct:.1f}%")

        # 5) PEG - 주가수익성장비율 (Lynch: PEG<1 저평가 성장주)
        peg = _safe_info(company_info, "PEG")
        if peg is not None and peg > 0:
            analyzed_count += 1
            if peg < 1.0:
                score += 2
                reasons.append(f"PEG {peg:.2f} < 1.0 → 성장 대비 저평가 (Lynch)")
            elif peg < 2.0:
                score += 1
                reasons.append(f"PEG {peg:.2f} → 적정 수준")
            elif peg > 3.0:
                score -= 1
                reasons.append(f"PEG {peg:.2f} > 3.0 → 성장 대비 고평가")
            indicators.append(f"PEG={peg:.2f}")

        # 6) 영업이익률 (Buffett: 높은 마진 = 경제적 해자)
        op_margin = _safe_info(company_info, "영업이익률")
        if op_margin is not None:
            analyzed_count += 1
            margin_pct = op_margin * 100 if abs(op_margin) < 1 else op_margin
            if margin_pct > 25:
                score += 1
                reasons.append(f"영업이익률 {margin_pct:.1f}% > 25% → 강한 해자")
            elif margin_pct < 5:
                score -= 1
                reasons.append(f"영업이익률 {margin_pct:.1f}% < 5% → 경쟁우위 약함")
            indicators.append(f"영업이익률={margin_pct:.1f}%")

        # 7) 부채비율 (섹터별 기준 적용)
        debt = _safe_info(company_info, "부채비율")
        debt_healthy = criteria["debt_healthy"]
        debt_warning = criteria["debt_warning"]
        if debt is not None:
            analyzed_count += 1
            if debt < debt_healthy:
                score += 1
                reasons.append(f"부채비율 {debt:.1f}% < {debt_healthy}% ({sector_label}) → 건전")
            elif debt < debt_warning:
                reasons.append(f"부채비율 {debt:.1f}% ({sector_label} 적정: ~{debt_warning}%)")
            else:
                score -= 1
                reasons.append(f"부채비율 {debt:.1f}% > {debt_warning}% ({sector_label}) → 과다")
            indicators.append(f"부채비율={debt:.1f}%")

        # 8) 보유현금 (섹터별 기준 적용)
        cash = _safe_info(company_info, "현금")
        mktcap = _safe_info(company_info, "시가총액")
        cash_rich = criteria["cash_rich"]
        cash_poor = criteria["cash_poor"]
        if cash is not None and mktcap is not None and cash > 0 and mktcap > 0:
            analyzed_count += 1
            cash_ratio = cash / mktcap
            if cash_ratio > cash_rich:
                score += 1
                reasons.append(f"현금비율 {cash_ratio*100:.1f}% > {cash_rich*100:.0f}% ({sector_label}) → 풍부")
            elif cash_ratio < cash_poor:
                score -= 1
                reasons.append(f"현금비율 {cash_ratio*100:.1f}% < {cash_poor*100:.0f}% ({sector_label}) → 부족")
            indicators.append(f"현금비율={cash_ratio*100:.1f}%")

        # 9) 애널리스트 목표가 괴리율
        target = _safe_info(company_info, "애널리스트_목표가")
        if target is not None and target > 0:
            analyzed_count += 1
            upside = (target - price) / price
            if upside > 0.30:
                score += 2
                reasons.append(f"목표가 ${target:.2f} (상승여력 +{upside*100:.0f}%) → 강한 저평가")
            elif upside > 0.10:
                score += 1
                reasons.append(f"목표가 ${target:.2f} (상승여력 +{upside*100:.0f}%) → 저평가")
            elif upside < -0.10:
                score -= 1
                reasons.append(f"목표가 ${target:.2f} (하락여력 {upside*100:.0f}%) → 고평가")
            indicators.append(f"목표가=${target:.2f} 괴리율={upside*100:+.1f}%")

        # ─── 매크로 환경 반영 (최대 ±2점) ───
        macro = get_macro_context(company_info)
        per = _safe_info(company_info, "PER")
        if macro is not None:
            rate = macro.get("treasury_10y")
            if rate and rate.get("trend") == "상승":
                if per is not None and per > 30:
                    score -= 1
                    reasons.append(f"[매크로] 금리 상승 + 고PER({per:.0f}) → 성장주 할인 (-1)")
                elif per is not None and per > 0 and per < 15:
                    score += 1
                    reasons.append(f"[매크로] 금리 상승 + 저PER({per:.0f}) → 가치주 매력 (+1)")

            env_score = macro.get("환경_점수", 0)
            if env_score >= 3:
                score += 1
                reasons.append(f"[매크로] 위험선호 환경(+{env_score}) → 투자 심리 양호 (+1)")
            elif env_score <= -3:
                score -= 1
                reasons.append(f"[매크로] 위험회피 환경({env_score}) → 투자 심리 위축 (-1)")

        # ─── 감성 반영 (최대 ±1점) ───
        sentiment = get_sentiment_context(company_info)
        if sentiment is not None and sentiment.get("confidence", 0) >= SENTIMENT_MIN_CONFIDENCE:
            sent_score = sentiment.get("score", 0)
            if sent_score >= SENTIMENT_EXTREME_BULLISH:
                score += 1
                reasons.append(f"[감성] 강한 긍정 뉴스({sent_score:.2f}) → 시장 인식 양호 (+1)")
            elif sent_score <= SENTIMENT_EXTREME_BEARISH:
                score -= 1
                reasons.append(f"[감성] 강한 부정 뉴스({sent_score:.2f}) → 시장 인식 악화 (-1)")

        # 포지션 결정 (ATR NaN 처리)
        atr = _safe_get(latest, "ATR")
        atr_val = atr if atr is not None else price * ATR_DEFAULT_RATIO

        if analyzed_count == 0:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count=0)
            buy_price = price * 0.85
            sell_price = price * 1.20
            stop_loss = price * 0.75
            reasons.append("⚠ 분석 가능한 펀더멘털 데이터 없음 → 판단 보류")
        elif score >= SCORE_BUY_THRESHOLD:
            position = "매수"
            confidence = calc_confidence(score, "매수", analyzed_count, ValueAnalyst.EXPECTED_COUNT)
            buy_price = price * 0.97
            sell_target = target if target is not None and target > 0 else price * 1.30
            sell_price = sell_target
            stop_loss = (low_52w * 0.95) if low_52w is not None and low_52w > 0 else price * 0.80
        elif score <= SCORE_SELL_THRESHOLD_VALUE:
            position = "매도"
            confidence = calc_confidence(score, "매도", analyzed_count, ValueAnalyst.EXPECTED_COUNT)
            buy_price = None
            sell_price = price * 1.03
            stop_loss = price + atr_val * 3
        else:
            position = "홀드"
            confidence = calc_confidence(score, "홀드", analyzed_count, ValueAnalyst.EXPECTED_COUNT)
            buy_price = (low_52w * 1.05) if low_52w is not None and low_52w > 0 else price * 0.85
            sell_price = target if target is not None and target > 0 else price * 1.20
            stop_loss = (low_52w * 0.90) if low_52w is not None and low_52w > 0 else price * 0.75

        # ─── 3분할 매수/매도가 산출 ───
        ichimoku_levels = extract_ichimoku_levels(df)
        ichimoku_angles_data = extract_ichimoku_angles(df)
        split_buy = calc_split_buy_prices(price, atr, ichimoku_levels, ichimoku_angles_data)
        split_sell = calc_split_sell_prices(price, atr, ichimoku_levels, ichimoku_angles_data)

        # 일목 구름 레벨 참고 표시 (점수 영향 없음)
        cloud_top = _safe_get(latest, "Ichimoku_CloudTop")
        cloud_bottom = _safe_get(latest, "Ichimoku_CloudBottom")
        if cloud_top is not None and cloud_bottom is not None:
            reasons.append(f"[일목 참조] 구름 지지 ${cloud_bottom:.2f} / 저항 ${cloud_top:.2f}")

        return ExpertOpinion(
            expert_name=ValueAnalyst.NAME,
            expert_style=ValueAnalyst.STYLE,
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
