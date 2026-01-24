/**
 * React 앱 보안 스캐너
 * 고위험(7점 이상) 취약점 테스트 및 메일 발송
 *
 * 사용법:
 *   node security-scanner.js --target=https://your-app.com --email=you@example.com
 *
 * 환경변수 설정 필요:
 *   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
 */

import nodemailer from 'nodemailer';
import {
  SQL_INJECTION,
  OS_COMMAND_INJECTION,
  CODE_INJECTION,
  XSS_ATTACK,
  SSRF_ATTACK,
  PATH_TRAVERSAL,
  DESERIALIZATION_ATTACK,
  XXE_ATTACK,
  CSRF_ATTACK,
  FILE_UPLOAD_ATTACK,
} from './high-severity-attacks.js';


// ============================================================
// 설정
// ============================================================
const CONFIG = {
  // 테스트 타겟 URL (실행 시 --target 옵션으로 지정)
  targetBaseUrl: process.env.TARGET_URL || 'http://localhost:3000',

  // 메일 설정
  email: {
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: parseInt(process.env.SMTP_PORT || '587'),
    secure: process.env.SMTP_SECURE === 'true',
    auth: {
      user: process.env.SMTP_USER || '',
      pass: process.env.SMTP_PASS || '',
    },
    from: process.env.SMTP_FROM || 'Security Scanner <security@example.com>',
    to: process.env.REPORT_EMAIL || '',
  },

  // 테스트 엔드포인트 매핑
  endpoints: {
    SQL_INJECTION: '/api/login',
    OS_COMMAND_INJECTION: '/api/file',
    CODE_INJECTION: '/api/eval',
    XSS_ATTACK: '/search',
    SSRF_ATTACK: '/api/fetch',
    PATH_TRAVERSAL: '/api/download',
    DESERIALIZATION_ATTACK: '/api/data',
    XXE_ATTACK: '/api/xml',
    CSRF_ATTACK: '/api/transfer',
    FILE_UPLOAD_ATTACK: '/api/upload',
  },
};


// ============================================================
// 커맨드라인 인자 파싱
// ============================================================
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    const [key, value] = arg.split('=');
    if (key.startsWith('--')) {
      args[key.slice(2)] = value || true;
    }
  });
  return args;
}


// ============================================================
// 모든 취약점 테스트 실행
// ============================================================
async function runAllTests(baseUrl, endpoints) {
  const tests = [
    { name: 'SQL_INJECTION', attack: SQL_INJECTION, endpoint: endpoints.SQL_INJECTION },
    { name: 'OS_COMMAND_INJECTION', attack: OS_COMMAND_INJECTION, endpoint: endpoints.OS_COMMAND_INJECTION },
    { name: 'CODE_INJECTION', attack: CODE_INJECTION, endpoint: endpoints.CODE_INJECTION },
    { name: 'XSS_ATTACK', attack: XSS_ATTACK, endpoint: endpoints.XSS_ATTACK },
    { name: 'SSRF_ATTACK', attack: SSRF_ATTACK, endpoint: endpoints.SSRF_ATTACK },
    { name: 'PATH_TRAVERSAL', attack: PATH_TRAVERSAL, endpoint: endpoints.PATH_TRAVERSAL },
    { name: 'DESERIALIZATION_ATTACK', attack: DESERIALIZATION_ATTACK, endpoint: endpoints.DESERIALIZATION_ATTACK },
    { name: 'XXE_ATTACK', attack: XXE_ATTACK, endpoint: endpoints.XXE_ATTACK },
    { name: 'CSRF_ATTACK', attack: CSRF_ATTACK, endpoint: endpoints.CSRF_ATTACK },
    { name: 'FILE_UPLOAD_ATTACK', attack: FILE_UPLOAD_ATTACK, endpoint: endpoints.FILE_UPLOAD_ATTACK },
  ];

  const results = [];
  const startTime = Date.now();

  console.log('\n========================================');
  console.log('🔒 React 앱 보안 스캔 시작');
  console.log(`📍 대상: ${baseUrl}`);
  console.log(`📅 시간: ${new Date().toISOString()}`);
  console.log('========================================\n');

  for (const { name, attack, endpoint } of tests) {
    const targetUrl = `${baseUrl}${endpoint}`;
    console.log(`\n[${attack.cvss}] ${attack.name} (${attack.cwe}) 테스트 중...`);
    console.log(`   엔드포인트: ${targetUrl}`);

    try {
      const result = await attack.test(targetUrl);
      results.push(result);

      if (result.vulnerable) {
        console.log(`   ❌ 취약점 발견!`);
        console.log(`   발견된 취약 케이스: ${result.results.filter(r => r.vulnerable).length}개`);
      } else {
        console.log(`   ✅ 안전`);
      }
    } catch (error) {
      console.log(`   ⚠️ 테스트 실패: ${error.message}`);
      results.push({
        name: attack.name,
        cwe: attack.cwe,
        cvss: attack.cvss,
        error: error.message,
        vulnerable: false,
      });
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
  console.log(`\n========================================`);
  console.log(`⏱️ 스캔 완료: ${elapsed}초`);
  console.log('========================================\n');

  return results;
}


// ============================================================
// 보고서 생성
// ============================================================
function generateReport(results, baseUrl) {
  const vulnerableResults = results.filter(r => r.vulnerable);
  const safeResults = results.filter(r => !r.vulnerable && !r.error);
  const errorResults = results.filter(r => r.error);

  const timestamp = new Date().toISOString();

  // 심각도별 분류
  const critical = vulnerableResults.filter(r => r.cvss >= 9.0);
  const high = vulnerableResults.filter(r => r.cvss >= 7.0 && r.cvss < 9.0);

  // HTML 보고서
  const htmlReport = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>보안 스캔 보고서 - ${timestamp}</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
    .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    h1 { color: #1a1a1a; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }
    h2 { color: #2c3e50; margin-top: 30px; }
    .summary { display: flex; gap: 20px; margin: 20px 0; }
    .summary-card { flex: 1; padding: 20px; border-radius: 8px; text-align: center; }
    .summary-card.critical { background: #e74c3c; color: white; }
    .summary-card.high { background: #e67e22; color: white; }
    .summary-card.safe { background: #27ae60; color: white; }
    .summary-card.error { background: #95a5a6; color: white; }
    .summary-card h3 { margin: 0 0 10px 0; font-size: 36px; }
    .summary-card p { margin: 0; font-size: 14px; }
    .vuln-item { background: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px; margin: 15px 0; border-radius: 4px; }
    .vuln-item.high { border-left-color: #e67e22; background: #fff8f0; }
    .vuln-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .vuln-title { font-weight: bold; font-size: 18px; color: #2c3e50; }
    .cvss { background: #e74c3c; color: white; padding: 4px 12px; border-radius: 20px; font-size: 14px; }
    .cvss.high { background: #e67e22; }
    .cwe { color: #7f8c8d; font-size: 14px; }
    .details { margin-top: 10px; }
    .detail-row { display: flex; gap: 10px; margin: 5px 0; font-size: 14px; }
    .detail-label { font-weight: bold; min-width: 100px; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #34495e; color: white; }
    tr:hover { background: #f5f5f5; }
    .status-vuln { color: #e74c3c; font-weight: bold; }
    .status-safe { color: #27ae60; }
    .status-error { color: #95a5a6; }
    .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; font-size: 12px; text-align: center; }
    code { background: #f8f8f8; padding: 2px 6px; border-radius: 4px; font-family: 'Courier New', monospace; }
    .evidence { background: #f8f8f8; padding: 10px; border-radius: 4px; margin-top: 10px; font-family: monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔒 보안 스캔 보고서</h1>

    <div class="details">
      <div class="detail-row"><span class="detail-label">대상 URL:</span> <code>${baseUrl}</code></div>
      <div class="detail-row"><span class="detail-label">스캔 시간:</span> ${timestamp}</div>
      <div class="detail-row"><span class="detail-label">테스트 항목:</span> ${results.length}개</div>
    </div>

    <h2>📊 요약</h2>
    <div class="summary">
      <div class="summary-card critical">
        <h3>${critical.length}</h3>
        <p>Critical (CVSS ≥9.0)</p>
      </div>
      <div class="summary-card high">
        <h3>${high.length}</h3>
        <p>High (CVSS 7.0-8.9)</p>
      </div>
      <div class="summary-card safe">
        <h3>${safeResults.length}</h3>
        <p>Safe</p>
      </div>
      <div class="summary-card error">
        <h3>${errorResults.length}</h3>
        <p>Error/Skipped</p>
      </div>
    </div>

    ${vulnerableResults.length > 0 ? `
    <h2>🚨 발견된 취약점</h2>
    ${vulnerableResults.map(v => `
    <div class="vuln-item ${v.cvss < 9.0 ? 'high' : ''}">
      <div class="vuln-header">
        <div>
          <span class="vuln-title">${v.name}</span>
          <span class="cwe">${v.cwe}</span>
        </div>
        <span class="cvss ${v.cvss < 9.0 ? 'high' : ''}">${v.cvss}</span>
      </div>
      <div class="details">
        <div class="detail-row"><span class="detail-label">취약 케이스:</span> ${v.results ? v.results.filter(r => r.vulnerable).length : 0}개</div>
        ${v.results && v.results.filter(r => r.vulnerable).slice(0, 3).map(r => `
        <div class="detail-row"><span class="detail-label">페이로드:</span> <code>${r.payload || 'N/A'}</code></div>
        ${r.evidence ? `<div class="evidence">${escapeHtml(r.evidence)}</div>` : ''}
        `).join('')}
      </div>
    </div>
    `).join('')}
    ` : '<h2>✅ 취약점이 발견되지 않았습니다</h2>'}

    <h2>📋 전체 테스트 결과</h2>
    <table>
      <thead>
        <tr>
          <th>취약점</th>
          <th>CWE</th>
          <th>CVSS</th>
          <th>상태</th>
          <th>발견</th>
        </tr>
      </thead>
      <tbody>
        ${results.map(r => `
        <tr>
          <td>${r.name}</td>
          <td>${r.cwe}</td>
          <td>${r.cvss}</td>
          <td class="${r.vulnerable ? 'status-vuln' : r.error ? 'status-error' : 'status-safe'}">
            ${r.vulnerable ? '❌ 취약' : r.error ? '⚠️ 에러' : '✅ 안전'}
          </td>
          <td>${r.results ? r.results.filter(x => x.vulnerable).length : 0}건</td>
        </tr>
        `).join('')}
      </tbody>
    </table>

    <h2>🛡️ 권장 조치사항</h2>
    <ul>
      ${critical.length > 0 ? '<li><strong>[긴급]</strong> Critical 취약점은 즉시 수정이 필요합니다.</li>' : ''}
      ${high.length > 0 ? '<li><strong>[중요]</strong> High 취약점은 가능한 빠른 시일 내 수정하세요.</li>' : ''}
      <li>입력값 검증 및 이스케이프 처리를 강화하세요.</li>
      <li>Prepared Statement / Parameterized Query를 사용하세요.</li>
      <li>Content Security Policy (CSP) 헤더를 설정하세요.</li>
      <li>CSRF 토큰 및 SameSite 쿠키를 적용하세요.</li>
      <li>파일 업로드 시 확장자 및 MIME 타입을 검증하세요.</li>
    </ul>

    <div class="footer">
      <p>이 보고서는 자동화된 보안 스캐너에 의해 생성되었습니다.</p>
      <p>KISA JavaScript 시큐어코딩 가이드 (2023) 기준</p>
    </div>
  </div>
</body>
</html>
`;

  // 텍스트 보고서
  const textReport = `
========================================
보안 스캔 보고서
========================================
대상: ${baseUrl}
시간: ${timestamp}
테스트: ${results.length}개

[요약]
- Critical (CVSS ≥9.0): ${critical.length}개
- High (CVSS 7.0-8.9): ${high.length}개
- Safe: ${safeResults.length}개
- Error: ${errorResults.length}개

${vulnerableResults.length > 0 ? `
[발견된 취약점]
${vulnerableResults.map(v => `
- ${v.name} (${v.cwe})
  CVSS: ${v.cvss}
  발견: ${v.results ? v.results.filter(r => r.vulnerable).length : 0}건
`).join('')}
` : '[발견된 취약점 없음]'}

[권장 조치사항]
- 입력값 검증 강화
- Prepared Statement 사용
- CSP 헤더 설정
- CSRF 토큰 적용
========================================
`;

  // JSON 보고서
  const jsonReport = {
    metadata: {
      target: baseUrl,
      timestamp,
      totalTests: results.length,
    },
    summary: {
      critical: critical.length,
      high: high.length,
      safe: safeResults.length,
      error: errorResults.length,
    },
    vulnerabilities: vulnerableResults,
    allResults: results,
  };

  return { htmlReport, textReport, jsonReport };
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}


// ============================================================
// 메일 발송
// ============================================================
async function sendEmail(config, reports, results) {
  const vulnerableCount = results.filter(r => r.vulnerable).length;

  if (!config.auth.user || !config.auth.pass) {
    console.log('\n⚠️ SMTP 설정이 없어 메일 발송을 건너뜁니다.');
    console.log('환경변수 설정: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, REPORT_EMAIL');
    return false;
  }

  if (!config.to) {
    console.log('\n⚠️ 수신자 이메일이 설정되지 않았습니다. (REPORT_EMAIL 또는 --email 옵션)');
    return false;
  }

  try {
    const transporter = nodemailer.createTransport({
      host: config.host,
      port: config.port,
      secure: config.secure,
      auth: config.auth,
    });

    const subject = vulnerableCount > 0
      ? `🚨 [보안경고] ${vulnerableCount}개 취약점 발견 - 보안 스캔 보고서`
      : `✅ [안전] 취약점 없음 - 보안 스캔 보고서`;

    const mailOptions = {
      from: config.from,
      to: config.to,
      subject,
      text: reports.textReport,
      html: reports.htmlReport,
      attachments: [
        {
          filename: `security-report-${Date.now()}.json`,
          content: JSON.stringify(reports.jsonReport, null, 2),
          contentType: 'application/json',
        },
      ],
    };

    const info = await transporter.sendMail(mailOptions);
    console.log(`\n📧 보고서 메일 발송 완료: ${info.messageId}`);
    console.log(`   수신자: ${config.to}`);
    return true;

  } catch (error) {
    console.error(`\n❌ 메일 발송 실패: ${error.message}`);
    return false;
  }
}


// ============================================================
// 보고서 파일 저장
// ============================================================
async function saveReports(reports) {
  const fs = await import('fs/promises');
  const timestamp = Date.now();
  const dir = './security-reports';

  try {
    await fs.mkdir(dir, { recursive: true });

    const htmlPath = `${dir}/report-${timestamp}.html`;
    const jsonPath = `${dir}/report-${timestamp}.json`;

    await fs.writeFile(htmlPath, reports.htmlReport);
    await fs.writeFile(jsonPath, JSON.stringify(reports.jsonReport, null, 2));

    console.log(`\n📁 보고서 저장 완료:`);
    console.log(`   HTML: ${htmlPath}`);
    console.log(`   JSON: ${jsonPath}`);

    return { htmlPath, jsonPath };

  } catch (error) {
    console.error(`\n❌ 보고서 저장 실패: ${error.message}`);
    return null;
  }
}


// ============================================================
// 메인 실행
// ============================================================
async function main() {
  const args = parseArgs();

  // 설정 오버라이드
  const targetUrl = args.target || CONFIG.targetBaseUrl;
  const reportEmail = args.email || CONFIG.email.to;

  if (args.help) {
    console.log(`
사용법: node security-scanner.js [옵션]

옵션:
  --target=URL     테스트 대상 URL (기본: http://localhost:3000)
  --email=ADDRESS  보고서 수신 이메일
  --help           도움말 표시

환경변수:
  TARGET_URL       테스트 대상 URL
  SMTP_HOST        SMTP 서버 호스트 (기본: smtp.gmail.com)
  SMTP_PORT        SMTP 서버 포트 (기본: 587)
  SMTP_USER        SMTP 사용자명
  SMTP_PASS        SMTP 비밀번호
  SMTP_FROM        발신자 이메일
  REPORT_EMAIL     수신자 이메일

예시:
  node security-scanner.js --target=https://myapp.com --email=security@company.com
`);
    process.exit(0);
  }

  // 테스트 실행
  const results = await runAllTests(targetUrl, CONFIG.endpoints);

  // 보고서 생성
  const reports = generateReport(results, targetUrl);

  // 콘솔 출력
  console.log(reports.textReport);

  // 파일 저장
  await saveReports(reports);

  // 메일 발송
  const emailConfig = { ...CONFIG.email, to: reportEmail };
  await sendEmail(emailConfig, reports, results);

  // 종료 코드 (취약점 발견 시 1)
  const vulnerableCount = results.filter(r => r.vulnerable).length;
  process.exit(vulnerableCount > 0 ? 1 : 0);
}


// ES Module에서 직접 실행 체크
const isMainModule = import.meta.url === `file://${process.argv[1]}`;
if (isMainModule) {
  main().catch(error => {
    console.error('실행 오류:', error);
    process.exit(1);
  });
}


export { runAllTests, generateReport, sendEmail, CONFIG };
