# AMXIS Audit Shield - Module Design Document

## 1. 개요
AMXIS Audit Shield 시스템의 백엔드 모듈 및 API 설계서입니다.
NestJS/Express 기반의 레이어드 아키텍처(Controller-Service-Repository)를 가정하여 구조를 정의합니다.

## 2. 모듈 구조 (Directory Structure)

```
src/
├── common/             # 공통 유틸리티 (Guards, Interceptors, Filters)
├── config/             # 환경 설정 (DB, AI Key, Mailer)
├── modules/
│   ├── auth/           # 인증 및 사용자 관리
│   ├── system/         # 시스템 정보 관리
│   ├── audit/          # 감사 일정 및 워크플로우 코어
│   ├── evidence/       # 증빙 샘플링 및 데이터 관리
│   ├── analysis/       # AI 분석 및 매핑 로직
│   └── notification/   # 메일/문자 발송
├── database/
│   ├── entities/       # TypeORM/Prisma 엔티티
│   └── repositories/   # DB 접근 계층
└── app.module.ts
```

---

## 3. 핵심 모듈 상세 설계

### 3.1. Audit Module (`modules/audit`)
**책임**: 감사 일정(Schedule) 생명주기 관리 및 전체 워크플로우 오케스트레이션
- **Dependencies**: `SystemModule`, `NotificationModule`, `EvidenceModule`

**API Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/audits` | 감사 일정 등록 (Req 1) -> `notification` 트리거 |
| GET | `/api/audits` | 감사 목록 조회 (필터: 상태, 기간, 시스템) |
| GET | `/api/audits/:id` | 감사 상세 정보 및 진행률 조회 |
| POST | `/api/audits/:id/submit` | 최종 제출 처리 (Req 10) |

**Service Logic (`AuditService`):**
- `createSchedule()`: 일정 생성 transaction + 담당자/팀장 리스트업 + 알림 이벤트 발행
- `finalizeAudit()`: 모든 `evidence_samples`가 확정(`CONFIRMED`/`MANUAL`) 상태인지 검증 후 `audit_submissions` 생성

### 3.2. Log Ingestion Module (`modules/log-ingestion`) [Internal/Job]
**책임**: (Req 3) 외부 시스템에서 배포/DB 로그 수집 (Batch 또는 Event Driven)

**Components:**
- `DeploymentLogCollector`: CI/CD 툴(Jenkins, Github Actions) 연동하여 `deployment_logs` 적재
- `DbLogCollector`: DB 감사 로그 파싱하여 `db_operation_logs` 적재

### 3.3. Evidence Module (`modules/evidence`)
**책임**: (Req 4, 7, 8, 9) 샘플링 대상 추출, 랜덤 선정, 담당자 상호작용
- **Dependencies**: `AnalysisModule`, `NotificationModule`

**API Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/audits/:id/sampling` | 랜덤 샘플링 실행 (Req 4) -> `analysis` 트리거 |
| GET | `/api/evidences` | 증빙 샘플 목록 조회 (담당자용) |
| POST | `/api/evidences/:id/confirm` | 증빙 확정 (AI 결과 승인) |
| POST | `/api/evidences/:id/manual` | 수동 증빙 업로드 (Req 9) |

**Service Logic (`EvidenceService`):**
- `executeRandomSampling(auditId)`:
  1. `audit_schedules` 기간 조회
  2. `deployment_logs` + `db_operation_logs` UNION 조회
  3. Python/Random 로직으로 N개 추출 -> `evidence_samples` INSERT
  4. Automation Event 발행 (`AnalysisService.analyzeSamples` 호출)

### 3.4. Analysis Module (`modules/analysis`)
**책임**: (Req 5, 6) AI를 사용한 증빙 매핑 및 분석
- **Strategy**: LLM (Gemini/Claude) 활용 or Rule-Based 매칭

**Service Logic (`AiAnalysisService`):**
- `analyzeSamples(sampleIds[])`:
  1. 각 샘플의 일시(Time)와 시스템(System)을 기준으로 `evidence_sources` 후보군 조회
  2. LLM Prompting: "이 DB작업(UPDATE...) 시점에 발생한 결재 문서나 CI/CD 파이프라인 찾아서 매핑해줘."
  3. 결과(`ai_evidence_mappings`) 저장
  4. 매칭 실패 시 상태를 `UNANALYZABLE`로 업데이트
  5. 분석 완료 알림 이벤트 발행

### 3.5. Notification Module (`modules/notification`)
**책임**: (Req 2, 6, 7) 이메일/문자 발송 및 이력 관리 (`notification_logs`, `reminder_logs`)

**Service Logic (`ReminderScheduler` - Cron):**
- 매일 오전 09:00 실행
- `owner_confirmations` 중 상태가 `PENDING`이고 3일 이상 지난 건 조회
- 담당자에게 리마인더 메일 발송 및 `reminder_logs` 카운트 증가

---

## 4. 데이터 흐름 (Data Flow)

1. **감사 시작**: `Admin` -> `AuditService.create` -> DB 저장 -> `NotificationService` -> 메일 발송
2. **샘플링**: `Admin` -> `EvidenceService.sampling` -> DB(Samples) 저장 -> `AnalysisService` 호출
3. **AI 분석**: `AnalysisService` -> LLM/Rule -> DB(Mappings) 저장 -> `NotificationService` (담당자 알림)
4. **증빙 확인**: `Owner` -> `EvidenceService.get` -> (AI결과 확인) -> `EvidenceService.confirm/manual` -> DB 업데이트
5. **최종 제출**: `Admin` -> `AuditService.submit` -> 검증(All Confirmed?) -> DB(Submission) 저장

## 5. 기술 스택 (Recommendation)
- **Framework**: NestJS (TypeScript)
- **ORM**: TypeORM or Prisma
- **Queue**: Redis (BullMQ) - AI 분석 및 메일 발송 비동기 처리용
- **Scheduler**: NestJS Schedule (Cron)
