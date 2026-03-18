"""
P3-2 테스트: 스크래퍼 어댑터 & 데이터 모델
- Article, AnalystRating, ExpertOpinion 모델 검증
- compute_news_sentiment_summary() 감성 분석 로직
- AnalystRating.position 정규화
- ExpertOpinion.to_dict() 변환
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.models import Article, AnalystRating, ExpertOpinion
from scraper_adapter import compute_news_sentiment_summary


# ─── Article 모델 테스트 ───

class TestArticleModel:
    """Article 데이터 모델"""

    def test_create_article(self):
        art = Article(
            title="PLUG surges 10%",
            source="Reuters",
            url="https://example.com",
            published="2024-06-01",
        )
        assert art.title == "PLUG surges 10%"
        assert art.sentiment == "neutral"  # 기본값

    def test_article_to_dict(self):
        art = Article(
            title="Test", source="Test", url="http://x",
            published="2024-01-01", sentiment="positive"
        )
        d = art.to_dict()
        assert d["제목"] == "Test"
        assert d["감성"] == "positive"
        assert "출처" in d
        assert "URL" in d

    def test_article_default_sentiment(self):
        art = Article(title="t", source="s", url="u", published="p")
        assert art.sentiment == "neutral"

    def test_article_default_relevance(self):
        art = Article(title="t", source="s", url="u", published="p")
        assert art.relevance == 0.0


# ─── AnalystRating 모델 테스트 ───

class TestAnalystRatingModel:
    """AnalystRating 데이터 모델"""

    def test_create_rating(self):
        r = AnalystRating(
            firm="Goldman Sachs", date="2024-06-01",
            grade="Buy", target_price=5.0
        )
        assert r.firm == "Goldman Sachs"
        assert r.grade == "Buy"

    def test_position_buy(self):
        """Buy 계열 등급 → 매수"""
        buy_grades = ["Buy", "Outperform", "Overweight", "Strong Buy"]
        for grade in buy_grades:
            r = AnalystRating(firm="F", date="D", grade=grade)
            assert r.position == "매수", f"'{grade}' → 매수 예상"

    def test_position_sell(self):
        """Sell 계열 등급 → 매도"""
        sell_grades = ["Sell", "Underperform", "Underweight", "Strong Sell"]
        for grade in sell_grades:
            r = AnalystRating(firm="F", date="D", grade=grade)
            assert r.position == "매도", f"'{grade}' → 매도 예상"

    def test_position_hold(self):
        """Hold/Neutral → 홀드"""
        hold_grades = ["Hold", "Neutral", "Equal-Weight", "Market Perform"]
        for grade in hold_grades:
            r = AnalystRating(firm="F", date="D", grade=grade)
            assert r.position == "홀드", f"'{grade}' → 홀드 예상"

    def test_action_kr(self):
        """action → 한국어 변환"""
        r = AnalystRating(firm="F", date="D", grade="Buy", action="up")
        assert "상향" in r.action_kr

        r2 = AnalystRating(firm="F", date="D", grade="Sell", action="down")
        assert "하향" in r2.action_kr

        r3 = AnalystRating(firm="F", date="D", grade="Buy", action="init")
        assert "신규" in r3.action_kr

    def test_to_dict(self):
        r = AnalystRating(
            firm="MS", date="2024-01-01", grade="Buy",
            target_price=10.0, prior_target=8.0
        )
        d = r.to_dict()
        assert d["증권사"] == "MS"
        assert d["포지션"] == "매수"
        assert "$10.00" in d["목표가"]
        assert "$8.00" in d["이전목표가"]

    def test_to_dict_no_target_price(self):
        r = AnalystRating(firm="F", date="D", grade="Hold")
        d = r.to_dict()
        assert d["목표가"] == "N/A"
        assert d["이전목표가"] == "N/A"


# ─── ExpertOpinion 모델 테스트 ───

class TestExpertOpinionModel:
    """ExpertOpinion 데이터 모델"""

    def test_create_opinion(self):
        op = ExpertOpinion(
            expert_name="추세추종 전문가",
            expert_style="이동평균 기반",
            position="매수",
            confidence=75.0,
            buy_price=8.5,
            sell_price=12.0,
            stop_loss=7.0,
        )
        assert op.position == "매수"
        assert op.confidence == 75.0

    def test_to_dict(self):
        op = ExpertOpinion(
            expert_name="테스트", expert_style="스타일",
            position="매수", confidence=80.0,
            buy_price=10.0, sell_price=15.0, stop_loss=8.0,
            rationale="근거", key_indicators=["RSI", "MACD"]
        )
        d = op.to_dict()
        assert d["전문가"] == "테스트"
        assert d["포지션"] == "매수"
        assert "$10.00" in d["매수가"]
        assert "$15.00" in d["매도가"]
        assert "$8.00" in d["손절가"]
        assert "RSI" in d["핵심지표"]

    def test_to_dict_no_prices(self):
        """가격 없을 때 '—' 표시"""
        op = ExpertOpinion(
            expert_name="t", expert_style="s",
            position="홀드", confidence=50.0
        )
        d = op.to_dict()
        assert d["매수가"] == "—"
        assert d["매도가"] == "—"
        assert d["손절가"] == "—"

    def test_key_indicators_default_empty(self):
        op = ExpertOpinion(
            expert_name="t", expert_style="s",
            position="홀드", confidence=50.0
        )
        assert op.key_indicators == []


# ─── compute_news_sentiment_summary() ───

class TestComputeNewsSentimentSummary:
    """감성 분석 요약 로직"""

    def test_empty_articles(self):
        result = compute_news_sentiment_summary([])
        assert result["총건수"] == 0
        assert result["종합감성"] == "N/A"

    def test_all_positive(self):
        articles = [
            Article(title="Good", source="s", url="u", published="p", sentiment="positive"),
            Article(title="Great", source="s", url="u", published="p", sentiment="positive"),
            Article(title="Nice", source="s", url="u", published="p", sentiment="positive"),
        ]
        result = compute_news_sentiment_summary(articles)
        assert result["긍정"] == 3
        assert result["부정"] == 0
        assert "긍정" in result["종합감성"]

    def test_all_negative(self):
        articles = [
            Article(title="Bad", source="s", url="u", published="p", sentiment="negative"),
            Article(title="Worse", source="s", url="u", published="p", sentiment="negative"),
            Article(title="Worst", source="s", url="u", published="p", sentiment="negative"),
        ]
        result = compute_news_sentiment_summary(articles)
        assert result["부정"] == 3
        assert "부정" in result["종합감성"]

    def test_neutral_when_balanced(self):
        """긍정과 부정 차이가 1 이하 → 중립"""
        articles = [
            Article(title="A", source="s", url="u", published="p", sentiment="positive"),
            Article(title="B", source="s", url="u", published="p", sentiment="negative"),
        ]
        result = compute_news_sentiment_summary(articles)
        assert "중립" in result["종합감성"]

    def test_positive_threshold(self):
        """긍정이 부정+1보다 많아야 긍정적"""
        articles = [
            Article(title="A", source="s", url="u", published="p", sentiment="positive"),
            Article(title="B", source="s", url="u", published="p", sentiment="positive"),
            Article(title="C", source="s", url="u", published="p", sentiment="negative"),
        ]
        # pos=2, neg=1, 차이=1 → 중립 (>1 필요)
        result = compute_news_sentiment_summary(articles)
        assert "중립" in result["종합감성"]

    def test_strong_positive(self):
        """긍정이 부정보다 2 이상 많으면 긍정적"""
        articles = [
            Article(title="A", source="s", url="u", published="p", sentiment="positive"),
            Article(title="B", source="s", url="u", published="p", sentiment="positive"),
            Article(title="C", source="s", url="u", published="p", sentiment="positive"),
            Article(title="D", source="s", url="u", published="p", sentiment="negative"),
        ]
        # pos=3, neg=1, 차이=2 > 1 → 긍정적
        result = compute_news_sentiment_summary(articles)
        assert "긍정" in result["종합감성"]

    def test_mixed_with_neutral(self):
        """중립 기사가 포함된 혼합"""
        articles = [
            Article(title="A", source="s", url="u", published="p", sentiment="positive"),
            Article(title="B", source="s", url="u", published="p", sentiment="neutral"),
            Article(title="C", source="s", url="u", published="p", sentiment="neutral"),
            Article(title="D", source="s", url="u", published="p", sentiment="negative"),
        ]
        result = compute_news_sentiment_summary(articles)
        assert result["중립"] == 2
        assert result["총건수"] == 4

    def test_total_count(self):
        articles = [
            Article(title=f"Art{i}", source="s", url="u", published="p")
            for i in range(5)
        ]
        result = compute_news_sentiment_summary(articles)
        assert result["총건수"] == 5

    def test_has_required_keys(self):
        articles = [Article(title="t", source="s", url="u", published="p")]
        result = compute_news_sentiment_summary(articles)
        assert "긍정" in result
        assert "부정" in result
        assert "중립" in result
        assert "총건수" in result
        assert "종합감성" in result


# ─── 스크래퍼 어댑터 소스 검증 ───

class TestScraperAdapterSource:
    """scraper_adapter.py 소스 레벨 검증"""

    def test_imports_config(self):
        import scraper_adapter
        source = open(scraper_adapter.__file__).read()
        assert "from common.config import get_config" in source

    def test_uses_positive_keywords(self):
        import scraper_adapter
        source = open(scraper_adapter.__file__).read()
        assert "_POS_KEYWORDS" in source

    def test_uses_negative_keywords(self):
        import scraper_adapter
        source = open(scraper_adapter.__file__).read()
        assert "_NEG_KEYWORDS" in source

    def test_sentiment_detection_logic(self):
        """감성 판단: 긍정 키워드 > 부정 키워드 → positive"""
        import scraper_adapter
        source = open(scraper_adapter.__file__).read()
        assert "pos_count > neg_count" in source
        assert "neg_count > pos_count" in source
