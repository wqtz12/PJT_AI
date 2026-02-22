#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Stock Report MCP Server
  - 차트 생성 (캔들스틱, 대시보드, 성과) + 텍스트 리포트
  - FastMCP 프레임워크 사용 (stdio 전송)
═══════════════════════════════════════════════════════════════

도구 목록:
  1. generate_candlestick   - 캔들스틱 차트 + MA + MACD/RSI/Volume
  2. generate_dashboard     - 기술적 분석 대시보드 (20+ 지표)
  3. generate_performance   - 수익률/변동성/Drawdown 차트
  4. generate_all_charts    - 차트 3종 일괄 생성
  5. generate_text_report   - 텍스트 종합 리포트 생성
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

from visualizer import (
    plot_candlestick_with_indicators,
    plot_technical_dashboard,
    plot_performance_summary,
)
from report_generator import generate_report as _generate_simple_report
from common.db import is_db_available, get_session, load_indicators

logger = logging.getLogger(__name__)

mcp = FastMCP("StockReport")

OUTPUT_DIR = os.path.join(_STOCK_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


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
    """analysis_json에서 DataFrame 복원 (DB 모드 자동 감지)"""
    parsed = json.loads(analysis_json)
    if isinstance(parsed, dict) and "analysis_id" in parsed and not parsed.get("_fallback"):
        aid = parsed["analysis_id"]
        if is_db_available():
            df = load_indicators(session_id=aid)
            if df is not None and not df.empty:
                return df
    return _json_to_df(analysis_json)


# ═══════════════════════════════════════════════════════════════
# 도구 1: 캔들스틱 차트
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_candlestick(analysis_json: str, ticker: str, name: str = "") -> str:
    """
    캔들스틱 차트를 생성합니다 (이동평균 + MACD + RSI + Volume 서브차트).

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        ticker: 종목 코드 (파일명에 사용)
        name: 종목명 (차트 제목에 사용, 선택)

    Returns:
        JSON: {path: "생성된 파일 경로"}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        display_name = name or ticker
        path = plot_candlestick_with_indicators(df, ticker, display_name)
        return json.dumps({"path": path, "type": "candlestick"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"캔들스틱 차트 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 2: 기술적 분석 대시보드
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_dashboard(analysis_json: str, ticker: str, name: str = "") -> str:
    """
    기술적 분석 대시보드를 생성합니다 (20+ 지표를 다중 서브플롯으로 표시).

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        ticker: 종목 코드
        name: 종목명 (선택)

    Returns:
        JSON: {path: "생성된 파일 경로"}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        display_name = name or ticker
        path = plot_technical_dashboard(df, ticker, display_name)
        return json.dumps({"path": path, "type": "dashboard"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"대시보드 차트 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 3: 수익률/변동성 차트
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_performance(analysis_json: str, ticker: str, name: str = "") -> str:
    """
    수익률/변동성/Drawdown 성과 차트를 생성합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        ticker: 종목 코드
        name: 종목명 (선택)

    Returns:
        JSON: {path: "생성된 파일 경로"}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        display_name = name or ticker
        path = plot_performance_summary(df, ticker, display_name)
        return json.dumps({"path": path, "type": "performance"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"성과 차트 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 4: 차트 3종 일괄 생성
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_all_charts(analysis_json: str, ticker: str, name: str = "") -> str:
    """
    캔들스틱, 대시보드, 성과 차트 3종을 한번에 생성합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값
        ticker: 종목 코드
        name: 종목명 (선택)

    Returns:
        JSON: {charts: [{type, path}], success_count: 3}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        display_name = name or ticker

        charts = []
        chart_funcs = [
            ("candlestick", plot_candlestick_with_indicators),
            ("dashboard", plot_technical_dashboard),
            ("performance", plot_performance_summary),
        ]

        for chart_type, func in chart_funcs:
            try:
                path = func(df, ticker, display_name)
                charts.append({"type": chart_type, "path": path, "status": "success"})
            except Exception as e:
                charts.append({"type": chart_type, "error": str(e), "status": "failed"})

        success_count = sum(1 for c in charts if c["status"] == "success")
        return json.dumps({
            "ticker": ticker,
            "charts": charts,
            "success_count": success_count,
            "total": len(chart_funcs),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"차트 일괄 생성 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 5: 텍스트 리포트
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_text_report(
    ticker: str,
    company_info_json: str,
    analysis_json: str,
    signals_json: str,
    chart_paths_json: str = "[]",
) -> str:
    """
    텍스트 종합 분석 리포트를 생성하고 파일로 저장합니다.

    Args:
        ticker: 종목 코드
        company_info_json: fetch_company_info의 반환값
        analysis_json: run_full_analysis의 반환값
        signals_json: generate_signals의 반환값
        chart_paths_json: 차트 파일 경로 배열 (JSON)

    Returns:
        JSON: {report_path, report_preview (처음 500자)}
    """
    try:
        df = _resolve_analysis_df(analysis_json)
        company_info = json.loads(company_info_json)
        signals_raw = json.loads(signals_json)

        # signals를 tuple 형식으로 복원
        signals = {}
        for key, val in signals_raw.items():
            if isinstance(val, dict) and "value" in val and "interpretation" in val:
                signals[key] = (val["value"], val["interpretation"])
            else:
                signals[key] = val

        chart_paths = json.loads(chart_paths_json)

        report = _generate_simple_report(
            ticker=ticker,
            company_info=company_info,
            df=df,
            signals=signals,
            chart_paths=chart_paths,
        )

        # 파일 저장
        report_path = os.path.join(OUTPUT_DIR, f"{ticker}_full_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return json.dumps({
            "report_path": report_path,
            "report_preview": report[:500] + "..." if len(report) > 500 else report,
            "total_length": len(report),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"리포트 생성 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
