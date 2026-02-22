#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Stock Analysis Scheduler Daemon
  - APScheduler로 워치리스트별 자동 분석
  - FastAPI 웹 UI를 데몬 스레드로 실행
  - launchd로 프로세스 생명주기 관리
═══════════════════════════════════════════════════════════════
"""
import os
import sys
import signal
import logging
import threading
import time
import uuid
import yaml
from datetime import datetime
from typing import Optional

# 프로젝트 루트를 PYTHONPATH에 추가
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.analysis_wrapper import analyze_watchlist
from scheduler.history_db import HistoryDB
from scheduler.notifiers import create_notifier
from scheduler.notifiers.summary_builder import (
    build_batch_summary_text,
    build_batch_summary_html,
)

logger = logging.getLogger("scheduler")

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "scheduler_config.yaml")


def _resolve_env_vars(obj):
    """재귀적으로 'env:VARIABLE' 패턴을 환경변수 값으로 치환"""
    if isinstance(obj, str):
        if obj.startswith("env:"):
            return os.environ.get(obj[4:], "")
        return obj
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


class StockScheduler:
    """메인 스케줄러 오케스트레이터"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or _CONFIG_PATH
        self.config = self._load_config()
        self.scheduler: Optional[BackgroundScheduler] = None
        self.history_db = HistoryDB()
        self.web_thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()
        self._current_jobs = {}  # watchlist_name -> job status

    def _load_config(self) -> dict:
        """scheduler_config.yaml 로드 (환경변수 치환 포함)"""
        if not os.path.exists(self.config_path):
            logger.error(f"설정 파일 없음: {self.config_path}")
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # 환경변수 치환 (notifications 섹션만)
        if "notifications" in config:
            config["notifications"] = _resolve_env_vars(config["notifications"])

        return config

    def save_config(self):
        """현재 설정을 YAML 파일로 저장 (환경변수 참조는 유지)"""
        # 원본 파일을 다시 읽어서 환경변수 참조를 보존
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                original = yaml.safe_load(f) or {}
        else:
            original = {}

        # watchlists와 scheduler 설정만 업데이트 (notifications는 env 참조 보존)
        original["watchlists"] = self.config.get("watchlists", {})
        sched_cfg = self.config.get("scheduler", {})
        if "scheduler" in original:
            original["scheduler"].update({
                k: v for k, v in sched_cfg.items()
                if k not in ("web_ui",)  # web_ui는 유지
            })

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(original, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False)

    def _setup_jobs(self):
        """워치리스트별 APScheduler 작업 등록"""
        watchlists = self.config.get("watchlists", {})
        timezone = self.config.get("scheduler", {}).get("timezone", "Asia/Seoul")

        for name, wl_config in watchlists.items():
            if not wl_config.get("enabled", True):
                logger.info(f"워치리스트 '{name}' 비활성화됨 (스킵)")
                continue

            schedule = wl_config.get("schedule", "09:00")
            try:
                hour, minute = map(int, schedule.split(":"))
            except ValueError:
                logger.error(f"워치리스트 '{name}' 잘못된 시간 형식: {schedule}")
                continue

            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                timezone=timezone,
            )

            self.scheduler.add_job(
                self._run_watchlist_job,
                trigger=trigger,
                args=[name, wl_config],
                id=f"watchlist_{name}",
                name=f"Watchlist: {name}",
                replace_existing=True,
                misfire_grace_time=3600,  # 1시간 이내면 실행
            )
            logger.info(f"워치리스트 '{name}' 등록: {schedule} {timezone} "
                         f"({len(wl_config.get('tickers', []))}종목)")

    def _run_watchlist_job(self, watchlist_name: str, wl_config: dict):
        """APScheduler 콜백: 워치리스트 분석 실행"""
        run_id = str(uuid.uuid4())[:8]
        self._current_jobs[watchlist_name] = {
            "run_id": run_id,
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }

        logger.info(f"{'='*60}")
        logger.info(f"  스케줄 실행: '{watchlist_name}' (run_id: {run_id})")
        logger.info(f"{'='*60}")

        start_time = time.time()
        tickers = wl_config.get("tickers", [])
        analysis_type = wl_config.get("analysis_type", "full")
        sched_cfg = self.config.get("scheduler", {})

        try:
            # 분석 실행
            results = analyze_watchlist(
                watchlist_name=watchlist_name,
                tickers=tickers,
                analysis_type=analysis_type,
                max_workers=sched_cfg.get("max_concurrent_tickers", 3),
                rate_limit_delay=sched_cfg.get("api_rate_limit_delay", 2.0),
            )

            total_duration = round(time.time() - start_time, 1)

            # 요약 생성
            summary_text = build_batch_summary_text(watchlist_name, results)
            summary_html = build_batch_summary_html(watchlist_name, results)

            # 모든 차트 경로 수집
            all_chart_paths = []
            for r in results:
                if r.success and r.chart_paths:
                    all_chart_paths.extend(r.chart_paths)

            # 알림 발송
            notification_channels = wl_config.get("notifications", ["file"])
            notifications_config = self.config.get("notifications", {})
            notifications_sent = []

            for channel in notification_channels:
                channel_config = notifications_config.get(channel, {})
                try:
                    notifier = create_notifier(channel, channel_config)
                    valid, msg = notifier.validate_config()
                    if not valid:
                        logger.warning(f"알림 채널 '{channel}' 설정 오류: {msg}")
                        continue

                    success = notifier.send_batch_summary(
                        watchlist_name=watchlist_name,
                        results=results,
                        summary_text=summary_text,
                        summary_html=summary_html,
                        chart_paths=all_chart_paths,
                    )
                    if success:
                        notifications_sent.append(channel)
                        logger.info(f"알림 전송 성공: {channel}")
                    else:
                        logger.warning(f"알림 전송 실패: {channel}")
                except Exception as e:
                    logger.error(f"알림 채널 '{channel}' 오류: {e}")

            # 이력 기록
            self.history_db.record_batch(
                run_id=run_id,
                watchlist_name=watchlist_name,
                results=results,
                total_duration=total_duration,
                notifications_sent=notifications_sent,
            )

            self._current_jobs[watchlist_name] = {
                "run_id": run_id,
                "status": "completed",
                "finished_at": datetime.now().isoformat(),
                "duration": total_duration,
                "success_count": sum(1 for r in results if r.success),
                "fail_count": sum(1 for r in results if not r.success),
            }

            logger.info(f"스케줄 완료: '{watchlist_name}' ({total_duration}초)")

        except Exception as e:
            logger.error(f"스케줄 실행 오류: '{watchlist_name}': {e}", exc_info=True)
            self._current_jobs[watchlist_name] = {
                "run_id": run_id,
                "status": "error",
                "error": str(e),
                "finished_at": datetime.now().isoformat(),
            }

    def start(self):
        """데몬 시작"""
        # 로깅 설정
        log_level = self.config.get("scheduler", {}).get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        logger.info("Stock Analysis Scheduler 시작...")
        logger.info(f"설정 파일: {self.config_path}")

        # APScheduler 초기화
        self.scheduler = BackgroundScheduler(
            timezone=self.config.get("scheduler", {}).get("timezone", "Asia/Seoul"),
        )
        self._setup_jobs()
        self.scheduler.start()

        # 웹 UI 시작 (설정된 경우)
        web_cfg = self.config.get("scheduler", {}).get("web_ui", {})
        if web_cfg.get("enabled", True):
            self._start_web_ui(
                host=web_cfg.get("host", "127.0.0.1"),
                port=web_cfg.get("port", 8500),
            )

        # 시그널 핸들러
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.running = True

        # 다음 실행 시간 출력
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                logger.info(f"  {job.name}: 다음 실행 {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        logger.info("스케줄러 실행 중... (Ctrl+C로 종료)")

        # 메인 스레드 대기
        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """데몬 종료"""
        if not self.running:
            return

        logger.info("스케줄러 종료 중...")
        self.running = False

        if self.scheduler:
            self.scheduler.shutdown(wait=False)

        self._stop_event.set()
        logger.info("스케줄러 종료 완료")

    def _signal_handler(self, signum, frame):
        """시그널 핸들러 (SIGTERM/SIGINT)"""
        logger.info(f"시그널 수신: {signum}")
        self._stop_event.set()

    def _start_web_ui(self, host: str = "127.0.0.1", port: int = 8500):
        """FastAPI 웹 UI를 데몬 스레드로 시작"""
        try:
            import uvicorn
            from scheduler.web.app import create_app

            app = create_app(self)

            def _run():
                uvicorn.run(app, host=host, port=port,
                            log_level="warning", access_log=False)

            self.web_thread = threading.Thread(target=_run, daemon=True)
            self.web_thread.start()
            logger.info(f"웹 UI 시작: http://{host}:{port}")
        except ImportError as e:
            logger.warning(f"웹 UI 의존성 부족 (무시): {e}")
        except Exception as e:
            logger.error(f"웹 UI 시작 실패: {e}")

    def manual_run(self, watchlist_name: str) -> dict:
        """수동 실행 (웹 UI / CLI에서 호출)"""
        watchlists = self.config.get("watchlists", {})
        if watchlist_name not in watchlists:
            return {"error": f"워치리스트 '{watchlist_name}' 없음"}

        wl_config = watchlists[watchlist_name]

        # 백그라운드 스레드에서 실행
        thread = threading.Thread(
            target=self._run_watchlist_job,
            args=[watchlist_name, wl_config],
            daemon=True,
        )
        thread.start()

        return {
            "status": "started",
            "watchlist": watchlist_name,
            "tickers": wl_config.get("tickers", []),
        }

    def get_status(self) -> dict:
        """스케줄러 상태 반환"""
        jobs = []
        if self.scheduler:
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S %Z") if next_run else "N/A",
                })

        return {
            "running": self.running,
            "jobs": jobs,
            "current_jobs": self._current_jobs,
            "stats": self.history_db.get_stats(),
        }

    def reload_config(self):
        """설정 재로드 및 작업 재등록"""
        logger.info("설정 재로드 중...")
        self.config = self._load_config()

        if self.scheduler:
            # 기존 작업 모두 제거 후 재등록
            for job in self.scheduler.get_jobs():
                job.remove()
            self._setup_jobs()

        logger.info("설정 재로드 완료")

    def get_watchlists(self) -> dict:
        """워치리스트 설정 반환"""
        return self.config.get("watchlists", {})

    def update_watchlist(self, name: str, wl_config: dict):
        """워치리스트 설정 업데이트"""
        if "watchlists" not in self.config:
            self.config["watchlists"] = {}
        self.config["watchlists"][name] = wl_config
        self.save_config()
        self.reload_config()

    def delete_watchlist(self, name: str):
        """워치리스트 삭제"""
        watchlists = self.config.get("watchlists", {})
        if name in watchlists:
            del watchlists[name]
            self.save_config()
            self.reload_config()


# ─── Entry Point ───
if __name__ == "__main__":
    scheduler = StockScheduler()

    # --once 플래그: 1회 실행 모드
    if "--once" in sys.argv:
        watchlist_name = sys.argv[sys.argv.index("--once") + 1] if len(sys.argv) > sys.argv.index("--once") + 1 else None
        if watchlist_name:
            logging.basicConfig(level=logging.INFO,
                                format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
            watchlists = scheduler.config.get("watchlists", {})
            if watchlist_name in watchlists:
                scheduler._run_watchlist_job(watchlist_name, watchlists[watchlist_name])
            else:
                print(f"워치리스트 '{watchlist_name}' 없음. 사용 가능: {list(watchlists.keys())}")
        else:
            print("Usage: scheduler_runner.py --once <watchlist_name>")
    else:
        scheduler.start()
