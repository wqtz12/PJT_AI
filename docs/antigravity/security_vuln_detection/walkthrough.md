# Security Vulnerability Detection System - Walkthrough

## Overview
MCP 기반 하이브리드 보안 취약점 탐지 시스템입니다.
Semgrep(정적 분석)과 Claude(LLM 검증)를 결합하여 정확도 높은 취약점 탐지를 수행합니다.

## System Components

| Package | 역할 |
|---------|------|
| `mcp-analysis` | Semgrep 래퍼 - 정적 분석 수행 (v0.2.0) |
| `mcp-knowledge` | 보안 Skills 제공 (3종) |
| `workflow-controller` | 분석/검증 오케스트레이터 |

## Security Skills (Knowledge Base)

| Skill | 설명 |
|-------|------|
| `javascript-secure-coding` | XSS, SQLi, Command Injection 등 |
| `privacy-checklist` | 개인정보보호법 준수 |
| `ai-security-checklist` | AI/LLM 보안, AI 기본법 |

## Quick Start

### 1. Setup
```bash
cd vuln-detector
npm install
npm run build --workspaces
```

### 2. Configure API Key
```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

### 3. Run Analysis
```bash
# General Usage
node apps/workflow-controller/dist/index.js ./target-file.js

# Test Mode (Dry Run without API Key)
node apps/workflow-controller/dist/index.js test-assets/vulnerable.js --dry-run
```

## Verified Test Output
*Test run on `test-assets/vulnerable.js` (Dry Run)*:

```
========================================
  Security Vulnerability Detector v0.2
========================================

⚠️  Running without API Key (Dry Run Mode Only)

Starting MCP Servers...
[Analysis] MCP Server running on stdio (v0.2.0)
✓ Connected to MCP Server: Analysis
Loading skills from: .../dist/skills
Total skills loaded: 3
✓ Connected to MCP Server: Knowledge

📁 Target Path: test-assets/vulnerable.js
🛠️  DRY RUN MODE: LLM calls will be mocked.

Step 1: Running Semgrep Scan...
[Analysis] Found 2 potential issues

Step 2: Loading Security Skills...
   Available Skills: javascript-secure-coding, privacy-checklist, ai-security-checklist

Step 3: Verifying findings with LLM...

[1/2] Analyzing: javascript.express.security.audit.xss.direct-response-write.direct-response-write
            Skill: javascript-secure-coding / Section: XSS
            → ❌ CONFIRMED Vulnerable (High)

[2/2] Analyzing: javascript.express.security.injection.raw-html-format.raw-html-format
            Skill: javascript-secure-coding / Section: XSS
            → ❌ CONFIRMED Vulnerable (High)

========================================
           FINAL REPORT
========================================
Total Findings: 2
Confirmed Vulnerabilities: 2
False Positives: 0
```

## MCP Tools Reference

### Analysis Server
- `run_scan(path, include_rules)` - Semgrep 스캔 실행
- `get_file_context(path, startLine, endLine)` - 코드 컨텍스트 조회

### Knowledge Server
- `list_security_skills()` - 스킬 목록 조회
- `get_security_skill(skill_name)` - 스킬 전체 내용
- `get_skill_section(skill_name, section_name)` - 특정 섹션 조회
- `search_skills(keyword)` - 키워드 검색
