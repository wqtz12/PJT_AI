"""
전문가 의견 가중 집계 모듈

시장 상태에 따라 전문가별 가중치를 조정:
- ADX > 30 (강한 추세): 추세추종/일목 가중치 ↑
- ADX < 20 (횡보): 가치분석 가중치 ↑
- VIX > 25 (고변동): 역발상 가중치 ↑
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

    return {
        "weighted_buy": round(w_buy, 2),
        "weighted_sell": round(w_sell, 2),
        "weighted_hold": round(w_hold, 2),
        "dominant": dominant,
        "weights_used": weights,
        "total_weight": round(total, 2),
    }
