# AMXIS Audit Shield Database Schema - Walkthrough

## 작업 완료 요약

AMXIS Audit Shield System의 데이터베이스 스키마를 10가지 비즈니스 요구사항에 맞게 설계 및 구현했습니다.

---

## 생성된 파일

| 파일 | 설명 |
|------|------|
| [audit_shield_schema.sql](file:///Users/jbs/PJT_AI/CEPF/db/audit_shield_schema.sql) | 전체 스키마 (13개 테이블 + 2개 뷰) |

---

## 테이블 구조 (비즈니스 요구사항 매핑)

| 단계 | 비즈니스 로직 | 테이블 |
|------|---------------|--------|
| 1 | 감사 일정 등록 | `users`, `systems`, `audit_schedules` |
| 2 | 담당자/팀장 메일 발송 | `notification_logs` |
| 3 | 배포/DB 작업 이력 추출 | `deployment_logs`, `db_operation_logs` |
| 4 | 랜덤 증빙 대상 선정 | `evidence_samples` |
| 5 | AI 증빙 분석 및 매핑 | `evidence_sources`, `ai_evidence_mappings` |
| 6 | 분석불가 처리 및 알림 | `evidence_samples.analysis_status`, `notification_logs` |
| 7 | 담당자 확인 및 리마인더 | `owner_confirmations`, `reminder_logs` |
| 8 | 증빙 확정/거부 | `owner_confirmations.status` |
| 9 | 수동 증빙 업로드 | `manual_evidences` |
| 10 | 최종 제출 | `audit_submissions` |

---

## 주요 기능

### 인덱스 최적화
- 날짜 범위 검색: `idx_audit_schedules_date_range`
- 상태 필터링: `idx_evidence_samples_status`, `idx_owner_confirmations_status`
- 시스템별 조회: `idx_deployment_logs_system`, `idx_db_operation_logs_system`

### 데이터 무결성 제약
- `chk_audit_date_range`: 감사 종료일 ≥ 시작일
- `chk_confidence_score`: AI 신뢰도 0~1 범위
- `chk_sample_counts`: 제출 시 샘플 수 합계 검증
- `chk_evidence_content`: 수동 증빙 시 파일 또는 사유 필수

### 유틸리티 뷰
- `v_audit_dashboard`: 감사 현황 대시보드
- `v_pending_confirmations`: 미확인 증빙 목록

---

## 검증 결과

파이썬 기반의 시뮬레이션 테스트(`tests/test_audit_schema.py`)를 통해 전체 스키마와 워크플로우를 검증했습니다.

| 검증 시나리오 | 상세 내용 | 결과 |
|---------------|-----------|------|
| **스키마 생성** | SQLite 호환성 변환 및 테이블 생성 | ✅ 성공 |
| **샘플 데이터** | 사용자, 시스템, 로그(배포/DB) 데이터 생성 | ✅ 성공 |
| **랜덤 샘플링** | 감사 기간 내 증빙 대상 추출 및 랜덤 선택 (Requirement 4) | ✅ 성공 |
| **AI 분석 워크플로우** | 분석 완료/불가 상태 시뮬레이션 (Requirement 5, 6) | ✅ 성공 |
| **담당자 확인** | 증빙 매핑 확인 및 확정 (Requirement 7, 8) | ✅ 성공 |
| **수동 증빙** | 분석 불가 항목에 대한 수동 업로드 (Requirement 9) | ✅ 성공 |
| **최종 제출** | 감사 결과 집계 및 제출 상태 변경 (Requirement 10) | ✅ 성공 |

### 테스트 실행 방법
```bash
python3 tests/test_audit_schema.py
```

### 테스트 결과 요약
- **랜덤 샘플링**: 정상적으로 3개 샘플 추출됨
- **최종 제출 통계**: Total=3, Analyzed=2, Manual=1, Unanalyzable=0
- **데이터 무결성**: 모든 FK 제약 조건과 상태 전이 로직이 정상 동작함

---

## 다음 단계 (권장)

1. **실제 DB 적용**: `audit_shield_schema.sql`을 실제 MySQL/PostgreSQL 서버에 적용
2. **API 개발**: 스키마 기반의 백엔드 API (NestJS/Express) 구현 시작
