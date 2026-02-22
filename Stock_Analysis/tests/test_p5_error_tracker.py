"""
P5 에러 추적 모듈 테스트 - common/error_tracker.py

테스트 항목:
    - ErrorCategory enum 값 검증
    - record_error() JSONL 기록 / 스레드 안전성
    - get_daily_errors() 읽기 / 빈 파일 / 손상 대응
    - get_daily_summary() 통계 정확성
    - get_error_log_dates() 목록 / 정렬
    - cleanup_old_logs() 보관 기간 기반 삭제
    - 경계 조건 (빈 디렉토리, 잘못된 파일명 등)
"""
import json
import os
import threading
from datetime import datetime, timedelta

import pytest

from common.error_tracker import (
    ErrorCategory,
    record_error,
    get_daily_errors,
    get_daily_summary,
    get_error_log_dates,
    cleanup_old_logs,
    _error_log_path,
    _ensure_error_log_dir,
)


# ──────────────────────────────────────────────
# 1. ErrorCategory enum 테스트
# ──────────────────────────────────────────────
class TestErrorCategory:
    """ErrorCategory enum 기본 검증"""

    def test_all_categories_defined(self):
        """7개 카테고리 모두 존재"""
        expected = {
            "DATA_FETCH", "INDICATOR", "EXPERT_STRATEGY",
            "MACRO_SENTIMENT", "REPORT", "CACHE", "UNEXPECTED",
        }
        actual = {c.name for c in ErrorCategory}
        assert actual == expected

    def test_category_values_are_strings(self):
        """enum value가 문자열"""
        for cat in ErrorCategory:
            assert isinstance(cat.value, str)
            assert cat.value  # 빈 문자열이 아닌지

    def test_category_from_value(self):
        """value로 enum 역참조"""
        assert ErrorCategory("data_fetch") == ErrorCategory.DATA_FETCH
        assert ErrorCategory("unexpected") == ErrorCategory.UNEXPECTED


# ──────────────────────────────────────────────
# 2. _error_log_path() 테스트
# ──────────────────────────────────────────────
class TestErrorLogPath:
    """에러 로그 경로 생성 테스트"""

    def test_path_with_date(self, tmp_path):
        """명시적 날짜로 경로 생성"""
        path = _error_log_path("2024-06-15", str(tmp_path))
        assert path.endswith("error_20240615.jsonl")
        assert str(tmp_path) in path

    def test_path_default_today(self):
        """날짜 생략 시 오늘 날짜"""
        today = datetime.now().strftime("%Y%m%d")
        path = _error_log_path()
        assert f"error_{today}.jsonl" in path

    def test_path_custom_dir(self, tmp_path):
        """커스텀 디렉토리 적용"""
        custom = str(tmp_path / "custom_logs")
        path = _error_log_path("2024-01-01", custom)
        assert custom in path


# ──────────────────────────────────────────────
# 3. record_error() 테스트
# ──────────────────────────────────────────────
class TestRecordError:
    """에러 기록 테스트"""

    def test_basic_record(self, tmp_path):
        """기본 에러 기록"""
        log_dir = str(tmp_path / "error_logs")
        record = record_error(
            category=ErrorCategory.DATA_FETCH,
            module="stock_analyzer",
            message="주가 데이터 수집 실패",
            context={"ticker": "PLUG"},
            log_dir=log_dir,
        )
        assert record["category"] == "data_fetch"
        assert record["module"] == "stock_analyzer"
        assert record["message"] == "주가 데이터 수집 실패"
        assert record["context"]["ticker"] == "PLUG"
        assert record["timestamp"]
        assert record["date"]

    def test_record_with_exception(self, tmp_path):
        """예외 객체 포함 기록"""
        log_dir = str(tmp_path / "error_logs")
        try:
            raise ValueError("테스트 에러")
        except ValueError as e:
            record = record_error(
                category=ErrorCategory.INDICATOR,
                module="indicators",
                message="RSI 계산 실패",
                exception=e,
                log_dir=log_dir,
            )
        assert record["exception_type"] == "ValueError"
        assert "테스트 에러" in record["exception_detail"]
        assert record["traceback"] is not None
        assert len(record["traceback"]) > 0

    def test_record_without_exception(self, tmp_path):
        """예외 없이 기록"""
        log_dir = str(tmp_path / "error_logs")
        record = record_error(
            category=ErrorCategory.CACHE,
            module="cache",
            message="캐시 만료",
            log_dir=log_dir,
        )
        assert record["exception_type"] is None
        assert record["exception_detail"] is None
        assert record["traceback"] is None

    def test_record_creates_directory(self, tmp_path):
        """디렉토리 자동 생성"""
        log_dir = str(tmp_path / "new_dir" / "error_logs")
        assert not os.path.exists(log_dir)
        record_error(
            category=ErrorCategory.UNEXPECTED,
            module="test",
            message="test",
            log_dir=log_dir,
        )
        assert os.path.isdir(log_dir)

    def test_record_appends_to_file(self, tmp_path):
        """같은 날 파일에 append"""
        log_dir = str(tmp_path / "error_logs")
        record_error(
            category=ErrorCategory.DATA_FETCH,
            module="mod1",
            message="에러 1",
            log_dir=log_dir,
        )
        record_error(
            category=ErrorCategory.INDICATOR,
            module="mod2",
            message="에러 2",
            log_dir=log_dir,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        errors = get_daily_errors(today, log_dir)
        assert len(errors) == 2
        assert errors[0]["message"] == "에러 1"
        assert errors[1]["message"] == "에러 2"

    def test_record_jsonl_format(self, tmp_path):
        """JSONL 형식 (한 줄에 하나의 JSON)"""
        log_dir = str(tmp_path / "error_logs")
        record_error(
            category=ErrorCategory.REPORT,
            module="report",
            message="생성 실패",
            log_dir=log_dir,
        )
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(log_dir, f"error_{today}.jsonl")
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["category"] == "report"

    def test_record_returns_dict(self, tmp_path):
        """record_error가 dict를 반환"""
        log_dir = str(tmp_path / "error_logs")
        result = record_error(
            category=ErrorCategory.CACHE,
            module="cache",
            message="test",
            log_dir=log_dir,
        )
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "category" in result

    def test_record_empty_context(self, tmp_path):
        """context 미제공 시 빈 dict"""
        log_dir = str(tmp_path / "error_logs")
        record = record_error(
            category=ErrorCategory.UNEXPECTED,
            module="test",
            message="test",
            log_dir=log_dir,
        )
        assert record["context"] == {}

    def test_thread_safety(self, tmp_path):
        """멀티스레드 동시 기록 안전성"""
        log_dir = str(tmp_path / "error_logs")
        errors_recorded = []

        def write_error(i):
            record = record_error(
                category=ErrorCategory.DATA_FETCH,
                module=f"thread_{i}",
                message=f"에러 {i}",
                log_dir=log_dir,
            )
            errors_recorded.append(record)

        threads = [threading.Thread(target=write_error, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors_recorded) == 20
        today = datetime.now().strftime("%Y-%m-%d")
        errors = get_daily_errors(today, log_dir)
        assert len(errors) == 20

        # 모든 에러가 유효한 JSON인지
        for e in errors:
            assert "module" in e
            assert "message" in e


# ──────────────────────────────────────────────
# 4. get_daily_errors() 테스트
# ──────────────────────────────────────────────
class TestGetDailyErrors:
    """일일 에러 목록 조회 테스트"""

    def test_empty_when_no_file(self, tmp_path):
        """파일 없으면 빈 리스트"""
        log_dir = str(tmp_path / "error_logs")
        errors = get_daily_errors("2024-01-01", log_dir)
        assert errors == []

    def test_read_existing_errors(self, tmp_path):
        """기존 에러 읽기"""
        log_dir = str(tmp_path / "error_logs")
        record_error(
            category=ErrorCategory.DATA_FETCH,
            module="test",
            message="에러 메시지",
            context={"key": "value"},
            log_dir=log_dir,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        errors = get_daily_errors(today, log_dir)
        assert len(errors) == 1
        assert errors[0]["context"]["key"] == "value"

    def test_handles_corrupted_line(self, tmp_path):
        """손상된 JSONL 라인 스킵"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(log_dir, f"error_{today}.jsonl")

        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"category": "test", "message": "정상"}) + "\n")
            f.write("이것은 잘못된 JSON\n")
            f.write(json.dumps({"category": "test2", "message": "정상2"}) + "\n")

        today_formatted = datetime.now().strftime("%Y-%m-%d")
        errors = get_daily_errors(today_formatted, log_dir)
        assert len(errors) == 2
        assert errors[0]["message"] == "정상"
        assert errors[1]["message"] == "정상2"

    def test_handles_empty_lines(self, tmp_path):
        """빈 줄 무시"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(log_dir, f"error_{today}.jsonl")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n")
            f.write(json.dumps({"message": "유일한 에러"}) + "\n")
            f.write("\n")

        today_formatted = datetime.now().strftime("%Y-%m-%d")
        errors = get_daily_errors(today_formatted, log_dir)
        assert len(errors) == 1


# ──────────────────────────────────────────────
# 5. get_daily_summary() 테스트
# ──────────────────────────────────────────────
class TestGetDailySummary:
    """일일 에러 요약 테스트"""

    def test_empty_summary(self, tmp_path):
        """에러 없을 때 요약"""
        log_dir = str(tmp_path / "error_logs")
        summary = get_daily_summary("2024-01-01", log_dir)
        assert summary["total_errors"] == 0
        assert summary["by_category"] == {}
        assert summary["most_common_category"] is None

    def test_summary_counts(self, tmp_path):
        """카테고리/모듈별 집계 정확성"""
        log_dir = str(tmp_path / "error_logs")

        # 다양한 에러 기록
        record_error(ErrorCategory.DATA_FETCH, "mod_a", "err1", log_dir=log_dir)
        record_error(ErrorCategory.DATA_FETCH, "mod_a", "err2", log_dir=log_dir)
        record_error(ErrorCategory.INDICATOR, "mod_b", "err3", log_dir=log_dir)
        record_error(ErrorCategory.DATA_FETCH, "mod_b", "err4", log_dir=log_dir)

        today = datetime.now().strftime("%Y-%m-%d")
        summary = get_daily_summary(today, log_dir)

        assert summary["total_errors"] == 4
        assert summary["by_category"]["data_fetch"] == 3
        assert summary["by_category"]["indicator"] == 1
        assert summary["by_module"]["mod_a"] == 2
        assert summary["by_module"]["mod_b"] == 2
        assert summary["most_common_category"] == "data_fetch"

    def test_summary_unique_messages(self, tmp_path):
        """고유 메시지 수 카운트"""
        log_dir = str(tmp_path / "error_logs")
        record_error(ErrorCategory.CACHE, "mod", "같은 메시지", log_dir=log_dir)
        record_error(ErrorCategory.CACHE, "mod", "같은 메시지", log_dir=log_dir)
        record_error(ErrorCategory.CACHE, "mod", "다른 메시지", log_dir=log_dir)

        today = datetime.now().strftime("%Y-%m-%d")
        summary = get_daily_summary(today, log_dir)
        assert summary["unique_messages"] == 2

    def test_summary_has_hour_distribution(self, tmp_path):
        """시간대별 분포 포함"""
        log_dir = str(tmp_path / "error_logs")
        record_error(ErrorCategory.REPORT, "mod", "err", log_dir=log_dir)

        today = datetime.now().strftime("%Y-%m-%d")
        summary = get_daily_summary(today, log_dir)
        assert len(summary["by_hour"]) >= 1

    def test_summary_date_field(self, tmp_path):
        """summary에 date 필드 포함"""
        log_dir = str(tmp_path / "error_logs")
        summary = get_daily_summary("2024-12-25", log_dir)
        assert summary["date"] == "2024-12-25"


# ──────────────────────────────────────────────
# 6. get_error_log_dates() 테스트
# ──────────────────────────────────────────────
class TestGetErrorLogDates:
    """에러 로그 날짜 목록 테스트"""

    def test_empty_directory(self, tmp_path):
        """빈 디렉토리"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)
        assert get_error_log_dates(log_dir) == []

    def test_nonexistent_directory(self, tmp_path):
        """존재하지 않는 디렉토리"""
        log_dir = str(tmp_path / "does_not_exist")
        assert get_error_log_dates(log_dir) == []

    def test_lists_dates_sorted(self, tmp_path):
        """날짜 목록 정렬"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        # 순서 뒤섞어 생성
        for d in ["20240315", "20240101", "20240228"]:
            with open(os.path.join(log_dir, f"error_{d}.jsonl"), "w") as f:
                f.write("{}\n")

        dates = get_error_log_dates(log_dir)
        assert dates == ["2024-01-01", "2024-02-28", "2024-03-15"]

    def test_ignores_non_error_files(self, tmp_path):
        """error_ 접두사가 아닌 파일 무시"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        with open(os.path.join(log_dir, "error_20240101.jsonl"), "w") as f:
            f.write("{}\n")
        with open(os.path.join(log_dir, "healing_20240101.jsonl"), "w") as f:
            f.write("{}\n")
        with open(os.path.join(log_dir, "random.txt"), "w") as f:
            f.write("noise")

        dates = get_error_log_dates(log_dir)
        assert dates == ["2024-01-01"]

    def test_ignores_invalid_date_filenames(self, tmp_path):
        """잘못된 날짜 파일명 무시"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        with open(os.path.join(log_dir, "error_20240101.jsonl"), "w") as f:
            f.write("{}\n")
        with open(os.path.join(log_dir, "error_99999999.jsonl"), "w") as f:
            f.write("{}\n")
        with open(os.path.join(log_dir, "error_abc.jsonl"), "w") as f:
            f.write("{}\n")

        dates = get_error_log_dates(log_dir)
        assert "2024-01-01" in dates
        # 99999999는 유효하지 않은 날짜이므로 포함되지 않아야 함
        for d in dates:
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Invalid date in list: {d}")


# ──────────────────────────────────────────────
# 7. cleanup_old_logs() 테스트
# ──────────────────────────────────────────────
class TestCleanupOldLogs:
    """오래된 로그 정리 테스트"""

    def test_cleanup_old_files(self, tmp_path):
        """보관 기간 초과 파일 삭제"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        # 40일 전 파일 (삭제 대상)
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"error_{old_date}.jsonl"), "w") as f:
            f.write("{}\n")

        # 오늘 파일 (보존)
        today = datetime.now().strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"error_{today}.jsonl"), "w") as f:
            f.write("{}\n")

        deleted = cleanup_old_logs(retention_days=30, log_dir=log_dir)
        assert deleted == 1
        assert not os.path.exists(os.path.join(log_dir, f"error_{old_date}.jsonl"))
        assert os.path.exists(os.path.join(log_dir, f"error_{today}.jsonl"))

    def test_cleanup_keeps_recent(self, tmp_path):
        """보관 기간 내 파일 보존"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"error_{recent_date}.jsonl"), "w") as f:
            f.write("{}\n")

        deleted = cleanup_old_logs(retention_days=30, log_dir=log_dir)
        assert deleted == 0

    def test_cleanup_nonexistent_dir(self, tmp_path):
        """존재하지 않는 디렉토리"""
        log_dir = str(tmp_path / "does_not_exist")
        deleted = cleanup_old_logs(retention_days=30, log_dir=log_dir)
        assert deleted == 0

    def test_cleanup_healing_logs(self, tmp_path):
        """healing 로그도 정리"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"healing_{old_date}.jsonl"), "w") as f:
            f.write("{}\n")

        deleted = cleanup_old_logs(retention_days=30, log_dir=log_dir)
        assert deleted == 1

    def test_cleanup_analysis_reports(self, tmp_path):
        """분석 보고서도 정리"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"analysis_report_{old_date}.txt"), "w") as f:
            f.write("old report")

        deleted = cleanup_old_logs(retention_days=30, log_dir=log_dir)
        assert deleted == 1

    def test_cleanup_custom_retention(self, tmp_path):
        """커스텀 보관 기간"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        # 10일 전 파일
        date_10 = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        with open(os.path.join(log_dir, f"error_{date_10}.jsonl"), "w") as f:
            f.write("{}\n")

        # retention=7 → 삭제됨
        deleted = cleanup_old_logs(retention_days=7, log_dir=log_dir)
        assert deleted == 1

        # 재생성 후 retention=15 → 보존
        with open(os.path.join(log_dir, f"error_{date_10}.jsonl"), "w") as f:
            f.write("{}\n")
        deleted = cleanup_old_logs(retention_days=15, log_dir=log_dir)
        assert deleted == 0
