#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Expert Analysis MCP Server
  - 5명 전문가 독립 분석 + 의견 후처리 + 가중 집계
  - 백테스트 & VaR 위험 분석
  - FastMCP 프레임워크 사용 (stdio 전송)
═══════════════════════════════════════════════════════════════

도구 목록:
  1. analyze_all_experts - 5전문가 통합 분석 + 가중 집계 + 필터
  2. analyze_single_expert - 개별 전문가 분석
  3. run_backtest       - 백테스트 시뮬레이션
  4. compute_var        - VaR 위험 분석
  5. compute_risk_metrics - 종합 리스크 지표
"""
import sys
import os
import json
import logging

_STOCK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _STOCK_ROOT not in sys.path:
    sys.path.insert(0, _STOCK_ROOT)

import pandas as pd
import numpy as np
from mcp.server.fastmcp import FastMCP

from expert_strategies import ALL_EXPERTS
from opinion_filter import apply_opinion_filters
from backtester import (
    run_backtest as _run_backtest,
    compute_var as _compute_var,
    compute_risk_metrics as _compute_risk_metrics,
    generate_backtest_report as _generate_backtest_report,
)
from scraper_adapter import (
    enrich_company_info_with_sentiment,
    compute_news_sentiment_summary,
)
from macro_fetcher import enrich_company_info_with_macro
from common.config import get_config
from common.aggregation import aggregate_expert_opinions
from common.db import (
    is_db_available, get_session, load_indicators,
    create_session, store_expert_opinions,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("ExpertAnalysis")


def _json_to_df(data_json: str) -> pd.DataFrame:
    """JSON → DataFrame 복원"""
    data = json.loads(data_json)
    if isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        records = data
    df = pd.DataFrame.from_dict(records, orient="index")
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_index()
    return df


def _resolve_analysis_df(analysis_json: str) -> pd.DataFrame:
    """
    analysis_json에서 DataFrame 복원 (DB 모드 자동 감지)
    analysis_json 안에 analysis_id가 있으면 DB에서 로드
    """
    parsed = json.loads(analysis_json)

    # DB 모드: analysis_id가 있고 _fallback이 아닌 경우
    if isinstance(parsed, dict) and "analysis_id" in parsed and not parsed.get("_fallback"):
        aid = parsed["analysis_id"]
        if is_db_available():
            df = load_indicators(session_id=aid)
            if df is not None and not df.empty:
                return df

    # 폴백: 기존 JSON 방식
    return _json_to_df(analysis_json)


def _parse_company_info(info_json: str) -> dict:
    """company_info JSON 파싱"""
    info = json.loads(info_json)
    if isinstance(info, dict) and "error" in info:
        return {"이름": "Unknown"}
    return info


def _aggregate_expert_opinions(opinions: list, df, company_info: dict) -> dict:
    """전문가 의견 가중 집계 - common.aggregation.aggregate_expert_opinions 위임"""
    return aggregate_expert_opinions(opinions, df, company_info)


# ═══════════════════════════════════════════════════════════════
# 도구 1: 5전문가 통합 분석
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def analyze_all_experts(analysis_json: str, company_info_json: str, macro_json: str = "", sentiment_json: str = "") -> str:
    """
    5명의 전문가(추세추종, 가치분석, 모멘텀, 역발상, 일목균형표)가 독립 분석 후
    ADX/VIX 기반 동적 가중치로 집계합니다. 의견 후처리 필터도 적용됩니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값 (기술적 지표 포함 OHLCV)
        company_info_json: fetch_company_info 도구의 반환값
        macro_json: fetch_macro_indicators 도구의 반환값 (선택)
        sentiment_json: fetch_news 도구의 sentiment_summary (선택)

    Returns:
        JSON: {experts: [{name, position, confidence, targets, rationale}],
               aggregated: {dominant, weighted_buy/sell/hold},
               filters_applied: [...]}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        company_info = _parse_company_info(company_info_json)

        # 매크로/감성 enrichment
        if macro_json:
            try:
                macro_data = json.loads(macro_json)
                enrich_company_info_with_macro(company_info, macro_data)
            except Exception:
                pass

        if sentiment_json:
            try:
                sent_data = json.loads(sentiment_json)
                # sentiment_summary(긍정/부정/중립/총건수) → score/confidence 변환
                if "score" not in sent_data and "총건수" in sent_data:
                    total = sent_data.get("총건수", 0)
                    pos = sent_data.get("긍정", 0)
                    neg = sent_data.get("부정", 0)
                    if total > 0:
                        raw_score = (pos - neg) / total
                        min_articles = 5
                        confidence = min(1.0, total / min_articles)
                        sent_data = {
                            "score": round(raw_score * confidence, 4),
                            "raw_score": round(raw_score, 4),
                            "label": sent_data.get("종합감성", "중립적"),
                            "positive_count": pos,
                            "negative_count": neg,
                            "neutral_count": sent_data.get("중립", 0),
                            "total_count": total,
                            "confidence": round(confidence, 2),
                        }
                company_info["_sentiment"] = sent_data
            except Exception:
                pass

        # 5전문가 분석
        opinions = []
        errors = []
        for ExpertClass in ALL_EXPERTS:
            try:
                opinion = ExpertClass.analyze(df, company_info)
                opinions.append(opinion)
            except Exception as e:
                errors.append(f"{ExpertClass.NAME}: {str(e)}")

        # 의견 후처리 필터
        filters_applied = []
        try:
            _of_cfg = get_config().get("opinion_filters", {})
            if _of_cfg.get("enabled", True) and opinions:
                pre_positions = {o.expert_name: o.position for o in opinions}
                opinions = apply_opinion_filters(opinions, df, company_info)
                for o in opinions:
                    if pre_positions.get(o.expert_name) != o.position:
                        filters_applied.append(
                            f"{o.expert_name}: {pre_positions[o.expert_name]} → {o.position}"
                        )
        except Exception:
            pass

        # 가중 집계
        aggregated = _aggregate_expert_opinions(opinions, df, company_info)

        result = {
            "experts": [o.to_dict() for o in opinions],
            "aggregated": aggregated,
            "filters_applied": filters_applied,
            "errors": errors,
            "expert_count": len(opinions),
        }

        # ── DB 저장 (side-effect, fail-safe) ──
        if is_db_available():
            try:
                parsed_analysis = json.loads(analysis_json)
                _ticker = "UNKNOWN"
                _analysis_id = None
                if isinstance(parsed_analysis, dict):
                    _ticker = parsed_analysis.get("ticker", "UNKNOWN")
                    _analysis_id = (parsed_analysis.get("analysis_id")
                                    or parsed_analysis.get("data_id"))

                # DB 모드에서 ticker가 없으면 세션에서 조회
                if _ticker == "UNKNOWN" and _analysis_id:
                    try:
                        sess = get_session(_analysis_id)
                        if sess and sess.get("ticker"):
                            _ticker = sess["ticker"]
                    except Exception:
                        pass

                # 여전히 UNKNOWN이면 로그 경고 (회사명은 ticker가 아니므로 사용하지 않음)
                if _ticker == "UNKNOWN":
                    logger.warning(f"expert DB 저장: ticker 추출 실패 (analysis_id={_analysis_id})")

                sid = create_session(
                    session_type="expert", ticker=_ticker,
                    metadata={"expert_count": len(opinions),
                              "dominant": aggregated.get("dominant")},
                )
                if sid:
                    store_expert_opinions(
                        result["experts"], aggregated, filters_applied,
                        _ticker, sid, analysis_id=_analysis_id,
                    )
            except Exception as e:
                logger.warning(f"전문가의견 DB 저장 실패: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"전문가 분석 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 2: 개별 전문가 분석
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def analyze_single_expert(analysis_json: str, company_info_json: str, expert_name: str) -> str:
    """
    특정 전문가 1명만 선택하여 분석합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        company_info_json: fetch_company_info 도구의 반환값
        expert_name: 전문가 이름 (trend/value/momentum/contrarian/ichimoku)

    Returns:
        JSON: {전문가, 포지션, 확신도, 매수가, 매도가, 근거, 핵심지표}
    """
    name_map = {
        "trend": 0,
        "value": 1,
        "momentum": 2,
        "contrarian": 3,
        "ichimoku": 4,
    }

    if expert_name not in name_map:
        return json.dumps({
            "error": f"지원하지 않는 전문가: {expert_name}",
            "available": list(name_map.keys()),
        }, ensure_ascii=False)

    try:
        df = _resolve_analysis_df(analysis_json)
        company_info = _parse_company_info(company_info_json)
        ExpertClass = ALL_EXPERTS[name_map[expert_name]]
        opinion = ExpertClass.analyze(df, company_info)
        return json.dumps(opinion.to_dict(), ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": f"분석 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 3: 백테스트
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def run_backtest(analysis_json: str, expert_json: str = "") -> str:
    """
    과거 데이터 기반 백테스트 시뮬레이션입니다.
    총 수익률, 연환산 수익률, MDD, 샤프비율, 승률을 계산합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        expert_json: analyze_all_experts 도구의 반환값 (선택)

    Returns:
        JSON: {총수익률, 연환산수익률, 최대낙폭, 샤프비율, 승률, 수익팩터, ...}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        bt_result = _run_backtest(df, expert_opinions=None)
        return json.dumps(bt_result.to_dict(), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"백테스트 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 4: VaR 분석
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def compute_var(analysis_json: str, confidence: float = 0.95) -> str:
    """
    VaR (Value at Risk) 위험도를 분석합니다.
    히스토리컬 VaR, 파라메트릭 VaR, 조건부 VaR(CVaR)를 제공합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        confidence: VaR 신뢰수준 (기본: 0.95 = 95%)

    Returns:
        JSON: {히스토리컬VaR, 파라메트릭VaR, 조건부VaR, 변동성, 왜도, 첨도}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        var_result = _compute_var(df, confidence=confidence)
        return json.dumps(var_result.to_dict(), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"VaR 분석 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 5: 종합 리스크 지표
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def compute_risk_metrics(analysis_json: str) -> str:
    """
    종합 리스크 지표를 계산합니다: 일일/연환산 변동성, MDD, 샤프비율, 왜도, 첨도.

    Args:
        analysis_json: run_full_analysis 도구의 반환값

    Returns:
        JSON: {일일변동성, 연환산변동성, 최대낙폭, 샤프비율, 평균수익률, 왜도, 첨도}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        metrics = _compute_risk_metrics(df)
        # float 변환
        result = {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"리스크 지표 계산 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
