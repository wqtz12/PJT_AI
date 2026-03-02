# AMXIS Audit Shield - Screen Design Document

## 1. 개요
AMXIS Audit Shield 시스템의 사용자 인터페이스(UI) 설계서입니다.
사용자 역할(감사자, 시스템 담당자, 결재자)에 따른 화면 구성과 주요 기능 흐름을 정의합니다.

## 2. 사용자 역할 및 주요 기능

| 역할 | 주요 기능 | 주요 화면 |
|------|-----------|-----------|
| **Auditor (감사자)** | 감사 일정 등록, 랜덤 샘플링 실행, 진행 현황 모니터링, 최종 승인 | 감사 대시보드, 일정 등록, 감사 상세 |
| **Owner (담당자)** | 증빙 요청 확인, AI 분석 결과 검토, 수동 증빙 업로드, 소명 작성 | 나의 할 일(To-Do), 증빙 확인/제출 |
| **Approver (팀장)** | 감사 일정 알림 수신, 이슈사항 모니터링 | (이메일 리포트 중심), 대시보드 조회 |

---

## 3. Sitemap & Flow

```mermaid
graph TD
    Login[로그인] --> Main[메인 대시보드]
    
    %% Auditor Flow
    Main -->|Auditor| ScheduleList[감사 일정 관리]
    ScheduleList --> ScheduleNew[신규 감사 등록]
    ScheduleList --> AuditDetail[감사 상세 (진행상태)]
    AuditDetail --> Sampling[랜덤 샘플링 & AI 분석 실행]
    AuditDetail --> FinalReport[최종 리포트]
    
    %% Owner Flow
    Main -->|Owner| MyTasks[나의 증빙 요청 목록]
    MyTasks --> TaskDetail[증빙 검토/제출]
    TaskDetail -->|AI 분석 완료| ReviewAI[AI 매핑 결과 확인]
    TaskDetail -->|분석 불가| ManualUpload[수동 증빙 업로드]
    ReviewAI --> Confirm[확정]
    ManualUpload --> Confirm
```

---

## 4. 상세 화면 설계

### 4.1. 공통 - 메인 대시보드 (Main Dashboard)
**목적:** 사용자의 역할에 따른 주요 지표 및 할 일 요약 제공

- **Auditor View**
  - **KPI Cards**: `진행 중인 감사`, `증빙 제출 지연`, `AI 분석 성공률`, `오늘 마감 일정`
  - **Status Chart**: 시스템별 증빙 확보율 (그래프)
  - **Recent Activity**: 최근 등록된 감사 일정 또는 제출된 증빙 로그

- **Owner View**
  - **Alert Banner**: "확인이 필요한 증빙 요청이 3건 있습니다." (긴급도 표시)
  - **Task List**: 
    - `[D-2] Payment Gateway 감사 증빙 (3/5 완료)`
    - `[NEW] User Service 감사 일정 통보`

### 4.2. 감사 일정 등록 (Create Audit Schedule)
**목적:** (Req 1) 주체가 되어 감사 대상 시스템과 기간을 설정하고 통보

- **Form Fields**
  - **System Select**: 드롭다운 (시스템 선택 시 담당자/팀장 자동 로드) -> `systems`, `users` 테이블 참조
  - **Period**: 시작일 ~ 종료일 (Date Picker)
  - **Auditor**: 감사자 선택 (본인 default)
- **Actions**
  - `미리보기`: 대상 기간 내 예상 로그 수(배포/DB) 조회 (Count Query)
  - `등록 및 통보`: 저장 후 담당자/팀장에게 메일 발송 (`notification_logs` 기록)

### 4.3. 감사 상세 및 샘플링 (Audit Detail & Sampling)
**목적:** (Req 3, 4) 로그 추출 및 랜덤 샘플링 수행 확인

- **Overview Tab**: 일정 정보, 진행 상태 (Step Bar: 일정 -> 추출 -> 분석 -> 확인 -> 완료)
- **Target Logs Tab**:
  - 추출된 전체 로그 리스트 (배포/DB 작업)
  - **Action**: `🎲 랜덤 샘플링 실행` 버튼
    - 클릭 시 로딩 애니메이션 (서버: 증빙 대상 선정 -> AI 분석 병렬 처리)
- **Evidence List Tab**:
  - 선정된 샘플 목록 (Card or Table List)
  - 상태 배지: `AI 분석완료`, `분석불가`, `확인대기`, `확정`

### 4.4. 증빙 검토 및 제출 (Evidence Review & Submission)
**목적:** (Req 5-9) 담당자가 AI 분석 결과를 확인하거나 수동 증빙 처리

- **Left Panel (Audit Target)**
  - 대상 항목 정보: (예: [DB DML] UPDATE users SET type='VIP'...)
  - 발생 일시, 실행자 정보

- **Right Panel (Evidence Area)**
  - **Case A: AI 분석 성공 (Recommended)**
    - "AI가 연결된 증빙을 찾았습니다." (신뢰도 95%)
    - 매핑된 CI/CD 로그 또는 결재 문서 요약 표시
    - **Actions**: `✅ 확정 (Confirm)`, `❌ 거부 (Reject)`
  
  - **Case B: AI 분석 불가 (Unanalyzable)**
    - "자동으로 매핑되는 증빙을 찾지 못했습니다."
    - **Upload Form**: 파일 첨부 (Drag & Drop) 또는 텍스트 사유 작성
    - **Actions**: `📤 증빙 제출`

### 4.5. 최종 리포트 및 제출 (Final Report)
**목적:** (Req 10) 모든 증빙이 확정된 후 최종 감사 결과 제출

- **Summary Stats**: 전체 샘플 수, AI 자동화율, 수동 처리 건수
- **Status Check**: 미확정 항목이 있을 경우 제출 불가 (Red Alert)
- **Submit Action**: `최종 제출` 버튼 -> 데이터베이스 상태 업데이트 (`SUBMITTED`)

## 5. UI 가이드라인 (Tone & Manner)
- **Colors**:
  - Primary: `Deep Blue` (신뢰, 보안)
  - Status: `Green`(확정/성공), `Red`(지연/분석불가), `Yellow`(대기중)
- **Components**:
  - 간결한 테이블 (Data Grid)
  - 명확한 Call-to-Action 버튼
  - AI 분석 결과는 별도의 하이라이트 박스(Note style)로 구분
