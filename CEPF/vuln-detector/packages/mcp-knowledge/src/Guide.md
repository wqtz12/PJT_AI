# Security Guide for Web Applications

## XSS (Cross-Site Scripting)

### Next.js
In Next.js, default data binding `{}` escapes HTML by default. However, be careful with `dangerouslySetInnerHTML`.
**Rule**: Avoid `dangerouslySetInnerHTML` unless absolutely necessary. Sanitize input using `DOMPurify` if you must use it.

**Bad Code**:
```jsx
<div dangerouslySetInnerHTML={{ __html: userInput }} />
```

**Good Code**:
```jsx
import DOMPurify from 'isomorphic-dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />
```

## SQL Injection

### Node.js (pg / TypeORM)
Never concatenate strings for SQL queries. Use parameterized queries or ORM methods.

**Bad Code**:
```javascript
const query = "SELECT * FROM users WHERE id = " + req.query.id;
db.query(query);
```

**Good Code**:
```javascript
const query = "SELECT * FROM users WHERE id = $1";
db.query(query, [req.query.id]);
```

## Sensitive Data Exposure

### General
Do not commit secrets like API Keys, Tokens, or passwords to Git. Use `.env` files and `dotenv`.
