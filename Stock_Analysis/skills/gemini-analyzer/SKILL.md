---
name: gemini-analyzer
description: Gemini 전용 분석 워크플로우. Claude가 수집한 데이터를 읽어 기술적/전문가 분석, 리포트, 차트를 생성합니다.
---

# Gemini Analyzer (분석 & 리포트 파이프라인)

Gemini가 실행하는 Phase 2~4 분석 전담 워크플로우입니다.
`data/` 디렉토리의 JSON 파일을 읽어 분석을 수행합니다.

## 전제 조건

`handoff/data_ready_{TICKER}.json` 파일이 존재해야 합니다.
이 파일은 Claude가 Phase 1 데이터 수집을 완료했다는 시그널입니다.

## 종합 분석 워크플로우

```
Step 0: 데이터 준비 확인
  data_ready = handoff/data_ready_{TICKER}.json 확인
  → 없으면: "Claude에게 데이터 수집을 요청하세요" 안내

Step 1: [technical-analysis] Phase 2 - 기술적 분석
  stock_data = data/{TICKER}_stock_data.json 읽기
  → data_id가 있으면: run_full_analysis(data_id=...)
  → 없으면: run_full_analysis(ohlcv_json=stock_data)
  → analysis_id 획득

Step 2: [technical-analysis] 매매 신호 생성
  generate_signals(analysis_id=...)

Step 3: [expert-analysis] Phase 3 - 5전문가 분석
  company_info = data/{TICKER}_company_info.json 읽기
  news = data/{TICKER}_news.json 읽기
  macro = data/macro_indicators.json 읽기
  
  sentiment_json = news의 sentiment_summary 부분 추출
  
  analyze_all_experts(
    analysis_json,
    company_info_json,
    macro_json=macro,
    sentiment_json=sentiment_json
  )

Step 4: [expert-analysis] Phase 4 - 리스크 분석 (선택)
  run_backtest(analysis_json)
  compute_var(analysis_json)
  compute_risk_metrics(analysis_json)

Step 5: [stock-report] 차트 & 리포트 생성
  generate_all_charts(analysis_json, ticker)
  generate_text_report(ticker, company_info_json, analysis_json, signals_json)
```

## 에러 발생 시 핸드오프

분석 도구 실행 중 에러 발생 시:

1. `handoff/error_task_{TICKER}.json` 생성
   - 실패 단계, 컴포넌트, 도구, 에러 메시지, 스택 트레이스 기록
2. Claude에게 수정 요청 메시지 전달
3. `handoff/resolution_{TICKER}.json` 확인 후 파이프라인 재개

## 에러 태스크 작성 규칙

```json
{
  "status": "ERROR",
  "ticker": "NVDA",
  "phase": "Phase 2 - Technical Analysis",
  "component": "technical-analysis",
  "tool_name": "run_full_analysis",
  "error": {
    "message": "KeyError: 'Close'",
    "traceback": "... (full traceback) ..."
  },
  "input_params": { "data_id": "abc123" },
  "expected_output": "analysis_id와 14개 기술적 지표",
  "suggested_fix": "data_fetcher.py의 컬럼명 매핑 확인 필요"
}
```

## 필요 MCP 서버

- **technical-analysis** (필수): `run_full_analysis`, `generate_signals`
- **expert-analysis** (필수): `analyze_all_experts`, `run_backtest`, `compute_var`
- **stock-report** (선택): `generate_all_charts`, `generate_text_report`
