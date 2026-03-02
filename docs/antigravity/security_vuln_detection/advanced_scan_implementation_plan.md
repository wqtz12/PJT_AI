# Implementation Plan - Advanced Vulnerability Scanning Workflow

## Goal Description
Implement a new scanning process that involves downloading source code from Git, analyzing its architecture, identifying high-severity vulnerabilities (Score >= 8) specific to that architecture, registering them as custom skills, and executing a scan.

## User Review Required
> [!IMPORTANT]
> **Refactoring `mcp-server.js`**: The existing `mcp-server.js` has hardcoded vulnerabilities. I will refactor this to load vulnerabilities from a `vulnerabilities.json` file. This is a change to the existing architecture to support dynamic skill registration.

> [!NOTE]
> **Interactive Workflow**: The new process will be a Node.js script (`advanced_scan_flow.js`) that requires user interaction (confirmation of architecture) in the terminal.

## Proposed Changes

### 1. Refactor `react-security-test`
#### [MODIFY] [mcp-server.js](file:///Users/jbs/PJT_AI/react-security-test/mcp-server.js)
-   Remove hardcoded `VULNERABILITIES` constant.
-   Add logic to load `VULNERABILITIES` from `vulnerabilities.json`.
-   Add a watcher or reload mechanism if needed, or simply load on startup.

#### [NEW] [vulnerabilities.json](file:///Users/jbs/PJT_AI/react-security-test/vulnerabilities.json)
-   Initial content will be the currently hardcoded vulnerabilities.

### 2. Create New Workflow Script
#### [NEW] [advanced_scan_flow.js](file:///Users/jbs/PJT_AI/react-security-test/advanced_scan_flow.js)
-   **Step 1 & 2**: prompt for Git URL and clone using `git-clone` or `child_process`.
-   **Step 3**: `analyzeArchitecture()` function. 
    -   Scans file extensions and imports (e.g., `mongoose` -> MongoDB, `react` -> React).
    -   Generates a text description of the architecture.
-   **Step 4**: Prompt user for confirmation of the architecture.
-   **Step 5**: `findAdvancedVulnerabilities()` function.
    -   Based on architecture, selects/adds high-severity vulnerabilities (CVSS >= 8).
    -   Example: If 'Node.js' + 'Exec' found -> Suggest 'OS Command Injection'.
-   **Step 6**: Update `vulnerabilities.json` with any new custom skills/payloads found.
-   **Step 7**: Trigger the scan (programmatically import `scanAll` from `mcp-server.js` or run it via MCP).
-   **Step 8**: `generateReport()` and save to file.

## Verification Plan

### Automated Tests
-   Verify `mcp-server.js` still works with `vulnerabilities.json` by running it and creating a dummy request.
-   Test `advanced_scan_flow.js` with a dummy local git repo (or skip git part for testing) and verify it generates a report.

### Manual Verification
-   Run `node advanced_scan_flow.js`.
-   Input a sample Git URL (e.g., a dummy repo or the current one).
-   Confirm the architecture analysis output.
-   Verify that new vulnerabilities are added to `vulnerabilities.json`.
-   Check the final report.
