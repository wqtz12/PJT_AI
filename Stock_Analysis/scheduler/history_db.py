"""
═══════════════════════════════════════════════════════════════
  Scheduler History DB - SQLite 기반 분석 이력 관리
═══════════════════════════════════════════════════════════════
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("scheduler.history")

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "scheduler_history.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    watchlist_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,

    -- 핵심 결과
    current_price REAL,
    change_pct REAL,
    dominant_position TEXT,
    weighted_buy REAL,
    weighted_sell REAL,
    weighted_hold REAL,
    avg_confidence REAL,
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    hold_count INTEGER DEFAULT 0,
    technical_signal TEXT,
    macro_environment TEXT,
    news_sentiment_label TEXT,
    analyst_consensus TEXT,

    -- 파일 참조
    report_path TEXT,
    chart_paths TEXT,

    -- 성능
    analysis_duration_sec REAL
);

CREATE INDEX IF NOT EXISTS idx_runs_watchlist ON analysis_runs(watchlist_name);
CREATE INDEX IF NOT EXISTS idx_runs_ticker ON analysis_runs(ticker);
CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON analysis_runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_runs_run_id ON analysis_runs(run_id);

CREATE TABLE IF NOT EXISTS batch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    watchlist_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    total_tickers INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    total_duration_sec REAL,
    notifications_sent TEXT
);

CREATE INDEX IF NOT EXISTS idx_batch_watchlist ON batch_runs(watchlist_name);
CREATE INDEX IF NOT EXISTS idx_batch_timestamp ON batch_runs(timestamp);
"""


class HistoryDB:
    """SQLite 기반 분석 이력 관리"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._init_db()

    def _init_db(self):
        """DB 초기화 (테이블 없으면 생성)"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        """SQLite 연결 (WAL 모드 활성화)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def record_batch(self, run_id: str, watchlist_name: str,
                     results: list, total_duration: float = 0,
                     notifications_sent: list = None):
        """배치 실행 결과 기록"""
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        with self._connect() as conn:
            # 배치 기록
            conn.execute(
                """INSERT INTO batch_runs
                   (run_id, watchlist_name, timestamp, total_tickers,
                    success_count, fail_count, total_duration_sec, notifications_sent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, watchlist_name, datetime.now().isoformat(),
                 len(results), success_count, fail_count, total_duration,
                 json.dumps(notifications_sent or []))
            )

            # 개별 종목 기록
            for r in results:
                conn.execute(
                    """INSERT INTO analysis_runs
                       (run_id, watchlist_name, ticker, company_name, timestamp,
                        success, error_message, current_price, change_pct,
                        dominant_position, weighted_buy, weighted_sell, weighted_hold,
                        avg_confidence, buy_count, sell_count, hold_count,
                        technical_signal, macro_environment, news_sentiment_label,
                        analyst_consensus, report_path, chart_paths,
                        analysis_duration_sec)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                               ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, watchlist_name, r.ticker, r.name, r.timestamp,
                     1 if r.success else 0, r.error_message,
                     r.current_price, r.change_pct,
                     r.dominant_position, r.weighted_buy, r.weighted_sell,
                     r.weighted_hold, r.avg_confidence,
                     r.buy_count, r.sell_count, r.hold_count,
                     r.technical_signal, r.macro_environment,
                     r.news_sentiment_label, r.analyst_consensus,
                     r.report_path, json.dumps(r.chart_paths),
                     r.analysis_duration_sec)
                )
            conn.commit()

    def get_history(self, watchlist_name: str = None, ticker: str = None,
                    limit: int = 50, offset: int = 0) -> list:
        """분석 이력 조회"""
        query = "SELECT * FROM analysis_runs WHERE 1=1"
        params = []

        if watchlist_name:
            query += " AND watchlist_name = ?"
            params.append(watchlist_name)
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_batch_history(self, watchlist_name: str = None,
                          limit: int = 20) -> list:
        """배치 실행 이력 조회"""
        query = "SELECT * FROM batch_runs WHERE 1=1"
        params = []

        if watchlist_name:
            query += " AND watchlist_name = ?"
            params.append(watchlist_name)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_run_details(self, run_id: str) -> list:
        """특정 배치 실행의 상세 결과"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_runs WHERE run_id = ? ORDER BY ticker",
                (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_latest_run(self, watchlist_name: str) -> Optional[dict]:
        """워치리스트의 가장 최근 배치 실행"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM batch_runs WHERE watchlist_name = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (watchlist_name,)
            ).fetchone()
            return dict(row) if row else None

    def get_stats(self) -> dict:
        """전체 통계"""
        with self._connect() as conn:
            total_runs = conn.execute(
                "SELECT COUNT(*) FROM batch_runs"
            ).fetchone()[0]
            total_analyses = conn.execute(
                "SELECT COUNT(*) FROM analysis_runs"
            ).fetchone()[0]
            success_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_runs WHERE success = 1"
            ).fetchone()[0]
            today_runs = conn.execute(
                "SELECT COUNT(*) FROM batch_runs WHERE timestamp >= ?",
                (datetime.now().strftime("%Y-%m-%d"),)
            ).fetchone()[0]

            return {
                "total_batch_runs": total_runs,
                "total_analyses": total_analyses,
                "success_count": success_count,
                "fail_count": total_analyses - success_count,
                "success_rate": round(success_count / total_analyses * 100, 1) if total_analyses > 0 else 0,
                "today_runs": today_runs,
            }

    def cleanup_old(self, days: int = 90):
        """오래된 이력 정리"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            # 배치 기록에 연결된 분석 기록 삭제
            conn.execute(
                "DELETE FROM analysis_runs WHERE timestamp < ?", (cutoff,))
            conn.execute(
                "DELETE FROM batch_runs WHERE timestamp < ?", (cutoff,))
            conn.execute("VACUUM")
            conn.commit()
        logger.info(f"이력 정리 완료: {days}일 이전 데이터 삭제")
