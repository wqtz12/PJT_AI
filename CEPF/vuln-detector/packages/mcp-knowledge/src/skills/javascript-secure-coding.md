# JavaScript Secure Coding Guide (SKILL.md)

---
name: javascript-secure-coding
description: JavaScript 및 Node.js 환경에서의 보안 코딩 가이드라인
---

## XSS (Cross-Site Scripting)

### Next.js / React
- **기본 보호**: React의 `{}` 바인딩은 기본적으로 HTML을 이스케이프합니다.
- **주의**: `dangerouslySetInnerHTML`은 XSS 취약점을 유발할 수 있습니다.

**취약한 코드**:
```jsx
// ❌ 사용자 입력을 직접 HTML로 렌더링
<div dangerouslySetInnerHTML={{ __html: userInput }} />
```

**안전한 코드**:
```jsx
// ✅ DOMPurify로 Sanitize 후 렌더링
import DOMPurify from 'isomorphic-dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />
```

### Express.js
- **템플릿 엔진**: EJS, Pug 등에서 `<%- %>` (unescaped) 대신 `<%= %>` (escaped) 사용
- **응답 헤더**: `Content-Type`을 명시적으로 설정

**취약한 코드**:
```javascript
// ❌ 사용자 데이터를 직접 응답에 포함
res.send(`<h1>Hello ${req.query.name}</h1>`);
```

**안전한 코드**:
```javascript
// ✅ 템플릿 엔진의 이스케이프 기능 활용
res.render('hello', { name: req.query.name });
// hello.ejs: <h1>Hello <%= name %></h1>
```

---

## SQL Injection

### Node.js (pg / mysql2)
- **파라미터화된 쿼리**: 문자열 연결 대신 Placeholder($1, ?)를 사용

**취약한 코드**:
```javascript
// ❌ 문자열 연결 - SQL Injection 가능
const query = "SELECT * FROM users WHERE id = " + req.query.id;
db.query(query);
```

**안전한 코드**:
```javascript
// ✅ Parameterized Query
const query = "SELECT * FROM users WHERE id = $1";
db.query(query, [req.query.id]);
```

### TypeORM / Prisma
- **ORM 사용 권장**: ORM은 기본적으로 파라미터화된 쿼리를 사용
- **Raw Query 주의**: `query()` 메서드 사용 시 파라미터 바인딩 필수

---

## Command Injection

### Node.js
- **child_process 주의**: `exec()` 대신 `execFile()` 또는 `spawn()` 사용
- **사용자 입력 금지**: 명령어에 사용자 입력 포함 금지

**취약한 코드**:
```javascript
// ❌ 사용자 입력이 명령어에 포함
const { exec } = require('child_process');
exec(`ls ${req.query.dir}`);
```

**안전한 코드**:
```javascript
// ✅ execFile로 인자 분리
const { execFile } = require('child_process');
execFile('ls', [req.query.dir], { shell: false });
```

---

## Path Traversal

### 파일 시스템 접근
- **경로 정규화**: `path.resolve()` 후 허용된 디렉토리 내 위치 확인

**취약한 코드**:
```javascript
// ❌ 사용자 입력으로 파일 경로 직접 구성
const filePath = './uploads/' + req.query.filename;
fs.readFile(filePath);
```

**안전한 코드**:
```javascript
// ✅ 경로 정규화 및 검증
const basePath = path.resolve('./uploads');
const filePath = path.resolve(basePath, req.query.filename);
if (!filePath.startsWith(basePath)) {
  throw new Error('Invalid path');
}
```

---

## 인증 및 세션 관리

### JWT
- **비밀키 관리**: 환경 변수에 저장, 코드에 하드코딩 금지
- **알고리즘 명시**: `algorithm` 옵션을 명시적으로 지정

### 세션
- **httpOnly, secure 플래그**: 쿠키 설정 시 반드시 활성화
- **세션 고정 방지**: 로그인 후 세션 ID 재생성

---

## 의존성 보안

### npm 패키지
- **정기 감사**: `npm audit` 정기 실행
- **lockfile 사용**: `package-lock.json` 커밋
- **신뢰할 수 있는 패키지**: 다운로드 수, 유지보수 상태 확인
