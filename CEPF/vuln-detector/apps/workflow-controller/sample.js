// This file contains intentional vulnerabilities for testing

const express = require('express');
const app = express();
const mysql = require('mysql');
const connection = mysql.createConnection({});

app.get('/user', (req, res) => {
    const userId = req.query.id;

    // VULNERABILITY 1: SQL Injection
    // Using string concatenation directly into query
    const query = "SELECT * FROM users WHERE id = " + userId;

    connection.query(query, (err, results) => {
        if (err) throw err;

        // VULNERABILITY 2: XSS
        // Rendering input directly
        const userName = results[0].name;
        res.send(`
            <h1>Welcome ${userName}</h1>
            <div>
                User supplied data: <span dangerouslySetInnerHTML={{__html: req.query.bio}}></span>
            </div>
        `);
    });
});
