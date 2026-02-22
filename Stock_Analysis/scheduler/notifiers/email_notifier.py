"""
═══════════════════════════════════════════════════════════════
  EmailNotifier - SMTP 이메일 알림
  HTML 형식 리포트 + 차트 이미지 첨부
═══════════════════════════════════════════════════════════════
"""
import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from typing import Tuple

from scheduler.notifiers.base import BaseNotifier, resolve_env_value

logger = logging.getLogger("scheduler.notifiers.email")


class EmailNotifier(BaseNotifier):
    """SMTP 이메일 알림 전송"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 587)
        self.use_tls = config.get("use_tls", True)
        self.sender = resolve_env_value(config.get("sender", ""))
        self.password = resolve_env_value(config.get("password", ""))
        self.recipients = config.get("recipients", [])
        self.send_charts = config.get("send_charts", True)

    def _create_message(
        self,
        subject: str,
        html_body: str,
        chart_paths: list = None,
    ) -> MIMEMultipart:
        """이메일 메시지 구성"""
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)

        # HTML 본문
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

        # 차트 이미지 첨부
        if self.send_charts and chart_paths:
            for i, path in enumerate(chart_paths):
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            img = MIMEImage(f.read())
                        img.add_header("Content-ID", f"<chart_{i}>")
                        img.add_header("Content-Disposition", "attachment",
                                       filename=os.path.basename(path))
                        msg.attach(img)
                    except Exception as e:
                        logger.warning(f"차트 첨부 실패 ({path}): {e}")

        return msg

    def _send_email(self, msg: MIMEMultipart) -> bool:
        """이메일 발송"""
        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)

            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            logger.error(f"이메일 발송 실패: {e}")
            return False

    def send_batch_summary(
        self,
        watchlist_name: str,
        results: list,
        summary_text: str,
        summary_html: str,
        chart_paths: list,
    ) -> bool:
        """HTML 이메일 + 차트 첨부 발송"""
        if not self.recipients:
            logger.warning("이메일 수신자 미설정")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"[Stock Analysis] {watchlist_name} 분석 완료 ({now})"

        success_count = sum(1 for r in results if r.success)
        subject += f" - {success_count}/{len(results)} 성공"

        msg = self._create_message(subject, summary_html, chart_paths)
        success = self._send_email(msg)

        if success:
            logger.info(f"이메일 발송 완료: {', '.join(self.recipients)}")
        return success

    def validate_config(self) -> Tuple[bool, str]:
        """설정 유효성 검사"""
        errors = []
        if not self.sender:
            errors.append("sender 미설정 (환경변수 EMAIL_SENDER 확인)")
        if not self.password:
            errors.append("password 미설정 (환경변수 EMAIL_PASSWORD 확인)")
        if not self.recipients:
            errors.append("recipients 목록이 비어있음")

        if errors:
            return False, " | ".join(errors)
        return True, f"이메일 설정 유효 (서버: {self.smtp_server}, 수신: {len(self.recipients)}명)"

    def test_connection(self) -> Tuple[bool, str]:
        """테스트 이메일 발송"""
        valid, msg = self.validate_config()
        if not valid:
            return False, msg

        test_html = """
        <html><body>
        <h2>Stock Analysis Scheduler</h2>
        <p>이메일 알림 테스트 메시지입니다.</p>
        <p>이 메시지를 받으셨다면 이메일 알림이 정상적으로 설정되었습니다.</p>
        </body></html>
        """
        test_msg = self._create_message(
            "[Stock Analysis] 이메일 알림 테스트",
            test_html
        )
        success = self._send_email(test_msg)
        if success:
            return True, f"테스트 이메일 발송 성공 ({', '.join(self.recipients)})"
        return False, "테스트 이메일 발송 실패"
