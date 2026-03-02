#!/usr/bin/env node
/**
 * MCP Knowledge Server
 * 
 * 보안 가이드라인(Skills)을 제공하는 MCP 서버입니다.
 * Skills는 파일 기반으로 관리되며, LLM이 도구를 통해 조회할 수 있습니다.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
    Tool,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from 'url';

// =============================================================================
// Types
// =============================================================================

interface SkillMetadata {
    name: string;
    description: string;
    content: string;
    sections: Map<string, string>; // section name -> content
}

// =============================================================================
// Tool Definitions
// =============================================================================

const LIST_SKILLS_TOOL: Tool = {
    name: "list_security_skills",
    description: "사용 가능한 모든 보안 스킬(가이드) 목록을 조회합니다.",
    inputSchema: {
        type: "object",
        properties: {}
    }
};

const GET_SKILL_TOOL: Tool = {
    name: "get_security_skill",
    description: "특정 보안 스킬의 전체 내용을 조회합니다.",
    inputSchema: {
        type: "object",
        properties: {
            skill_name: {
                type: "string",
                description: "스킬 이름 (예: 'javascript-secure-coding', 'privacy-checklist', 'ai-security-checklist')"
            }
        },
        required: ["skill_name"]
    }
};

const GET_SKILL_SECTION_TOOL: Tool = {
    name: "get_skill_section",
    description: "특정 보안 스킬 내의 특정 섹션(## 헤더)만 조회합니다.",
    inputSchema: {
        type: "object",
        properties: {
            skill_name: {
                type: "string",
                description: "스킬 이름"
            },
            section_name: {
                type: "string",
                description: "섹션 이름 (예: 'XSS', 'SQL Injection', 'Prompt Injection 방어')"
            }
        },
        required: ["skill_name", "section_name"]
    }
};

const SEARCH_SKILLS_TOOL: Tool = {
    name: "search_skills",
    description: "모든 스킬에서 키워드를 검색하여 관련 섹션을 반환합니다.",
    inputSchema: {
        type: "object",
        properties: {
            keyword: {
                type: "string",
                description: "검색할 키워드 (예: 'XSS', 'injection', '암호화')"
            }
        },
        required: ["keyword"]
    }
};

// =============================================================================
// Skill Loading
// =============================================================================

const SKILLS: Map<string, SkillMetadata> = new Map();

/**
 * Markdown 파일에서 섹션(## 헤더)을 추출합니다.
 */
function parseSections(content: string): Map<string, string> {
    const sections = new Map<string, string>();
    const lines = content.split('\n');
    let currentSection = '';
    let currentContent: string[] = [];

    for (const line of lines) {
        if (line.startsWith('## ')) {
            // 이전 섹션 저장
            if (currentSection) {
                sections.set(currentSection, currentContent.join('\n').trim());
            }
            currentSection = line.replace('## ', '').trim();
            currentContent = [line];
        } else if (currentSection) {
            currentContent.push(line);
        }
    }

    // 마지막 섹션 저장
    if (currentSection) {
        sections.set(currentSection, currentContent.join('\n').trim());
    }

    return sections;
}

/**
 * YAML frontmatter에서 메타데이터를 추출합니다.
 */
function parseMetadata(content: string): { name: string; description: string; body: string } {
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (!frontmatterMatch) {
        return { name: '', description: '', body: content };
    }

    const frontmatter = frontmatterMatch[1];
    const body = content.slice(frontmatterMatch[0].length).trim();

    const nameMatch = frontmatter.match(/name:\s*(.+)/);
    const descMatch = frontmatter.match(/description:\s*(.+)/);

    return {
        name: nameMatch ? nameMatch[1].trim() : '',
        description: descMatch ? descMatch[1].trim() : '',
        body
    };
}

/**
 * skills 디렉토리에서 모든 .md 파일을 로드합니다.
 */
async function loadSkills(skillsDir: string): Promise<void> {
    try {
        const files = await fs.readdir(skillsDir);
        const mdFiles = files.filter(f => f.endsWith('.md'));

        for (const file of mdFiles) {
            const filePath = path.join(skillsDir, file);
            const content = await fs.readFile(filePath, 'utf-8');
            const { name, description, body } = parseMetadata(content);

            // 파일명에서 스킬 이름 추출 (fallback)
            const skillName = name || file.replace('.md', '');

            const skill: SkillMetadata = {
                name: skillName,
                description: description || `Security guide: ${skillName}`,
                content: body,
                sections: parseSections(body)
            };

            SKILLS.set(skillName, skill);
            console.error(`Loaded skill: ${skillName} (${skill.sections.size} sections)`);
        }

        console.error(`Total skills loaded: ${SKILLS.size}`);
    } catch (error) {
        console.error(`Error loading skills from ${skillsDir}:`, error);
    }
}

// =============================================================================
// Server Setup
// =============================================================================

const server = new Server(
    {
        name: "vuln-detector/knowledge",
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
        tools: [LIST_SKILLS_TOOL, GET_SKILL_TOOL, GET_SKILL_SECTION_TOOL, SEARCH_SKILLS_TOOL],
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    // -------------------------------------------------------------------------
    // list_security_skills
    // -------------------------------------------------------------------------
    if (name === "list_security_skills") {
        const skillList = Array.from(SKILLS.values()).map(skill => ({
            name: skill.name,
            description: skill.description,
            sections: Array.from(skill.sections.keys())
        }));

        return {
            content: [{ type: "text", text: JSON.stringify(skillList, null, 2) }]
        };
    }

    // -------------------------------------------------------------------------
    // get_security_skill
    // -------------------------------------------------------------------------
    if (name === "get_security_skill") {
        const skillName = (args as any).skill_name;
        const skill = SKILLS.get(skillName);

        if (!skill) {
            const availableSkills = Array.from(SKILLS.keys());
            return {
                content: [{
                    type: "text",
                    text: `Skill '${skillName}' not found. Available skills: ${availableSkills.join(', ')}`
                }],
                isError: true
            };
        }

        return {
            content: [{ type: "text", text: skill.content }]
        };
    }

    // -------------------------------------------------------------------------
    // get_skill_section
    // -------------------------------------------------------------------------
    if (name === "get_skill_section") {
        const skillName = (args as any).skill_name;
        const sectionName = (args as any).section_name;
        const skill = SKILLS.get(skillName);

        if (!skill) {
            return {
                content: [{ type: "text", text: `Skill '${skillName}' not found.` }],
                isError: true
            };
        }

        // 정확한 매칭 또는 부분 매칭 시도
        let sectionContent = skill.sections.get(sectionName);

        if (!sectionContent) {
            // 부분 매칭 시도 (대소문자 무시)
            for (const [key, value] of skill.sections) {
                if (key.toLowerCase().includes(sectionName.toLowerCase())) {
                    sectionContent = value;
                    break;
                }
            }
        }

        if (!sectionContent) {
            const availableSections = Array.from(skill.sections.keys());
            return {
                content: [{
                    type: "text",
                    text: `Section '${sectionName}' not found in skill '${skillName}'. Available sections: ${availableSections.join(', ')}`
                }]
            };
        }

        return {
            content: [{ type: "text", text: sectionContent }]
        };
    }

    // -------------------------------------------------------------------------
    // search_skills
    // -------------------------------------------------------------------------
    if (name === "search_skills") {
        const keyword = (args as any).keyword.toLowerCase();
        const results: { skill: string; section: string; snippet: string }[] = [];

        for (const [skillName, skill] of SKILLS) {
            for (const [sectionName, sectionContent] of skill.sections) {
                if (
                    sectionName.toLowerCase().includes(keyword) ||
                    sectionContent.toLowerCase().includes(keyword)
                ) {
                    // 스니펫 추출 (처음 200자)
                    const snippet = sectionContent.substring(0, 200) + (sectionContent.length > 200 ? '...' : '');
                    results.push({
                        skill: skillName,
                        section: sectionName,
                        snippet
                    });
                }
            }
        }

        if (results.length === 0) {
            return {
                content: [{ type: "text", text: `No results found for keyword '${keyword}'` }]
            };
        }

        return {
            content: [{ type: "text", text: JSON.stringify(results, null, 2) }]
        };
    }

    throw new Error(`Unknown tool: ${name}`);
});

// =============================================================================
// Main
// =============================================================================

async function run() {
    const __dirname = path.dirname(fileURLToPath(import.meta.url));

    // skills 디렉토리 경로 결정 (dist or src)
    let skillsDir = path.resolve(__dirname, './skills');
    try {
        await fs.access(skillsDir);
    } catch {
        // dist에서 실행 중이면 src 참조
        skillsDir = path.resolve(__dirname, '../src/skills');
    }

    console.error(`Loading skills from: ${skillsDir}`);
    await loadSkills(skillsDir);

    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Knowledge MCP Server running on stdio (v0.2.0)");
}

run().catch((error) => {
    console.error("Fatal error in Knowledge MCP Server:", error);
    process.exit(1);
});
