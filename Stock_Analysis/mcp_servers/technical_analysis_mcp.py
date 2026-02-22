#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Technical Analysis MCP Server
  - 14개 기술적 지표 계산 + 매매 신호 생성
  - DB 모드: data_id/analysis_id로 참조 (토큰 97% 절감)
  - 폴백 모드: 기존 JSON 전달 방식 하위 호환
  - FastMCP 프레임워크 사용 (stdio 전송)
═══════════════════════════════════════════════════════════════

도구 목록:
  1. run_full_analysis   - 14개 지표 일괄 계산 (SMA, RSI, MACD, BB, 일목 등)
  2. generate_signals    - 기술적 지표 기반 종합 매매 신호
  3. calc_single_indicator - 개별 지표 계산 (선택적)
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

from technical_analysis import (
    run_full_analysis as _run_full_analysis,
    generate_signals as _generate_signals,
    add_moving_averages,
    add_rsi,
    add_macd,
    add_bollinger_bands,
    add_stochastic,
    add_atr,
    add_adx,
    add_obv,
    add_ichimoku,
    add_ichimoku_angles,
)
from common.db import (
    is_db_available,
    create_session,
    get_session,
    load_ohlcv,
    store_indicators,
    load_indicators,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("TechnicalAnalysis")


def _json_to_df(ohlcv_json: str) -> pd.DataFrame:
    """JSON(fetch_stock_data 반환값) → DataFrame 복원"""
    data = json.loads(ohlcv_json)

    # fetch_stock_data의 반환값에서 'data' 키 추출
    if isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        records = data

    df = pd.DataFrame.from_dict(records, orient="index")
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_index()
    return df


def _df_to_json(df: pd.DataFrame) -> str:
    """DataFrame → 안전한 JSON (NaN → null)"""
    data = df.copy()
    data.index = data.index.strftime("%Y-%m-%d")
    # NaN/Inf 를 None으로 변환
    data = data.replace([np.inf, -np.inf], np.nan)
    return data.where(data.notna(), None).to_json(orient="index", date_format="iso")


def _resolve_dataframe(ohlcv_json: str = "", data_id: str = "") -> tuple:
    """
    data_id 또는 ohlcv_json에서 DataFrame 복원

    우선순위: data_id (DB) > ohlcv_json (JSON)

    Returns:
        tuple: (df, ticker, interval, data_id_used)
    """
    # 1) data_id 우선: DB에서 로드
    if data_id and is_db_available():
        session = get_session(data_id)
        if session:
            df = load_ohlcv(session_id=data_id)
            if df is not None and not df.empty:
                return df, session["ticker"], session["interval"], data_id

    # 2) ohlcv_json 폴백
    if ohlcv_json:
        parsed = json.loads(ohlcv_json)
        # data_id가 JSON 안에 있는 경우 (DB 모드 반환값)
        if isinstance(parsed, dict) and "data_id" in parsed and not parsed.get("_fallback"):
            inner_id = parsed["data_id"]
            if is_db_available():
                session = get_session(inner_id)
                if session:
                    df = load_ohlcv(session_id=inner_id)
                    if df is not None and not df.empty:
                        return df, session["ticker"], session["interval"], inner_id

        # 일반 JSON 데이터
        df = _json_to_df(ohlcv_json)
        ticker = parsed.get("ticker", "UNKNOWN") if isinstance(parsed, dict) else "UNKNOWN"
        interval = parsed.get("interval", "1d") if isinstance(parsed, dict) else "1d"
        return df, ticker, interval, None

    raise ValueError("data_id 또는 ohlcv_json 중 하나는 필수입니다")


def _resolve_analysis(analysis_json: str = "", analysis_id: str = "") -> tuple:
    """
    analysis_id 또는 analysis_json에서 지표 DataFrame 복원

    Returns:
        tuple: (df, ticker, interval, analysis_id_used)
    """
    # 1) analysis_id 우선: DB에서 지표 로드
    if analysis_id and is_db_available():
        df = load_indicators(session_id=analysis_id)
        if df is not None and not df.empty:
            session = get_session(analysis_id)
            ticker = session["ticker"] if session else "UNKNOWN"
            interval = session["interval"] if session else "1d"
            return df, ticker, interval, analysis_id

    # 2) analysis_json 폴백
    if analysis_json:
        parsed = json.loads(analysis_json)
        # analysis_id가 JSON 안에 있는 경우 (DB 모드 반환값)
        if isinstance(parsed, dict) and "analysis_id" in parsed and not parsed.get("_fallback"):
            inner_id = parsed["analysis_id"]
            if is_db_available():
                df = load_indicators(session_id=inner_id)
                if df is not None and not df.empty:
                    session = get_session(inner_id)
                    ticker = session["ticker"] if session else "UNKNOWN"
                    interval = session["interval"] if session else "1d"
                    return df, ticker, interval, inner_id

        # 일반 JSON 데이터
        df = _json_to_df(analysis_json)
        ticker = parsed.get("ticker", "UNKNOWN") if isinstance(parsed, dict) else "UNKNOWN"
        interval = parsed.get("interval", "1d") if isinstance(parsed, dict) else "1d"
        return df, ticker, interval, None

    raise ValueError("analysis_id 또는 analysis_json 중 하나는 필수입니다")


# ═══════════════════════════════════════════════════════════════
# 도구 1: 전체 기술적 지표 계산
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def run_full_analysis(ohlcv_json: str = "", data_id: str = "") -> str:
    """
    OHLCV 데이터에 14개 기술적 지표를 계산합니다.
    SMA(5/20/60/120), EMA(12/26), RSI, MACD, 볼린저밴드, 스토캐스틱,
    ATR, ADX, OBV, 일목균형표, 일목빗각을 포함합니다.

    Args:
        ohlcv_json: fetch_stock_data 도구의 반환값 (JSON 문자열, 폴백용)
        data_id: fetch_stock_data가 반환한 data_id (DB 모드, 우선)

    Returns:
        DB 모드: {analysis_id, data_id, ticker, interval, rows, indicator_columns, latest_indicators} (~3KB)
        폴백 모드: {rows, indicator_columns, latest_indicators, data} (기존 호환)
    """
    try:
        df, ticker, interval, resolved_data_id = _resolve_dataframe(ohlcv_json, data_id)
        df = _run_full_analysis(df)

        # 추가된 지표 컬럼 추출
        base_cols = {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}
        indicator_cols = [c for c in df.columns if c not in base_cols]

        # 최근 지표값 요약
        latest = df.iloc[-1]
        summary = {}
        for col in indicator_cols:
            val = latest.get(col)
            if val is not None and not (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                summary[col] = round(float(val), 4) if isinstance(val, (int, float, np.floating)) else val

        # ── DB 모드: 지표를 DB에 저장, 참조 ID만 반환 ──
        if is_db_available() and resolved_data_id:
            try:
                analysis_session_id = create_session(
                    session_type="full_analysis",
                    ticker=ticker,
                    interval=interval,
                    parent_id=resolved_data_id,
                    metadata={"indicator_count": len(indicator_cols)},
                )
                if analysis_session_id:
                    stored = store_indicators(df, ticker, interval, analysis_session_id)
                    result = {
                        "analysis_id": analysis_session_id,
                        "data_id": resolved_data_id,
                        "ticker": ticker,
                        "interval": interval,
                        "rows": len(df),
                        "stored_rows": stored,
                        "indicator_columns": indicator_cols,
                        "latest_indicators": summary,
                    }
                    return json.dumps(result, ensure_ascii=False, indent=2, default=str)
            except Exception as e:
                logger.warning(f"지표 DB 저장 실패, JSON 폴백: {e}")

        # ── 폴백 모드: 기존 방식 ──
        result = {
            "rows": len(df),
            "indicator_columns": indicator_cols,
            "latest_indicators": summary,
            "data": json.loads(_df_to_json(df)),
            "_fallback": True,
        }
        if ticker != "UNKNOWN":
            result["ticker"] = ticker
            result["interval"] = interval
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"기술적 분석 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 2: 종합 매매 신호
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def generate_signals(analysis_json: str = "", analysis_id: str = "") -> str:
    """
    기술적 지표 기반으로 종합 매매 신호를 생성합니다.
    RSI, MACD, 이동평균, 볼린저밴드, 스토캐스틱, ADX, 일목균형표 등을 종합합니다.

    Args:
        analysis_json: run_full_analysis 도구의 반환값 (JSON 문자열, 폴백용)
        analysis_id: run_full_analysis가 반환한 analysis_id (DB 모드, 우선)

    Returns:
        JSON: {지표별_신호, 종합판단 (매수우세/매도우세/중립)}
    """
    try:
        df, ticker, interval, resolved_id = _resolve_analysis(analysis_json, analysis_id)
        signals = _generate_signals(df)

        # tuple을 dict로 변환
        formatted = {}
        for key, val in signals.items():
            if isinstance(val, tuple) and len(val) == 2:
                formatted[key] = {"value": val[0], "interpretation": val[1]}
            else:
                formatted[key] = val

        return json.dumps(formatted, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"신호 생성 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 3: 개별 지표 계산
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def calc_single_indicator(ohlcv_json: str = "", data_id: str = "",
                                indicator: str = "") -> str:
    """
    개별 기술적 지표를 선택적으로 계산합니다.

    Args:
        ohlcv_json: fetch_stock_data 도구의 반환값 (JSON 문자열, 폴백용)
        data_id: fetch_stock_data가 반환한 data_id (DB 모드, 우선)
        indicator: 지표 이름 (rsi/macd/bollinger/stochastic/atr/adx/obv/ichimoku/moving_averages)

    Returns:
        JSON: 해당 지표 컬럼의 최근 데이터
    """
    func_map = {
        "moving_averages": add_moving_averages,
        "rsi": add_rsi,
        "macd": add_macd,
        "bollinger": add_bollinger_bands,
        "stochastic": add_stochastic,
        "atr": add_atr,
        "adx": add_adx,
        "obv": add_obv,
        "ichimoku": add_ichimoku,
        "ichimoku_angles": add_ichimoku_angles,
    }

    if indicator not in func_map:
        return json.dumps({
            "error": f"지원하지 않는 지표: {indicator}",
            "available": list(func_map.keys()),
        }, ensure_ascii=False)

    try:
        df, ticker, interval, resolved_id = _resolve_dataframe(ohlcv_json, data_id)
        base_cols = set(df.columns)
        df = func_map[indicator](df)
        new_cols = [c for c in df.columns if c not in base_cols]

        latest = df.iloc[-1]
        values = {}
        for col in new_cols:
            val = latest.get(col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                values[col] = round(float(val), 4) if isinstance(val, (int, float, np.floating)) else val

        result = {
            "indicator": indicator,
            "columns_added": new_cols,
            "latest_values": values,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"지표 계산 실패: {str(e)}"}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
