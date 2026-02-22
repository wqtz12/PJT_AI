"""
P4 테스트: 뉴스 감성 통합
- _compute_sentiment_score() 감성 점수 계산
- enrich_company_info_with_sentiment() 주입
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper_adapter import (
    _compute_sentiment_score, enrich_company_info_with_sentiment,
    compute_news_sentiment_summary,
)
from common.models import Article


def _articles(sentiments):
    return [Article(f"Title {i}", "Src", "url", "2024-01-01", sentiment=s)
            for i, s in enumerate(sentiments)]


class TestComputeSentimentScore:
    def test_all_positive(self):
        articles = _articles(["positive"] * 5)
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        assert result["score"] > 0.5
        assert result["label"] == "긍정적"

    def test_all_negative(self):
        articles = _articles(["negative"] * 5)
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        assert result["score"] < -0.5
        assert result["label"] == "부정적"

    def test_mixed_neutral(self):
        articles = _articles(["positive", "negative", "neutral"])
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        assert -0.5 < result["score"] < 0.5

    def test_empty_returns_zero(self):
        result = _compute_sentiment_score({"총건수": 0, "긍정": 0, "부정": 0, "중립": 0}, [])
        assert result["score"] == 0.0
        assert result["confidence"] == 0.0
        assert result["label"] == "중립적"

    def test_score_range(self):
        for sentiments in [["positive"]*10, ["negative"]*10, ["neutral"]*10]:
            articles = _articles(sentiments)
            sentiment = compute_news_sentiment_summary(articles)
            result = _compute_sentiment_score(sentiment, articles)
            assert -1.0 <= result["score"] <= 1.0

    def test_confidence_scales_with_count(self):
        """기사 많을수록 신뢰도 증가"""
        for n in [1, 3, 5, 10]:
            articles = _articles(["positive"] * n)
            sentiment = compute_news_sentiment_summary(articles)
            result = _compute_sentiment_score(sentiment, articles)
            assert 0 < result["confidence"] <= 1.0

    def test_one_article_low_confidence(self):
        articles = _articles(["positive"])
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        assert result["confidence"] < 0.5

    def test_five_articles_full_confidence(self):
        articles = _articles(["positive"] * 5)
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        assert result["confidence"] == 1.0

    def test_has_all_keys(self):
        articles = _articles(["positive", "negative"])
        sentiment = compute_news_sentiment_summary(articles)
        result = _compute_sentiment_score(sentiment, articles)
        for key in ("score", "raw_score", "label", "positive_count",
                     "negative_count", "neutral_count", "total_count", "confidence"):
            assert key in result


class TestEnrichCompanyInfoWithSentiment:
    def test_adds_sentiment_key(self):
        info = {"이름": "Test"}
        articles = _articles(["positive", "negative", "neutral"])
        sentiment = compute_news_sentiment_summary(articles)
        enrich_company_info_with_sentiment(info, sentiment, articles)
        assert "_sentiment" in info

    def test_empty_no_change(self):
        info = {"이름": "Test"}
        enrich_company_info_with_sentiment(info, {"총건수": 0}, [])
        assert "_sentiment" not in info

    def test_none_no_change(self):
        info = {"이름": "Test"}
        enrich_company_info_with_sentiment(info, None, [])
        assert "_sentiment" not in info

    def test_preserves_existing(self):
        info = {"이름": "Test", "PBR": 2.5}
        articles = _articles(["positive"] * 3)
        sentiment = compute_news_sentiment_summary(articles)
        enrich_company_info_with_sentiment(info, sentiment, articles)
        assert info["이름"] == "Test"
        assert info["PBR"] == 2.5
        assert "_sentiment" in info
