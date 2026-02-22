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

    # 전문가별 가중치 결정
    weights = {}
    for op in opinions:
        name = op.expert_name
        w = base_w

        if "추세" in name and adx is not None and adx > cfg.get("trend_boost_adx_threshold", 30):
            w = base_w * boost
        elif "일목" in name and adx is not None and adx > cfg.get("trend_boost_adx_threshold", 30):
            w = base_w * boost
        elif "가치" in name and adx is not None and adx < cfg.get("value_boost_adx_threshold", 20):
            w = base_w * boost
        elif "역발상" in name and vix is not None and vix > cfg.get("contrarian_boost_vix_threshold", 25):
            w = base_w * boost

        weights[name] = w

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
    }
