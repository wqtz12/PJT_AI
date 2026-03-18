"""
기술적 분석 모듈 - 이동평균, RSI, MACD, 볼린저밴드, 스토캐스틱, ATR
- 설정값은 config.yaml에서 로드
"""
import pandas as pd
import numpy as np
from math import atan2, degrees
from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator, IchimokuIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
from common.config import get_config

# config.yaml에서 지표 설정 로드
_ind_cfg = get_config().get("indicators", {})
_SMA_WINDOWS = _ind_cfg.get("sma_windows", [5, 20, 60, 120])
_EMA_WINDOWS = _ind_cfg.get("ema_windows", [12, 26])
_RSI_WINDOW = _ind_cfg.get("rsi_window", 14)
_BB_WINDOW = _ind_cfg.get("bb_window", 20)
_BB_STD_DEV = _ind_cfg.get("bb_std_dev", 2)
_ATR_WINDOW = _ind_cfg.get("atr_window", 14)
_ADX_WINDOW = _ind_cfg.get("adx_window", 14)

# 일목균형표 설정
_ichimoku_cfg = _ind_cfg.get("ichimoku", {})
_TENKAN_WINDOW = _ichimoku_cfg.get("tenkan_window", 9)
_KIJUN_WINDOW = _ichimoku_cfg.get("kijun_window", 26)
_SENKOU_B_WINDOW = _ichimoku_cfg.get("senkou_b_window", 52)
_CHIKOU_SHIFT = _ichimoku_cfg.get("chikou_shift", 26)

# 빗각 설정
_thresh_cfg = get_config().get("thresholds", {}).get("ichimoku", {})
_ANGLE_WINDOW = _thresh_cfg.get("angle_window", 5)


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """이동평균선 (SMA/EMA - 윈도우는 config에서 로드)"""
    for window in _SMA_WINDOWS:
        sma = SMAIndicator(close=df["Close"], window=window)
        df[f"SMA_{window}"] = sma.sma_indicator()

    for window in _EMA_WINDOWS:
        ema = EMAIndicator(close=df["Close"], window=window)
        df[f"EMA_{window}"] = ema.ema_indicator()

    return df


def add_rsi(df: pd.DataFrame, window: int = None) -> pd.DataFrame:
    """RSI (Relative Strength Index)"""
    window = window or _RSI_WINDOW
    rsi = RSIIndicator(close=df["Close"], window=window)
    df["RSI"] = rsi.rsi()
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """MACD (Moving Average Convergence Divergence)"""
    macd = MACD(close=df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()
    return df


def add_bollinger_bands(df: pd.DataFrame, window: int = None) -> pd.DataFrame:
    """볼린저 밴드"""
    window = window or _BB_WINDOW
    bb = BollingerBands(close=df["Close"], window=window, window_dev=_BB_STD_DEV)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Middle"] = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Width"] = bb.bollinger_wband()
    df["BB_Pct"] = bb.bollinger_pband()
    return df


def add_stochastic(df: pd.DataFrame) -> pd.DataFrame:
    """스토캐스틱 오실레이터"""
    stoch = StochasticOscillator(
        high=df["High"], low=df["Low"], close=df["Close"]
    )
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()
    return df


def add_atr(df: pd.DataFrame, window: int = None) -> pd.DataFrame:
    """ATR (Average True Range) - 변동성 지표"""
    window = window or _ATR_WINDOW
    atr = AverageTrueRange(
        high=df["High"], low=df["Low"], close=df["Close"], window=window
    )
    df["ATR"] = atr.average_true_range()
    return df


def add_adx(df: pd.DataFrame, window: int = None) -> pd.DataFrame:
    """ADX (Average Directional Index) - 추세 강도"""
    window = window or _ADX_WINDOW
    adx = ADXIndicator(
        high=df["High"], low=df["Low"], close=df["Close"], window=window
    )
    df["ADX"] = adx.adx()
    df["ADX_Pos"] = adx.adx_pos()
    df["ADX_Neg"] = adx.adx_neg()
    return df


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """OBV (On Balance Volume)"""
    obv = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"])
    df["OBV"] = obv.on_balance_volume()
    return df


def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """일목균형표 (Ichimoku Kinko Hyo) - 7개 컬럼 생성

    - Ichimoku_Tenkan: 전환선 (9일)
    - Ichimoku_Kijun: 기준선 (26일)
    - Ichimoku_SenkouA: 선행스팬A (전환선+기준선)/2
    - Ichimoku_SenkouB: 선행스팬B (52일)
    - Ichimoku_Chikou: 후행스팬 (26일 후행)
    - Ichimoku_CloudTop: 구름 상단
    - Ichimoku_CloudBottom: 구름 하단
    """
    ichimoku = IchimokuIndicator(
        high=df["High"],
        low=df["Low"],
        window1=_TENKAN_WINDOW,
        window2=_KIJUN_WINDOW,
        window3=_SENKOU_B_WINDOW,
    )

    df["Ichimoku_Tenkan"] = ichimoku.ichimoku_conversion_line()
    df["Ichimoku_Kijun"] = ichimoku.ichimoku_base_line()
    df["Ichimoku_SenkouA"] = ichimoku.ichimoku_a()
    df["Ichimoku_SenkouB"] = ichimoku.ichimoku_b()

    # 후행스팬: 현재 종가를 26일 뒤로 시프트 (과거 비교용 → 음수 shift)
    df["Ichimoku_Chikou"] = df["Close"].shift(-_CHIKOU_SHIFT)

    # 구름 상단/하단 (현재 시점 기준)
    senkou_a = df["Ichimoku_SenkouA"]
    senkou_b = df["Ichimoku_SenkouB"]
    df["Ichimoku_CloudTop"] = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
    df["Ichimoku_CloudBottom"] = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)

    return df


def add_ichimoku_angles(df: pd.DataFrame) -> pd.DataFrame:
    """일목균형표 빗각(기울기) 계산 - 3개 컬럼 생성

    빗각 = degrees(atan2(변화율%, window))
    - % 변화로 정규화하여 가격 수준에 무관한 각도
    - |angle| > 26° → 강한 추세
    - |angle| < 10° → 횡보/전환 임박

    - Ichimoku_Tenkan_Angle: 전환선 빗각 (단기 모멘텀)
    - Ichimoku_Kijun_Angle: 기준선 빗각 (중기 추세)
    - Ichimoku_SenkouA_Angle: 선행스팬A 빗각 (구름 방향)
    """
    window = _ANGLE_WINDOW

    for col_src, col_dst in [
        ("Ichimoku_Tenkan", "Ichimoku_Tenkan_Angle"),
        ("Ichimoku_Kijun", "Ichimoku_Kijun_Angle"),
        ("Ichimoku_SenkouA", "Ichimoku_SenkouA_Angle"),
    ]:
        if col_src not in df.columns:
            df[col_dst] = np.nan
            continue

        angles = pd.Series(np.nan, index=df.index)
        values = df[col_src]

        for i in range(window, len(df)):
            prev_val = values.iloc[i - window]
            curr_val = values.iloc[i]
            if pd.notna(prev_val) and pd.notna(curr_val) and prev_val != 0:
                change_pct = (curr_val - prev_val) / prev_val * 100
                angles.iloc[i] = degrees(atan2(change_pct, window))
            # else: stays NaN

        df[col_dst] = angles

    return df


def run_full_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """전체 기술적 지표 적용 - 데이터 부족 시 안전 스킵 (min_rows는 config에서 로드)"""
    import logging
    logger = logging.getLogger(__name__)
    n = len(df)

    # config에서 지표별 최소 행 수 로드
    _mr = _ind_cfg.get("min_rows_per_indicator", {})

    # 각 지표 적용 (필요 최소 행 수 체크 후 안전 적용)
    indicators = [
        ("이동평균", add_moving_averages, _mr.get("moving_averages", 5)),
        ("RSI", add_rsi, _mr.get("rsi", 15)),
        ("MACD", add_macd, _mr.get("macd", 27)),
        ("볼린저밴드", add_bollinger_bands, _mr.get("bollinger_bands", 21)),
        ("스토캐스틱", add_stochastic, _mr.get("stochastic", 15)),
        ("ATR", add_atr, _mr.get("atr", 15)),
        ("ADX", add_adx, _mr.get("adx", 30)),
        ("OBV", add_obv, _mr.get("obv", 2)),
        ("일목균형표", add_ichimoku, _mr.get("ichimoku", 53)),
        ("일목빗각", add_ichimoku_angles, _mr.get("ichimoku_angles", 53)),
    ]

    for name, func, min_rows in indicators:
        if n >= min_rows:
            try:
                df = func(df)
            except Exception as e:
                logger.warning(f"[{name}] 지표 계산 실패 (rows={n}): {e}")
        else:
            logger.info(f"[{name}] 데이터 부족으로 스킵 ({n}/{min_rows}행)")

    return df


def _get_indicator(series_row, name: str):
    """지표값 안전 추출 - NaN이면 None 반환 (.get() 기본값 대체)"""
    val = series_row.get(name, None)
    if val is None:
        return None
    try:
        import numpy as _np
        if _np.isnan(val) or _np.isinf(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def generate_signals(df: pd.DataFrame) -> dict:
    """매매 신호 종합 판단 - 명시적 NaN 처리 (기본값 마스킹 제거)"""
    if df.empty:
        return {"종합판단": "데이터 부족"}

    latest = df.iloc[-1]
    signals = {}
    unavailable = []  # 계산 불가 지표 추적

    # RSI 신호
    rsi = _get_indicator(latest, "RSI")
    if rsi is not None:
        if rsi < 30:
            signals["RSI"] = ("과매도 🟢", "매수 신호")
        elif rsi > 70:
            signals["RSI"] = ("과매수 🔴", "매도 신호")
        else:
            signals["RSI"] = (f"{rsi:.1f}", "중립")
    else:
        unavailable.append("RSI")

    # MACD 신호
    macd_val = _get_indicator(latest, "MACD")
    macd_sig = _get_indicator(latest, "MACD_Signal")
    if macd_val is not None and macd_sig is not None:
        if macd_val > macd_sig:
            signals["MACD"] = ("골든크로스 🟢", "매수 신호")
        else:
            signals["MACD"] = ("데드크로스 🔴", "매도 신호")
    else:
        unavailable.append("MACD")

    # 이동평균 배열 (정배열/역배열)
    sma5 = _get_indicator(latest, "SMA_5")
    sma20 = _get_indicator(latest, "SMA_20")
    sma60 = _get_indicator(latest, "SMA_60")
    price = latest["Close"]

    if all(v is not None for v in [sma5, sma20, sma60]):
        if price > sma5 > sma20 > sma60:
            signals["이동평균"] = ("정배열 🟢", "강한 상승 추세")
        elif price < sma5 < sma20 < sma60:
            signals["이동평균"] = ("역배열 🔴", "강한 하락 추세")
        else:
            signals["이동평균"] = ("혼조 🟡", "방향성 모호")
    else:
        unavailable.append("이동평균")

    # 볼린저 밴드 위치
    bb_pct = _get_indicator(latest, "BB_Pct")
    if bb_pct is not None:
        if bb_pct < 0:
            signals["볼린저밴드"] = ("하단 이탈 🟢", "반등 가능성")
        elif bb_pct > 1:
            signals["볼린저밴드"] = ("상단 이탈 🔴", "조정 가능성")
        else:
            signals["볼린저밴드"] = (f"{bb_pct:.2f}", "밴드 내 정상")
    else:
        unavailable.append("볼린저밴드")

    # 스토캐스틱
    stoch_k = _get_indicator(latest, "Stoch_K")
    stoch_d = _get_indicator(latest, "Stoch_D")
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_k > stoch_d:
            signals["스토캐스틱"] = ("과매도 반전 🟢", "매수 신호")
        elif stoch_k > 80 and stoch_k < stoch_d:
            signals["스토캐스틱"] = ("과매수 반전 🔴", "매도 신호")
        else:
            signals["스토캐스틱"] = (f"K:{stoch_k:.1f}", "중립")
    else:
        unavailable.append("스토캐스틱")

    # ADX 추세 강도
    adx_val = _get_indicator(latest, "ADX")
    if adx_val is not None:
        if adx_val > 25:
            signals["ADX"] = (f"{adx_val:.1f} (강한 추세)", "추세 진행 중")
        else:
            signals["ADX"] = (f"{adx_val:.1f} (약한 추세)", "횡보 구간")
    else:
        unavailable.append("ADX")

    # 일목균형표 신호
    tenkan = _get_indicator(latest, "Ichimoku_Tenkan")
    kijun = _get_indicator(latest, "Ichimoku_Kijun")
    cloud_top = _get_indicator(latest, "Ichimoku_CloudTop")
    cloud_bottom = _get_indicator(latest, "Ichimoku_CloudBottom")

    if all(v is not None for v in [tenkan, kijun, cloud_top, cloud_bottom]):
        if price > cloud_top and tenkan > kijun:
            signals["일목균형표"] = ("구름 위 + TK↑ 🟢", "강한 상승 추세")
        elif price < cloud_bottom and tenkan < kijun:
            signals["일목균형표"] = ("구름 아래 + TK↓ 🔴", "강한 하락 추세")
        elif price > cloud_top:
            signals["일목균형표"] = ("구름 위 🟢", "상승 추세")
        elif price < cloud_bottom:
            signals["일목균형표"] = ("구름 아래 🔴", "하락 추세")
        else:
            signals["일목균형표"] = ("구름 내 🟡", "방향성 모호")
    else:
        unavailable.append("일목균형표")

    # 계산 불가 지표 기록
    if unavailable:
        signals["미계산지표"] = (", ".join(unavailable), "데이터 부족으로 미계산")

    # 종합 점수 계산 (미계산 지표 제외)
    scorable = {k: v for k, v in signals.items() if k not in ("종합판단", "미계산지표")}
    buy_count = sum(1 for v in scorable.values() if "매수" in v[1] or "상승" in v[1] or "반등" in v[1])
    sell_count = sum(1 for v in scorable.values() if "매도" in v[1] or "하락" in v[1] or "조정" in v[1])
    total = len(scorable)

    if total == 0:
        signals["종합판단"] = "판단 불가 (지표 데이터 부족)"
    elif buy_count > sell_count + 1:
        signals["종합판단"] = f"매수 우세 ({buy_count}/{total})"
    elif sell_count > buy_count + 1:
        signals["종합판단"] = f"매도 우세 ({sell_count}/{total})"
    else:
        signals["종합판단"] = f"중립/관망 (매수:{buy_count} 매도:{sell_count})"

    return signals
