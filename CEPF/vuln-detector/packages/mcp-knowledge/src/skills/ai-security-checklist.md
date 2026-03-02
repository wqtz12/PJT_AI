# AI Security Checklist (SKILL.md)

---
name: ai-security-checklist
description: AI/LLM 서비스 보안 및 AI 기본법 준수 체크리스트
---

## Prompt Injection 방어

### 시스템 프롬프트 보호
- [ ] 시스템 프롬프트를 사용자 입력과 명확히 분리
- [ ] 사용자 입력 내용을 시스템 프롬프트에 직접 삽입 금지
- [ ] 입력 검증 및 필터링 적용

**취약한 코드**:
```javascript
// ❌ 사용자 입력이 시스템 프롬프트에 직접 삽입
const systemPrompt = `You are a helpful assistant. User profile: ${userInput}`;
```

**안전한 코드**:
```javascript
// ✅ 사용자 입력을 별도 메시지로 분리
const messages = [
  { role: "system", content: "You are a helpful assistant." },
  { role: "user", content: userInput }
];
```

### Indirect Prompt Injection
- [ ] 외부 데이터(웹 검색 결과, 문서)에 대한 신뢰도 제한
- [ ] 외부 데이터 삽입 시 샌드박싱 또는 마크업 적용

---

## 모델 출력 검증

### 출력 필터링
- [ ] 유해 콘텐츠 필터 적용
- [ ] 개인정보 탐지 및 마스킹
- [ ] 민감 정보(API 키 등) 노출 방지

```javascript
// ✅ 출력 필터링 예시
const output = await llm.generate(prompt);
const sanitized = filterSensitiveInfo(output);
if (containsHarmfulContent(sanitized)) {
  return { error: "Unable to provide this response" };
}
return sanitized;
```

### Hallucination 대응
- [ ] 사실 확인이 필요한 출력에 대한 경고 표시
- [ ] 참조 출처 제공 시스템 구축
- [ ] 확실하지 않은 정보에 대해 "확인 필요" 표기

---

## 데이터 보안

### 학습 데이터 보호
- [ ] 민감 정보가 포함된 데이터 학습 금지
- [ ] 데이터 익명화/가명화 처리
- [ ] 학습 데이터 출처 추적 가능하게 관리

### 추론 데이터 보호
- [ ] 사용자 프롬프트 로깅 시 동의 획득
- [ ] 프롬프트에서 개인정보 자동 제거
- [ ] 추론 로그 보관 기간 최소화

---

## AI 기본법 준수

### 투명성 의무
- [ ] AI 시스템 사용 사실 고지 (AI 생성 콘텐츠 표시)
- [ ] AI 의사결정 로직에 대한 설명 가능성 확보
- [ ] 사용자가 AI 응답임을 인지할 수 있도록 표시

### 인간 감독
- [ ] 고위험 결정에 인간 검토 절차 포함
- [ ] AI 결정에 대한 이의 제기 절차 마련
- [ ] 자동화된 의사결정의 영향 평가 수행

### 공정성
- [ ] 편향성 테스트 정기 수행
- [ ] 차별적 결과 모니터링
- [ ] 피해 발생 시 신속한 대응 체계 구축

---

## API 보안

### 인증 및 권한
- [ ] API 키 안전한 저장 (환경 변수)
- [ ] Rate Limiting 적용
- [ ] 요청별 사용자 인증

### 비용 보호
- [ ] 토큰 사용량 모니터링
- [ ] 이상 사용 패턴 탐지
- [ ] 일일/월별 사용 한도 설정

**취약한 코드**:
```javascript
// ❌ API 키 하드코딩
const client = new OpenAI({ apiKey: "sk-..." });
```

**안전한 코드**:
```javascript
// ✅ 환경 변수 사용
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
```

---

## 모델 서빙 보안

### 모델 파일 보호
- [ ] 모델 가중치 파일 접근 제한
- [ ] 모델 역공학 방지 조치
- [ ] 무결성 검증 (체크섬)

### 인프라 보안
- [ ] GPU 서버 네트워크 격리
- [ ] 추론 요청 로깅 및 감사
- [ ] 컨테이너 보안 스캔
