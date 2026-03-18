"""
API 응답 캐싱 모듈 - yfinance 호출 결과를 디스크에 캐싱

사용법:
    from common.cache import cached_call
    # 30분 TTL로 캐싱
    df = cached_call("stock_data_PLUG_6mo", fetch_stock_data, "PLUG", "6mo", ttl_minutes=30)

캐시 저장 위치: Stock_Analysis/.cache/
"""
import os
import time
import hashlib
import pickle
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")


def _ensure_cache_dir():
    """캐시 디렉토리 생성"""
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    """캐시 키로 파일 경로 생성"""
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(_CACHE_DIR, f"{safe_key}.pkl")


def get_cache(key: str, ttl_minutes: float = 30):
    """
    캐시에서 값 조회

    Args:
        key: 캐시 키 (예: "stock_data_PLUG_6mo")
        ttl_minutes: 유효 시간 (분). 이 시간 초과 시 None 반환

    Returns:
        캐시된 값 또는 None (미스/만료)
    """
    path = _cache_path(key)
    if not os.path.exists(path):
        return None

    try:
        mtime = os.path.getmtime(path)
        age_minutes = (time.time() - mtime) / 60

        if age_minutes > ttl_minutes:
            logger.debug(f"캐시 만료: {key} ({age_minutes:.1f}분 경과)")
            return None

        with open(path, "rb") as f:
            data = pickle.load(f)
        logger.info(f"캐시 히트: {key} ({age_minutes:.1f}분 전)")
        return data

    except Exception as e:
        logger.debug(f"캐시 읽기 실패: {key} - {e}")
        return None


def set_cache(key: str, value):
    """
    캐시에 값 저장

    Args:
        key: 캐시 키
        value: 저장할 값 (pickle 가능해야 함)
    """
    _ensure_cache_dir()
    path = _cache_path(key)

    try:
        with open(path, "wb") as f:
            pickle.dump(value, f)
        logger.debug(f"캐시 저장: {key}")
    except Exception as e:
        logger.debug(f"캐시 저장 실패: {key} - {e}")


def cached_call(key: str, func, *args, ttl_minutes: float = 30, **kwargs):
    """
    함수 호출 결과를 캐싱하는 래퍼

    Args:
        key: 캐시 키
        func: 호출할 함수
        *args: 함수 인자
        ttl_minutes: 캐시 유효 시간 (분)
        **kwargs: 함수 키워드 인자

    Returns:
        함수 실행 결과 (캐시 또는 새 호출)
    """
    cached = get_cache(key, ttl_minutes)
    if cached is not None:
        return cached

    result = func(*args, **kwargs)
    set_cache(key, result)
    return result


def get_market_aware_ttl(base_ttl: float, market: str = "US",
                         now: datetime = None) -> float:
    """
    시장 상태에 따른 동적 TTL 반환

    장중에는 짧은 TTL로 최신 데이터 유지, 장마감/주말에는 긴 TTL로 불필요한 호출 방지.

    Args:
        base_ttl: 기본 TTL (분)
        market: "US" (NYSE 9:30-16:00 ET) 또는 "KR" (KRX 9:00-15:30 KST)
        now: 현재 시각 (테스트용, None이면 실제 시각)

    Returns:
        float: 조정된 TTL (분)
    """
    from common.config import get_config

    cache_cfg = get_config().get("cache", {})
    if not cache_cfg.get("market_aware_ttl", True):
        return base_ttl

    after_hours_mult = cache_cfg.get("after_hours_multiplier", 4)
    weekend_mult = cache_cfg.get("weekend_multiplier", 16)

    try:
        import pytz
    except ImportError:
        # pytz 없으면 기본 TTL 반환
        return base_ttl

    if now is None:
        now = datetime.now(pytz.UTC)

    if market == "KR":
        tz_str = cache_cfg.get("kr_market_hours", {}).get("tz", "Asia/Seoul")
        open_str = cache_cfg.get("kr_market_hours", {}).get("open", "09:00")
        close_str = cache_cfg.get("kr_market_hours", {}).get("close", "15:30")
    else:  # US
        tz_str = cache_cfg.get("us_market_hours", {}).get("tz", "US/Eastern")
        open_str = cache_cfg.get("us_market_hours", {}).get("open", "09:30")
        close_str = cache_cfg.get("us_market_hours", {}).get("close", "16:00")

    try:
        tz = pytz.timezone(tz_str)
        local_now = now.astimezone(tz)
    except Exception:
        return base_ttl

    # 주말 체크 (토=5, 일=6)
    if local_now.weekday() >= 5:
        return base_ttl * weekend_mult

    # 장 시간 파싱
    try:
        open_h, open_m = map(int, open_str.split(":"))
        close_h, close_m = map(int, close_str.split(":"))
        open_minutes = open_h * 60 + open_m
        close_minutes = close_h * 60 + close_m
        now_minutes = local_now.hour * 60 + local_now.minute

        if open_minutes <= now_minutes <= close_minutes:
            # 장중 → 기본 TTL
            return base_ttl
        else:
            # 장외 → 장마감 배율
            return base_ttl * after_hours_mult
    except Exception:
        return base_ttl


def detect_market(ticker: str) -> str:
    """
    티커에서 시장 감지

    Args:
        ticker: 종목 티커

    Returns:
        "KR" (한국) 또는 "US" (미국, 기본값)
    """
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KR"
    return "US"


def clear_ticker_cache(ticker: str) -> int:
    """
    특정 종목의 캐시만 삭제

    Args:
        ticker: 종목 티커 (예: "PLUG", "012450.KS")

    Returns:
        int: 삭제된 캐시 파일 수
    """
    # interval 조합 캐시 키 생성
    periods = ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
    intervals = ["1d", "1wk", "1mo"]
    keys = []
    for p in periods:
        for iv in intervals:
            keys.append(f"stock_data_{ticker}_{p}_{iv}")
        # 하위 호환: interval 없는 기존 캐시 키
        keys.append(f"stock_data_{ticker}_{p}")
    keys.extend([
        f"company_info_{ticker}",
        f"analyst_ratings_{ticker}",
        f"analyst_summary_{ticker}",
        f"news_{ticker}",
    ])
    count = 0
    for key in keys:
        path = _cache_path(key)
        if os.path.exists(path):
            try:
                os.remove(path)
                count += 1
                logger.debug(f"캐시 삭제: {key}")
            except OSError:
                pass
    if count > 0:
        logger.info(f"[{ticker}] 캐시 {count}개 삭제")
    return count


def clear_cache():
    """전체 캐시 삭제"""
    if not os.path.exists(_CACHE_DIR):
        return 0

    count = 0
    for f in os.listdir(_CACHE_DIR):
        if f.endswith(".pkl"):
            try:
                os.remove(os.path.join(_CACHE_DIR, f))
                count += 1
            except OSError:
                pass

    logger.info(f"캐시 삭제: {count}개 파일")
    return count


def cache_stats() -> dict:
    """캐시 통계 반환"""
    if not os.path.exists(_CACHE_DIR):
        return {"files": 0, "total_size_mb": 0, "oldest_minutes": 0}

    files = [f for f in os.listdir(_CACHE_DIR) if f.endswith(".pkl")]
    total_size = sum(
        os.path.getsize(os.path.join(_CACHE_DIR, f))
        for f in files
    )
    now = time.time()
    ages = [
        (now - os.path.getmtime(os.path.join(_CACHE_DIR, f))) / 60
        for f in files
    ]

    return {
        "files": len(files),
        "total_size_mb": total_size / (1024 * 1024),
        "oldest_minutes": max(ages) if ages else 0,
        "newest_minutes": min(ages) if ages else 0,
    }
