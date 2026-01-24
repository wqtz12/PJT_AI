"""
Web Scraper MCP - nodriver를 활용한 범용 웹 스크래핑 도구
Claude Desktop과 연동하여 웹사이트에서 데이터를 수집합니다.
"""

import asyncio
import os
import json
from typing import List, Dict, Any
import nodriver as n
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WebScraper")

# 전역 브라우저 인스턴스 (재사용)
_browser = None
_profile_dir = None

async def get_browser():
    """브라우저 인스턴스를 가져오거나 새로 생성합니다."""
    global _browser, _profile_dir

    if _browser is None:
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

        # 봇 전용 프로필 폴더
        current_dir = os.getcwd()
        _profile_dir = os.path.join(current_dir, "web_scraper_profile")

        _browser = await n.start(
            headless=False,
            browser_executable_path=chrome_path,
            user_data_dir=_profile_dir,
            browser_args=[
                "--window-size=1920,1080",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

    return _browser


@mcp.tool()
async def scrape_by_selector(url: str, selector: str, limit: int = 10) -> str:
    """
    CSS 선택자를 사용하여 웹페이지에서 특정 요소들을 추출합니다.

    Args:
        url: 스크래핑할 웹페이지 URL
        selector: CSS 선택자 (예: '.product-title', '#main-content', 'div.article')
        limit: 추출할 최대 요소 개수 (기본값: 10)

    Returns:
        JSON 형식의 추출된 데이터 (텍스트, href, src 속성 포함)
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        # 페이지 로딩 대기
        await asyncio.sleep(3)

        # JavaScript로 요소 추출
        data = await page.evaluate(f"""
            () => {{
                const elements = document.querySelectorAll('{selector}');
                const results = Array.from(elements).slice(0, {limit}).map((el, index) => {{
                    return {{
                        index: index + 1,
                        text: el.innerText?.trim() || '',
                        html: el.innerHTML?.substring(0, 200) || '',
                        href: el.href || el.querySelector('a')?.href || '',
                        src: el.src || el.querySelector('img')?.src || '',
                        className: el.className || '',
                        id: el.id || ''
                    }};
                }});
                return results;
            }}
        """)

        if not data:
            return f"❌ 선택자 '{selector}'에 해당하는 요소를 찾을 수 없습니다."

        result = {
            "url": url,
            "selector": selector,
            "count": len(data),
            "data": data
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def get_web_content(url: str) -> str:
    """
    웹페이지의 전체 텍스트 내용을 가져옵니다.

    Args:
        url: 가져올 웹페이지 URL

    Returns:
        웹페이지의 텍스트 내용
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        await asyncio.sleep(3)

        # 페이지 제목과 본문 텍스트 추출
        content = await page.evaluate("""
            () => {
                return {
                    title: document.title,
                    text: document.body.innerText,
                    description: document.querySelector('meta[name="description"]')?.content || ''
                };
            }
        """)

        result = f"""=== 📄 {content['title']} ===
URL: {url}
설명: {content['description']}

본문:
{content['text'][:5000]}...
"""
        return result

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def extract_links(url: str, filter_text: str = "") -> str:
    """
    웹페이지에서 모든 링크를 추출합니다.

    Args:
        url: 링크를 추출할 웹페이지 URL
        filter_text: 필터링할 텍스트 (링크 텍스트에 이 문자열이 포함된 것만 추출)

    Returns:
        JSON 형식의 링크 목록
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        await asyncio.sleep(3)

        links = await page.evaluate(f"""
            () => {{
                const anchors = document.querySelectorAll('a[href]');
                const filter = '{filter_text}';
                const results = Array.from(anchors).map((a, index) => {{
                    const text = a.innerText?.trim() || '';
                    const href = a.href || '';

                    if (filter && !text.toLowerCase().includes(filter.toLowerCase())) {{
                        return null;
                    }}

                    return {{
                        index: index + 1,
                        text: text.substring(0, 100),
                        url: href
                    }};
                }}).filter(item => item !== null);

                return results;
            }}
        """)

        result = {
            "source_url": url,
            "filter": filter_text or "없음",
            "link_count": len(links),
            "links": links[:50]  # 최대 50개만 반환
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def take_screenshot(url: str, output_path: str = "screenshot.png") -> str:
    """
    웹페이지의 스크린샷을 캡처합니다.

    Args:
        url: 스크린샷을 찍을 웹페이지 URL
        output_path: 저장할 파일 경로 (기본값: screenshot.png)

    Returns:
        스크린샷 저장 경로
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        await asyncio.sleep(3)

        # 절대 경로로 변환
        if not os.path.isabs(output_path):
            output_path = os.path.join(os.getcwd(), output_path)

        # 스크린샷 저장
        await page.save_screenshot(output_path)

        return f"✅ 스크린샷 저장 완료: {output_path}"

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def scrape_table(url: str, table_index: int = 0) -> str:
    """
    웹페이지에서 테이블 데이터를 추출합니다.

    Args:
        url: 테이블이 있는 웹페이지 URL
        table_index: 추출할 테이블 인덱스 (0부터 시작, 기본값: 0)

    Returns:
        JSON 형식의 테이블 데이터
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        await asyncio.sleep(3)

        table_data = await page.evaluate(f"""
            () => {{
                const tables = document.querySelectorAll('table');
                if (tables.length === 0) {{
                    return {{ error: '테이블을 찾을 수 없습니다.' }};
                }}

                if ({table_index} >= tables.length) {{
                    return {{ error: `테이블 인덱스가 범위를 벗어났습니다. (최대: ${{tables.length - 1}})` }};
                }}

                const table = tables[{table_index}];
                const headers = [];
                const rows = [];

                // 헤더 추출
                const headerCells = table.querySelectorAll('thead th, thead td');
                if (headerCells.length > 0) {{
                    headerCells.forEach(cell => headers.push(cell.innerText.trim()));
                }} else {{
                    // 첫 번째 행을 헤더로 사용
                    const firstRow = table.querySelector('tr');
                    if (firstRow) {{
                        firstRow.querySelectorAll('th, td').forEach(cell =>
                            headers.push(cell.innerText.trim())
                        );
                    }}
                }}

                // 데이터 행 추출
                const dataRows = table.querySelectorAll('tbody tr, tr');
                dataRows.forEach((row, rowIndex) => {{
                    if (rowIndex === 0 && headerCells.length === 0) return; // 헤더로 사용한 첫 행 스킵

                    const cells = row.querySelectorAll('td, th');
                    if (cells.length > 0) {{
                        const rowData = [];
                        cells.forEach(cell => rowData.push(cell.innerText.trim()));
                        rows.push(rowData);
                    }}
                }});

                return {{
                    table_index: {table_index},
                    total_tables: tables.length,
                    headers: headers,
                    rows: rows.slice(0, 50), // 최대 50행만
                    row_count: rows.length
                }};
            }}
        """)

        if 'error' in table_data:
            return f"❌ {table_data['error']}"

        result = {
            "url": url,
            "table_info": table_data
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def wait_and_click(url: str, selector: str, wait_seconds: int = 3) -> str:
    """
    웹페이지에서 특정 요소를 찾아 클릭합니다.

    Args:
        url: 접속할 웹페이지 URL
        selector: 클릭할 요소의 CSS 선택자
        wait_seconds: 클릭 후 대기 시간 (초)

    Returns:
        작업 결과 메시지
    """
    browser = None
    try:
        browser = await get_browser()
        page = await browser.get(url)

        await asyncio.sleep(2)

        # 요소 찾기 및 클릭
        element = await page.select(selector)
        if element:
            await element.click()
            await asyncio.sleep(wait_seconds)

            # 현재 페이지 정보 반환
            current_url = await page.evaluate("() => window.location.href")
            title = await page.evaluate("() => document.title")

            return f"✅ 클릭 완료\n현재 URL: {current_url}\n페이지 제목: {title}"
        else:
            return f"❌ 선택자 '{selector}'에 해당하는 요소를 찾을 수 없습니다."

    except Exception as e:
        return f"🚨 오류: {str(e)}"


@mcp.tool()
async def close_browser() -> str:
    """
    브라우저를 종료합니다.

    Returns:
        종료 결과 메시지
    """
    global _browser
    try:
        if _browser:
            _browser.stop()
            _browser = None
            return "✅ 브라우저가 종료되었습니다."
        else:
            return "ℹ️ 실행 중인 브라우저가 없습니다."
    except Exception as e:
        return f"🚨 오류: {str(e)}"


if __name__ == "__main__":
    mcp.run()