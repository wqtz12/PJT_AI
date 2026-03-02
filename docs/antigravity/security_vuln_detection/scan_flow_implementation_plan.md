# Implementation Plan: Complete vuln-detector Workflow

## Source Analysis

Analyzed existing files from `react-security-test/`:

| File | Key Functions | Reuse Strategy |
|---|---|---|
| `auto_fix_flow.js` | Git branching, code fix logic, test simulation | → **Adapt into `RemediationService` and `TestService`** |
| `advanced_scan_flow.js` | Git clone, architecture analysis, custom skill registration | → Reference for enhanced analysis (future) |
| `mcp-server.js` | Scan, report generation, email | → Already similar to current MCP packages |

---

## Missing Processes → Services Mapping

| Process | Service | Source Reference |
|---|---|---|
| 소스코드 수정 | `RemediationService` | `auto_fix_flow.js:91-127` (fix logic) |
| Git 백업 | `RemediationService` | `auto_fix_flow.js:62-76` (branching) |
| 테스트 | `TestService` | `auto_fix_flow.js:136-151` |

---

## Proposed New Files

### 1. `src/services/remediation.service.ts`

```typescript
interface IRemediationService {
    createBackupBranch(): Promise<string>;
    generateFix(vuln: VerifiedVulnerability): FixSuggestion;
    applyFix(filePath: string, line: number, fix: FixSuggestion): boolean;
}
```

Fix patterns (from `auto_fix_flow.js`):
- `remove_eval` → Replace `eval()` with error log
- `parameterized_query` → Convert string concat to `?` placeholder
- `sanitize_input` → Wrap with `sanitize()`

---

### 2. `src/services/test.service.ts`

```typescript
interface ITestService {
    runTests(): Promise<TestResult>;
    simulateUserTest(): Promise<boolean>;
}
```

---

### 3. [MODIFY] `src/index.ts`

Add workflow steps:
```
Step 5: Remediation (createBranch → applyFix)
Step 6: Testing (runTests → simulateUserTest)
Step 7: Final Report
```

---

## Verification

1. Build: `npm run build`
2. Dry-run: `npm start -- ./test-assets --dry-run`
