"""
═══════════════════════════════════════════════════════════════
  FileNotifier - 파일 저장 알림
  분석 결과를 로컬 파일 시스템에 요약 리포트로 저장
═══════════════════════════════════════════════════════════════
"""
import os
import logging
from datetime import datetime
from typing import Tuple

from scheduler.notifiers.base import BaseNotifier

logger = logging.getLogger("scheduler.notifiers.file")


class FileNotifier(BaseNotifier):
    """파일 시스템에 배치 요약 저장"""

    def send_batch_summary(
        self,
        watchlist_name: str,
        results: list,
        summary_text: str,
        summary_html: str,
        chart_paths: list,
    ) -> bool:
        """요약 텍스트를 파일로 저장"""
        try:
            output_dir = self.config.get("output_dir", "output/scheduled")
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{watchlist_name}_summary_{timestamp}.txt"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary_text)

            logger.info(f"배치 요약 저장: {filepath}")
            return True

        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
            return False

    def validate_config(self) -> Tuple[bool, str]:
        """설정 유효성 검사"""
        output_dir = self.config.get("output_dir", "output/scheduled")
        try:
            os.makedirs(output_dir, exist_ok=True)
            return True, f"출력 디렉토리: {output_dir}"
        except Exception as e:
            return False, f"디렉토리 생성 실패: {e}"

    def test_connection(self) -> Tuple[bool, str]:
        """테스트 파일 생성"""
        try:
            output_dir = self.config.get("output_dir", "output/scheduled")
            os.makedirs(output_dir, exist_ok=True)
            test_path = os.path.join(output_dir, "_test_notification.txt")
            with open(test_path, "w") as f:
                f.write(f"Test notification at {datetime.now().isoformat()}\n")
            os.remove(test_path)
            return True, f"파일 알림 정상 (디렉토리: {output_dir})"
        except Exception as e:
            return False, f"테스트 실패: {e}"
