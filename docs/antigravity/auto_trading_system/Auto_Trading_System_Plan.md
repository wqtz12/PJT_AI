# KIS Automated Trading System Planning Document

## 1. 개요 (Overview)
본 문서는 한국투자증권(KIS) openAPI를 활용하여 국내 및 해외 주식의 자동 매매를 수행하는 시스템 구축을 위한 기획서입니다.
기존 구축된 '종목 분석 및 매매가 산출 시스템'과 연동하여, 실제 주문을 집행하고 계좌를 관리하는 **Execution Layer**에 초점을 맞춥니다.

## 2. 시스템 목표 (Goals)
1. **국내/해외 통합 매매**: 한국 주식(KOSPI, KOSDAQ) 및 미국 주식(NASDAQ, NYSE, AMEX) 자동 매매 지원.
2. **신뢰성 있는 실행**: API Rate Limit 준수, 토큰 만료 자동 갱신, 네트워크 예외 처리를 통한 안정적 운영.
3. **리스크 관리**: 주문 한도 설정, 미수 발생 방지, 손실 제한(Stop-loss) 로직 탑재.
4. **확장성**: 추후 다른 증권사나 자산군(코인 등)으로의 확장이 용이한 구조 설계.

## 3. 시스템 아키텍처 (Architecture)

### 3.1 전체 구조
```mermaid
graph TD
    A[Signal Generator\n(Analysis System)] -->|Trade Signal| B(Order Manager)
    B -->|Order Strategy| C{Execution Engine}
    
    subgraph "KIS Executor Module"
        C -->|Domestic| D[Domestic Trader]
        C -->|Overseas| E[Overseas Trader]
        D -->|Rest API| F(("KIS Open API\n(Domestic)"))
        E -->|Rest API| G(("KIS Open API\n(Overseas)"))
    end
    
    H[Risk Manager] -.->|Check Limit| B
    C -->|Log/Result| I[Trade Database]
    F -->|Balance/Pos| J[Account Manager]
    G -->|Balance/Pos| J
```

### 3.2 핵심 모듈 정의
1.  **Order Manager**: 분석 시스템의 시그널(매수/매도/비중)을 받아 실제 주문 가능 여부를 판단하고 분할 주문 등의 전략을 수립합니다.
2.  **KIS Executor**:
    *   **Auth Handler**: Access Token 발급 및 자동 갱신 (1일 1회 또는 만료 시).
    *   **Domestic Trader**: 국내 주식 주문, 정정, 취소 (모의/실전).
    *   **Overseas Trader**: 해외 주식 주문, 환전(필요 시), 정정, 취소.
3.  **Risk Manager**:
    *   주문당 최대 금액 제한.
    *   일일 최대 손실폭 도달 시 매매 중단.
    *   중복 주문 방지.
4.  **Account Manager**: 예수금(원화/달러) 조회, 보유 종목 수익률 실시간 모니터링.

## 4. 상세 기능 명세 (Functional Specifications)

### 4.1 인증 및 보안 (Authentication & Security)
*   **App Key/Secret 관리**: 환경 변수(`.env`) 또는 안전한 Vault를 통해 관리.
*   **Token Lifecycle**:
    *   앱 초기 구동 시 토큰 발급.
    *   Websocket 접속키 별도 관리 (실시간 체결 통보용).
    *   `Hash Key` 생성 로직 (POST 요청 데이터 보안).

### 4.2 국내 주식 트레이딩 (Domestic Trading)
*   **주문 유형**: 지정가, 시장가, 조건부지정가.
*   **운영 시간**: 09:00 ~ 15:30 (장중 매매).
*   **특이 사항**: `mojito` 라이브러리 활용 또는 직접 REST API 구현 (기존 `kis.py` 확장).

### 4.3 해외 주식 트레이딩 (Overseas Trading)
*   **대상 국가**: 미국 (USA).
*   **주문 유형**: 지정가(Limit), 시장가(Market - 브로커에 따라 제한적일 수 있음), LOC/MOC.
*   **운영 시간**: 프리마켓, 정규장, 애프터마켓 대응 설정.
*   **환전**:
    *   자동 환전 설정 여부 확인.
    *   예수금 부족 시 매수 불가 처리 로직.
    *   **통화 코드**: USD (미국 달러).

### 4.4 모니터링 및 로깅 (Monitoring & Logging)
*   **실시간 체결 확인**: REST API 폴링(Polling) 방식 또는 WebSocket 활용.
*   **알림**: 매매 체결 시 Slack/Telegram 알림 전송.
*   **로그**: 일자별/종목별 매매 이력 파일 저장 및 DB 적재.

### 4.5 상세 매매 로직 (Detailed Trading Logic)
사용자의 구체적인 요구사항을 반영한 매매 프로세스를 정의합니다.

1.  **파라미터 수신 (Input)**:
    *   분석 시스템(Signal Generator)으로부터 `종목명`, `3분할 매수 금액`, `3분할 매도 금액`을 수신.
2.  **종목 코드 추출 및 검증 (Symbol Resolution)**:
    *   수신된 `종목명`을 기반으로 KIS 마스터 파일 또는 API를 통해 종목 코드 검색.
    *   **User Interaction**: 검색된 종목 코드가 **2개 이상**일 경우, 사용자에게 질문하여 정확한 대상을 선정 (재질의 프로세스).
3.  **분할 매수 실행 (Split Buy Execution)**:
    *   선정된 코드로 확정 시, 입력받은 `3분할 매수 금액`에 맞춰 순차적 또는 동시 호가 주문.
    *   시장가 또는 지정가(최우선 매도호가) 활용.
4.  **매도 주문 및 손절 설정 (Sell & Stop-loss)**:
    *   매수 체결 확인 즉시 `3분할 매도 금액` 기준으로 **이익 실현(Take Profit) 주문** 접수.
    *   **Trailing Stop**: 손실 제한을 위해 트레일링 스탑 조건 감시 시작 (고점 대비 하락 비율로 매도 트리거).

## 5. 기술 스택 및 환경 (Tech Stack)
*   **Language**: Python 3.10+
*   **Libraries**:
    *   `requests` (API 호출)
    *   `mojito2` (국내 주식 래퍼, 해외 주식 미지원 시 직접 구현 필요)
    *   `pandas` (데이터 관리)
    *   `apscheduler` (스케줄링)
*   **Infra**: Docker Container (24h 운영)

## 6. 개발 로드맵 (Roadmap)

### Phase 1: 기반 구축 (Current)
*   [x] 국내 주식 기본 매매 기능 구현 (`kis.py`)
*   [ ] 토큰 자동 갱신 및 유효성 검증 로직 추가

### Phase 2: 해외 주식 확장
*   [ ] 해외 주식 주문 (매수/매도) API 연동
*   [ ] 해외 잔고 및 미체결 내역 조회 기능 구현
*   [ ] 환율 조회 및 환전 로직 검토

### Phase 3: 통합 및 고도화
*   [ ] Risk Manager 연동 (주문 필터링)
*   [ ] 통합 스케줄러 구축 (국내/해외 장 운영 시간 자동 대응)
*   [ ] 실전 배포 및 모니터링 대시보드 연동

## 7. 잠재적 리스크 및 대응 방안 (Potential Risks & Countermeasures)

### 7.1 프로세스 블로킹 리스크 (Critical)
*   **이슈**: 종목 코드 중복 시 **사용자 질문(User Interaction)** 단계가 전체 매매 루프를 차단(Blocking)할 수 있습니다.
*   **대응**:
    *   **Timeout 설정**: 사용자 응답이 $N$초(예: 30초) 내에 없으면 해당 종목 매수를 포기하고 다음 시그널로 넘어가는 Non-blocking 로직 구현.
    *   **메신저 연동**: 터미널 입력이 아닌 Slack/Telegram 버튼 클릭으로 종목을 선택하도록 하여 시스템과 UI 분리.

### 7.2 체결 불일치 및 상태 관리 (State consistency)
*   **이슈**: 매수 주문은 나갔으나 체결되지 않고 잔량이 남거나, 일부만 체결된 상태에서 프로그램이 종료될 경우 데이터 정합성 깨짐.
*   **대응**:
    *   **DB 기반 상태 관리**: 메모리 변수가 아닌 SQLite/PostgreSQL에 주문 상태(Pending/PartiallyFilled/Filled)를 기록.
    *   **재구동 시 복구 로직**: 시스템 시작 시 KIS 미체결 내역 및 잔고를 조회하여 DB 상태와 동기화(Reconciliation).

### 7.3 분할 주문 및 API 제한 (Rate Limit)
*   **이슈**: 3분할 매수/매도 시 짧은 시간에 API 호출이 집중되어 `Rate Limit(초당 건수 제한)`에 걸릴 수 있음.
*   **대응**:
    *   **Command Queue**: 주문 요청을 큐(Queue)에 넣고, `RateLimiter`가 초당 허용 횟수(예: 0.2초당 1건)에 맞춰 순차적으로 API 전송.
    *   **Batch Order**: 가능할 경우 일괄 주문 API 활용 검토.

### 7.4 갭 하락 및 트레일링 스탑 실패 (Slippage)
*   **이슈**: 급락 시 트레일링 스탑 트리거 가격보다 훨씬 낮은 가격에 체결되거나, 하한가로 인해 매도 불가할 수 있음.
*   **대응**:
    *   **시장가(Market) 매도**: 손절 트리거 발동 시 지정가가 아닌 시장가로 즉시 탈출.
    *   **오버나이트 리스크 관리**: 장 종료 전 강제 청산(Liquidate on Close) 옵션 도입 고려.

## 8. 결론 (Conclusion)
본 시스템은 안정적인 자산 증식을 목표로 하며, 기계적이고 원칙에 입각한 매매를 수행하도록 설계됩니다. 초기에는 국내 주식 위주로 안정성을 검증하고, 이후 해외 주식으로 포트폴리오를 다변화하는 단계적 접근을 권장합니다.
