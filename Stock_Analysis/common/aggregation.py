"""
전문가 의견 가중 집계 모듈

시장 상태에 따라 전문가별 가중치를 조정:
- ADX > 30 (강한 추세): 추세추종/일목 가중치 ↑
- ADX < 20 (횡보): 가치분석 가중치 ↑
- VIX > 25 (고변동): 역발상 가중치 ↑

시장 사이클 복합 판별 (Howard Marks 원칙) - v2 추가:
- VIX + 금리추세 + S&P500 위치로 강세/약세장 판별
- 약세장에서 전체 매수 확신도 감점
"""
import numpy as np
from common.config import get_config


def aggregate_expert_opinions(opinions: list, df, company_info: dict) -> dict:
    """
    전문가 의견 가중 집계

    Args:
        opinions: ExpertOpinion 리스트 (.expert_name, .position 속성 필요)
        df: 기술적 지표가 포함된 DataFrame (ADX 컬럼 사용)
        company_info: 기업 정보 dict (_macro.vix 사용)

    Returns:
        dict: {weighted_buy, weighted_sell, weighted_hold, dominant, weights_used, total_weight}
    """
    cfg = get_config().get("expert_aggregation", {})
    if not cfg.get("weighted", True) or not opinions:
        buy = sum(1 for o in opinions if o.position == "매수")
        sell = sum(1 for o in opinions if o.position == "매도")
        hold = sum(1 for o in opinions if o.position == "홀드")
        dominant = "매수" if buy > sell and buy > hold else "매도" if sell > buy and sell > hold else "홀드"
        return {
            "weighted_buy": float(buy), "weighted_sell": float(sell),
            "weighted_hold": float(hold), "dominant": dominant,
            "weights_used": {}, "total_weight": float(len(opinions)),
        }

    base_w = cfg.get("base_weight", 1.0)
    boost = cfg.get("boost_multiplier", 1.5)

    # 시장 상태 감지
    adx = None
    if df is not None and not df.empty and "ADX" in df.columns:
        adx_val = df.iloc[-1].get("ADX")
        if adx_val is not None:
            try:
                if not np.isnan(adx_val):
                    adx = float(adx_val)
            except (TypeError, ValueError):
                pass

    vix = None
    macro = company_info.get("_macro") if company_info else None
    if macro:
        vix_data = macro.get("vix")
        if vix_data and vix_data.get("current"):
            vix = float(vix_data["current"])

    # 섹터 감지 (섹터별 가중치 편향용)
    sector = None
    if company_info:
        raw_sector = company_info.get("섹터") or company_info.get("sector") or ""
        sector = raw_sector.lower().replace(" ", "_")
    sector_bias = cfg.get("sector_weight_bias", {}).get(sector, {}) if sector else {}

    # 전문가별 가중치 결정 (ADX/VIX 동적 + 섹터 편향)
    weights = {}
    for op in opinions:
        name = op.expert_name
        w = base_w

        # 1단계: ADX/VIX 기반 동적 가중치
        if "추세" in name and adx is not None and adx > cfg.get("trend_boost_adx_threshold", 30):
            w = base_w * boost
        elif "일목" in name and adx is not None and adx > cfg.get("trend_boost_adx_threshold", 30):
            w = base_w * boost
        elif "가치" in name and adx is not None and adx < cfg.get("value_boost_adx_threshold", 20):
            w = base_w * boost
        elif "역발상" in name and vix is not None and vix > cfg.get("contrarian_boost_vix_threshold", 25):
            w = base_w * boost

        # 2단계: 섹터별 가중치 편향 곱셈
        if sector_bias:
            for keyword, bias_mult in sector_bias.items():
                if keyword in name:
                    w *= bias_mult
                    break

        weights[name] = round(w, 3)

    # 가중 집계
    w_buy = sum(weights.get(o.expert_name, base_w) for o in opinions if o.position == "매수")
    w_sell = sum(weights.get(o.expert_name, base_w) for o in opinions if o.position == "매도")
    w_hold = sum(weights.get(o.expert_name, base_w) for o in opinions if o.position == "홀드")
    total = w_buy + w_sell + w_hold

    dominant = "매수" if w_buy > w_sell and w_buy > w_hold else "매도" if w_sell > w_buy and w_sell > w_hold else "홀드"

    # ─── 시장 사이클 복합 판별 (Howard Marks) ───
    cycle_score = 0
    cycle_reasons = []

    if vix is not None:
        if vix < 15:
            cycle_score += 2
            cycle_reasons.append(f"VIX {vix:.0f} < 15 (안정)")
        elif vix < 25:
            cycle_score += 0
        elif vix < 35:
            cycle_score -= 1
            cycle_reasons.append(f"VIX {vix:.0f} (고변동)")
        else:
            cycle_score -= 2
            cycle_reasons.append(f"VIX {vix:.0f} (극단공포)")

    if macro:
        rate = macro.get("treasury_10y")
        if rate and rate.get("trend"):
            if rate["trend"] == "상승":
                cycle_score -= 1
                cycle_reasons.append("금리 상승")
            elif rate["trend"] == "하락":
                cycle_score += 1
                cycle_reasons.append("금리 하락")

        sp = macro.get("sp500")
        if sp and sp.get("trend"):
            if sp["trend"] == "상승":
                cycle_score += 1
                cycle_reasons.append("S&P500 상승추세")
            elif sp["trend"] == "하락":
                cycle_score -= 1
                cycle_reasons.append("S&P500 하락추세")

    if cycle_score >= 3:
        market_phase = "강세장"
    elif cycle_score >= 1:
        market_phase = "보통"
    elif cycle_score >= -1:
        market_phase = "주의"
    else:
        market_phase = "약세장"

    # 약세장에서 매수 dominant이면 확신도 감점 플래그
    confidence_penalty = 0
    if market_phase == "약세장" and dominant == "매수":
        confidence_penalty = -10
    elif market_phase == "강세장" and dominant == "매도":
        confidence_penalty = -5  # 강세장에서 매도는 소폭 감점

    # ─── 전문가 충돌 패턴 해석 ───
    opinion_conflicts = _detect_opinion_conflicts(opinions)

    return {
        "weighted_buy": round(w_buy, 2),
        "weighted_sell": round(w_sell, 2),
        "weighted_hold": round(w_hold, 2),
        "dominant": dominant,
        "weights_used": weights,
        "total_weight": round(total, 2),
        "market_cycle": {
            "phase": market_phase,
            "score": cycle_score,
            "reasons": cycle_reasons,
            "confidence_penalty": confidence_penalty,
        },
        "opinion_conflicts": opinion_conflicts,
    }


def _detect_opinion_conflicts(opinions: list) -> list:
    """
    전문가 의견 충돌 패턴 해석

    전문가간 포지션이 서로 상충할 때 그 의미를 해석합니다.
    5명의 전문가 중 특정 조합의 충돌은 시장 상태에 대한 중요한 신호입니다.
    """
    positions = {}
    for o in opinions:
        positions[o.expert_name] = o.position

    conflicts = []

    # 추세추종 vs 역발상 충돌 = 변곡점
    trend_pos = positions.get("추세추종 전문가")
    contra_pos = positions.get("역발상 전문가")
    if trend_pos and contra_pos:
        if trend_pos == "매수" and contra_pos == "매도":
            conflicts.append("추세추종↑ vs 역발상↓ → 추세 피크 가능성, 분할 매도 고려")
        elif trend_pos == "매도" and contra_pos == "매수":
            conflicts.append("추세추종↓ vs 역발상↑ → 바닥 반전 가능성, 분할 매수 고려")

    # 가치분석 vs 모멘텀 충돌 = 가치함정 or 고평가 성장
    value_pos = positions.get("가치분석 전문가")
    momentum_pos = positions.get("모멘텀 트레이더")
    if value_pos and momentum_pos:
        if value_pos == "매수" and momentum_pos == "매도":
            conflicts.append("가치분석↑ vs 모멘텀↓ → 가치함정 주의, 모멘텀 반전 확인 후 진입")
        elif value_pos == "매도" and momentum_pos == "매수":
            conflicts.append("가치분석↓ vs 모멘텀↑ → 고평가 성장주, 추세 지속 여부 확인")

    # 일목균형표 vs 역발상 충돌 = 구름 위 과매수
    ichimoku_pos = positions.get("일목균형표 전문가")
    if ichimoku_pos and contra_pos:
        if ichimoku_pos == "매수" and contra_pos == "매도":
            conflicts.append("일목균형표↑ vs 역발상↓ → 구름 위 과매수, 단기 조정 후 재진입 고려")
        elif ichimoku_pos == "매도" and contra_pos == "매수":
            conflicts.append("일목균형표↓ vs 역발상↑ → 구름 아래 과매도, 반전 시점 탐색")

    # 전원 일치 = 높은 확신 (but 컨센서스 과밀 주의)
    unique_positions = set(positions.values())
    if len(positions) >= 4 and len(unique_positions) == 1:
        pos = unique_positions.pop()
        conflicts.append(f"5전문가 {pos} 일치 → 높은 확신, 단 컨센서스 과밀 시 역발상 관점 점검")

    return conflicts
