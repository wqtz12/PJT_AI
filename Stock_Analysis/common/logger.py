"""
공통 로깅 설정 모듈
- 파일 + 콘솔 듀얼 핸들러
- 모듈별 로거 제공
- 에러 발생 시 상세 컨텍스트 포함
"""
import logging
import os
import sys
from datetime import datetime

# 로그 디렉터리
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "logs")


def setup_logging(level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """
    전역 로깅 설정

    Args:
        level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR")
        log_to_file: 파일 출력 여부

    Returns:
        root logger
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 포맷터
    console_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    file_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # 파일 핸들러
    if log_to_file:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_filename = datetime.now().strftime("analysis_%Y%m%d_%H%M%S.log")
        log_path = os.path.join(LOG_DIR, log_filename)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 파일은 항상 DEBUG
        file_handler.setFormatter(file_fmt)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """모듈별 로거 생성"""
    return logging.getLogger(name)


class AnalysisError(Exception):
    """분석 파이프라인 에러 기본 클래스"""

    def __init__(self, message: str, module: str = "", context: dict = None):
        self.module = module
        self.context = context or {}
        super().__init__(f"[{module}] {message}" if module else message)


class DataFetchError(AnalysisError):
    """데이터 수집 에러"""
    pass


class IndicatorError(AnalysisError):
    """기술적 지표 계산 에러"""
    pass


class ExpertAnalysisError(AnalysisError):
    """전문가 분석 에러"""
    pass


class ReportGenerationError(AnalysisError):
    """리포트 생성 에러"""
    pass
