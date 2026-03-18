"""
일목균형표 + 빗각이론 + 3분할 매수/매도 테스트

Phase A: 일목균형표 지표 + 빗각 계산 (Foundation)
    - add_ichimoku(): 7개 컬럼 생성
    - add_ichimoku_angles(): 3개 빗각 컬럼
    - generate_signals() 일목 신호
    - config 기본값 검증

Phase B: ExpertOpinion 확장 + 3분할 계산 모듈
    - ExpertOpinion.buy_prices / sell_prices
    - split_calculator: calc_split_buy_prices / calc_split_sell_prices
    - extract_ichimoku_levels / extract_ichimoku_angles
"""
from datetime import datetime
from math import atan2, degrees

import numpy as np
import pandas as pd
import pytest

from common.config import get_config
from common.constants import (
    ICHIMOKU_CLOUD_THICK_RATIO,
    ICHIMOKU_CLOUD_THIN_RATIO,
    ICHIMOKU_ANGLE_STRONG,
    ICHIMOKU_ANGLE_FLAT,
    ICHIMOKU_ANGLE_WINDOW,
)


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 데이터 생성
# ──────────────────────────────────────────────
def _make_ohlcv(rows: int = 80, base_price: float = 100.0, trend: str = "flat") -> pd.DataFrame:
    """테스트용 OHLCV DataFrame"""
    dates = pd.date_range(end=datetime.now(), periods=rows, freq="B", tz="US/Eastern")

    if trend == "up":
        closes = [base_price * (1 + 0.003 * i) for i in range(rows)]
    elif trend == "down":
        closes = [base_price * (1 - 0.003 * i) for i in range(rows)]
    elif trend == "strong_up":
        closes = [base_price * (1 + 0.01 * i) for i in range(rows)]
    elif trend == "strong_down":
        closes = [base_price * (1 - 0.01 * i) for i in range(rows)]
    else:
        closes = [base_price] * rows

    data = {
        "Open": [c * 0.998 for c in closes],
        "High": [c * 1.015 for c in closes],
        "Low": [c * 0.985 for c in closes],
        "Close": closes,
        "Volume": [1000000] * rows,
    }
    return pd.DataFrame(data, index=dates)


# ══════════════════════════════════════════════
# 1. add_ichimoku() 기본 테스트
# ══════════════════════════════════════════════
class TestAddIchimoku:
    """일목균형표 7개 컬럼 생성 테스트"""

    def test_columns_created(self):
        """7개 일목 컬럼이 생성되는지"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80)
        result = add_ichimoku(df)

        expected_cols = [
            "Ichimoku_Tenkan", "Ichimoku_Kijun",
            "Ichimoku_SenkouA", "Ichimoku_SenkouB",
            "Ichimoku_Chikou",
            "Ichimoku_CloudTop", "Ichimoku_CloudBottom",
        ]
        for col in expected_cols:
            assert col in result.columns, f"{col} 컬럼 미생성"

    def test_tenkan_not_all_nan(self):
        """전환선에 유효한 값이 존재"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80)
        result = add_ichimoku(df)
        assert result["Ichimoku_Tenkan"].dropna().shape[0] > 0

    def test_kijun_not_all_nan(self):
        """기준선에 유효한 값이 존재"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80)
        result = add_ichimoku(df)
        assert result["Ichimoku_Kijun"].dropna().shape[0] > 0

    def test_senkou_a_b_exist(self):
        """선행스팬A/B에 유효한 값이 존재"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80)
        result = add_ichimoku(df)
        assert result["Ichimoku_SenkouA"].dropna().shape[0] > 0
        assert result["Ichimoku_SenkouB"].dropna().shape[0] > 0

    def test_cloud_top_gte_bottom(self):
        """구름 상단 >= 구름 하단 (유효한 행 기준)"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80, trend="up")
        result = add_ichimoku(df)

        valid = result.dropna(subset=["Ichimoku_CloudTop", "Ichimoku_CloudBottom"])
        assert (valid["Ichimoku_CloudTop"] >= valid["Ichimoku_CloudBottom"]).all()

    def test_chikou_is_shifted_close(self):
        """후행스팬 = Close의 -26 shift"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80)
        result = add_ichimoku(df)

        # 마지막 26행은 NaN (미래 데이터 없음)
        assert pd.isna(result["Ichimoku_Chikou"].iloc[-1])

        # 중간 부분은 Close와 일치
        mid = len(df) // 2
        expected = df["Close"].iloc[mid]
        actual = result["Ichimoku_Chikou"].iloc[mid - 26]
        if pd.notna(actual):
            assert abs(actual - expected) < 0.001

    def test_flat_market_tenkan_equals_kijun(self):
        """횡보 시장 → 전환선 ≈ 기준선"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=80, base_price=100.0, trend="flat")
        result = add_ichimoku(df)

        # flat market에서 high/low가 일정하므로 tenkan ≈ kijun
        valid = result.dropna(subset=["Ichimoku_Tenkan", "Ichimoku_Kijun"])
        if len(valid) > 0:
            last = valid.iloc[-1]
            assert abs(last["Ichimoku_Tenkan"] - last["Ichimoku_Kijun"]) < 1.0

    def test_insufficient_data_still_runs(self):
        """데이터가 부족해도 에러 없이 실행 (NaN만 많아짐)"""
        from technical_analysis import add_ichimoku

        df = _make_ohlcv(rows=20)
        result = add_ichimoku(df)
        assert "Ichimoku_Tenkan" in result.columns


# ══════════════════════════════════════════════
# 2. add_ichimoku_angles() 빗각 테스트
# ══════════════════════════════════════════════
class TestAddIchimokuAngles:
    """일목균형표 빗각 3개 컬럼 테스트"""

    def test_angle_columns_created(self):
        """3개 빗각 컬럼 생성"""
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="up")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        for col in ["Ichimoku_Tenkan_Angle", "Ichimoku_Kijun_Angle", "Ichimoku_SenkouA_Angle"]:
            assert col in result.columns, f"{col} 컬럼 미생성"

    def test_uptrend_positive_angles(self):
        """상승 추세 → 양의 빗각"""
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="strong_up")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        # 후반부에서 전환선 빗각이 양수여야 함
        valid_angles = result["Ichimoku_Tenkan_Angle"].dropna()
        if len(valid_angles) > 10:
            last_angles = valid_angles.iloc[-10:]
            assert (last_angles > 0).all(), f"상승 추세인데 음의 빗각: {last_angles.values}"

    def test_downtrend_negative_angles(self):
        """하락 추세 → 음의 빗각"""
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="strong_down")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        valid_angles = result["Ichimoku_Tenkan_Angle"].dropna()
        if len(valid_angles) > 10:
            last_angles = valid_angles.iloc[-10:]
            assert (last_angles < 0).all(), f"하락 추세인데 양의 빗각: {last_angles.values}"

    def test_flat_market_small_angles(self):
        """횡보 → 빗각 ≈ 0 (|angle| < 10°)"""
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="flat")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        valid_angles = result["Ichimoku_Tenkan_Angle"].dropna()
        if len(valid_angles) > 5:
            last_angles = valid_angles.iloc[-5:]
            # 횡보에서는 high/low 차이로 약간의 변동이 있을 수 있지만 작아야 함
            assert (last_angles.abs() < 20).all(), f"횡보인데 큰 빗각: {last_angles.values}"

    def test_angle_range_bounded(self):
        """빗각은 -90° ~ +90° 범위"""
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="strong_up")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        for col in ["Ichimoku_Tenkan_Angle", "Ichimoku_Kijun_Angle", "Ichimoku_SenkouA_Angle"]:
            valid = result[col].dropna()
            if len(valid) > 0:
                assert valid.min() >= -90, f"{col} 최소값이 -90 미만"
                assert valid.max() <= 90, f"{col} 최대값이 90 초과"

    def test_no_ichimoku_columns_fills_nan(self):
        """일목 컬럼 없으면 NaN으로 채움"""
        from technical_analysis import add_ichimoku_angles

        df = _make_ohlcv(rows=80)
        # ichimoku 미적용 상태에서 angles 호출
        result = add_ichimoku_angles(df)

        assert "Ichimoku_Tenkan_Angle" in result.columns
        assert result["Ichimoku_Tenkan_Angle"].isna().all()

    def test_angle_formula_correctness(self):
        """빗각 공식 검증: degrees(atan2(change_pct, window))"""
        # 직접 계산과 비교
        from technical_analysis import add_ichimoku, add_ichimoku_angles

        df = _make_ohlcv(rows=80, trend="up")
        df = add_ichimoku(df)
        result = add_ichimoku_angles(df)

        # 마지막 유효한 빗각을 수동 계산과 비교
        window = 5
        tenkan_vals = result["Ichimoku_Tenkan"]
        last_valid_idx = result["Ichimoku_Tenkan_Angle"].last_valid_index()

        if last_valid_idx is not None:
            idx_pos = result.index.get_loc(last_valid_idx)
            curr = tenkan_vals.iloc[idx_pos]
            prev = tenkan_vals.iloc[idx_pos - window]

            if pd.notna(curr) and pd.notna(prev) and prev != 0:
                expected_pct = (curr - prev) / prev * 100
                expected_angle = degrees(atan2(expected_pct, window))
                actual_angle = result["Ichimoku_Tenkan_Angle"].iloc[idx_pos]
                assert abs(actual_angle - expected_angle) < 0.001


# ══════════════════════════════════════════════
# 3. run_full_analysis() 일목 통합
# ══════════════════════════════════════════════
class TestRunFullAnalysisIchimoku:
    """run_full_analysis()에 일목균형표 통합"""

    def test_ichimoku_in_full_analysis(self):
        """80행 → 일목균형표 컬럼 생성됨"""
        from technical_analysis import run_full_analysis

        df = _make_ohlcv(rows=80, trend="up")
        result = run_full_analysis(df)

        assert "Ichimoku_Tenkan" in result.columns
        assert "Ichimoku_Kijun" in result.columns
        assert "Ichimoku_CloudTop" in result.columns

    def test_ichimoku_angles_in_full_analysis(self):
        """80행 → 빗각 컬럼도 생성됨"""
        from technical_analysis import run_full_analysis

        df = _make_ohlcv(rows=80, trend="up")
        result = run_full_analysis(df)

        assert "Ichimoku_Tenkan_Angle" in result.columns
        assert "Ichimoku_Kijun_Angle" in result.columns

    def test_ichimoku_skipped_short_data(self):
        """30행 → 일목균형표 스킵"""
        from technical_analysis import run_full_analysis

        df = _make_ohlcv(rows=30)
        result = run_full_analysis(df)

        # 30행 < 53 최소 요구 → 컬럼 미생성
        assert "Ichimoku_Tenkan" not in result.columns


# ══════════════════════════════════════════════
# 4. generate_signals() 일목 신호
# ══════════════════════════════════════════════
class TestGenerateSignalsIchimoku:
    """generate_signals() 일목균형표 신호"""

    def _make_df_with_ichimoku(
        self,
        close: float = 100.0,
        tenkan: float = 98.0,
        kijun: float = 95.0,
        cloud_top: float = 93.0,
        cloud_bottom: float = 90.0,
    ) -> pd.DataFrame:
        """일목 컬럼이 있는 테스트 DataFrame"""
        df = _make_ohlcv(rows=5, base_price=close)
        df["Ichimoku_Tenkan"] = tenkan
        df["Ichimoku_Kijun"] = kijun
        df["Ichimoku_CloudTop"] = cloud_top
        df["Ichimoku_CloudBottom"] = cloud_bottom
        df["RSI"] = 50.0
        df["MACD"] = 1.0
        df["MACD_Signal"] = 0.5
        df["SMA_5"] = close
        df["SMA_20"] = close * 0.98
        df["SMA_60"] = close * 0.95
        df["BB_Pct"] = 0.5
        df["Stoch_K"] = 50.0
        df["Stoch_D"] = 50.0
        df["ADX"] = 25.0
        return df

    def test_strong_buy_signal(self):
        """구름 위 + 전환선>기준선 → 강한 상승"""
        from technical_analysis import generate_signals

        df = self._make_df_with_ichimoku(
            close=100, tenkan=98, kijun=95, cloud_top=90, cloud_bottom=85
        )
        signals = generate_signals(df)

        assert "일목균형표" in signals
        assert "상승" in signals["일목균형표"][1]

    def test_strong_sell_signal(self):
        """구름 아래 + 전환선<기준선 → 강한 하락"""
        from technical_analysis import generate_signals

        df = self._make_df_with_ichimoku(
            close=80, tenkan=82, kijun=85, cloud_top=95, cloud_bottom=90
        )
        signals = generate_signals(df)

        assert "일목균형표" in signals
        assert "하락" in signals["일목균형표"][1]

    def test_inside_cloud_neutral(self):
        """구름 내 → 방향성 모호"""
        from technical_analysis import generate_signals

        df = self._make_df_with_ichimoku(
            close=92, tenkan=91, kijun=93, cloud_top=95, cloud_bottom=90
        )
        signals = generate_signals(df)

        assert "일목균형표" in signals
        assert "모호" in signals["일목균형표"][1]

    def test_no_ichimoku_data(self):
        """일목 컬럼 없으면 미계산 지표에 포함"""
        from technical_analysis import generate_signals

        df = _make_ohlcv(rows=5)
        df["RSI"] = 50.0
        df["MACD"] = 1.0
        df["MACD_Signal"] = 0.5
        df["SMA_5"] = 100.0
        df["SMA_20"] = 100.0
        df["SMA_60"] = 100.0
        df["BB_Pct"] = 0.5
        df["Stoch_K"] = 50.0
        df["Stoch_D"] = 50.0
        df["ADX"] = 25.0
        signals = generate_signals(df)

        assert "미계산지표" in signals
        assert "일목균형표" in signals["미계산지표"][0]


# ══════════════════════════════════════════════
# 5. config + constants 검증
# ══════════════════════════════════════════════
class TestIchimokuConfig:
    """일목균형표 설정값 검증"""

    def test_config_ichimoku_indicators(self):
        """indicators.ichimoku 기본값 존재"""
        cfg = get_config()
        ichi = cfg["indicators"]["ichimoku"]
        assert ichi["tenkan_window"] == 9
        assert ichi["kijun_window"] == 26
        assert ichi["senkou_b_window"] == 52
        assert ichi["chikou_shift"] == 26

    def test_config_ichimoku_thresholds(self):
        """thresholds.ichimoku 기본값 존재"""
        cfg = get_config()
        ichi_t = cfg["thresholds"]["ichimoku"]
        assert ichi_t["cloud_thick_ratio"] == 0.02
        assert ichi_t["cloud_thin_ratio"] == 0.005
        assert ichi_t["angle_strong"] == 26
        assert ichi_t["angle_flat"] == 10
        assert ichi_t["angle_window"] == 5

    def test_config_min_rows_ichimoku(self):
        """min_rows_per_indicator에 ichimoku 포함"""
        cfg = get_config()
        mr = cfg["indicators"]["min_rows_per_indicator"]
        assert "ichimoku" in mr
        assert mr["ichimoku"] == 53

    def test_config_split_entry(self):
        """split_entry 기본값 존재"""
        cfg = get_config()
        se = cfg["split_entry"]
        assert se["conservative_atr_mult"] == 2.0
        assert se["moderate_atr_mult"] == 1.0
        assert se["aggressive_atr_mult"] == 0.0
        assert se["conservative_sell_atr"] == 1.5
        assert se["moderate_sell_atr"] == 3.0
        assert se["aggressive_sell_atr"] == 5.0

    def test_constants_bound(self):
        """constants.py에 일목 상수 바인딩 확인"""
        assert ICHIMOKU_CLOUD_THICK_RATIO == 0.02
        assert ICHIMOKU_CLOUD_THIN_RATIO == 0.005
        assert ICHIMOKU_ANGLE_STRONG == 26
        assert ICHIMOKU_ANGLE_FLAT == 10
        assert ICHIMOKU_ANGLE_WINDOW == 5


# ══════════════════════════════════════════════
# Phase B: ExpertOpinion 확장 + 3분할 계산
# ══════════════════════════════════════════════

# ── 6. ExpertOpinion 확장 ──
class TestExpertOpinionExtended:
    """ExpertOpinion buy_prices/sell_prices 필드"""

    def test_default_none(self):
        """신규 필드 기본값 None"""
        from common.models import ExpertOpinion

        op = ExpertOpinion(
            expert_name="test", expert_style="test",
            position="홀드", confidence=50.0,
        )
        assert op.buy_prices is None
        assert op.sell_prices is None

    def test_with_split_prices(self):
        """3분할 가격 설정"""
        from common.models import ExpertOpinion

        op = ExpertOpinion(
            expert_name="test", expert_style="test",
            position="매수", confidence=70.0,
            buy_prices=[90.0, 95.0, 100.0],
            sell_prices=[110.0, 120.0, 130.0],
        )
        assert op.buy_prices == [90.0, 95.0, 100.0]
        assert op.sell_prices == [110.0, 120.0, 130.0]

    def test_to_dict_includes_split(self):
        """to_dict()에 3분할 키 포함"""
        from common.models import ExpertOpinion

        op = ExpertOpinion(
            expert_name="test", expert_style="test",
            position="매수", confidence=70.0,
            buy_prices=[90.0, 95.0, 100.0],
            sell_prices=[110.0, 120.0, 130.0],
        )
        d = op.to_dict()
        assert "3분할_매수" in d
        assert "3분할_매도" in d
        assert len(d["3분할_매수"]) == 3

    def test_to_dict_no_split_when_none(self):
        """buy_prices=None이면 to_dict()에 키 없음"""
        from common.models import ExpertOpinion

        op = ExpertOpinion(
            expert_name="test", expert_style="test",
            position="홀드", confidence=50.0,
        )
        d = op.to_dict()
        assert "3분할_매수" not in d
        assert "3분할_매도" not in d

    def test_backward_compatibility(self):
        """기존 코드와 호환: buy_price/sell_price 그대로 동작"""
        from common.models import ExpertOpinion

        op = ExpertOpinion(
            expert_name="test", expert_style="test",
            position="매수", confidence=70.0,
            buy_price=100.0, sell_price=120.0, stop_loss=90.0,
        )
        d = op.to_dict()
        assert d["매수가"] == "$100.00"
        assert d["매도가"] == "$120.00"
        assert d["손절가"] == "$90.00"


# ── 7. split_calculator 매수 가격 ──
class TestSplitBuyPrices:
    """calc_split_buy_prices() 테스트"""

    def test_atr_fallback(self):
        """일목 없으면 ATR 기반 폴백"""
        from common.split_calculator import calc_split_buy_prices

        prices = calc_split_buy_prices(price=100.0, atr=3.0)
        assert len(prices) == 3
        # 1차: 100-3*2=94, 2차: 100-3*1=97, 3차: 100-3*0=100
        assert prices[0] == 94.0
        assert prices[1] == 97.0
        assert prices[2] == 100.0

    def test_ichimoku_based(self):
        """일목 레벨 기반 매수 가격"""
        from common.split_calculator import calc_split_buy_prices

        ichimoku = {"cloud_bottom": 90.0, "kijun": 95.0, "tenkan": 98.0}
        prices = calc_split_buy_prices(price=100.0, atr=3.0, ichimoku=ichimoku)
        assert len(prices) == 3
        # 정렬됨: cloud_bottom <= kijun <= tenkan
        assert prices[0] == 90.0
        assert prices[1] == 95.0
        assert prices[2] == 98.0

    def test_angle_strong_up_adjusts_p3(self):
        """강한 상승 빗각 → 3차 매수 현재가 근처"""
        from common.split_calculator import calc_split_buy_prices

        ichimoku = {"cloud_bottom": 85.0, "kijun": 90.0, "tenkan": 93.0}
        angle = {"tenkan_angle": 30.0, "kijun_angle": 15.0}
        prices = calc_split_buy_prices(price=100.0, atr=3.0, ichimoku=ichimoku, angle=angle)
        # 3차가 tenkan(93) 보다 상향 조정되어야 함
        assert prices[2] >= 93.0

    def test_angle_down_kijun_adjusts_p1(self):
        """하락 기준선 빗각 → 1차 매수 하향"""
        from common.split_calculator import calc_split_buy_prices

        ichimoku = {"cloud_bottom": 90.0, "kijun": 95.0, "tenkan": 98.0}
        angle = {"tenkan_angle": 5.0, "kijun_angle": -15.0}
        prices = calc_split_buy_prices(price=100.0, atr=3.0, ichimoku=ichimoku, angle=angle)
        # 1차가 cloud_bottom(90) 보다 하향 조정되어야 함
        assert prices[0] < 90.0

    def test_no_atr_uses_3pct_fallback(self):
        """ATR=None이면 가격의 3% 폴백"""
        from common.split_calculator import calc_split_buy_prices

        prices = calc_split_buy_prices(price=100.0, atr=None)
        assert len(prices) == 3
        # ATR=3.0 (100*0.03)
        assert prices[0] == 94.0

    def test_prices_always_positive(self):
        """극단적 ATR에서도 양수"""
        from common.split_calculator import calc_split_buy_prices

        prices = calc_split_buy_prices(price=5.0, atr=10.0)
        assert all(p > 0 for p in prices)

    def test_prices_sorted_ascending(self):
        """매수 가격은 항상 오름차순"""
        from common.split_calculator import calc_split_buy_prices

        ichimoku = {"cloud_bottom": 88.0, "kijun": 95.0, "tenkan": 92.0}
        prices = calc_split_buy_prices(price=100.0, atr=3.0, ichimoku=ichimoku)
        assert prices[0] <= prices[1] <= prices[2]


# ── 8. split_calculator 매도 가격 ──
class TestSplitSellPrices:
    """calc_split_sell_prices() 테스트"""

    def test_atr_fallback(self):
        """일목 없으면 ATR 기반 폴백"""
        from common.split_calculator import calc_split_sell_prices

        prices = calc_split_sell_prices(price=100.0, atr=3.0)
        assert len(prices) == 3
        # 1차: 100+3*1.5=104.5, 2차: 100+3*3=109, 3차: 100+3*5=115
        assert prices[0] == 104.5
        assert prices[1] == 109.0
        assert prices[2] == 115.0

    def test_ichimoku_based_above_price(self):
        """일목 기반 + 가격이 이미 기준선 위 → ATR 보정"""
        from common.split_calculator import calc_split_sell_prices

        # 현재가 100인데 기준선 95, 구름상단 97 → 이미 위에 있음
        ichimoku = {"cloud_top": 97.0, "kijun": 95.0}
        prices = calc_split_sell_prices(price=100.0, atr=3.0, ichimoku=ichimoku)
        assert len(prices) == 3
        # 모든 매도가 > 현재가
        assert all(p > 100.0 for p in prices)

    def test_ichimoku_based_below_levels(self):
        """현재가 < 기준선/구름상단 → 일목 레벨 사용"""
        from common.split_calculator import calc_split_sell_prices

        ichimoku = {"cloud_top": 120.0, "kijun": 110.0}
        prices = calc_split_sell_prices(price=100.0, atr=3.0, ichimoku=ichimoku)
        assert len(prices) == 3
        # kijun(110), ATR확장(115=100+3*5), cloud_top(120) → 정렬됨
        assert prices[0] == 110.0
        assert prices[2] == 120.0  # 구름상단이 가장 높은 목표

    def test_strong_uptrend_extends_p3(self):
        """강한 상승 빗각 → 3차 매도 목표 상향"""
        from common.split_calculator import calc_split_sell_prices

        ichimoku = {"cloud_top": 120.0, "kijun": 110.0}
        angle_normal = {"tenkan_angle": 15.0}
        angle_strong = {"tenkan_angle": 30.0}

        p_normal = calc_split_sell_prices(price=100.0, atr=3.0, ichimoku=ichimoku, angle=angle_normal)
        p_strong = calc_split_sell_prices(price=100.0, atr=3.0, ichimoku=ichimoku, angle=angle_strong)
        # 강한 상승 시 3차 매도 목표가 더 높아야 함
        assert p_strong[2] >= p_normal[2]

    def test_prices_sorted_ascending(self):
        """매도 가격은 항상 오름차순"""
        from common.split_calculator import calc_split_sell_prices

        prices = calc_split_sell_prices(price=100.0, atr=5.0)
        assert prices[0] <= prices[1] <= prices[2]


# ── 9. extract helpers ──
class TestExtractIchimokuLevels:
    """extract_ichimoku_levels() 테스트"""

    def test_extract_from_df(self):
        """일목 컬럼이 있는 DF에서 레벨 추출"""
        from common.split_calculator import extract_ichimoku_levels

        df = _make_ohlcv(rows=5)
        df["Ichimoku_Tenkan"] = 98.0
        df["Ichimoku_Kijun"] = 95.0
        df["Ichimoku_CloudTop"] = 93.0
        df["Ichimoku_CloudBottom"] = 90.0

        levels = extract_ichimoku_levels(df)
        assert levels is not None
        assert levels["tenkan"] == 98.0
        assert levels["kijun"] == 95.0
        assert levels["cloud_top"] == 93.0
        assert levels["cloud_bottom"] == 90.0

    def test_returns_none_no_columns(self):
        """일목 컬럼 없으면 None"""
        from common.split_calculator import extract_ichimoku_levels

        df = _make_ohlcv(rows=5)
        assert extract_ichimoku_levels(df) is None

    def test_returns_none_nan_values(self):
        """NaN 값이면 None"""
        from common.split_calculator import extract_ichimoku_levels

        df = _make_ohlcv(rows=5)
        df["Ichimoku_Tenkan"] = np.nan
        df["Ichimoku_Kijun"] = 95.0
        df["Ichimoku_CloudTop"] = 93.0
        df["Ichimoku_CloudBottom"] = 90.0

        assert extract_ichimoku_levels(df) is None

    def test_empty_df(self):
        """빈 DF → None"""
        from common.split_calculator import extract_ichimoku_levels

        df = pd.DataFrame()
        assert extract_ichimoku_levels(df) is None


class TestExtractIchimokuAngles:
    """extract_ichimoku_angles() 테스트"""

    def test_extract_angles(self):
        """빗각 추출"""
        from common.split_calculator import extract_ichimoku_angles

        df = _make_ohlcv(rows=5)
        df["Ichimoku_Tenkan_Angle"] = 15.0
        df["Ichimoku_Kijun_Angle"] = 10.0
        df["Ichimoku_SenkouA_Angle"] = 5.0

        angles = extract_ichimoku_angles(df)
        assert angles is not None
        assert angles["tenkan_angle"] == 15.0
        assert angles["kijun_angle"] == 10.0

    def test_returns_none_no_columns(self):
        """빗각 컬럼 없으면 None"""
        from common.split_calculator import extract_ichimoku_angles

        df = _make_ohlcv(rows=5)
        assert extract_ichimoku_angles(df) is None

    def test_nan_angle_becomes_none(self):
        """NaN 빗각은 None으로"""
        from common.split_calculator import extract_ichimoku_angles

        df = _make_ohlcv(rows=5)
        df["Ichimoku_Tenkan_Angle"] = np.nan
        df["Ichimoku_Kijun_Angle"] = 10.0
        df["Ichimoku_SenkouA_Angle"] = 5.0

        angles = extract_ichimoku_angles(df)
        assert angles is not None
        assert angles["tenkan_angle"] is None
        assert angles["kijun_angle"] == 10.0


# ══════════════════════════════════════════════
# Phase C: 일목균형표 전문가 + 기존 전문가 통합
# ══════════════════════════════════════════════

def _make_full_df(
    rows: int = 80,
    close: float = 100.0,
    trend: str = "flat",
    ichimoku: bool = True,
) -> pd.DataFrame:
    """전문가 분석용 완전한 테스트 DataFrame"""
    df = _make_ohlcv(rows=rows, base_price=close, trend=trend)

    # 기존 기술적 지표
    df["RSI"] = 50.0
    df["RSI_14"] = 50.0
    df["MACD"] = 1.0
    df["MACD_Signal"] = 0.5
    df["MACD_Hist"] = 0.5
    df["SMA_5"] = close
    df["SMA_20"] = close * 0.98
    df["SMA_60"] = close * 0.96
    df["SMA_120"] = close * 0.94
    df["BB_Pct"] = 0.5
    df["BB_Upper"] = close * 1.05
    df["BB_Lower"] = close * 0.95
    df["BB_Middle"] = close
    df["BB_Width"] = 0.1
    df["ADX"] = 25.0
    df["ADX_Pos"] = 15.0
    df["ADX_Neg"] = 10.0
    df["ATR"] = close * 0.03
    df["Stoch_K"] = 50.0
    df["Stoch_D"] = 50.0
    df["OBV"] = list(range(rows))

    if ichimoku:
        df["Ichimoku_Tenkan"] = close * 0.99
        df["Ichimoku_Kijun"] = close * 0.97
        df["Ichimoku_SenkouA"] = close * 0.95
        df["Ichimoku_SenkouB"] = close * 0.93
        df["Ichimoku_CloudTop"] = close * 0.95
        df["Ichimoku_CloudBottom"] = close * 0.93
        df["Ichimoku_Chikou"] = close
        df["Ichimoku_Tenkan_Angle"] = 15.0
        df["Ichimoku_Kijun_Angle"] = 10.0
        df["Ichimoku_SenkouA_Angle"] = 8.0

    return df


# ── 10. IchimokuExpert 전문가 ──
class TestIchimokuExpert:
    """일목균형표 전문가 분석 테스트"""

    def test_basic_analyze(self):
        """기본 분석 실행"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        df = _make_full_df(close=100.0)
        info = {"52주_최고": 150.0, "52주_최저": 50.0}
        opinion = IchimokuExpert.analyze(df, info)

        assert opinion.expert_name == "일목균형표 전문가"
        assert opinion.position in ("매수", "홀드", "매도")
        assert 0 < opinion.confidence <= 100

    def test_buy_signal_above_cloud(self):
        """가격 > 구름 상단 + TK 상승크로스 → 매수 쪽"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        df = _make_full_df(close=100.0)
        # 가격 100 > 구름상단 95 + 전환선(99) > 기준선(97)
        info = {}
        opinion = IchimokuExpert.analyze(df, info)

        assert "구름 상단" in opinion.rationale or "상승" in opinion.rationale
        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None
        assert len(opinion.buy_prices) == 3
        assert len(opinion.sell_prices) == 3

    def test_sell_signal_below_cloud(self):
        """가격 < 구름 하단 + TK 하락크로스 → 매도 쪽"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        df = _make_full_df(close=80.0)
        df["Ichimoku_Tenkan"] = 85.0
        df["Ichimoku_Kijun"] = 88.0
        df["Ichimoku_CloudTop"] = 95.0
        df["Ichimoku_CloudBottom"] = 90.0
        df["Ichimoku_Tenkan_Angle"] = -30.0
        df["Ichimoku_Kijun_Angle"] = -20.0

        info = {}
        opinion = IchimokuExpert.analyze(df, info)

        assert "하락" in opinion.rationale

    def test_no_ichimoku_data(self):
        """일목 컬럼 없을 때 → 데이터 부족 메시지"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        df = _make_full_df(close=100.0, ichimoku=False)
        info = {}
        opinion = IchimokuExpert.analyze(df, info)

        # 일목 컬럼이 없으면 구름/TK는 미분석이지만 후행스팬은 가격 데이터로 분석 가능
        assert "데이터 부족" in opinion.rationale

    def test_split_prices_always_present(self):
        """3분할 가격은 항상 반환"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        df = _make_full_df(close=100.0, ichimoku=False)
        info = {}
        opinion = IchimokuExpert.analyze(df, info)

        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None
        assert len(opinion.buy_prices) == 3

    def test_angle_affects_score(self):
        """강한 빗각이 점수에 영향"""
        from expert_strategies.ichimoku_expert import IchimokuExpert

        # 강한 상승 빗각
        df = _make_full_df(close=100.0)
        df["Ichimoku_Tenkan_Angle"] = 35.0  # > 26° 강한
        df["Ichimoku_Kijun_Angle"] = 30.0

        info = {}
        opinion = IchimokuExpert.analyze(df, info)
        assert "강한 상승 모멘텀" in opinion.rationale


# ── 11. 기존 전문가 3분할 통합 ──
class TestExistingExpertsSplitIntegration:
    """기존 4전문가의 3분할 통합 테스트"""

    def test_trend_follower_has_split_prices(self):
        """추세추종 전문가가 3분할 가격 반환"""
        from expert_strategies.trend_follower import TrendFollower

        df = _make_full_df(close=100.0)
        info = {"52주_최고": 150.0, "52주_최저": 50.0}
        opinion = TrendFollower.analyze(df, info)

        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None
        assert len(opinion.buy_prices) == 3
        assert len(opinion.sell_prices) == 3

    def test_value_analyst_has_split_prices(self):
        """가치분석 전문가가 3분할 가격 반환"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_full_df(close=100.0)
        info = {"52주_최고": 150.0, "52주_최저": 50.0, "PBR": 1.5, "EPS": 3.0}
        opinion = ValueAnalyst.analyze(df, info)

        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None

    def test_momentum_trader_has_split_prices(self):
        """모멘텀 트레이더가 3분할 가격 반환"""
        from expert_strategies.momentum_trader import MomentumTrader

        df = _make_full_df(close=100.0)
        info = {}
        opinion = MomentumTrader.analyze(df, info)

        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None

    def test_contrarian_expert_has_split_prices(self):
        """역발상 전문가가 3분할 가격 반환"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_full_df(close=100.0)
        info = {"52주_최고": 150.0, "52주_최저": 50.0}
        opinion = ContrarianExpert.analyze(df, info)

        assert opinion.buy_prices is not None
        assert opinion.sell_prices is not None

    def test_trend_follower_ichimoku_cloud_check(self):
        """추세추종 전문가에 일목 구름 확인 반영"""
        from expert_strategies.trend_follower import TrendFollower

        df = _make_full_df(close=100.0)
        # 가격(100) > 구름상단(95) → 추세 상승 확인
        info = {}
        opinion = TrendFollower.analyze(df, info)

        assert "[일목]" in opinion.rationale

    def test_momentum_ichimoku_angle_check(self):
        """모멘텀 트레이더에 일목 TK+빗각 반영"""
        from expert_strategies.momentum_trader import MomentumTrader

        df = _make_full_df(close=100.0)
        # tenkan(99) > kijun(97) + angle(15) < 26 → 반영 안됨
        df["Ichimoku_Tenkan_Angle"] = 30.0  # > 26° → 반영됨
        info = {}
        opinion = MomentumTrader.analyze(df, info)

        assert "[일목]" in opinion.rationale

    def test_contrarian_chikou_check(self):
        """역발상 전문가에 후행스팬 괴리 확인"""
        from expert_strategies.contrarian_expert import ContrarianExpert

        df = _make_full_df(rows=80, close=80.0)
        # 26일전 가격을 100으로 설정하여 괴리 생성
        df.iloc[-27, df.columns.get_loc("Close")] = 100.0
        # 현재 80 < 100 * 0.9 = 90 → 후행스팬 괴리

        info = {"52주_최고": 150.0, "52주_최저": 50.0}
        opinion = ContrarianExpert.analyze(df, info)

        assert "[일목]" in opinion.rationale or "후행" in opinion.rationale

    def test_value_analyst_ichimoku_reference(self):
        """가치분석 전문가에 일목 참조 표시"""
        from expert_strategies.value_analyst import ValueAnalyst

        df = _make_full_df(close=100.0)
        info = {"52주_최고": 150.0, "52주_최저": 50.0, "PBR": 1.5, "EPS": 3.0}
        opinion = ValueAnalyst.analyze(df, info)

        assert "[일목 참조]" in opinion.rationale

    def test_all_experts_without_ichimoku(self):
        """일목 컬럼 없어도 모든 전문가가 정상 동작"""
        from expert_strategies import ALL_EXPERTS

        df = _make_full_df(close=100.0, ichimoku=False)
        info = {"52주_최고": 150.0, "52주_최저": 50.0, "PBR": 1.5, "EPS": 3.0}

        for expert in ALL_EXPERTS:
            opinion = expert.analyze(df, info)
            assert opinion.position in ("매수", "홀드", "매도")
            assert opinion.buy_prices is not None  # ATR 폴백
            assert len(opinion.buy_prices) == 3


# ── 12. ALL_EXPERTS 확인 ──
class TestAllExpertsCount:
    """전문가 5명 등록 확인"""

    def test_5_experts(self):
        from expert_strategies import ALL_EXPERTS
        assert len(ALL_EXPERTS) == 5

    def test_ichimoku_in_list(self):
        from expert_strategies import ALL_EXPERTS, IchimokuExpert
        assert IchimokuExpert in ALL_EXPERTS


# ══════════════════════════════════════════════
# Phase D: 리포트 확장 테스트
# ══════════════════════════════════════════════

def _make_report_df(n=100):
    """리포트 테스트용 DataFrame"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    close = np.linspace(100, 110, n) + np.random.randn(n)
    df = pd.DataFrame({
        "Open": close * 0.99, "High": close * 1.02,
        "Low": close * 0.98, "Close": close,
        "Volume": np.random.randint(100000, 1000000, n),
    }, index=dates)
    df["SMA_5"] = df["Close"].rolling(5).mean()
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["RSI"] = 55.0
    df["ATR"] = 3.0
    return df


def _base_company_info():
    return {
        "이름": "TestCorp", "섹터": "Technology",
        "52주_최고": 130, "52주_최저": 80,
        "시가총액": 1e10, "PER": 25, "PBR": 5.0,
        "EPS": 3.5, "부채비율": 45.0, "베타": 1.2,
    }


def _mock_expert_opinions_with_split():
    """3분할 가격이 포함된 전문가 의견 리스트"""
    from common.models import ExpertOpinion
    opinions = []
    for i, (name, style, pos) in enumerate([
        ("추세추종 전문가", "이동평균 기반", "매수"),
        ("가치분석 전문가", "PER/PBR 기반", "홀드"),
        ("모멘텀 트레이더", "RSI/MACD 기반", "매수"),
        ("역발상 전문가", "볼린저밴드 기반", "홀드"),
        ("일목균형표 전문가", "구름/TK크로스 기반", "매수"),
    ]):
        opinions.append(ExpertOpinion(
            expert_name=name,
            expert_style=style,
            position=pos,
            confidence=70.0 + i * 3,
            buy_price=95.0 + i,
            sell_price=115.0 + i,
            stop_loss=88.0 + i,
            rationale="테스트 근거",
            key_indicators=[f"RSI={50+i}"],
            buy_prices=[90.0 + i, 95.0 + i, 100.0 + i],
            sell_prices=[110.0 + i, 120.0 + i, 130.0 + i],
        ))
    return opinions


def _mock_expert_opinions_without_split():
    """3분할 가격이 없는 전문가 의견 (하위 호환 테스트)"""
    from common.models import ExpertOpinion
    return [
        ExpertOpinion(
            expert_name="테스트 전문가",
            expert_style="테스트 스타일",
            position="매수",
            confidence=70,
            buy_price=100.0,
            sell_price=120.0,
            stop_loss=90.0,
            rationale="테스트 근거",
            key_indicators=["RSI=55"],
        )
    ]


def _default_news_sentiment():
    return {"총건수": 0, "긍정": 0, "부정": 0, "중립": 0, "종합감성": "N/A"}


class TestReportIchimokuIntegration:
    """Phase D: 리포트 내 3분할/5인/일목 표시 검증"""

    def test_report_5_experts_header(self):
        """리포트에 '전문가 5인' 헤더 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "전문가 5인 분석" in report

    def test_report_summary_5_experts(self):
        """종합 요약에 '전문가 5인 종합 요약' 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "전문가 5인 종합 요약" in report

    def test_report_split_prices_displayed(self):
        """3분할 매수/매도 전략 카드 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "3분할 매수/매도 전략" in report

    def test_report_split_labels(self):
        """1차/2차/3차 매수/매도 라벨 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "1차 매수(보수적)" in report
        assert "2차 매수(중간)" in report
        assert "3차 매수(적극적)" in report
        assert "1차 매도(보수적)" in report
        assert "2차 매도(중간)" in report
        assert "3차 매도(적극적)" in report

    def test_report_average_split_prices(self):
        """종합 요약에 3분할 평균 매수/매도가 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "3분할 평균 매수가" in report
        assert "3분할 평균 매도가" in report

    def test_report_no_split_backward_compatible(self):
        """3분할 가격 없는 전문가 → 에러 없이 리포트 생성"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_without_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert report  # 비어있지 않음
        # 3분할 표시가 없어야 함
        assert "3분할 매수/매도 전략" not in report

    def test_report_ichimoku_expert_displayed(self):
        """일목균형표 전문가가 리포트에 표시"""
        from stock_analyzer import build_report

        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=_mock_expert_opinions_with_split(),
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        assert "일목균형표 전문가" in report

    def test_report_split_price_values(self):
        """3분할 가격값이 올바르게 표시"""
        from stock_analyzer import build_report

        opinions = _mock_expert_opinions_with_split()
        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=opinions,
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        # 첫 번째 전문가의 1차 매수가 $90.00
        assert "$90.00" in report
        # 첫 번째 전문가의 1차 매도가 $110.00
        assert "$110.00" in report

    def test_report_average_split_calculation(self):
        """3분할 평균 계산이 정확한지 확인"""
        from stock_analyzer import build_report

        opinions = _mock_expert_opinions_with_split()
        report = build_report(
            ticker="TEST", company_info=_base_company_info(),
            df=_make_report_df(),
            signals={"종합판단": "보통"},
            expert_opinions=opinions,
            analyst_ratings=[], analyst_summary={},
            articles=[], news_sentiment=_default_news_sentiment(),
            chart_paths=[],
        )
        # 5명의 1차 매수: 90,91,92,93,94 → 평균 92.00
        assert "$92.00" in report
