/**
 * Auto Fix Vulnerability Flow
 * 
 * This script automates the process of fixing security vulnerabilities based on a report.
 * (ESM Version)
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

// Helper for ESM path resolution
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const REPORT_FILE = 'mock_report.json';
const GIT_REPO_URL = process.argv[2] || 'https://github.com/example/security-report.git';
const TARGET_DIR = process.cwd();

// Helper to log with colors
const log = {
    info: (msg) => console.log(`\x1b[36mℹ️  ${msg}\x1b[0m`),
    success: (msg) => console.log(`\x1b[32m✅ ${msg}\x1b[0m`),
    warning: (msg) => console.log(`\x1b[33m⚠️  ${msg}\x1b[0m`),
    error: (msg) => console.log(`\x1b[31m❌ ${msg}\x1b[0m`),
    section: (msg) => console.log(`\n\x1b[35m========== ${msg} ==========\x1b[0m\n`),
};

async function main() {
    log.section('Starting Auto-Fix Vulnerability Process');

    // Step 1: Download report via git
    log.info(`Step 1: Downloading report from ${GIT_REPO_URL}...`);
    try {
        log.success('Report downloaded (Simulated).');
    } catch (e) {
        log.error('Failed to download report.');
    }

    // Step 2: Check report existence
    if (!fs.existsSync(REPORT_FILE)) {
        log.error(`Step 2: Report file ${REPORT_FILE} not found. Exiting.`);
        process.exit(1);
    }
    log.success(`Step 2: Report file ${REPORT_FILE} found.`);

    // Step 3: Sort vulnerabilities by risk
    log.info('Step 3: Sorting vulnerabilities by risk priority...');
    let vulnerabilities = [];
    try {
        const reportData = fs.readFileSync(REPORT_FILE, 'utf8');
        vulnerabilities = JSON.parse(reportData);
        vulnerabilities.sort((a, b) => b.risk - a.risk);
        log.success(`Sorted ${vulnerabilities.length} vulnerabilities.`);
    } catch (e) {
        log.error('Failed to parse report JSON.');
        process.exit(1);
    }

    // Step 5: Git backup (Branching)
    log.section('Step 5: Creating Backup Branch');
    const branchName = `fix/auto-patch-${Date.now()}`;
    try {
        if (!fs.existsSync(path.join(TARGET_DIR, '.git'))) {
            log.warning("Git not initialized. Initializing for demo...");
            execSync('git init');
            execSync('git add .');
            try {
                execSync('git commit -m "Initial commit"');
            } catch (e) { /* ignore nothing to commit */ }
        }
        execSync(`git checkout -b ${branchName}`);
        log.success(`Created and switched to branch: ${branchName}`);
    } catch (e) {
        log.error(`Failed to create branch: ${e.message}`);
    }

    // Step 4 & 6: Analyze and Fix
    log.section('Step 4 & 6: Analyze, Design, and Modify Code');

    for (const vuln of vulnerabilities) {
        log.info(`Processing [${vuln.id}] (Risk: ${vuln.risk}) in ${vuln.file}:${vuln.line}`);

        log.info(`  Analysis: ${vuln.description}`);
        const filePath = path.join(TARGET_DIR, vuln.file);

        if (!fs.existsSync(filePath)) {
            log.warning(`  File ${vuln.file} not found. Skipping.`);
            continue;
        }

        try {
            let content = fs.readFileSync(filePath, 'utf8');
            let lines = content.split('\n');
            const originalLine = lines[vuln.line - 1]; // 0-indexed

            log.info(`  Original Code: ${originalLine ? originalLine.trim() : 'N/A'}`);
            if (!originalLine) continue;

            let fixedLine = originalLine;
            let solutionDescription = "";

            if (vuln.fix_type === 'remove_eval' || originalLine.includes('eval(')) {
                solutionDescription = "Replacing eval() with safe alternative/commenting out.";
                fixedLine = originalLine.replace(/eval\((.*)\)/, 'console.error("Eval usage blocked due to security risk")');
            }
            else if (vuln.fix_type === 'parameterized_query' || originalLine.includes('SELECT')) {
                solutionDescription = "Converting string concatenation to parameterized query.";
                // Simple regex for string concat "+ var"
                fixedLine = originalLine.replace(/["']\s*\+\s*([\w.]+)/, ' ?", [$1]');
            }
            else if (vuln.fix_type === 'sanitize_input' || originalLine.includes('exec(')) {
                solutionDescription = "Wrapping input with sanitizer.";
                fixedLine = originalLine.replace(/exec\((.*),/, 'exec(sanitize($1),');
            }
            else {
                solutionDescription = "Applying generic fix (commenting out).";
                fixedLine = `// FIXED: ${originalLine} // Review required`;
            }

            log.info(`  Design: ${solutionDescription}`);

            if (fixedLine !== originalLine) {
                lines[vuln.line - 1] = fixedLine;
                fs.writeFileSync(filePath, lines.join('\n'));
                log.success(`  [Fixed] Code modified.`);
                log.info(`  New Code: ${fixedLine.trim()}`);
            } else {
                log.warning(`  No fix pattern matched or line unchanged. Skipping.`);
            }

        } catch (e) {
            log.error(`  Failed to apply fix: ${e.message}`);
        }
    }

    // Step 7: Test
    log.section('Step 7: Running Program Tests');
    try {
        log.info('Running unit tests...');
        log.success('Tests passed (Simulated).');
    } catch (e) {
        log.error('Tests failed.');
        process.exit(1);
    }

    // Step 8: User Perspective Test
    log.section('Step 8: User Perspective Test');
    log.info('Simulating user manual verification...');
    await new Promise(resolve => setTimeout(resolve, 1000));
    log.success('User verification passed.');

    // Step 9: Git Push
    log.section('Step 9: Git Push');
    try {
        log.info(`Pushing branch ${branchName} to remote...`);
        log.success('Successfully pushed to remote (Simulated).');
    } catch (e) {
        log.error('Failed to push to remote.');
    } // End of main
}

main();
