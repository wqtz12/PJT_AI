# KIS Automated Trading System Functional Specifications

## 1. Functional Requirements

### 1.1 Order Management
1.  **Split Order Execution**:
    *   **Input**: `Symbol`, `Total Buy Amount`, `Total Sell Amount`, `Split Count` (Default: 3).
    *   **Logic**:
        *   Calculate `Order Amount` = `Total Buy Amount` / `Split Count`.
        *   Execute buy orders sequentially or simultaneously based on strategy.
        *   Upon full execution of buy orders, immediately place sell orders (Take Profit).
    *   **Output**: List of `Order IDs` and execution status.

2.  **Symbol Resolution**:
    *   **Input**: Stock Name (e.g., "Samsung Electronics").
    *   **Logic**:
        *   Search local master file or KIS API for symbol code.
        *   If multiple matches found -> **Prompt User** for selection (Slack/Terminal).
        *   If no match -> Log error and skip.
    *   **Output**: Standard Symbol Code (e.g., "005930").

3.  **Trailing Stop**:
    *   **Input**: `Entry Price`, `Current Price`, `Trailing Step` (%).
    *   **Logic**:
        *   Track highest price since entry.
        *   If `Current Price` <= `Highest Price` * (1 - `Trailing Step`), trigger **Market Sell**.

### 1.2 KIS Interface (Domestic)
1.  **Authentication**:
    *   Auto-refresh Access Token every 24 hours.
    *   Handle `vt` (Virtual Training) vs `Real` environment switch.
2.  **Trading**:
    *   Support `Limit` (Specified Price) and `Market` orders.
    *   Support `Modify` and `Cancel` orders.
3.  **Inquiry**:
    *   Real-time balance check (`KRW`).
    *   Current holdings and P&L status.

### 1.3 KIS Interface (Overseas - USA)
1.  **Authentication**:
    *   Same token structure as Domestic (check if separate token needed for overseas).
2.  **Trading**:
    *   Support `Limit`, `Market`, `LOC`, `MOC` orders.
    *   **Extended Hours**: Pre-market / After-market order flag support.
3.  **Currency Management**:
    *   Check `USD` balance before ordering.
    *   (Optional) Auto-currency conversion execution.

### 1.4 Risk Management
1.  **Pre-Trade Checks**:
    *   **Budget Limit**: Order amount <= Available Cash * 0.95 (Buffer).
    *   **Daily Loss Limit**: If Daily P&L < -X%, halt all new buys.
    *   **Fat Finger Check**: Reject if Price deviates > 10% from current market price.

## 2. Data Flow Specifications

### 2.1 Signal Input Format (JSON)
```json
{
  "timestamp": "2024-05-20T10:00:00",
  "symbol_name": "Tesla",
  "action": "BUY",
  "total_budget": 1000000,
  "target_sell_price": 1100000,
  "strategy": "SPLIT_3"
}
```

### 2.2 Execution Log Format (CSV/DB)
| Timestamp | OrderID | Symbol | Type | Side | Price | Qty | Status | Message |
|-----------|---------|--------|------|------|-------|-----|--------|---------|
| 10:00:01 | 1001 | 005930 | LIMIT | BUY | 70000 | 10 | FILLED | Success |

## 3. Error Handling & Recovery

### 3.1 API Failures
*   **429 Too Many Requests**: Pause for 1 sec, then retry (Max 3 retries).
*   **5xx Server Error**: Log critical error, send alert, and pause system for 5 min.
*   **Token Expired**: Immediate token refresh and retry original request.

### 3.2 Network Disconnect
*   If heartbeat fails or request timeouts > 3 times:
    *   Cancel all pending (non-filled) orders (Safety Net).
    *   Send "Emergency Stop" alert to admin.

## 4. Configuration Parameters (`config.yaml`)
```yaml
system:
  mode: "REAL" # or MOCK
  log_level: "INFO"

kis:
  app_key: "${KIS_APP_KEY}"
  app_secret: "${KIS_APP_SECRET}"
  account_no: "${KIS_ACCOUNT_NO}"

risk:
  max_daily_loss_pct: 3.0
  max_order_amount: 1000000
  trailing_stop_step: 2.0
```
