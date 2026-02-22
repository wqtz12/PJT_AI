#!/usr/bin/env python3
"""
=================================================================
  Stock & Coin 종합 분석기 (stock_analyzer.py)
  - 통합 분석 스크립트 (뉴스 항상 포함)
=================================================================

파이프라인:
  yfinance API → [6개월 OHLCV 데이터]
    → [기술적 지표 계산] → MA20, MA50, RSI, 52주 범위
    → [뉴스/애널리스트/매크로 병렬 수집]
    → [company_info enrichment] → _macro, _sentiment 주입
    → [4전문가 전략 적용] → 매크로/감성 반영 매수/매도 산출
    → [통합 리포트 출력]
"""
import os
import sys
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.logger import setup_logging, get_logger, AnalysisError
from common.cache import cached_call, cache_stats, set_cache, clear_ticker_cache, get_market_aware_ttl, detect_market
from common.config import get_config
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
from common.models import ExpertOpinion
from common.aggregation import aggregate_expert_opinions as _aggregate_opinions_impl
from common.error_tracker import record_error, ErrorCategory
from log_analyzer import run_daily_analysis

logger = get_logger(__name__)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _track_error(category: ErrorCategory, module: str, message: str,
                 exception: Exception = None, context: dict = None):
    """파이프라인 에러를 구조화 로그에 기록 (실패해도 무시)"""
    try:
        record_error(
            category=category,
            module=module,
            message=message,
            exception=exception,
            context=context,
        )
    except Exception:
        pass  # 에러 추적 실패가 메인 파이프라인을 중단시키면 안됨


# ─────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────
def fmt_num(num):
    """숫자를 읽기 쉬운 형태로"""
    if isinstance(num, str) or num is None or num == "N/A":
        return str(num) if num else "N/A"
    if abs(num) >= 1e12:
        return f"${num/1e12:.2f}T"
    if abs(num) >= 1e9:
        return f"${num/1e9:.2f}B"
    if abs(num) >= 1e6:
        return f"${num/1e6:.2f}M"
    if abs(num) >= 1e3:
        return f"${num/1e3:.1f}K"
    return f"${num:.2f}" if isinstance(num, float) else str(num)


def bar_chart(value: float, max_val: float = 100, width: int = 20) -> str:
    """텍스트 막대 그래프"""
    ratio = min(max(value / max_val, 0), 1.0)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────────────
# 전문가 가중 집계 (common.aggregation 위임)
# ─────────────────────────────────────────────────────
def _aggregate_expert_opinions(opinions: list, df, company_info: dict) -> dict:
    """전문가 의견 가중 집계 - common.aggregation.aggregate_expert_opinions 위임"""
    return _aggregate_opinions_impl(opinions, df, company_info)


# ─────────────────────────────────────────────────────
# 통합 리포트 생성
# ─────────────────────────────────────────────────────
def build_report(
    ticker: str,
    company_info: dict,
    df,
    signals: dict,
    expert_opinions: list,
    analyst_ratings: list,
    analyst_summary: dict,
    articles: list,
    news_sentiment: dict,
    chart_paths: list,
    macro_data: dict = None,
) -> str:
    """전체 통합 리포트 문자열 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    latest = df.iloc[-1]
    price = latest["Close"]
    prev = df.iloc[-2]["Close"] if len(df) > 1 else price
    change = price - prev
    change_pct = (change / prev) * 100 if prev else 0

    high_52w = company_info.get("52주_최고") or 0
    low_52w = company_info.get("52주_최저") or 0
    range_pct = ((price - low_52w) / (high_52w - low_52w) * 100) if high_52w != low_52w else 0

    r = ""
    L = "━" * 70

    # ▶ 헤더
    r += f"""
{'╔' + '═'*68 + '╗'}
║{'':^68}║
║{f'{company_info.get("이름", ticker)} ({ticker}) 종합 분석 리포트':^60}║
║{f'생성일시: {now}':^64}║
║{'':^68}║
{'╚' + '═'*68 + '╝'}
"""

    # ━━━ 1. 기업 개요 ━━━
    r += f"""
{L}
  📌 1. 기업 개요
{L}
  종목명    : {company_info.get('이름') or 'N/A'}
  섹터/산업 : {company_info.get('섹터') or 'N/A'} / {company_info.get('산업') or 'N/A'}
  시가총액  : {fmt_num(company_info.get('시가총액'))}
  직원수    : {company_info.get('직원수') or 'N/A'}명
  홈페이지  : {company_info.get('홈페이지') or 'N/A'}
"""

    # ━━━ 2. 현재 주가 ━━━
    r += f"""
{L}
  📊 2. 현재 주가 현황
{L}
  현재가     : ${price:.2f}  ({'+' if change >= 0 else ''}{change:.2f}, {'+' if change_pct >= 0 else ''}{change_pct:.2f}%)
  52주 최고  : ${high_52w:.2f}
  52주 최저  : ${low_52w:.2f}
  52주 위치  : [{bar_chart(range_pct)}] {range_pct:.1f}%
  거래량     : {latest['Volume']:,.0f}
"""

    # ━━━ 3. 투자 지표 ━━━
    r += f"""
{L}
  📈 3. 투자 지표
{L}
  PER        : {company_info.get('PER') or 'N/A'}
  PBR        : {company_info.get('PBR') or 'N/A'}
  EPS        : {company_info.get('EPS') or 'N/A'}
  베타       : {company_info.get('베타') or 'N/A'}
  총매출     : {fmt_num(company_info.get('총매출'))}
  영업이익   : {fmt_num(company_info.get('영업이익'))}
  부채비율   : {company_info.get('부채비율') or 'N/A'}
  보유현금   : {fmt_num(company_info.get('현금'))}
"""

    # ━━━ 4. 기술적 분석 신호 ━━━
    r += f"""
{L}
  🔍 4. 기술적 분석 (매매 신호)
{L}
"""
    for ind, val in signals.items():
        if ind == "종합판단":
            continue
        if isinstance(val, tuple) and len(val) == 2:
            v, interp = val
            r += f"  {ind:14s}: {v:22s} → {interp}\n"
        else:
            r += f"  {ind:14s}: {str(val)}\n"

    r += f"""
  ┌{'─'*52}┐
  │  >>> 종합 기술적 판단: {signals.get('종합판단', 'N/A'):30s}│
  └{'─'*52}┘
"""

    # ━━━ 5. 매크로경제 환경 분석 ━━━
    r += f"""
{L}
  🌍 5. 매크로경제 환경 분석
{L}
"""
    macro_ctx = company_info.get("_macro") if company_info else None
    if macro_ctx and macro_data:
        env = macro_ctx.get("시장_환경", "N/A")
        env_score = macro_ctx.get("환경_점수", 0)
        env_emoji = {"위험선호": "🟢", "위험회피": "🔴", "중립": "🟡"}.get(env, "⚪")
        r += f"  시장 환경: {env_emoji} {env} (환경 점수: {env_score:+d})\n\n"

        # 지표 테이블
        r += f"  {'지표':<20} {'현재값':>10} {'변동률':>8} {'20일평균':>10} {'추세':>6}\n"
        r += f"  {'─'*20} {'─'*10} {'─'*8} {'─'*10} {'─'*6}\n"

        indicator_keys = ["vix", "sp500", "treasury_10y", "oil", "gold", "dollar"]
        for key in indicator_keys:
            data = macro_data.get(key)
            if data:
                name = data.get("name", key)[:18]
                current = data.get("current", 0)
                change = data.get("change_pct", 0)
                avg = data.get("avg_20d", 0)
                trend = data.get("trend", "N/A")
                trend_emoji = {"상승": "↑", "하락": "↓", "안정": "→"}.get(trend, "?")

                # VIX는 level도 표시
                extra = f" ({data['level']})" if key == "vix" and "level" in data else ""
                r += f"  {name:<20} {current:>10.2f} {change:>+7.2f}% {avg:>10.2f} {trend_emoji}{trend}{extra}\n"

        r += "\n"
    else:
        r += "  (매크로경제 데이터 수집 불가 또는 비활성)\n\n"

    # ━━━ 5-2. 뉴스 감성 점수 ━━━
    sent_ctx = company_info.get("_sentiment") if company_info else None
    if sent_ctx:
        sent_score = sent_ctx.get("score", 0)
        sent_label = sent_ctx.get("label", "N/A")
        sent_conf = sent_ctx.get("confidence", 0)
        sent_emoji = {"긍정적": "📈", "부정적": "📉", "중립적": "➡️"}.get(sent_label, "❓")
        r += f"  뉴스 감성 점수: {sent_emoji} {sent_score:+.3f} ({sent_label}, 신뢰도 {sent_conf:.0%})\n"
        r += f"  긍정 {sent_ctx.get('positive_count', 0)}건 / 부정 {sent_ctx.get('negative_count', 0)}건 / 중립 {sent_ctx.get('neutral_count', 0)}건\n"

    # ━━━ 6. 5명 전문가 분석 (핵심 섹션) ━━━
    r += f"""
{L}
  🧠 6. 전문가 5인 분석 — 포지션 / 매수가 / 매도가 / 3분할 전략
{L}
"""
    for i, op in enumerate(expert_opinions, 1):
        d = op.to_dict()
        pos_emoji = {"매수": "🟢", "매도": "🔴", "홀드": "🟡"}.get(d["포지션"], "⚪")

        r += f"""
  ┌{'─'*66}┐
  │ 전문가 {i}: {d['전문가']:50s}│
  │ 스타일 : {d['스타일'][:55]:55s}│
  ├{'─'*66}┤
  │ {pos_emoji} 포지션: {d['포지션']:8s}  확신도: {d['확신도']:6s}                        │
  │   매수가  : {d['매수가']:10s}                                          │
  │   매도가  : {d['매도가']:10s}                                          │
  │   손절가  : {d['손절가']:10s}                                          │
  ├{'─'*66}┤
  │ 근거:                                                            │
"""
        # 근거를 줄바꿈하며 넣기
        rationale = d["근거"]
        parts = rationale.split(" | ")
        for part in parts:
            part = part.strip()
            if len(part) > 60:
                part = part[:57] + "..."
            r += f"  │   • {part:62s}│\n"

        # 핵심 지표
        if d["핵심지표"]:
            r += f"  │ 핵심지표:                                                        │\n"
            for ki in d["핵심지표"]:
                if len(ki) > 62:
                    ki = ki[:59] + "..."
                r += f"  │   {ki:64s}│\n"

        # 3분할 매수/매도 가격 표시
        if d.get("3분할_매수") or d.get("3분할_매도"):
            r += f"  ├{'─'*66}┤\n"
            r += f"  │ 📊 3분할 매수/매도 전략                                           │\n"
            if d.get("3분할_매수"):
                bp = d["3분할_매수"]
                r += f"  │   1차 매수(보수적): {bp[0]:>10s}  │  "
                if d.get("3분할_매도"):
                    sp = d["3분할_매도"]
                    r += f"1차 매도(보수적): {sp[0]:>10s}│\n"
                else:
                    r += f"{'':>28s}│\n"
                r += f"  │   2차 매수(중간)  : {bp[1]:>10s}  │  "
                if d.get("3분할_매도"):
                    sp = d["3분할_매도"]
                    r += f"2차 매도(중간)  : {sp[1]:>10s}│\n"
                else:
                    r += f"{'':>28s}│\n"
                r += f"  │   3차 매수(적극적): {bp[2]:>10s}  │  "
                if d.get("3분할_매도"):
                    sp = d["3분할_매도"]
                    r += f"3차 매도(적극적): {sp[2]:>10s}│\n"
                else:
                    r += f"{'':>28s}│\n"

        r += f"  └{'─'*66}┘\n"

    # ━━━ 전문가 종합 요약 ━━━
    buy_count = sum(1 for o in expert_opinions if o.position == "매수")
    sell_count = sum(1 for o in expert_opinions if o.position == "매도")
    hold_count = sum(1 for o in expert_opinions if o.position == "홀드")
    avg_confidence = sum(o.confidence for o in expert_opinions) / len(expert_opinions) if expert_opinions else 0

    buy_prices = [o.buy_price for o in expert_opinions if o.buy_price]
    sell_prices = [o.sell_price for o in expert_opinions if o.sell_price]

    r += f"""
  ┌{'─'*66}┐
  │            📋 전문가 5인 종합 요약                                │
  ├{'─'*66}┤
  │  🟢 매수: {buy_count}명    🟡 홀드: {hold_count}명    🔴 매도: {sell_count}명                      │
  │  평균 확신도: {avg_confidence:.0f}%                                            │
"""
    if buy_prices:
        avg_buy = sum(buy_prices) / len(buy_prices)
        r += f"  │  평균 매수 추천가: ${avg_buy:.2f}                                       │\n"
    if sell_prices:
        avg_sell = sum(sell_prices) / len(sell_prices)
        r += f"  │  평균 매도 추천가: ${avg_sell:.2f}                                       │\n"

    # 3분할 평균 매수/매도가 표시
    split_buys = [o.buy_prices for o in expert_opinions if o.buy_prices and len(o.buy_prices) == 3]
    split_sells = [o.sell_prices for o in expert_opinions if o.sell_prices and len(o.sell_prices) == 3]
    if split_buys:
        avg_sb = [sum(p[i] for p in split_buys) / len(split_buys) for i in range(3)]
        r += f"  ├{'─'*66}┤\n"
        r += f"  │  📊 3분할 평균 매수가: ${avg_sb[0]:.2f} / ${avg_sb[1]:.2f} / ${avg_sb[2]:.2f}           │\n"
    if split_sells:
        avg_ss = [sum(p[i] for p in split_sells) / len(split_sells) for i in range(3)]
        r += f"  │  📊 3분할 평균 매도가: ${avg_ss[0]:.2f} / ${avg_ss[1]:.2f} / ${avg_ss[2]:.2f}           │\n"

    # 가중 집계 결과 표시
    try:
        agg = _aggregate_expert_opinions(expert_opinions, df, company_info)
        if agg.get("weights_used"):
            w_info = f"가중 종합: 매수 {agg['weighted_buy']:.1f} / 홀드 {agg['weighted_hold']:.1f} / 매도 {agg['weighted_sell']:.1f}"
            if len(w_info) > 64:
                w_info = w_info[:61] + "..."
            r += f"  │  {w_info:<64s}│\n"
            r += f"  │  가중 판단: {agg['dominant']:<56s}│\n"
    except Exception:
        pass

    r += f"  └{'─'*66}┘\n"

    # ━━━ 7. 실제 애널리스트 등급 ━━━
    r += f"""
{L}
  🏦 7. 증권사 애널리스트 등급 (최근 리포트)
{L}
"""
    if analyst_ratings:
        r += f"  {'날짜':<12} {'증권사':<22} {'포지션':<6} {'등급':<16} {'변경':<10} {'목표가':>8} {'이전목표가':>10}\n"
        r += f"  {'─'*12} {'─'*22} {'─'*6} {'─'*16} {'─'*10} {'─'*8} {'─'*10}\n"
        for ar in analyst_ratings:
            d = ar.to_dict()
            pos_mark = {"매수": "🟢", "매도": "🔴", "홀드": "🟡"}.get(d["포지션"], "⚪")
            r += f"  {d['날짜']:<12} {d['증권사']:<22} {pos_mark}{d['포지션']:<4} {d['등급']:<16} {d['변경']:<10} {d['목표가']:>8} {d['이전목표가']:>10}\n"
    else:
        r += "  (애널리스트 데이터 없음)\n"

    # 컨센서스 요약
    if analyst_summary:
        r += f"""
  ┌{'─'*52}┐
  │  컨센서스: {analyst_summary.get('등급표시', 'N/A'):40s}│
  │  추천 수 : {analyst_summary.get('추천수', 0)}명                                      │
  │  목표가  : 평균 ${analyst_summary.get('목표가_평균', 0):.2f}  (${analyst_summary.get('목표가_최저', 0):.2f} ~ ${analyst_summary.get('목표가_최고', 0):.2f})      │
"""
        sb = analyst_summary.get("강력매수", 0)
        b = analyst_summary.get("매수", 0)
        h = analyst_summary.get("보유", 0)
        s = analyst_summary.get("매도", 0)
        ss = analyst_summary.get("강력매도", 0)
        r += f"  │  강력매수:{sb} | 매수:{b} | 보유:{h} | 매도:{s} | 강력매도:{ss}              │\n"
        r += f"  └{'─'*52}┘\n"

    # ━━━ 8. 뉴스 & 감성 분석 ━━━
    r += f"""
{L}
  📰 8. 뉴스 트렌드 & 감성 분석
{L}
  뉴스 수집: {news_sentiment.get('총건수', 0)}건
  종합 감성: {news_sentiment.get('종합감성', 'N/A')}
  긍정: {news_sentiment.get('긍정', 0)}건 | 부정: {news_sentiment.get('부정', 0)}건 | 중립: {news_sentiment.get('중립', 0)}건

"""
    if articles:
        for i, art in enumerate(articles[:8], 1):
            emoji = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(art.sentiment, "")
            title = art.title[:60] + "..." if len(art.title) > 60 else art.title
            r += f"  {i}. {emoji} [{art.source}] {title}\n"
            if art.published:
                r += f"     발행: {art.published}\n"
    else:
        r += "  (뉴스 데이터 없음)\n"

    # ━━━ 9. 차트 파일 ━━━
    r += f"""
{L}
  📊 9. 생성된 차트 파일
{L}
"""
    for i, path in enumerate(chart_paths, 1):
        r += f"  [{i}] {os.path.basename(path)}\n"

    # ━━━ 면책조항 ━━━
    r += f"""
{'╔' + '═'*68 + '╗'}
║  ⚠ 본 리포트는 자동 생성된 기술적 분석 자료이며,              ║
║    투자 판단의 참고자료로만 활용하시기 바랍니다.              ║
║    투자에 대한 최종 결정과 책임은 투자자 본인에게 있습니다.   ║
{'╚' + '═'*68 + '╝'}
"""
    return r


# ─────────────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────────────
def main(ticker: str = "PLUG"):
    # 로깅 초기화
    setup_logging(level="INFO", log_to_file=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 일일 에러 로그 분석 (전날 분석 + 오래된 로그 정리)
    run_daily_analysis()

    logger.info(f"{'═'*60}")
    logger.info(f"  {ticker} 종합 분석 시작")
    logger.info(f"{'═'*60}")

    # ── 시장 감지 (동적 TTL용) ──
    _mkt = detect_market(ticker)

    # ── Step 1: 데이터 수집 (캐싱 적용) ──
    logger.info("[1/6] 주가 데이터 수집 중 (6개월)...")
    try:
        cache_key_stock = f"stock_data_{ticker}_6mo"
        df = cached_call(cache_key_stock, fetch_stock_data, ticker, "6mo",
                         ttl_minutes=get_market_aware_ttl(30, _mkt))
        logger.info(f"  {len(df)}일 데이터 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
    except InsufficientDataError as e:
        logger.error(f"데이터 부족으로 분석 중단: {e}")
        _track_error(ErrorCategory.DATA_FETCH, "stock_analyzer", f"데이터 부족: {e}", e, {"ticker": ticker})
        return None
    except Exception as e:
        logger.error(f"주가 데이터 수집 실패: {e}", exc_info=True)
        _track_error(ErrorCategory.DATA_FETCH, "stock_analyzer", f"주가 데이터 수집 실패: {e}", e, {"ticker": ticker})
        return None

    # ── Step 1-2: 가격 교차검증 (P0-1) ──
    _pv_cfg = get_config().get("price_validation", {})
    if _pv_cfg.get("enabled", True):
        try:
            price_check = validate_price_freshness(
                df, ticker,
                threshold_pct=_pv_cfg.get("threshold_pct", 5.0),
            )
            if price_check.get("warning"):
                logger.warning(f"  ⚠ 가격 검증: {price_check['warning']}")
            if not price_check["valid"] and _pv_cfg.get("auto_refresh", True):
                disc = price_check.get("discrepancy_pct", 0) or 0
                if disc > _pv_cfg.get("threshold_pct", 5.0):
                    logger.info(f"  → 가격 괴리 {disc:.1f}% → 캐시 무효화 후 재수집...")
                    clear_ticker_cache(ticker)
                    df = fetch_stock_data(ticker, "6mo")
                    set_cache(cache_key_stock, df)
                    logger.info(f"  → 재수집 완료: {len(df)}일 데이터")
        except Exception as e:
            logger.debug(f"  가격 검증 실패 (무시): {e}")

    logger.info("[2/6] 기업 정보 수집 중...")
    try:
        cache_key_info = f"company_info_{ticker}"
        company_info = cached_call(cache_key_info, fetch_company_info, ticker,
                                   ttl_minutes=get_market_aware_ttl(60, _mkt))
        name = company_info.get("이름") or ticker
        logger.info(f"  {name} | 시가총액 {fmt_num(company_info.get('시가총액'))}")
    except Exception as e:
        logger.warning(f"기업 정보 수집 실패 (계속 진행): {e}")
        _track_error(ErrorCategory.DATA_FETCH, "stock_analyzer", f"기업 정보 수집 실패: {e}", e, {"ticker": ticker})
        company_info = {"이름": ticker}
        name = ticker

    # ── Step 2: 기술적 분석 ──
    logger.info("[3/7] 기술적 지표 계산 중...")
    try:
        df = run_full_analysis(df)
        signals = generate_signals(df)
        logger.info(f"  기술적 종합: {signals.get('종합판단', 'N/A')}")
    except Exception as e:
        logger.error(f"기술적 분석 실패: {e}", exc_info=True)
        _track_error(ErrorCategory.INDICATOR, "stock_analyzer", f"기술적 분석 실패: {e}", e, {"ticker": ticker})
        signals = {"종합판단": "분석 실패"}

    # ── Step 3: 애널리스트/뉴스/매크로 병렬 수집 (전문가 전에 수행) ──
    logger.info("[4/7] 애널리스트 등급 & 뉴스 & 매크로 병렬 수집 중...")
    analyst_ratings = []
    analyst_summary = {}
    articles = []
    macro_data = None

    def _fetch_ratings():
        return cached_call(f"analyst_ratings_{ticker}", fetch_analyst_ratings, ticker, top_n=8,
                           ttl_minutes=get_market_aware_ttl(60, _mkt))

    def _fetch_summary():
        return cached_call(f"analyst_summary_{ticker}", fetch_analyst_summary, ticker,
                           ttl_minutes=get_market_aware_ttl(60, _mkt))

    def _fetch_articles():
        return cached_call(f"news_{ticker}", fetch_news, ticker, max_articles=10,
                           ttl_minutes=get_market_aware_ttl(15, _mkt))

    def _fetch_macro():
        return cached_call("macro_indicators", fetch_macro_indicators,
                           ttl_minutes=get_market_aware_ttl(120, _mkt))

    task_map = {
        "ratings": _fetch_ratings,
        "summary": _fetch_summary,
        "news": _fetch_articles,
        "macro": _fetch_macro,
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fn): name for name, fn in task_map.items()}
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                result = future.result()
                if task_name == "ratings":
                    analyst_ratings = result
                elif task_name == "summary":
                    analyst_summary = result
                elif task_name == "news":
                    articles = result
                elif task_name == "macro":
                    macro_data = result
            except Exception as e:
                logger.warning(f"{task_name} 수집 실패: {e}")
                cat = ErrorCategory.MACRO_SENTIMENT if task_name == "macro" else ErrorCategory.DATA_FETCH
                _track_error(cat, "stock_analyzer", f"{task_name} 수집 실패: {e}", e, {"ticker": ticker, "task": task_name})

    news_sentiment = compute_news_sentiment_summary(articles)
    logger.info(f"  애널리스트 {len(analyst_ratings)}건 | 뉴스 {len(articles)}건 ({news_sentiment.get('종합감성', '')})")

    macro_count = macro_data.get("_available_count", 0) if macro_data else 0
    logger.info(f"  매크로 지표: {macro_count}/6개 수집")

    # 캐시 상태 로깅
    stats = cache_stats()
    if stats["files"] > 0:
        logger.info(f"  캐시 상태: {stats['files']}개 파일, {stats['total_size_mb']:.2f}MB")

    # ── Step 3-2: company_info enrichment (전문가 호출 전) ──
    logger.info("  company_info enrichment: 매크로/감성 주입...")
    enrich_company_info_with_macro(company_info, macro_data)
    enrich_company_info_with_sentiment(company_info, news_sentiment, articles)
    if company_info.get("_macro"):
        env = company_info["_macro"].get("시장_환경", "N/A")
        logger.info(f"  매크로 환경: {env}")
    if company_info.get("_sentiment"):
        sent = company_info["_sentiment"]
        logger.info(f"  감성 점수: {sent.get('score', 0):+.3f} ({sent.get('label', 'N/A')})")

    # ── Step 4: 4전문가 전략 (매크로/감성 반영) ──
    logger.info("[5/7] 5명 전문가 전략 적용 중 (매크로/감성/일목균형표 반영)...")
    expert_opinions = []
    for ExpertClass in ALL_EXPERTS:
        try:
            opinion = ExpertClass.analyze(df, company_info)
            expert_opinions.append(opinion)
            emoji = {"매수": "🟢", "매도": "🔴", "홀드": "🟡"}.get(opinion.position, "⚪")
            logger.info(f"  {emoji} {opinion.expert_name}: {opinion.position} (확신도 {opinion.confidence:.0f}%)")
        except Exception as e:
            logger.error(f"  [{ExpertClass.NAME}] 분석 실패: {e}", exc_info=True)
            _track_error(ErrorCategory.EXPERT_STRATEGY, "stock_analyzer",
                         f"[{ExpertClass.NAME}] 분석 실패: {e}", e,
                         {"ticker": ticker, "expert": ExpertClass.NAME})

    # ── Step 4-2: 의견 후처리 필터 (P1-3) ──
    try:
        from opinion_filter import apply_opinion_filters
        _of_cfg = get_config().get("opinion_filters", {})
        if _of_cfg.get("enabled", True) and expert_opinions:
            pre_buy = sum(1 for o in expert_opinions if o.position == "매수")
            expert_opinions = apply_opinion_filters(expert_opinions, df, company_info)
            post_buy = sum(1 for o in expert_opinions if o.position == "매수")
            if pre_buy != post_buy:
                logger.info(f"  📋 의견 필터: 매수 {pre_buy}→{post_buy} (다운그레이드 {pre_buy - post_buy}건)")
    except Exception as e:
        logger.debug(f"  의견 필터 실패 (무시): {e}")

    # ── Step 5: 차트 생성 ──
    logger.info("[6/7] 차트 생성 중...")
    chart_paths = []
    chart_funcs = [
        ("캔들스틱 차트", plot_candlestick_with_indicators),
        ("기술적 분석 대시보드", plot_technical_dashboard),
        ("수익률/변동성 차트", plot_performance_summary),
    ]
    for chart_name, chart_func in chart_funcs:
        try:
            path = chart_func(df, ticker, name)
            chart_paths.append(path)
            logger.info(f"  {chart_name}: {os.path.basename(path)}")
        except Exception as e:
            logger.warning(f"  [{chart_name}] 생성 실패: {e}")
            _track_error(ErrorCategory.REPORT, "stock_analyzer",
                         f"[{chart_name}] 차트 생성 실패: {e}", e,
                         {"ticker": ticker, "chart": chart_name})

    # ── Step 6: 리포트 생성 & 저장 ──
    try:
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
            chart_paths=chart_paths,
            macro_data=macro_data,
        )

        report_path = os.path.join(OUTPUT_DIR, f"{ticker}_full_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # 콘솔 출력
        print(report)

        logger.info(f"{'═'*60}")
        logger.info(f"  분석 완료! 결과: {OUTPUT_DIR}")
        logger.info(f"{'═'*60}")

        return report

    except Exception as e:
        logger.error(f"리포트 생성 실패: {e}", exc_info=True)
        _track_error(ErrorCategory.REPORT, "stock_analyzer",
                     f"리포트 생성 실패: {e}", e, {"ticker": ticker})
        return None


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "PLUG"
    main(ticker)
