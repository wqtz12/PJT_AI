"""
═══════════════════════════════════════════════════════════════
  SlackNotifier - Slack Incoming Webhook 알림
  Block Kit 포맷 메시지 전송
═══════════════════════════════════════════════════════════════
"""
import logging
from datetime import datetime
from typing import Tuple

from scheduler.notifiers.base import BaseNotifier, resolve_env_value

logger = logging.getLogger("scheduler.notifiers.slack")


class SlackNotifier(BaseNotifier):
    """Slack Incoming Webhook 알림 전송"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = resolve_env_value(config.get("webhook_url", ""))
        self.channel = config.get("channel", "#stock-alerts")

    def _post_message(self, blocks: list, text: str = "") -> bool:
        """Slack 웹훅으로 메시지 전송"""
        try:
            import httpx

            payload = {
                "channel": self.channel,
                "text": text or "Stock Analysis 알림",
                "blocks": blocks,
            }
            resp = httpx.post(self.webhook_url, json=payload, timeout=30)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"슬랙 메시지 전송 실패: {e}")
            return False

    def _build_blocks(self, watchlist_name: str, results: list) -> list:
        """Slack Block Kit 포맷 메시지 생성"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"\U0001f4ca {watchlist_name} \ubd84\uc11d \uacb0\uacfc",
                    "emoji": True,
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"{now} | {len(results)}\uc885\ubaa9 ({success_count}\uc131\uacf5, {fail_count}\uc2e4\ud328)"
                }]
            },
            {"type": "divider"},
        ]

        # 종목별 결과
        lines = []
        for r in sorted(results, key=lambda x: x.ticker):
            if r.success:
                emoji = {"매수": ":large_green_circle:",
                         "매도": ":red_circle:",
                         "홀드": ":large_yellow_circle:"}.get(
                    r.dominant_position or "홀드", ":white_circle:")
                price = f"${r.current_price:.2f}" if r.current_price else "N/A"
                change = f"{r.change_pct:+.1f}%" if r.change_pct is not None else ""
                conf = f"{r.avg_confidence:.0f}%"
                lines.append(
                    f"{emoji} *{r.ticker}* {r.dominant_position or '홀드'} "
                    f"({conf}) | {price} {change}"
                )
            else:
                lines.append(f":x: *{r.ticker}* \uc2e4\ud328")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            }
        })

        # 매크로 환경
        macro_env = None
        for r in results:
            if r.success and r.macro_environment:
                macro_env = r.macro_environment
                break
        if macro_env:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f":globe_with_meridians: \ub9e4\ud06c\ub85c \ud658\uacbd: *{macro_env}*"
                }]
            })

        return blocks

    def send_batch_summary(
        self,
        watchlist_name: str,
        results: list,
        summary_text: str,
        summary_html: str,
        chart_paths: list,
    ) -> bool:
        """Slack Block Kit 메시지 전송"""
        blocks = self._build_blocks(watchlist_name, results)
        success = self._post_message(blocks, text=f"{watchlist_name} 분석 완료")

        if success:
            logger.info(f"슬랙 알림 전송 완료: {self.channel}")
        return success

    def validate_config(self) -> Tuple[bool, str]:
        """설정 유효성 검사"""
        if not self.webhook_url:
            return False, "webhook_url 미설정 (환경변수 SLACK_WEBHOOK_URL 확인)"
        if not self.webhook_url.startswith("http"):
            return False, f"유효하지 않은 webhook URL: {self.webhook_url[:20]}..."
        return True, f"슬랙 설정 유효 (채널: {self.channel})"

    def test_connection(self) -> Tuple[bool, str]:
        """테스트 메시지 전송"""
        valid, msg = self.validate_config()
        if not valid:
            return False, msg

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Stock Analysis Scheduler*\n\uc2ac\ub799 \uc54c\ub9bc \ud14c\uc2a4\ud2b8 \uba54\uc2dc\uc9c0\uc785\ub2c8\ub2e4."
                }
            }
        ]
        success = self._post_message(blocks, "Stock Analysis 테스트")
        if success:
            return True, "슬랙 테스트 메시지 전송 성공"
        return False, "슬랙 테스트 메시지 전송 실패"
