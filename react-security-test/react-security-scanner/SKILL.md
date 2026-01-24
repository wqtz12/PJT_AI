---
name: react-security-scanner
description: React/JavaScript 앱의 보안 취약점을 스캔하고 보고서를 생성하는 skill. KISA JavaScript 시큐어코딩 가이드(2023) 기반 CVSS 7.0 이상 고위험 취약점 10종을 테스트. SQL Injection, XSS, SSRF, OS Command Injection 등 주요 웹 취약점 공격 페이로드 제공 및 자동화 테스트 수행. 보안 점검 결과를 HTML/JSON 보고서로 생성하고 이메일로 발송. 자체 앱 보안 테스트, 펜테스트, CTF 대회 준비에 활용.
---

# React Security Scanner Skill

KISA JavaScript 시큐어코딩 가이드(2023)를 기반으로 React/JavaScript 앱의 고위험(CVSS 7.0+) 취약점을 스캔하는 도구입니다.

## 지원 취약점 (10종)

| 취약점 | CWE | CVSS | 심각도 |
|--------|-----|------|--------|
| SQL Injection | CWE-89 | 9.8 | Critical |
| OS Command Injection | CWE-78 | 9.8 | Critical |
| Code Injection (eval) | CWE-94 | 9.8 | Critical |
| Insecure Deserialization | CWE-502 | 9.8 | Critical |
| Unrestricted File Upload | CWE-434 | 9.8 | Critical |
| SSRF | CWE-918 | 9.1 | Critical |
| CSRF | CWE-352 | 8.0 | High |
| Path Traversal | CWE-22 | 7.5 | High |
| XXE | CWE-611 | 7.5 | High |
| XSS | CWE-79 | 7.1 | High |

## 사용 방법

### 1. 전체 취약점 스캔

대상 앱의 모든 고위험 취약점을 한 번에 스캔합니다.

```
사용자: https://myapp.com 에 대해 보안 스캔을 실행해줘

Claude: scan_all 도구를 사용하여 전체 스캔을 수행합니다.
```

### 2. 특정 취약점 테스트

특정 취약점 유형만 선택적으로 테스트합니다.

```
사용자: /api/login 엔드포인트에 SQL Injection 취약점이 있는지 테스트해줘

Claude: scan_vulnerability 도구를 사용합니다.
- vulnerabilityType: SQL_INJECTION
- targetUrl: https://myapp.com/api/login
```

### 3. 공격 페이로드 조회

특정 취약점의 공격 페이로드를 확인합니다.

```
사용자: XSS 공격에 사용할 수 있는 페이로드들을 보여줘

Claude: get_payloads 도구를 사용합니다.
- vulnerabilityType: XSS_ATTACK
```

### 4. 보고서 생성

스캔 결과를 HTML, JSON, 텍스트 형식으로 보고서화합니다.

```
사용자: 스캔 결과를 HTML 보고서로 만들어줘

Claude: generate_report 도구를 사용합니다.
- format: html
```

### 5. 이메일 발송

스캔 결과를 이메일로 발송합니다.

```
사용자: 보안 스캔 결과를 security@company.com으로 보내줘

Claude: send_report_email 도구를 사용합니다.
- to: security@company.com
- smtpUser: (설정된 SMTP 계정)
- smtpPass: (설정된 SMTP 비밀번호)
```

## MCP 서버 설정

### Claude Desktop 설정 (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "react-security-scanner": {
      "command": "node",
      "args": ["/path/to/react-security-test/mcp-server.js"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your-email@gmail.com",
        "SMTP_PASS": "your-app-password"
      }
    }
  }
}
```

### Claude Code 설정 (.claude/settings.json)

```json
{
  "mcpServers": {
    "react-security-scanner": {
      "command": "node",
      "args": ["./react-security-test/mcp-server.js"]
    }
  }
}
```

## 제공 도구 (Tools)

### scan_vulnerability
특정 취약점 유형을 테스트합니다.

**파라미터:**
- `vulnerabilityType` (필수): 취약점 유형 (SQL_INJECTION, XSS_ATTACK 등)
- `targetUrl` (필수): 테스트 대상 URL
- `inputField`: 입력 필드명 (기본값: input)
- `method`: HTTP 메서드 (GET/POST)
- `maxPayloads`: 카테고리당 최대 페이로드 수

### scan_all
모든 고위험 취약점을 스캔합니다.

**파라미터:**
- `targetBaseUrl` (필수): 대상 기본 URL
- `endpoints`: 취약점별 엔드포인트 매핑 (선택)

### get_payloads
취약점별 공격 페이로드를 조회합니다.

**파라미터:**
- `vulnerabilityType` (필수): 취약점 유형
- `category`: 페이로드 카테고리 (선택)

### generate_report
스캔 결과로 보고서를 생성합니다.

**파라미터:**
- `scanResults` (필수): 스캔 결과 객체
- `format`: 보고서 형식 (html/json/text)

### send_report_email
보고서를 이메일로 발송합니다.

**파라미터:**
- `scanResults` (필수): 스캔 결과
- `to` (필수): 수신자 이메일
- `smtpUser` (필수): SMTP 사용자
- `smtpPass` (필수): SMTP 비밀번호
- `smtpHost`: SMTP 서버 (기본: smtp.gmail.com)
- `smtpPort`: SMTP 포트 (기본: 587)

### list_vulnerabilities
지원하는 취약점 목록을 조회합니다.

## 취약점별 페이로드 카테고리

### SQL Injection
- `authBypass`: 인증 우회 페이로드
- `unionBased`: UNION 기반 데이터 추출
- `timeBased`: 시간 기반 Blind SQL Injection
- `errorBased`: 에러 기반 추출

### XSS (Cross-Site Scripting)
- `reflected`: Reflected XSS
- `stored`: Stored XSS
- `domBased`: DOM 기반 XSS
- `filterBypass`: 필터 우회

### OS Command Injection
- `basic`: 기본 명령어 삽입
- `encoded`: 인코딩 우회
- `timeBased`: 시간 기반 탐지

### SSRF
- `internalNetwork`: 내부 네트워크 스캔
- `cloudMetadata`: 클라우드 메타데이터 접근
- `protocolHandlers`: 프로토콜 핸들러 악용

### Path Traversal
- `basic`: 기본 경로 조작
- `encoded`: URL 인코딩 우회
- `nullByte`: Null 바이트 삽입

## 보고서 예시

### 이메일 제목
- 취약점 발견 시: `🚨 [보안경고] 3개 취약점 발견 - 보안 스캔 보고서`
- 안전한 경우: `✅ [안전] 취약점 없음 - 보안 스캔 보고서`

### 보고서 내용
- 요약: Critical/High/Safe 취약점 수
- 발견된 취약점 상세 정보
- 취약 페이로드 및 증거
- 전체 테스트 결과 테이블
- 권장 조치사항

## 사용 예시

### 예시 1: 로그인 API SQL Injection 테스트

```
사용자: 우리 앱의 로그인 API에 SQL Injection 취약점이 있는지 확인해줘

Claude: scan_vulnerability 도구로 SQL Injection 테스트를 수행하겠습니다.

결과:
- 취약점: SQL Injection (CWE-89)
- CVSS: 9.8 (Critical)
- 상태: ❌ 취약점 발견
- 발견된 페이로드: "' OR '1'='1' --"
- 증거: 응답에 "Welcome, admin" 포함

권장 조치:
1. Prepared Statement 사용
2. ORM 라이브러리 활용
3. 입력값 화이트리스트 검증
```

### 예시 2: 전체 스캔 및 이메일 발송

```
사용자: https://staging.myapp.com 전체 보안 스캔하고 결과를 security@mycompany.com으로 보내줘

Claude:
1. scan_all로 전체 스캔 수행
2. 결과 분석
3. send_report_email로 보고서 발송

결과:
- 스캔 완료: 10개 취약점 유형 테스트
- 발견: Critical 2개, High 1개
- 이메일 발송: ✅ 완료 (Message ID: xxx)
```

## 참고사항

- 이 도구는 **자체 앱 보안 테스트 전용**입니다
- 타인의 시스템에 무단 사용 금지
- KISA JavaScript 시큐어코딩 가이드 2023 기준
- OWASP Top 10 및 CWE 표준 반영

## 의존성

```json
{
  "@modelcontextprotocol/sdk": "^1.0.0",
  "nodemailer": "^6.9.0"
}
```
