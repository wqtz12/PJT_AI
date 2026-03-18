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
    get_latest_analysis_session,
)

from datetime import datetime, date

logger = logging.getLogger(__name__)

mcp = FastMCP("TechnicalAnalysis")


def _compute_ohlcv_checksum(df, n: int = 10) -> float:
    """
    OHLCV DataFrame의 최근 N일 Close 합계 체크섬.
    주식분할/데이터 소급조정 감지용.
    """
    if df is None or df.empty:
        return 0.0
    try:
        closes = df["Close"].tail(n).dropna()
        return round(float(closes.sum()), 4)
    except Exception:
        return 0.0


def _try_cached_analysis(data_id: str, ticker: str, interval: str, ohlcv_rows: int = 0):
    """
    DB에서 기존 분석 결과 재사용 시도

    전략:
    - data_id(OHLCV 세션)가 증분 수집(cache_hit)으로 만들어진 경우,
      기존 full_analysis 결과가 아직 유효할 수 있음
    - 해당 종목의 최신 full_analysis를 찾아 데이터가 동일한지 확인
    - 날짜 비교 + 체크섬(Close 합계) 비교 → 주식분할 감지
    - 행 수 비교 → period 불일치 감지
    - 동일하면 기존 analysis_id 재사용

    Returns:
        dict (결과 JSON) 또는 None (재사용 불가)
    """
    if not is_db_available() or not data_id:
        return None

    try:
        # data_id 세션의 메타데이터 확인
        data_session = get_session(data_id)
        if not data_session:
            return None

        # 해당 종목의 최신 full_analysis 세션 조회
        latest_analysis = get_latest_analysis_session(ticker, interval)
        if not latest_analysis:
            return None

        analysis_id = latest_analysis["id"]
        created_at = latest_analysis["created_at"]

        # 분석이 오늘 생성된 것인지 확인
        if hasattr(created_at, 'date'):
            analysis_date = created_at.date()
        else:
            analysis_date = created_at
        if analysis_date != date.today():
            return None  # 어제 이전 분석은 재사용하지 않음

        # 기존 분석 데이터 로드 확인
        existing_df = load_indicators(session_id=analysis_id)
        if existing_df is None or existing_df.empty:
            return None

        # 새 OHLCV 데이터 로드
        new_ohlcv = load_ohlcv(session_id=data_id)
        if new_ohlcv is None or new_ohlcv.empty:
            return None

        # ── 검증 1: 날짜 범위 비교 ──
        analysis_last_date = existing_df.index[-1].date() if hasattr(existing_df.index[-1], 'date') else existing_df.index[-1]
        ohlcv_last_date = new_ohlcv.index[-1].date() if hasattr(new_ohlcv.index[-1], 'date') else new_ohlcv.index[-1]

        if analysis_last_date < ohlcv_last_date:
            return None  # 새 데이터가 있어 재계산 필요

        # ── 검증 2: 행 수 비교 (period 불일치 감지) ──
        # 기존 분석 행 수와 새 OHLCV 행 수 차이가 20% 이상이면 period 변경으로 간주
        if ohlcv_rows > 0 and abs(len(existing_df) - ohlcv_rows) / max(ohlcv_rows, 1) > 0.2:
            logger.info(
                f"[{ticker}] 분석 캐시 무효: 행 수 불일치 "
                f"(기존={len(existing_df)}, 새 OHLCV={ohlcv_rows})"
            )
            return None

        # ── 검증 3: 체크섬 비교 (주식분할/데이터 소급조정 감지) ──
        existing_checksum = _compute_ohlcv_checksum(existing_df, n=10)
        new_checksum = _compute_ohlcv_checksum(new_ohlcv, n=10)
        if existing_checksum > 0 and new_checksum > 0:
            diff_pct = abs(existing_checksum - new_checksum) / existing_checksum * 100
            if diff_pct > 1.0:  # 1% 이상 차이 → 분할/조정 발생
                logger.info(
                    f"[{ticker}] 분석 캐시 무효: 체크섬 불일치 "
                    f"(기존={existing_checksum}, 새={new_checksum}, 차이={diff_pct:.2f}%)"
                )
                return None

        # ── 모든 검증 통과 → 캐시 재사용! ──
        base_cols = {"Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"}
        indicator_cols = [c for c in existing_df.columns if c not in base_cols]

        latest = existing_df.iloc[-1]
        summary = {}
        for col in indicator_cols:
            val = latest.get(col)
            if val is not None and not (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                summary[col] = round(float(val), 4) if isinstance(val, (int, float, np.floating)) else val

        logger.info(
            f"[{ticker}] 기술분석 DB 캐시 히트: analysis_id={analysis_id[:8]}... "
            f"({len(existing_df)}행, 최신={analysis_last_date})"
        )

        result = {
            "analysis_id": analysis_id,
            "data_id": data_id,
            "ticker": ticker,
            "interval": interval,
            "rows": len(existing_df),
            "cached": True,
            "indicator_columns": indicator_cols,
            "latest_indicators": summary,
        }
        return result

    except Exception as e:
        logger.debug(f"[{ticker}] 분석 캐시 확인 실패: {e}")
        return None


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

        # ── 캐시 확인: 기존 분석 결과 재사용 가능한지 검사 (토큰 절약) ──
        cached = _try_cached_analysis(resolved_data_id, ticker, interval, ohlcv_rows=len(df))
        if cached is not None:
            return json.dumps(cached, ensure_ascii=False, indent=2, default=str)

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
