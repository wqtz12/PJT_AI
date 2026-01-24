# Web Scraper MCP 사용 가이드

## 개요

nodriver와 FastMCP를 활용한 범용 웹 스크래핑 도구입니다. Claude Desktop과 연동하여 웹사이트에서 데이터를 자동으로 수집할 수 있습니다.

## 주요 특징

- **차단 회피**: 사용자 프로필 유지로 실제 사용자처럼 인식
- **범용성**: CSS 선택자로 모든 웹사이트 대응 가능
- **다양한 기능**: 텍스트 추출, 링크 수집, 테이블 파싱, 스크린샷 등
- **MCP 통합**: Claude Desktop에서 자연어로 제어 가능

## 설치 방법

### 1. 필수 패키지 설치

```bash
pip install nodriver mcp
```

### 2. Chrome 브라우저 설치

macOS 기준으로 Chrome이 다음 경로에 설치되어 있어야 합니다:
```
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

Windows나 Linux 사용자는 `web_scraper_mcp.py` 파일의 `chrome_path` 변수를 수정하세요.

### 3. Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json` 파일에 다음 내용 추가:

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

**주의**: 파일 경로는 실제 경로로 수정하세요.

### 4. Claude Desktop 재시작

설정 후 Claude Desktop을 완전히 종료하고 다시 시작합니다.

## 제공 기능 (Tools)

### 1. scrape_by_selector
CSS 선택자를 사용하여 특정 요소 추출

**매개변수:**
- `url`: 스크래핑할 웹페이지 URL
- `selector`: CSS 선택자 (예: `.product-title`, `#main-content`)
- `limit`: 추출할 최대 개수 (기본값: 10)

**반환:** JSON 형식의 요소 데이터 (텍스트, href, src, className 등)

### 2. get_web_content
웹페이지의 전체 텍스트 내용 가져오기

**매개변수:**
- `url`: 가져올 웹페이지 URL

**반환:** 페이지 제목, 설명, 본문 텍스트

### 3. extract_links
웹페이지의 모든 링크 추출

**매개변수:**
- `url`: 링크를 추출할 웹페이지 URL
- `filter_text`: 필터링할 텍스트 (선택사항)

**반환:** JSON 형식의 링크 목록 (최대 50개)

### 4. take_screenshot
웹페이지 스크린샷 캡처

**매개변수:**
- `url`: 스크린샷을 찍을 웹페이지 URL
- `output_path`: 저장할 파일 경로 (기본값: screenshot.png)

**반환:** 저장된 파일 경로

### 5. scrape_table
웹페이지의 테이블 데이터 추출

**매개변수:**
- `url`: 테이블이 있는 웹페이지 URL
- `table_index`: 추출할 테이블 인덱스 (기본값: 0)

**반환:** JSON 형식의 테이블 데이터 (헤더, 행)

### 6. wait_and_click
특정 요소를 찾아 클릭

**매개변수:**
- `url`: 접속할 웹페이지 URL
- `selector`: 클릭할 요소의 CSS 선택자
- `wait_seconds`: 클릭 후 대기 시간 (기본값: 3초)

**반환:** 클릭 후 페이지 정보

### 7. close_browser
브라우저 종료

**매개변수:** 없음

**반환:** 종료 결과 메시지

## 사용 예시

### 예시 1: 뉴스 헤드라인 수집

```
사용자: 네이버 뉴스 메인페이지에서 헤드라인 10개 가져와줘
https://news.naver.com
```

Claude가 자동으로 `scrape_by_selector`를 사용하여:
- CSS 선택자로 뉴스 제목 요소 찾기
- 제목과 링크 추출
- 구조화된 데이터 반환

### 예시 2: 특정 제품 정보 추출

```
사용자: 이 쇼핑몰 페이지에서 상품명과 가격을 추출해줘
https://example.com/products

CSS 선택자는:
- 상품명: .product-name
- 가격: .product-price
```

### 예시 3: 링크 목록 수집

```
사용자: 이 블로그 페이지에서 "Python"이라는 단어가 포함된 글 링크만 가져와줘
https://example.com/blog
```

### 예시 4: 테이블 데이터 추출

```
사용자: 이 통계 페이지의 첫 번째 테이블 데이터를 CSV로 변환해줘
https://example.com/statistics
```

### 예시 5: 스크린샷 캡처

```
사용자: 이 웹페이지의 스크린샷을 찍어서 reports/screenshot.png에 저장해줘
https://example.com
```

### 예시 6: 자동 로그인 후 데이터 수집

```
사용자:
1. https://example.com/login 페이지로 이동해서
2. 로그인 버튼(#login-btn)을 클릭하고
3. 로그인 후 나오는 대시보드에서 .user-stats 클래스의 데이터를 가져와줘
```

## 고급 활용법

### CSS 선택자 팁

- **클래스**: `.class-name`
- **ID**: `#element-id`
- **속성**: `[data-id="123"]`
- **자식**: `div > p` (직접 자식)
- **하위**: `div p` (모든 하위)
- **여러 선택자**: `.class1, .class2`

### 차단 회피 전략

1. **프로필 유지**: 쿠키와 세션이 `web_scraper_profile` 폴더에 저장됨
2. **자연스러운 대기**: 각 작업마다 2-3초 대기
3. **실제 브라우저**: headless=False로 실제 브라우저처럼 동작

### 데이터 후처리

추출한 JSON 데이터를 Claude에게 요청하여:
- CSV, Excel로 변환
- 데이터 정제 및 필터링
- 통계 분석
- 시각화 코드 생성

## 문제 해결

### "브라우저를 시작할 수 없습니다"
- Chrome 경로가 올바른지 확인
- Chrome이 최신 버전인지 확인

### "요소를 찾을 수 없습니다"
- CSS 선택자가 올바른지 확인
- 페이지 로딩 시간이 충분한지 확인
- 브라우저 개발자 도구(F12)로 선택자 테스트

### "차단되었습니다"
- `wait_seconds`를 늘려서 더 자연스럽게 동작
- VPN 사용 고려
- 사이트의 robots.txt 준수

### 브라우저가 종료되지 않음
```
사용자: 브라우저 종료해줘
```

## 실전 활용 사례

### 1. 경쟁사 가격 모니터링
```
매일 아침 경쟁사 쇼핑몰에서 주요 제품 가격 수집
-> 가격 변동 분석 -> 알람 발송
```

### 2. 뉴스 모니터링
```
특정 키워드가 포함된 뉴스 실시간 수집
-> 감성 분석 -> 요약 리포트 생성
```

### 3. 부동산 매물 추적
```
부동산 사이트에서 새로운 매물 수집
-> 조건 필터링 -> 알림
```

### 4. SNS 데이터 수집
```
특정 해시태그의 게시물 수집
-> 트렌드 분석 -> 시각화
```

## 주의사항

### 법적 고지
- **robots.txt 준수**: 웹사이트의 크롤링 정책을 확인하세요
- **이용약관 확인**: 사이트의 데이터 수집 정책을 지키세요
- **개인정보 보호**: 개인정보 수집 시 관련 법규 준수
- **서버 부하**: 과도한 요청으로 서버에 부담을 주지 마세요

### 권장사항
- 크롤링 간격을 충분히 두세요 (최소 1-2초)
- 필요한 데이터만 수집하세요
- 데이터는 합법적인 목적으로만 사용하세요

## 추가 리소스

- **nodriver 문서**: https://github.com/ultrafunkamsterdam/nodriver
- **MCP 프로토콜**: https://github.com/anthropics/mcp
- **CSS 선택자 학습**: https://www.w3schools.com/cssref/css_selectors.php

## 버전 정보

- **버전**: 1.0
- **개발 환경**: Python 3.8+, nodriver, FastMCP
- **테스트 환경**: macOS, Chrome 120+

## 문의 및 피드백

사용 중 문제가 있거나 개선 제안이 있으면 언제든지 문의하세요.