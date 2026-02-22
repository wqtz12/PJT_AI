#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Stock Data Collector MCP Server
  - yfinance 기반 주가/기업정보/뉴스/애널리스트/매크로 데이터 수집
  - FastMCP 프레임워크 사용 (stdio 전송)
═══════════════════════════════════════════════════════════════

도구 목록:
  1. fetch_stock_data      - OHLCV 주가 데이터 수집 + 품질 검증
  2. fetch_company_info    - 기업 기본 정보 (섹터, PER, PBR, 시총 등)
  3. validate_price        - 실시간 vs 히스토리 가격 교차 검증
  4. fetch_news            - 종목 관련 뉴스 + 감성 분석
  5. fetch_analyst_ratings - 애널리스트 투자의견 수집
  6. fetch_analyst_summary - 컨센서스 요약 (강력매수~강력매도)
  7. fetch_macro_indicators- 매크로 지표 6종 (VIX, 금리, S&P500 등)
  8. clear_cache           - 특정 종목 캐시 삭제
"""
import sys
import os
import json
import logging

# Stock_Analysis 루트를 sys.path에 추가 (common, data_fetcher 등 임포트용)
_STOCK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _STOCK_ROOT not in sys.path:
    sys.path.insert(0, _STOCK_ROOT)

from mcp.server.fastmcp import FastMCP

# 기존 모듈 임포트
from data_fetcher import (
    fetch_stock_data as _fetch_stock_data,
    fetch_company_info as _fetch_company_info,
    validate_price_freshness as _validate_price_freshness,
    InsufficientDataError,
)
from scraper_adapter import (
    fetch_news as _fetch_news,
    fetch_analyst_ratings as _fetch_analyst_ratings,
    fetch_analyst_summary as _fetch_analyst_summary,
    compute_news_sentiment_summary as _compute_news_sentiment_summary,
)
from macro_fetcher import (
    fetch_macro_indicators as _fetch_macro_indicators,
    compute_macro_summary as _compute_macro_summary,
)
from common.cache import (
    cached_call,
    get_market_aware_ttl,
    detect_market,
    clear_ticker_cache as _clear_ticker_cache,
    cache_stats as _cache_stats,
)
from common.db import (
    is_db_available,
    create_session,
    store_ohlcv,
    store_company_info,
    store_news_sentiment,
    store_macro_indicators,
)

logger = logging.getLogger(__name__)

# ─── MCP 서버 인스턴스 ───
mcp = FastMCP("StockDataCollector")


def _df_to_json(df) -> str:
    """DataFrame → JSON 직렬화 (날짜 인덱스 포함)"""
    data = df.copy()
    data.index = data.index.strftime("%Y-%m-%d")
    return data.to_json(orient="index", date_format="iso")


# ═══════════════════════════════════════════════════════════════
# 도구 1: 주가 데이터 수집
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_stock_data(ticker: str, period: str = "6mo", interval: str = "1d") -> str:
    """
    yfinance API로 OHLCV 주가 데이터를 수집하고 품질을 검증합니다.

    Args:
        ticker: 종목 코드 (예: 'NVDA', 'AAPL', '005930.KS')
        period: 수집 기간 (1mo/3mo/6mo/1y/2y/5y, 기본: 6mo)
        interval: 데이터 간격 (1d=일봉/1wk=주봉/1mo=월봉, 기본: 1d)

    Returns:
        JSON: DB 모드 → {data_id, ticker, rows, latest_close, ...} (~2KB)
              폴백 모드 → {data, ticker, rows, ...} (기존 호환)
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"stock_data_{ticker}_{period}_{interval}"
        df = cached_call(cache_key, _fetch_stock_data, ticker, period, interval,
                         ttl_minutes=get_market_aware_ttl(30, _mkt))

        # ── DB 모드: 데이터를 DB에 저장하고 참조 ID만 반환 ──
        if is_db_available():
            try:
                session_id = create_session(
                    session_type="ohlcv",
                    ticker=ticker,
                    interval=interval,
                    period=period,
                    metadata={"source": "yfinance", "market": _mkt},
                )
                if session_id:
                    stored = store_ohlcv(df, ticker, interval, session_id)
                    result = {
                        "data_id": session_id,
                        "ticker": ticker,
                        "period": period,
                        "interval": interval,
                        "rows": len(df),
                        "stored_rows": stored,
                        "start_date": str(df.index[0].date()),
                        "end_date": str(df.index[-1].date()),
                        "latest_close": float(df.iloc[-1]["Close"]),
                        "latest_volume": int(df.iloc[-1]["Volume"]),
                    }
                    return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"DB 저장 실패, JSON 폴백: {e}")

        # ── 폴백 모드: 기존 방식 (전체 데이터 JSON 반환) ──
        result = {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "rows": len(df),
            "start_date": str(df.index[0].date()),
            "end_date": str(df.index[-1].date()),
            "latest_close": float(df.iloc[-1]["Close"]),
            "latest_volume": int(df.iloc[-1]["Volume"]),
            "data": json.loads(_df_to_json(df)),
            "_fallback": True,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except InsufficientDataError as e:
        return json.dumps({"error": f"데이터 부족: {str(e)}", "ticker": ticker}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"수집 실패: {str(e)}", "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 2: 기업 기본 정보
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_company_info(ticker: str) -> str:
    """
    yfinance에서 기업 기본 정보를 수집합니다.

    Args:
        ticker: 종목 코드 (예: 'MSFT', '005930.KS')

    Returns:
        JSON: 이름, 섹터, 시가총액, PER, PBR, EPS, 52주 범위, 부채비율, 현금 등
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"company_info_{ticker}"
        info = cached_call(cache_key, _fetch_company_info, ticker,
                           ttl_minutes=get_market_aware_ttl(60, _mkt))

        # ── DB 저장 (side-effect, fail-safe) ──
        if is_db_available():
            try:
                sid = create_session(session_type="company_info", ticker=ticker,
                                     metadata={"source": "yfinance", "market": _mkt})
                if sid:
                    store_company_info(info, ticker, sid)
            except Exception as e:
                logger.warning(f"기업정보 DB 저장 실패: {e}")

        return json.dumps(info, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": f"기업정보 수집 실패: {str(e)}", "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 3: 가격 교차 검증
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def validate_price(ticker: str, period: str = "6mo") -> str:
    """
    히스토리 종가와 실시간 가격을 교차 검증합니다 (괴리율 5% 경고).

    Args:
        ticker: 종목 코드
        period: OHLCV 데이터 기간 (기본: 6mo)

    Returns:
        JSON: {valid, history_price, realtime_price, discrepancy_pct, warning}
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"stock_data_{ticker}_{period}"
        df = cached_call(cache_key, _fetch_stock_data, ticker, period,
                         ttl_minutes=get_market_aware_ttl(30, _mkt))
        result = _validate_price_freshness(df, ticker)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 4: 뉴스 수집 + 감성 분석
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_news(ticker: str, max_count: int = 10) -> str:
    """
    종목 관련 뉴스를 수집하고 감성(긍정/부정/중립)을 분석합니다.
    한국 종목(.KS/.KQ)은 네이버 뉴스로 자동 폴백합니다.

    Args:
        ticker: 종목 코드 (예: 'GOOGL', '065450.KQ')
        max_count: 최대 수집 건수 (기본: 10)

    Returns:
        JSON: {articles: [{제목, 출처, 감성, ...}], sentiment_summary: {긍정, 부정, 중립, 종합감성}}
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"news_{ticker}"
        articles = cached_call(cache_key, _fetch_news, ticker, max_articles=max_count,
                               ttl_minutes=get_market_aware_ttl(15, _mkt))
        sentiment = _compute_news_sentiment_summary(articles)

        result = {
            "ticker": ticker,
            "articles": [a.to_dict() for a in articles],
            "sentiment_summary": sentiment,
        }

        # ── DB 저장 (side-effect, fail-safe) ──
        if is_db_available():
            try:
                sid = create_session(session_type="news", ticker=ticker,
                                     metadata={"source": "yfinance/naver",
                                               "count": len(articles)})
                if sid:
                    store_news_sentiment(result["articles"], ticker, sid)
            except Exception as e:
                logger.warning(f"뉴스감성 DB 저장 실패: {e}")

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 5: 애널리스트 투자의견
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_analyst_ratings(ticker: str, top_n: int = 8) -> str:
    """
    애널리스트 투자의견(증권사, 등급, 목표가)을 수집합니다.
    한국 종목은 네이버 리서치로 자동 폴백합니다.

    Args:
        ticker: 종목 코드
        top_n: 최근 N건 수집 (기본: 8)

    Returns:
        JSON: [{증권사, 날짜, 등급, 포지션, 목표가, ...}]
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"analyst_ratings_{ticker}"
        ratings = cached_call(cache_key, _fetch_analyst_ratings, ticker, top_n=top_n,
                              ttl_minutes=get_market_aware_ttl(60, _mkt))
        result = {
            "ticker": ticker,
            "count": len(ratings),
            "ratings": [r.to_dict() for r in ratings],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 6: 애널리스트 컨센서스 요약
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_analyst_summary(ticker: str) -> str:
    """
    애널리스트 컨센서스 요약 (강력매수~강력매도, 목표가 범위)을 수집합니다.

    Args:
        ticker: 종목 코드

    Returns:
        JSON: {추천수, 등급표시, 목표가_평균/최고/최저, 강력매수/매수/보유/매도 수}
    """
    try:
        _mkt = detect_market(ticker)
        cache_key = f"analyst_summary_{ticker}"
        summary = cached_call(cache_key, _fetch_analyst_summary, ticker,
                              ttl_minutes=get_market_aware_ttl(60, _mkt))
        return json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 7: 매크로경제 지표 6종
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_macro_indicators() -> str:
    """
    매크로경제 지표 6종을 수집합니다: VIX, 10Y 국채금리, S&P500, WTI 원유, 금, 달러 인덱스.
    각 지표의 현재값, 변동률, 20일 평균, 추세를 제공합니다.

    Returns:
        JSON: {vix: {...}, treasury_10y: {...}, sp500: {...}, oil: {...}, gold: {...}, dollar: {...}, summary: {...}}
    """
    try:
        cache_key = "macro_indicators"
        macro = cached_call(cache_key, _fetch_macro_indicators,
                            ttl_minutes=get_market_aware_ttl(120, "US"))
        summary = _compute_macro_summary(macro)
        macro["summary"] = summary

        # ── DB 저장 (side-effect, fail-safe) ──
        if is_db_available():
            try:
                sid = create_session(session_type="macro", ticker="MACRO",
                                     metadata={"source": "yfinance",
                                               "available": macro.get("_available_count", 0)})
                if sid:
                    store_macro_indicators(macro, sid)
            except Exception as e:
                logger.warning(f"매크로지표 DB 저장 실패: {e}")

        return json.dumps(macro, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 도구 8: 캐시 관리
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
async def clear_cache(ticker: str = "") -> str:
    """
    캐시를 삭제합니다. 종목을 지정하면 해당 종목만, 비우면 전체 캐시 통계를 반환합니다.

    Args:
        ticker: 종목 코드 (비우면 캐시 통계만 반환)

    Returns:
        JSON: {action, deleted_count} 또는 {cache_stats}
    """
    try:
        if ticker:
            count = _clear_ticker_cache(ticker)
            return json.dumps({"action": "clear", "ticker": ticker, "deleted_count": count}, ensure_ascii=False)
        else:
            stats = _cache_stats()
            return json.dumps({"action": "stats", "cache": stats}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
