"""
네이버 뉴스 헤드라인 수집 스크립트
"""

import asyncio
import os
import nodriver as n

async def get_naver_news():
    """네이버 뉴스 메인에서 헤드라인 10개를 가져옵니다."""
    browser = None
    try:
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        current_dir = os.getcwd()
        profile_dir = os.path.join(current_dir, "bot_profile")

        print("🔄 브라우저를 시작합니다...")
        browser = await n.start(
            headless=False,
            browser_executable_path=chrome_path,
            user_data_dir=profile_dir,
            browser_args=[
                "--window-size=1920,1080",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

        url = "https://news.naver.com"
        print(f"🌐 페이지 접속 중: {url}")
        page = await browser.get(url)

        print("⏳ 페이지 로딩 대기 중...")
        await asyncio.sleep(5)

        # 스크린샷 저장
        screenshot_path = os.path.join(current_dir, "news_screenshot.png")
        try:
            await page.save_screenshot(screenshot_path)
            print(f"📸 스크린샷 저장: {screenshot_path}")
        except:
            print("⚠️ 스크린샷 저장 실패")

        print("📊 헤드라인 추출 중...")

        # 여러 선택자 시도
        selectors = [
            'a.ca_item_title_link',
            '.cjs_t a',
            '.sa_text_title',
            'div.cjs_t',
            'a[href*="/article/"]'
        ]

        news_data = []
        for selector in selectors:
            try:
                elements = await page.select_all(selector)
                if elements:
                    print(f"✓ '{selector}' 선택자로 {len(elements)}개 요소 발견")

                    for idx, elem in enumerate(elements[:10]):
                        try:
                            # 텍스트와 링크 추출
                            text = await elem.get_property('textContent')
                            text_value = await text.json_value() if text else ''

                            href = await elem.get_property('href')
                            href_value = await href.json_value() if href else ''

                            if text_value and text_value.strip():
                                news_data.append({
                                    'rank': len(news_data) + 1,
                                    'title': text_value.strip(),
                                    'link': href_value
                                })

                            if len(news_data) >= 10:
                                break
                        except:
                            continue

                    if len(news_data) >= 10:
                        break
            except Exception as e:
                print(f"  ⨯ '{selector}' 선택자 실패: {e}")
                continue

        if not news_data or len(news_data) == 0:
            print("❌ 데이터 추출 실패")
            print("페이지 HTML 구조 확인 중...")

            # 디버깅을 위해 사용 가능한 선택자 확인
            available_selectors = await page.evaluate("""
                () => {
                    return {
                        cjs_news_tw: document.querySelectorAll('.cjs_news_tw').length,
                        sa_text_title: document.querySelectorAll('.sa_text_title').length,
                        cluster_text: document.querySelectorAll('.cluster_text').length
                    };
                }
            """)
            print(f"사용 가능한 선택자: {available_selectors}")
            return

        print("\n" + "="*70)
        print(f"📰 네이버 뉴스 헤드라인 Top {len(news_data)}")
        print("="*70 + "\n")

        for item in news_data:
            print(f"{item['rank']:2d}. {item['title']}")
            if item['link']:
                print(f"    🔗 {item['link']}")
            print()

        print("="*70)
        print(f"✅ 총 {len(news_data)}개의 헤드라인을 수집했습니다.")

        await asyncio.sleep(2)

    except Exception as e:
        print(f"🚨 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        if browser:
            try:
                print("\n🔚 브라우저를 종료합니다...")
                browser.stop()
            except:
                pass

if __name__ == "__main__":
    print("=" * 70)
    print("네이버 뉴스 헤드라인 수집기")
    print("=" * 70 + "\n")
    asyncio.run(get_naver_news())