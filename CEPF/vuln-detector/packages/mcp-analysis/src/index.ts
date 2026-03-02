#!/usr/bin/env node
/**
 * MCP Analysis Server
 *
 * Semgrep 기반의 정적 분석 도구를 MCP 서버로 래핑합니다.
 * 주요 기능:
 * - run_scan: 지정 경로에 대해 보안 스캔 수행
 * - get_file_context: 취약점 검증을 위한 코드 컨텍스트 제공
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
    Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";

const execAsync = promisify(exec);

// =============================================================================
// Tool Definitions
// =============================================================================

const RUN_SCAN_TOOL: Tool = {
    name: "run_scan",
    description: "Semgrep을 사용하여 보안 스캔을 수행합니다. 잠재적 취약점을 JSON 형식으로 반환합니다.",
    inputSchema: {
        type: "object",
        properties: {
            path: {
                type: "string",
                description: "스캔할 디렉토리 또는 파일의 절대/상대 경로"
            },
            include_rules: {
                type: "array",
                items: { type: "string" },
                description: "사용할 Semgrep 룰셋 (예: ['p/javascript', 'p/security-audit'])"
            }
        },
        required: ["path"]
    }
};

const GET_FILE_CONTEXT_TOOL: Tool = {
    name: "get_file_context",
    description: "취약점 검증을 위해 파일의 특정 영역을 읽어 컨텍스트를 제공합니다.",
    inputSchema: {
        type: "object",
        properties: {
            path: { type: "string", description: "파일 경로" },
            startLine: { type: "number", description: "시작 라인 번호 (1-based)" },
            endLine: { type: "number", description: "종료 라인 번호 (1-based)" },
            contextLines: { type: "number", description: "전후로 포함할 추가 라인 수 (기본: 5)" }
        },
        required: ["path", "startLine", "endLine"]
    }
};

const LIST_SUPPORTED_LANGUAGES_TOOL: Tool = {
    name: "list_supported_languages",
    description: "지원되는 프로그래밍 언어 및 프레임워크 목록을 반환합니다.",
    inputSchema: {
        type: "object",
        properties: {}
    }
};

// =============================================================================
// Server Implementation
// =============================================================================

const server = new Server(
    {
        name: "vuln-detector/analysis",
        version: "0.2.0",
    },
    {
        capabilities: {
            tools: {},
        },
    }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [RUN_SCAN_TOOL, GET_FILE_CONTEXT_TOOL, LIST_SUPPORTED_LANGUAGES_TOOL],
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    // -------------------------------------------------------------------------
    // run_scan
    // -------------------------------------------------------------------------
    if (name === "run_scan") {
        const scanPath = (args as any).path;
        const includeRules = (args as any).include_rules || ["p/security-audit", "p/secrets"];

        try {
            // 경로 존재 확인
            await fs.access(scanPath);

            // Semgrep 명령어 구성
            const rules = includeRules.map((r: string) => `--config "${r}"`).join(" ");
            const cmd = `npx semgrep --json --quiet ${rules} "${scanPath}"`;

            console.error(`[Analysis] Executing: ${cmd}`);

            const { stdout, stderr } = await execAsync(cmd, {
                maxBuffer: 10 * 1024 * 1024, // 10MB buffer
                timeout: 300000 // 5분 타임아웃
            });

            if (stderr && !stdout) {
                return {
                    content: [{ type: "text", text: `Semgrep warning: ${stderr}` }],
                    isError: true
                };
            }

            const results = JSON.parse(stdout);

            // 결과 단순화 (토큰 절약)
            const findings = results.results.map((r: any) => ({
                check_id: r.check_id,
                path: r.path,
                start: r.start.line,
                end: r.end.line,
                message: r.extra?.message || "No message",
                severity: r.extra?.severity || "WARNING",
                lines: r.extra?.lines || ""
            }));

            console.error(`[Analysis] Found ${findings.length} potential issues`);

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify(findings, null, 2)
                }],
            };
        } catch (error: any) {
            // Semgrep이 설치되지 않은 경우 처리
            if (error.message.includes("command not found") || error.message.includes("not found")) {
                return {
                    content: [{
                        type: "text",
                        text: "Error: Semgrep is not installed. Please install it with: pip install semgrep"
                    }],
                    isError: true
                };
            }

            // 파일이 없는 경우
            if (error.code === 'ENOENT') {
                return {
                    content: [{
                        type: "text",
                        text: `Error: Path not found: ${scanPath}`
                    }],
                    isError: true
                };
            }

            return {
                content: [{
                    type: "text",
                    text: `Error executing scan: ${error.message}\n${error.stderr || ""}`
                }],
                isError: true
            };
        }
    }

    // -------------------------------------------------------------------------
    // get_file_context
    // -------------------------------------------------------------------------
    if (name === "get_file_context") {
        const filePath = (args as any).path;
        const startLine = Number((args as any).startLine);
        const endLine = Number((args as any).endLine);
        const contextLines = Number((args as any).contextLines) || 5;

        try {
            const content = await fs.readFile(filePath, "utf-8");
            const lines = content.split("\n");

            // 범위 계산 (0-indexed)
            const actualStart = Math.max(0, startLine - 1 - contextLines);
            const actualEnd = Math.min(lines.length, endLine + contextLines);

            // 라인 번호와 마커를 포함한 스니펫 생성
            const snippet = lines.slice(actualStart, actualEnd).map((line, idx) => {
                const lineNum = actualStart + idx + 1;
                const isTarget = lineNum >= startLine && lineNum <= endLine;
                const marker = isTarget ? ">" : " ";
                return `${lineNum.toString().padStart(4)} |${marker} ${line}`;
            }).join("\n");

            // 파일 정보 추가
            const header = `File: ${path.basename(filePath)} (${path.extname(filePath).slice(1) || 'txt'})\n${'─'.repeat(60)}\n`;

            return {
                content: [{ type: "text", text: header + snippet }]
            };
        } catch (error: any) {
            return {
                content: [{
                    type: "text",
                    text: `Error reading file: ${error.message}`
                }],
                isError: true
            };
        }
    }

    // -------------------------------------------------------------------------
    // list_supported_languages
    // -------------------------------------------------------------------------
    if (name === "list_supported_languages") {
        const languages = {
            primary: ["JavaScript", "TypeScript", "Python", "Java", "Go", "Ruby", "PHP"],
            frameworks: ["React", "Next.js", "Express", "Django", "Flask", "Spring"],
            rulesets: [
                { id: "p/security-audit", description: "General security vulnerabilities" },
                { id: "p/javascript", description: "JavaScript/TypeScript specific" },
                { id: "p/python", description: "Python specific" },
                { id: "p/secrets", description: "Hardcoded secrets detection" },
                { id: "p/owasp-top-ten", description: "OWASP Top 10 vulnerabilities" }
            ]
        };

        return {
            content: [{ type: "text", text: JSON.stringify(languages, null, 2) }]
        };
    }

    throw new Error(`Unknown tool: ${name}`);
});

// =============================================================================
// Main
// =============================================================================

async function run() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("[Analysis] MCP Server running on stdio (v0.2.0)");
}

run().catch((error) => {
    console.error("[Analysis] Fatal error:", error);
    process.exit(1);
});
