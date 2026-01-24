# CEPF Coding Convention Guide

## 1. Tech Stack & Environment
- **Framework:** Next.js (Pages Router)
- **Styling:** Tailwind CSS
- **State/Auth/DB:** Firebase
- **Language:** JavaScript (ES6+)

## 2. Coding Rules (ESLint & Style)
- **Naming Convention:**
  - Function/Variable: `camelCase`
  - Component/Class: `PascalCase`
  - Constant: `UPPER_SNAKE_CASE`
- **Syntax:**
  - Use `const` and `let` (No `var`).
  - Prefer Arrow Functions: `() => { ... }`.
  - Use Explicit Types over `any` (in JSDoc or TS).
- **Comments:**
  - Document "Why", not "What".
  - Use JSDoc for functions: `/** @param {string} userId */`
  - Write comments in Korean.

## 3. Framework Specifics
### Next.js
- **Routing:** Use `pages/` directory structure (lowercase URLs).
- **API:** Place serverless functions in `pages/api/`.
- **Optimization:** Use `next/image` and `next/link`.

### Firebase
- **Security:** NEVER hardcode API Keys. Use `process.env.NEXT_PUBLIC_FIREBASE_API_KEY`.
- **Indexing:** Ensure composite indexes are set in Firestore for complex queries.

### Tailwind CSS
- **Order:** Utility classes first (e.g., layout -> spacing -> typography -> color).
- **Customization:** Define custom colors/fonts in `tailwind.config.js`, avoid arbitrary values like `text-[14px]`.

## 4. Folder Structure
CEPF/
├── public/               # Static assets
├── src/
│   ├── components/       # Reusable UI components (PascalCase)
│   ├── pages/            # Next.js Routes (lowercase)
│   ├── lib/              # Business Logic & Hooks
│   ├── styles/           # Global styles
│   └── utils/            # Helper functions (Firebase init, date parsers)
├── .env.local            # Environment variables (GitIgnored)
└── ...

## 5. Git & Commit Strategy
- **Branch:** `main` (Protected) <- `feature/feature-name`
- **Commit Message Format:** `type: subject`
  - `feat`: New feature
  - `fix`: Bug fix
  - `refactor`: Code restructuring without behavior change
  - `docs`: Documentation only