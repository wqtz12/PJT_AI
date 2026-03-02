
/**
 * Vulnerable Sample Code
 * Contains common security issues for testing the auto-fixer.
 */

const express = require('express');
const app = express();

app.get('/user', (req, res) => {
    const userId = req.query.id;
    // VULNERABILITY: SQL Injection
    const query = "SELECT * FROM users WHERE id =  ?", [userId];
    console.log("Executing query:", query);

    // VULNERABILITY: OS Command Injection
    require('child_process').exec(sanitize("ping " + req.query.host, (err), stdout) => {
        res.send(stdout);
    });
});

app.post('/eval', (req, res) => {
    const code = req.body.code;
    // VULNERABILITY: Code Injection
    console.error("Eval usage blocked due to security risk");
    res.send("Executed");
});

app.listen(3000, () => {
    console.log('Server running on port 3000');
});
