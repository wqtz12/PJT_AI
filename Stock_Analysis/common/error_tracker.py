"""
구조화된 에러 추적 모듈 - JSONL 형식 일자별 에러 로그 관리

기능:
    - 에러 발생 시 구조화된 JSONL 형식으로 기록
    - 일자별 에러 로그 파일 자동 분리 (error_YYYYMMDD.jsonl)
    - 스레드 안전 기록 (ThreadPoolExecutor 병렬 수집 대응)
    - 에러 카테고리 분류 (DATA_FETCH, INDICATOR, EXPERT_STRATEGY 등)
    - 일일 요약 통계 생성
    - 오래된 로그 자동 정리

사용법:
    from common.error_tracker import record_error, get_daily_summary, ErrorCategory
    record_error(
        category=ErrorCategory.DATA_FETCH,
        module="stock_analyzer",
        message="주가 데이터 수집 실패",
        context={"ticker": "PLUG"}
    )
    summary = get_daily_summary("2024-01-15")

로그 저장 위치: Stock_Analysis/output/error_logs/
"""
import json
import os
import logging
import threading
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 에러 로그 디렉토리 ───
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_LOG_DIR = os.path.join(_BASE_DIR, "output", "error_logs")

# ─── 스레드 안전을 위한 Lock ───
_write_lock = threading.Lock()


class ErrorCategory(Enum):
    """에러 카테고리 분류"""
    DATA_FETCH = "data_fetch"           # 데이터 수집 (yfinance, 뉴스, 애널리스트)
    INDICATOR = "indicator"             # 기술적 지표 계산
    EXPERT_STRATEGY = "expert_strategy" # 전문가 전략 분석
    MACRO_SENTIMENT = "macro_sentiment" # 매크로/감성 분석
    REPORT = "report"                   # 리포트 생성
    CACHE = "cache"                     # 캐시 처리
    UNEXPECTED = "unexpected"           # 예상치 못한 에러


def _ensure_error_log_dir(log_dir: str = None):
    """에러 로그 디렉토리 생성"""
    target = log_dir or ERROR_LOG_DIR
    os.makedirs(target, exist_ok=True)


def _error_log_path(date_str: str = None, log_dir: str = None) -> str:
    """
    일자별 에러 로그 파일 경로 반환

    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD), None이면 오늘
        log_dir: 로그 디렉토리 경로, None이면 기본값

    Returns:
        에러 로그 파일 절대 경로
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    date_part = date_str.replace("-", "")
    target = log_dir or ERROR_LOG_DIR
    return os.path.join(target, f"error_{date_part}.jsonl")


def record_error(
    category: ErrorCategory,
    module: str,
    message: str,
    context: dict = None,
    exception: Exception = None,
    log_dir: str = None,
) -> dict:
    """
    에러를 구조화된 JSONL 형식으로 기록

    Args:
        category: 에러 카테고리 (ErrorCategory enum)
        module: 에러 발생 모듈명
        message: 에러 메시지
        context: 추가 컨텍스트 (ticker, 단계 등)
        exception: 원본 예외 객체
        log_dir: 로그 디렉토리 (테스트용)

    Returns:
        dict: 기록된 에러 레코드
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    record = {
        "timestamp": now.isoformat(),
        "date": date_str,
        "category": category.value if isinstance(category, ErrorCategory) else str(category),
        "module": module,
        "message": message,
        "context": context or {},
    }

    # 예외 정보 추가
    if exception is not None:
        record["exception_type"] = type(exception).__name__
        record["exception_detail"] = str(exception)
        record["traceback"] = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
    else:
        record["exception_type"] = None
        record["exception_detail"] = None
        record["traceback"] = None

    # JSONL 파일에 스레드 안전하게 기록
    try:
        _ensure_error_log_dir(log_dir)
        path = _error_log_path(date_str, log_dir)

        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        logger.debug(f"에러 기록: [{category.value}] {module} - {message}")
    except Exception as e:
        # 에러 기록 자체가 실패해도 메인 파이프라인은 계속
        logger.warning(f"에러 로그 기록 실패: {e}")

    return record


def get_daily_errors(date_str: str = None, log_dir: str = None) -> list:
    """
    특정 날짜의 에러 목록 조회

    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD), None이면 오늘
        log_dir: 로그 디렉토리 (테스트용)

    Returns:
        list[dict]: 에러 레코드 목록
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    path = _error_log_path(date_str, log_dir)

    if not os.path.exists(path):
        return []

    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    errors.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONL 파싱 실패 (line {line_num}): {e}")
    except Exception as e:
        logger.warning(f"에러 로그 읽기 실패: {e}")

    return errors


def get_daily_summary(date_str: str = None, log_dir: str = None) -> dict:
    """
    특정 날짜의 에러 요약 통계 생성

    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD), None이면 오늘
        log_dir: 로그 디렉토리 (테스트용)

    Returns:
        dict: 에러 요약 (총 건수, 카테고리별 건수, 모듈별 건수, 시간대별 분포)
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    errors = get_daily_errors(date_str, log_dir)

    if not errors:
        return {
            "date": date_str,
            "total_errors": 0,
            "by_category": {},
            "by_module": {},
            "by_hour": {},
            "unique_messages": 0,
            "most_common_category": None,
            "most_common_module": None,
        }

    # 카테고리별 집계
    by_category = {}
    for e in errors:
        cat = e.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    # 모듈별 집계
    by_module = {}
    for e in errors:
        mod = e.get("module", "unknown")
        by_module[mod] = by_module.get(mod, 0) + 1

    # 시간대별 집계
    by_hour = {}
    for e in errors:
        try:
            ts = e.get("timestamp", "")
            hour = ts[11:13] if len(ts) > 13 else "unknown"
            by_hour[hour] = by_hour.get(hour, 0) + 1
        except (IndexError, TypeError):
            pass

    # 고유 메시지 수
    unique_messages = len(set(e.get("message", "") for e in errors))

    # 최다 카테고리/모듈
    most_common_category = max(by_category, key=by_category.get) if by_category else None
    most_common_module = max(by_module, key=by_module.get) if by_module else None

    return {
        "date": date_str,
        "total_errors": len(errors),
        "by_category": by_category,
        "by_module": by_module,
        "by_hour": by_hour,
        "unique_messages": unique_messages,
        "most_common_category": most_common_category,
        "most_common_module": most_common_module,
    }


def get_error_log_dates(log_dir: str = None) -> list:
    """
    에러 로그가 존재하는 날짜 목록 반환 (정렬됨)

    Args:
        log_dir: 로그 디렉토리 (테스트용)

    Returns:
        list[str]: 날짜 목록 (YYYY-MM-DD 형식)
    """
    target = log_dir or ERROR_LOG_DIR
    if not os.path.exists(target):
        return []

    dates = []
    for fname in os.listdir(target):
        if fname.startswith("error_") and fname.endswith(".jsonl"):
            date_part = fname[6:-6]  # error_YYYYMMDD.jsonl → YYYYMMDD
            if len(date_part) == 8 and date_part.isdigit():
                try:
                    formatted = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    # 유효한 날짜인지 검증
                    datetime.strptime(formatted, "%Y-%m-%d")
                    dates.append(formatted)
                except ValueError:
                    continue

    return sorted(dates)


def cleanup_old_logs(retention_days: int = 30, log_dir: str = None) -> int:
    """
    오래된 에러 로그 파일 삭제

    Args:
        retention_days: 보관 일수 (기본 30일)
        log_dir: 로그 디렉토리 (테스트용)

    Returns:
        int: 삭제된 파일 수
    """
    target = log_dir or ERROR_LOG_DIR
    if not os.path.exists(target):
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff.strftime("%Y%m%d")
    deleted = 0

    for fname in os.listdir(target):
        if fname.startswith("error_") and fname.endswith(".jsonl"):
            date_part = fname[6:-6]  # error_YYYYMMDD.jsonl → YYYYMMDD
            if len(date_part) == 8 and date_part.isdigit():
                if date_part < cutoff_str:
                    try:
                        os.remove(os.path.join(target, fname))
                        deleted += 1
                        logger.debug(f"오래된 에러 로그 삭제: {fname}")
                    except OSError as e:
                        logger.warning(f"에러 로그 삭제 실패: {fname} - {e}")

    # healing 로그도 정리
    for fname in os.listdir(target):
        if fname.startswith("healing_") and fname.endswith(".jsonl"):
            date_part = fname[8:-6]  # healing_YYYYMMDD.jsonl → YYYYMMDD
            if len(date_part) == 8 and date_part.isdigit():
                if date_part < cutoff_str:
                    try:
                        os.remove(os.path.join(target, fname))
                        deleted += 1
                    except OSError:
                        pass

    # 분석 보고서도 정리
    for fname in os.listdir(target):
        if fname.startswith("analysis_report_") and fname.endswith(".txt"):
            date_part = fname[16:-4]  # analysis_report_YYYYMMDD.txt → YYYYMMDD
            if len(date_part) == 8 and date_part.isdigit():
                if date_part < cutoff_str:
                    try:
                        os.remove(os.path.join(target, fname))
                        deleted += 1
                    except OSError:
                        pass

    if deleted > 0:
        logger.info(f"오래된 로그 정리: {deleted}개 파일 삭제 (보관 {retention_days}일)")

    return deleted
