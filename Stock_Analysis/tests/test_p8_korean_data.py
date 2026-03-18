"""
Phase 8: 한국 종목 데이터 수집 테스트
- 네이버 금융 API 폴백 (뉴스, 리서치, 컨센서스)
- 한국어 감성 분석
- 기존 US 종목 로직 불변 (regression)
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from scraper_adapter import (
    _is_korean_ticker,
    _extract_stock_code,
    _analyze_sentiment_kr,
    _fetch_news_naver,
    _fetch_ratings_naver,
    _fetch_summary_naver,
    fetch_news,
    fetch_analyst_ratings,
    fetch_analyst_summary,
)
from common.models import Article, AnalystRating


# ════════════════════════════════════════════
# 헬퍼 함수 테스트
# ════════════════════════════════════════════
class TestHelpers:
    """_is_korean_ticker, _extract_stock_code 유닛 테스트"""

    def test_korean_kospi(self):
        assert _is_korean_ticker("005930.KS") is True

    def test_korean_kosdaq(self):
        assert _is_korean_ticker("065450.KQ") is True

    def test_us_ticker(self):
        assert _is_korean_ticker("AAPL") is False

    def test_us_nasdaq(self):
        assert _is_korean_ticker("TSLA") is False

    def test_empty_string(self):
        assert _is_korean_ticker("") is False

    def test_partial_suffix(self):
        assert _is_korean_ticker("ABC.K") is False

    def test_extract_kospi(self):
        assert _extract_stock_code("005930.KS") == "005930"

    def test_extract_kosdaq(self):
        assert _extract_stock_code("065450.KQ") == "065450"

    def test_extract_no_dot(self):
        assert _extract_stock_code("AAPL") == "AAPL"


# ════════════════════════════════════════════
# 한국어 감성 분석 테스트
# ════════════════════════════════════════════
class TestKoreanSentiment:
    """_analyze_sentiment_kr 테스트"""

    def test_positive(self):
        assert _analyze_sentiment_kr("삼성전자 급등", "실적 호실적 성장세") == "positive"

    def test_negative(self):
        assert _analyze_sentiment_kr("주가 급락", "적자 전환 리스크 우려") == "negative"

    def test_neutral(self):
        assert _analyze_sentiment_kr("공시 발표", "변동 없음") == "neutral"

    def test_mixed_positive_wins(self):
        result = _analyze_sentiment_kr("급등 상승 성장", "하락")
        assert result == "positive"

    def test_mixed_negative_wins(self):
        result = _analyze_sentiment_kr("상승", "하락 급락 적자 손실")
        assert result == "negative"

    def test_empty_strings(self):
        assert _analyze_sentiment_kr("", "") == "neutral"

    def test_compound_keyword(self):
        """복합 키워드 '목표가 상향'이 인식되는지 확인"""
        assert _analyze_sentiment_kr("목표가 상향 발표", "") == "positive"

    def test_compound_negative_keyword(self):
        """복합 키워드 '실적 부진'이 인식되는지 확인"""
        assert _analyze_sentiment_kr("실적 부진 우려", "") == "negative"


# ════════════════════════════════════════════
# 네이버 뉴스 API 테스트
# ════════════════════════════════════════════
def _mock_naver_news_response():
    """네이버 뉴스 API 응답 목 데이터"""
    return [
        {
            "total": 2,
            "items": [
                {
                    "title": "빅텍 주가 급등",
                    "body": "빅텍이 수주 소식에 힘입어 상승세를 보이고 있다",
                    "officeName": "한국경제",
                    "datetime": "202602101433",
                    "officeId": "015",
                    "articleId": "0001234567",
                },
                {
                    "title": "빅텍 실적 발표",
                    "body": "영업이익 감소 우려",
                    "officeName": "매일경제",
                    "datetime": "202602091200",
                    "officeId": "009",
                    "articleId": "0009876543",
                },
            ],
        }
    ]


class TestFetchNewsNaver:
    """_fetch_news_naver mock 테스트"""

    @patch("scraper_adapter.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_news_response()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        articles = _fetch_news_naver("065450.KQ", 10)

        assert len(articles) == 2
        assert isinstance(articles[0], Article)
        assert articles[0].title == "빅텍 주가 급등"
        assert articles[0].source == "한국경제"
        assert articles[0].published == "2026-02-10 14:33"
        assert articles[0].sentiment == "positive"
        assert "n.news.naver.com" in articles[0].url

    @patch("scraper_adapter.requests.get")
    def test_second_article_negative(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_news_response()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        articles = _fetch_news_naver("065450.KQ", 10)
        assert articles[1].sentiment == "negative"
        assert articles[1].source == "매일경제"

    @patch("scraper_adapter.requests.get")
    def test_api_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        articles = _fetch_news_naver("065450.KQ", 10)
        assert articles == []

    @patch("scraper_adapter.requests.get")
    def test_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        articles = _fetch_news_naver("065450.KQ", 10)
        assert articles == []

    @patch("scraper_adapter.requests.get")
    def test_correct_url_called(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        _fetch_news_naver("005930.KS", 5)

        call_url = mock_get.call_args[0][0]
        assert "005930" in call_url
        assert "pageSize=5" in call_url

    @patch("scraper_adapter.requests.get")
    def test_datetime_short_format(self, mock_get):
        """날짜 8자리만 있는 경우"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"total": 1, "items": [
                {"title": "테스트", "body": "", "officeName": "뉴스",
                 "datetime": "20260210", "officeId": "", "articleId": ""}
            ]}
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        articles = _fetch_news_naver("065450.KQ", 10)
        assert len(articles) == 1
        # 8자리 → strptime 실패 시 dt_str[:8] 반환
        assert articles[0].published in ("20260210", "2026-02-10 00:00")


# ════════════════════════════════════════════
# 네이버 리서치 API 테스트
# ════════════════════════════════════════════
def _mock_naver_research_response():
    return [
        {
            "brokerName": "미래에셋증권",
            "title": "빅텍 - 수주 모멘텀 지속",
            "writeDate": "2026-02-11",
        },
        {
            "brokerName": "삼성증권",
            "title": "빅텍 - 실적 개선 기대",
            "writeDate": "2026-02-10",
        },
    ]


class TestFetchRatingsNaver:
    """_fetch_ratings_naver mock 테스트"""

    @patch("scraper_adapter.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_research_response()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        ratings = _fetch_ratings_naver("065450.KQ", 5)

        assert len(ratings) == 2
        assert isinstance(ratings[0], AnalystRating)
        assert ratings[0].firm == "미래에셋증권"
        assert ratings[0].date == "2026-02-11"
        assert ratings[0].action == "리서치"

    @patch("scraper_adapter.requests.get")
    def test_api_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        ratings = _fetch_ratings_naver("065450.KQ", 5)
        assert ratings == []

    @patch("scraper_adapter.requests.get")
    def test_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        ratings = _fetch_ratings_naver("065450.KQ", 5)
        assert ratings == []

    @patch("scraper_adapter.requests.get")
    def test_respects_top_n(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_research_response()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        ratings = _fetch_ratings_naver("065450.KQ", 1)
        assert len(ratings) == 1

    @patch("scraper_adapter.requests.get")
    def test_grade_truncated(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"brokerName": "증권사", "title": "A" * 50, "writeDate": "2026-01-01"}
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        ratings = _fetch_ratings_naver("065450.KQ", 5)
        assert len(ratings[0].grade) == 30


# ════════════════════════════════════════════
# 네이버 컨센서스 API 테스트
# ════════════════════════════════════════════
def _mock_naver_integration_with_consensus():
    return {
        "consensusInfo": {
            "recommMean": "4.00",
            "priceTargetMean": "15,000",
        },
        "researches": [{"id": 1}, {"id": 2}, {"id": 3}],
    }


def _mock_naver_integration_no_consensus():
    return {
        "consensusInfo": None,
        "researches": [{"id": 1}],
    }


class TestFetchSummaryNaver:
    """_fetch_summary_naver mock 테스트"""

    @patch("scraper_adapter.requests.get")
    def test_with_consensus(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_integration_with_consensus()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)

        assert result["추천평균"] == 4.0
        assert result["등급표시"] == "매수"
        assert result["추천키"] == "buy"
        assert result["목표가_평균"] == 15000.0
        assert result["추천수"] >= 1

    @patch("scraper_adapter.requests.get")
    def test_grade_mapping_strong_buy(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "consensusInfo": {"recommMean": "4.80", "priceTargetMean": "10,000"},
            "researches": [],
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("005930.KS", base)
        assert result["등급표시"] == "강력매수"
        assert result["추천키"] == "strongBuy"

    @patch("scraper_adapter.requests.get")
    def test_grade_mapping_hold(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "consensusInfo": {"recommMean": "3.00", "priceTargetMean": "5,000"},
            "researches": [],
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)
        assert result["등급표시"] == "보유"
        assert result["추천키"] == "hold"

    @patch("scraper_adapter.requests.get")
    def test_grade_mapping_sell(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "consensusInfo": {"recommMean": "2.00", "priceTargetMean": "3,000"},
            "researches": [],
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)
        assert result["등급표시"] == "매도"

    @patch("scraper_adapter.requests.get")
    def test_grade_mapping_strong_sell(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "consensusInfo": {"recommMean": "1.20", "priceTargetMean": "1,000"},
            "researches": [],
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)
        assert result["등급표시"] == "강력매도"

    @patch("scraper_adapter.requests.get")
    def test_no_consensus_preserves_base(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_naver_integration_no_consensus()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)

        assert result["등급표시"] == "N/A"
        assert result["추천수"] >= 1  # researches 카운트로 보강

    @patch("scraper_adapter.requests.get")
    def test_api_failure_returns_base(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("065450.KQ", base)

        assert result["등급표시"] == "N/A"
        assert result["추천수"] == 0

    @patch("scraper_adapter.requests.get")
    def test_comma_in_target_price(self, mock_get):
        """목표가에 콤마가 있는 경우"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "consensusInfo": {"recommMean": "4.00", "priceTargetMean": "1,541,944"},
            "researches": [],
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        base = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        result = _fetch_summary_naver("012450.KS", base)
        assert result["목표가_평균"] == 1541944.0


# ════════════════════════════════════════════
# 통합 디스패처 테스트 (폴백 로직)
# ════════════════════════════════════════════
class TestFetchNewsDispatcher:
    """fetch_news() 디스패처: yfinance → Naver 폴백"""

    @patch("scraper_adapter._fetch_news_naver")
    @patch("scraper_adapter._fetch_news_yfinance")
    def test_yfinance_success_no_fallback(self, mock_yf, mock_naver):
        mock_yf.return_value = [Article("Test", "Source", "", "", "")]
        fetch_news("AAPL", 10)
        mock_naver.assert_not_called()

    @patch("scraper_adapter._fetch_news_naver")
    @patch("scraper_adapter._fetch_news_yfinance")
    def test_korean_ticker_fallback_when_empty(self, mock_yf, mock_naver):
        mock_yf.return_value = []
        mock_naver.return_value = [Article("뉴스", "네이버", "", "", "")]

        articles = fetch_news("065450.KQ", 10)

        mock_naver.assert_called_once_with("065450.KQ", 10)
        assert len(articles) == 1
        assert articles[0].title == "뉴스"

    @patch("scraper_adapter._fetch_news_naver")
    @patch("scraper_adapter._fetch_news_yfinance")
    def test_us_ticker_no_fallback_even_when_empty(self, mock_yf, mock_naver):
        mock_yf.return_value = []
        articles = fetch_news("AAPL", 10)
        mock_naver.assert_not_called()
        assert articles == []

    @patch("scraper_adapter._fetch_news_naver")
    @patch("scraper_adapter._fetch_news_yfinance")
    def test_korean_yfinance_has_data_no_fallback(self, mock_yf, mock_naver):
        """한국 종목이라도 yfinance에 데이터가 있으면 폴백 안 함"""
        mock_yf.return_value = [Article("Yahoo뉴스", "Yahoo", "", "", "")]
        articles = fetch_news("005930.KS", 10)
        mock_naver.assert_not_called()
        assert articles[0].title == "Yahoo뉴스"


class TestFetchRatingsDispatcher:
    """fetch_analyst_ratings() 디스패처"""

    @patch("scraper_adapter._fetch_ratings_naver")
    @patch("scraper_adapter._fetch_ratings_yfinance")
    def test_korean_fallback(self, mock_yf, mock_naver):
        mock_yf.return_value = []
        mock_naver.return_value = [AnalystRating("증권사", "2026-01-01", "Buy")]

        ratings = fetch_analyst_ratings("065450.KQ", 5)
        mock_naver.assert_called_once()
        assert len(ratings) == 1

    @patch("scraper_adapter._fetch_ratings_naver")
    @patch("scraper_adapter._fetch_ratings_yfinance")
    def test_us_no_fallback(self, mock_yf, mock_naver):
        mock_yf.return_value = []
        ratings = fetch_analyst_ratings("AAPL", 5)
        mock_naver.assert_not_called()


class TestFetchSummaryDispatcher:
    """fetch_analyst_summary() 디스패처"""

    @patch("scraper_adapter._fetch_summary_naver")
    @patch("scraper_adapter._fetch_summary_yfinance")
    def test_korean_fallback_when_zero(self, mock_yf, mock_naver):
        mock_yf.return_value = {"추천수": 0, "추천평균": 0, "추천키": "N/A", "등급표시": "N/A"}
        mock_naver.return_value = {"추천수": 3, "추천평균": 4.0, "추천키": "buy", "등급표시": "매수"}

        result = fetch_analyst_summary("065450.KQ")
        mock_naver.assert_called_once()
        assert result["추천수"] == 3

    @patch("scraper_adapter._fetch_summary_naver")
    @patch("scraper_adapter._fetch_summary_yfinance")
    def test_us_no_fallback(self, mock_yf, mock_naver):
        mock_yf.return_value = {"추천수": 5, "추천평균": 3.5, "추천키": "buy", "등급표시": "Buy"}
        result = fetch_analyst_summary("AAPL")
        mock_naver.assert_not_called()
        assert result["추천수"] == 5

    @patch("scraper_adapter._fetch_summary_naver")
    @patch("scraper_adapter._fetch_summary_yfinance")
    def test_korean_yfinance_has_data_no_fallback(self, mock_yf, mock_naver):
        mock_yf.return_value = {"추천수": 2, "추천평균": 4.0, "추천키": "buy", "등급표시": "Buy"}
        result = fetch_analyst_summary("005930.KS")
        mock_naver.assert_not_called()
        assert result["추천수"] == 2


# ════════════════════════════════════════════
# 한국어 감성 키워드 config 테스트
# ════════════════════════════════════════════
class TestKoreanSentimentConfig:
    """config에서 한국어 키워드가 로드되는지 확인"""

    def test_config_has_kr_positive(self):
        from common.config import get_config
        cfg = get_config()
        kr_pos = cfg.get("sentiment", {}).get("positive_keywords_kr", [])
        assert len(kr_pos) > 0
        assert "상승" in kr_pos

    def test_config_has_kr_negative(self):
        from common.config import get_config
        cfg = get_config()
        kr_neg = cfg.get("sentiment", {}).get("negative_keywords_kr", [])
        assert len(kr_neg) > 0
        assert "하락" in kr_neg

    def test_scraper_loads_kr_keywords(self):
        from scraper_adapter import _POS_KR_KEYWORDS, _NEG_KR_KEYWORDS
        assert "급등" in _POS_KR_KEYWORDS
        assert "급락" in _NEG_KR_KEYWORDS
