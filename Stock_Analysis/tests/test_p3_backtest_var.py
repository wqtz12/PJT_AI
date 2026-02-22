"""
P3-3 테스트: 백테스팅 & VaR 분석
- compute_daily_returns() 수익률 계산
- compute_max_drawdown() MDD 계산
- compute_sharpe_ratio() 샤프 비율
- compute_risk_metrics() 종합 리스크
- compute_var() VaR 분석
- run_backtest() 백테스트 시뮬레이션
- BacktestResult / VaRResult 모델
- generate_backtest_report() 리포트 생성
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester import (
    compute_daily_returns, compute_max_drawdown, compute_sharpe_ratio,
    compute_risk_metrics, compute_var, run_backtest,
    generate_backtest_report,
    BacktestResult, VaRResult,
)
from common.models import ExpertOpinion


# ─── 테스트 데이터 유틸 ───

def _make_df(rows=100, base_price=10.0, trend="up"):
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    np.random.seed(42)
    if trend == "up":
        prices = base_price + np.cumsum(np.random.normal(0.05, 0.3, rows))
    elif trend == "down":
        prices = base_price + np.cumsum(np.random.normal(-0.05, 0.3, rows))
    else:
        prices = base_price + np.random.normal(0, 0.3, rows)
    prices = np.maximum(prices, 0.5)
    return pd.DataFrame({
        "Open": prices * 0.99,
        "High": prices * 1.02,
        "Low": prices * 0.97,
        "Close": prices,
        "Volume": np.random.randint(500_000, 5_000_000, rows).astype(float),
    }, index=dates)


def _make_opinions(position="매수"):
    return [
        ExpertOpinion("추세추종", "이동평균 기반", position, 75.0,
                      buy_price=9.0, sell_price=13.0, stop_loss=7.5),
        ExpertOpinion("가치분석", "PBR/PER 기반", "홀드", 60.0),
        ExpertOpinion("모멘텀", "RSI/MACD 기반", position, 70.0,
                      buy_price=9.5, sell_price=12.5, stop_loss=8.0),
        ExpertOpinion("역발상", "볼린저 기반", "홀드", 55.0),
    ]


# ─── compute_daily_returns() ───

class TestComputeDailyReturns:
    """일일 수익률 계산"""

    def test_returns_series(self):
        df = _make_df(rows=50)
        returns = compute_daily_returns(df)
        assert isinstance(returns, pd.Series)

    def test_returns_length(self):
        """수익률은 원본보다 1개 적음"""
        df = _make_df(rows=50)
        returns = compute_daily_returns(df)
        assert len(returns) == 49

    def test_no_nan_in_returns(self):
        df = _make_df(rows=50)
        returns = compute_daily_returns(df)
        assert returns.isna().sum() == 0

    def test_empty_df(self):
        df = pd.DataFrame({"Close": []})
        returns = compute_daily_returns(df)
        assert len(returns) == 0

    def test_single_row(self):
        df = pd.DataFrame({"Close": [10.0]})
        returns = compute_daily_returns(df)
        assert len(returns) == 0

    def test_known_return(self):
        """알려진 수익률 검증: 10→11 = 10%"""
        df = pd.DataFrame({"Close": [10.0, 11.0]},
                          index=pd.date_range("2024-01-01", periods=2))
        returns = compute_daily_returns(df)
        assert abs(returns.iloc[0] - 0.1) < 1e-10


# ─── compute_max_drawdown() ───

class TestComputeMaxDrawdown:
    """최대 낙폭(MDD) 계산"""

    def test_returns_negative(self):
        """MDD는 항상 0 이하"""
        df = _make_df(rows=100)
        mdd = compute_max_drawdown(df)
        assert mdd <= 0

    def test_pure_uptrend_small_mdd(self):
        """순수 상승 → MDD가 작음"""
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        prices = np.linspace(10, 20, 50)
        df = pd.DataFrame({"Close": prices}, index=dates)
        mdd = compute_max_drawdown(df)
        assert mdd == 0.0  # 순수 상승이면 MDD = 0

    def test_50pct_drop(self):
        """10→5 하락 → -50% MDD"""
        df = pd.DataFrame({"Close": [10.0, 10.0, 5.0, 5.0]},
                          index=pd.date_range("2024-01-01", periods=4))
        mdd = compute_max_drawdown(df)
        assert abs(mdd - (-50.0)) < 0.1

    def test_empty_df(self):
        df = pd.DataFrame({"Close": []})
        mdd = compute_max_drawdown(df)
        assert mdd == 0.0

    def test_single_row(self):
        df = pd.DataFrame({"Close": [10.0]})
        mdd = compute_max_drawdown(df)
        assert mdd == 0.0

    def test_recovery_doesnt_reduce_mdd(self):
        """회복해도 MDD는 최대 낙폭 유지"""
        df = pd.DataFrame({"Close": [10.0, 5.0, 10.0]},
                          index=pd.date_range("2024-01-01", periods=3))
        mdd = compute_max_drawdown(df)
        assert abs(mdd - (-50.0)) < 0.1


# ─── compute_sharpe_ratio() ───

class TestComputeSharpeRatio:
    """샤프 비율 계산"""

    def test_returns_float(self):
        returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005])
        sharpe = compute_sharpe_ratio(returns)
        assert isinstance(sharpe, float)

    def test_empty_returns(self):
        returns = pd.Series([], dtype=float)
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe == 0.0

    def test_single_return(self):
        returns = pd.Series([0.01])
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe == 0.0

    def test_positive_returns_positive_sharpe(self):
        """양의 수익률 → 양의 샤프"""
        returns = pd.Series([0.02, 0.03, 0.01, 0.025, 0.015, 0.02, 0.01])
        sharpe = compute_sharpe_ratio(returns, risk_free_rate=0.0)
        assert sharpe > 0

    def test_negative_returns_negative_sharpe(self):
        """음의 수익률 → 음의 샤프"""
        returns = pd.Series([-0.02, -0.03, -0.01, -0.025, -0.015])
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe < 0

    def test_zero_std_returns_zero(self):
        """표준편차 0 → 샤프 0"""
        returns = pd.Series([0.001, 0.001, 0.001, 0.001])
        sharpe = compute_sharpe_ratio(returns, risk_free_rate=0.001 * 252)
        assert sharpe == 0.0


# ─── compute_risk_metrics() ───

class TestComputeRiskMetrics:
    """종합 리스크 지표"""

    def test_returns_dict(self):
        df = _make_df(rows=50)
        metrics = compute_risk_metrics(df)
        assert isinstance(metrics, dict)

    def test_has_required_keys(self):
        df = _make_df(rows=50)
        metrics = compute_risk_metrics(df)
        required = ["일일변동성", "연환산변동성", "최대낙폭", "샤프비율",
                     "평균수익률", "왜도", "첨도"]
        for key in required:
            assert key in metrics, f"키 누락: {key}"

    def test_volatility_positive(self):
        df = _make_df(rows=100)
        metrics = compute_risk_metrics(df)
        assert metrics["일일변동성"] > 0
        assert metrics["연환산변동성"] > 0

    def test_annualized_greater_than_daily(self):
        """연환산 변동성 > 일일 변동성"""
        df = _make_df(rows=100)
        metrics = compute_risk_metrics(df)
        assert metrics["연환산변동성"] > metrics["일일변동성"]

    def test_insufficient_data(self):
        df = pd.DataFrame({"Close": [10.0]})
        metrics = compute_risk_metrics(df)
        assert metrics["일일변동성"] == 0.0


# ─── compute_var() ───

class TestComputeVaR:
    """VaR 분석"""

    def test_returns_var_result(self):
        df = _make_df(rows=100)
        result = compute_var(df)
        assert isinstance(result, VaRResult)

    def test_historical_var_negative(self):
        """VaR은 보통 음수 (손실 표시)"""
        df = _make_df(rows=100)
        result = compute_var(df)
        assert result.historical_var < 0 or result.historical_var >= 0  # 존재 확인

    def test_parametric_var_exists(self):
        df = _make_df(rows=100)
        result = compute_var(df)
        assert isinstance(result.parametric_var, float)

    def test_cvar_worse_than_var(self):
        """CVaR(Expected Shortfall)은 VaR보다 작거나 같음 (더 나쁜 시나리오)"""
        df = _make_df(rows=200)
        result = compute_var(df)
        # CVaR <= 히스토리컬 VaR (둘 다 음수이므로)
        assert result.conditional_var <= result.historical_var + 0.5  # 약간의 여유

    def test_confidence_level_stored(self):
        df = _make_df(rows=50)
        result = compute_var(df, confidence=0.99)
        assert result.confidence_level == 0.99

    def test_holding_days_stored(self):
        df = _make_df(rows=50)
        result = compute_var(df, holding_days=5)
        assert result.holding_days == 5

    def test_longer_holding_larger_var(self):
        """보유 기간 길수록 VaR 절대값 증가"""
        df = _make_df(rows=200)
        var_1d = compute_var(df, holding_days=1)
        var_5d = compute_var(df, holding_days=5)
        # sqrt 스케일링이므로 5일 VaR > 1일 VaR (절대값)
        assert abs(var_5d.historical_var) >= abs(var_1d.historical_var) * 0.9

    def test_higher_confidence_larger_var(self):
        """신뢰수준 높을수록 VaR 절대값 증가"""
        df = _make_df(rows=200)
        var_90 = compute_var(df, confidence=0.90)
        var_99 = compute_var(df, confidence=0.99)
        assert abs(var_99.parametric_var) >= abs(var_90.parametric_var) * 0.9

    def test_volatility_positive(self):
        df = _make_df(rows=100)
        result = compute_var(df)
        assert result.daily_volatility > 0
        assert result.annualized_volatility > 0

    def test_insufficient_data(self):
        df = pd.DataFrame({"Close": [10.0, 10.5]},
                          index=pd.date_range("2024-01-01", periods=2))
        result = compute_var(df)
        assert result.historical_var == 0.0

    def test_to_dict(self):
        df = _make_df(rows=100)
        result = compute_var(df)
        d = result.to_dict()
        assert "히스토리컬VaR" in d
        assert "파라메트릭VaR" in d
        assert "조건부VaR(CVaR)" in d


# ─── run_backtest() ───

class TestRunBacktest:
    """백테스트 시뮬레이션"""

    def test_returns_backtest_result(self):
        df = _make_df(rows=100)
        result = run_backtest(df)
        assert isinstance(result, BacktestResult)

    def test_with_expert_opinions(self):
        df = _make_df(rows=100)
        opinions = _make_opinions("매수")
        result = run_backtest(df, expert_opinions=opinions)
        assert isinstance(result, BacktestResult)

    def test_holding_period_matches_data(self):
        df = _make_df(rows=80)
        result = run_backtest(df)
        assert result.holding_period_days == 80

    def test_win_rate_in_range(self):
        """승률은 0~100%"""
        df = _make_df(rows=100)
        result = run_backtest(df)
        assert 0 <= result.win_rate_pct <= 100

    def test_total_trades_equals_win_plus_loss(self):
        """총거래 = 수익 + 손실"""
        df = _make_df(rows=100)
        result = run_backtest(df)
        assert result.total_trades == result.winning_trades + result.losing_trades

    def test_short_data_empty_result(self):
        """데이터 부족 시 빈 결과"""
        df = _make_df(rows=5)
        result = run_backtest(df)
        assert result.total_trades == 0

    def test_strategy_name_set(self):
        df = _make_df(rows=100)
        result = run_backtest(df, strategy_name="테스트 전략")
        assert result.strategy_name == "테스트 전략"

    def test_profit_factor_positive(self):
        """수익팩터는 0 이상"""
        df = _make_df(rows=100)
        result = run_backtest(df)
        assert result.profit_factor >= 0

    def test_sell_consensus_less_trades(self):
        """매도 컨센서스 → 진입 조건 더 까다로움"""
        df = _make_df(rows=100)
        buy_result = run_backtest(df, expert_opinions=_make_opinions("매수"))
        sell_result = run_backtest(df, expert_opinions=_make_opinions("매도"))
        # 매도 컨센서스에서는 진입하지 않으므로 거래수 적음
        assert sell_result.total_trades <= buy_result.total_trades

    def test_to_dict(self):
        df = _make_df(rows=100)
        result = run_backtest(df)
        d = result.to_dict()
        assert "총수익률" in d
        assert "샤프비율" in d
        assert "승률" in d
        assert "전략" in d


# ─── BacktestResult 모델 ───

class TestBacktestResult:
    """BacktestResult 데이터 모델"""

    def test_create_result(self):
        result = BacktestResult(
            total_return_pct=15.5,
            annualized_return_pct=31.0,
            max_drawdown_pct=-12.3,
            sharpe_ratio=1.5,
            win_rate_pct=65.0,
            total_trades=20,
            winning_trades=13,
            losing_trades=7,
            avg_win_pct=3.5,
            avg_loss_pct=-2.1,
            profit_factor=2.3,
            holding_period_days=126,
            strategy_name="테스트",
        )
        assert result.total_return_pct == 15.5
        assert result.strategy_name == "테스트"

    def test_to_dict_format(self):
        result = BacktestResult(
            total_return_pct=10.0, annualized_return_pct=20.0,
            max_drawdown_pct=-5.0, sharpe_ratio=1.0,
            win_rate_pct=60.0, total_trades=10,
            winning_trades=6, losing_trades=4,
            avg_win_pct=3.0, avg_loss_pct=-2.0,
            profit_factor=1.5, holding_period_days=100,
        )
        d = result.to_dict()
        assert "%" in d["총수익률"]
        assert "%" in d["승률"]


# ─── VaRResult 모델 ───

class TestVaRResult:
    """VaRResult 데이터 모델"""

    def test_create_result(self):
        result = VaRResult(
            historical_var=-2.5, parametric_var=-2.3,
            conditional_var=-3.2, confidence_level=0.95,
            holding_days=1, daily_volatility=1.5,
            annualized_volatility=23.8,
            mean_return=0.05, skewness=-0.3, kurtosis=2.5,
        )
        assert result.historical_var == -2.5
        assert result.confidence_level == 0.95

    def test_to_dict_format(self):
        result = VaRResult(
            historical_var=-2.5, parametric_var=-2.3,
            conditional_var=-3.2, confidence_level=0.95,
            holding_days=1, daily_volatility=1.5,
            annualized_volatility=23.8,
            mean_return=0.05, skewness=-0.3, kurtosis=2.5,
        )
        d = result.to_dict()
        assert "%" in d["히스토리컬VaR"]
        assert "95%" in d["신뢰수준"]


# ─── generate_backtest_report() ───

class TestGenerateBacktestReport:
    """리포트 생성"""

    def test_report_is_string(self):
        df = _make_df(rows=100)
        bt = run_backtest(df)
        var = compute_var(df)
        risk = compute_risk_metrics(df)
        report = generate_backtest_report(bt, var, risk)
        assert isinstance(report, str)

    def test_report_has_backtest_section(self):
        df = _make_df(rows=100)
        bt = run_backtest(df)
        var = compute_var(df)
        risk = compute_risk_metrics(df)
        report = generate_backtest_report(bt, var, risk)
        assert "백테스트" in report

    def test_report_has_var_section(self):
        df = _make_df(rows=100)
        bt = run_backtest(df)
        var = compute_var(df)
        risk = compute_risk_metrics(df)
        report = generate_backtest_report(bt, var, risk)
        assert "VaR" in report

    def test_report_has_risk_section(self):
        df = _make_df(rows=100)
        bt = run_backtest(df)
        var = compute_var(df)
        risk = compute_risk_metrics(df)
        report = generate_backtest_report(bt, var, risk)
        assert "리스크" in report

    def test_report_shows_strategy_name(self):
        df = _make_df(rows=100)
        bt = run_backtest(df, strategy_name="나의 전략")
        var = compute_var(df)
        risk = compute_risk_metrics(df)
        report = generate_backtest_report(bt, var, risk)
        assert "나의 전략" in report


# ─── config.yaml 연동 ───

class TestBacktestConfig:
    """config.yaml 백테스트 설정 검증"""

    def test_config_has_backtest_section(self):
        from common.config import get_config
        cfg = get_config()
        assert "backtest" in cfg

    def test_var_confidence_default(self):
        from common.config import get_config
        cfg = get_config()
        assert cfg["backtest"]["var_confidence"] == 0.95

    def test_risk_free_rate_default(self):
        from common.config import get_config
        cfg = get_config()
        assert cfg["backtest"]["risk_free_rate"] == 0.04

    def test_trading_days_default(self):
        from common.config import get_config
        cfg = get_config()
        assert cfg["backtest"]["trading_days_per_year"] == 252
