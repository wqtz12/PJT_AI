-- =====================================================
-- AMXIS Audit Shield System Database Schema
-- Version: 1.0
-- Created: 2026-02-05
-- Description: 감사 업무 자동화를 위한 데이터베이스 스키마
-- =====================================================

-- 기존 테이블 삭제 (개발 환경용)
DROP TABLE IF EXISTS audit_submissions;
DROP TABLE IF EXISTS manual_evidences;
DROP TABLE IF EXISTS reminder_logs;
DROP TABLE IF EXISTS owner_confirmations;
DROP TABLE IF EXISTS ai_evidence_mappings;
DROP TABLE IF EXISTS evidence_sources;
DROP TABLE IF EXISTS evidence_samples;
DROP TABLE IF EXISTS db_operation_logs;
DROP TABLE IF EXISTS deployment_logs;
DROP TABLE IF EXISTS notification_logs;
DROP TABLE IF EXISTS audit_schedules;
DROP TABLE IF EXISTS systems;
DROP TABLE IF EXISTS users;

-- =====================================================
-- 1. users: 사용자 테이블 (담당자, 팀장, 감사자)
-- =====================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    role ENUM('AUDITOR', 'OWNER', 'APPROVER') NOT NULL,
    manager_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_users_manager FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 사용자 인덱스
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_manager ON users(manager_id);

-- =====================================================
-- 2. systems: 감사 대상 시스템 테이블
-- =====================================================
CREATE TABLE systems (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    owner_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_systems_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- 시스템 인덱스
CREATE INDEX idx_systems_owner ON systems(owner_id);

-- =====================================================
-- 3. audit_schedules: 감사 일정 테이블
-- =====================================================
CREATE TABLE audit_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    auditor_id INT NOT NULL,
    system_id INT NOT NULL,
    owner_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status ENUM('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'SUBMITTED') DEFAULT 'SCHEDULED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_audit_schedules_auditor FOREIGN KEY (auditor_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_schedules_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_schedules_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_audit_date_range CHECK (end_date >= start_date)
);

-- 감사 일정 인덱스
CREATE INDEX idx_audit_schedules_auditor ON audit_schedules(auditor_id);
CREATE INDEX idx_audit_schedules_system ON audit_schedules(system_id);
CREATE INDEX idx_audit_schedules_status ON audit_schedules(status);
CREATE INDEX idx_audit_schedules_date_range ON audit_schedules(start_date, end_date);

-- =====================================================
-- 4. notification_logs: 알림(메일/문자) 발송 이력
-- =====================================================
CREATE TABLE notification_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audit_schedule_id INT NOT NULL,
    recipient_id INT NOT NULL,
    channel ENUM('EMAIL', 'SMS') NOT NULL,
    notification_type ENUM('SCHEDULE_CREATED', 'EVIDENCE_READY', 'REMINDER', 'SUBMISSION_COMPLETE') NOT NULL,
    status ENUM('PENDING', 'SENT', 'FAILED') DEFAULT 'PENDING',
    sent_at TIMESTAMP NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_notification_logs_schedule FOREIGN KEY (audit_schedule_id) REFERENCES audit_schedules(id) ON DELETE CASCADE,
    CONSTRAINT fk_notification_logs_recipient FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 알림 로그 인덱스
CREATE INDEX idx_notification_logs_schedule ON notification_logs(audit_schedule_id);
CREATE INDEX idx_notification_logs_status ON notification_logs(status);

-- =====================================================
-- 5. deployment_logs: 배포 이력 테이블
-- =====================================================
CREATE TABLE deployment_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_id INT NOT NULL,
    deployer_id INT NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    deployed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_deployment_logs_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
    CONSTRAINT fk_deployment_logs_deployer FOREIGN KEY (deployer_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- 배포 로그 인덱스
CREATE INDEX idx_deployment_logs_system ON deployment_logs(system_id);
CREATE INDEX idx_deployment_logs_deployed_at ON deployment_logs(deployed_at);

-- =====================================================
-- 6. db_operation_logs: DB 작업(DML/DDL/DCL) 이력
-- =====================================================
CREATE TABLE db_operation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_id INT NOT NULL,
    operation_category ENUM('DML', 'DDL', 'DCL') NOT NULL,
    operation_type ENUM(
        -- DML
        'INSERT', 'UPDATE', 'DELETE',
        -- DDL
        'CREATE', 'ALTER', 'DROP',
        -- DCL
        'GRANT', 'REVOKE'
    ) NOT NULL,
    sql_statement TEXT NOT NULL,
    executor_id INT NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_db_operation_logs_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
    CONSTRAINT fk_db_operation_logs_executor FOREIGN KEY (executor_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- DB 작업 로그 인덱스
CREATE INDEX idx_db_operation_logs_system ON db_operation_logs(system_id);
CREATE INDEX idx_db_operation_logs_category ON db_operation_logs(operation_category);
CREATE INDEX idx_db_operation_logs_executed_at ON db_operation_logs(executed_at);

-- =====================================================
-- 7. evidence_samples: 증빙 대상 (랜덤 선택된 항목)
-- =====================================================
CREATE TABLE evidence_samples (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audit_schedule_id INT NOT NULL,
    target_type ENUM('DEPLOYMENT', 'DB_OPERATION') NOT NULL,
    target_id INT NOT NULL,
    analysis_status ENUM('PENDING', 'ANALYZED', 'UNANALYZABLE', 'CONFIRMED', 'MANUAL') DEFAULT 'PENDING',
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_evidence_samples_schedule FOREIGN KEY (audit_schedule_id) REFERENCES audit_schedules(id) ON DELETE CASCADE
);

-- 증빙 대상 인덱스
CREATE INDEX idx_evidence_samples_schedule ON evidence_samples(audit_schedule_id);
CREATE INDEX idx_evidence_samples_status ON evidence_samples(analysis_status);
CREATE INDEX idx_evidence_samples_target ON evidence_samples(target_type, target_id);

-- =====================================================
-- 8. evidence_sources: 증빙 소스 데이터
-- (CI/CD, 전자결재, DB/서버 접근제어 기록)
-- =====================================================
CREATE TABLE evidence_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_id INT NOT NULL,
    source_type ENUM('CICD', 'APPROVAL', 'DB_ACCESS_CONTROL', 'SERVER_ACCESS_CONTROL') NOT NULL,
    raw_data JSON NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_evidence_sources_system FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
);

-- 증빙 소스 인덱스
CREATE INDEX idx_evidence_sources_system ON evidence_sources(system_id);
CREATE INDEX idx_evidence_sources_type ON evidence_sources(source_type);
CREATE INDEX idx_evidence_sources_occurred_at ON evidence_sources(occurred_at);

-- =====================================================
-- 9. ai_evidence_mappings: AI 분석 결과 (증빙 매핑)
-- =====================================================
CREATE TABLE ai_evidence_mappings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_sample_id INT NOT NULL,
    evidence_source_id INT NOT NULL,
    confidence_score DECIMAL(5, 4) NOT NULL,
    selection_reason TEXT NOT NULL,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_ai_mappings_sample FOREIGN KEY (evidence_sample_id) REFERENCES evidence_samples(id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_mappings_source FOREIGN KEY (evidence_source_id) REFERENCES evidence_sources(id) ON DELETE CASCADE,
    CONSTRAINT chk_confidence_score CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

-- AI 매핑 인덱스
CREATE INDEX idx_ai_mappings_sample ON ai_evidence_mappings(evidence_sample_id);
CREATE INDEX idx_ai_mappings_confidence ON ai_evidence_mappings(confidence_score);

-- =====================================================
-- 10. owner_confirmations: 담당자 확인 이력
-- =====================================================
CREATE TABLE owner_confirmations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_sample_id INT NOT NULL UNIQUE,
    owner_id INT NOT NULL,
    status ENUM('PENDING', 'VIEWED', 'CONFIRMED', 'REJECTED') DEFAULT 'PENDING',
    rejection_reason TEXT NULL,
    viewed_at TIMESTAMP NULL,
    confirmed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_owner_confirmations_sample FOREIGN KEY (evidence_sample_id) REFERENCES evidence_samples(id) ON DELETE CASCADE,
    CONSTRAINT fk_owner_confirmations_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- 담당자 확인 인덱스
CREATE INDEX idx_owner_confirmations_status ON owner_confirmations(status);
CREATE INDEX idx_owner_confirmations_owner ON owner_confirmations(owner_id);

-- =====================================================
-- 11. reminder_logs: 리마인더 발송 이력
-- =====================================================
CREATE TABLE reminder_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_confirmation_id INT NOT NULL,
    channel ENUM('EMAIL', 'SMS') NOT NULL,
    reminder_count INT NOT NULL DEFAULT 1,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_reminder_logs_confirmation FOREIGN KEY (owner_confirmation_id) REFERENCES owner_confirmations(id) ON DELETE CASCADE
);

-- 리마인더 인덱스
CREATE INDEX idx_reminder_logs_confirmation ON reminder_logs(owner_confirmation_id);

-- =====================================================
-- 12. manual_evidences: 담당자 직접 증빙
-- =====================================================
CREATE TABLE manual_evidences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_sample_id INT NOT NULL UNIQUE,
    uploader_id INT NOT NULL,
    file_path VARCHAR(500) NULL,
    reason_text TEXT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_manual_evidences_sample FOREIGN KEY (evidence_sample_id) REFERENCES evidence_samples(id) ON DELETE CASCADE,
    CONSTRAINT fk_manual_evidences_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_evidence_content CHECK (file_path IS NOT NULL OR reason_text IS NOT NULL)
);

-- 수동 증빙 인덱스
CREATE INDEX idx_manual_evidences_uploader ON manual_evidences(uploader_id);

-- =====================================================
-- 13. audit_submissions: 최종 제출
-- =====================================================
CREATE TABLE audit_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audit_schedule_id INT NOT NULL UNIQUE,
    submitter_id INT NOT NULL,
    total_samples INT NOT NULL DEFAULT 0,
    analyzed_count INT NOT NULL DEFAULT 0,
    manual_count INT NOT NULL DEFAULT 0,
    unanalyzable_count INT NOT NULL DEFAULT 0,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_audit_submissions_schedule FOREIGN KEY (audit_schedule_id) REFERENCES audit_schedules(id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_submissions_submitter FOREIGN KEY (submitter_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_sample_counts CHECK (total_samples = analyzed_count + manual_count + unanalyzable_count)
);

-- 최종 제출 인덱스
CREATE INDEX idx_audit_submissions_submitter ON audit_submissions(submitter_id);

-- =====================================================
-- 유틸리티 뷰: 감사 현황 대시보드
-- =====================================================
CREATE OR REPLACE VIEW v_audit_dashboard AS
SELECT 
    a.id AS audit_id,
    s.name AS system_name,
    auditor.name AS auditor_name,
    owner.name AS owner_name,
    a.start_date,
    a.end_date,
    a.status,
    COUNT(DISTINCT es.id) AS total_samples,
    SUM(CASE WHEN es.analysis_status = 'ANALYZED' THEN 1 ELSE 0 END) AS analyzed_count,
    SUM(CASE WHEN es.analysis_status = 'UNANALYZABLE' THEN 1 ELSE 0 END) AS unanalyzable_count,
    SUM(CASE WHEN es.analysis_status = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed_count,
    SUM(CASE WHEN es.analysis_status = 'MANUAL' THEN 1 ELSE 0 END) AS manual_count
FROM audit_schedules a
JOIN systems s ON a.system_id = s.id
JOIN users auditor ON a.auditor_id = auditor.id
JOIN users owner ON a.owner_id = owner.id
LEFT JOIN evidence_samples es ON a.id = es.audit_schedule_id
GROUP BY a.id, s.name, auditor.name, owner.name, a.start_date, a.end_date, a.status;

-- =====================================================
-- 유틸리티 뷰: 미확인 증빙 목록
-- =====================================================
CREATE OR REPLACE VIEW v_pending_confirmations AS
SELECT 
    oc.id AS confirmation_id,
    a.id AS audit_id,
    s.name AS system_name,
    es.target_type,
    es.analysis_status,
    owner.name AS owner_name,
    owner.email AS owner_email,
    oc.status AS confirmation_status,
    (SELECT COUNT(*) FROM reminder_logs rl WHERE rl.owner_confirmation_id = oc.id) AS reminder_count
FROM owner_confirmations oc
JOIN evidence_samples es ON oc.evidence_sample_id = es.id
JOIN audit_schedules a ON es.audit_schedule_id = a.id
JOIN systems s ON a.system_id = s.id
JOIN users owner ON oc.owner_id = owner.id
WHERE oc.status IN ('PENDING', 'VIEWED');
