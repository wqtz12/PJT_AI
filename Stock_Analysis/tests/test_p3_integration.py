"""
P3-2 테스트: 통합 테스트 (build_report, bar_chart, 전문가 통합)
- build_report() 출력 검증
- bar_chart() 텍스트 그래프
- fmt_num() 추가 엣지 케이스
- 4전문가 통합 시나리오
- ExpertOpinion 일관성 검증
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_analyzer import build_report, fmt_num, bar_chart
from common.models import Article, AnalystRating, ExpertOpinion
from scraper_adapter import compute_news_sentiment_summary
from expert_strategies import ALL_EXPERTS
from technical_analysis import run_full_analysis, generate_signals


# ─── 테스트 데이터 생성 ───

def _make_df(rows=100, base_price=10.0):
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    np.random.seed(42)
    prices = base_price + np.cumsum(np.random.normal(0.02, 0.3, rows))
    prices = np.maximum(prices, 0.5)
    return pd.DataFrame({
        "Open": prices * 0.99,
        "High": prices * 1.02,
        "Low": prices * 0.97,
        "Close": prices,
        "Volume": np.random.randint(500_000, 5_000_000, rows).astype(float),
    }, index=dates)


def _make_expert_opinions():
    return [
        ExpertOpinion("추세추종", "이동평균 기반", "매수", 75.0,
                      buy_price=9.0, sell_price=13.0, stop_loss=7.5,
                      rationale="정배열 | RSI 중립", key_indicators=["SMA_20", "RSI"]),
        ExpertOpinion("가치분석", "PBR/PER 기반", "홀드", 60.0,
                      rationale="PBR 적정 | 부채비율 양호"),
        ExpertOpinion("모멘텀", "RSI/MACD 기반", "매수", 70.0,
                      buy_price=9.5, sell_price=12.5, stop_loss=8.0,
                      rationale="MACD 골든크로스"),
        ExpertOpinion("역발상", "볼린저/역추세", "홀드", 55.0,
                      rationale="BB 정상 범위"),
    ]


def _make_company_info():
    return {
        "이름": "Plug Power Inc",
        "섹터": "Technology",
        "산업": "Fuel Cell",
        "시가총액": 2_500_000_000,
        "직원수": 1500,
        "홈페이지": "https://plugpower.com",
        "PER": -15.5,
        "PBR": 2.3,
        "EPS": -0.85,
        "베타": 1.8,
        "총매출": 890_000_000,
        "영업이익": -350_000_000,
        "부채비율": 45.0,
        "현금": 1_200_000_000,
        "52주_최고": 15.0,
        "52주_최저": 2.0,
    }


def _make_analyst_ratings():
    return [
        AnalystRating("Goldman Sachs", "2024-05-20", "Buy", target_price=12.0, prior_target=10.0, action="up"),
        AnalystRating("Morgan Stanley", "2024-05-15", "Hold", target_price=8.0, action="main"),
        AnalystRating("JP Morgan", "2024-05-10", "Sell", target_price=5.0, prior_target=7.0, action="down"),
    ]


# ─── bar_chart() ───

class TestBarChart:
    """bar_chart() 텍스트 막대 그래프"""

    def test_zero_value(self):
        result = bar_chart(0, max_val=100, width=10)
        assert result == "░" * 10

    def test_full_value(self):
        result = bar_chart(100, max_val=100, width=10)
        assert result == "█" * 10

    def test_half_value(self):
        result = bar_chart(50, max_val=100, width=10)
        assert "█" in result
        assert "░" in result
        assert len(result) == 10

    def test_over_max(self):
        """최대값 초과 → 100%로 클램프"""
        result = bar_chart(150, max_val=100, width=10)
        assert result == "█" * 10

    def test_negative_value(self):
        """음수 → 0%로 클램프"""
        result = bar_chart(-10, max_val=100, width=10)
        assert result == "░" * 10

    def test_custom_width(self):
        result = bar_chart(50, max_val=100, width=20)
        assert len(result) == 20


# ─── fmt_num() 추가 케이스 ───

class TestFmtNumExtended:
    """fmt_num() 추가 엣지 케이스"""

    def test_trillion(self):
        assert "T" in fmt_num(1.5e12)

    def test_thousand(self):
        assert "K" in fmt_num(5000)

    def test_string_input(self):
        assert fmt_num("hello") == "hello"

    def test_empty_string(self):
        assert fmt_num("") == "N/A"

    def test_integer(self):
        result = fmt_num(42)
        assert result == "42"

    def test_negative_billion(self):
        result = fmt_num(-2_500_000_000)
        assert "B" in result
        assert "-" in result


# ─── build_report() ───

class TestBuildReport:
    """build_report() 통합 리포트 생성"""

    def _build_sample_report(self):
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        signals = generate_signals(df)
        opinions = _make_expert_opinions()
        ratings = _make_analyst_ratings()
        analyst_summary = {
            "등급표시": "Buy", "추천수": 15,
            "목표가_평균": 10.0, "목표가_최고": 15.0, "목표가_최저": 5.0,
            "강력매수": 5, "매수": 6, "보유": 3, "매도": 1, "강력매도": 0,
        }
        articles = [
            Article("PLUG surges", "Reuters", "http://x", "2024-06-01", sentiment="positive"),
            Article("Market falls", "Bloomberg", "http://y", "2024-06-01", sentiment="negative"),
        ]
        news_sentiment = compute_news_sentiment_summary(articles)
        chart_paths = ["/tmp/test_chart_1.png", "/tmp/test_chart_2.png"]

        return build_report(
            ticker="PLUG",
            company_info=_make_company_info(),
            df=df,
            signals=signals,
            expert_opinions=opinions,
            analyst_ratings=ratings,
            analyst_summary=analyst_summary,
            articles=articles,
            news_sentiment=news_sentiment,
            chart_paths=chart_paths,
        )

    def test_report_is_string(self):
        report = self._build_sample_report()
        assert isinstance(report, str)

    def test_report_has_company_section(self):
        report = self._build_sample_report()
        assert "기업 개요" in report
        assert "Plug Power" in report

    def test_report_has_price_section(self):
        report = self._build_sample_report()
        assert "현재 주가" in report

    def test_report_has_indicators_section(self):
        report = self._build_sample_report()
        assert "투자 지표" in report

    def test_report_has_technical_section(self):
        report = self._build_sample_report()
        assert "기술적 분석" in report
        assert "종합" in report

    def test_report_has_expert_section(self):
        report = self._build_sample_report()
        assert "전문가" in report
        assert "추세추종" in report
        assert "가치분석" in report

    def test_report_has_expert_summary(self):
        report = self._build_sample_report()
        assert "종합 요약" in report
        assert "매수" in report

    def test_report_has_analyst_section(self):
        report = self._build_sample_report()
        assert "애널리스트" in report
        assert "Goldman Sachs" in report

    def test_report_has_news_section(self):
        report = self._build_sample_report()
        assert "뉴스" in report
        assert "감성" in report

    def test_report_has_chart_section(self):
        report = self._build_sample_report()
        assert "차트 파일" in report

    def test_report_has_disclaimer(self):
        report = self._build_sample_report()
        assert "투자 판단" in report

    def test_report_no_analyst_data(self):
        """애널리스트 데이터 없어도 리포트 생성"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        report = build_report(
            ticker="TEST", company_info={"이름": "Test"},
            df=df, signals=generate_signals(df),
            expert_opinions=_make_expert_opinions(),
            analyst_ratings=[],
            analyst_summary={},
            articles=[], news_sentiment=compute_news_sentiment_summary([]),
            chart_paths=[],
        )
        assert "데이터 없음" in report

    def test_report_52w_range_display(self):
        """52주 범위 표시"""
        report = self._build_sample_report()
        assert "52주" in report


# ─── 4전문가 통합 테스트 ───

class TestAllExpertsIntegration:
    """5명 전문가 전체 통합 테스트"""

    def test_all_experts_registered(self):
        """ALL_EXPERTS에 5명 등록 (일목균형표 전문가 포함)"""
        assert len(ALL_EXPERTS) == 5

    def test_all_experts_have_analyze(self):
        """모든 전문가가 analyze() 메서드 보유"""
        for expert in ALL_EXPERTS:
            assert hasattr(expert, "analyze")

    def test_all_experts_have_name(self):
        """모든 전문가가 NAME 속성 보유"""
        for expert in ALL_EXPERTS:
            assert hasattr(expert, "NAME")
            assert isinstance(expert.NAME, str)

    def test_all_experts_return_opinion(self):
        """모든 전문가가 ExpertOpinion 반환"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            assert isinstance(result, ExpertOpinion), f"{expert.NAME} 반환 타입 오류"

    def test_opinions_have_valid_position(self):
        """모든 포지션이 매수/홀드/매도 중 하나"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            assert result.position in ("매수", "홀드", "매도"), \
                f"{expert.NAME}: 잘못된 포지션 '{result.position}'"

    def test_opinions_confidence_in_range(self):
        """확신도가 0~100% 범위"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            assert 0 <= result.confidence <= 100, \
                f"{expert.NAME}: 확신도 {result.confidence} 범위 초과"

    def test_buy_opinion_has_buy_price(self):
        """매수 포지션이면 매수가 존재"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            if result.position == "매수":
                assert result.buy_price is not None, \
                    f"{expert.NAME}: 매수인데 매수가 없음"
                assert result.buy_price > 0

    def test_sell_opinion_has_sell_price(self):
        """매도 포지션이면 매도가 존재"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            if result.position == "매도":
                assert result.sell_price is not None, \
                    f"{expert.NAME}: 매도인데 매도가 없음"

    def test_stop_loss_below_buy_price(self):
        """손절가 < 매수가 (매수 포지션)"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            if result.position == "매수" and result.stop_loss and result.buy_price:
                assert result.stop_loss < result.buy_price, \
                    f"{expert.NAME}: 손절가({result.stop_loss}) >= 매수가({result.buy_price})"

    def test_rationale_not_empty(self):
        """근거가 비어있지 않음"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        info = _make_company_info()

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            assert len(result.rationale) > 0, f"{expert.NAME}: 근거 없음"

    def test_with_minimal_data(self):
        """최소 데이터로 모든 전문가 동작"""
        df = _make_df(rows=20)
        df = run_full_analysis(df)
        info = {}

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, info)
            assert isinstance(result, ExpertOpinion)
            assert result.position in ("매수", "홀드", "매도")

    def test_with_empty_info(self):
        """기업 정보 없어도 동작"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)

        for expert in ALL_EXPERTS:
            result = expert.analyze(df, {})
            assert isinstance(result, ExpertOpinion)


# ─── 종단간 파이프라인 테스트 ───

class TestEndToEndPipeline:
    """데이터 → 분석 → 리포트 파이프라인"""

    def test_full_pipeline_no_crash(self):
        """전체 파이프라인이 크래시 없이 완료"""
        df = _make_df(rows=100)
        df = run_full_analysis(df)
        signals = generate_signals(df)
        info = _make_company_info()

        opinions = []
        for expert in ALL_EXPERTS:
            op = expert.analyze(df, info)
            opinions.append(op)

        articles = [
            Article("Test news", "Source", "url", "2024-01-01", sentiment="positive")
        ]
        news_sentiment = compute_news_sentiment_summary(articles)

        report = build_report(
            ticker="PLUG", company_info=info, df=df,
            signals=signals, expert_opinions=opinions,
            analyst_ratings=_make_analyst_ratings(),
            analyst_summary={"등급표시": "Buy", "추천수": 10,
                             "목표가_평균": 10.0, "목표가_최고": 15.0, "목표가_최저": 5.0,
                             "강력매수": 5, "매수": 3, "보유": 2, "매도": 0, "강력매도": 0},
            articles=articles,
            news_sentiment=news_sentiment,
            chart_paths=[],
        )

        assert len(report) > 500  # 의미 있는 길이의 리포트
        assert "PLUG" in report

    def test_pipeline_minimal_data(self):
        """최소 데이터로도 파이프라인 완료"""
        df = _make_df(rows=20)
        df = run_full_analysis(df)
        signals = generate_signals(df)

        opinions = [expert.analyze(df, {}) for expert in ALL_EXPERTS]

        report = build_report(
            ticker="TEST", company_info={"이름": "Test"},
            df=df, signals=signals, expert_opinions=opinions,
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=compute_news_sentiment_summary([]),
            chart_paths=[],
        )

        assert isinstance(report, str)
        assert len(report) > 100
