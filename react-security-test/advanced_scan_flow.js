#!/usr/bin/env node
/**
 * Advanced Vulnerability Scan Flow
 * 
 * 이 스크립트는 다음 워크플로우를 수행합니다:
 * 1. Git URL 입력 받기
 * 2. 소스코드 다운로드
 * 3. 아키텍처 분석 및 구성도 생성
 * 4. 사용자 확인
 * 5. 고위험 취약점(CVSS >= 8) 탐색 및 커스텀 스킬 등록
 * 6. 취약점 스캔 실행
 * 7. 보고서 생성
 */

import { exec, execSync } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';

const execAsync = promisify(exec);

// =============================================================================
// 설정
// =============================================================================

const SCAN_DIR = path.join(process.cwd(), '.scan_workspace');
const VULNERABILITIES_PATH = path.join(process.cwd(), 'vulnerabilities.json');

// =============================================================================
// 유틸리티 함수
// =============================================================================

/**
 * 사용자 입력을 받는 함수
 * @param {string} question - 질문 문자열
 * @returns {Promise<string>} 사용자 입력
 */
function askQuestion(question) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
    });

    return new Promise((resolve) => {
        rl.question(question, (answer) => {
            rl.close();
            resolve(answer.trim());
        });
    });
}

/**
 * 콘솔 출력 헬퍼
 */
const log = {
    info: (msg) => console.log(`\x1b[36mℹ️  ${msg}\x1b[0m`),
    success: (msg) => console.log(`\x1b[32m✅ ${msg}\x1b[0m`),
    warning: (msg) => console.log(`\x1b[33m⚠️  ${msg}\x1b[0m`),
    error: (msg) => console.log(`\x1b[31m❌ ${msg}\x1b[0m`),
    section: (msg) => console.log(`\n\x1b[35m========== ${msg} ==========\x1b[0m\n`),
};

// =============================================================================
// Step 1 & 2: Git Clone
// =============================================================================

/**
 * Git URL로부터 소스코드를 다운로드합니다.
 * @param {string} gitUrl - Git 저장소 URL
 * @returns {Promise<string>} 클론된 디렉토리 경로
 */
async function cloneRepository(gitUrl) {
    log.section('Step 1 & 2: Git 저장소 다운로드');

    // 기존 작업 디렉토리 정리
    if (fs.existsSync(SCAN_DIR)) {
        log.info('이전 스캔 작업 디렉토리 정리 중...');
        fs.rmSync(SCAN_DIR, { recursive: true, force: true });
    }

    fs.mkdirSync(SCAN_DIR, { recursive: true });

    const repoName = gitUrl.split('/').pop().replace('.git', '') || 'repo';
    const clonePath = path.resolve(SCAN_DIR, repoName);

    log.info(`저장소 클론 중: ${gitUrl}`);

    try {
        await execAsync(`git clone --depth 1 ${gitUrl} ${clonePath}`);
        log.success(`클론 완료: ${clonePath}`);
        return clonePath;
    } catch (error) {
        log.error(`Git 클론 실패: ${error.message}`);
        throw error;
    }
}

// =============================================================================
// Step 3: Architecture Analysis
// =============================================================================

/**
 * 소스코드를 분석하여 아키텍처와 구성도를 생성합니다.
 * @param {string} projectPath - 프로젝트 경로
 * @returns {object} 아키텍처 분석 결과
 */
async function analyzeArchitecture(projectPath) {
    log.section('Step 3: 아키텍처 분석');

    const architecture = {
        projectName: path.basename(projectPath),
        path: projectPath,
        languages: new Set(),
        frameworks: new Set(),
        databases: new Set(),
        riskFactors: [],
        fileStats: {
            total: 0,
            byExtension: {},
        },
        dependencies: {},
        structure: [],
    };

    // 파일 확장자 분석
    const files = getAllFiles(projectPath);
    architecture.fileStats.total = files.length;

    for (const file of files) {
        const ext = path.extname(file).toLowerCase();
        architecture.fileStats.byExtension[ext] = (architecture.fileStats.byExtension[ext] || 0) + 1;

        // 언어 감지
        if (['.js', '.mjs', '.cjs'].includes(ext)) architecture.languages.add('JavaScript');
        if (['.ts', '.tsx'].includes(ext)) architecture.languages.add('TypeScript');
        if (['.py'].includes(ext)) architecture.languages.add('Python');
        if (['.java'].includes(ext)) architecture.languages.add('Java');
        if (['.jsx', '.tsx'].includes(ext)) architecture.frameworks.add('React');
        if (['.vue'].includes(ext)) architecture.frameworks.add('Vue.js');
    }

    // package.json 분석
    const packageJsonPath = path.resolve(projectPath, 'package.json');
    if (fs.existsSync(packageJsonPath)) {
        try {
            const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
            architecture.dependencies = {
                ...packageJson.dependencies,
                ...packageJson.devDependencies,
            };

            // 프레임워크/라이브러리 감지
            const deps = Object.keys(architecture.dependencies);
            if (deps.includes('react')) architecture.frameworks.add('React');
            if (deps.includes('next')) architecture.frameworks.add('Next.js');
            if (deps.includes('express')) architecture.frameworks.add('Express.js');
            if (deps.includes('vue')) architecture.frameworks.add('Vue.js');
            if (deps.includes('angular')) architecture.frameworks.add('Angular');
            if (deps.includes('fastify')) architecture.frameworks.add('Fastify');

            // 데이터베이스 감지
            if (deps.includes('mongoose') || deps.includes('mongodb')) architecture.databases.add('MongoDB');
            if (deps.includes('pg') || deps.includes('postgres')) architecture.databases.add('PostgreSQL');
            if (deps.includes('mysql') || deps.includes('mysql2')) architecture.databases.add('MySQL');
            if (deps.includes('firebase') || deps.includes('firebase-admin')) architecture.databases.add('Firebase');
            if (deps.includes('redis') || deps.includes('ioredis')) architecture.databases.add('Redis');
            if (deps.includes('sequelize')) architecture.databases.add('SQL (Sequelize ORM)');

            // 위험 요소 감지
            if (deps.includes('child_process')) architecture.riskFactors.push('child_process 사용 (Command Injection 위험)');
            if (deps.includes('serialize-javascript') || deps.includes('node-serialize')) {
                architecture.riskFactors.push('직렬화 라이브러리 사용 (Deserialization 위험)');
            }
            if (deps.includes('xml2js') || deps.includes('fast-xml-parser')) {
                architecture.riskFactors.push('XML 파서 사용 (XXE 위험)');
            }
            if (deps.includes('multer') || deps.includes('formidable')) {
                architecture.riskFactors.push('파일 업로드 라이브러리 사용 (Upload 위험)');
            }
        } catch (e) {
            log.warning('package.json 파싱 실패');
        }
    }

    // requirements.txt 분석 (Python)
    const requirementsPath = path.resolve(projectPath, 'requirements.txt');
    if (fs.existsSync(requirementsPath)) {
        architecture.languages.add('Python');
        const requirements = fs.readFileSync(requirementsPath, 'utf-8');
        if (requirements.includes('django')) architecture.frameworks.add('Django');
        if (requirements.includes('flask')) architecture.frameworks.add('Flask');
        if (requirements.includes('fastapi')) architecture.frameworks.add('FastAPI');
    }

    // 소스 코드 내 위험 패턴 스캔
    for (const file of files) {
        if (['.js', '.ts', '.jsx', '.tsx', '.py', '.java'].some(ext => file.endsWith(ext))) {
            try {
                const content = fs.readFileSync(file, 'utf-8');

                // eval() 사용 감지
                if (/\beval\s*\(/.test(content)) {
                    architecture.riskFactors.push(`eval() 사용 감지: ${path.relative(projectPath, file)}`);
                }
                // exec 사용 감지
                if (/\bexec\s*\(|execSync\s*\(|spawn\s*\(/.test(content)) {
                    architecture.riskFactors.push(`명령어 실행 함수 사용: ${path.relative(projectPath, file)}`);
                }
                // dangerouslySetInnerHTML 사용 감지
                if (/dangerouslySetInnerHTML/.test(content)) {
                    architecture.riskFactors.push(`dangerouslySetInnerHTML 사용: ${path.relative(projectPath, file)}`);
                }
                // SQL 쿼리 직접 작성 감지
                if (/`\s*SELECT\s.*\$\{|'\s*\+\s*.*\+\s*'/.test(content)) {
                    architecture.riskFactors.push(`동적 SQL 쿼리 의심: ${path.relative(projectPath, file)}`);
                }
            } catch (e) {
                // 파일 읽기 실패는 무시
            }
        }
    }

    // Set을 Array로 변환
    architecture.languages = Array.from(architecture.languages);
    architecture.frameworks = Array.from(architecture.frameworks);
    architecture.databases = Array.from(architecture.databases);

    // 디렉토리 구조 분석
    architecture.structure = getDirectoryStructure(projectPath, 2);

    return architecture;
}

/**
 * 디렉토리 내 모든 파일 목록을 가져옵니다.
 * @param {string} dirPath - 디렉토리 경로
 * @returns {string[]} 파일 경로 목록
 */
function getAllFiles(dirPath, maxDepth = 10, currentDepth = 0) {
    if (currentDepth > maxDepth) return [];

    const files = [];
    const ignoreDirs = ['node_modules', '.git', 'dist', 'build', '__pycache__', '.next', 'vendor'];

    try {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.resolve(dirPath, entry.name);

            if (entry.isDirectory()) {
                if (!ignoreDirs.includes(entry.name)) {
                    files.push(...getAllFiles(fullPath, maxDepth, currentDepth + 1));
                }
            } else {
                files.push(fullPath);
            }
        }
    } catch (e) {
        // 권한 문제 등 무시
    }

    return files;
}

/**
 * 디렉토리 구조를 트리 형태로 반환합니다.
 * @param {string} dirPath - 디렉토리 경로
 * @param {number} maxDepth - 최대 깊이
 * @returns {string[]} 구조 문자열 배열
 */
function getDirectoryStructure(dirPath, maxDepth, prefix = '', currentDepth = 0) {
    if (currentDepth > maxDepth) return ['...'];

    const result = [];
    const ignoreDirs = ['node_modules', '.git', 'dist', 'build', '__pycache__', '.next', 'vendor'];

    try {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        const filtered = entries.filter(e => !ignoreDirs.includes(e.name) && !e.name.startsWith('.'));

        filtered.forEach((entry, index) => {
            const isLast = index === filtered.length - 1;
            const connector = isLast ? '└── ' : '├── ';
            const newPrefix = isLast ? '    ' : '│   ';

            result.push(`${prefix}${connector}${entry.name}${entry.isDirectory() ? '/' : ''}`);

            if (entry.isDirectory() && currentDepth < maxDepth) {
                const fullPath = path.resolve(dirPath, entry.name);
                result.push(...getDirectoryStructure(fullPath, maxDepth, prefix + newPrefix, currentDepth + 1));
            }
        });
    } catch (e) {
        // 권한 문제 등 무시
    }

    return result;
}

/**
 * 아키텍처 분석 결과를 포맷팅하여 출력합니다.
 * @param {object} arch - 아키텍처 분석 결과
 * @returns {string} 포맷된 문자열
 */
function formatArchitecture(arch) {
    let output = '';

    output += `📁 프로젝트: ${arch.projectName}\n`;
    output += `📍 경로: ${arch.path}\n\n`;

    output += `📊 파일 통계:\n`;
    output += `   총 파일 수: ${arch.fileStats.total}\n`;
    output += `   확장자별:\n`;
    Object.entries(arch.fileStats.byExtension)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .forEach(([ext, count]) => {
            output += `     ${ext || '(no ext)'}: ${count}개\n`;
        });

    output += `\n🔤 사용 언어: ${arch.languages.join(', ') || '감지 안됨'}\n`;
    output += `🛠️  프레임워크: ${arch.frameworks.join(', ') || '감지 안됨'}\n`;
    output += `🗄️  데이터베이스: ${arch.databases.join(', ') || '감지 안됨'}\n`;

    if (arch.riskFactors.length > 0) {
        output += `\n⚠️  위험 요소:\n`;
        arch.riskFactors.forEach((risk, i) => {
            output += `   ${i + 1}. ${risk}\n`;
        });
    }

    output += `\n📂 디렉토리 구조:\n`;
    output += arch.structure.slice(0, 30).map(line => `   ${line}`).join('\n');
    if (arch.structure.length > 30) {
        output += '\n   ... (더 많은 항목 생략)';
    }

    return output;
}

// =============================================================================
// Step 5: Advanced Vulnerability Discovery
// =============================================================================

/**
 * 아키텍처 기반으로 고위험 취약점(CVSS >= 8)을 탐색합니다.
 * @param {object} architecture - 아키텍처 분석 결과
 * @returns {object[]} 발견된 취약점 목록
 */
function findAdvancedVulnerabilities(architecture) {
    log.section('Step 5: 고위험 취약점 탐색 (CVSS >= 8)');

    // 기존 취약점 로드
    let existingVulns = {};
    if (fs.existsSync(VULNERABILITIES_PATH)) {
        existingVulns = JSON.parse(fs.readFileSync(VULNERABILITIES_PATH, 'utf-8'));
    }

    const recommendedVulns = [];
    const customVulns = {};

    // 아키텍처 기반 취약점 매핑
    const vulnMapping = [
        {
            condition: () => architecture.languages.includes('JavaScript') || architecture.languages.includes('TypeScript'),
            vulns: ['CODE_INJECTION', 'XSS_ATTACK', 'DESERIALIZATION_ATTACK'],
        },
        {
            condition: () => architecture.frameworks.some(f => ['Express.js', 'Fastify', 'Next.js'].includes(f)),
            vulns: ['SQL_INJECTION', 'SSRF_ATTACK', 'PATH_TRAVERSAL', 'CSRF_ATTACK'],
        },
        {
            condition: () => architecture.databases.some(d => ['MongoDB', 'PostgreSQL', 'MySQL'].includes(d) || d.includes('SQL')),
            vulns: ['SQL_INJECTION'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('Command Injection') || r.includes('명령어 실행')),
            vulns: ['OS_COMMAND_INJECTION'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('Deserialization') || r.includes('직렬화')),
            vulns: ['DESERIALIZATION_ATTACK'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('XXE') || r.includes('XML')),
            vulns: ['XXE_ATTACK'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('Upload') || r.includes('업로드')),
            vulns: ['FILE_UPLOAD_ATTACK'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('eval')),
            vulns: ['CODE_INJECTION'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('dangerouslySetInnerHTML')),
            vulns: ['XSS_ATTACK'],
        },
        {
            condition: () => architecture.riskFactors.some(r => r.includes('동적 SQL')),
            vulns: ['SQL_INJECTION'],
        },
    ];

    // 조건에 맞는 취약점 추가
    for (const mapping of vulnMapping) {
        if (mapping.condition()) {
            for (const vulnKey of mapping.vulns) {
                if (existingVulns[vulnKey] && existingVulns[vulnKey].cvss >= 8) {
                    if (!recommendedVulns.find(v => v.key === vulnKey)) {
                        recommendedVulns.push({
                            key: vulnKey,
                            ...existingVulns[vulnKey],
                        });
                    }
                }
            }
        }
    }

    // 아키텍처 특화 커스텀 취약점 생성
    if (architecture.frameworks.includes('React') && architecture.riskFactors.some(r => r.includes('dangerouslySetInnerHTML'))) {
        customVulns['REACT_DANGEROUS_HTML'] = {
            name: 'React dangerouslySetInnerHTML XSS',
            cwe: 'CWE-79',
            cvss: 8.0,
            severity: 'High',
            description: 'React의 dangerouslySetInnerHTML을 통한 XSS 취약점. 사용자 입력이 직접 렌더링될 경우 발생.',
            payloads: {
                basic: [
                    '<img src=x onerror=alert(document.cookie)>',
                    '<svg onload=alert(1)>',
                ],
                react: [
                    '{"__html": "<script>alert(1)</script>"}',
                ],
            },
            custom: true,
            sourceArchitecture: architecture.projectName,
        };
    }

    if (architecture.frameworks.includes('Next.js')) {
        customVulns['NEXTJS_SSRF'] = {
            name: 'Next.js API Route SSRF',
            cwe: 'CWE-918',
            cvss: 9.0,
            severity: 'Critical',
            description: 'Next.js API Route에서 발생할 수 있는 SSRF 취약점. 외부 URL을 직접 fetch할 경우 발생.',
            payloads: {
                internalNetwork: [
                    'http://localhost:3000/api/internal',
                    'http://127.0.0.1:22',
                ],
                metadata: [
                    'http://169.254.169.254/latest/meta-data/',
                ],
            },
            custom: true,
            sourceArchitecture: architecture.projectName,
        };
    }

    // 결과 출력
    log.info(`기존 취약점 중 권장 항목: ${recommendedVulns.length}개`);
    recommendedVulns.forEach(v => {
        console.log(`   - ${v.name} (${v.cwe}) - CVSS ${v.cvss}`);
    });

    if (Object.keys(customVulns).length > 0) {
        log.info(`아키텍처 특화 커스텀 취약점: ${Object.keys(customVulns).length}개`);
        Object.values(customVulns).forEach(v => {
            console.log(`   - [NEW] ${v.name} (${v.cwe}) - CVSS ${v.cvss}`);
        });
    }

    return { recommendedVulns, customVulns };
}

// =============================================================================
// Step 6: Register Custom Skills
// =============================================================================

/**
 * 커스텀 취약점을 vulnerabilities.json에 등록합니다.
 * @param {object} customVulns - 커스텀 취약점 목록
 */
function registerCustomSkills(customVulns) {
    log.section('Step 6: 커스텀 스킬 등록');

    if (Object.keys(customVulns).length === 0) {
        log.info('등록할 커스텀 취약점이 없습니다.');
        return;
    }

    let existingVulns = {};
    if (fs.existsSync(VULNERABILITIES_PATH)) {
        existingVulns = JSON.parse(fs.readFileSync(VULNERABILITIES_PATH, 'utf-8'));
    }

    // 커스텀 취약점 추가
    const updatedVulns = { ...existingVulns, ...customVulns };

    fs.writeFileSync(VULNERABILITIES_PATH, JSON.stringify(updatedVulns, null, 2));

    log.success(`${Object.keys(customVulns).length}개 커스텀 취약점이 등록되었습니다.`);
    log.info(`저장 위치: ${VULNERABILITIES_PATH}`);
}

// =============================================================================
// Step 7: Execute Scan
// =============================================================================

/**
 * 취약점 스캔을 실행합니다.
 * @param {string} targetUrl - 스캔 대상 URL
 * @param {string[]} vulnKeys - 스캔할 취약점 키 목록
 * @returns {object} 스캔 결과
 */
async function executeScan(targetUrl, vulnKeys) {
    log.section('Step 7: 취약점 스캔 실행');

    // vulnerabilities.json 로드
    const vulns = JSON.parse(fs.readFileSync(VULNERABILITIES_PATH, 'utf-8'));

    const results = [];
    const timestamp = new Date().toISOString();

    for (const key of vulnKeys) {
        const vuln = vulns[key];
        if (!vuln) continue;

        log.info(`스캔 중: ${vuln.name} (${vuln.cwe})`);

        // 간단한 모의 스캔 (실제로는 MCP 서버를 통해 수행)
        results.push({
            key,
            name: vuln.name,
            cwe: vuln.cwe,
            cvss: vuln.cvss,
            severity: vuln.severity,
            tested: true,
            vulnerable: false, // 실제 테스트 결과로 대체 필요
            note: '정적 분석 기반 권장 항목 (동적 테스트 필요)',
        });
    }

    return {
        targetUrl,
        timestamp,
        summary: {
            total: results.length,
            vulnerable: results.filter(r => r.vulnerable).length,
        },
        results,
    };
}

// =============================================================================
// Step 8: Generate Report
// =============================================================================

/**
 * 보고서를 생성합니다.
 * @param {object} architecture - 아키텍처 분석 결과
 * @param {object} scanResult - 스캔 결과
 * @param {object} vulnerabilityInfo - 취약점 정보
 * @returns {string} 보고서 파일 경로
 */
function generateReport(architecture, scanResult, vulnerabilityInfo) {
    log.section('Step 8: 보고서 생성');

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const reportPath = path.resolve(SCAN_DIR, `security-report-${timestamp}.html`);

    const { recommendedVulns, customVulns } = vulnerabilityInfo;

    const html = `
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>보안 취약점 스캔 보고서 - ${architecture.projectName}</title>
  <style>
    * { box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 1200px; 
      margin: 0 auto; 
      padding: 40px 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
    }
    .container {
      background: white;
      border-radius: 20px;
      padding: 40px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }
    h1 { 
      color: #1a202c;
      border-bottom: 4px solid #667eea;
      padding-bottom: 15px;
      font-size: 2rem;
    }
    h2 {
      color: #2d3748;
      margin-top: 40px;
      font-size: 1.5rem;
    }
    .meta { 
      color: #718096;
      font-size: 0.9rem;
      margin-bottom: 30px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin: 30px 0;
    }
    .stat {
      padding: 25px;
      border-radius: 15px;
      text-align: center;
      color: white;
    }
    .stat h3 { margin: 0; font-size: 2.5rem; }
    .stat p { margin: 10px 0 0; opacity: 0.9; }
    .stat.critical { background: linear-gradient(135deg, #f56565 0%, #c53030 100%); }
    .stat.high { background: linear-gradient(135deg, #ed8936 0%, #c05621 100%); }
    .stat.total { background: linear-gradient(135deg, #4299e1 0%, #2b6cb0 100%); }
    .stat.safe { background: linear-gradient(135deg, #48bb78 0%, #276749 100%); }
    .arch-info {
      background: #f7fafc;
      border-radius: 12px;
      padding: 25px;
      margin: 20px 0;
    }
    .arch-info h3 { margin-top: 0; color: #2d3748; }
    .tag {
      display: inline-block;
      background: #e2e8f0;
      color: #4a5568;
      padding: 5px 12px;
      border-radius: 20px;
      margin: 3px;
      font-size: 0.85rem;
    }
    .tag.framework { background: #c6f6d5; color: #22543d; }
    .tag.database { background: #bee3f8; color: #2a4365; }
    .tag.language { background: #faf089; color: #744210; }
    .risk-list {
      background: #fff5f5;
      border-left: 4px solid #f56565;
      padding: 15px 20px;
      margin: 15px 0;
      border-radius: 0 8px 8px 0;
    }
    .vuln-card {
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 20px;
      margin: 15px 0;
      transition: box-shadow 0.3s;
    }
    .vuln-card:hover { box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    .vuln-card.custom { border-left: 4px solid #9f7aea; }
    .vuln-header { display: flex; justify-content: space-between; align-items: center; }
    .vuln-name { font-weight: 600; color: #2d3748; font-size: 1.1rem; }
    .cvss {
      padding: 5px 12px;
      border-radius: 20px;
      font-weight: bold;
      font-size: 0.85rem;
    }
    .cvss.critical { background: #fed7d7; color: #c53030; }
    .cvss.high { background: #feebc8; color: #c05621; }
    .vuln-detail { color: #718096; margin-top: 10px; font-size: 0.9rem; }
    pre {
      background: #2d3748;
      color: #e2e8f0;
      padding: 15px;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 0.85rem;
    }
    .footer {
      text-align: center;
      color: #a0aec0;
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #e2e8f0;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔒 보안 취약점 스캔 보고서</h1>
    <div class="meta">
      <strong>프로젝트:</strong> ${architecture.projectName} | 
      <strong>생성 시간:</strong> ${new Date().toLocaleString('ko-KR')}
    </div>
    
    <div class="summary">
      <div class="stat total">
        <h3>${scanResult.summary.total}</h3>
        <p>검사 항목</p>
      </div>
      <div class="stat critical">
        <h3>${recommendedVulns.filter(v => v.cvss >= 9).length}</h3>
        <p>Critical</p>
      </div>
      <div class="stat high">
        <h3>${recommendedVulns.filter(v => v.cvss >= 8 && v.cvss < 9).length}</h3>
        <p>High</p>
      </div>
      <div class="stat safe">
        <h3>${Object.keys(customVulns).length}</h3>
        <p>커스텀 룰</p>
      </div>
    </div>
    
    <h2>📊 아키텍처 분석</h2>
    <div class="arch-info">
      <h3>기술 스택</h3>
      <p>
        <strong>언어:</strong>
        ${architecture.languages.map(l => `<span class="tag language">${l}</span>`).join('')}
      </p>
      <p>
        <strong>프레임워크:</strong>
        ${architecture.frameworks.map(f => `<span class="tag framework">${f}</span>`).join('')}
      </p>
      <p>
        <strong>데이터베이스:</strong>
        ${architecture.databases.map(d => `<span class="tag database">${d}</span>`).join('')}
      </p>
    </div>
    
    ${architecture.riskFactors.length > 0 ? `
    <div class="risk-list">
      <strong>⚠️ 감지된 위험 요소</strong>
      <ul>
        ${architecture.riskFactors.map(r => `<li>${r}</li>`).join('')}
      </ul>
    </div>
    ` : ''}
    
    <h2>🎯 권장 검사 취약점</h2>
    ${recommendedVulns.map(v => `
    <div class="vuln-card">
      <div class="vuln-header">
        <span class="vuln-name">${v.name}</span>
        <span class="cvss ${v.cvss >= 9 ? 'critical' : 'high'}">CVSS ${v.cvss}</span>
      </div>
      <div class="vuln-detail">
        <strong>${v.cwe}</strong> - ${v.description}
      </div>
    </div>
    `).join('')}
    
    ${Object.keys(customVulns).length > 0 ? `
    <h2>🆕 커스텀 취약점 (아키텍처 기반)</h2>
    ${Object.values(customVulns).map(v => `
    <div class="vuln-card custom">
      <div class="vuln-header">
        <span class="vuln-name">✨ ${v.name}</span>
        <span class="cvss ${v.cvss >= 9 ? 'critical' : 'high'}">CVSS ${v.cvss}</span>
      </div>
      <div class="vuln-detail">
        <strong>${v.cwe}</strong> - ${v.description}
      </div>
    </div>
    `).join('')}
    ` : ''}
    
    <h2>📂 디렉토리 구조</h2>
    <pre>${architecture.structure.slice(0, 30).join('\n')}</pre>
    
    <div class="footer">
      <p>Generated by Advanced Vulnerability Scanner</p>
      <p>Based on KISA JavaScript Secure Coding Guide 2023</p>
    </div>
  </div>
</body>
</html>
`;

    fs.writeFileSync(reportPath, html);
    log.success(`보고서 생성 완료: ${reportPath}`);

    return reportPath;
}

// =============================================================================
// 메인 실행
// =============================================================================

async function main() {
    console.log('\n');
    console.log('╔═══════════════════════════════════════════════════════════════╗');
    console.log('║     🛡️  Advanced Vulnerability Scanning Workflow              ║');
    console.log('║     KISA JavaScript 시큐어코딩 가이드 기반                      ║');
    console.log('╚═══════════════════════════════════════════════════════════════╝');
    console.log('\n');

    try {
        // Step 1: Git URL 입력
        const gitUrl = await askQuestion('📥 분석할 Git 저장소 URL을 입력하세요: ');

        if (!gitUrl) {
            log.error('Git URL이 입력되지 않았습니다.');
            process.exit(1);
        }

        // Step 2: 소스코드 다운로드
        const projectPath = await cloneRepository(gitUrl);

        // Step 3: 아키텍처 분석
        const architecture = await analyzeArchitecture(projectPath);

        console.log('\n' + formatArchitecture(architecture) + '\n');

        // Step 4: 사용자 확인
        log.section('Step 4: 아키텍처 확인');
        const confirmation = await askQuestion('위 분석 결과가 맞습니까? (y/n) 또는 추가 의견을 입력하세요: ');

        if (confirmation.toLowerCase() === 'n') {
            log.warning('사용자가 분석 결과를 거부했습니다. 프로그램을 종료합니다.');
            process.exit(0);
        }

        if (confirmation.toLowerCase() !== 'y' && confirmation.length > 1) {
            log.info(`사용자 추가 의견: ${confirmation}`);
            architecture.userNotes = confirmation;
        }

        // Step 5: 고위험 취약점 탐색
        const vulnerabilityInfo = findAdvancedVulnerabilities(architecture);

        // Step 6: 커스텀 스킬 등록
        registerCustomSkills(vulnerabilityInfo.customVulns);

        // Step 7: 스캔 실행 (모의)
        const allVulnKeys = [
            ...vulnerabilityInfo.recommendedVulns.map(v => v.key),
            ...Object.keys(vulnerabilityInfo.customVulns),
        ];

        const scanResult = await executeScan(gitUrl, allVulnKeys);

        // Step 8: 보고서 생성
        const reportPath = generateReport(architecture, scanResult, vulnerabilityInfo);

        // 최종 결과
        log.section('완료');
        log.success('취약점 스캔 워크플로우가 완료되었습니다!');
        console.log(`\n📄 보고서: ${reportPath}`);
        console.log(`📁 작업 디렉토리: ${SCAN_DIR}`);
        console.log('\n');

        // 보고서 자동 열기 여부 확인
        const openReport = await askQuestion('보고서를 브라우저에서 열겠습니까? (y/n): ');
        if (openReport.toLowerCase() === 'y') {
            const openCmd = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
            execSync(`${openCmd} "${reportPath}"`);
        }

    } catch (error) {
        log.error(`오류 발생: ${error.message}`);
        console.error(error);
        process.exit(1);
    }
}

main();
