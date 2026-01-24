# React Security Scanner

KISA JavaScript 시큐어코딩 가이드(2023) 기반 React/JavaScript 앱 보안 취약점 스캐너

## 기능

- **10개 고위험 취약점 테스트** (CVSS 7.0+)
- **MCP 서버** - Claude Desktop/Code와 통합
- **Skill 파일** - Claude Code에서 사용
- **CLI 스캐너** - 독립 실행 가능
- **이메일 발송** - 자동 보고서 발송
- **HTML/JSON 보고서** - 시각화된 결과

## 지원 취약점

| 취약점 | CWE | CVSS | 심각도 |
|--------|-----|------|--------|
| SQL Injection | CWE-89 | 9.8 | Critical |
| OS Command Injection | CWE-78 | 9.8 | Critical |
| Code Injection | CWE-94 | 9.8 | Critical |
| Deserialization | CWE-502 | 9.8 | Critical |
| File Upload | CWE-434 | 9.8 | Critical |
| SSRF | CWE-918 | 9.1 | Critical |
| CSRF | CWE-352 | 8.0 | High |
| Path Traversal | CWE-22 | 7.5 | High |
| XXE | CWE-611 | 7.5 | High |
| XSS | CWE-79 | 7.1 | High |

## 설치

```bash
cd react-security-test
npm install
```

## 사용 방법

### 1. CLI 스캐너

```bash
# 기본 스캔
node security-scanner.js --target=https://your-app.com

# 메일 발송 포함
node security-scanner.js --target=https://your-app.com --email=security@company.com

# 환경변수로 SMTP 설정
export SMTP_HOST=smtp.gmail.com
export SMTP_USER=your-email@gmail.com
export SMTP_PASS=your-app-password
export REPORT_EMAIL=security@company.com
node security-scanner.js --target=https://your-app.com
```

### 2. MCP 서버 설정

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "react-security-scanner": {
      "command": "node",
      "args": ["/Users/jbs/PJT_AI/react-security-test/mcp-server.js"],
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

#### Claude Code (`.claude/settings.json` 또는 프로젝트 설정)

```json
{
  "mcpServers": {
    "react-security-scanner": {
      "command": "node",
      "args": ["/Users/jbs/PJT_AI/react-security-test/mcp-server.js"]
    }
  }
}
```

### 3. Skill 파일 사용

생성된 `react-security-scanner.skill` 파일을 Claude Code의 skill 디렉토리에 복사:

```bash
cp react-security-scanner.skill ~/.claude/skills/
# 또는
cp react-security-scanner.skill /Users/jbs/PJT_AI/skil\ \&\ mcp/
```

## MCP 도구 목록

### scan_vulnerability
특정 취약점 테스트

```
사용: SQL Injection 취약점 테스트해줘
파라미터:
- vulnerabilityType: SQL_INJECTION
- targetUrl: https://app.com/api/login
```

### scan_all
전체 취약점 스캔

```
사용: https://myapp.com 전체 보안 스캔 실행해줘
```

### get_payloads
공격 페이로드 조회

```
사용: XSS 공격 페이로드 보여줘
```

### generate_report
보고서 생성 (HTML/JSON/Text)

### send_report_email
이메일로 보고서 발송

### list_vulnerabilities
지원 취약점 목록 조회

## 파일 구조

```
react-security-test/
├── package.json                    # 의존성 및 스크립트
├── mcp-server.js                   # MCP 서버 (Claude 통합)
├── security-scanner.js             # CLI 스캐너
├── high-severity-attacks.js        # 공격 페이로드 모듈
├── SecurityScannerApp.jsx          # React 대시보드
├── react-security-scanner.skill    # Skill 파일 (압축)
├── react-security-scanner/
│   ├── SKILL.md                    # Skill 메인 문서
│   └── references/
│       └── payloads.md             # 페이로드 레퍼런스
└── api/
    └── send-security-report.js     # 이메일 API
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `TARGET_URL` | 스캔 대상 URL | `http://localhost:3000` |
| `SMTP_HOST` | SMTP 서버 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 포트 | `587` |
| `SMTP_USER` | SMTP 사용자 | - |
| `SMTP_PASS` | SMTP 비밀번호 | - |
| `REPORT_EMAIL` | 보고서 수신자 | - |

## 사용 예시

### Claude와 대화

```
사용자: https://staging.myapp.com 에 대해 보안 스캔 실행하고
       결과를 security@company.com으로 보내줘

Claude: scan_all 도구로 전체 스캔을 수행하겠습니다.

[스캔 실행 중...]

스캔 결과:
- 전체 테스트: 10개
- Critical 취약점: 2개 (SQL Injection, OS Command Injection)
- High 취약점: 1개 (XSS)

send_report_email로 보고서를 발송합니다.

✅ 보고서 발송 완료
- 수신자: security@company.com
- 제목: 🚨 [보안경고] 3개 취약점 발견 - 보안 스캔 보고서
```

## 주의사항

- **자체 앱 테스트 전용**입니다
- 타인의 시스템에 무단 사용 금지
- 프로덕션 환경 테스트 시 주의 필요
- SMTP 앱 비밀번호 사용 권장 (Gmail 2FA)

## 라이선스

MIT
