"""
웹 스크래핑 어댑터 - yfinance 뉴스 + 애널리스트 데이터 수집
- 감성 키워드 및 수집 한도는 config.yaml에서 로드
- 한국 종목(.KS/.KQ)은 네이버 금융 API 폴백
"""
import logging

import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import List

from common.models import Article, AnalystRating
from common.config import get_config

logger = logging.getLogger(__name__)

# config.yaml에서 설정 로드
_cfg = get_config()
_data_cfg = _cfg.get("data", {})
_sent_cfg = _cfg.get("sentiment", {})
_POS_KEYWORDS = _sent_cfg.get("positive_keywords",
    ["surge", "rally", "gain", "rise", "bullish", "upgrade", "beat", "record", "growth", "strong", "buy"])
_NEG_KEYWORDS = _sent_cfg.get("negative_keywords",
    ["drop", "fall", "decline", "bearish", "downgrade", "miss", "loss", "weak", "sell", "cut", "concern"])
_POS_KR_KEYWORDS = _sent_cfg.get("positive_keywords_kr",
    ["상승", "급등", "호실적", "수주", "매수", "목표가 상향", "사상 최고", "영업이익 증가", "성장", "흑자", "수혜"])
_NEG_KR_KEYWORDS = _sent_cfg.get("negative_keywords_kr",
    ["하락", "급락", "적자", "실적 부진", "매도", "목표가 하향", "손실", "감소", "하향", "리스크", "우려"])
_MAX_NEWS = _data_cfg.get("max_news_articles", 10)
_MAX_RATINGS = _data_cfg.get("max_analyst_ratings", 8)

_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}
_NAVER_TIMEOUT = 10


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def _is_korean_ticker(ticker: str) -> bool:
    """한국 종목 여부 (KOSPI .KS / KOSDAQ .KQ)"""
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _extract_stock_code(ticker: str) -> str:
    """'065450.KQ' → '065450'"""
    return ticker.split(".")[0]


def _analyze_sentiment_kr(title: str, body: str) -> str:
    """한국어 텍스트 감성 분석"""
    text = title + " " + body
    pos = sum(1 for w in _POS_KR_KEYWORDS if w in text)
    neg = sum(1 for w in _NEG_KR_KEYWORDS if w in text)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


# ──────────────────────────────────────────────
# 뉴스 수집
# ──────────────────────────────────────────────
def _fetch_news_yfinance(ticker: str, max_articles: int) -> List[Article]:
    """yfinance에서 종목 관련 뉴스 수집"""
    stock = yf.Ticker(ticker)
    articles = []

    try:
        news_list = stock.news or []
    except Exception:
        news_list = []

    for item in news_list[:max_articles]:
        content = item.get("content", {})
        title = content.get("title", item.get("title", ""))
        provider = content.get("provider", {})
        source = provider.get("displayName", item.get("publisher", "Unknown"))
        url = content.get("canonicalUrl", {}).get("url", "")
        if not url:
            url = item.get("link", "")

        pub_date = content.get("pubDate", "")
        if not pub_date:
            pub_ts = item.get("providerPublishTime", 0)
            if pub_ts:
                pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M")

        summary = content.get("summary", item.get("summary", ""))

        # 간단한 감성 분석 (키워드 기반 - config.yaml에서 로드)
        text = (title + " " + summary).lower()
        pos_count = sum(1 for w in _POS_KEYWORDS if w in text)
        neg_count = sum(1 for w in _NEG_KEYWORDS if w in text)

        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        articles.append(Article(
            title=title,
            source=source,
            url=url,
            published=pub_date,
            summary=summary[:200] if summary else "",
            sentiment=sentiment,
            relevance=0.8,
        ))

    return articles


def _fetch_news_naver(ticker: str, max_articles: int) -> List[Article]:
    """네이버 금융 API에서 한국 종목 뉴스 수집"""
    code = _extract_stock_code(ticker)
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize={max_articles}&page=1"

    try:
        resp = requests.get(url, headers=_NAVER_HEADERS, timeout=_NAVER_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[Naver 뉴스] {ticker} 수집 실패: {e}")
        return []

    articles = []
    for group in data:
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []):
            title = item.get("title", item.get("titleFull", ""))
            body = item.get("body", "")
            source = item.get("officeName", "네이버뉴스")

            # datetime 파싱: "202602101433" → "2026-02-10 14:33"
            dt_str = item.get("datetime", "")
            pub_date = ""
            if dt_str and len(dt_str) >= 8:
                try:
                    pub_date = datetime.strptime(dt_str[:12], "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    pub_date = dt_str[:8]

            office_id = item.get("officeId", "")
            article_id = item.get("articleId", "")
            article_url = f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}" if office_id and article_id else ""

            sentiment = _analyze_sentiment_kr(title, body)

            articles.append(Article(
                title=title,
                source=source,
                url=article_url,
                published=pub_date,
                summary=body[:200] if body else "",
                sentiment=sentiment,
                relevance=0.8,
            ))

    logger.info(f"[Naver 뉴스] {ticker}: {len(articles)}건 수집")
    return articles


def fetch_news(ticker: str, max_articles: int = None) -> List[Article]:
    max_articles = max_articles or _MAX_NEWS
    """yfinance → (한국 종목 0건이면) Naver 폴백"""
    articles = _fetch_news_yfinance(ticker, max_articles)

    if not articles and _is_korean_ticker(ticker):
        articles = _fetch_news_naver(ticker, max_articles)

    return articles


# ──────────────────────────────────────────────
# 애널리스트 등급
# ──────────────────────────────────────────────
def _fetch_ratings_yfinance(ticker: str, top_n: int) -> List[AnalystRating]:
    """yfinance에서 애널리스트 등급/목표가 수집"""
    stock = yf.Ticker(ticker)
    ratings = []

    try:
        ud = stock.upgrades_downgrades
        if ud is None or ud.empty:
            return ratings

        recent = ud.head(top_n)

        for idx, row in recent.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            ratings.append(AnalystRating(
                firm=row.get("Firm", "Unknown"),
                date=date_str,
                grade=row.get("ToGrade", "N/A"),
                from_grade=row.get("FromGrade", ""),
                action=row.get("Action", ""),
                target_price=float(row.get("currentPriceTarget", 0) or 0),
                prior_target=float(row.get("priorPriceTarget", 0) or 0),
            ))
    except Exception as e:
        logger.warning(f"[yfinance] 애널리스트 등급 수집 실패: {e}")

    return ratings


def _fetch_ratings_naver(ticker: str, top_n: int) -> List[AnalystRating]:
    """네이버 금융 리서치 API에서 증권사 리포트 수집"""
    code = _extract_stock_code(ticker)
    url = f"https://m.stock.naver.com/api/research/stock/{code}?pageSize={top_n}&page=1"

    try:
        resp = requests.get(url, headers=_NAVER_HEADERS, timeout=_NAVER_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[Naver 리서치] {ticker} 수집 실패: {e}")
        return []

    ratings = []
    items = data if isinstance(data, list) else []

    for item in items[:top_n]:
        broker = item.get("brokerName", "Unknown")
        title = item.get("title", "")
        write_date = item.get("writeDate", "")

        # writeDate: "2026-02-11" → 그대로 사용
        date_str = write_date if write_date else ""

        ratings.append(AnalystRating(
            firm=broker,
            date=date_str,
            grade=title[:30] if title else "N/A",
            from_grade="",
            action="리서치",
            target_price=0,
            prior_target=0,
        ))

    logger.info(f"[Naver 리서치] {ticker}: {len(ratings)}건 수집")
    return ratings


def fetch_analyst_ratings(ticker: str, top_n: int = None) -> List[AnalystRating]:
    top_n = top_n or _MAX_RATINGS
    """yfinance → (한국 종목 0건이면) Naver 리서치 폴백"""
    ratings = _fetch_ratings_yfinance(ticker, top_n)

    if not ratings and _is_korean_ticker(ticker):
        ratings = _fetch_ratings_naver(ticker, top_n)

    return ratings


# ──────────────────────────────────────────────
# 애널리스트 컨센서스 요약
# ──────────────────────────────────────────────
def _fetch_summary_yfinance(ticker: str) -> dict:
    """yfinance에서 애널리스트 컨센서스 요약"""
    result = {
        "추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A",
    }

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        result["추천수"] = info.get("numberOfAnalystOpinions", 0)
        result["추천평균"] = info.get("recommendationMean", 0)
        result["추천키"] = info.get("recommendationKey", "N/A")
        result["등급표시"] = info.get("averageAnalystRating", "N/A")
    except Exception:
        pass

    try:
        apt = stock.analyst_price_targets
        if apt:
            result["목표가_현재"] = apt.get("current", 0)
            result["목표가_최고"] = apt.get("high", 0)
            result["목표가_최저"] = apt.get("low", 0)
            result["목표가_평균"] = apt.get("mean", 0)
            result["목표가_중간"] = apt.get("median", 0)
    except Exception:
        pass

    try:
        recs = stock.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[0]
            result["강력매수"] = int(latest.get("strongBuy", 0))
            result["매수"] = int(latest.get("buy", 0))
            result["보유"] = int(latest.get("hold", 0))
            result["매도"] = int(latest.get("sell", 0))
            result["강력매도"] = int(latest.get("strongSell", 0))
    except Exception:
        pass

    return result


def _fetch_summary_naver(ticker: str, base_result: dict) -> dict:
    """네이버 금융 통합 API에서 컨센서스 정보 수집"""
    code = _extract_stock_code(ticker)
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    result = dict(base_result)

    try:
        resp = requests.get(url, headers=_NAVER_HEADERS, timeout=_NAVER_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[Naver 컨센서스] {ticker} 수집 실패: {e}")
        return result

    # consensusInfo: {"recommMean": "4.00", "priceTargetMean": "1,541,944"}
    consensus = data.get("consensusInfo")
    if consensus:
        try:
            recomm_mean = float(consensus.get("recommMean", 0))
            result["추천평균"] = recomm_mean

            # recommMean → 등급 변환 (5=강력매수, 4=매수, 3=보유, 2=매도, 1=강력매도)
            if recomm_mean >= 4.5:
                result["등급표시"] = "강력매수"
                result["추천키"] = "strongBuy"
            elif recomm_mean >= 3.5:
                result["등급표시"] = "매수"
                result["추천키"] = "buy"
            elif recomm_mean >= 2.5:
                result["등급표시"] = "보유"
                result["추천키"] = "hold"
            elif recomm_mean >= 1.5:
                result["등급표시"] = "매도"
                result["추천키"] = "sell"
            else:
                result["등급표시"] = "강력매도"
                result["추천키"] = "strongSell"

            # 목표가 (콤마 제거 후 숫자 변환)
            target_str = consensus.get("priceTargetMean", "0")
            target_val = float(str(target_str).replace(",", ""))
            result["목표가_평균"] = target_val
            result["목표가_현재"] = target_val
            result["추천수"] = 1  # 컨센서스 데이터 존재 표시
        except (ValueError, TypeError) as e:
            logger.warning(f"[Naver 컨센서스] 파싱 실패: {e}")

    # researches 카운트로 추천수 보강
    researches = data.get("researches", [])
    if researches:
        result["추천수"] = max(result.get("추천수", 0), len(researches))

    logger.info(f"[Naver 컨센서스] {ticker}: 등급={result.get('등급표시')}, 목표가={result.get('목표가_평균', 0)}")
    return result


def fetch_analyst_summary(ticker: str) -> dict:
    """yfinance → (한국 종목이고 빈 결과면) Naver 폴백"""
    result = _fetch_summary_yfinance(ticker)

    if _is_korean_ticker(ticker) and result.get("추천수", 0) == 0:
        result = _fetch_summary_naver(ticker, result)

    return result


# ──────────────────────────────────────────────
# 감성 분석
# ──────────────────────────────────────────────
def _compute_sentiment_score(news_sentiment: dict, articles: List[Article]) -> dict:
    """
    뉴스 감성 점수 계산 (전문가 통합용)

    Returns:
        {
            "score": float (-1.0 ~ +1.0, 신뢰도 가중),
            "raw_score": float (-1.0 ~ +1.0),
            "label": "긍정적" / "부정적" / "중립적",
            "positive_count": int,
            "negative_count": int,
            "neutral_count": int,
            "total_count": int,
            "confidence": float (0.0 ~ 1.0),
        }
    """
    total = news_sentiment.get("총건수", 0)
    pos = news_sentiment.get("긍정", 0)
    neg = news_sentiment.get("부정", 0)
    neu = news_sentiment.get("중립", 0)

    if total == 0:
        return {
            "score": 0.0, "raw_score": 0.0, "label": "중립적",
            "positive_count": 0, "negative_count": 0, "neutral_count": 0,
            "total_count": 0, "confidence": 0.0,
        }

    raw_score = (pos - neg) / total

    min_articles = _sent_cfg.get("min_articles_for_full_confidence", 5)
    confidence = min(1.0, total / min_articles)
    weighted_score = raw_score * confidence

    bullish_thresh = _sent_cfg.get("bullish_threshold", 0.3)
    bearish_thresh = _sent_cfg.get("bearish_threshold", -0.3)

    if weighted_score > bullish_thresh:
        label = "긍정적"
    elif weighted_score < bearish_thresh:
        label = "부정적"
    else:
        label = "중립적"

    return {
        "score": round(weighted_score, 4),
        "raw_score": round(raw_score, 4),
        "label": label,
        "positive_count": pos,
        "negative_count": neg,
        "neutral_count": neu,
        "total_count": total,
        "confidence": round(confidence, 2),
    }


def enrich_company_info_with_sentiment(
    company_info: dict, news_sentiment: dict, articles: List[Article]
) -> dict:
    """
    company_info에 _sentiment 키 주입

    전문가 전략이 company_info.get("_sentiment")로 접근
    """
    if not news_sentiment or news_sentiment.get("총건수", 0) == 0:
        return company_info

    sentiment_data = _compute_sentiment_score(news_sentiment, articles)
    company_info["_sentiment"] = sentiment_data
    return company_info


def compute_news_sentiment_summary(articles: List[Article]) -> dict:
    """뉴스 감성 분석 요약"""
    if not articles:
        return {"긍정": 0, "부정": 0, "중립": 0, "총건수": 0, "종합감성": "N/A"}

    pos = sum(1 for a in articles if a.sentiment == "positive")
    neg = sum(1 for a in articles if a.sentiment == "negative")
    neu = sum(1 for a in articles if a.sentiment == "neutral")
    total = len(articles)

    if pos > neg + 1:
        overall = "긍정적 📈"
    elif neg > pos + 1:
        overall = "부정적 📉"
    else:
        overall = "중립적 ➡️"

    return {
        "긍정": pos,
        "부정": neg,
        "중립": neu,
        "총건수": total,
        "종합감성": overall,
    }
