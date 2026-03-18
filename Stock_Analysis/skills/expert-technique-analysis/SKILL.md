---
name: expert-technique-analysis
description: 5명의 전문가별 투자 기법을 개별 분석하고, 유명 투자자 원칙 기반 심층 해석을 제공합니다.
---

# Expert Technique Analysis (전문가별 투자 기법 분석)

각 전문가의 투자 기법을 유명 투자자 원칙 관점에서 개별 심층 분석합니다.

## 사용 방법

사용자: "NVDA 전문가별 기법 분석해줘" 또는 "TSLA 투자 기법 분석"

```
Step 1: 데이터 수집 (병렬)
  fetch_stock_data(ticker, period="6mo")
  fetch_company_info(ticker)
  fetch_news(ticker)
  fetch_macro_indicators()

Step 2: run_full_analysis(data_id)

Step 3: 개별 전문가 분석 (5회 analyze_single_expert)
  expert_name: trend / value / momentum / contrarian / ichimoku

Step 4: 전문가별 기법 해석 리포트 생성
```

## 전문가-투자자 매핑

| 전문가 | 투자자 원칙 | v2 추가 핵심 |
|--------|-----------|-------------|
| 추세추종 | Livermore | 거래량 확인 돌파 (진짜/가짜 돌파 판별) |
| 가치분석 | Buffett/Lynch | ROE(경쟁우위), PEG(성장저평가), 영업이익률(해자) |
| 모멘텀 | O'Neil CANSLIM | 상대강도 RS (시장 대비 Leader/Laggard) |
| 역발상 | Howard Marks | 시장 사이클 + 2차 사고 (ADX로 추세/반전 구별) |
| 일목균형표 | 一目山人 원전 | 삼역호전/역전 (3조건 동시 = 최강 신호) |

## 해석 원칙 (리포트 생성시 적용)

- 각 전문가의 rationale에 점수 구성이 이미 포함됨
- score >= 6은 해당 전문가의 "강한 확신" 구간
- 전문가간 의견 불일치는 시장 불확실성을 의미
- 시장 사이클(강세/약세)은 aggregation 결과의 market_cycle.phase에 표시됨

## 부분 분석

- "NVDA 추세추종 기법 분석" → analyze_single_expert(expert_name="trend")
- "AAPL Buffett 관점 분석" → analyze_single_expert(expert_name="value")
- "TSLA 일목 삼역호전 확인" → analyze_single_expert(expert_name="ichimoku")
