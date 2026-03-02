# KIS Automated Trading System Architecture Design

## 1. System Overview
본 시스템은 기존의 분석 시스템(Signal Generator)과 연동하여 한국투자증권(KIS) API를 통해 국내 및 해외 주식의 자동 매매를 수행하는 실행 엔진(Execution Engine)입니다.

## 2. System Context Diagram (Level 0)
```mermaid
graph TD
    User((User)) -->|Monitoring & Control| WebDash[Web Dashboard / Admin]
    Analysis[Analysis System\n(Signal Generator)] -->|Trade Signals| AutoTrading[**Auto Trading System**]
    
    AutoTrading -->|Order/Inquiry| KIS_API((KIS Open API))
    KIS_API -->|Execution/Balance| AutoTrading
    
    AutoTrading -->|Log/Status| DB[(Database)]
    AutoTrading -->|Notification| Messenger((Slack/Telegram))
```

## 3. Container Diagram (Level 1)
시스템은 다음과 같은 독립적인 컨테이너로 구성됩니다.

```mermaid
graph TB
    subgraph "Auto Trading System"
        API_GW[API Gateway / Controller]
        
        OrderMgr[**Order Manager**\n(Strategy & Validation)]
        RiskMgr[**Risk Manager**\n(Limit & Safety)]
        
        Scheduler[**Scheduler**\n(Cron & Market Time)]
        
        subgraph "Executor Layer"
            KIS_Dom[**Domestic Executor**\n(KRW Stocks)]
            KIS_Ovr[**Overseas Executor**\n(USD Stocks)]
        end
        
        DB_Adapter[Persistence Adapter]
    end
    
    Analysis -->|REST/gRPC| API_GW
    
    API_GW --> OrderMgr
    OrderMgr --> RiskMgr
    RiskMgr -->|Approved| OrderMgr
    OrderMgr -->|Execute| KIS_Dom
    OrderMgr -->|Execute| KIS_Ovr
    
    Scheduler -->|Trigger| OrderMgr
    
    KIS_Dom -->|REST| KIS_API
    KIS_Ovr -->|REST| KIS_API
    
    OrderMgr --> DB_Adapter
    DB_Adapter --> DB
```

## 4. Component Design (Level 2)

### 4.1 Order Manager
*   **Role**: 트레이딩 시그널 수신, 주문 생성, 분할 매매 로직 수행.
*   **Key Classes**:
    *   `SignalReceiver`: 외부 시그널 수신 (Webhook/Voting).
    *   `OrderStrategy`: 분할 매수/매도 알고리즘 (SplitOrder).
    *   `TradeState`: 주문 상태 관리 (Pending, Partial, Filled).

### 4.2 Risk Manager
*   **Role**: 주문 전 리스크 검증 및 실행 차단.
*   **Key Checks**:
    *   `MaxDailyLoss`: 일일 최대 손실 한도 초과 여부.
    *   `OrderLimit`: 1회 주문 최대 금액 제한.
    *   `DuplicateCheck`: 동일 종목 중복 주문 방지.
    *   `BalanceCheck`: 미수 발생 가능성(예수금 부족) 사전 차단.

### 4.3 KIS Executor (Domestic & Overseas)
*   **Role**: 실제 KIS API 호출 및 토큰 관리.
*   **Key Modules**:
    *   `AuthManager`: Access Token 발급 및 갱신 (Invalid Token 처리).
    *   `RateLimiter`: API 호출 횟수 제한 (Leaky Bucket 알고리즘).
    *   `KisDomestic`: 국내 주식 API 래퍼 (mojito2 활용/확장).
    *   `KisOverseas`: 해외 주식 API 래퍼 (직접 구현).
    *   `ExchangeService`: 환전 및 환율 조회.

### 4.4 Data Persistence
*   **Database**: SQLite (초기) -> PostgreSQL (운영).
*   **Schema**:
    *   `orders`: 주문 내역 (order_id, symbol, qty, price, status, created_at).
    *   `trades`: 체결 내역 (trade_id, order_id, exec_price, exec_qty, fee).
    *   `daily_summary`: 일별 손익 현황.

## 5. Deployment View
*   **Environment**: Docker Compose 기반 컨테이너 환경.
*   **Network**: Internal Network (App <-> DB), External Network (App -> KIS API).
*   **Volume**: API Token, Log, DB Data 영구 저장.

## 6. Interface Specifications
*   **Internal**: Python AsyncIO (Module 간 호출).
*   **External**: REST API (KIS), Webhook (Signal).

