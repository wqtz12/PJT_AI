"""
═══════════════════════════════════════════════════════════════
  TelegramNotifier - 텔레그램 Bot API 알림
  요약 메시지 + 차트 이미지 전송
═══════════════════════════════════════════════════════════════
"""
import os
import logging
from typing import Tuple

from scheduler.notifiers.base import BaseNotifier, resolve_env_value

logger = logging.getLogger("scheduler.notifiers.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramNotifier(BaseNotifier):
    """텔레그램 Bot API를 통한 알림 전송"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = resolve_env_value(config.get("bot_token", ""))
        self.chat_id = resolve_env_value(config.get("chat_id", ""))
        self.send_charts = config.get("send_charts", True)
        self.max_chart_count = config.get("max_chart_count", 3)

    def _get_base_url(self) -> str:
        return TELEGRAM_API.format(token=self.bot_token)

    def _send_message(self, text: str) -> bool:
        """텍스트 메시지 전송"""
        try:
            import httpx

            # 텔레그램 메시지 길이 제한 (4096자)
            if len(text) > 4000:
                text = text[:3997] + "..."

            url = f"{self._get_base_url()}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            resp = httpx.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {e}")
            return False

    def _send_photo(self, photo_path: str, caption: str = "") -> bool:
        """이미지 전송"""
        try:
            import httpx

            if not os.path.exists(photo_path):
                logger.warning(f"차트 파일 없음: {photo_path}")
                return False

            url = f"{self._get_base_url()}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f, "image/png")}
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption[:1024]  # 캡션 길이 제한
                resp = httpx.post(url, data=data, files=files, timeout=60)
                resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"텔레그램 이미지 전송 실패: {e}")
            return False

    def send_batch_summary(
        self,
        watchlist_name: str,
        results: list,
        summary_text: str,
        summary_html: str,
        chart_paths: list,
    ) -> bool:
        """배치 요약 전송 (텍스트 + 차트)"""
        # 1. 텍스트 요약 전송
        success = self._send_message(f"<pre>{summary_text}</pre>")

        # 2. 차트 이미지 전송 (설정된 경우)
        if self.send_charts and chart_paths:
            sent = 0
            for path in chart_paths[:self.max_chart_count]:
                if os.path.exists(path):
                    ticker = os.path.basename(path).split("_")[0]
                    if self._send_photo(path, caption=f"{ticker} 차트"):
                        sent += 1
            if sent > 0:
                logger.info(f"텔레그램 차트 {sent}개 전송")

        return success

    def validate_config(self) -> Tuple[bool, str]:
        """설정 유효성 검사"""
        if not self.bot_token:
            return False, "bot_token 미설정 (환경변수 TELEGRAM_BOT_TOKEN 확인)"
        if not self.chat_id:
            return False, "chat_id 미설정 (환경변수 TELEGRAM_CHAT_ID 확인)"
        return True, "텔레그램 설정 유효"

    def test_connection(self) -> Tuple[bool, str]:
        """테스트 메시지 전송"""
        valid, msg = self.validate_config()
        if not valid:
            return False, msg

        success = self._send_message(
            "<b>Stock Analysis Scheduler</b>\n"
            "텔레그램 알림 테스트 메시지입니다."
        )
        if success:
            return True, "텔레그램 테스트 메시지 전송 성공"
        return False, "텔레그램 테스트 메시지 전송 실패"
