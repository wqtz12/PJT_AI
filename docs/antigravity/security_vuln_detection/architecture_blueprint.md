# Security Vulnerability Detection System - Architecture Blueprint

## 1. Executive Summary
본 문서는 소스코드를 분석하여 보안 취약점을 탐지하고 조치 보고서를 생성하는 시스템의 아키텍처를 정의합니다.
LLM의 창의성과 재사용 가능한 MCP(Model Context Protocol) 기반 도구의 효율성을 결합하여, **비용 효율적(Cost-Effective)**이고 **확장 가능(Scalable)**한 하이브리드 진단 시스템을 구축합니다.

---

## 2. Technical Stack Recommendation

Anthropic의 MCP 표준을 준수하고, 비동기 처리에 강한 **TypeScript/Node.js** 생태계를 중심으로 구성합니다.

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Core Runtime** | **Node.js (TypeScript)** | MCP SDK의 First-party 지원 및 비동기 I/O 처리에 최적화. |
| **LLM Orchestrator** | **LangGraph** or **Custom Agent** | 복잡한 진단 흐름(Stateful) 제어 및 분기 처리 용이. |
| **MCP Servers** | **TypeScript** | 유지보수 용이성 및 Core Runtime과의 정합성. |
| **Static Analysis (SAST)** | **Semgrep** (via MCP) | 속도가 빠르고 커스텀 룰(Guide.md 반영) 작성이 용이하며 JSON 출력이 명확함. |
| **Knowledge Base** | **In-Memory / File** | 별도의 Vector DB 없이, MCP Tool(Skill)을 통해 가이드 문서를 확정적으로 호출. |
| **Report UI** | **Next.js** + Tailwind CSS | 사용자 규칙 준수 및 보고서 렌더링 최적화. |
| **Main DB** | **PostgreSQL** | 점검 이력, 사용자 세션, 보고서 데이터의 정형 저장. |

---

## 3. System Architecture (Data Flow)

시스템은 'Minimal LLM-heavy' 전략에 따라, 확정적인 도구(SAST)가 1차 필터링을 수행하고 LLM은 고도의 판단이 필요한 영역에 집중합니다.

```mermaid
graph TD
    User[사용자] -->|Source Code / Git URL| Controller[Workflow Controller]
    
    subgraph "Phase 1: Preparation"
        Controller -->|Read| FS_MCP[File System MCP]
        Controller -->|Parsing & Scope| Parser[Code Parser]
    end
    
    subgraph "Phase 2: Hybrid Analysis"
        Controller -->|1. Rule-based Scan| SAST_MCP[SAST MCP (Semgrep/ESLint)]
        SAST_MCP -->|Raw Findings| Filter[Findings Filter]
        
        Filter -->|2. Context Injection| Guide_Skill[Security Guide Skill (MCP)]
        Guide_Skill -->|Relevant Rules| LLM_Reviewer[LLM Verifier]
        
        Filter -->|Candidate Code Snippets| LLM_Reviewer
        LLM_Reviewer -->|3. Verify False Positives| LLM_Reviewer
    end
    
    subgraph "Phase 3: Reporting"
        LLM_Reviewer -->|Verified Vulnerabilities| DB[(PostgreSQL)]
        DB -->|Generate| Report_Gen[Report Generator]
        Report_Gen --> User
    end
```

### Data Flow Steps
1.  **Ingestion**: 사용자가 소스코드를 업로드하거나 Git URL을 제공.
2.  **Detection (Tool-First)**: `SAST MCP`를 호출하여 XSS, SQLi 등 패턴 기반 취약점을 1차 식별. 이 단계에서는 LLM을 사용하지 않음 (비용 절감).
3.  **Enrichment**: 탐지된 취약점 유형에 맞는 보안 가이드(JS 시큐어코딩 등)를 KB에서 조회.
4.  **Verification (LLM)**: SAST 결과(오탐 가능성 있음)와 관련 코드 스니펫, 보안 가이드를 LLM에 프롬프트로 전달하여 **실제 취약점 여부(True Positive)** 판단 및 수정 방안 생성.
5.  **Reporting**: 확정된 취약점에 대해 보고서 포맷(PDF/HTML)으로 변환.

---

## 4. Skills & MCP Design

모듈식 확장을 위해 핵심 기능을 MCP 서버로 분리하고, LLM이 이를 Skill 형태로 호출합니다.

### A. Core MCP Servers

#### 1. `analysis-mcp-server`
*   **Role**: 정적 분석 도구 실행 래퍼.
*   **Tools**:
    *   `run_semgrep_scan(path: string, ruleset: string[])`: 지정된 경로에 대해 Semgrep 스캔 수행.
    *   `parse_language_structure(file_path: string)`: AST 파싱을 통해 함수/클래스 구조 추출 (Context 확보용).

#### 2. `knowledge-mcp-server`
*   **Role**: 보안 가이드라인 제공 (File-based Skill).
*   **Tools**:
    *   `get_security_guide(category: string)`: "XSS", "SQL Injection" 등 카테고리별 가이드 전문 로드.
    *   `list_guide_categories()`: 이용 가능한 가이드 목차 조회.

#### 3. `filesystem-mcp-server` (Standard)
*   소스코드 읽기/쓰기 접근 제어.

### B. LLM Skills Strategy

LLM은 전체 코드를 읽는 대신, MCP 도구가 좁혀준 '관심 영역(Region of Interest)'에 집중합니다.

*   **Skill: `verify_vulnerability`**
    *   **Input**: `code_snippet`, `sast_finding`, `security_rule_context`
    *   **Logic**: "SAST 도구가 15번 라인에서 SQL Injection을 탐지했다. 하지만 코드를 보면 ORM을 사용하고 있어 오탐일 수 있다. 보안 가이드 제3조(입력값 검증)에 의거하여 실제 위협인지 판단하라."
    *   **Output**: `IsVulnerable (bool)`, `Reasoning`, `SuggestedFix`

---

## 5. Operational & Cost Optimization Strategy

### A. Minimal LLM-heavy Strategy (Token 절감)
1.  **"Don't Read All"**: 소스코드 전체를 프롬프트에 넣지 않습니다. SAST 도구가 지적한 파일과 라인 주변(Context Window)만 추출하여 LLM에 전달합니다.
2.  **Structured Output**: LLM의 응답을 길게 서술하는 대신, JSON 스키마를 강제하여 `Status`, `Severity`, `FixCode`만 명확히 받습니다.

### B. Guide.md based Prompting
*   **Prompt Caching**: `Guide.md` (JS 시큐어코딩 가이드 등 고정된 컨텍스트)는 Anthropic의 Prompt Caching 기능을 사용하여 캐싱합니다. 반복 호출 시 비용을 최대 90% 절감하고 응답 속도를 높입니다.
*   **Rule Reference**: LLM이 자의적으로 판단하지 않도록, 반드시 "가이드 문서의 섹션 4.2에 따라 위반임"과 같이 근거를 명시하도록 지시합니다.

### C. Tiered Analysis
*   **Level 1 (Fast)**: MCP 도구만 사용하는 순수 패턴 매칭. (비용 0에 수렴)
*   **Level 2 (Deep)**: Level 1에서 탐지된 항목 중 'High/Critical' 등급만 LLM 검증 수행.
*   **Level 3 (Audit)**: 사용자가 요청한 특정 파일만 심층 분석.

---

## 6. Conclusion
제안된 아키텍처는 **MCP를 통한 도구의 확장성**과 **LLM의 인지 능력**을 결합하되, **비용 효율성**을 최우선으로 고려했습니다. Semgrep 등의 강력한 SAST 도구를 1차 방어선으로 구축하고, LLM은 전문 보안 감사자(Auditor)처럼 최종 판단과 가이드 제시에만 집중함으로써 빠르고 정확한 보안 리포트를 제공할 수 있습니다.
