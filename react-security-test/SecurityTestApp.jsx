/**
 * React 앱 보안 테스트 대시보드
 * 자체 앱에 통합하여 개발/테스트 환경에서 사용
 */

import React, { useState, useCallback } from 'react';
import {
  XSS_PAYLOADS,
  SQL_PAYLOADS,
  OPEN_REDIRECT_PAYLOADS,
  testPrototypePollution,
  checkSecurityHeaders,
  createTestReport,
} from './security-test-utils';

// ============================================================
// 메인 보안 테스트 대시보드
// ============================================================

export default function SecurityTestApp() {
  const [activeTest, setActiveTest] = useState('xss');
  const [results, setResults] = useState([]);

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>🔒 React 보안 테스트 대시보드</h1>
      <p style={styles.warning}>
        ⚠️ 이 도구는 자체 앱 테스트 전용입니다. 타인의 앱에 사용하지 마세요.
      </p>

      <nav style={styles.nav}>
        {['xss', 'injection', 'redirect', 'headers', 'prototype'].map(test => (
          <button
            key={test}
            onClick={() => setActiveTest(test)}
            style={{
              ...styles.navButton,
              backgroundColor: activeTest === test ? '#3b82f6' : '#374151',
            }}
          >
            {test.toUpperCase()}
          </button>
        ))}
      </nav>

      <div style={styles.content}>
        {activeTest === 'xss' && <XSSTestPanel onResult={setResults} />}
        {activeTest === 'injection' && <InjectionTestPanel onResult={setResults} />}
        {activeTest === 'redirect' && <RedirectTestPanel onResult={setResults} />}
        {activeTest === 'headers' && <HeadersTestPanel onResult={setResults} />}
        {activeTest === 'prototype' && <PrototypeTestPanel onResult={setResults} />}
      </div>

      {results.length > 0 && (
        <div style={styles.results}>
          <h3>테스트 결과</h3>
          <pre style={styles.resultPre}>
            {JSON.stringify(createTestReport(results), null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ============================================================
// XSS 테스트 패널
// ============================================================

function XSSTestPanel({ onResult }) {
  const [input, setInput] = useState('');
  const [renderMode, setRenderMode] = useState('safe');
  const [output, setOutput] = useState('');

  const testPayload = (payload) => {
    setInput(payload);
    setOutput(payload);

    // 취약점 감지 로직
    const isVulnerable = renderMode === 'unsafe' &&
      (payload.includes('<script') || payload.includes('onerror') || payload.includes('javascript:'));

    onResult(prev => [...prev, {
      type: 'XSS',
      payload: payload.substring(0, 50),
      renderMode,
      vulnerable: isVulnerable,
    }]);
  };

  return (
    <div style={styles.panel}>
      <h2>XSS (Cross-Site Scripting) 테스트</h2>

      <div style={styles.modeSelector}>
        <label>
          <input
            type="radio"
            value="safe"
            checked={renderMode === 'safe'}
            onChange={(e) => setRenderMode(e.target.value)}
          />
          안전 모드 (React 기본 이스케이프)
        </label>
        <label>
          <input
            type="radio"
            value="unsafe"
            checked={renderMode === 'unsafe'}
            onChange={(e) => setRenderMode(e.target.value)}
          />
          취약 모드 (dangerouslySetInnerHTML)
        </label>
      </div>

      <div style={styles.inputGroup}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="XSS 페이로드 입력..."
          style={styles.textarea}
        />
        <button onClick={() => testPayload(input)} style={styles.button}>
          테스트 실행
        </button>
      </div>

      <div style={styles.payloadList}>
        <h4>사전 정의된 페이로드:</h4>
        {Object.entries(XSS_PAYLOADS).map(([category, payloads]) => (
          <div key={category}>
            <strong>{category}:</strong>
            <div style={styles.payloadButtons}>
              {payloads.slice(0, 3).map((payload, idx) => (
                <button
                  key={idx}
                  onClick={() => testPayload(payload)}
                  style={styles.smallButton}
                  title={payload}
                >
                  #{idx + 1}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={styles.outputSection}>
        <h4>렌더링 결과:</h4>
        <div style={styles.outputBox}>
          {renderMode === 'safe' ? (
            // 안전: React가 자동으로 이스케이프
            <div>{output}</div>
          ) : (
            // 취약: 실제 앱에서는 절대 이렇게 하면 안 됨
            <div dangerouslySetInnerHTML={{ __html: output }} />
          )}
        </div>
        <p style={styles.hint}>
          {renderMode === 'safe'
            ? '✅ React가 HTML을 이스케이프하여 스크립트가 실행되지 않습니다.'
            : '❌ dangerouslySetInnerHTML 사용 시 스크립트가 실행될 수 있습니다.'}
        </p>
      </div>
    </div>
  );
}

// ============================================================
// SQL/NoSQL Injection 테스트 패널
// ============================================================

function InjectionTestPanel({ onResult }) {
  const [input, setInput] = useState('');
  const [queryType, setQueryType] = useState('sql');

  const payloads = queryType === 'sql' ? SQL_PAYLOADS.basic : SQL_PAYLOADS.noSQL;

  const testPayload = (payload) => {
    setInput(typeof payload === 'string' ? payload : JSON.stringify(payload));

    // 시뮬레이션: 실제로는 백엔드에서 테스트해야 함
    console.log(`[Injection Test] Type: ${queryType}, Payload:`, payload);

    onResult(prev => [...prev, {
      type: 'Injection',
      queryType,
      payload: String(payload).substring(0, 50),
      note: '서버 로그 확인 필요',
    }]);
  };

  return (
    <div style={styles.panel}>
      <h2>SQL/NoSQL Injection 테스트</h2>
      <p style={styles.note}>
        ⚠️ Injection 취약점은 백엔드에서 발생합니다.
        프론트엔드에서는 페이로드를 생성하고, 서버 응답/로그를 확인하세요.
      </p>

      <div style={styles.modeSelector}>
        <label>
          <input
            type="radio"
            value="sql"
            checked={queryType === 'sql'}
            onChange={(e) => setQueryType(e.target.value)}
          />
          SQL Injection
        </label>
        <label>
          <input
            type="radio"
            value="nosql"
            checked={queryType === 'nosql'}
            onChange={(e) => setQueryType(e.target.value)}
          />
          NoSQL Injection
        </label>
      </div>

      <div style={styles.inputGroup}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="검색어 또는 필터 값으로 사용될 입력..."
          style={styles.textarea}
        />
        <button onClick={() => testPayload(input)} style={styles.button}>
          페이로드 복사
        </button>
      </div>

      <div style={styles.payloadList}>
        <h4>테스트 페이로드:</h4>
        {payloads.map((payload, idx) => (
          <button
            key={idx}
            onClick={() => testPayload(payload)}
            style={styles.payloadItem}
          >
            {typeof payload === 'string' ? payload : JSON.stringify(payload)}
          </button>
        ))}
      </div>

      <div style={styles.codeBlock}>
        <h4>안전한 쿼리 예시:</h4>
        <pre>
{`// ❌ 취약
const query = \`SELECT * FROM users WHERE name = '\${userInput}'\`;

// ✅ 안전 (Parameterized Query)
const query = 'SELECT * FROM users WHERE name = $1';
db.query(query, [userInput]);

// ✅ NoSQL 안전 (입력 타입 검증)
if (typeof userInput !== 'string') throw new Error('Invalid input');
db.collection.find({ name: userInput });`}
        </pre>
      </div>
    </div>
  );
}

// ============================================================
// Open Redirect 테스트 패널
// ============================================================

function RedirectTestPanel({ onResult }) {
  const [url, setUrl] = useState('');
  const [testResults, setTestResults] = useState([]);

  const isValidRedirect = (urlString) => {
    try {
      if (urlString.startsWith('/') && !urlString.startsWith('//')) {
        return { safe: true, reason: '상대 경로' };
      }
      const parsed = new URL(urlString, window.location.origin);
      if (parsed.origin === window.location.origin) {
        return { safe: true, reason: '동일 오리진' };
      }
      return { safe: false, reason: `외부 도메인: ${parsed.origin}` };
    } catch {
      return { safe: false, reason: '잘못된 URL' };
    }
  };

  const testRedirect = (testUrl) => {
    const result = isValidRedirect(testUrl);
    const newResult = {
      url: testUrl,
      ...result,
    };
    setTestResults(prev => [...prev, newResult]);
    onResult(prev => [...prev, {
      type: 'Open Redirect',
      url: testUrl.substring(0, 50),
      vulnerable: !result.safe,
    }]);
  };

  return (
    <div style={styles.panel}>
      <h2>Open Redirect 테스트</h2>

      <div style={styles.inputGroup}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="리다이렉트 URL 입력..."
          style={styles.input}
        />
        <button onClick={() => testRedirect(url)} style={styles.button}>
          검증
        </button>
      </div>

      <div style={styles.payloadList}>
        <h4>테스트 페이로드:</h4>
        {OPEN_REDIRECT_PAYLOADS.map((payload, idx) => (
          <button
            key={idx}
            onClick={() => testRedirect(payload)}
            style={styles.payloadItem}
          >
            {payload}
          </button>
        ))}
      </div>

      {testResults.length > 0 && (
        <div style={styles.resultList}>
          <h4>검증 결과:</h4>
          {testResults.map((result, idx) => (
            <div
              key={idx}
              style={{
                ...styles.resultItem,
                borderColor: result.safe ? '#22c55e' : '#ef4444',
              }}
            >
              <code>{result.url}</code>
              <span style={{ color: result.safe ? '#22c55e' : '#ef4444' }}>
                {result.safe ? '✅ 안전' : '❌ 위험'}: {result.reason}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// 보안 헤더 테스트 패널
// ============================================================

function HeadersTestPanel({ onResult }) {
  const [url, setUrl] = useState(window.location.origin);
  const [headers, setHeaders] = useState(null);
  const [loading, setLoading] = useState(false);

  const checkHeaders = async () => {
    setLoading(true);
    const result = await checkSecurityHeaders(url);
    setHeaders(result);
    setLoading(false);

    if (!result.error) {
      const missing = Object.entries(result)
        .filter(([, v]) => !v.present)
        .map(([k]) => k);

      onResult(prev => [...prev, {
        type: 'Security Headers',
        url,
        missingHeaders: missing,
        vulnerable: missing.length > 0,
      }]);
    }
  };

  return (
    <div style={styles.panel}>
      <h2>보안 헤더 검사</h2>

      <div style={styles.inputGroup}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="검사할 URL..."
          style={styles.input}
        />
        <button onClick={checkHeaders} style={styles.button} disabled={loading}>
          {loading ? '검사 중...' : '헤더 검사'}
        </button>
      </div>

      {headers && !headers.error && (
        <div style={styles.headerResults}>
          {Object.entries(headers).map(([name, { present, value }]) => (
            <div key={name} style={styles.headerItem}>
              <span style={{ color: present ? '#22c55e' : '#ef4444' }}>
                {present ? '✅' : '❌'} {name}
              </span>
              {present && <code style={styles.headerValue}>{value}</code>}
            </div>
          ))}
        </div>
      )}

      <div style={styles.codeBlock}>
        <h4>권장 보안 헤더 설정 (Express.js):</h4>
        <pre>
{`const helmet = require('helmet');

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:", "https:"],
    },
  },
  hsts: { maxAge: 31536000, includeSubDomains: true },
  frameguard: { action: 'deny' },
  noSniff: true,
  xssFilter: true,
}));`}
        </pre>
      </div>
    </div>
  );
}

// ============================================================
// Prototype Pollution 테스트 패널
// ============================================================

function PrototypeTestPanel({ onResult }) {
  const [testLog, setTestLog] = useState([]);

  // 취약한 merge 함수 (테스트용)
  const vulnerableMerge = (target, source) => {
    for (const key in source) {
      if (typeof source[key] === 'object' && source[key] !== null) {
        if (!target[key]) target[key] = {};
        vulnerableMerge(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
    return target;
  };

  // 안전한 merge 함수
  const safeMerge = (target, source) => {
    const forbidden = ['__proto__', 'constructor', 'prototype'];
    for (const key in source) {
      if (forbidden.includes(key)) continue;
      if (!Object.prototype.hasOwnProperty.call(source, key)) continue;

      if (typeof source[key] === 'object' && source[key] !== null) {
        if (!target[key]) target[key] = {};
        safeMerge(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
    return target;
  };

  const runTest = (mergeFn, name) => {
    const results = testPrototypePollution(mergeFn);
    setTestLog(prev => [...prev, { name, results }]);

    results.forEach(r => {
      onResult(prev => [...prev, {
        type: 'Prototype Pollution',
        function: name,
        ...r,
      }]);
    });
  };

  return (
    <div style={styles.panel}>
      <h2>Prototype Pollution 테스트</h2>

      <div style={styles.buttonGroup}>
        <button
          onClick={() => runTest(vulnerableMerge, 'vulnerableMerge')}
          style={{ ...styles.button, backgroundColor: '#ef4444' }}
        >
          취약한 함수 테스트
        </button>
        <button
          onClick={() => runTest(safeMerge, 'safeMerge')}
          style={{ ...styles.button, backgroundColor: '#22c55e' }}
        >
          안전한 함수 테스트
        </button>
      </div>

      {testLog.length > 0 && (
        <div style={styles.testLog}>
          {testLog.map((log, idx) => (
            <div key={idx} style={styles.logEntry}>
              <h4>{log.name} 테스트 결과:</h4>
              {log.results.map((r, i) => (
                <div
                  key={i}
                  style={{
                    color: r.vulnerable ? '#ef4444' : '#22c55e',
                    padding: '4px 0',
                  }}
                >
                  {r.message}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// 스타일
// ============================================================

const styles = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: 'system-ui, sans-serif',
    backgroundColor: '#1f2937',
    color: '#f3f4f6',
    minHeight: '100vh',
  },
  title: {
    fontSize: '24px',
    marginBottom: '8px',
  },
  warning: {
    backgroundColor: '#7c2d12',
    padding: '12px',
    borderRadius: '8px',
    marginBottom: '20px',
  },
  nav: {
    display: 'flex',
    gap: '8px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  navButton: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    color: 'white',
    cursor: 'pointer',
  },
  content: {
    backgroundColor: '#374151',
    borderRadius: '8px',
    padding: '20px',
  },
  panel: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  modeSelector: {
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap',
  },
  inputGroup: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  textarea: {
    flex: 1,
    minWidth: '200px',
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #4b5563',
    backgroundColor: '#1f2937',
    color: '#f3f4f6',
    minHeight: '80px',
  },
  input: {
    flex: 1,
    minWidth: '200px',
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #4b5563',
    backgroundColor: '#1f2937',
    color: '#f3f4f6',
  },
  button: {
    padding: '8px 16px',
    backgroundColor: '#3b82f6',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  smallButton: {
    padding: '4px 8px',
    backgroundColor: '#4b5563',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    margin: '2px',
  },
  buttonGroup: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  payloadList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  payloadButtons: {
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
    marginTop: '4px',
  },
  payloadItem: {
    padding: '8px',
    backgroundColor: '#1f2937',
    border: '1px solid #4b5563',
    borderRadius: '4px',
    color: '#f3f4f6',
    cursor: 'pointer',
    textAlign: 'left',
    fontSize: '12px',
    wordBreak: 'break-all',
  },
  outputSection: {
    backgroundColor: '#1f2937',
    padding: '16px',
    borderRadius: '8px',
  },
  outputBox: {
    backgroundColor: 'white',
    color: 'black',
    padding: '16px',
    borderRadius: '4px',
    minHeight: '50px',
  },
  hint: {
    fontSize: '14px',
    marginTop: '8px',
  },
  note: {
    backgroundColor: '#374151',
    padding: '12px',
    borderRadius: '4px',
  },
  codeBlock: {
    backgroundColor: '#1f2937',
    padding: '16px',
    borderRadius: '8px',
    overflow: 'auto',
  },
  resultList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  resultItem: {
    padding: '12px',
    backgroundColor: '#1f2937',
    borderRadius: '4px',
    borderLeft: '4px solid',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '8px',
  },
  headerResults: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  headerItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  headerValue: {
    fontSize: '12px',
    color: '#9ca3af',
    wordBreak: 'break-all',
  },
  testLog: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  logEntry: {
    backgroundColor: '#1f2937',
    padding: '12px',
    borderRadius: '8px',
  },
  results: {
    marginTop: '20px',
    backgroundColor: '#374151',
    borderRadius: '8px',
    padding: '20px',
  },
  resultPre: {
    backgroundColor: '#1f2937',
    padding: '16px',
    borderRadius: '4px',
    overflow: 'auto',
    fontSize: '12px',
  },
};
