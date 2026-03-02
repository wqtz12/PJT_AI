/**
 * MCP Core - Shared Types
 * 
 * 모든 MCP 서버 및 클라이언트에서 공유하는 타입 정의
 */

// =============================================================================
// Analysis Types
// =============================================================================

export interface Finding {
    check_id: string;
    path: string;
    start: number;
    end: number;
    message: string;
    severity: 'ERROR' | 'WARNING' | 'INFO';
    lines?: string;
}

export interface ScanResult {
    findings: Finding[];
    scanned_files: number;
    scan_duration_ms: number;
}

// =============================================================================
// Knowledge Types
// =============================================================================

export interface SkillInfo {
    name: string;
    description: string;
    sections: string[];
}

export interface SearchResult {
    skill: string;
    section: string;
    snippet: string;
}

// =============================================================================
// Verification Types
// =============================================================================

export interface VerificationAnalysis {
    is_vulnerable: boolean;
    confidence: 'Low' | 'Medium' | 'High';
    reason: string;
    remediation: string;
    referenced_skill?: string;
}

export interface VerifiedVulnerability extends Finding {
    analysis: VerificationAnalysis;
}

// =============================================================================
// Report Types
// =============================================================================

export interface SecurityReport {
    generated_at: string;
    target_path: string;
    total_findings: number;
    confirmed_vulnerabilities: number;
    false_positives: number;
    vulnerabilities: VerifiedVulnerability[];
}
