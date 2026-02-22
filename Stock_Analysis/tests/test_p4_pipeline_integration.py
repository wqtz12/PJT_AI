"""
P4 테스트: 파이프라인 통합 (build_report 매크로 섹션)
- build_report에 macro_data 전달 시 매크로 섹션 출력
- macro_data=None이면 "(매크로경제 데이터 수집 불가)" 표시
- 감성 점수가 enrichment 후 리포트에 표시
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_analyzer import build_report, bar_chart


def _make_df(n=100):
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    close = np.linspace(100, 110, n) + np.random.randn(n)
    df = pd.DataFrame({
        "Open": close * 0.99, "High": close * 1.02,
        "Low": close * 0.98, "Close": close,
        "Volume": np.random.randint(100000, 1000000, n),
    }, index=dates)
    df["SMA_5"] = df["Close"].rolling(5).mean()
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["RSI"] = 55.0
    df["ATR"] = 3.0
    return df


def _base_company_info():
    return {
        "이름": "TestCorp", "섹터": "Technology",
        "52주_최고": 130, "52주_최저": 80,
        "시가총액": 1e10, "PER": 25, "PBR": 5.0,
        "EPS": 3.5, "부채비율": 45.0, "베타": 1.2,
    }


def _mock_expert_opinion():
    from common.models import ExpertOpinion
    return ExpertOpinion(
        expert_name="테스트 전문가",
        expert_style="테스트 스타일",
        position="매수",
        confidence=70,
        buy_price=100.0,
        sell_price=120.0,
        stop_loss=90.0,
        rationale="테스트 근거",
        key_indicators=["RSI=55"],
    )


def _mock_macro_data():
    return {
        "vix": {"current": 18.5, "change_pct": -1.2, "avg_20d": 19.0, "trend": "하락", "level": "보통", "name": "VIX (변동성지수)"},
        "sp500": {"current": 5500, "change_pct": 0.3, "avg_20d": 5450, "trend": "상승", "name": "S&P 500"},
        "treasury_10y": {"current": 4.2, "change_pct": 0.05, "avg_20d": 4.15, "trend": "안정", "name": "10년 국채금리"},
        "oil": {"current": 75.0, "change_pct": -0.5, "avg_20d": 76.0, "trend": "하락", "name": "WTI 원유"},
        "gold": {"current": 2050, "change_pct": 0.2, "avg_20d": 2030, "trend": "안정", "name": "금"},
        "dollar": {"current": 103.5, "change_pct": -0.1, "avg_20d": 104.0, "trend": "하락", "name": "달러 인덱스"},
        "_available_count": 6,
        "_fetch_time": "2024-01-01 10:00:00",
    }


class TestBuildReportWithMacro:
    def test_macro_section_rendered(self):
        """매크로 데이터 있으면 매크로 섹션 렌더링"""
        df = _make_df()
        info = _base_company_info()
        macro = _mock_macro_data()

        # Enrich company_info
        from macro_fetcher import enrich_company_info_with_macro
        enrich_company_info_with_macro(info, macro)

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=[],
            macro_data=macro,
        )
        assert "매크로경제 환경 분석" in report
        assert "VIX" in report
        assert "S&P 500" in report
        assert "시장 환경:" in report

    def test_macro_section_no_data(self):
        """매크로 데이터 없으면 '수집 불가' 표시"""
        df = _make_df()
        info = _base_company_info()

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=[],
            macro_data=None,
        )
        assert "매크로경제 환경 분석" in report
        assert "수집 불가" in report

    def test_sentiment_in_report(self):
        """감성 점수 enriched이면 리포트에 표시"""
        df = _make_df()
        info = _base_company_info()
        info["_sentiment"] = {
            "score": 0.45, "raw_score": 0.5, "label": "긍정적",
            "positive_count": 4, "negative_count": 1, "neutral_count": 0,
            "total_count": 5, "confidence": 0.8,
        }

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 5, "긍정": 4, "부정": 1, "중립": 0, "종합감성": "긍정적"},
            chart_paths=[],
        )
        assert "뉴스 감성 점수" in report
        assert "긍정적" in report

    def test_report_section_numbers(self):
        """리포트 섹션 번호 순서 확인 (1~9)"""
        df = _make_df()
        info = _base_company_info()
        macro = _mock_macro_data()
        from macro_fetcher import enrich_company_info_with_macro
        enrich_company_info_with_macro(info, macro)

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=["/tmp/test.png"],
            macro_data=macro,
        )
        assert "1. 기업 개요" in report
        assert "2. 현재 주가 현황" in report
        assert "3. 투자 지표" in report
        assert "4. 기술적 분석" in report
        assert "5. 매크로경제 환경 분석" in report
        assert "6. 전문가 5인 분석" in report
        assert "7. 증권사 애널리스트 등급" in report
        assert "8. 뉴스 트렌드 & 감성 분석" in report
        assert "9. 생성된 차트 파일" in report

    def test_macro_backward_compatible(self):
        """macro_data 파라미터 없이도 build_report 동작 (하위 호환)"""
        df = _make_df()
        info = _base_company_info()

        # macro_data 파라미터 생략 (default=None)
        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=[],
        )
        assert "매크로경제 환경 분석" in report
        assert report  # 비어있지 않음

    def test_macro_risk_on_display(self):
        """위험선호 환경 표시"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 12, "level": "저변동"},
            "환경_점수": 4,
            "시장_환경": "위험선호",
        }
        macro = _mock_macro_data()

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=[],
            macro_data=macro,
        )
        assert "위험선호" in report

    def test_macro_risk_off_display(self):
        """위험회피 환경 표시"""
        df = _make_df()
        info = _base_company_info()
        info["_macro"] = {
            "vix": {"current": 35, "level": "고변동"},
            "환경_점수": -4,
            "시장_환경": "위험회피",
        }
        macro = _mock_macro_data()

        report = build_report(
            ticker="TEST", company_info=info, df=df,
            signals={"종합판단": "보통"},
            expert_opinions=[_mock_expert_opinion()],
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment={"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"},
            chart_paths=[],
            macro_data=macro,
        )
        assert "위험회피" in report
