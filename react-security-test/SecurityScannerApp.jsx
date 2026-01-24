/**
 * React 기반 보안 스캐너 대시보드
 * 브라우저에서 실행 가능한 통합 테스트 인터페이스
 *
 * 기능:
 * - 10개 고위험(7점+) 취약점 테스트
 * - 실시간 진행 상황 표시
 * - HTML 보고서 생성
 * - 이메일 발송 (서버 API 필요)
 */

import React, { useState, useCallback } from 'react';
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
// 메인 스캐너 앱
// ============================================================
export default function SecurityScannerApp() {
  const [config, setConfig] = useState({
    targetUrl: 'http://localhost:3000',
    email: '',
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
  });

  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 10, currentTest: '' });
  const [results, setResults] = useState([]);
  const [emailSent, setEmailSent] = useState(false);

  // 모든 테스트 목록
  const ALL_TESTS = [
    { key: 'SQL_INJECTION', attack: SQL_INJECTION },
    { key: 'OS_COMMAND_INJECTION', attack: OS_COMMAND_INJECTION },
    { key: 'CODE_INJECTION', attack: CODE_INJECTION },
    { key: 'XSS_ATTACK', attack: XSS_ATTACK },
    { key: 'SSRF_ATTACK', attack: SSRF_ATTACK },
    { key: 'PATH_TRAVERSAL', attack: PATH_TRAVERSAL },
    { key: 'DESERIALIZATION_ATTACK', attack: DESERIALIZATION_ATTACK },
    { key: 'XXE_ATTACK', attack: XXE_ATTACK },
    { key: 'CSRF_ATTACK', attack: CSRF_ATTACK },
    { key: 'FILE_UPLOAD_ATTACK', attack: FILE_UPLOAD_ATTACK },
  ];

  // 스캔 실행
  const runScan = useCallback(async () => {
    setScanning(true);
    setResults([]);
    setEmailSent(false);

    const scanResults = [];

    for (let i = 0; i < ALL_TESTS.length; i++) {
      const { key, attack } = ALL_TESTS[i];
      const endpoint = config.endpoints[key];
      const targetUrl = `${config.targetUrl}${endpoint}`;

      setProgress({
        current: i + 1,
        total: ALL_TESTS.length,
        currentTest: attack.name,
      });

      try {
        const result = await attack.test(targetUrl);
        scanResults.push(result);
        setResults([...scanResults]);
      } catch (error) {
        scanResults.push({
          name: attack.name,
          cwe: attack.cwe,
          cvss: attack.cvss,
          error: error.message,
          vulnerable: false,
          results: [],
        });
        setResults([...scanResults]);
      }

      // 테스트 간 딜레이
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setScanning(false);

    // 이메일 발송
    if (config.email) {
      await sendEmailReport(scanResults, config);
      setEmailSent(true);
    }
  }, [config]);

  // 이메일 발송 (서버 API 호출)
  const sendEmailReport = async (scanResults, config) => {
    try {
      const report = generateHTMLReport(scanResults, config.targetUrl);

      const response = await fetch('/api/send-security-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: config.email,
          subject: getEmailSubject(scanResults),
          html: report,
          results: scanResults,
        }),
      });

      if (!response.ok) throw new Error('이메일 발송 실패');
      return true;
    } catch (error) {
      console.error('Email error:', error);
      return false;
    }
  };

  // 이메일 제목 생성
  const getEmailSubject = (results) => {
    const vulnCount = results.filter(r => r.vulnerable).length;
    return vulnCount > 0
      ? `🚨 [보안경고] ${vulnCount}개 취약점 발견 - 보안 스캔 보고서`
      : `✅ [안전] 취약점 없음 - 보안 스캔 보고서`;
  };

  // 통계 계산
  const stats = {
    total: results.length,
    vulnerable: results.filter(r => r.vulnerable).length,
    safe: results.filter(r => !r.vulnerable && !r.error).length,
    error: results.filter(r => r.error).length,
    critical: results.filter(r => r.vulnerable && r.cvss >= 9.0).length,
    high: results.filter(r => r.vulnerable && r.cvss >= 7.0 && r.cvss < 9.0).length,
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🔒 React 보안 스캐너</h1>
        <p style={styles.subtitle}>KISA JavaScript 시큐어코딩 가이드 기반 (CVSS 7.0+ 취약점)</p>
      </header>

      {/* 설정 패널 */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>⚙️ 스캔 설정</h2>
        <div style={styles.configGrid}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>대상 URL</label>
            <input
              type="url"
              value={config.targetUrl}
              onChange={(e) => setConfig(c => ({ ...c, targetUrl: e.target.value }))}
              style={styles.input}
              placeholder="https://your-app.com"
              disabled={scanning}
            />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>보고서 수신 이메일</label>
            <input
              type="email"
              value={config.email}
              onChange={(e) => setConfig(c => ({ ...c, email: e.target.value }))}
              style={styles.input}
              placeholder="security@company.com"
              disabled={scanning}
            />
          </div>
        </div>

        <details style={styles.details}>
          <summary style={styles.summary}>엔드포인트 설정 (클릭하여 펼치기)</summary>
          <div style={styles.endpointGrid}>
            {Object.entries(config.endpoints).map(([key, value]) => (
              <div key={key} style={styles.inputGroup}>
                <label style={styles.smallLabel}>{key}</label>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => setConfig(c => ({
                    ...c,
                    endpoints: { ...c.endpoints, [key]: e.target.value }
                  }))}
                  style={styles.smallInput}
                  disabled={scanning}
                />
              </div>
            ))}
          </div>
        </details>

        <button
          onClick={runScan}
          disabled={scanning}
          style={{
            ...styles.button,
            ...(scanning ? styles.buttonDisabled : {}),
          }}
        >
          {scanning ? '🔄 스캔 중...' : '🚀 보안 스캔 시작'}
        </button>
      </section>

      {/* 진행 상황 */}
      {scanning && (
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>📊 진행 상황</h2>
          <div style={styles.progressContainer}>
            <div style={styles.progressBar}>
              <div
                style={{
                  ...styles.progressFill,
                  width: `${(progress.current / progress.total) * 100}%`,
                }}
              />
            </div>
            <p style={styles.progressText}>
              {progress.current} / {progress.total} - {progress.currentTest}
            </p>
          </div>
        </section>
      )}

      {/* 결과 요약 */}
      {results.length > 0 && (
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>📈 스캔 결과 요약</h2>
          <div style={styles.statsGrid}>
            <div style={{ ...styles.statCard, ...styles.statCritical }}>
              <span style={styles.statNumber}>{stats.critical}</span>
              <span style={styles.statLabel}>Critical</span>
            </div>
            <div style={{ ...styles.statCard, ...styles.statHigh }}>
              <span style={styles.statNumber}>{stats.high}</span>
              <span style={styles.statLabel}>High</span>
            </div>
            <div style={{ ...styles.statCard, ...styles.statSafe }}>
              <span style={styles.statNumber}>{stats.safe}</span>
              <span style={styles.statLabel}>Safe</span>
            </div>
            <div style={{ ...styles.statCard, ...styles.statError }}>
              <span style={styles.statNumber}>{stats.error}</span>
              <span style={styles.statLabel}>Error</span>
            </div>
          </div>

          {emailSent && (
            <div style={styles.emailBanner}>
              📧 보고서가 {config.email}로 발송되었습니다.
            </div>
          )}
        </section>
      )}

      {/* 상세 결과 */}
      {results.length > 0 && (
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>🔍 상세 결과</h2>
          <div style={styles.resultsList}>
            {results.map((result, idx) => (
              <ResultCard key={idx} result={result} />
            ))}
          </div>

          {/* 보고서 다운로드 */}
          <div style={styles.downloadSection}>
            <button
              onClick={() => downloadReport(results, config.targetUrl)}
              style={styles.downloadButton}
            >
              📥 HTML 보고서 다운로드
            </button>
            <button
              onClick={() => downloadJSON(results)}
              style={styles.downloadButton}
            >
              📥 JSON 데이터 다운로드
            </button>
          </div>
        </section>
      )}

      <footer style={styles.footer}>
        <p>자체 앱 보안 테스트 전용 | KISA JavaScript 시큐어코딩 가이드 2023 기준</p>
      </footer>
    </div>
  );
}


// ============================================================
// 결과 카드 컴포넌트
// ============================================================
function ResultCard({ result }) {
  const [expanded, setExpanded] = useState(false);

  const severityColor = result.cvss >= 9.0 ? '#e74c3c' : '#e67e22';
  const statusColor = result.vulnerable ? '#e74c3c' : result.error ? '#95a5a6' : '#27ae60';

  return (
    <div style={{ ...styles.resultCard, borderLeftColor: statusColor }}>
      <div style={styles.resultHeader} onClick={() => setExpanded(!expanded)}>
        <div style={styles.resultInfo}>
          <span style={{ ...styles.cvssTag, backgroundColor: severityColor }}>
            {result.cvss}
          </span>
          <span style={styles.resultName}>{result.name}</span>
          <span style={styles.cweTag}>{result.cwe}</span>
        </div>
        <div style={styles.resultStatus}>
          {result.vulnerable && <span style={styles.vulnBadge}>취약점 발견</span>}
          {result.error && <span style={styles.errorBadge}>에러</span>}
          {!result.vulnerable && !result.error && <span style={styles.safeBadge}>안전</span>}
          <span style={styles.expandIcon}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={styles.resultDetails}>
          {result.error ? (
            <p style={styles.errorText}>에러: {result.error}</p>
          ) : (
            <>
              <p style={styles.detailText}>
                테스트 케이스: {result.results?.length || 0}개 |
                취약 발견: {result.results?.filter(r => r.vulnerable).length || 0}개
              </p>
              {result.results?.filter(r => r.vulnerable).slice(0, 5).map((r, i) => (
                <div key={i} style={styles.payloadItem}>
                  <code style={styles.payloadCode}>{r.payload || r.category || 'N/A'}</code>
                  {r.evidence && (
                    <pre style={styles.evidenceBlock}>{r.evidence}</pre>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}


// ============================================================
// HTML 보고서 생성
// ============================================================
function generateHTMLReport(results, targetUrl) {
  const timestamp = new Date().toISOString();
  const vulnerable = results.filter(r => r.vulnerable);
  const critical = vulnerable.filter(r => r.cvss >= 9.0);
  const high = vulnerable.filter(r => r.cvss >= 7.0 && r.cvss < 9.0);

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>보안 스캔 보고서</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }
    .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
    h1 { color: #1a1a1a; border-bottom: 3px solid #e74c3c; padding-bottom: 15px; }
    h2 { color: #2c3e50; margin-top: 30px; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 25px 0; }
    .stat { padding: 20px; border-radius: 10px; text-align: center; color: white; }
    .stat.critical { background: linear-gradient(135deg, #e74c3c, #c0392b); }
    .stat.high { background: linear-gradient(135deg, #e67e22, #d35400); }
    .stat.safe { background: linear-gradient(135deg, #27ae60, #1e8449); }
    .stat.error { background: linear-gradient(135deg, #95a5a6, #7f8c8d); }
    .stat h3 { margin: 0 0 5px 0; font-size: 32px; }
    .stat p { margin: 0; font-size: 13px; opacity: 0.9; }
    .vuln { background: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px 20px; margin: 15px 0; border-radius: 0 8px 8px 0; }
    .vuln.high { border-left-color: #e67e22; background: #fff8f0; }
    .vuln-header { display: flex; justify-content: space-between; align-items: center; }
    .vuln-name { font-weight: 600; font-size: 16px; }
    .cvss { background: #e74c3c; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; }
    .cvss.high { background: #e67e22; }
    .cwe { color: #666; font-size: 13px; margin-left: 10px; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th { background: #2c3e50; color: white; padding: 12px; text-align: left; }
    td { padding: 12px; border-bottom: 1px solid #eee; }
    tr:hover { background: #f8f9fa; }
    .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 12px; text-align: center; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔒 보안 스캔 보고서</h1>
    <p><strong>대상:</strong> <code>${targetUrl}</code></p>
    <p><strong>스캔 시간:</strong> ${timestamp}</p>

    <h2>📊 요약</h2>
    <div class="summary">
      <div class="stat critical"><h3>${critical.length}</h3><p>Critical (≥9.0)</p></div>
      <div class="stat high"><h3>${high.length}</h3><p>High (7.0-8.9)</p></div>
      <div class="stat safe"><h3>${results.filter(r => !r.vulnerable && !r.error).length}</h3><p>Safe</p></div>
      <div class="stat error"><h3>${results.filter(r => r.error).length}</h3><p>Error</p></div>
    </div>

    ${vulnerable.length > 0 ? `
    <h2>🚨 발견된 취약점</h2>
    ${vulnerable.map(v => `
    <div class="vuln ${v.cvss < 9.0 ? 'high' : ''}">
      <div class="vuln-header">
        <span><span class="vuln-name">${v.name}</span><span class="cwe">${v.cwe}</span></span>
        <span class="cvss ${v.cvss < 9.0 ? 'high' : ''}">${v.cvss}</span>
      </div>
      <p>발견된 취약 케이스: ${v.results?.filter(r => r.vulnerable).length || 0}건</p>
    </div>
    `).join('')}
    ` : '<h2>✅ 취약점이 발견되지 않았습니다</h2>'}

    <h2>📋 전체 결과</h2>
    <table>
      <tr><th>취약점</th><th>CWE</th><th>CVSS</th><th>상태</th></tr>
      ${results.map(r => `
      <tr>
        <td>${r.name}</td>
        <td>${r.cwe}</td>
        <td>${r.cvss}</td>
        <td style="color: ${r.vulnerable ? '#e74c3c' : r.error ? '#95a5a6' : '#27ae60'}">
          ${r.vulnerable ? '❌ 취약' : r.error ? '⚠️ 에러' : '✅ 안전'}
        </td>
      </tr>
      `).join('')}
    </table>

    <div class="footer">
      <p>KISA JavaScript 시큐어코딩 가이드 2023 기준 | 자동 생성된 보고서</p>
    </div>
  </div>
</body>
</html>
`;
}


// ============================================================
// 다운로드 함수
// ============================================================
function downloadReport(results, targetUrl) {
  const html = generateHTMLReport(results, targetUrl);
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `security-report-${Date.now()}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(results) {
  const json = JSON.stringify(results, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `security-results-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}


// ============================================================
// 스타일
// ============================================================
const styles = {
  container: {
    maxWidth: '1000px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    minHeight: '100vh',
  },
  header: {
    textAlign: 'center',
    marginBottom: '30px',
    paddingBottom: '20px',
    borderBottom: '1px solid #334155',
  },
  title: {
    fontSize: '28px',
    fontWeight: '700',
    margin: '0 0 10px 0',
    color: '#f1f5f9',
  },
  subtitle: {
    fontSize: '14px',
    color: '#94a3b8',
    margin: 0,
  },
  section: {
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: '600',
    margin: '0 0 20px 0',
    color: '#f1f5f9',
  },
  configGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '16px',
    marginBottom: '16px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: '500',
    color: '#94a3b8',
  },
  input: {
    padding: '10px 14px',
    borderRadius: '8px',
    border: '1px solid #334155',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '14px',
    outline: 'none',
  },
  details: {
    marginBottom: '20px',
  },
  summary: {
    cursor: 'pointer',
    padding: '10px',
    backgroundColor: '#334155',
    borderRadius: '6px',
    fontSize: '13px',
  },
  endpointGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px',
    marginTop: '12px',
  },
  smallLabel: {
    fontSize: '11px',
    color: '#64748b',
  },
  smallInput: {
    padding: '6px 10px',
    borderRadius: '6px',
    border: '1px solid #334155',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '12px',
  },
  button: {
    width: '100%',
    padding: '14px',
    backgroundColor: '#3b82f6',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
  },
  buttonDisabled: {
    backgroundColor: '#475569',
    cursor: 'not-allowed',
  },
  progressContainer: {
    marginTop: '10px',
  },
  progressBar: {
    height: '8px',
    backgroundColor: '#334155',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#3b82f6',
    transition: 'width 0.3s ease',
  },
  progressText: {
    textAlign: 'center',
    fontSize: '13px',
    color: '#94a3b8',
    marginTop: '10px',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
  },
  statCard: {
    padding: '20px',
    borderRadius: '10px',
    textAlign: 'center',
    color: 'white',
  },
  statCritical: { background: 'linear-gradient(135deg, #dc2626, #b91c1c)' },
  statHigh: { background: 'linear-gradient(135deg, #ea580c, #c2410c)' },
  statSafe: { background: 'linear-gradient(135deg, #16a34a, #15803d)' },
  statError: { background: 'linear-gradient(135deg, #64748b, #475569)' },
  statNumber: {
    display: 'block',
    fontSize: '32px',
    fontWeight: '700',
  },
  statLabel: {
    fontSize: '12px',
    opacity: 0.9,
  },
  emailBanner: {
    marginTop: '16px',
    padding: '12px',
    backgroundColor: '#166534',
    borderRadius: '8px',
    textAlign: 'center',
    fontSize: '14px',
  },
  resultsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  resultCard: {
    backgroundColor: '#0f172a',
    borderRadius: '8px',
    borderLeft: '4px solid',
    overflow: 'hidden',
  },
  resultHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px',
    cursor: 'pointer',
  },
  resultInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  cvssTag: {
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: '600',
    color: 'white',
  },
  resultName: {
    fontWeight: '500',
    fontSize: '14px',
  },
  cweTag: {
    fontSize: '12px',
    color: '#64748b',
  },
  resultStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  vulnBadge: {
    padding: '4px 10px',
    backgroundColor: '#dc2626',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: '500',
  },
  errorBadge: {
    padding: '4px 10px',
    backgroundColor: '#64748b',
    borderRadius: '12px',
    fontSize: '11px',
  },
  safeBadge: {
    padding: '4px 10px',
    backgroundColor: '#16a34a',
    borderRadius: '12px',
    fontSize: '11px',
  },
  expandIcon: {
    fontSize: '10px',
    color: '#64748b',
  },
  resultDetails: {
    padding: '16px',
    borderTop: '1px solid #334155',
    backgroundColor: '#1e293b',
  },
  detailText: {
    fontSize: '13px',
    color: '#94a3b8',
    margin: '0 0 12px 0',
  },
  errorText: {
    color: '#f87171',
    fontSize: '13px',
  },
  payloadItem: {
    marginBottom: '10px',
  },
  payloadCode: {
    display: 'block',
    padding: '8px 12px',
    backgroundColor: '#0f172a',
    borderRadius: '6px',
    fontSize: '12px',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
  },
  evidenceBlock: {
    marginTop: '8px',
    padding: '8px',
    backgroundColor: '#0f172a',
    borderRadius: '4px',
    fontSize: '11px',
    fontFamily: 'monospace',
    overflow: 'auto',
    maxHeight: '100px',
  },
  downloadSection: {
    display: 'flex',
    gap: '12px',
    marginTop: '20px',
  },
  downloadButton: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#334155',
    color: '#e2e8f0',
    border: 'none',
    borderRadius: '8px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  footer: {
    textAlign: 'center',
    padding: '20px',
    color: '#64748b',
    fontSize: '12px',
  },
};
