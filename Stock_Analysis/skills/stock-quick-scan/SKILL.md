---
name: stock-quick-scan
description: 종목 코드만 입력하면 30초 내 매수/홀드/매도 빠른 진단 + 3분할 가격을 제공합니다.
---

# ⚡ Stock Quick Scan (주식 빠른 진단)

종목 코드 하나만 입력하면 **30초 내**에 핵심 진단 결과를 제공합니다.
전체 분석(stock-analyzer)의 축약 버전입니다.

## 사용 방법

사용자: "AAPL 빠른 진단" 또는 "005930.KS 빠른 스캔"

```
Step 1: [stock-data-collector] fetch_stock_data(ticker, period="3mo")
  → 3개월 주가 (빠른 수집)

Step 2: [stock-data-collector] fetch_company_info(ticker)
  → 기업 기본 정보

Step 3: [technical-analysis] run_full_analysis(ohlcv_json)
  → 14개 기술적 지표

Step 4: [expert-analysis] analyze_all_experts(analysis_json, company_info_json)
  → 5전문가 분석 + 가중 집계

→ 결과: 포지션(매수/홀드/매도) + 확신도 + 3분할 매수/매도가
```

## 출력 형식

```
⚡ AAPL 빠른 진단
━━━━━━━━━━━━━━━━━━
📊 현재가: $245.82
📈 종합: 🟢 매수 (확신도 72%)
━━━━━━━━━━━━━━━━━━
전문가  │ 포지션 │ 확신도
추세추종 │ 🟢 매수 │ 71%
가치분석 │ 🟡 홀드 │ 45%
모멘텀   │ 🟢 매수 │ 64%
역발상   │ 🟡 홀드 │ 40%
일목균형 │ 🟢 매수 │ 68%
━━━━━━━━━━━━━━━━━━
3분할 매수: $240.50 / $243.00 / $245.82
3분할 매도: $248.00 / $252.50 / $260.00
손절가: $235.00
```

## 전체 분석과의 차이점

| 항목 | Quick Scan | Full Analysis |
|------|-----------|---------------|
| 데이터 기간 | 3개월 | 6개월 |
| 뉴스/애널리스트 | ❌ 스킵 | ✅ 포함 |
| 매크로 지표 | ❌ 스킵 | ✅ 6종 수집 |
| 백테스트/VaR | ❌ 스킵 | ✅ 포함 |
| 차트 생성 | ❌ 스킵 | ✅ 3종 |
| 텍스트 리포트 | ❌ 스킵 | ✅ 종합 |
| 소요 시간 | ~30초 | ~2분 |

## 필요 MCP 서버

- stock-data-collector (필수)
- technical-analysis (필수)
- expert-analysis (필수)
