import asyncio
import os
import nodriver as n
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("NaverNewsScraper")

@mcp.tool()
async def get_naver_news(url: str) -> str:
    """
    지정된 네이버 뉴스 섹션 URL에 접속하여 주요 뉴스 10개를 가져옵니다.
    사용자 프로필을 유지하여 차단을 회피합니다.
    - url (str): 수집할 네이버 뉴스 섹션 URL (예: "https://news.naver.com/section/101")
    """
    browser = None
    try:
        # 1. 내 컴퓨터의 Chrome 경로 (Mac 기준)
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        
        # 2. 봇 전용 프로필 폴더 생성 (현재 폴더에 'bot_profile'이라는 폴더를 만들어 저장)
        # 이렇게 하면 쿠키가 저장되어 다음 접속 때 '재방문자'로 인식됩니다.
        current_dir = os.getcwd()
        profile_dir = os.path.join(current_dir, "bot_profile")

        browser = await n.start(
            headless=False, # 화면 띄우기 (필수)
            browser_executable_path=chrome_path,
            # [핵심] 프로필 폴더 지정
            user_data_dir=profile_dir, 
            browser_args=[
                "--window-size=1920,1080",
                # 맥북 유저인 척하는 User-Agent
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )
        
        page = await browser.get(url)
        
        # [중요] 페이지 들어가서 3초 정도 멍 때리기 (사람처럼 보이기 위함)
        await asyncio.sleep(3) 
        
        # 요소 대기
        await page.wait_for("div.section_body", timeout=20)
        
        news_data = await page.evaluate("""
            () => {
                const items = document.querySelectorAll('.sa_text_title');
                const results = Array.from(items).slice(0, 10).map((el, index) => {
                    return {
                        rank: index + 1,
                        title: el.innerText.trim(),
                        link: el.href
                    };
                });
                return results;
            }
        """ ) 
        
        if not news_data:
            return "❌ 데이터 추출 실패. (차단 화면이 떴는지 모니터를 확인해보세요)"

        result_text = f"=== 📈 네이버 뉴스 Top 10 ({url}) ===\n\n"
        for item in news_data:
            result_text += f"{item['rank']}. {item['title']}\n   🔗 {item['link']}\n"
            
        return result_text

    except Exception as e:
        return f"🚨 오류: {str(e)}"
    
    finally:
        if browser:
            try:
                # 디버깅을 위해 라우저를 바로 끄지 않고 싶으면 아래 줄을 주석 처리하세요.
                browser.stop()
            except:
                pass

if __name__ == "__main__":
    mcp.run()
