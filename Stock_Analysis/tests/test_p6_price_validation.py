"""
P6 가격 교차검증 테스트 - Phase 1 (P0-1)

테스트 항목:
    - validate_price_freshness(): 히스토리 vs 실시간 가격 검증
    - clear_ticker_cache(): 종목별 캐시 삭제
    - config.yaml price_validation 섹션 기본값 검증
    - stock_analyzer.py 통합 (가격 괴리 → 캐시 무효화 흐름)
"""
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from data_fetcher import validate_price_freshness, _safe_numeric
from common.cache import (
    clear_ticker_cache, set_cache, get_cache, _cache_path, clear_cache,
    get_market_aware_ttl, detect_market,
)
from common.config import get_config


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 OHLCV 데이터프레임 생성
# ──────────────────────────────────────────────
def _make_ohlcv(
    close: float = 100.0,
    rows: int = 30,
    end_date: datetime = None,
    tz: str = "US/Eastern",
) -> pd.DataFrame:
    """테스트용 OHLCV 데이터프레임 생성"""
    if end_date is None:
        end_date = datetime.now()

    dates = pd.date_range(
        end=end_date, periods=rows, freq="B", tz=tz,
    )
    data = {
        "Open": [close * 0.99] * rows,
        "High": [close * 1.01] * rows,
        "Low": [close * 0.98] * rows,
        "Close": [close] * rows,
        "Volume": [1000000] * rows,
    }
    return pd.DataFrame(data, index=dates)


# ══════════════════════════════════════════════
# 1. validate_price_freshness() 기본 동작
# ══════════════════════════════════════════════
class TestValidatePriceFreshnessBasic:
    """가격 교차검증 기본 테스트"""

    def test_empty_dataframe_returns_invalid(self):
        """빈 데이터프레임 → valid=False"""
        df = pd.DataFrame()
        result = validate_price_freshness(df, "TEST")
        assert result["valid"] is False
        assert "비어있음" in result["warning"]
        assert result["history_price"] is None

    def test_history_price_extracted_correctly(self):
        """마지막 행의 Close가 history_price로 추출"""
        df = _make_ohlcv(close=150.0)
        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = {}
            result = validate_price_freshness(df, "TEST")

        assert result["history_price"] == 150.0

    def test_no_discrepancy_when_prices_match(self):
        """히스토리 == 실시간 → valid, 괴리율 ~0"""
        df = _make_ohlcv(close=200.0)
        company_info = {"currentPrice": 200.0}
        result = validate_price_freshness(df, "TEST", company_info=company_info)

        assert result["valid"] is True
        assert result["history_price"] == 200.0
        assert result["realtime_price"] == 200.0
        assert result["discrepancy_pct"] == 0.0

    def test_small_discrepancy_is_valid(self):
        """작은 괴리 (<5%) → valid=True, 경고 없음"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 103.0}  # 3% 괴리
        result = validate_price_freshness(df, "TEST", company_info=company_info)

        assert result["valid"] is True
        assert result["discrepancy_pct"] == 3.0
        assert result["warning"] is None or "괴리" not in (result["warning"] or "")


# ══════════════════════════════════════════════
# 2. 괴리율 경고/에러 케이스
# ══════════════════════════════════════════════
class TestValidatePriceDiscrepancy:
    """가격 괴리 감지 테스트"""

    def test_large_discrepancy_triggers_warning(self):
        """괴리 >5% → valid=False + 경고"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 110.0}  # 10% 괴리
        result = validate_price_freshness(df, "TSLA", company_info=company_info)

        assert result["valid"] is False
        assert result["discrepancy_pct"] == 10.0
        assert "괴리" in result["warning"]
        assert "TSLA" in result["warning"]

    def test_custom_threshold(self):
        """threshold_pct 커스텀 설정"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 102.0}  # 2% 괴리

        # threshold=1% → 경고
        result = validate_price_freshness(
            df, "TEST", company_info=company_info, threshold_pct=1.0,
        )
        assert result["valid"] is False
        assert result["discrepancy_pct"] == 2.0

        # threshold=5% → 정상
        result = validate_price_freshness(
            df, "TEST", company_info=company_info, threshold_pct=5.0,
        )
        assert result["valid"] is True

    def test_exact_threshold_boundary(self):
        """정확히 threshold_pct 경계값 → valid=True (초과만 경고)"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 105.0}  # 정확히 5%
        result = validate_price_freshness(
            df, "TEST", company_info=company_info, threshold_pct=5.0,
        )
        # 5.0 > 5.0 is False → valid=True
        assert result["valid"] is True
        assert result["discrepancy_pct"] == 5.0

    def test_discrepancy_pct_is_absolute(self):
        """괴리율은 절대값 (하락도 감지)"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 88.0}  # -12% 괴리
        result = validate_price_freshness(df, "SMR", company_info=company_info)

        assert result["valid"] is False
        assert result["discrepancy_pct"] == 12.0
        assert "괴리" in result["warning"]


# ══════════════════════════════════════════════
# 3. 실시간 가격 미가용 (한국주식 등)
# ══════════════════════════════════════════════
class TestRealtimePriceUnavailable:
    """실시간 가격 미가용 케이스"""

    def test_no_realtime_price_skips_validation(self):
        """yfinance info에서 가격 못 찾으면 → valid=True (스킵)"""
        df = _make_ohlcv(close=100.0)
        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = {}  # 가격 필드 없음
            result = validate_price_freshness(df, "012450.KS")

        assert result["valid"] is True
        assert result["realtime_price"] is None
        assert result["discrepancy_pct"] is None

    def test_company_info_korean_price_keys(self):
        """한국주식 company_info에 '현재가' 키 사용"""
        df = _make_ohlcv(close=100000.0)
        company_info = {"현재가": 103000.0}  # 3%
        result = validate_price_freshness(
            df, "012450.KS", company_info=company_info,
        )

        assert result["valid"] is True
        assert result["realtime_price"] == 103000.0
        assert result["discrepancy_pct"] == 3.0

    def test_yfinance_info_exception_graceful(self):
        """yfinance info 조회 중 예외 → valid=True (graceful)"""
        df = _make_ohlcv(close=100.0)
        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = property(
                lambda self: (_ for _ in ()).throw(Exception("API Error"))
            )
            # info 접근 시 예외가 발생하도록 설정
            mock_yf.Ticker.return_value = MagicMock()
            mock_yf.Ticker.return_value.info.__getitem__ = MagicMock(
                side_effect=Exception("API Error")
            )
            type(mock_yf.Ticker.return_value).info = property(
                lambda self: (_ for _ in ()).throw(Exception("API Error"))
            )
            result = validate_price_freshness(df, "FAIL_TICKER")

        assert result["valid"] is True
        assert result["realtime_price"] is None


# ══════════════════════════════════════════════
# 4. company_info 가격 키 우선순위
# ══════════════════════════════════════════════
class TestCompanyInfoPriority:
    """company_info에서 실시간 가격 추출 우선순위"""

    def test_prefers_company_info_over_yfinance(self):
        """company_info가 있으면 yfinance 재호출 안 함"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 101.0}

        with patch("data_fetcher.yf") as mock_yf:
            result = validate_price_freshness(
                df, "TEST", company_info=company_info,
            )
            # yfinance Ticker가 호출되지 않았어야 함
            mock_yf.Ticker.assert_not_called()

        assert result["realtime_price"] == 101.0

    def test_falls_back_to_yfinance_when_company_info_empty(self):
        """company_info에 가격 없으면 yfinance 조회"""
        df = _make_ohlcv(close=100.0)
        company_info = {"이름": "TestCo"}  # 가격 필드 없음

        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = {"currentPrice": 105.0}
            result = validate_price_freshness(
                df, "TEST", company_info=company_info,
            )

        assert result["realtime_price"] == 105.0

    def test_company_info_key_priority(self):
        """현재가 > regularMarketPrice > currentPrice 순서"""
        df = _make_ohlcv(close=100.0)

        # "현재가"가 가장 먼저 시도됨
        info = {"현재가": 101.0, "regularMarketPrice": 102.0, "currentPrice": 103.0}
        result = validate_price_freshness(df, "TEST", company_info=info)
        assert result["realtime_price"] == 101.0

        # "현재가" 없으면 "regularMarketPrice"
        info2 = {"regularMarketPrice": 102.0, "currentPrice": 103.0}
        result2 = validate_price_freshness(df, "TEST", company_info=info2)
        assert result2["realtime_price"] == 102.0

    def test_zero_or_negative_price_ignored(self):
        """0 이하 가격 값은 무시"""
        df = _make_ohlcv(close=100.0)
        company_info = {"currentPrice": 0, "regularMarketPrice": -5.0}

        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = {"currentPrice": 99.0}
            result = validate_price_freshness(
                df, "TEST", company_info=company_info,
            )

        assert result["realtime_price"] == 99.0


# ══════════════════════════════════════════════
# 5. Stale 데이터 감지
# ══════════════════════════════════════════════
class TestStaleDataDetection:
    """오래된 데이터 감지"""

    def test_fresh_data_no_stale_warning(self):
        """최근 데이터 → stale 경고 없음"""
        df = _make_ohlcv(close=100.0, end_date=datetime.now())
        company_info = {"currentPrice": 100.0}
        result = validate_price_freshness(df, "TEST", company_info=company_info)

        assert result["stale_days"] <= 3
        # stale 경고가 아닌 경우
        if result["warning"]:
            assert "stale" not in result["warning"]

    def test_stale_data_detected(self):
        """14일 전 데이터 → stale 경고"""
        old_date = datetime.now() - timedelta(days=14)
        df = _make_ohlcv(close=100.0, end_date=old_date)

        with patch("data_fetcher.yf") as mock_yf:
            mock_yf.Ticker.return_value.info = {}
            result = validate_price_freshness(df, "STALE")

        # 타임존 차이로 ±1일 허용
        assert result["stale_days"] >= 7  # stale_days_warning 기본값 3 초과 확인
        assert result["warning"] is not None
        assert "stale" in result["warning"].lower() or "일 전" in result["warning"]


# ══════════════════════════════════════════════
# 6. clear_ticker_cache() 테스트
# ══════════════════════════════════════════════
class TestClearTickerCache:
    """종목별 캐시 삭제"""

    def setup_method(self):
        """테스트 전 캐시 정리"""
        clear_cache()

    def teardown_method(self):
        """테스트 후 캐시 정리"""
        clear_cache()

    def test_clears_existing_cache_files(self):
        """존재하는 캐시 파일만 삭제"""
        ticker = "TEST_CLEAR"
        # 캐시 생성
        set_cache(f"stock_data_{ticker}_6mo", {"data": True})
        set_cache(f"company_info_{ticker}", {"info": True})

        # 파일 존재 확인
        assert os.path.exists(_cache_path(f"stock_data_{ticker}_6mo"))
        assert os.path.exists(_cache_path(f"company_info_{ticker}"))

        # 삭제
        count = clear_ticker_cache(ticker)
        assert count == 2

        # 삭제 확인
        assert not os.path.exists(_cache_path(f"stock_data_{ticker}_6mo"))
        assert not os.path.exists(_cache_path(f"company_info_{ticker}"))

    def test_returns_zero_when_no_cache(self):
        """캐시 없을 때 → 0 반환"""
        count = clear_ticker_cache("NONEXISTENT_TICKER")
        assert count == 0

    def test_does_not_affect_other_tickers(self):
        """다른 종목의 캐시는 건드리지 않음"""
        set_cache("stock_data_AAPL_6mo", {"aapl": True})
        set_cache("stock_data_TSLA_6mo", {"tsla": True})

        clear_ticker_cache("TSLA")

        # AAPL 캐시는 남아있어야 함
        assert get_cache("stock_data_AAPL_6mo", ttl_minutes=60) is not None
        # TSLA 캐시는 삭제됨
        assert not os.path.exists(_cache_path("stock_data_TSLA_6mo"))


# ══════════════════════════════════════════════
# 7. config price_validation 기본값 검증
# ══════════════════════════════════════════════
class TestPriceValidationConfig:
    """price_validation 설정값 검증"""

    def test_defaults_exist(self):
        """price_validation 기본값이 config에 존재"""
        cfg = get_config()
        pv = cfg.get("price_validation", {})
        assert "enabled" in pv
        assert "threshold_pct" in pv
        assert "auto_refresh" in pv
        assert "stale_days_warning" in pv

    def test_default_values(self):
        """기본값이 올바른지"""
        cfg = get_config()
        pv = cfg["price_validation"]
        assert pv["enabled"] is True
        assert pv["threshold_pct"] == 5.0
        assert pv["auto_refresh"] is True
        assert pv["stale_days_warning"] == 3

    def test_threshold_is_numeric(self):
        """threshold_pct는 숫자"""
        cfg = get_config()
        assert isinstance(cfg["price_validation"]["threshold_pct"], (int, float))


# ══════════════════════════════════════════════
# 8. _safe_numeric() 테스트 (가격 검증에 사용)
# ══════════════════════════════════════════════
class TestSafeNumeric:
    """_safe_numeric 유틸리티"""

    def test_normal_int(self):
        assert _safe_numeric(42) == 42

    def test_normal_float(self):
        assert _safe_numeric(3.14) == 3.14

    def test_none_returns_default(self):
        assert _safe_numeric(None) is None
        assert _safe_numeric(None, default=-1) == -1

    def test_nan_returns_default(self):
        assert _safe_numeric(float("nan")) is None

    def test_inf_returns_default(self):
        assert _safe_numeric(float("inf")) is None

    def test_string_returns_default(self):
        assert _safe_numeric("N/A") is None
        assert _safe_numeric("100") is None  # 문자열은 변환 안 함


# ══════════════════════════════════════════════════════════════
# Phase 2: 시장 상태 연동 캐시 TTL 테스트
# ══════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────
# 9. detect_market() 테스트
# ──────────────────────────────────────────────
class TestDetectMarket:
    """티커 기반 시장 감지"""

    def test_us_stock(self):
        assert detect_market("AAPL") == "US"
        assert detect_market("TSLA") == "US"
        assert detect_market("NVDA") == "US"

    def test_korean_stock_ks(self):
        assert detect_market("012450.KS") == "KR"
        assert detect_market("005930.KS") == "KR"

    def test_korean_stock_kq(self):
        assert detect_market("247540.KQ") == "KR"

    def test_default_is_us(self):
        """알 수 없는 형식 → US"""
        assert detect_market("UNKNOWN") == "US"
        assert detect_market("1234.T") == "US"  # 일본도 US 취급


# ──────────────────────────────────────────────
# 10. get_market_aware_ttl() 테스트
# ──────────────────────────────────────────────
class TestMarketAwareTTL:
    """시장 상태 연동 동적 TTL"""

    def _make_dt(self, year=2026, month=2, day=12, hour=10, minute=0, tz_str="US/Eastern"):
        """특정 시각으로 datetime 생성"""
        import pytz
        tz = pytz.timezone(tz_str)
        return tz.localize(datetime(year, month, day, hour, minute))

    def test_us_market_open_returns_base_ttl(self):
        """US 장중(10:00 ET, 평일) → base TTL"""
        # 2026-02-12은 목요일
        now = self._make_dt(hour=10, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30

    def test_us_market_close_returns_multiplied_ttl(self):
        """US 장마감(18:00 ET) → base × 4"""
        now = self._make_dt(hour=18, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30 * 4  # 120

    def test_us_before_open_returns_multiplied_ttl(self):
        """US 장전(08:00 ET) → base × 4"""
        now = self._make_dt(hour=8, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30 * 4  # 120

    def test_us_weekend_returns_weekend_ttl(self):
        """US 주말(토요일) → base × 16"""
        # 2026-02-14는 토요일
        now = self._make_dt(day=14, hour=12, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30 * 16  # 480

    def test_us_sunday_returns_weekend_ttl(self):
        """US 일요일 → base × 16"""
        # 2026-02-15는 일요일
        now = self._make_dt(day=15, hour=10, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30 * 16  # 480

    def test_kr_market_open(self):
        """KR 장중(10:00 KST) → base TTL"""
        now = self._make_dt(hour=10, minute=0, tz_str="Asia/Seoul")
        ttl = get_market_aware_ttl(30, "KR", now=now)
        assert ttl == 30

    def test_kr_market_close(self):
        """KR 장마감(17:00 KST) → base × 4"""
        now = self._make_dt(hour=17, minute=0, tz_str="Asia/Seoul")
        ttl = get_market_aware_ttl(30, "KR", now=now)
        assert ttl == 30 * 4  # 120

    def test_kr_weekend(self):
        """KR 주말 → base × 16"""
        # 2026-02-14는 토요일
        now = self._make_dt(day=14, hour=10, minute=0, tz_str="Asia/Seoul")
        ttl = get_market_aware_ttl(30, "KR", now=now)
        assert ttl == 30 * 16  # 480

    def test_different_base_ttl(self):
        """다양한 base_ttl 값 지원"""
        now = self._make_dt(hour=10, minute=0)  # 장중
        assert get_market_aware_ttl(15, "US", now=now) == 15
        assert get_market_aware_ttl(60, "US", now=now) == 60
        assert get_market_aware_ttl(120, "US", now=now) == 120

    def test_disabled_returns_base_ttl(self):
        """기능 비활성화 시 base_ttl 그대로 반환"""
        now = self._make_dt(hour=18, minute=0)  # 장마감
        with patch("common.config.get_config") as mock_cfg:
            mock_cfg.return_value = {"cache": {"market_aware_ttl": False}}
            ttl = get_market_aware_ttl(30, "US", now=now)
            assert ttl == 30  # 배율 적용 안 됨

    def test_at_market_open_boundary(self):
        """정확히 장 시작 시간(09:30 ET) → 장중 TTL"""
        now = self._make_dt(hour=9, minute=30)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30

    def test_at_market_close_boundary(self):
        """정확히 장 마감 시간(16:00 ET) → 장중 TTL"""
        now = self._make_dt(hour=16, minute=0)
        ttl = get_market_aware_ttl(30, "US", now=now)
        assert ttl == 30


# ──────────────────────────────────────────────
# 11. cache config 기본값 검증
# ──────────────────────────────────────────────
class TestCacheConfig:
    """cache 설정값 검증"""

    def test_cache_defaults_exist(self):
        """cache 기본값이 config에 존재"""
        cfg = get_config()
        cache = cfg.get("cache", {})
        assert "market_aware_ttl" in cache
        assert "us_market_hours" in cache
        assert "kr_market_hours" in cache
        assert "after_hours_multiplier" in cache
        assert "weekend_multiplier" in cache

    def test_us_market_hours(self):
        """US 장 시간 기본값"""
        cfg = get_config()
        us = cfg["cache"]["us_market_hours"]
        assert us["open"] == "09:30"
        assert us["close"] == "16:00"
        assert us["tz"] == "US/Eastern"

    def test_kr_market_hours(self):
        """KR 장 시간 기본값"""
        cfg = get_config()
        kr = cfg["cache"]["kr_market_hours"]
        assert kr["open"] == "09:00"
        assert kr["close"] == "15:30"
        assert kr["tz"] == "Asia/Seoul"

    def test_multiplier_values(self):
        """배율 기본값"""
        cfg = get_config()
        assert cfg["cache"]["after_hours_multiplier"] == 4
        assert cfg["cache"]["weekend_multiplier"] == 16
