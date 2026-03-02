# Automated Trading System Implementation Plan

## Goal Description
Build a fully automated trading system that leverages the existing 4-Skill Analysis Pipeline (`StockAgent`, `NewsAgent`, `MacroAgent`, `ExpertAgent`) to execute trades autonomously on crypto (Upbit) and stock (Kiwoom) markets.

## User Review Required
> [!IMPORTANT]
> **Real Money Trading**: Phase 2 involves real API keys. Ensure `UPBIT_ACCESS_KEY` and `UPBIT_SECRET_KEY` are secured.
> **Risk Management**: Review the default risk limits (Max 10% per trade, Max 3% loss) in `RiskManager`.

## Proposed Changes

### Phase 1: Foundation (Architecture & Scheduling)
#### [NEW] `src/auto_trading/scheduler.py`
- Iterate using `APScheduler`.
- Jobs:
    - `run_crypto_analysis`: Every 1 hour.
    - `run_stock_analysis`: Daily at 08:30 KST.

#### [NEW] `src/auto_trading/signal_generator.py`
- Wrapper around `main_system.py` logic.
- Returns structured `Signal` objects instead of printing to console.

### Phase 2: Execution Engine
#### [NEW] `src/auto_trading/executor/base.py`
- Abstract base class `TradeExecutor`.
- Methods: `buy(asset, amount)`, `sell(asset, amount)`, `get_balance()`.

#### [NEW] `src/auto_trading/executor/paper.py`
- Mock implementation for testing.
- Tracks virtual balance and trade history in memory/file.

#### [NEW] `src/auto_trading/executor/upbit.py`
- Real implementation using `pyupbit`.
- Handles API errors and rate limits.

### Phase 3: Risk & Position Management
#### [NEW] `src/auto_trading/risk_manager.py`
- Gatekeeper logic.
- Input: `Signal`, `AccountBalance`.
- Logic:
    - IF `daily_loss > max_daily_loss`: Reject.
    - IF `trade_amount > max_trade_size`: Cap amount.

#### [NEW] `src/auto_trading/portfolio.py`
- Tracks active positions.
- Persists state to `portfolio.json` or `sqlite`.
- Implements Trailing Stop logic.

### Phase 4: Notification & Dashboard
#### [NEW] `src/auto_trading/notification.py`
- Telegram bot integration.
- Sends alerts for Buy/Sell/StopLoss events.

#### [NEW] `src/auto_trading/dashboard.py` (CLI)
- Simple text-based dashboard showing PnL and active positions.

## Verification Plan

### Automated Tests
1. **Scheduler Test**: Verify jobs trigger at correct intervals.
2. **Signal Test**: Ensure `SignalGenerator` produces valid signals from mock market data.
3. **Paper Trading**: Run a 24-hour loop with `PaperExecutor` and verify PnL calculation.

### Manual Verification
1. **Dry Run**: Run the system with `PaperExecutor` and check logs.
2. **Exchange Config**: Verify Upbit API connection (get balance).
