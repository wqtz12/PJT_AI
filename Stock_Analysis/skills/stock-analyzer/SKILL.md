---
name: stock-analyzer
description: 종목 코드를 입력하면 데이터 수집부터 5전문가 분석, 차트, 리포트까지 완전 자동화 분석을 수행합니다.
---

# Stock Analyzer (주식 종합 분석기)

데이터 수집 → 기술적 분석 → 5전문가 앙상블 → 가중 집계 → 차트/리포트 생성 자동화 파이프라인.

## 전체 분석 워크플로우

사용자: "NVDA 종합 분석해줘"

```
Step 1: [stock-data-collector] 병렬 수집
  fetch_stock_data(ticker, period="6mo")
  fetch_company_info(ticker)
  fetch_news(ticker)
  fetch_macro_indicators()

Step 2: [technical-analysis]
  run_full_analysis(data_id) → analysis_id
  generate_signals(analysis_id)

Step 3: [expert-analysis]
  analyze_all_experts(analysis_json, company_info_json, macro_json, sentiment_json)

Step 4: [expert-analysis] 선택
  run_backtest(analysis_json)
  compute_var(analysis_json)

Step 5: [stock-report]
  generate_all_charts(analysis_json, ticker)
```

## 부분 분석

- "기술적 분석만" → Step 1(주가+기업정보) + Step 2
- "일목균형표 분석" → Step 1, 2 후 analyze_single_expert(expert_name="ichimoku")
- "매크로 환경" → fetch_macro_indicators()만
- "뉴스 감성" → fetch_news()만

## 5전문가 + 투자자 원칙

| 전문가 | 핵심 지표 | 투자자 원칙 |
|--------|-----------|------------|
| 추세추종 | SMA, ADX, MACD, 거래량 확인 돌파 | Livermore |
| 가치분석 | ROE, PEG, PBR, EPS, 영업이익률 | Buffett/Lynch |
| 모멘텀 | RSI, 스토캐스틱, 상대강도(RS) | O'Neil CANSLIM |
| 역발상 | BB %B, RSI 극단, VIX | Howard Marks |
| 일목균형표 | 구름, TK, 빗각, 삼역호전/역전 | 一目山人 원전 |

## 동적 가중치 + 시장 사이클

- ADX > 30: 추세추종/일목 1.5배 | ADX < 20: 가치 1.5배 | VIX > 25: 역발상 1.5배
- 시장 사이클(VIX+금리+S&P500): 강세장/보통/주의/약세장 판별 → 약세장 매수 확신도 감점

## 한국 종목

.KS/.KQ 자동 감지 → 네이버 뉴스/리서치 폴백, 시장 시간 캐시 TTL 조정
