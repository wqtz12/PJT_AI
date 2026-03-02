"""
═══════════════════════════════════════════════════════════════
  Scheduler Analysis Wrapper
  - stock_analyzer.py 파이프라인을 배치 실행에 최적화하여 재사용
  - 기존 코드 무수정, 동일한 내부 함수 직접 import
═══════════════════════════════════════════════════════════════
"""
import os
import sys
import time
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# 프로젝트 루트를 PYTHONPATH에 추가 + cwd 변경
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)  # 기존 모듈들이 cwd 기반 상대경로 사용

from data_fetcher import fetch_stock_data, fetch_company_info, InsufficientDataError, validate_price_freshness
from technical_analysis import run_full_analysis, generate_signals
from visualizer import (
    plot_candlestick_with_indicators,
    plot_technical_dashboard,
    plot_performance_summary,
)
from scraper_adapter import (
    fetch_news,
    fetch_analyst_ratings,
    fetch_analyst_summary,
    compute_news_sentiment_summary,
    enrich_company_info_with_sentiment,
)
from macro_fetcher import fetch_macro_indicators, enrich_company_info_with_macro
from expert_strategies import ALL_EXPERTS
from opinion_filter import apply_opinion_filters
from common.aggregation import aggregate_expert_opinions
from common.cache import cached_call, get_market_aware_ttl, detect_market, clear_ticker_cache, set_cache
from common.config import get_config
from common.error_tracker import record_error, ErrorCategory
from stock_analyzer import build_report

logger = logging.getLogger("scheduler.analysis")

# matplotlib 스레드 안전성을 위한 Lock
_chart_lock = threading.Lock()


@dataclass
class AnalysisResult:
    """단일 종목 분석 결과 (알림 및 이력 저장용)"""
    ticker: str
    name: str = ""
    success: bool = True
    error_message: Optional[str] = None

    # 핵심 결과 (알림 요약용)
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    dominant_position: Optional[str] = None  # "매수" / "매도" / "홀드"
    weighted_buy: float = 0.0
    weighted_sell: float = 0.0
    weighted_hold: float = 0.0
    avg_confidence: float = 0.0
    expert_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0

    # 컨텍스트
    technical_signal: Optional[str] = None
    macro_environment: Optional[str] = None
    news_sentiment_label: Optional[str] = None
    analyst_consensus: Optional[str] = None

    # 파일 경로
    report_path: Optional[str] = None
    chart_paths: list = field(default_factory=list)

    # 타이밍
    analysis_duration_sec: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def _safe_record_error(category, module, message, exception=None, context=None):
    """에러 추적 (실패해도 무시)"""
    try:
        record_error(category=category, module=module, message=message,
                     exception=exception, context=context)
    except Exception:
        pass


def analyze_single_ticker(
    ticker: str,
    macro_data: Optional[dict] = None,
    analysis_type: str = "full",
    output_dir: Optional[str] = None,
) -> AnalysisResult:
    """
    단일 종목 Full Pipeline 분석.

    stock_analyzer.py::main()과 동일한 파이프라인이지만:
    - setup_logging() / run_daily_analysis() 호출 안함
    - macro_data 외부 주입 가능 (배치 내 공유)
    - AnalysisResult 구조화 결과 반환

    Args:
        ticker: 종목 코드 (예: "AAPL", "005930.KS")
        macro_data: 사전 수집된 매크로 데이터 (None이면 내부 수집)
        analysis_type: "full" 또는 "quick"
        output_dir: 결과 저장 디렉토리 (None이면 output/scheduled/YYYYMMDD/)
    """
    start_time = time.time()
    result = AnalysisResult(ticker=ticker)

    # 출력 디렉토리 설정
    if output_dir is None:
        date_str = datetime.now().strftime("%Y%m%d")
        output_dir = os.path.join(_PROJECT_ROOT, "output", "scheduled", date_str)
    os.makedirs(output_dir, exist_ok=True)

    _mkt = detect_market(ticker)
    cfg = get_config()

    try:
        # ═══ Step 1: 주가 데이터 수집 ═══
        logger.info(f"[{ticker}] 주가 데이터 수집...")
        cache_key_stock = f"stock_data_{ticker}_6mo"
        period = "3mo" if analysis_type == "quick" else "6mo"
        df = cached_call(cache_key_stock, fetch_stock_data, ticker, period,
                         ttl_minutes=get_market_aware_ttl(30, _mkt))
        logger.info(f"[{ticker}] {len(df)}일 데이터 수집 완료")

        # 가격 교차검증
        _pv_cfg = cfg.get("price_validation", {})
        if _pv_cfg.get("enabled", True):
            try:
                price_check = validate_price_freshness(
                    df, ticker, threshold_pct=_pv_cfg.get("threshold_pct", 5.0))
                if not price_check["valid"] and _pv_cfg.get("auto_refresh", True):
                    disc = price_check.get("discrepancy_pct", 0) or 0
                    if disc > _pv_cfg.get("threshold_pct", 5.0):
                        clear_ticker_cache(ticker)
                        df = fetch_stock_data(ticker, period)
                        set_cache(cache_key_stock, df)
            except Exception:
                pass

        # ═══ Step 2: 기업 정보 ═══
        logger.info(f"[{ticker}] 기업 정보 수집...")
        cache_key_info = f"company_info_{ticker}"
        company_info = cached_call(cache_key_info, fetch_company_info, ticker,
                                   ttl_minutes=get_market_aware_ttl(60, _mkt))
        name = company_info.get("이름") or ticker
        result.name = name

        # ═══ Step 3: 기술적 분석 ═══
        logger.info(f"[{ticker}] 기술적 지표 계산...")
        df = run_full_analysis(df)
        signals = generate_signals(df)
        result.technical_signal = signals.get("종합판단", "N/A")

        # ═══ Step 4: 뉴스/애널리스트/매크로 병렬 수집 ═══
        logger.info(f"[{ticker}] 뉴스/애널리스트 수집...")
        analyst_ratings = []
        analyst_summary = {}
        articles = []

        if analysis_type == "full":
            def _fetch_ratings():
                return cached_call(f"analyst_ratings_{ticker}", fetch_analyst_ratings,
                                   ticker, top_n=8,
                                   ttl_minutes=get_market_aware_ttl(60, _mkt))

            def _fetch_summary():
                return cached_call(f"analyst_summary_{ticker}", fetch_analyst_summary,
                                   ticker, ttl_minutes=get_market_aware_ttl(60, _mkt))

            def _fetch_articles():
                return cached_call(f"news_{ticker}", fetch_news, ticker,
                                   max_articles=10,
                                   ttl_minutes=get_market_aware_ttl(15, _mkt))

            task_map = {
                "ratings": _fetch_ratings,
                "summary": _fetch_summary,
                "news": _fetch_articles,
            }

            # 매크로가 미제공이면 여기서 수집
            if macro_data is None:
                task_map["macro"] = lambda: cached_call(
                    "macro_indicators", fetch_macro_indicators,
                    ttl_minutes=get_market_aware_ttl(120, _mkt))

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(fn): name for name, fn in task_map.items()}
                for future in as_completed(futures):
                    task_name = futures[future]
                    try:
                        res = future.result()
                        if task_name == "ratings":
                            analyst_ratings = res
                        elif task_name == "summary":
                            analyst_summary = res
                        elif task_name == "news":
                            articles = res
                        elif task_name == "macro":
                            macro_data = res
                    except Exception as e:
                        logger.warning(f"[{ticker}] {task_name} 수집 실패: {e}")

        news_sentiment = compute_news_sentiment_summary(articles)

        # ═══ Step 5: Enrichment ═══
        enrich_company_info_with_macro(company_info, macro_data)
        enrich_company_info_with_sentiment(company_info, news_sentiment, articles)

        macro_ctx = company_info.get("_macro")
        if macro_ctx:
            result.macro_environment = macro_ctx.get("시장_환경", "N/A")

        sent_ctx = company_info.get("_sentiment")
        if sent_ctx:
            result.news_sentiment_label = sent_ctx.get("label", "N/A")

        if analyst_summary:
            result.analyst_consensus = analyst_summary.get("등급표시", "N/A")

        # ═══ Step 6: 5전문가 분석 ═══
        logger.info(f"[{ticker}] 5전문가 분석...")
        expert_opinions = []
        for ExpertClass in ALL_EXPERTS:
            try:
                opinion = ExpertClass.analyze(df, company_info)
                expert_opinions.append(opinion)
            except Exception as e:
                logger.error(f"[{ticker}] {ExpertClass.NAME} 분석 실패: {e}")
                _safe_record_error(ErrorCategory.EXPERT_STRATEGY, "scheduler",
                                   f"[{ExpertClass.NAME}] 실패: {e}", e, {"ticker": ticker})

        # 의견 후처리 필터
        try:
            _of_cfg = cfg.get("opinion_filters", {})
            if _of_cfg.get("enabled", True) and expert_opinions:
                expert_opinions = apply_opinion_filters(expert_opinions, df, company_info)
        except Exception:
            pass

        # 가중 집계
        try:
            agg = aggregate_expert_opinions(expert_opinions, df, company_info)
            result.dominant_position = agg.get("dominant", "홀드")
            result.weighted_buy = agg.get("weighted_buy", 0)
            result.weighted_sell = agg.get("weighted_sell", 0)
            result.weighted_hold = agg.get("weighted_hold", 0)
        except Exception:
            pass

        # 결과 집계
        result.expert_count = len(expert_opinions)
        result.buy_count = sum(1 for o in expert_opinions if o.position == "매수")
        result.sell_count = sum(1 for o in expert_opinions if o.position == "매도")
        result.hold_count = sum(1 for o in expert_opinions if o.position == "홀드")
        result.avg_confidence = (sum(o.confidence for o in expert_opinions)
                                 / len(expert_opinions)) if expert_opinions else 0

        # 현재가
        latest = df.iloc[-1]
        result.current_price = float(latest["Close"])
        if len(df) > 1:
            prev = float(df.iloc[-2]["Close"])
            result.change_pct = ((result.current_price - prev) / prev * 100) if prev else 0

        # ═══ Step 7: 차트 생성 ═══
        if analysis_type == "full":
            logger.info(f"[{ticker}] 차트 생성...")
            chart_funcs = [
                ("캔들스틱", plot_candlestick_with_indicators),
                ("대시보드", plot_technical_dashboard),
                ("성과", plot_performance_summary),
            ]
            for chart_name, chart_func in chart_funcs:
                try:
                    with _chart_lock:
                        path = chart_func(df, ticker, name)
                    if path:
                        result.chart_paths.append(path)
                except Exception as e:
                    logger.warning(f"[{ticker}] {chart_name} 차트 실패: {e}")

        # ═══ Step 8: 리포트 생성 & 저장 ═══
        logger.info(f"[{ticker}] 리포트 생성...")
        report = build_report(
            ticker=ticker,
            company_info=company_info,
            df=df,
            signals=signals,
            expert_opinions=expert_opinions,
            analyst_ratings=analyst_ratings,
            analyst_summary=analyst_summary,
            articles=articles,
            news_sentiment=news_sentiment,
            chart_paths=result.chart_paths,
            macro_data=macro_data,
        )

        report_path = os.path.join(output_dir, f"{ticker}_full_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        result.report_path = report_path

        result.success = True
        logger.info(f"[{ticker}] 분석 완료: {result.dominant_position} "
                     f"(확신도 {result.avg_confidence:.0f}%)")

    except InsufficientDataError as e:
        result.success = False
        result.error_message = f"데이터 부족: {e}"
        logger.error(f"[{ticker}] {result.error_message}")
    except Exception as e:
        result.success = False
        result.error_message = f"분석 실패: {e}"
        logger.error(f"[{ticker}] {result.error_message}", exc_info=True)
        _safe_record_error(ErrorCategory.DATA_FETCH, "scheduler",
                           f"[{ticker}] 분석 실패: {e}", e, {"ticker": ticker})

    result.analysis_duration_sec = round(time.time() - start_time, 1)
    result.timestamp = datetime.now().isoformat()
    return result


def analyze_watchlist(
    watchlist_name: str,
    tickers: list,
    analysis_type: str = "full",
    max_workers: int = 3,
    rate_limit_delay: float = 2.0,
    output_dir: Optional[str] = None,
) -> list:
    """
    워치리스트 전체 분석.

    1. 매크로 데이터 1회 수집 (전 종목 공유)
    2. 종목별 분석 실행 (rate limit 적용)
    3. 개별 실패는 격리 (다른 종목에 영향 없음)
    """
    start_time = time.time()
    logger.info(f"{'═'*60}")
    logger.info(f"  워치리스트 '{watchlist_name}' 분석 시작: {len(tickers)}종목")
    logger.info(f"{'═'*60}")

    # 출력 디렉토리
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(_PROJECT_ROOT, "output", "scheduled",
                                  f"{watchlist_name}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    # 매크로 데이터 1회 수집 (공유)
    macro_data = None
    if analysis_type == "full":
        try:
            logger.info("매크로 지표 수집 (전 종목 공유)...")
            macro_data = cached_call("macro_indicators", fetch_macro_indicators,
                                     ttl_minutes=120)
            logger.info("매크로 지표 수집 완료")
        except Exception as e:
            logger.warning(f"매크로 지표 수집 실패 (무시): {e}")

    # 종목별 분석 실행
    results = []

    def _analyze_with_delay(idx, ticker):
        if idx > 0 and rate_limit_delay > 0:
            time.sleep(rate_limit_delay)
        return analyze_single_ticker(
            ticker=ticker,
            macro_data=macro_data,
            analysis_type=analysis_type,
            output_dir=output_dir,
        )

    # max_workers=1이면 순차, 그 이상이면 병렬 (rate limit은 submit 간격으로)
    if max_workers <= 1:
        for idx, ticker in enumerate(tickers):
            r = _analyze_with_delay(idx, ticker)
            results.append(r)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, ticker in enumerate(tickers):
                if idx > 0 and rate_limit_delay > 0:
                    time.sleep(rate_limit_delay)
                future = executor.submit(analyze_single_ticker,
                                         ticker=ticker,
                                         macro_data=macro_data,
                                         analysis_type=analysis_type,
                                         output_dir=output_dir)
                futures[future] = ticker

            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    r = future.result()
                    results.append(r)
                except Exception as e:
                    r = AnalysisResult(ticker=ticker, success=False,
                                       error_message=str(e))
                    results.append(r)

    # 결과 요약
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    total_time = round(time.time() - start_time, 1)

    logger.info(f"{'═'*60}")
    logger.info(f"  워치리스트 '{watchlist_name}' 완료: "
                f"{success_count}성공 / {fail_count}실패 ({total_time}초)")
    logger.info(f"{'═'*60}")

    return results
