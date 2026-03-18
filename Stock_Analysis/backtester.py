"""
백테스팅 & VaR(Value at Risk) 분석 모듈

기능:
  1. 간이 백테스트: 4전문가 시그널 기반 과거 성과 시뮬레이션
  2. VaR 분석: 히스토리컬 VaR, 파라메트릭 VaR
  3. 리스크 지표: 최대 낙폭(MDD), 샤프 비율, 승률

사용법:
    from backtester import run_backtest, compute_var, compute_risk_metrics
    result = run_backtest(df, expert_opinions)
    var_result = compute_var(df)
    risk = compute_risk_metrics(df)
"""
import numpy as np
import pandas as pd
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from common.config import get_config

logger = logging.getLogger(__name__)

# config에서 백테스트 설정 로드
_cfg = get_config()
_bt_cfg = _cfg.get("backtest", {})
_VAR_CONFIDENCE = _bt_cfg.get("var_confidence", 0.95)
_VAR_HOLDING_DAYS = _bt_cfg.get("var_holding_days", 1)
_RISK_FREE_RATE = _bt_cfg.get("risk_free_rate", 0.04)  # 연 무위험수익률
_TRADING_DAYS = _bt_cfg.get("trading_days_per_year", 252)


# ─── 데이터 모델 ───

@dataclass
class BacktestResult:
    """백테스트 결과"""
    total_return_pct: float         # 총 수익률 (%)
    annualized_return_pct: float    # 연환산 수익률 (%)
    max_drawdown_pct: float         # 최대 낙폭 (%)
    sharpe_ratio: float             # 샤프 비율
    win_rate_pct: float             # 승률 (%)
    total_trades: int               # 총 거래 수
    winning_trades: int             # 수익 거래 수
    losing_trades: int              # 손실 거래 수
    avg_win_pct: float              # 평균 수익 (%)
    avg_loss_pct: float             # 평균 손실 (%)
    profit_factor: float            # 수익 팩터 (총이익/총손실)
    holding_period_days: int        # 분석 기간 (일)
    strategy_name: str = ""
    trades: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "총수익률": f"{self.total_return_pct:.2f}%",
            "연환산수익률": f"{self.annualized_return_pct:.2f}%",
            "최대낙폭": f"{self.max_drawdown_pct:.2f}%",
            "샤프비율": f"{self.sharpe_ratio:.2f}",
            "승률": f"{self.win_rate_pct:.1f}%",
            "총거래수": self.total_trades,
            "수익거래": self.winning_trades,
            "손실거래": self.losing_trades,
            "평균수익": f"{self.avg_win_pct:.2f}%",
            "평균손실": f"{self.avg_loss_pct:.2f}%",
            "수익팩터": f"{self.profit_factor:.2f}",
            "분석기간": f"{self.holding_period_days}일",
            "전략": self.strategy_name,
        }


@dataclass
class VaRResult:
    """VaR 분석 결과"""
    historical_var: float           # 히스토리컬 VaR (%)
    parametric_var: float           # 파라메트릭 VaR (%)
    conditional_var: float          # CVaR / Expected Shortfall (%)
    confidence_level: float         # 신뢰수준
    holding_days: int               # 보유 기간
    daily_volatility: float         # 일일 변동성 (%)
    annualized_volatility: float    # 연환산 변동성 (%)
    mean_return: float              # 평균 일일 수익률 (%)
    skewness: float                 # 왜도
    kurtosis: float                 # 첨도

    def to_dict(self) -> dict:
        return {
            "히스토리컬VaR": f"{self.historical_var:.2f}%",
            "파라메트릭VaR": f"{self.parametric_var:.2f}%",
            "조건부VaR(CVaR)": f"{self.conditional_var:.2f}%",
            "신뢰수준": f"{self.confidence_level*100:.0f}%",
            "보유기간": f"{self.holding_days}일",
            "일일변동성": f"{self.daily_volatility:.2f}%",
            "연환산변동성": f"{self.annualized_volatility:.2f}%",
            "평균일일수익률": f"{self.mean_return:.4f}%",
            "왜도": f"{self.skewness:.2f}",
            "첨도": f"{self.kurtosis:.2f}",
        }


# ─── 리스크 지표 계산 ───

def compute_daily_returns(df: pd.DataFrame) -> pd.Series:
    """일일 수익률 계산"""
    if "Close" not in df.columns or len(df) < 2:
        return pd.Series(dtype=float)
    returns = df["Close"].pct_change().dropna()
    return returns


def compute_max_drawdown(df: pd.DataFrame) -> float:
    """최대 낙폭(MDD) 계산 (%)"""
    if "Close" not in df.columns or len(df) < 2:
        return 0.0
    prices = df["Close"]
    peak = prices.expanding(min_periods=1).max()
    drawdown = (prices - peak) / peak * 100
    return float(drawdown.min())


def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = None) -> float:
    """샤프 비율 계산"""
    if len(returns) < 2:
        return 0.0
    rfr = risk_free_rate if risk_free_rate is not None else _RISK_FREE_RATE
    daily_rf = rfr / _TRADING_DAYS
    excess = returns - daily_rf
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(_TRADING_DAYS))


def compute_risk_metrics(df: pd.DataFrame) -> dict:
    """종합 리스크 지표 계산"""
    returns = compute_daily_returns(df)
    if len(returns) < 2:
        return {
            "일일변동성": 0.0,
            "연환산변동성": 0.0,
            "최대낙폭": 0.0,
            "샤프비율": 0.0,
            "평균수익률": 0.0,
            "왜도": 0.0,
            "첨도": 0.0,
        }

    daily_vol = float(returns.std() * 100)
    ann_vol = float(returns.std() * np.sqrt(_TRADING_DAYS) * 100)
    mdd = compute_max_drawdown(df)
    sharpe = compute_sharpe_ratio(returns)

    return {
        "일일변동성": daily_vol,
        "연환산변동성": ann_vol,
        "최대낙폭": mdd,
        "샤프비율": sharpe,
        "평균수익률": float(returns.mean() * 100),
        "왜도": float(returns.skew()),
        "첨도": float(returns.kurtosis()),
    }


# ─── VaR 분석 ───

def compute_var(
    df: pd.DataFrame,
    confidence: float = None,
    holding_days: int = None,
) -> VaRResult:
    """
    VaR (Value at Risk) 분석

    Args:
        df: OHLCV DataFrame
        confidence: 신뢰수준 (기본 0.95)
        holding_days: 보유 기간 (기본 1일)

    Returns:
        VaRResult 객체
    """
    confidence = confidence if confidence is not None else _VAR_CONFIDENCE
    holding_days = holding_days if holding_days is not None else _VAR_HOLDING_DAYS
    returns = compute_daily_returns(df)

    if len(returns) < 5:
        logger.warning("VaR 계산에 충분한 데이터 부족")
        return VaRResult(
            historical_var=0.0, parametric_var=0.0, conditional_var=0.0,
            confidence_level=confidence, holding_days=holding_days,
            daily_volatility=0.0, annualized_volatility=0.0,
            mean_return=0.0, skewness=0.0, kurtosis=0.0,
        )

    # 1. 히스토리컬 VaR: 과거 수익률 분위수
    alpha = 1 - confidence
    hist_var = float(np.percentile(returns, alpha * 100))
    hist_var_scaled = hist_var * np.sqrt(holding_days) * 100  # % 단위

    # 2. 파라메트릭 VaR: 정규분포 가정
    from scipy.stats import norm
    z_score = norm.ppf(alpha)
    para_var = float((returns.mean() + z_score * returns.std()) * np.sqrt(holding_days) * 100)

    # 3. 조건부 VaR (CVaR / Expected Shortfall)
    tail = returns[returns <= np.percentile(returns, alpha * 100)]
    cvar = float(tail.mean() * np.sqrt(holding_days) * 100) if len(tail) > 0 else hist_var_scaled

    daily_vol = float(returns.std() * 100)
    ann_vol = float(returns.std() * np.sqrt(_TRADING_DAYS) * 100)

    return VaRResult(
        historical_var=hist_var_scaled,
        parametric_var=para_var,
        conditional_var=cvar,
        confidence_level=confidence,
        holding_days=holding_days,
        daily_volatility=daily_vol,
        annualized_volatility=ann_vol,
        mean_return=float(returns.mean() * 100),
        skewness=float(returns.skew()),
        kurtosis=float(returns.kurtosis()),
    )


# ─── 간이 백테스트 ───

def run_backtest(
    df: pd.DataFrame,
    expert_opinions: list = None,
    initial_capital: float = 10000.0,
    strategy_name: str = "4전문가 컨센서스",
) -> BacktestResult:
    """
    간이 백테스트: 전문가 의견 기반 시뮬레이션

    전략:
    - 매수 다수 → 진입
    - 매도 다수 → 청산
    - 손절가 활용

    Args:
        df: OHLCV DataFrame (기술적 지표 포함)
        expert_opinions: 전문가 의견 리스트
        initial_capital: 초기 자본
        strategy_name: 전략 이름

    Returns:
        BacktestResult
    """
    if len(df) < 10:
        return _empty_result(strategy_name, len(df))

    prices = df["Close"].values
    returns = compute_daily_returns(df)

    # 전문가 의견 기반 파라미터
    if expert_opinions:
        buy_count = sum(1 for o in expert_opinions if o.position == "매수")
        sell_count = sum(1 for o in expert_opinions if o.position == "매도")
        consensus = "매수" if buy_count > sell_count else ("매도" if sell_count > buy_count else "홀드")

        # 매수/매도/손절 목표가 (전문가 평균)
        buy_prices = [o.buy_price for o in expert_opinions if o.buy_price]
        sell_prices = [o.sell_price for o in expert_opinions if o.sell_price]
        stop_losses = [o.stop_loss for o in expert_opinions if o.stop_loss]

        avg_buy = np.mean(buy_prices) if buy_prices else prices[-1] * 0.95
        avg_sell = np.mean(sell_prices) if sell_prices else prices[-1] * 1.15
        avg_stop = np.mean(stop_losses) if stop_losses else prices[-1] * 0.90
    else:
        consensus = "홀드"
        avg_buy = prices[-1] * 0.95
        avg_sell = prices[-1] * 1.15
        avg_stop = prices[-1] * 0.90

    # 단순 시뮬레이션: 히스토리컬 데이터에서 구간별 트레이드
    trades = []
    in_position = False
    entry_price = 0.0
    n = len(prices)
    lookback = min(20, n // 5)

    for i in range(lookback, n):
        price = prices[i]

        if not in_position:
            # 진입 조건: 가격이 평균 매수가 이하로 하락 후 반등
            recent_low = prices[max(0, i-lookback):i].min()
            if price <= recent_low * 1.02 and consensus != "매도":
                in_position = True
                entry_price = price
        else:
            # 청산 조건
            pnl_pct = (price - entry_price) / entry_price * 100
            if price >= avg_sell or price <= avg_stop or pnl_pct >= 15 or pnl_pct <= -10:
                trades.append(pnl_pct)
                in_position = False

    # 미청산 포지션 정리
    if in_position:
        pnl_pct = (prices[-1] - entry_price) / entry_price * 100
        trades.append(pnl_pct)

    # 결과 계산
    if not trades:
        return _empty_result(strategy_name, n)

    winning = [t for t in trades if t > 0]
    losing = [t for t in trades if t <= 0]

    total_return = sum(trades)
    days = n
    ann_return = (total_return / 100 + 1) ** (_TRADING_DAYS / max(days, 1)) - 1
    ann_return *= 100

    gross_profit = sum(winning) if winning else 0
    gross_loss = abs(sum(losing)) if losing else 0.001  # 0 나눗셈 방지

    mdd = compute_max_drawdown(df)
    sharpe = compute_sharpe_ratio(returns)

    return BacktestResult(
        total_return_pct=total_return,
        annualized_return_pct=ann_return,
        max_drawdown_pct=mdd,
        sharpe_ratio=sharpe,
        win_rate_pct=len(winning) / len(trades) * 100 if trades else 0,
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        avg_win_pct=np.mean(winning) if winning else 0,
        avg_loss_pct=np.mean(losing) if losing else 0,
        profit_factor=gross_profit / gross_loss,
        holding_period_days=days,
        strategy_name=strategy_name,
        trades=trades,
    )


def _empty_result(strategy_name: str, days: int) -> BacktestResult:
    """빈 결과 (데이터 부족 시)"""
    return BacktestResult(
        total_return_pct=0.0,
        annualized_return_pct=0.0,
        max_drawdown_pct=0.0,
        sharpe_ratio=0.0,
        win_rate_pct=0.0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        avg_win_pct=0.0,
        avg_loss_pct=0.0,
        profit_factor=0.0,
        holding_period_days=days,
        strategy_name=strategy_name,
    )


def generate_backtest_report(
    bt_result: BacktestResult,
    var_result: VaRResult,
    risk_metrics: dict,
) -> str:
    """백테스트 & VaR 분석 리포트 문자열 생성"""
    L = "━" * 70

    r = f"""
{L}
  📊 백테스트 & 리스크 분석 리포트
{L}

  ┌{'─'*52}┐
  │  전략: {bt_result.strategy_name:44s}│
  │  분석기간: {bt_result.holding_period_days}일                                      │
  ├{'─'*52}┤
  │  총수익률       : {bt_result.total_return_pct:>8.2f}%                           │
  │  연환산수익률   : {bt_result.annualized_return_pct:>8.2f}%                           │
  │  최대낙폭(MDD)  : {bt_result.max_drawdown_pct:>8.2f}%                           │
  │  샤프비율       : {bt_result.sharpe_ratio:>8.2f}                             │
  ├{'─'*52}┤
  │  총거래수: {bt_result.total_trades}건  승률: {bt_result.win_rate_pct:.1f}%                         │
  │  수익거래: {bt_result.winning_trades}건 (평균 +{bt_result.avg_win_pct:.2f}%)                      │
  │  손실거래: {bt_result.losing_trades}건 (평균 {bt_result.avg_loss_pct:.2f}%)                      │
  │  수익팩터: {bt_result.profit_factor:.2f}                                     │
  └{'─'*52}┘

{L}
  ⚠ VaR (Value at Risk) 분석 — 신뢰수준 {var_result.confidence_level*100:.0f}%
{L}
  히스토리컬 VaR : {var_result.historical_var:>8.2f}%  (과거 데이터 기반)
  파라메트릭 VaR : {var_result.parametric_var:>8.2f}%  (정규분포 가정)
  조건부 VaR     : {var_result.conditional_var:>8.2f}%  (최악 시나리오 평균)

  일일 변동성    : {var_result.daily_volatility:.2f}%
  연환산 변동성  : {var_result.annualized_volatility:.2f}%
  평균 일일 수익 : {var_result.mean_return:.4f}%
  왜도(Skewness) : {var_result.skewness:.2f}
  첨도(Kurtosis) : {var_result.kurtosis:.2f}

{L}
  📈 종합 리스크 지표
{L}
"""
    for key, val in risk_metrics.items():
        if isinstance(val, float):
            r += f"  {key:16s}: {val:>8.2f}\n"
        else:
            r += f"  {key:16s}: {val}\n"

    return r
