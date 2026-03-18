"""
Notification subsystem - 알림 채널 관리
"""
from scheduler.notifiers.base import BaseNotifier
from scheduler.notifiers.file_notifier import FileNotifier
from scheduler.notifiers.telegram_notifier import TelegramNotifier
from scheduler.notifiers.email_notifier import EmailNotifier
from scheduler.notifiers.slack_notifier import SlackNotifier

NOTIFIER_REGISTRY = {
    "file": FileNotifier,
    "telegram": TelegramNotifier,
    "email": EmailNotifier,
    "slack": SlackNotifier,
}


def create_notifier(channel: str, config: dict) -> BaseNotifier:
    """채널명으로 노티파이어 인스턴스 생성"""
    cls = NOTIFIER_REGISTRY.get(channel)
    if cls is None:
        raise ValueError(f"Unknown notification channel: {channel}. "
                         f"Available: {list(NOTIFIER_REGISTRY.keys())}")
    return cls(config)
