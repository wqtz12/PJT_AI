"""
데이터 수집 모듈 - yfinance 기반 주가/기업정보 수집
- 데이터 충분성 검증 (최소 행 수, NaN 비율, 기간 충족)
- 명시적 경고/에러 처리
- 설정값은 config.yaml에서 로드
"""
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from common.config import get_config

logger = logging.getLogger(__name__)

# config.yaml에서 데이터 설정 로드
_data_cfg = get_config().get("data", {})

# 기간별 최소 필요 행 수 (기술적 지표 계산에 필요한 최소 데이터)
MIN_ROWS = _data_cfg.get("min_rows", {
    "1mo": 15, "3mo": 40, "6mo": 80, "1y": 180, "2y": 350, "5y": 800,
})

# 필수 OHLCV 컬럼
REQUIRED_COLUMNS = _data_cfg.get("required_columns", ["Open", "High", "Low", "Close", "Volume"])

# NaN 허용 비율 (이 비율 초과 시 경고)
MAX_NAN_RATIO = _data_cfg.get("max_nan_ratio", 0.10)


class DataQualityWarning(UserWarning):
    """데이터 품질 경고"""
    pass


class InsufficientDataError(ValueError):
    """데이터 부족 에러"""
    pass


def validate_dataframe(df: pd.DataFrame, ticker: str, period: str,
                       interval: str = "1d") -> dict:
    """
    데이터프레임 품질 검증

    Args:
        df: OHLCV 데이터프레임
        ticker: 종목 코드
        period: 수집 기간
        interval: 데이터 간격 (1d/1wk/1mo)

    Returns:
        dict: {
            "valid": bool,
            "warnings": list[str],
            "errors": list[str],
            "stats": dict
        }
    """
    result = {"valid": True, "warnings": [], "errors": [], "stats": {}}

    # 1) 빈 데이터프레임 체크
    if df.empty:
        result["valid"] = False
        result["errors"].append(f"[{ticker}] 데이터가 비어있습니다.")
        return result

    # 2) 필수 컬럼 존재 여부
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        result["valid"] = False
        result["errors"].append(f"[{ticker}] 필수 컬럼 누락: {missing_cols}")
        return result

    # 3) 최소 행 수 검증 (interval에 따라 조정)
    min_rows = MIN_ROWS.get(period, 15)
    min_rows = _adjust_min_rows(min_rows, interval)
    actual_rows = len(df)
    result["stats"]["rows"] = actual_rows
    result["stats"]["min_required"] = min_rows

    if actual_rows < min_rows:
        result["valid"] = False
        result["errors"].append(
            f"[{ticker}] 데이터 부족: {actual_rows}행 (최소 {min_rows}행 필요, period={period})"
        )

    # 4) OHLCV 컬럼별 NaN 비율 검사
    nan_report = {}
    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            nan_ratio = nan_count / len(df) if len(df) > 0 else 0
            nan_report[col] = {"count": int(nan_count), "ratio": round(nan_ratio, 4)}
            if nan_ratio > MAX_NAN_RATIO:
                result["warnings"].append(
                    f"[{ticker}] '{col}' 컬럼 NaN 비율 높음: {nan_ratio:.1%} ({nan_count}/{len(df)})"
                )
    result["stats"]["nan_report"] = nan_report

    # 5) 데이터 기간(날짜 범위) 검증
    if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
        date_range = df.index.max() - df.index.min()
        result["stats"]["date_range_days"] = date_range.days
        result["stats"]["start_date"] = str(df.index.min().date())
        result["stats"]["end_date"] = str(df.index.max().date())

        # 최신 데이터가 5영업일 이상 오래된 경우 경고
        days_since_last = (pd.Timestamp.now(tz=df.index.tz) - df.index.max()).days
        if days_since_last > 5:
            result["warnings"].append(
                f"[{ticker}] 최신 데이터가 {days_since_last}일 전 ({df.index.max().date()})"
            )
        result["stats"]["days_since_last"] = days_since_last

    # 6) Close 가격 유효성 (0 이하 가격 감지)
    invalid_prices = (df["Close"] <= 0).sum()
    if invalid_prices > 0:
        result["warnings"].append(
            f"[{ticker}] 유효하지 않은 종가 {invalid_prices}건 (0 이하)"
        )
    result["stats"]["invalid_prices"] = int(invalid_prices)

    # 7) Volume 0 비율 (유동성 경고)
    zero_vol = (df["Volume"] == 0).sum()
    zero_vol_ratio = zero_vol / len(df) if len(df) > 0 else 0
    if zero_vol_ratio > 0.2:
        result["warnings"].append(
            f"[{ticker}] 거래량 0인 날 비율 높음: {zero_vol_ratio:.1%} ({zero_vol}일)"
        )
    result["stats"]["zero_volume_days"] = int(zero_vol)

    return result


def _adjust_min_rows(min_rows: int, interval: str) -> int:
    """interval에 따라 최소 행 수 조정"""
    if interval == "1wk":
        return max(min_rows // 5, 5)  # 주봉: 1/5
    elif interval == "1mo":
        return max(min_rows // 21, 3)  # 월봉: 1/21
    return min_rows  # 일봉: 그대로


def fetch_stock_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    주가 데이터 수집 (OHLCV) + 품질 검증

    Args:
        ticker: 종목 코드
        period: 수집 기간 (1mo/3mo/6mo/1y/2y/5y)
        interval: 데이터 간격 (1d/1wk/1mo, 기본: 1d)

    Raises:
        InsufficientDataError: 데이터가 부족하거나 필수 조건 미충족 시
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)

    # 데이터 품질 검증
    validation = validate_dataframe(df, ticker, period, interval=interval)

    # 경고 로깅
    for warn in validation["warnings"]:
        logger.warning(warn)

    # 에러 시 예외 발생
    if not validation["valid"]:
        error_msg = " | ".join(validation["errors"])
        raise InsufficientDataError(error_msg)

    # 검증 통계 로깅
    stats = validation["stats"]
    logger.info(
        f"[{ticker}] 데이터 검증 통과: {stats.get('rows', 0)}행, "
        f"{stats.get('start_date', '?')} ~ {stats.get('end_date', '?')}"
    )

    return df


def _safe_numeric(value, default=None):
    """숫자값 안전 추출 - None/NaN/"N/A" 대신 명시적 None 반환"""
    if value is None:
        return default
    if isinstance(value, str):
        return default
    if isinstance(value, (int, float)):
        if np.isnan(value) or np.isinf(value):
            return default
        return value
    return default


def fetch_company_info(ticker: str) -> dict:
    """
    기업 기본 정보 수집 - 명시적 None/값 구분

    숫자 필드: 값이 없으면 None (0으로 마스킹하지 않음)
    문자 필드: 값이 없으면 None
    """
    stock = yf.Ticker(ticker)
    try:
        info = stock.info
    except Exception as e:
        logger.error(f"[{ticker}] 기업정보 수집 실패: {e}")
        info = {}

    result = {
        "이름": info.get("shortName") or info.get("longName") or ticker,
        "섹터": info.get("sector") or None,
        "산업": info.get("industry") or None,
        "시가총액": _safe_numeric(info.get("marketCap")),
        "52주_최고": _safe_numeric(info.get("fiftyTwoWeekHigh")),
        "52주_최저": _safe_numeric(info.get("fiftyTwoWeekLow")),
        "PER": _safe_numeric(info.get("trailingPE")),
        "PBR": _safe_numeric(info.get("priceToBook")),
        "EPS": _safe_numeric(info.get("trailingEps")),
        "배당수익률": _safe_numeric(info.get("dividendYield")),
        "베타": _safe_numeric(info.get("beta")),
        "애널리스트_목표가": _safe_numeric(info.get("targetMeanPrice")),
        "추천": info.get("recommendationKey") or None,
        "총매출": _safe_numeric(info.get("totalRevenue")),
        "영업이익": _safe_numeric(info.get("operatingIncome")),
        "부채비율": _safe_numeric(info.get("debtToEquity")),
        "현금": _safe_numeric(info.get("totalCash")),
        "직원수": _safe_numeric(info.get("fullTimeEmployees")),
        "홈페이지": info.get("website") or None,
        "설명": info.get("longBusinessSummary") or None,
    }

    # 수집된 필드 중 None 비율 로깅
    none_count = sum(1 for v in result.values() if v is None)
    total = len(result)
    if none_count > total * 0.5:
        logger.warning(f"[{ticker}] 기업정보 누락 비율 높음: {none_count}/{total} 필드 미수집")

    return result


def validate_price_freshness(df: pd.DataFrame, ticker: str,
                              company_info: dict = None,
                              threshold_pct: float = 5.0) -> dict:
    """
    히스토리 종가 vs 실시간 가격 교차검증

    yfinance history()의 마지막 Close와 info의 currentPrice를 비교하여
    가격 괴리를 감지합니다. 괴리율이 threshold_pct 이상이면 경고합니다.

    Args:
        df: OHLCV 데이터프레임
        ticker: 종목 티커
        company_info: 이미 수집된 기업정보 (있으면 재사용)
        threshold_pct: 괴리율 경고 임계값 (%, 기본 5.0)

    Returns:
        dict: {
            "valid": bool,
            "history_price": float,
            "realtime_price": float | None,
            "discrepancy_pct": float | None,
            "warning": str | None,
            "stale_days": int
        }
    """
    result = {
        "valid": True,
        "history_price": None,
        "realtime_price": None,
        "discrepancy_pct": None,
        "warning": None,
        "stale_days": 0,
    }

    # 히스토리 가격 추출
    if df.empty:
        result["valid"] = False
        result["warning"] = f"[{ticker}] 히스토리 데이터 비어있음"
        return result

    history_price = df.iloc[-1]["Close"]
    result["history_price"] = float(history_price)

    # 최신 데이터 기간 확인 (stale 체크)
    try:
        last_date = df.index[-1]
        now = pd.Timestamp.now(tz=last_date.tzinfo) if last_date.tzinfo else pd.Timestamp.now()
        stale_days = (now - last_date).days
        result["stale_days"] = stale_days

        stale_cfg = get_config().get("price_validation", {}).get("stale_days_warning", 3)
        if stale_days > stale_cfg:
            result["warning"] = (
                f"[{ticker}] 최신 데이터가 {stale_days}일 전 "
                f"({last_date.strftime('%Y-%m-%d')}) — stale 가능성"
            )
    except Exception:
        pass

    # 실시간 가격 추출 (yfinance info)
    realtime_price = None
    try:
        if company_info:
            # company_info에서 먼저 시도 (이미 수집된 데이터 재사용)
            for key in ("현재가", "regularMarketPrice", "currentPrice"):
                val = company_info.get(key)
                if val is not None and isinstance(val, (int, float)) and val > 0:
                    realtime_price = float(val)
                    break

        if realtime_price is None:
            # 직접 yfinance info 조회
            stock = yf.Ticker(ticker)
            info = stock.info
            for key in ("currentPrice", "regularMarketPrice",
                        "regularMarketPreviousClose", "previousClose"):
                val = info.get(key)
                if val is not None:
                    numeric = _safe_numeric(val)
                    if numeric is not None and numeric > 0:
                        realtime_price = float(numeric)
                        break
    except Exception as e:
        logger.debug(f"[{ticker}] 실시간 가격 조회 실패: {e}")

    if realtime_price is None:
        # 실시간 가격 미가용 (한국주식 등) → 검증 스킵, valid=True 유지
        logger.debug(f"[{ticker}] 실시간 가격 미가용 → 교차검증 스킵")
        return result

    result["realtime_price"] = realtime_price

    # 괴리율 계산
    if history_price > 0:
        discrepancy = abs(realtime_price - history_price) / history_price * 100
        result["discrepancy_pct"] = round(discrepancy, 2)

        if discrepancy > threshold_pct:
            result["valid"] = False
            result["warning"] = (
                f"[{ticker}] 가격 괴리 {discrepancy:.1f}%: "
                f"히스토리 종가 ${history_price:,.2f} vs "
                f"실시간 ${realtime_price:,.2f} "
                f"(임계값 {threshold_pct}%)"
            )
            logger.warning(result["warning"])

    return result


def fetch_financials(ticker: str) -> dict:
    """재무제표 요약 데이터"""
    stock = yf.Ticker(ticker)
    result = {}

    income = stock.quarterly_income_stmt
    if not income.empty:
        result["분기_손익계산서"] = income

    balance = stock.quarterly_balance_sheet
    if not balance.empty:
        result["분기_재무상태표"] = balance

    cashflow = stock.quarterly_cashflow
    if not cashflow.empty:
        result["분기_현금흐름표"] = cashflow

    return result


def fetch_multi_period_data(ticker: str) -> dict:
    """다중 기간 주가 데이터"""
    periods = {
        "1개월": "1mo",
        "3개월": "3mo",
        "6개월": "6mo",
        "1년": "1y",
        "2년": "2y",
        "5년": "5y",
    }
    data = {}
    for label, period in periods.items():
        try:
            df = fetch_stock_data(ticker, period)
            data[label] = df
        except InsufficientDataError as e:
            logger.warning(f"[{ticker}] {label} 데이터 부족: {e}")
        except Exception as e:
            logger.error(f"[{ticker}] {label} 데이터 수집 실패: {e}")
    return data
