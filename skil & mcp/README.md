# Web Scraper MCP

nodriver와 FastMCP를 활용한 범용 웹 스크래핑 도구입니다. Claude Desktop과 연동하여 자연어로 웹 데이터를 수집할 수 있습니다.

## 빠른 시작

### 1. 패키지 설치

```bash
cd "skil & mcp"
pip install -r requirements.txt
```

### 2. Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json` 파일 수정:

```json
{
  "mcpServers": {
    "web-scraper": {
      "command": "python",
      "args": ["/Users/jbs/PJT_AI/skil & mcp/web_scraper_mcp.py"]
    }
  }
}
```

**Windows 사용자**: 경로를 `C:\Users\...\web_scraper_mcp.py` 형식으로 수정하세요.

### 3. Claude Desktop 재시작

설정 완료 후 Claude Desktop을 완전히 종료하고 다시 실행합니다.

### 4. 테스트

Claude Desktop에서 다음과 같이 테스트해보세요:

```
네이버 뉴스 메인페이지에서 헤드라인 5개 가져와줘
https://news.naver.com
```

## 주요 기능

| 기능 | 설명 |
|------|------|
| **scrape_by_selector** | CSS 선택자로 특정 요소 추출 |
| **get_web_content** | 페이지 전체 텍스트 가져오기 |
| **extract_links** | 모든 링크 추출 |
| **take_screenshot** | 스크린샷 캡처 |
| **scrape_table** | 테이블 데이터 추출 |
| **wait_and_click** | 요소 클릭 및 상호작용 |
| **close_browser** | 브라우저 종료 |

## 사용 예시

### CSS 선택자로 데이터 추출
```
이 페이지에서 .product-title 클래스의 상품명 10개 가져와줘
https://example.com/products
```

### 테이블 데이터 파싱
```
이 통계 페이지의 테이블을 CSV로 변환해줘
https://example.com/statistics
```

### 스크린샷 캡처
```
이 웹페이지 스크린샷을 screenshot.png로 저장해줘
https://example.com
```

## 파일 구조

```
skil & mcp/
├── web_scraper_mcp.py          # MCP 서버 메인 파일
├── web_scraper_사용가이드.md   # 상세 사용 가이드
├── requirements.txt             # 필수 패키지 목록
├── README.md                    # 이 파일
└── naver_news_mcp.py            # 네이버 뉴스 예시
```

## 문제 해결

### Chrome 경로 오류
`web_scraper_mcp.py` 파일의 18번째 줄에서 Chrome 경로를 수정하세요:

```python
# Windows
chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"

# Linux
chrome_path = "/usr/bin/google-chrome"
```

### 모듈을 찾을 수 없음
```bash
pip install --upgrade nodriver mcp
```

### 브라우저가 시작되지 않음
1. Chrome이 설치되어 있는지 확인
2. Chrome 버전이 최신인지 확인
3. 권한 문제가 있는지 확인

## 더 알아보기

자세한 내용은 [web_scraper_사용가이드.md](./web_scraper_사용가이드.md)를 참고하세요.

## 주의사항

- 웹사이트의 `robots.txt`와 이용약관을 준수하세요
- 과도한 요청으로 서버에 부담을 주지 마세요
- 개인정보 관련 법규를 지켜주세요

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 자유롭게 사용할 수 있습니다.