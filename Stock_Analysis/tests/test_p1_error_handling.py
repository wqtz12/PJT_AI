"""
P1-1 테스트: 구조화된 에러 핸들링/로깅 시스템
- common/logger.py 모듈 검증
- stock_analyzer.py main()의 에러 복원력 검증
- 각 모듈의 에러 전파 방식 검증
"""
import sys
import os
import pytest
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logger import (
    setup_logging,
    get_logger,
    AnalysisError,
    DataFetchError,
    IndicatorError,
    ExpertAnalysisError,
    ReportGenerationError,
    LOG_DIR,
)
from data_fetcher import InsufficientDataError, DataQualityWarning


# ─── 로거 모듈 테스트 ───

class TestLoggerSetup:

    def test_setup_logging_returns_logger(self):
        """setup_logging이 루트 로거를 반환"""
        root = setup_logging(level="WARNING", log_to_file=False)
        assert isinstance(root, logging.Logger)

    def test_get_logger_returns_named_logger(self):
        """get_logger가 명명된 로거를 반환"""
        lg = get_logger("test_module")
        assert lg.name == "test_module"

    def test_log_level_set_correctly(self):
        """로그 레벨이 올바르게 설정됨"""
        setup_logging(level="DEBUG", log_to_file=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_console_handler_exists(self):
        """콘솔 핸들러가 존재"""
        setup_logging(level="INFO", log_to_file=False)
        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "StreamHandler" in handler_types

    def test_no_duplicate_handlers(self):
        """중복 핸들러 방지"""
        setup_logging(level="INFO", log_to_file=False)
        setup_logging(level="INFO", log_to_file=False)
        root = logging.getLogger()
        # 파일 로그 없이 콘솔만 → 핸들러 1개
        assert len(root.handlers) == 1


# ─── 커스텀 예외 클래스 테스트 ───

class TestCustomExceptions:

    def test_analysis_error_basic(self):
        """기본 AnalysisError"""
        err = AnalysisError("테스트 에러", module="data_fetcher")
        assert "data_fetcher" in str(err)
        assert err.module == "data_fetcher"

    def test_analysis_error_with_context(self):
        """컨텍스트 포함 AnalysisError"""
        err = AnalysisError("에러", module="test", context={"ticker": "PLUG"})
        assert err.context["ticker"] == "PLUG"

    def test_data_fetch_error_inherits(self):
        """DataFetchError는 AnalysisError 상속"""
        err = DataFetchError("데이터 없음")
        assert isinstance(err, AnalysisError)

    def test_indicator_error_inherits(self):
        """IndicatorError는 AnalysisError 상속"""
        assert issubclass(IndicatorError, AnalysisError)

    def test_expert_analysis_error_inherits(self):
        """ExpertAnalysisError는 AnalysisError 상속"""
        assert issubclass(ExpertAnalysisError, AnalysisError)

    def test_report_generation_error_inherits(self):
        """ReportGenerationError는 AnalysisError 상속"""
        assert issubclass(ReportGenerationError, AnalysisError)

    def test_insufficient_data_error(self):
        """InsufficientDataError는 ValueError 상속"""
        err = InsufficientDataError("데이터 부족")
        assert isinstance(err, ValueError)


# ─── fmt_num 유틸리티 테스트 (None 처리) ───

class TestFmtNum:

    def test_none_returns_na(self):
        """None → 'N/A'"""
        from stock_analyzer import fmt_num
        assert fmt_num(None) == "N/A"

    def test_na_string(self):
        """'N/A' 문자열 → 'N/A'"""
        from stock_analyzer import fmt_num
        assert fmt_num("N/A") == "N/A"

    def test_billion(self):
        """10억 → $X.XXB"""
        from stock_analyzer import fmt_num
        result = fmt_num(5_000_000_000)
        assert "B" in result

    def test_million(self):
        """100만 → $X.XXM"""
        from stock_analyzer import fmt_num
        result = fmt_num(2_500_000)
        assert "M" in result

    def test_zero(self):
        """0"""
        from stock_analyzer import fmt_num
        result = fmt_num(0)
        assert result == "0"

    def test_small_float(self):
        """소수"""
        from stock_analyzer import fmt_num
        result = fmt_num(3.14)
        assert "$3.14" in result


# ─── 에러 복원력 통합 테스트 ───

class TestErrorResilience:
    """각 모듈이 비정상 입력에서도 크래시 없이 동작하는지 검증"""

    def test_generate_signals_empty_df(self):
        """빈 DataFrame → 에러 없이 반환"""
        import pandas as pd
        from technical_analysis import generate_signals
        result = generate_signals(pd.DataFrame())
        assert "종합판단" in result

    def test_expert_with_minimal_df(self):
        """최소 데이터 DataFrame → 4전문가 모두 정상"""
        import pandas as pd
        import numpy as np
        from expert_strategies import ALL_EXPERTS

        dates = pd.bdate_range("2024-01-01", periods=5)
        df = pd.DataFrame({
            "Open": [10, 11, 12, 11, 10],
            "High": [12, 13, 14, 13, 12],
            "Low": [9, 10, 11, 10, 9],
            "Close": [11, 12, 13, 12, 11],
            "Volume": [1000, 2000, 3000, 2000, 1000],
        }, index=dates, dtype=float)

        info = {"이름": "Test"}

        for Expert in ALL_EXPERTS:
            opinion = Expert.analyze(df, info)
            assert opinion.position in ("매수", "매도", "홀드")

    def test_compute_sentiment_empty(self):
        """빈 기사 목록 → 정상 반환"""
        from scraper_adapter import compute_news_sentiment_summary
        result = compute_news_sentiment_summary([])
        assert result["총건수"] == 0
        assert result["종합감성"] == "N/A"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
