"""
시장별 통화 감지 및 가격/숫자 포맷 유틸리티

- 티커 기반 시장/통화 자동 감지
- 한국(KRW): 정수 가격, 조/억/만 스케일링
- 미국(USD): 소수점 2자리, T/B/M/K 스케일링
"""


def detect_currency(ticker: str) -> dict:
    """
    티커 코드로 통화 정보 감지

    Args:
        ticker: 종목 코드 (예: "005930.KS", "NVDA")

    Returns:
        dict: {symbol, code, decimals, market, scale_style}
    """
    t = str(ticker).upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return {
            "symbol": "₩",
            "code": "KRW",
            "decimals": 0,
            "market": "KR",
            "scale_style": "korean",
        }
    return {
        "symbol": "$",
        "code": "USD",
        "decimals": 2,
        "market": "US",
        "scale_style": "english",
    }


def is_korean_ticker(ticker: str) -> bool:
    """한국 종목 여부"""
    t = str(ticker).upper()
    return t.endswith(".KS") or t.endswith(".KQ")


def format_price(value, ticker: str = "") -> str:
    """
    시장에 맞는 가격 포맷

    한국: ₩50,000  /  미국: $177.19
    """
    if value is None or value == "N/A":
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)

    cur = detect_currency(ticker)
    sym = cur["symbol"]
    dec = cur["decimals"]

    if dec == 0:
        return f"{sym}{v:,.0f}"
    return f"{sym}{v:,.{dec}f}"


def format_number(num, ticker: str = "") -> str:
    """
    숫자를 읽기 쉬운 형태로 변환 (시장별 스케일링)

    한국: 500조, 1.2조, 3,456억, 780만
    미국: $1.50T, $2.30B, $45.00M, $1.2K
    """
    if isinstance(num, str) or num == "N/A":
        return str(num)
    if num is None:
        return "N/A"

    try:
        v = float(num)
    except (TypeError, ValueError):
        return str(num)

    cur = detect_currency(ticker)

    if cur["scale_style"] == "korean":
        return _format_number_korean(v, cur["symbol"])
    return _format_number_english(v, cur["symbol"])


def _format_number_korean(num, sym: str = "₩") -> str:
    """한국식 숫자 포맷 (조/억/만 단위)"""
    abs_num = abs(num)
    sign = "-" if num < 0 else ""

    if abs_num >= 1e12:
        return f"{sign}{sym}{abs_num/1e12:.1f}조"
    elif abs_num >= 1e8:
        return f"{sign}{sym}{abs_num/1e8:.0f}억"
    elif abs_num >= 1e4:
        return f"{sign}{sym}{abs_num/1e4:.0f}만"
    elif abs_num >= 1:
        return f"{sign}{sym}{abs_num:,.0f}"
    else:
        return f"{sign}{sym}{abs_num:.2f}"


def _format_number_english(num, sym: str = "$") -> str:
    """영문식 숫자 포맷 (T/B/M/K 단위)"""
    abs_num = abs(num)
    sign = "-" if num < 0 else ""

    if abs_num >= 1e12:
        return f"{sign}{sym}{abs_num/1e12:.2f}T"
    elif abs_num >= 1e9:
        return f"{sign}{sym}{abs_num/1e9:.2f}B"
    elif abs_num >= 1e6:
        return f"{sign}{sym}{abs_num/1e6:.2f}M"
    elif abs_num >= 1e3:
        return f"{sign}{sym}{abs_num/1e3:.1f}K"
    elif isinstance(num, float):
        return f"{sign}{sym}{abs_num:.2f}"
    else:
        return f"{sign}{sym}{abs_num}"


def get_price_decimals(ticker: str) -> int:
    """시장별 가격 소수점 자릿수"""
    return detect_currency(ticker)["decimals"]


def get_currency_symbol(ticker: str) -> str:
    """시장별 통화 기호"""
    return detect_currency(ticker)["symbol"]
