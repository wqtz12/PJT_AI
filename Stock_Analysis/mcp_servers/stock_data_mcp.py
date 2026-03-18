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
    get_latest_ohlcv_date,
    load_ohlcv_all,
    load_company_info,
    get_latest_company_info_date,
)

from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

# ─── MCP 서버 인스턴스 ───
mcp = FastMCP("StockDataCollector")


# ═══════════════════════════════════════════════════════════════
# 시장별 거래일/시간 판단 헬퍼
# ═══════════════════════════════════════════════════════════════

def _get_market_now(mkt: str):
    """
    시장 timezone 기준의 현재 시각 반환

    Args:
        mkt: "US" 또는 "KR"

    Returns:
        datetime (tz-aware)
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz_map = {"US": "America/New_York", "KR": "Asia/Seoul"}
    tz = ZoneInfo(tz_map.get(mkt, "America/New_York"))
    return datetime.now(tz)


def _is_market_closed_today(mkt: str) -> bool:
    """
    오늘 해당 시장이 이미 장 마감했는지 판단

    US: 16:30 EST 이후 → 종가 확정 (16:00 마감 + 30분 여유)
    KR: 16:00 KST 이후 → 종가 확정 (15:30 마감 + 30분 여유)

    Returns:
        True = 오늘 장 마감 완료 (종가 수집 가능)
    """
    now = _get_market_now(mkt)
    close_hour = {"US": 16, "KR": 16}.get(mkt, 16)
    close_minute = {"US": 30, "KR": 0}.get(mkt, 30)
    return now.hour > close_hour or (now.hour == close_hour and now.minute >= close_minute)


def _get_market_today(mkt: str):
    """시장 timezone 기준의 오늘 날짜"""
    return _get_market_now(mkt).date()


def _is_weekend(d) -> bool:
    """주말 여부 (토=5, 일=6)"""
    return d.weekday() >= 5


def _get_last_expected_trading_date(mkt: str):
    """
    시장별 '가장 최근 예상 거래일' 계산

    - 장 마감 후 → 오늘
    - 장 전/장중 → 어제 (주말이면 금요일)
    - 주말 → 직전 금요일

    Returns:
        datetime.date
    """
    from datetime import date as _date

    market_today = _get_market_today(mkt)
    closed_today = _is_market_closed_today(mkt)

    if closed_today and not _is_weekend(market_today):
        # 오늘 장 마감됨 → 오늘 데이터 있어야 함
        return market_today

    # 장 전/장중/주말 → 직전 거래일
    d = market_today if not closed_today else market_today
    if not closed_today:
        d = d - timedelta(days=1)  # 아직 장중이면 어제부터
    # 주말 스킵
    while _is_weekend(d):
        d = d - timedelta(days=1)
    return d


# period → 일수 매핑 (여유분 +60일 포함, 기술분석 SMA_120 계산에 필요)
_PERIOD_TO_DAYS = {
    "1mo": 90, "3mo": 150, "6mo": 240,
    "1y": 425, "2y": 790, "5y": 1885,
}


# ═══════════════════════════════════════════════════════════════
# 증분(Incremental) 데이터 수집 헬퍼
# ═══════════════════════════════════════════════════════════════

def _try_incremental_fetch(ticker: str, period: str, interval: str, mkt: str):
    """
    DB에 기존 데이터가 있으면 증분 수집 시도

    전략:
    - DB에서 해당 종목의 최신 저장 날짜 조회
    - 시장 timezone 기준으로 '마지막 예상 거래일'과 비교
    - DB 데이터가 최신이면 → 캐시 재사용 (yfinance 호출 0)
    - 부족하면 → 부족한 기간만 추가 수집 → DB 병합

    Returns:
        tuple: (merged_df, session_id, reused_rows, new_rows) 또는 None (증분 불가)
    """
    if not is_db_available():
        return None

    try:
        latest_date = get_latest_ohlcv_date(ticker, interval)
        if latest_date is None:
            return None  # DB에 데이터 없음 → 전체 수집 필요

        from datetime import date as _date

        last_expected = _get_last_expected_trading_date(mkt)

        # DB의 최신 날짜가 마지막 예상 거래일 이상이면 → 캐시 재사용
        if latest_date >= last_expected:
            existing_df = load_ohlcv_all(ticker, interval,
                                         since_days=_PERIOD_TO_DAYS.get(period, 240))
            if existing_df is not None and len(existing_df) >= 20:
                # ── #4 수정: 캐시히트에도 period에 맞게 트림 ──
                existing_df = _trim_to_period(existing_df, period)
                logger.info(
                    f"[{ticker}] DB 캐시 히트: {len(existing_df)}행, "
                    f"DB최신={latest_date}, 예상거래일={last_expected} → 재사용"
                )
                session_id = create_session(
                    session_type="ohlcv",
                    ticker=ticker,
                    interval=interval,
                    period=period,
                    metadata={
                        "source": "db_cache",
                        "market": mkt,
                        "cache_hit": True,
                        "original_rows": len(existing_df),
                    },
                )
                if session_id:
                    store_ohlcv(existing_df, ticker, interval, session_id)
                    return existing_df, session_id, len(existing_df), 0

        # DB 데이터가 부족 → 부족한 기간만 추가 수집
        # 안전하게 latest_date - 5일부터 수집 (겹침 허용, ON CONFLICT UPDATE)
        fetch_start = latest_date - timedelta(days=5)
        fetch_start_str = fetch_start.strftime("%Y-%m-%d")
        # end = 내일 날짜 (yfinance end는 exclusive → 내일로 설정해야 오늘 포함)
        market_today = _get_market_today(mkt)
        fetch_end = market_today + timedelta(days=1)
        fetch_end_str = fetch_end.strftime("%Y-%m-%d")

        logger.info(
            f"[{ticker}] 증분 수집: DB최신={latest_date}, "
            f"예상거래일={last_expected}, 수집 {fetch_start_str}~{fetch_end_str}"
        )

        # yfinance start/end 방식으로 부분 수집
        import yfinance as yf
        stock = yf.Ticker(ticker)
        delta_df = stock.history(start=fetch_start_str, end=fetch_end_str, interval=interval)

        if delta_df.empty:
            # 추가 데이터 없음 (시장 휴장 등) → 기존 DB 데이터 사용
            existing_df = load_ohlcv_all(ticker, interval,
                                         since_days=_PERIOD_TO_DAYS.get(period, 240))
            if existing_df is not None and len(existing_df) >= 20:
                existing_df = _trim_to_period(existing_df, period)
                session_id = create_session(
                    session_type="ohlcv",
                    ticker=ticker,
                    interval=interval,
                    period=period,
                    metadata={
                        "source": "db_cache_no_new",
                        "market": mkt,
                        "cache_hit": True,
                    },
                )
                if session_id:
                    store_ohlcv(existing_df, ticker, interval, session_id)
                    return existing_df, session_id, len(existing_df), 0
            return None

        # 새 데이터를 DB에 저장 (ON CONFLICT UPDATE)
        session_id = create_session(
            session_type="ohlcv",
            ticker=ticker,
            interval=interval,
            period=period,
            metadata={
                "source": "yfinance_incremental",
                "market": mkt,
                "incremental": True,
                "delta_rows": len(delta_df),
            },
        )
        if session_id:
            store_ohlcv(delta_df, ticker, interval, session_id)

        # DB에서 병합된 전체 데이터 로드 (period 범위만 — 누적 방지)
        merged_df = load_ohlcv_all(ticker, interval,
                                   since_days=_PERIOD_TO_DAYS.get(period, 240))
        if merged_df is not None and len(merged_df) >= 20:
            # 요청된 period에 맞게 데이터 트리밍
            merged_df = _trim_to_period(merged_df, period)
            logger.info(
                f"[{ticker}] 증분 완료: 기존+추가 → {len(merged_df)}행"
            )
            return merged_df, session_id, len(merged_df) - len(delta_df), len(delta_df)

        return None

    except Exception as e:
        logger.warning(f"[{ticker}] 증분 수집 실패, 전체 수집으로 폴백: {e}")
        return None


def _trim_to_period(df, period: str):
    """period 문자열에 맞게 DataFrame을 최근 N개월/년으로 트림"""
    if df is None or df.empty:
        return df

    from datetime import date as _date

    period_map = {
        "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825,
    }
    days = period_map.get(period, 180)
    cutoff = pd.Timestamp(_date.today() - timedelta(days=days))
    # tz-aware 인덱스면 tz-naive로 비교하기 위해 tz 제거
    idx = df.index
    if hasattr(idx, 'tz') and idx.tz is not None:
        idx = idx.tz_localize(None)
    trimmed = df[idx >= cutoff]
    return trimmed if len(trimmed) >= 10 else df


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

        # ── 1단계: DB 증분 수집 시도 (토큰 절약 핵심) ──
        incremental = _try_incremental_fetch(ticker, period, interval, _mkt)
        if incremental is not None:
            df, session_id, reused_rows, new_rows = incremental
            result = {
                "data_id": session_id,
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "rows": len(df),
                "reused_rows": reused_rows,
                "new_rows": new_rows,
                "incremental": True,
                "start_date": str(df.index[0].date()),
                "end_date": str(df.index[-1].date()),
                "latest_close": float(df.iloc[-1]["Close"]),
                "latest_volume": int(df.iloc[-1]["Volume"]),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # ── 2단계: 전체 수집 (첫 번째 호출 또는 증분 실패) ──
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
                    metadata={"source": "yfinance_full", "market": _mkt},
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
                        "incremental": False,
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

        # ── DB 캐시 확인: TTL 4시간 이내 데이터가 있으면 재사용 (토큰 절약) ──
        _COMPANY_INFO_TTL_HOURS = 4
        if is_db_available():
            try:
                latest_dt = get_latest_company_info_date(ticker)
                if latest_dt is not None:
                    # TTL 기반 판단 (날짜가 아닌 시간 단위)
                    if hasattr(latest_dt, 'hour'):
                        # datetime 객체 → 직접 비교
                        elapsed = datetime.now() - latest_dt
                    else:
                        # date 객체 → datetime 변환
                        elapsed = datetime.now() - datetime.combine(latest_dt, datetime.min.time())
                    if elapsed < timedelta(hours=_COMPANY_INFO_TTL_HOURS):
                        cached_info = load_company_info(ticker=ticker)
                        if cached_info:
                            logger.info(
                                f"[{ticker}] 기업정보 DB 캐시 히트: "
                                f"{latest_dt} (경과 {elapsed.seconds // 3600}h{(elapsed.seconds % 3600) // 60}m)"
                            )
                            return json.dumps(cached_info, ensure_ascii=False, indent=2, default=str)
            except Exception as e:
                logger.debug(f"[{ticker}] 기업정보 DB 캐시 조회 실패: {e}")

        # ── yfinance에서 신규 수집 ──
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
