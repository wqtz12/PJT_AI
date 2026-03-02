# AMXIS Audit Shield System Architecture

## 1. 아키텍처 개요 (Architecture Overview)

**AMXIS Audit Shield**는 민감한 재무 및 소스코드 데이터를 다루므로 **보안성(Security), 독립성(Isolation), 경량화(Lightweight)**를 3대 원칙으로 설계되었습니다.

### 1.1 핵심 설계 원칙
*   **On-premise First**: 외부 인터넷 연결이 차단된 폐쇄망에서도 100% 기능 동작.
*   **Zero Data Leakage**: 데이터의 외부 유출 경로를 원천 차단 (Local LLM/OCR 사용).
*   **Resource Optimized**: 고가의 GPU 장비 없이 일반 CPU 서버에서 구동 가능한 경량 모델 채택.

---

## 2. 시스템 컨텍스트 (System Context - Top Level)

```mermaid
C4Context
    title System Context Diagram for AMXIS Audit Shield

    Person(developer, "Developer", "소스코드 커밋 및 배포 수행")
    Person(finance, "Finance Staff", "증빙 업로드 및 감사 대응")
    Person(auditor, "Auditor", "내부회계 감사 및 리포트 조회")

    System_Boundary(amxis_boundary, "AMXIS Audit Shield Protocol") {
        System(amxis, "AMXIS System", "내부통제 자동화 및 증빙 분석 플랫폼")
    }

    System_Ext(git, "Git Server", "GitLab/GitHub Enterprise (On-prem)")
    System_Ext(erp, "Legacy ERP", "SAP, Douzone etc. (Financial Data)")
    System_Ext(sso, "SSO / LDAP", "사내 인증 시스템")

    Rel(developer, git, "Commits code")
    Rel(git, amxis, "Webhook triggers Audit (Push/Merge)")
    
    Rel(finance, amxis, "Uploads receipts/docs")
    Rel(amxis, erp, "Cross-checks financial data")
    
    Rel(auditor, amxis, "Reviews Audit Reports")
    Rel(developer, amxis, "Checks Code Violation Logs")
    
    Rel(amxis, sso, "Authenticates users")
```

---

## 3. 컨테이너 아키텍처 (Container Architecture)

시스템은 **Docker Compose** 기반의 마이크로서비스 구조로 배포되며, 크게 **Frontend, Backend, AI Engine, Persistence** 계층으로 나뉩니다.

```mermaid
C4Container
    title Container Diagram

    Container(web, "Web Reference", "Next.js", "사용자 대시보드 및 리포트 UI 제공")
    Container(api, "API Gateway / Backend", "Python FastAPI", "REST API, 인증/권한, 비즈니스 로직 처리")

    Container_Boundary(ai_layer, "AI Intelligence Layer") {
        Container(semgrep, "Semgrep Runner", "CLI/Sidecar", "소스코드 정적 분석 엔진 (CPU Optimized)")
        Container(ocr, "Evidence Processor", "PaddleOCR (Python)", "영수증/문서 텍스트 추출 (CPU Mode)")
        Container(llm, "Context Cloud", "Ollama (Phi-3-mini)", "텍스트 요약 및 문맥 분석 (Local LLM)")
    }

    Container_Boundary(data_layer, "Persistence Layer") {
        ContainerDb(rdb, "Core DB", "PostgreSQL", "사용자 정보, 감사 로그, 메타데이터 저장")
        ContainerDb(vec, "Vector Store", "ChromaDB", "규정집 임베딩 및 유사 증빙 검색")
        ContainerDb(obj, "Object Storage", "MinIO (Optional)", "증빙 이미지 원본 저장 (Encrypted)")
    }

    Rel(web, api, "Uses", "HTTPS/JSON")
    
    Rel(api, semgrep, "Triggers Scan", "gRPC/Process")
    Rel(api, ocr, "Sends Images", "Queue (Redis)")
    Rel(api, llm, "Requests Summary", "REST API")
    
    Rel(api, rdb, "Reads/Writes", "SQL")
    Rel(api, vec, "Semantic Search", "gRPC")
    Rel(api, obj, "Stores/Retrieves", "S3 Protocol")
```

---

## 4. 컴포넌트 상세 설계 (Component Design)

### 4.1 Code Audit Engine
*   **Tech**: Semgrep CLI
*   **Role**: Git Webhook 수신 시 트리거되어 변경된 코드의 AST(Abstract Syntax Tree)를 분석.
*   **Ruleset**: `rule.yaml` 파일로 관리되며, 재무 로직 변조(e.g., `if (amount > limit) bypass()`) 패턴을 탐지.
*   **Optimization**: 변경된 파일만 검사하는 Incremental Scan 적용.

### 4.2 Evidence Processor
*   **Tech**: PaddleOCR (Detection/Recognition) + Phi-3-mini
*   **Process**:
    1.  **Preprocessing**: 이미지 노이즈 제거 및 회전 보정.
    2.  **OCR**: 텍스트 및 좌표 추출 (CPU 병렬 처리).
    3.  **Parsing (LLM)**: 추출된 텍스트 파편(Tokens)을 Phi-3-mini에 입력하여 `{"date": "...", "amount": 10000, "vendor": "..."}` 형태의 JSON으로 구조화.

### 4.3 RAG Engine (ChromaDB)
*   **Tech**: ChromaDB + Hybrid Search
*   **Role**: 과거 감사 지적 사례 및 내부 회계 규정 검색.
*   **Filtering**: `where={"dept": "finance", "year": "2024"}`와 같은 메타데이터 필터링을 통해 검색 정확도 향상.

---

## 5. 데이터 흐름 (Data Flow)

### Scenario: 증빙 자동 감사 (Auto Audit Flow)

```mermaid
sequenceDiagram
    participant User as Finance User
    participant API as API Server
    participant OCR as OCR Worker
    participant LLM as Phi-3 (Ollama)
    participant DB as PostgreSQL
    participant RAG as ChromaDB

    User->>API: 증빙 이미지 업로드
    API->>DB: 메타데이터 저장 (Status: Processing)
    API->>OCR: 작업 큐(Queue) 전송
    
    OCR->>OCR: 이미지 텍스트 추출 (PaddleOCR)
    OCR->>LLM: 텍스트 구조화 요청 (Extract JSON)
    LLM-->>OCR: 구조화된 데이터 반환
    
    OCR->>RAG: 유사 증빙/규정 검색 (위반 여부 판단용)
    RAG-->>OCR: 관련 규정 Top-3 반환
    
    OCR->>API: 분석 결과 전송
    API->>DB: 결과 저장 및 위반 Flag 업데이트
    API-->>User: 분석 완료 알림 (Dashboard 갱신)
```

---

## 6. 인프라 요구사항 (Infrastructure Requirements)

**Minimum Hardware Specs (On-premise)**

| 구분 | 사양 (Specification) | 비고 |
| :--- | :--- | :--- |
| **CPU** | 8 Core 이상 (Modern Arch) | AVX2 지원 권장 (OCR/Vector 연산 가속) |
| **RAM** | 32GB 이상 | LLM(4GB) + ChromaDB + App + OS |
| **Storage** | SSD 500GB 이상 | DB 및 증빙 이미지 저장 공간 |
| **Network** | 1Gbps Internal LAN | 외부 인터넷 연결 불필요 (Air-gapped) |
| **OS** | Linux (Ubuntu 22.04 LTS) | Docker Engine 필수 설치 |

---

## 7. 보안 설계 (Security Implementation)

*   **Ingress**: Nginx Reverse Proxy (TLS 1.3 Termination).
*   **Internal**: 컨테이너 간 통신은 Docker Internal Network 내에서만 허용.
*   **Storage**: MinIO 및 PostgreSQL 데이터 볼륨은 호스트 레벨에서 LUKS 암호화 적용 권장.
*   **Audit Trail**: 모든 API 요청은 Hash Chaining되어 `audit_logs` 테이블에 위변조 불가능한 상태로 기록.
