/**
 * Workflow Controller
 *
 * MCP 서버(Analysis, Knowledge)를 활용하여 보안 취약점을 탐지하고
 * LLM(Claude)으로 검증하는 오케스트레이터입니다.
 *
 * 환경 변수:
 * - ANTHROPIC_API_KEY: Claude API 키
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Anthropic } from "@anthropic-ai/sdk";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";
import fs from "fs/promises";

// .env 파일 로드 (vuln-detector 루트 또는 apps/workflow-controller)
dotenv.config({ path: path.resolve(process.cwd(), '.env') });
dotenv.config();

// =============================================================================
// Types
// =============================================================================

interface Finding {
    check_id: string;
    path: string;
    start: number;
    end: number;
    message: string;
    severity: string;
    lines?: string;
}

interface VerifiedVulnerability extends Finding {
    analysis: {
        is_vulnerable: boolean;
        confidence: string;
        reason: string;
        remediation: string;
        referenced_skill: string;
    };
}

// =============================================================================
// MCP Client Helper
// =============================================================================

async function startMcpClient(serverPath: string, name: string): Promise<Client> {
    const transport = new StdioClientTransport({
        command: "node",
        args: [serverPath],
    });

    const client = new Client(
        { name: "workflow-controller", version: "0.2.0" },
        { capabilities: {} }
    );

    await client.connect(transport);
    console.log(`✓ Connected to MCP Server: ${name}`);
    return client;
}

// =============================================================================
// Skill Selection Logic
// =============================================================================

/**
 * 취약점 유형에 따라 적절한 스킬과 섹션을 결정합니다.
 */
function determineSkillAndSection(checkId: string, message: string): { skill: string; section: string } {
    const lowerCheckId = checkId.toLowerCase();
    const lowerMessage = message.toLowerCase();

    // XSS 관련
    if (lowerCheckId.includes('xss') || lowerMessage.includes('xss') || lowerMessage.includes('cross-site scripting')) {
        return { skill: 'javascript-secure-coding', section: 'XSS' };
    }

    // SQL Injection
    if (lowerCheckId.includes('sql') || lowerCheckId.includes('injection') || lowerMessage.includes('sql')) {
        return { skill: 'javascript-secure-coding', section: 'SQL Injection' };
    }

    // Command Injection
    if (lowerCheckId.includes('command') || lowerMessage.includes('command injection')) {
        return { skill: 'javascript-secure-coding', section: 'Command Injection' };
    }

    // Path Traversal
    if (lowerCheckId.includes('path') || lowerMessage.includes('path traversal') || lowerMessage.includes('directory')) {
        return { skill: 'javascript-secure-coding', section: 'Path Traversal' };
    }

    // 개인정보 관련
    if (lowerMessage.includes('personal') || lowerMessage.includes('privacy') || lowerMessage.includes('pii')) {
        return { skill: 'privacy-checklist', section: '개인정보 저장' };
    }

    // AI/LLM 관련
    if (lowerMessage.includes('prompt') || lowerMessage.includes('llm') || lowerMessage.includes('ai')) {
        return { skill: 'ai-security-checklist', section: 'Prompt Injection 방어' };
    }

    // 인증 관련
    if (lowerCheckId.includes('auth') || lowerMessage.includes('jwt') || lowerMessage.includes('session')) {
        return { skill: 'javascript-secure-coding', section: '인증 및 세션 관리' };
    }

    // Hardcoded secrets
    if (lowerCheckId.includes('secret') || lowerCheckId.includes('hardcoded') || lowerMessage.includes('api key')) {
        return { skill: 'ai-security-checklist', section: 'API 보안' };
    }

    // 기본값
    return { skill: 'javascript-secure-coding', section: 'XSS' };
}

// =============================================================================
// Main Workflow
// =============================================================================

async function main() {
    console.log("========================================");
    console.log("  Security Vulnerability Detector v0.2");
    console.log("========================================\n");

    // API Key 확인
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
        console.error("❌ Error: ANTHROPIC_API_KEY is not set.");
        console.error("   Set it in .env file or environment variable.");
        process.exit(1);
    }
    console.log("✓ API Key loaded from environment\n");

    const anthropic = new Anthropic({ apiKey });
    const __dirname = path.dirname(fileURLToPath(import.meta.url));

    // MCP 서버 경로 설정
    const rootDir = path.resolve(__dirname, '../../..');
    const analysisServerPath = path.join(rootDir, 'packages/mcp-analysis/dist/index.js');
    const knowledgeServerPath = path.join(rootDir, 'packages/mcp-knowledge/dist/index.js');

    // MCP 클라이언트 시작
    console.log("Starting MCP Servers...");
    const analysisClient = await startMcpClient(analysisServerPath, "Analysis");
    const knowledgeClient = await startMcpClient(knowledgeServerPath, "Knowledge");

    // 대상 경로 설정
    const targetPath = process.argv[2] || process.cwd();
    console.log(`\n📁 Target Path: ${targetPath}\n`);

    try {
        // =====================================================================
        // Step 1: Static Analysis (Semgrep)
        // =====================================================================
        console.log("Step 1: Running Semgrep Scan...");
        const scanResult = await analysisClient.callTool({
            name: "run_scan",
            arguments: { path: targetPath, include_rules: ["p/security-audit", "p/javascript"] }
        });

        const findingsJson = ((scanResult as any).content[0] as any).text;

        // 에러 체크
        if (findingsJson.includes("Error")) {
            console.error("⚠️  Scan Error:", findingsJson);
            console.log("\nTip: Semgrep이 설치되어 있는지 확인하세요.");
            console.log("     npm install -g semgrep 또는 pip install semgrep");
            return;
        }

        const findings: Finding[] = JSON.parse(findingsJson);

        if (findings.length === 0) {
            console.log("✅ No initial findings by Semgrep. Code appears clean!\n");
            return;
        }

        console.log(`   Found ${findings.length} candidates.\n`);

        // =====================================================================
        // Step 2: List Available Skills
        // =====================================================================
        console.log("Step 2: Loading Security Skills...");
        const skillsResult = await knowledgeClient.callTool({
            name: "list_security_skills",
            arguments: {}
        });
        const skills = JSON.parse(((skillsResult as any).content[0] as any).text);
        console.log(`   Available Skills: ${skills.map((s: any) => s.name).join(', ')}\n`);

        // =====================================================================
        // Step 3: Verification Loop
        // =====================================================================
        console.log("Step 3: Verifying findings with LLM...\n");
        const verifiedVulnerabilities: VerifiedVulnerability[] = [];

        for (let i = 0; i < findings.length; i++) {
            const finding = findings[i];
            console.log(`[${i + 1}/${findings.length}] Analyzing: ${finding.check_id}`);
            console.log(`            File: ${finding.path}:${finding.start}`);

            // Context 1: Code Snippet
            const contextResult = await analysisClient.callTool({
                name: "get_file_context",
                arguments: {
                    path: finding.path,
                    startLine: finding.start,
                    endLine: finding.end
                }
            });
            const codeSnippet = ((contextResult as any).content[0] as any).text;

            // Context 2: Determine appropriate skill and section
            const { skill, section } = determineSkillAndSection(finding.check_id, finding.message);
            console.log(`            Skill: ${skill} / Section: ${section}`);

            // Context 3: Get Security Guide
            const guideResult = await knowledgeClient.callTool({
                name: "get_skill_section",
                arguments: { skill_name: skill, section_name: section }
            });
            const guideContent = ((guideResult as any).content[0] as any).text;

            // Construct Prompt
            const prompt = `
당신은 시니어 보안 엔지니어입니다. 아래 코드 발견 사항이 실제 취약점(True Positive)인지 오탐(False Positive)인지 판단해주세요.

## 발견된 취약점 정보
- **취약점 유형**: ${finding.check_id}
- **메시지**: ${finding.message}
- **파일 위치**: ${finding.path} (Line ${finding.start})
- **심각도**: ${finding.severity}

## 코드 스니펫
\`\`\`
${codeSnippet}
\`\`\`

## 참조 보안 가이드 (${skill} - ${section})
${guideContent}

## 분석 과제
1. 코드가 실제로 취약한지 분석하세요.
2. 보안 가이드의 기준에 따라 판단하세요.
3. 조치 방안을 제시하세요.

## 응답 형식 (JSON만 출력)
{
  "is_vulnerable": boolean,
  "confidence": "Low" | "Medium" | "High",
  "reason": "판단 근거 (한글, 50자 이내)",
  "remediation": "조치 방안 (한글, 100자 이내)"
}
`;

            const response = await anthropic.messages.create({
                model: "claude-sonnet-4-20250514",
                max_tokens: 500,
                messages: [{ role: "user", content: prompt }]
            });

            const answerText = (response.content[0] as any).text;

            try {
                const jsonMatch = answerText.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    const analysis = JSON.parse(jsonMatch[0]);
                    if (analysis.is_vulnerable) {
                        console.log(`            → ❌ CONFIRMED Vulnerable (${analysis.confidence})`);
                        verifiedVulnerabilities.push({
                            ...finding,
                            analysis: {
                                ...analysis,
                                referenced_skill: `${skill}/${section}`
                            }
                        });
                    } else {
                        console.log(`            → ✅ False Positive`);
                    }
                } else {
                    console.log(`            → ⚠️  Failed to parse LLM response`);
                }
            } catch (e) {
                console.error(`            → ⚠️  Error:`, e);
            }
            console.log();
        }

        // =====================================================================
        // Step 4: Generate Report
        // =====================================================================
        console.log("========================================");
        console.log("           FINAL REPORT");
        console.log("========================================\n");

        console.log(`Total Findings: ${findings.length}`);
        console.log(`Confirmed Vulnerabilities: ${verifiedVulnerabilities.length}`);
        console.log(`False Positives: ${findings.length - verifiedVulnerabilities.length}\n`);

        if (verifiedVulnerabilities.length > 0) {
            console.log("--- Confirmed Vulnerabilities ---\n");
            for (const vuln of verifiedVulnerabilities) {
                console.log(`📛 ${vuln.check_id}`);
                console.log(`   File: ${vuln.path}:${vuln.start}`);
                console.log(`   Confidence: ${vuln.analysis.confidence}`);
                console.log(`   Reason: ${vuln.analysis.reason}`);
                console.log(`   Remediation: ${vuln.analysis.remediation}`);
                console.log(`   Reference: ${vuln.analysis.referenced_skill}\n`);
            }

            // JSON 파일로 저장
            const reportPath = path.join(process.cwd(), 'security-report.json');
            await fs.writeFile(reportPath, JSON.stringify(verifiedVulnerabilities, null, 2));
            console.log(`📄 Report saved to: ${reportPath}`);
        } else {
            console.log("🎉 No confirmed vulnerabilities found!\n");
        }

    } catch (error) {
        console.error("❌ Workflow Error:", error);
    } finally {
        process.exit(0);
    }
}

main();
