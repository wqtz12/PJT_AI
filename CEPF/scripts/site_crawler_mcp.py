import asyncio
import nodriver as n
from mcp.server.fastmcp import FastMCP

# 1. 서버 이름 설정
mcp = FastMCP("Nodriver Crawler")

@mcp.tool()
async def scrape_website(url: str) -> str:
    """
    주어진 URL의 웹사이트를 방문하여 텍스트 콘텐츠를 크롤링합니다.
    JavaScript가 많은 동적 웹사이트도 처리할 수 있습니다.
    
    Args:
        url: 크롤링할 웹사이트 주소 (예: https://example.com)
    """
    browser = None
    try:
        # 2. 브라우저 시작 (headless=True: 화면을 띄우지 않고 백그라운드 실행)
        # sandbox=False는 일부 환경(Docker 등)에서 필요할 수 있습니다.
        browser = await n.start(headless=True)
        
        # 3. 페이지 이동
        page = await browser.get(url)
        
        # 4. 페이지 로딩 대기 (필요시 특정 요소가 뜰 때까지 대기 가능)
        # 여기서는 body 태그가 뜰 때까지 최대 10초 기다림
        await page.wait_for("body", timeout=10)
        
        # 5. 데이터 추출
        # (1) 페이지 제목
        title = await page.evaluate("document.title")
        
        # (2) 본문 텍스트 (Markdown으로 변환하면 더 좋지만, 여기서는 순수 텍스트 추출)
        # innerText는 사람이 보는 텍스트만 가져옵니다 (숨겨진 코드 제외)
        content = await page.evaluate("document.body.innerText")
        
        # 결과 정리
        result = f"--- [Page Title]: {title} ---\n\n{content}"
        
        # 텍스트가 너무 길면 Claude 컨텍스트를 위해 적당히 자릅니다 (선택사항)
        if len(result) > 20000:
            result = result[:20000] + "\n...(내용이 너무 길어 생략됨)..."
            
        return result

    except Exception as e:
        return f"크롤링 중 오류가 발생했습니다: {str(e)}"
    
    finally:
        # 6. 작업이 끝나면 반드시 브라우저를 종료해야 메모리가 안 쌓입니다.
        if browser:
            try:
                browser.stop()
            except:
                pass

if __name__ == "__main__":
    mcp.run()