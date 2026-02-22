---
name: stock-analyzer
description: 종목 코드를 입력하면 데이터 수집부터 5전문가 분석, 차트, 리포트까지 완전 자동화 분석을 수행합니다.
---

# 📊 Stock Analyzer (주식 종합 분석기)

주식 종목에 대한 **완전 자동화 분석 파이프라인**입니다.
데이터 수집 → 기술적 분석 → 5명 전문가 앙상블 → 가중 집계 → 차트/리포트 생성까지 한 번에 수행합니다.

## 지원 기능

| 기능 | 설명 | MCP 서버 |
|------|------|----------|
| 주가 데이터 | yfinance OHLCV 수집 + 품질 검증 | stock-data-collector |
| 기업 정보 | 섹터, PER, PBR, EPS, 시총, 부채비율 | stock-data-collector |
| 뉴스 감성 | 뉴스 수집 + 긍정/부정/중립 감성 분석 | stock-data-collector |
| 애널리스트 | 증권사 투자의견 + 컨센서스 요약 | stock-data-collector |
| 매크로 경제 | VIX, 금리, S&P500, 유가, 금, 달러 | stock-data-collector |
| 기술적 분석 | 14개 지표 (MA, RSI, MACD, BB, 일목균형표 등) | technical-analysis |
| 전문가 분석 | 추세추종/가치/모멘텀/역발상/일목 5명 앙상블 | expert-analysis |
| 의견 필터 | 하락추세 경고, 가치함정 탐지, 과매도 검증 | expert-analysis |
| 백테스트 | 수익률, MDD, 샤프비율, 승률, VaR | expert-analysis |
| 시각화 | 캔들스틱, 대시보드, 성과 차트 3종 | stock-report |
| 리포트 | 텍스트 종합 분석 보고서 | stock-report |

## 사용 방법

### 전체 분석 워크플로우

사용자: "NVDA 종합 분석해줘"

```
Step 1: [stock-data-collector] fetch_stock_data(ticker="NVDA", period="6mo")
  → OHLCV 주가 데이터 수집

Step 2: [stock-data-collector] fetch_company_info(ticker="NVDA")
  → 기업 기본 정보 (섹터, 밸류에이션)

Step 3: [stock-data-collector] 병렬 수집
  - fetch_news(ticker="NVDA") → 뉴스 + 감성
  - fetch_analyst_ratings(ticker="NVDA") → 증권사 의견
  - fetch_macro_indicators() → 매크로 6종

Step 4: [technical-analysis] run_full_analysis(ohlcv_json)
  → 14개 기술적 지표 계산

Step 5: [technical-analysis] generate_signals(analysis_json)
  → 매매 신호 종합 판단

Step 6: [expert-analysis] analyze_all_experts(analysis_json, company_info_json, ...)
  → 5전문가 분석 + 가중 집계 + 필터

Step 7: [expert-analysis] run_backtest(analysis_json) + compute_var(analysis_json)
  → 백테스트 + VaR 위험 분석

Step 8: [stock-report] generate_all_charts(analysis_json, ticker)
  → 캔들스틱 + 대시보드 + 성과 차트 3종
```

### 부분 분석

- "AAPL 기술적 분석만 해줘" → Step 1, 4, 5만 실행
- "TSLA 일목균형표 분석" → Step 1, 4 후 analyze_single_expert(expert_name="ichimoku")
- "매크로 환경 분석" → fetch_macro_indicators()만 실행
- "삼성전자(005930.KS) 뉴스 감성 분석" → fetch_news()만 실행

## 5명의 전문가

| 전문가 | 분석 관점 | 핵심 지표 |
|--------|-----------|-----------|
| 추세추종 (TrendFollower) | MA 배열 + 추세 강도 | SMA 5/20/60, ADX, MACD |
| 가치분석 (ValueAnalyst) | 섹터별 밸류에이션 | PBR, EPS, 부채비율, 52주 범위 |
| 모멘텀 (MomentumTrader) | 가격/거래량 모멘텀 | RSI, 스토캐스틱, 거래량, 5일 수익률 |
| 역발상 (ContrarianExpert) | 극단 반전 포착 | BB %B, RSI 극단, 거래량 클라이맥스 |
| 일목균형표 (IchimokuExpert) | 구름 + 빗각이론 | 구름, TK크로스, 빗각, 3분할 전략 |

## 동적 가중치

시장 상태에 따라 전문가별 가중치가 자동 조정됩니다:
- **ADX > 30** (강한 추세): 추세추종 + 일목 가중치 1.5배
- **ADX < 20** (횡보): 가치분석 가중치 1.5배
- **VIX > 25** (고변동): 역발상 가중치 1.5배

## 필요 MCP 서버

아래 4개 MCP 서버가 Claude Desktop config에 등록되어야 합니다:

```json
{
  "mcpServers": {
    "stock-data-collector": {
      "command": "python",
      "args": ["/path/to/Stock_Analysis/mcp_servers/stock_data_mcp.py"]
    },
    "technical-analysis": {
      "command": "python",
      "args": ["/path/to/Stock_Analysis/mcp_servers/technical_analysis_mcp.py"]
    },
    "expert-analysis": {
      "command": "python",
      "args": ["/path/to/Stock_Analysis/mcp_servers/expert_analysis_mcp.py"]
    },
    "stock-report": {
      "command": "python",
      "args": ["/path/to/Stock_Analysis/mcp_servers/stock_report_mcp.py"]
    }
  }
}
```

## 한국 종목 지원

한국 종목 코드 (.KS, .KQ)를 자동 감지하여:
- 네이버 금융 뉴스 폴백
- 네이버 리서치 애널리스트 폴백
- 한국 시장 시간 기반 캐시 TTL 조정

예: `005930.KS` (삼성전자), `065450.KQ` (빅텐테크놀로지)

## 참고사항

- 모든 데이터는 yfinance API 기반이며, 실시간 데이터가 아닌 지연 데이터입니다
- 본 분석은 투자 판단의 참고자료이며, 투자 결정의 책임은 사용자에게 있습니다
- 캐시 TTL은 시장 개장/폐장 시간에 따라 자동 조정됩니다
