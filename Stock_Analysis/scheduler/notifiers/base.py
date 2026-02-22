"""
═══════════════════════════════════════════════════════════════
  BaseNotifier - 알림 채널 추상 인터페이스
═══════════════════════════════════════════════════════════════
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Tuple

logger = logging.getLogger("scheduler.notifiers")


def resolve_env_value(value) -> str:
    """'env:VARIABLE_NAME' 형식의 값을 환경변수에서 로드"""
    if isinstance(value, str) and value.startswith("env:"):
        var_name = value[4:]
        resolved = os.environ.get(var_name, "")
        if not resolved:
            logger.warning(f"환경변수 '{var_name}' 미설정")
        return resolved
    return str(value) if value is not None else ""


class BaseNotifier(ABC):
    """
    모든 알림 채널의 기반 클래스.

    배치 요약 1건을 전송하는 인터페이스를 정의합니다.
    (종목별 개별 알림이 아닌, 워치리스트 단위 요약)
    """

    def __init__(self, config: dict):
        self.config = config
        self.enabled = True

    @abstractmethod
    def send_batch_summary(
        self,
        watchlist_name: str,
        results: list,
        summary_text: str,
        summary_html: str,
        chart_paths: list,
    ) -> bool:
        """
        워치리스트 배치 분석 결과 알림 전송.

        Args:
            watchlist_name: 워치리스트 이름
            results: AnalysisResult 리스트
            summary_text: 텍스트 형식 요약
            summary_html: HTML 형식 요약
            chart_paths: 첨부할 차트 파일 경로들

        Returns:
            전송 성공 여부
        """

    @abstractmethod
    def validate_config(self) -> Tuple[bool, str]:
        """
        설정 유효성 검사.

        Returns:
            (유효 여부, 오류 메시지)
        """

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        테스트 알림 전송.

        Returns:
            (성공 여부, 결과 메시지)
        """
