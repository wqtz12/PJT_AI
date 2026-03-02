# 구현 계획서: React (Next.js) 표준 프레임워크 구축

## 1. 개요

사전 정의된 코딩 규칙(`MEMORY[GEMINI.md]`)과 비즈니스 요구사항에 부합하는 프론트엔드 표준 프레임워크(Boilerplate)를 구축합니다. 향후 모든 React 기반 웹 프로젝트의 뼈대가 되며, 확장성과 유지보수성을 극대화하는 디렉토리 구조 및 설정 자동화를 목표로 합니다.

## 2. 기술 스택 (Tech Stack)

- **Core**: Next.js (Pages Router 기반) & React
- **Language**: TypeScript (Any 타입 지양, 명시적 타입 선언)
- **Styling**: Tailwind CSS
- **Linting/Formatting**: ESLint (Airbnb Style Guide), Prettier
- **Testing**: Jest, React Testing Library
- **State Management**: React Context API (필요시 Zustand 확장 적용)

## 3. 핵심 아키텍처 및 디렉토리 구조

프로젝트 루트는 가이드라인에 명시된 구조를 따릅니다.

```
src/
 ├── components/       # 재사용 가능한 UI 컴포넌트 (PascalCase)
 │   ├── common/       # 버튼, 인풋 등 공통 요소
 │   └── layout/       # 헤더, 푸터, 네비게이션
 ├── pages/            # Next.js 라우팅 페이지 (소문자 폴더/파일명)
 │   ├── api/          # Serverless API Routes
 │   ├── index.tsx     # 메인 페이지
 │   └── _app.tsx      # 글로벌 앱 설정
 ├── lib/              # 커스텀 훅 (useFirebaseAuth 등) 및 타입 정의
 ├── styles/           # 전역 스타일
 │   └── globals.css   # Tailwind 지시어 포함
 ├── utils/            # 비즈니스 로직 및 외부 서비스 연동 (firebase.js 등)
 └── config/           # 환경 변수 설정 스키마 및 공통 상수
```

## 4. 코딩 규칙 (Coding Guidelines) 적용 계획

1. **네이밍 컨벤션**:
   - 컴포넌트 & 클래스: `PascalCase` (예: `UserProfile.tsx`)
   - 함수 & 변수: `camelCase` (예: `getUserData`)
   - 페이지: 소문자 (예: `pages/blog/post.tsx`)
2. **ESLint & Prettier**: eslint-config-airbnb-typescript 적용 및 저장 시 자동 포맷팅.
3. **문서화**: 로직이 포함된 함수나 커스텀 훅, 유틸리티 등에는 **JSDoc (한글 주석)** 작성.
4. **타입스크립트**: 명시적 타입(interface/type) 정의 (any 타입 금지).

## 5. 단계별 구현 절차 (Proposed Changes)

### Phase 1: 기반 환경 구성
- `npx create-next-app` 생성 (TypeScript, Tailwind, Pages Router, src directory 활용)
- ESLint (Airbnb), Prettier 설치 및 `.eslintrc.json`, `.prettierrc` 구성
- 절대 경로(Absolute Import) `@/` 설정 (`tsconfig.json`)

### Phase 2: 디렉토리 및 코어 모듈 구성
- `src/` 하위 폴더 뼈대 생성 (components, lib, utils, config 등)
- 데이터 페칭용 커스텀 훅 설계 (`lib/useFetch.ts` 등)
- JSDoc 스니펫 및 기초 유틸리티(`utils/logger.ts`, `utils/api.ts`) 세팅

### Phase 3: 글로벌 스타일 및 UI 시스템
- `tailwind.config.ts` 기본 색상/폰트/단위 테마 설정
- 글로벌 레이아웃 컴포넌트 (`Layout.tsx`, `Header.tsx`) 구현

### Phase 4: 테스트 환경 구축
- Jest & React Testing Library 설치
- `jest.config.js` 및 `jest.setup.js` 설정
- 예제 컴포넌트 로직에 대한 테스트 케이스(`*.test.tsx`) 샘플 작성

## 6. User Review Required

> [!IMPORTANT]
> - Next.js의 버전을 **App Router**(최신) 대신 가이드라인 예시대로 **Pages Router**를 사용할 예정입니다. App Router 전환을 원하시면 피드백 부탁드립니다.
> - 상태 관리 라이브러리로 Recoil/Zustand 등 특정 도구를 선호하시는지, 혹은 기본 Context API로 구성할지 확인이 필요합니다.
