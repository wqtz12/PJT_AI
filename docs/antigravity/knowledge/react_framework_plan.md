# React Standard Framework Boilerplate

A blueprint for a standardized React framework based on Next.js, designed for internal productivity and consistency.

## Core Stack

- **Framework**: Next.js (Pages Router preferred)
- **Language**: TypeScript (strict typing)
- **Styling**: Tailwind CSS
- **Code Quality**: ESLint (Airbnb configurations), Prettier
- **Testing**: Jest, React Testing Library

## Directory Structure

```
src/
 ├── components/       # Reusable UI components (PascalCase)
 │   ├── common/       # Atomic elements (buttons, inputs)
 │   └── layout/       # Structural elements (headers, footers)
 ├── pages/            # Next.js Routes (lowercase)
 ├── lib/              # Custom hooks and type definitions
 ├── styles/           # Global styles
 ├── utils/            # Shared business logic and external integrations
 └── config/           # Environment and constant configurations
```

## Implementation Strategy

1. **Phase 1**: Base environment setup (Eslint, Prettier, Absolute Imports).
2. **Phase 2**: Directory skeleton and core module implementation (Fetch utility, JSDoc standards).
3. **Phase 3**: Global UI system and Tailwind theme customization.
4. **Phase 5**: Testing infrastructure (Jest config, sample tests).
