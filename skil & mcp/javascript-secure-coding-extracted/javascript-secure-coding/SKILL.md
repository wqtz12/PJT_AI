---
name: javascript-secure-coding
description: JavaScript 코드의 보안 취약점을 분석하고 시큐어코딩 가이드를 제공하는 skill. 소스코드 보안 점검, 취약점 식별, 시큐어코딩 권장사항 제시, 취약한 코드 패턴 탐지 및 수정 가이드 제공 시 사용. JavaScript, Node.js, TypeScript 프로젝트의 보안 리뷰나 코드 감사에 활용. SQL 인젝션, XSS, CSRF, 인증/인가, 암호화, 입력 검증 등 보안 취약점 분석이 필요할 때 사용.
---

# JavaScript 시큐어코딩 가이드

이 skill은 JavaScript 코드의 보안 취약점을 식별하고 수정하기 위한 종합 가이드를 제공합니다. 한국인터넷진흥원(KISA)의 JavaScript 시큐어코딩 가이드(2023년 개정본)를 기반으로 합니다.

## 주요 보안 취약점 카테고리

### 1. 입력데이터 검증 및 표현
- SQL 삽입 (SQL Injection)
- 코드 삽입 (Code Injection)
- 경로 조작 및 자원 삽입
- 크로스사이트 스크립트 (XSS)
- 운영체제 명령어 삽입
- 위험한 형식 파일 업로드
- 신뢰되지 않은 URL 자동접속
- XML 외부 개체 참조 및 XML 삽입
- LDAP 삽입
- 크로스사이트 요청 위조 (CSRF)
- 서버사이드 요청 위조 (SSRF)
- 보안기능 결정에 사용되는 부적절한 입력값

### 2. 보안기능
- 적절한 인증 없는 중요 기능 허용
- 부적절한 인가
- 중요한 자원에 대한 잘못된 권한 설정
- 취약한 암호화 알고리즘 사용
- 암호화되지 않은 중요정보
- 하드코드된 중요정보
- 충분하지 않은 키 길이
- 적절하지 않은 난수 값 사용
- 취약한 패스워드 허용
- 부적절한 전자서명 확인
- 부적절한 인증서 유효성 검증
- 쿠키를 통한 정보 노출
- 주석문 안에 포함된 시스템 주요정보
- 솔트 없이 일방향 해시 함수 사용
- 무결성 검사없는 코드 다운로드
- 반복된 인증시도 제한 기능 부재

### 3. 시간 및 상태
- 종료되지 않는 반복문 또는 재귀 함수

### 4. 에러처리
- 오류 메시지 정보노출
- 오류상황 대응 부재
- 부적절한 예외 처리

### 5. 코드오류
- Null Pointer 역참조
- 부적절한 자원 해제
- 신뢰할 수 없는 데이터의 역직렬화

### 6. 캡슐화
- 잘못된 세션에 의한 데이터 정보 노출
- 제거되지 않고 남은 디버그 코드
- Public 메소드로부터 반환된 Private 배열
- Private 배열에 Public 데이터 할당

### 7. API 오용
- DNS lookup에 의존한 보안결정
- 취약한 API 사용

## 사용 방법

### 코드 보안 점검 워크플로우

1. **취약점 카테고리 식별**
   - 사용자가 제공한 코드나 프로젝트를 분석
   - 어떤 보안 카테고리에 해당하는지 식별

2. **상세 가이드 참조**
   - `references/guide.md` 파일에서 해당 취약점 섹션 검색
   - grep을 사용한 빠른 검색 가능

3. **취약점 분석 및 보고**
   - 발견된 취약점에 대한 설명
   - 위험도 평가 (상/중/하)
   - 공격 시나리오 설명

4. **수정 방안 제시**
   - 안전한 코드 예시 제공
   - 권장 라이브러리나 프레임워크 제안
   - 단계별 수정 가이드

### 참조 파일 사용

#### references/guide.md
JavaScript 시큐어코딩 가이드 전체 내용 (159페이지, 약 214KB)

**검색 패턴 예시:**
```bash
# SQL 삽입 관련 내용 찾기
grep -A 20 "SQL 삽입" references/guide.md

# XSS 관련 내용 찾기
grep -A 20 "크로스사이트 스크립트" references/guide.md

# 암호화 관련 내용 찾기
grep -A 20 "암호화" references/guide.md

# 인증 관련 내용 찾기
grep -A 20 "인증" references/guide.md

# 특정 페이지 범위 확인 (예: 페이지 10-15)
sed -n '/## 페이지 10/,/## 페이지 15/p' references/guide.md
```

## 코드 점검 예시

### 예시 1: SQL 인젝션 점검
```javascript
// 취약한 코드
const userId = req.query.userId;
const query = `SELECT * FROM users WHERE id = ${userId}`;
db.query(query);

// ❌ 문제점: 사용자 입력을 직접 쿼리에 삽입
// ✅ 해결방안: Prepared Statement 사용
const query = 'SELECT * FROM users WHERE id = ?';
db.query(query, [userId]);
```

### 예시 2: XSS 점검
```javascript
// 취약한 코드
document.getElementById('output').innerHTML = userInput;

// ❌ 문제점: 사용자 입력을 직접 HTML에 삽입
// ✅ 해결방안: 텍스트로 삽입 또는 sanitization
document.getElementById('output').textContent = userInput;
// 또는 DOMPurify 같은 라이브러리 사용
```

### 예시 3: 하드코드된 중요정보
```javascript
// 취약한 코드
const API_KEY = "sk-1234567890abcdef";

// ❌ 문제점: 소스코드에 API 키 하드코딩
// ✅ 해결방안: 환경변수 사용
const API_KEY = process.env.API_KEY;
```

## 보안 점검 보고서 형식

코드 보안 점검 결과는 다음 형식으로 제공:

```markdown
## 보안 점검 결과

### 발견된 취약점 요약
- 총 취약점 수: X개
- 위험도: 상(N개), 중(N개), 하(N개)

### 상세 분석

#### [취약점 #1] SQL 삽입
**위치:** `routes/user.js:45`
**위험도:** 상
**설명:** 사용자 입력을 검증 없이 SQL 쿼리에 직접 삽입
**공격 시나리오:** 악의적인 사용자가 `' OR '1'='1` 입력 시 전체 데이터 조회 가능
**수정 방안:**
- Prepared Statement 사용
- ORM 라이브러리 활용 (Sequelize, TypeORM 등)
**수정 코드:**
[안전한 코드 예시]

...
```

## 지원 범위

- **JavaScript (ES5, ES6+)**
- **Node.js (서버사이드)**
- **TypeScript**
- **프레임워크**: Express.js, React, Vue.js, Angular 등
- **런타임 환경**: 브라우저, Node.js

## 참고사항

- 이 가이드는 2023년 개정본 기준입니다
- 실제 프로덕션 환경에 적용 전 충분한 테스트 필요
- 보안 취약점은 지속적으로 업데이트되므로 최신 정보 참조 권장
- OWASP Top 10과 CWE(Common Weakness Enumeration) 기준 반영됨
