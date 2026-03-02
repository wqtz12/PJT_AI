# Privacy Checklist (SKILL.md)

---
name: privacy-checklist
description: 개인정보보호법 준수를 위한 개발자 체크리스트
---

## 개인정보 수집

### 동의 획득
- [ ] 필수 항목과 선택 항목을 구분하여 고지
- [ ] 수집 목적을 명확하게 고지
- [ ] 보유 기간을 명시
- [ ] 동의 철회 방법 안내

### 최소 수집 원칙
- [ ] 서비스 제공에 필요한 최소한의 정보만 수집
- [ ] 주민등록번호 수집 금지 (법적 근거 없는 경우)

---

## 개인정보 저장

### 암호화
- [ ] 비밀번호: bcrypt, scrypt, argon2 등 단방향 해시 사용
- [ ] 민감정보: AES-256 등 강력한 암호화 적용
- [ ] 전송 시: TLS 1.2 이상 사용

### 접근 제어
- [ ] 개인정보 접근 권한 최소화
- [ ] 접근 로그 기록 및 모니터링
- [ ] 개발/테스트 환경에 실제 개인정보 사용 금지

**취약한 코드**:
```javascript
// ❌ 평문 저장
const user = { password: req.body.password };
db.save(user);
```

**안전한 코드**:
```javascript
// ✅ 해시 저장
import bcrypt from 'bcrypt';
const hashedPassword = await bcrypt.hash(req.body.password, 12);
const user = { password: hashedPassword };
```

---

## 개인정보 이용 및 제공

### 목적 외 이용 금지
- [ ] 수집 목적 범위 내에서만 이용
- [ ] 제3자 제공 시 별도 동의 획득
- [ ] 위탁 시 수탁자 관리·감독

### 마케팅 활용
- [ ] 광고성 정보 수신 동의 별도 획득
- [ ] 수신 거부 방법 명시
- [ ] 야간(21시~08시) 발송 금지

---

## 개인정보 파기

### 파기 원칙
- [ ] 보유 기간 만료 시 지체 없이 파기
- [ ] 복구 불가능한 방법으로 파기
- [ ] 파기 기록 유지

### 기술적 조치
```javascript
// ✅ 안전한 파기 예시
// 1. DB 레코드 삭제
await db.query('DELETE FROM users WHERE id = $1', [userId]);

// 2. 관련 파일 완전 삭제
const { execFile } = require('child_process');
execFile('shred', ['-u', '-z', filePath]); // Linux
```

---

## 정보주체 권리 보장

### 열람권
- [ ] 본인 정보 열람 요청 처리 절차 마련
- [ ] 10일 이내 조치 및 통지

### 정정/삭제권
- [ ] 정정/삭제 요청 처리 절차 마련
- [ ] 삭제 시 복구 불가능하게 처리

### 처리정지권
- [ ] 처리 중지 요청 수용 체계 구축

---

## 로그 및 모니터링

### 접근 로그
- [ ] 개인정보 접근 기록 최소 3년 보관
- [ ] 로그에 실제 개인정보 포함 금지 (ID만 기록)

**취약한 코드**:
```javascript
// ❌ 로그에 개인정보 포함
console.log(`User logged in: ${user.email}, ${user.phone}`);
```

**안전한 코드**:
```javascript
// ✅ 마스킹 처리
console.log(`User logged in: userId=${user.id}`);
```
