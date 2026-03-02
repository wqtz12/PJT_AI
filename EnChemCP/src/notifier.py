"""
이메일 알림 모듈 (notifier.py)

SMTP 서버를 통해 PM에게 변동 사항 알림 메일을 발송한다.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from src.utils import get_config, setup_logger

logger = setup_logger(__name__)

SMTP_SERVER = get_config("SMTP_SERVER")
SMTP_PORT = int(get_config("SMTP_PORT", "587"))
SENDER_EMAIL = get_config("SENDER_EMAIL")
SENDER_PASSWORD = get_config("SENDER_PASSWORD")


class EmailNotifier:
    """SMTP 연동을 통한 이메일 알림 클래스."""

    def __init__(self, is_mock: bool = True):
        """
        Args:
            is_mock (bool): True이면 실제 발송 없이 로그만 남긴다.
        """
        self.is_mock = is_mock
        self._validate_config()

    def _validate_config(self) -> None:
        """Guard Clause — 운영 모드에서 설정 누락 시 즉시 경고."""
        if not self.is_mock:
            missing = []
            if not SMTP_SERVER:
                missing.append("SMTP_SERVER")
            if not SENDER_EMAIL:
                missing.append("SENDER_EMAIL")
            if not SENDER_PASSWORD:
                missing.append("SENDER_PASSWORD")
            if missing:
                logger.error(
                    "운영 모드인데 필수 환경변수가 누락되었습니다: %s", ", ".join(missing)
                )
                raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    def send_alert(
        self,
        to_email: str,
        pm_name: str,
        diff_records: List[dict],
        identifier: str = "",
    ) -> None:
        """
        차이 발생 알림 및 사유 작성 요청 메일을 발송한다.

        Args:
            to_email (str): 수신자(PM) 이메일
            pm_name (str): 수신자 이름
            diff_records (list): 변동 사항 딕셔너리 리스트
            identifier (str): 주차/월 구분자 (메일 제목에 사용)
        """
        # Guard Clause
        if not diff_records:
            logger.info("변동 내역 없음 — 메일 발송 건너뜀 (PM: %s)", pm_name)
            return
        if not to_email:
            logger.warning("PM '%s'의 이메일 주소가 없어 발송을 건너뜁니다.", pm_name)
            return

        logger.info("메일 준비 중: PM=%s, 수신=%s, 건수=%d", pm_name, to_email, len(diff_records))

        html_content = self._build_html_body(pm_name, diff_records)

        msg = MIMEMultipart("alternative")
        subject_prefix = f"[{identifier}] " if identifier else ""
        msg["Subject"] = f"{subject_prefix}[Team Cost & Profit] {pm_name}님 주요 변동사항 보고"
        msg["From"] = SENDER_EMAIL if SENDER_EMAIL else "noreply@example.com"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        if self.is_mock:
            logger.info("[Mock] 메일 발송 시뮬레이션 완료: %s → %s", pm_name, to_email)
            return

        # 실 발송
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
            logger.info("메일 발송 성공: %s", to_email)
        except Exception as e:
            logger.error("메일 발송 실패 (%s): %s", to_email, e)
            raise

    @staticmethod
    def _build_html_body(pm_name: str, diff_records: List[dict]) -> str:
        """HTML 메일 본문 생성."""
        rows_html = ""
        for rec in diff_records:
            rows_html += f"""
                <tr>
                    <td>{rec.get('WBS', '-')}</td>
                    <td style="text-align:right">{rec.get('매출차이', 0):,}</td>
                    <td style="text-align:right">{rec.get('영업이익차이', 0):,}</td>
                    <td style="text-align:right">{rec.get('비용차이', 0):,}</td>
                </tr>"""

        return f"""
        <html>
        <body style="font-family: 'Malgun Gothic', sans-serif; font-size: 14px;">
            <h3>[Team Cost &amp; Profit] 프로젝트 변동 알림</h3>
            <p>안녕하세요 <b>{pm_name}</b> PM님,</p>
            <p>담당 프로젝트에서 <b>기준 초과 차액</b>이 발생하여 안내드립니다.</p>
            <p>아래 내역을 확인하시고 변동 사유를 작성해 주세요.</p>

            <table border="1" cellpadding="6" cellspacing="0"
                   style="border-collapse:collapse; min-width:500px;">
                <tr style="background:#4472C4; color:#fff;">
                    <th>프로젝트(WBS)</th>
                    <th>매출 차이</th>
                    <th>영업이익 차이</th>
                    <th>비용 차이</th>
                </tr>
                {rows_html}
            </table>
            <br>
            <p>감사합니다.</p>
        </body>
        </html>"""
