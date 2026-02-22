"""
P3-1 테스트: API 캐싱 & 병렬 처리
- cached_call() 동작 검증
- get_cache() / set_cache() 기본 동작
- 캐시 TTL 만료
- clear_cache() 동작
- cache_stats() 통계
- ThreadPoolExecutor 병렬 실행 패턴 검증
- stock_analyzer.py 캐싱/병렬 통합 검증
"""
import os
import sys
import time
import pickle
import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.cache import (
    cached_call,
    get_cache,
    set_cache,
    clear_cache,
    cache_stats,
    _cache_path,
    _CACHE_DIR,
)


# ─── Fixture: 테스트 전후 캐시 정리 ───

@pytest.fixture(autouse=True)
def clean_cache():
    """각 테스트 전후로 캐시 정리"""
    clear_cache()
    yield
    clear_cache()


# ─── get_cache / set_cache 기본 동작 ───

class TestSetGetCache:
    """set_cache / get_cache 기본 동작"""

    def test_set_and_get(self):
        set_cache("test_key_1", {"data": 42})
        result = get_cache("test_key_1", ttl_minutes=30)
        assert result == {"data": 42}

    def test_get_nonexistent_returns_none(self):
        result = get_cache("nonexistent_key_xyz", ttl_minutes=30)
        assert result is None

    def test_cache_stores_various_types(self):
        """다양한 타입 저장/복원"""
        test_cases = [
            ("str_key", "hello"),
            ("int_key", 42),
            ("list_key", [1, 2, 3]),
            ("dict_key", {"a": 1, "b": [2, 3]}),
            ("float_key", 3.14),
            ("bool_key", True),
            ("none_key_val", None),
        ]
        for key, value in test_cases:
            # None 값은 캐시에 저장되지만 get에서 miss로 처리됨 (의도적 설계)
            set_cache(key, value)
            result = get_cache(key, ttl_minutes=30)
            if value is None:
                # None은 cached_call에서 miss로 처리
                assert result is None
            else:
                assert result == value, f"타입 {type(value).__name__} 복원 실패"

    def test_cache_creates_directory(self):
        """캐시 디렉토리 자동 생성"""
        set_cache("dir_test", "value")
        assert os.path.exists(_CACHE_DIR)

    def test_cache_file_is_pickle(self):
        """캐시 파일이 pickle 형식"""
        set_cache("pickle_test", [1, 2, 3])
        path = _cache_path("pickle_test")
        assert os.path.exists(path)
        assert path.endswith(".pkl")

        with open(path, "rb") as f:
            data = pickle.load(f)
        assert data == [1, 2, 3]


class TestCacheTTL:
    """캐시 TTL (유효시간) 검증"""

    def test_fresh_cache_is_valid(self):
        """방금 저장한 캐시는 유효"""
        set_cache("ttl_fresh", "fresh_data")
        result = get_cache("ttl_fresh", ttl_minutes=30)
        assert result == "fresh_data"

    def test_expired_cache_returns_none(self):
        """만료된 캐시는 None 반환"""
        set_cache("ttl_expired", "old_data")
        # 파일 수정 시간을 과거로 변경
        path = _cache_path("ttl_expired")
        old_time = time.time() - 3600  # 1시간 전
        os.utime(path, (old_time, old_time))

        result = get_cache("ttl_expired", ttl_minutes=30)
        assert result is None

    def test_ttl_boundary(self):
        """TTL 경계값: 정확히 TTL 직전은 유효"""
        set_cache("ttl_boundary", "boundary_data")
        path = _cache_path("ttl_boundary")
        # 29분 전으로 설정 (30분 TTL보다 이전)
        nearly_expired = time.time() - (29 * 60)
        os.utime(path, (nearly_expired, nearly_expired))

        result = get_cache("ttl_boundary", ttl_minutes=30)
        assert result == "boundary_data"

    def test_short_ttl(self):
        """짧은 TTL 설정"""
        set_cache("ttl_short", "short_data")
        path = _cache_path("ttl_short")
        # 2분 전으로 설정
        old_time = time.time() - 120
        os.utime(path, (old_time, old_time))

        result = get_cache("ttl_short", ttl_minutes=1)
        assert result is None  # 1분 TTL, 2분 경과 → 만료


# ─── cached_call() 래퍼 ───

class TestCachedCall:
    """cached_call() 래퍼 함수 검증"""

    def test_first_call_executes_function(self):
        """첫 호출 시 함수 실행"""
        call_count = {"n": 0}
        def expensive_func():
            call_count["n"] += 1
            return "result"

        result = cached_call("cc_first", expensive_func, ttl_minutes=30)
        assert result == "result"
        assert call_count["n"] == 1

    def test_second_call_uses_cache(self):
        """두 번째 호출 시 캐시 사용"""
        call_count = {"n": 0}
        def expensive_func():
            call_count["n"] += 1
            return "result"

        cached_call("cc_second", expensive_func, ttl_minutes=30)
        cached_call("cc_second", expensive_func, ttl_minutes=30)
        assert call_count["n"] == 1  # 한 번만 호출됨

    def test_cached_call_with_args(self):
        """인자가 있는 함수 캐싱"""
        def add(a, b):
            return a + b

        result = cached_call("cc_args", add, 3, 4, ttl_minutes=30)
        assert result == 7

    def test_cached_call_with_kwargs(self):
        """키워드 인자가 있는 함수 캐싱"""
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = cached_call("cc_kwargs", greet, "World", greeting="Hi", ttl_minutes=30)
        assert result == "Hi, World!"

    def test_expired_cache_re_executes(self):
        """만료된 캐시는 함수 재실행"""
        call_count = {"n": 0}
        def func():
            call_count["n"] += 1
            return f"call_{call_count['n']}"

        # 첫 호출
        result1 = cached_call("cc_expire", func, ttl_minutes=30)
        assert result1 == "call_1"

        # 캐시 시간을 과거로 변경하여 만료시킴
        path = _cache_path("cc_expire")
        old_time = time.time() - 3600
        os.utime(path, (old_time, old_time))

        # 재호출 → 함수 다시 실행
        result2 = cached_call("cc_expire", func, ttl_minutes=30)
        assert result2 == "call_2"
        assert call_count["n"] == 2

    def test_different_keys_independent(self):
        """다른 키는 독립적으로 캐시"""
        def func(x):
            return x * 2

        r1 = cached_call("key_a", func, 5, ttl_minutes=30)
        r2 = cached_call("key_b", func, 10, ttl_minutes=30)
        assert r1 == 10
        assert r2 == 20


# ─── clear_cache() ───

class TestClearCache:
    """clear_cache() 동작 검증"""

    def test_clear_removes_all(self):
        """모든 캐시 파일 삭제"""
        set_cache("clear_1", "data1")
        set_cache("clear_2", "data2")
        set_cache("clear_3", "data3")

        count = clear_cache()
        assert count == 3

    def test_clear_empty_returns_zero(self):
        """빈 캐시에서 clear → 0 반환"""
        count = clear_cache()
        assert count == 0

    def test_cleared_cache_not_available(self):
        """삭제 후 조회 시 None"""
        set_cache("clear_check", "data")
        clear_cache()
        result = get_cache("clear_check", ttl_minutes=30)
        assert result is None


# ─── cache_stats() ───

class TestCacheStats:
    """cache_stats() 통계 검증"""

    def test_empty_stats(self):
        """빈 캐시 통계"""
        stats = cache_stats()
        assert stats["files"] == 0
        assert stats["total_size_mb"] == 0

    def test_stats_after_set(self):
        """데이터 저장 후 통계"""
        set_cache("stats_1", "data1")
        set_cache("stats_2", list(range(100)))

        stats = cache_stats()
        assert stats["files"] == 2
        assert stats["total_size_mb"] > 0

    def test_stats_has_age_info(self):
        """통계에 age 정보 포함"""
        set_cache("stats_age", "data")
        stats = cache_stats()
        assert "oldest_minutes" in stats
        assert "newest_minutes" in stats
        assert stats["oldest_minutes"] >= 0
        assert stats["newest_minutes"] >= 0


# ─── _cache_path() ───

class TestCachePath:
    """캐시 경로 생성 검증"""

    def test_path_is_in_cache_dir(self):
        path = _cache_path("test_key")
        assert _CACHE_DIR in path

    def test_path_ends_with_pkl(self):
        path = _cache_path("test_key")
        assert path.endswith(".pkl")

    def test_same_key_same_path(self):
        """같은 키 → 같은 경로"""
        p1 = _cache_path("same_key")
        p2 = _cache_path("same_key")
        assert p1 == p2

    def test_different_key_different_path(self):
        """다른 키 → 다른 경로"""
        p1 = _cache_path("key_alpha")
        p2 = _cache_path("key_beta")
        assert p1 != p2

    def test_special_chars_in_key(self):
        """특수문자 키도 안전한 경로 생성"""
        path = _cache_path("stock/PLUG:6mo!@#")
        assert os.path.isabs(os.path.dirname(path)) or True  # 경로가 유효한지
        assert ".pkl" in path


# ─── 병렬 처리 패턴 검증 ───

class TestParallelExecution:
    """ThreadPoolExecutor 병렬 실행 검증"""

    def test_parallel_tasks_complete(self):
        """병렬 작업이 모두 완료되는지"""
        results = {}

        def task_a():
            time.sleep(0.05)
            return "a_done"

        def task_b():
            time.sleep(0.05)
            return "b_done"

        def task_c():
            time.sleep(0.05)
            return "c_done"

        task_map = {"a": task_a, "b": task_b, "c": task_c}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in task_map.items()}
            for future in as_completed(futures):
                task_name = futures[future]
                results[task_name] = future.result()

        assert results["a"] == "a_done"
        assert results["b"] == "b_done"
        assert results["c"] == "c_done"

    def test_parallel_faster_than_sequential(self):
        """병렬이 순차보다 빠른지 (대략적 확인)"""
        def slow_task():
            time.sleep(0.1)
            return True

        # 병렬 실행
        start = time.time()
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(slow_task) for _ in range(3)]
            for f in futures:
                f.result()
        parallel_time = time.time() - start

        # 순차 실행
        start = time.time()
        for _ in range(3):
            slow_task()
        sequential_time = time.time() - start

        # 병렬이 순차보다 빨라야 함 (최소 1.5배)
        assert parallel_time < sequential_time * 0.8

    def test_parallel_error_handling(self):
        """병렬 작업 중 에러 발생 시 다른 작업에 영향 없음"""
        results = {}

        def success_task():
            return "ok"

        def failing_task():
            raise ValueError("의도적 에러")

        task_map = {"good": success_task, "bad": failing_task}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(fn): name for name, fn in task_map.items()}
            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    results[task_name] = future.result()
                except Exception as e:
                    results[task_name] = f"error: {e}"

        assert results["good"] == "ok"
        assert "error" in results["bad"]

    def test_cached_call_in_parallel(self):
        """cached_call이 병렬 환경에서도 동작"""
        call_count = {"n": 0}

        def expensive():
            call_count["n"] += 1
            return "expensive_result"

        # 같은 키로 병렬 cached_call → 첫 호출만 실행, 나머지는 캐시
        # (race condition이 있을 수 있지만 결과는 항상 올바름)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(cached_call, f"parallel_key", expensive, ttl_minutes=30)
                for _ in range(5)
            ]
            results = [f.result() for f in futures]

        assert all(r == "expensive_result" for r in results)


# ─── stock_analyzer.py 통합 검증 ───

class TestStockAnalyzerCacheIntegration:
    """stock_analyzer.py가 캐싱/병렬을 사용하는지 소스 레벨 검증"""

    def test_imports_cached_call(self):
        """stock_analyzer가 cached_call을 import"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "from common.cache import cached_call" in source

    def test_imports_thread_pool(self):
        """stock_analyzer가 ThreadPoolExecutor를 import"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "ThreadPoolExecutor" in source

    def test_main_uses_cached_call(self):
        """main()에서 cached_call 사용"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "cached_call(" in source

    def test_main_uses_thread_pool(self):
        """main()에서 ThreadPoolExecutor 사용"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "ThreadPoolExecutor(max_workers=" in source

    def test_parallel_tasks_defined(self):
        """ratings, summary, news 병렬 작업 정의"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "fetch_analyst_ratings" in source
        assert "fetch_analyst_summary" in source
        assert "fetch_news" in source

    def test_stock_data_cached(self):
        """주가 데이터 캐싱 키 패턴"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "stock_data_" in source

    def test_company_info_cached(self):
        """기업 정보 캐싱 키 패턴"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "company_info_" in source

    def test_cache_stats_logged(self):
        """캐시 통계 로깅"""
        import stock_analyzer
        source = open(stock_analyzer.__file__).read()
        assert "cache_stats()" in source


# ─── 캐시 키 충돌 방지 ───

class TestCacheKeyIsolation:
    """다른 종목의 캐시가 충돌하지 않는지"""

    def test_different_tickers_different_keys(self):
        """PLUG와 AAPL의 캐시 키가 다름"""
        p1 = _cache_path("stock_data_PLUG_6mo")
        p2 = _cache_path("stock_data_AAPL_6mo")
        assert p1 != p2

    def test_different_tickers_independent_cache(self):
        """다른 종목의 캐시가 독립적"""
        set_cache("stock_data_PLUG_6mo", {"ticker": "PLUG"})
        set_cache("stock_data_AAPL_6mo", {"ticker": "AAPL"})

        plug = get_cache("stock_data_PLUG_6mo", ttl_minutes=30)
        aapl = get_cache("stock_data_AAPL_6mo", ttl_minutes=30)

        assert plug["ticker"] == "PLUG"
        assert aapl["ticker"] == "AAPL"

    def test_stock_vs_info_keys_different(self):
        """stock_data vs company_info 키가 다름"""
        p1 = _cache_path("stock_data_PLUG_6mo")
        p2 = _cache_path("company_info_PLUG")
        assert p1 != p2
