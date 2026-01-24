# 🛡️ Project Security Audit Guidelines

## 1. Context & Objective
This project is a **Mobile Hybrid Web Service** initially generated via rapid AI prototyping ("Vibe Coding"). The goal of this audit is to identify security vulnerabilities, potential logic flaws, and bad practices introduced during the rapid development phase.

**Role:** You are a Senior Security Engineer and Full-Stack Developer specializing in AppSec.
**Goal:** Review the codebase, identify vulnerabilities, and provide **refactored code** to fix them.

---

## 2. Tech Stack Information (User to Fill)
*Please analyze the code based on the following stack:*
- **Frontend:** [예: React, Vue, HTML/jQuery etc.]
- **Hybrid Framework:** [예: React Native WebView, Flutter WebView, Android/iOS Native Wrapper]
- **Backend:** [예: Node.js (Express), Python (FastAPI/Django), Supabase etc.]
- **Database:** [예: MySQL, PostgreSQL, MongoDB, Firebase]

---

## 3. Mandatory Audit Checklist

### 🚨 A. High Priority (Critical Vulnerabilities)
1.  **Hardcoded Secrets:** Scan for any API Keys, DB Credentials, or JWT Secrets hardcoded in the source files. Move them to `.env`.
2.  **Injection Attacks:**
    - Check for SQL Injection risks (e.g., string concatenation in queries).
    - Check for NoSQL Injection.
3.  **Broken Authentication & Authorization:**
    - Verify if sensitive API endpoints check for valid tokens/sessions.
    - Check if `localStorage` is used for sensitive tokens (Suggest `SecureStore` or `HttpOnly Cookies`).
4.  **File Upload Vulnerabilities:** Check if file uploads are restricted by type/size and scanned for executables.

### 📱 B. Mobile & Hybrid Specifics (WebView)
1.  **WebView Configuration:**
    - Check if `setJavaScriptEnabled` is true (Is it necessary?).
    - **CRITICAL:** Ensure `setAllowFileAccess` is FALSE (prevents local file theft).
    - Check for `addJavascriptInterface` vulnerabilities (ensure restricted exposure).
2.  **Communication:**
    - Ensure all API calls use `HTTPS`.
    - Check for proper CORS settings on the backend.

### 🧹 C. Code Quality & Logic (AI-Generated Quirks)
1.  **Placeholder Logic:** Look for code like `if (true) return;` or `TODO` comments that bypass security.
2.  **Error Handling:** Ensure error messages sent to the client do not reveal stack traces or DB structure.
3.  **Dependencies:** Check `package.json` or `requirements.txt` for severely outdated or insecure packages.

---

## 4. Output Format (Strict)
Please report the findings in the following format. **Do not just list the issues; provide the corrected code.**

### [Severity: High/Medium/Low] Issue Name

**1. Problem Description**
* Briefly explain why this is dangerous.
* *Location:* `src/path/to/vulnerable_file.js`

**2. Vulnerable Code Snippet**
```javascript
// The current bad code
const query = "SELECT * FROM users WHERE id = " + req.body.id;