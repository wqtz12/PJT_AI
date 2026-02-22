"""
3분할 매수/매도 가격 계산 모듈

일목균형표 레벨 + ATR 기반으로 3단계 진입/청산 가격 산출.

3분할 매수 (Ichimoku 기반):
    1차 (보수적): 구름 하단 (CloudBottom) → 가장 안전한 진입점
    2차 (중간):   기준선 (Kijun-sen) → 중기 지지선 매수
    3차 (적극적): 전환선 (Tenkan-sen) → 단기 신호 확인 즉시 진입

3분할 매도 (Ichimoku 기반):
    1차 (보수적): 기준선 저항 (Kijun) → 1차 수익 실현
    2차 (중간):   구름 상단 (CloudTop) → 추세 저항선 도달
    3차 (적극적): ATR × 5배 확장 → 강한 추세 연장 기대

Ichimoku 없을 때 ATR 폴백:
    매수: [price - ATR×2, price - ATR×1, price]
    매도: [price + ATR×1.5, price + ATR×3, price + ATR×5]

빗각 반영:
    전환선 빗각 > 26° (강한 상승) → 3차 매수 가격을 현재가 근처로 상향
    기준선 빗각 < -10° (하락 전환) → 1차 매수 가격을 구름 하단 아래로 하향
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from common.config import get_config
from common.constants import ICHIMOKU_ANGLE_STRONG, ICHIMOKU_ANGLE_FLAT

logger = logging.getLogger(__name__)


def calc_split_buy_prices(
    price: float,
    atr: Optional[float],
    ichimoku: Optional[dict] = None,
    angle: Optional[dict] = None,
) -> list:
    """
    3분할 매수 가격 계산

    Args:
        price: 현재가
        atr: ATR 값 (변동성)
        ichimoku: 일목균형표 레벨 dict (선택)
            - cloud_bottom: 구름 하단
            - kijun: 기준선
            - tenkan: 전환선
        angle: 빗각 dict (선택)
            - tenkan_angle: 전환선 빗각
            - kijun_angle: 기준선 빗각

    Returns:
        [1차(보수적), 2차(중간), 3차(적극적)] 매수 가격
    """
    cfg = get_config().get("split_entry", {})
    atr_val = atr if atr and atr > 0 else price * 0.03  # ATR 없으면 3% 폴백

    if ichimoku and all(
        ichimoku.get(k) is not None and not (isinstance(ichimoku.get(k), float) and np.isnan(ichimoku.get(k)))
        for k in ["cloud_bottom", "kijun", "tenkan"]
    ):
        # 일목균형표 기반
        p1 = ichimoku["cloud_bottom"]    # 1차: 구름 하단
        p2 = ichimoku["kijun"]           # 2차: 기준선
        p3 = ichimoku["tenkan"]          # 3차: 전환선

        # 빗각 반영
        if angle:
            tenkan_angle = angle.get("tenkan_angle")
            kijun_angle = angle.get("kijun_angle")

            # 강한 상승 빗각 → 3차 매수를 현재가 근처로 (빨리 진입)
            if tenkan_angle is not None and tenkan_angle > ICHIMOKU_ANGLE_STRONG:
                p3 = max(p3, price - atr_val * 0.3)

            # 하락 빗각 → 1차 매수를 더 낮게 (신중)
            if kijun_angle is not None and kijun_angle < -ICHIMOKU_ANGLE_FLAT:
                p1 = min(p1, p1 - atr_val * 0.5)

        # 정렬 보장: p1 <= p2 <= p3
        prices = sorted([p1, p2, p3])
    else:
        # ATR 폴백
        p1 = price - atr_val * cfg.get("conservative_atr_mult", 2.0)
        p2 = price - atr_val * cfg.get("moderate_atr_mult", 1.0)
        p3 = price - atr_val * cfg.get("aggressive_atr_mult", 0.0)
        prices = [p1, p2, p3]

    # 음수 방지 및 반올림
    prices = [round(max(0.01, p), 2) for p in prices]

    return prices


def calc_split_sell_prices(
    price: float,
    atr: Optional[float],
    ichimoku: Optional[dict] = None,
    angle: Optional[dict] = None,
) -> list:
    """
    3분할 매도 가격 계산

    Args:
        price: 현재가
        atr: ATR 값 (변동성)
        ichimoku: 일목균형표 레벨 dict (선택)
            - cloud_top: 구름 상단
            - kijun: 기준선
            - tenkan: 전환선
        angle: 빗각 dict (선택)
            - tenkan_angle: 전환선 빗각
            - kijun_angle: 기준선 빗각

    Returns:
        [1차(보수적), 2차(중간), 3차(적극적)] 매도 가격
    """
    cfg = get_config().get("split_entry", {})
    atr_val = atr if atr and atr > 0 else price * 0.03

    if ichimoku and all(
        ichimoku.get(k) is not None and not (isinstance(ichimoku.get(k), float) and np.isnan(ichimoku.get(k)))
        for k in ["cloud_top", "kijun"]
    ):
        # 일목균형표 기반
        p1 = ichimoku["kijun"]           # 1차: 기준선 저항
        p2 = ichimoku["cloud_top"]       # 2차: 구름 상단
        p3 = price + atr_val * cfg.get("aggressive_sell_atr", 5.0)  # 3차: ATR 확장

        # 가격이 이미 기준선/구름 위에 있는 경우 보정
        if p1 <= price:
            p1 = price + atr_val * cfg.get("conservative_sell_atr", 1.5)
        if p2 <= price:
            p2 = price + atr_val * cfg.get("moderate_sell_atr", 3.0)

        # 빗각 반영
        if angle:
            tenkan_angle = angle.get("tenkan_angle")

            # 강한 상승 빗각 → 3차 매도 목표 상향 (추세 연장)
            if tenkan_angle is not None and tenkan_angle > ICHIMOKU_ANGLE_STRONG:
                p3 = price + atr_val * cfg.get("aggressive_sell_atr", 5.0) * 1.2

        # 정렬 보장: p1 <= p2 <= p3
        prices = sorted([p1, p2, p3])
    else:
        # ATR 폴백
        p1 = price + atr_val * cfg.get("conservative_sell_atr", 1.5)
        p2 = price + atr_val * cfg.get("moderate_sell_atr", 3.0)
        p3 = price + atr_val * cfg.get("aggressive_sell_atr", 5.0)
        prices = [p1, p2, p3]

    prices = [round(max(0.01, p), 2) for p in prices]
    return prices


def extract_ichimoku_levels(df: pd.DataFrame) -> Optional[dict]:
    """
    DataFrame에서 일목균형표 레벨 추출 (최신 행 기준)

    Returns:
        dict or None: 일목 레벨이 있으면 dict, 없으면 None
    """
    if df.empty:
        return None

    latest = df.iloc[-1]
    required = ["Ichimoku_Tenkan", "Ichimoku_Kijun", "Ichimoku_CloudTop", "Ichimoku_CloudBottom"]

    if not all(col in df.columns for col in required):
        return None

    levels = {}
    for col, key in [
        ("Ichimoku_Tenkan", "tenkan"),
        ("Ichimoku_Kijun", "kijun"),
        ("Ichimoku_CloudTop", "cloud_top"),
        ("Ichimoku_CloudBottom", "cloud_bottom"),
    ]:
        val = latest.get(col)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        levels[key] = float(val)

    return levels


def extract_ichimoku_angles(df: pd.DataFrame) -> Optional[dict]:
    """
    DataFrame에서 일목균형표 빗각 추출 (최신 행 기준)

    Returns:
        dict or None: 빗각이 있으면 dict, 없으면 None
    """
    if df.empty:
        return None

    latest = df.iloc[-1]
    angle_cols = ["Ichimoku_Tenkan_Angle", "Ichimoku_Kijun_Angle", "Ichimoku_SenkouA_Angle"]

    if not all(col in df.columns for col in angle_cols):
        return None

    angles = {}
    for col, key in [
        ("Ichimoku_Tenkan_Angle", "tenkan_angle"),
        ("Ichimoku_Kijun_Angle", "kijun_angle"),
        ("Ichimoku_SenkouA_Angle", "senkou_a_angle"),
    ]:
        val = latest.get(col)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            angles[key] = float(val)
        else:
            angles[key] = None

    return angles
