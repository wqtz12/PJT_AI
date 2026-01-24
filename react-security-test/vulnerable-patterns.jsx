/**
 * React 웹 취약점 패턴 및 보안 테스트 가이드
 * 목적: 자체 앱 보안 점검용
 *
 * 각 섹션은 다음을 포함합니다:
 * 1. 취약한 코드 패턴 (❌)
 * 2. 공격 페이로드 예시
 * 3. 시큐어 코딩 방법 (✅)
 */

// ============================================================
// 1. XSS (Cross-Site Scripting) 취약점
// ============================================================

// ❌ 취약한 코드: dangerouslySetInnerHTML 오용
function VulnerableXSS({ userInput }) {
  return (
    <div dangerouslySetInnerHTML={{ __html: userInput }} />
  );
}

// 🔴 공격 테스트 페이로드
const xssPayloads = [
  '<script>alert("XSS")</script>',
  '<img src=x onerror="alert(document.cookie)">',
  '<svg onload="alert(1)">',
  '<body onpageshow="alert(1)">',
  '"><script>alert(String.fromCharCode(88,83,83))</script>',
  '<iframe src="javascript:alert(1)">',
  '<a href="javascript:alert(1)">Click</a>',
];

// ✅ 시큐어 코딩: DOMPurify 사용
import DOMPurify from 'dompurify';

function SecureXSS({ userInput }) {
  const sanitized = DOMPurify.sanitize(userInput, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br'],
    ALLOWED_ATTR: []
  });
  return (
    <div dangerouslySetInnerHTML={{ __html: sanitized }} />
  );
}

// ✅ 더 좋은 방법: HTML 파싱 자체를 피함
function BestPracticeXSS({ userInput }) {
  return <div>{userInput}</div>; // React가 자동으로 이스케이프
}


// ============================================================
// 2. URL 기반 XSS (href, src 속성)
// ============================================================

// ❌ 취약한 코드: 사용자 입력을 href에 직접 사용
function VulnerableLink({ url }) {
  return <a href={url}>Click here</a>;
}

// 🔴 공격 테스트 페이로드
const urlXssPayloads = [
  'javascript:alert(document.domain)',
  'javascript:eval(atob("YWxlcnQoMSk="))',
  'data:text/html,<script>alert(1)</script>',
  'vbscript:msgbox("XSS")',
];

// ✅ 시큐어 코딩: URL 프로토콜 검증
function SecureLink({ url }) {
  const isValidUrl = (urlString) => {
    try {
      const parsed = new URL(urlString);
      return ['http:', 'https:', 'mailto:'].includes(parsed.protocol);
    } catch {
      return false;
    }
  };

  if (!isValidUrl(url)) {
    return <span>Invalid URL</span>;
  }
  return <a href={url}>Click here</a>;
}


// ============================================================
// 3. Stored XSS via JSON Injection
// ============================================================

// ❌ 취약한 코드: 서버 데이터를 그대로 렌더링
function VulnerableSSR({ serverData }) {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `window.__INITIAL_STATE__ = ${JSON.stringify(serverData)}`
      }}
    />
  );
}

// 🔴 공격 테스트: 서버 데이터에 악성 스크립트 삽입
const maliciousServerData = {
  user: '</script><script>alert("XSS")</script><script>',
  comment: '{"name":"</script><script>alert(1)</script>"}'
};

// ✅ 시큐어 코딩: serialize-javascript 사용
import serialize from 'serialize-javascript';

function SecureSSR({ serverData }) {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `window.__INITIAL_STATE__ = ${serialize(serverData, { isJSON: true })}`
      }}
    />
  );
}


// ============================================================
// 4. Prototype Pollution
// ============================================================

// ❌ 취약한 코드: 깊은 객체 병합 시 검증 없음
function vulnerableMerge(target, source) {
  for (const key in source) {
    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {};
      vulnerableMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

// 🔴 공격 테스트 페이로드
const pollutionPayload = JSON.parse('{"__proto__":{"isAdmin":true}}');
// vulnerableMerge({}, pollutionPayload);
// console.log({}.isAdmin); // true - 모든 객체에 영향

// ✅ 시큐어 코딩: 프로토타입 키 필터링
function secureMerge(target, source) {
  const forbiddenKeys = ['__proto__', 'constructor', 'prototype'];

  for (const key in source) {
    if (forbiddenKeys.includes(key)) continue;
    if (!Object.prototype.hasOwnProperty.call(source, key)) continue;

    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {};
      secureMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}


// ============================================================
// 5. Open Redirect 취약점
// ============================================================

// ❌ 취약한 코드: 검증 없는 리다이렉트
function VulnerableRedirect() {
  const params = new URLSearchParams(window.location.search);
  const redirectUrl = params.get('redirect');

  const handleClick = () => {
    window.location.href = redirectUrl; // 위험!
  };

  return <button onClick={handleClick}>Continue</button>;
}

// 🔴 공격 테스트 URL
const openRedirectPayloads = [
  '//evil.com',
  'https://evil.com',
  '//evil.com%2F@trusted.com',
  '/\\evil.com',
  'https://trusted.com@evil.com',
];

// ✅ 시큐어 코딩: 화이트리스트 기반 검증
function SecureRedirect() {
  const ALLOWED_HOSTS = ['myapp.com', 'www.myapp.com'];

  const isValidRedirect = (url) => {
    try {
      // 상대 경로만 허용하거나
      if (url.startsWith('/') && !url.startsWith('//')) {
        return true;
      }
      // 허용된 도메인만 허용
      const parsed = new URL(url);
      return ALLOWED_HOSTS.includes(parsed.host);
    } catch {
      return false;
    }
  };

  const params = new URLSearchParams(window.location.search);
  const redirectUrl = params.get('redirect') || '/';

  const handleClick = () => {
    if (isValidRedirect(redirectUrl)) {
      window.location.href = redirectUrl;
    } else {
      window.location.href = '/';
    }
  };

  return <button onClick={handleClick}>Continue</button>;
}


// ============================================================
// 6. CSRF (Cross-Site Request Forgery)
// ============================================================

// ❌ 취약한 코드: CSRF 토큰 없음
function VulnerableForm() {
  const handleSubmit = async (e) => {
    e.preventDefault();
    await fetch('/api/transfer', {
      method: 'POST',
      body: new FormData(e.target),
      credentials: 'include' // 쿠키 자동 포함
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="amount" />
      <input name="to" />
      <button type="submit">Transfer</button>
    </form>
  );
}

// 🔴 공격 페이지 예시 (공격자 사이트에서 실행)
const csrfAttackPage = `
<html>
<body onload="document.forms[0].submit()">
  <form action="https://target-app.com/api/transfer" method="POST">
    <input type="hidden" name="amount" value="10000" />
    <input type="hidden" name="to" value="attacker" />
  </form>
</body>
</html>
`;

// ✅ 시큐어 코딩: CSRF 토큰 사용
function SecureForm() {
  const [csrfToken, setCsrfToken] = useState('');

  useEffect(() => {
    // 서버에서 CSRF 토큰 획득
    fetch('/api/csrf-token')
      .then(res => res.json())
      .then(data => setCsrfToken(data.token));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    await fetch('/api/transfer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken // CSRF 토큰 헤더로 전송
      },
      body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      credentials: 'include'
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="amount" />
      <input name="to" />
      <button type="submit">Transfer</button>
    </form>
  );
}


// ============================================================
// 7. Insecure Direct Object Reference (IDOR)
// ============================================================

// ❌ 취약한 코드: 권한 검증 없이 데이터 접근
function VulnerableProfile() {
  const { userId } = useParams(); // URL에서 userId 가져옴
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    fetch(`/api/users/${userId}`) // 다른 사용자 ID로 접근 가능
      .then(res => res.json())
      .then(setProfile);
  }, [userId]);

  return <div>{profile?.email}</div>;
}

// 🔴 공격 테스트: URL의 userId를 다른 값으로 변경
// /profile/1 → /profile/2 → /profile/3 (순차적 접근)

// ✅ 시큐어 코딩: 서버에서 권한 검증 + 클라이언트에서 자신의 ID만 사용
function SecureProfile() {
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    // 현재 로그인한 사용자의 프로필만 조회 (서버에서 토큰으로 식별)
    fetch('/api/users/me', {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      }
    })
      .then(res => res.json())
      .then(setProfile);
  }, []);

  return <div>{profile?.email}</div>;
}


// ============================================================
// 8. Sensitive Data Exposure
// ============================================================

// ❌ 취약한 코드: 민감 정보가 클라이언트에 노출
function VulnerableUserList({ users }) {
  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>
          {user.name}
          {/* 아래 정보가 DOM에 숨겨져 있어도 개발자 도구로 확인 가능 */}
          <span style={{ display: 'none' }}>
            Password: {user.password}
            SSN: {user.ssn}
          </span>
        </li>
      ))}
    </ul>
  );
}

// 🔴 공격: 개발자 도구 → Network 탭에서 API 응답 확인
// 또는 React DevTools에서 props 확인

// ✅ 시큐어 코딩: 서버에서 필요한 필드만 반환
// 서버 API: SELECT id, name FROM users (password, ssn 제외)
function SecureUserList({ users }) {
  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}


// ============================================================
// 9. SQL Injection via GraphQL
// ============================================================

// ❌ 취약한 GraphQL 쿼리 구성
function VulnerableSearch({ searchTerm }) {
  const query = `
    query {
      users(filter: "${searchTerm}") {
        id
        name
      }
    }
  `;

  // searchTerm에 악성 입력이 들어갈 수 있음
  return fetch('/graphql', {
    method: 'POST',
    body: JSON.stringify({ query })
  });
}

// 🔴 공격 테스트 페이로드
const graphqlInjectionPayloads = [
  '") { id } users(filter: "',
  '") { id name email password } users(filter: "',
];

// ✅ 시큐어 코딩: 변수 사용
function SecureSearch({ searchTerm }) {
  const query = `
    query SearchUsers($filter: String!) {
      users(filter: $filter) {
        id
        name
      }
    }
  `;

  return fetch('/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      variables: { filter: searchTerm }
    })
  });
}


// ============================================================
// 10. 취약점 테스트 자동화 도구 사용 예시
// ============================================================

/**
 * 자체 앱 보안 테스트 체크리스트:
 *
 * 1. XSS 테스트
 *    - 모든 입력 필드에 XSS 페이로드 삽입
 *    - URL 파라미터에 스크립트 삽입
 *    - dangerouslySetInnerHTML 사용처 검토
 *
 * 2. 인증/인가 테스트
 *    - 로그아웃 후 이전 URL 직접 접근
 *    - 다른 사용자 리소스 접근 시도
 *    - JWT 토큰 만료 처리 확인
 *
 * 3. CSRF 테스트
 *    - 외부 페이지에서 API 호출 시도
 *    - CSRF 토큰 없이 요청 전송
 *
 * 4. 데이터 노출 테스트
 *    - Network 탭에서 API 응답 검사
 *    - 민감 정보 포함 여부 확인
 *    - React DevTools로 state/props 검사
 *
 * 추천 도구:
 * - OWASP ZAP (자동화 스캐닝)
 * - Burp Suite (수동 테스트)
 * - ESLint 보안 플러그인 (eslint-plugin-security)
 */

export {
  VulnerableXSS,
  SecureXSS,
  xssPayloads,
  urlXssPayloads,
  VulnerableLink,
  SecureLink,
  pollutionPayload,
  secureMerge,
  openRedirectPayloads,
  SecureRedirect,
  SecureForm,
  SecureProfile,
  SecureSearch,
};