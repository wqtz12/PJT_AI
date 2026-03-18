---
name: claude-data-collector
description: Claude 전용 데이터 수집 워크플로우. 주식 데이터를 수집하고 data/ 디렉토리에 저장한 뒤 Gemini에게 분석 요청 시그널을 보냅니다.
---

# Claude Data Collector (데이터 수집 파이프라인)

Claude가 실행하는 Phase 1 데이터 수집 전담 워크플로우입니다.
수집 완료 후 `handoff/data_ready.md` 신호를 생성하여 Gemini에게 분석을 요청합니다.

## 종합 분석용 수집 워크플로우

사용자: "NVDA 데이터 수집해줘" 또는 종합 분석 요청의 Phase 1 단계

```
Step 1: [stock-data-collector] 병렬 데이터 수집
  result_1 = fetch_stock_data(ticker, period="6mo")
  result_2 = fetch_company_info(ticker)
  result_3 = fetch_news(ticker)
  result_4 = fetch_macro_indicators()

Step 2: 수집 결과를 data/ 디렉토리에 JSON 저장
  → data/{TICKER}_stock_data.json
  → data/{TICKER}_company_info.json
  → data/{TICKER}_news.json
  → data/macro_indicators.json

Step 3: handoff/data_ready_{TICKER}.json 생성
  → Gemini에게 "데이터 수집 완료, 분석 시작" 시그널 전달
```

## 에러 발생 시 자가 치유

데이터 수집 중 에러가 발생하면 Claude가 직접 코드를 수정합니다:

1. 에러 로그 분석
2. 관련 소스 코드 확인 (`Stock_Analysis/mcp_servers/stock_data_mcp.py`, `data_fetcher.py` 등)
3. 코드 수정 및 재실행
4. 성공 시 Step 2로 복귀

## 에러 태스크 수정 워크플로우

Gemini가 `handoff/error_task.md`를 생성했을 때:

```
Step 1: handoff/error_task_{TICKER}.json 읽기
  → 에러 발생 컴포넌트, 도구, 스택 트레이스 확인

Step 2: 관련 소스 코드 분석
  → Stock_Analysis/mcp_servers/{component}.py
  → Stock_Analysis/{관련 모듈}.py

Step 3: 코드 수정 및 로컬 테스트
  → cd Stock_Analysis && python -m pytest tests/ -v

Step 4: handoff/resolution_{TICKER}.json 생성
  → Gemini에게 "수정 완료, 파이프라인 재개" 시그널 전달
```

## 빠른 진단용 수집 (축약)

```
Step 1: fetch_stock_data(ticker, period="3mo")
Step 2: fetch_company_info(ticker)
→ 뉴스/매크로 스킵
```

## 데이터 파일명 규칙

| 데이터 유형 | 파일명 | 비고 |
|------------|--------|------|
| 주가 OHLCV | `{TICKER}_stock_data.json` | data_id 포함 |
| 기업 정보 | `{TICKER}_company_info.json` | PER/PBR/ROE 등 |
| 뉴스 감성 | `{TICKER}_news.json` | sentiment_summary 포함 |
| 매크로 지표 | `macro_indicators.json` | 글로벌, 종목 무관 |

## 필요 MCP 서버

- **stock-data-collector** (필수): `fetch_stock_data`, `fetch_company_info`, `fetch_news`, `fetch_macro_indicators`
