---
name: expert-technique-analysis
description: 5명의 전문가별 투자 기법을 개별 분석하고, 유명 투자자 원칙 기반 심층 해석을 제공합니다.
---

# 🎯 Expert Technique Analysis (전문가별 투자 기법 분석)

각 전문가의 투자 기법을 **유명 투자자 원칙** 관점에서 심층 분석합니다.
종합 분석(stock-analyzer)에서 각 전문가가 어떤 근거로 판단했는지,
그 기법이 어떤 투자 철학에 기반하는지 상세 해석을 제공합니다.

## 사용 방법

사용자: "NVDA 전문가별 기법 분석해줘" 또는 "TSLA 투자 기법 분석"

```
Step 1: 데이터 수집 (병렬)
  [stock-data-collector] fetch_stock_data(ticker, period="6mo") → data_id
  [stock-data-collector] fetch_company_info(ticker) → company_info
  [stock-data-collector] fetch_news(ticker) → news (sentiment)
  [stock-data-collector] fetch_macro_indicators() → macro

Step 2: 기술적 분석
  [technical-analysis] run_full_analysis(data_id) → analysis_id

Step 3: 개별 전문가 분석 (5회)
  [expert-analysis] analyze_single_expert(analysis_json, company_info_json, expert_name="trend")
  [expert-analysis] analyze_single_expert(..., expert_name="value")
  [expert-analysis] analyze_single_expert(..., expert_name="momentum")
  [expert-analysis] analyze_single_expert(..., expert_name="contrarian")
  [expert-analysis] analyze_single_expert(..., expert_name="ichimoku")

Step 4: 전문가별 기법 해석 리포트 생성
  → 각 전문가의 점수 구성, 핵심 근거, 관련 투자자 원칙을 정리
```

## 5전문가 × 투자자 원칙 매핑

### 1. 추세추종 전문가 → Jesse Livermore + 거래량 확인

| 분석 요소 | Livermore 원칙 | 구현 |
|-----------|---------------|------|
| MA 정배열 (5>20>60) | Pivotal Point 돌파 | SMA 배열 판정 ±3 |
| 거래량 확인 돌파 | 진짜 돌파 vs 가짜 돌파 | Volume/SMA20 비율 ±1 |
| ADX 추세 강도 | 추세가 있을 때만 진입 | ADX>30 강한 추세 ±2 |
| MACD 크로스 | 모멘텀 전환 확인 | 골든/데드 크로스 ±2 |
| VIX 연동 | 시장 환경 감안 | VIX 고변동시 추세 신뢰도 감점 |

**해석 가이드**:
- score >= 6: Livermore가 말한 "확신을 가지고 진입할 타이밍"
- score 3~5: 진입 가능하나 분할 매수 권장
- 거래량 부족 감점: "거래량 없는 돌파는 진짜 돌파가 아니다"

### 2. 가치분석 전문가 → Warren Buffett + Peter Lynch

| 분석 요소 | 투자자 원칙 | 구현 |
|-----------|-----------|------|
| ROE > 15% | Buffett: 지속 가능한 경쟁우위 | ROE 구간별 ±2 |
| PEG < 1.0 | Lynch: 성장 대비 저평가 | PEG 구간별 ±2 |
| 영업이익률 > 25% | Buffett: 경제적 해자 프록시 | 마진 구간별 ±1 |
| PBR 섹터 조정 | Buffett: 적정 가치 | 섹터별 기준 ±2 |
| 52주 위치 | Lynch: 하락한 우량주 매수 기회 | 범위별 ±3 |
| 부채비율 | Buffett: 재무 건전성 | 섹터별 기준 ±1 |
| 목표가 괴리율 | 시장 컨센서스 대비 | 상승여력별 ±2 |

**해석 가이드**:
- ROE 20%+ & PEG < 1.0: "Buffett이 좋아할 종목" - 지속 가능한 고수익 + 저평가
- ROE 높은데 PBR 높음: "이미 시장이 해자를 인식" - 적정 가격인지 확인
- PEG > 3.0 & 영업이익률 < 5%: "Lynch 기준 고평가 + 해자 약함" - 매도 고려

### 3. 모멘텀 트레이더 → William O'Neil (CANSLIM) + 상대강도

| 분석 요소 | O'Neil 원칙 | 구현 |
|-----------|-----------|------|
| 상대강도 RS | L: Leader vs Laggard | 종목 vs S&P500 20일 수익률 ±2 |
| RSI 모멘텀 | 가격 모멘텀 추적 | RSI 구간별 ±2 |
| 거래량 급증 | S: Supply & Demand | Volume/SMA20 비율 ±2 |
| 스토캐스틱 크로스 | 단기 전환점 | %K/%D 크로스 ±2 |
| OBV 추세 | 매집/분산 판별 | OBV 10일 변화 ±1 |
| S&P500 동조 | M: Market Direction | 시장 방향 ±1 |

**해석 가이드**:
- RS 시장 대비 +5%p 이상: "O'Neil의 'Leader 종목'" - 시장을 이기는 종목
- RS 시장 대비 -5%p 이하: "Laggard 종목" - 모멘텀 전략 부적합
- 거래량 급증 + RSI 60~75: "기관 매집 구간" 가능성

### 4. 역발상 전문가 → Howard Marks + 시장 사이클

| 분석 요소 | Marks 원칙 | 구현 |
|-----------|-----------|------|
| BB %B 극단 | 통계적 이상치 반전 | %B < 0 or > 1 → ±3 |
| RSI 극단 + ADX | 2차 사고 (추세 vs 반전) | RSI < 25/> 75 + ADX 체크 ±3 |
| 연속 하락일 | 공포 극대화 지점 | 4일+ 연속 하락 ±2 |
| 52주 저점 근접 | 최악이 이미 반영된 구간 | 52주 하위 25% ±2 |
| VIX 극단 | 시장 공포/탐욕 지표 | VIX > 35 역발상 매수 ±2 |
| 극단 감성 | 컨센서스 역행 | 극단 부정 → 매수, 극단 긍정 → 매도 ±1 |

**해석 가이드**:
- BB %B < 0 + RSI < 25 + ADX < 25: "Marks의 이상적 역발상 매수" - 과매도 + 추세 약화
- BB %B < 0 + RSI < 25 + ADX > 30: "추세적 하락 중" - 역발상 매수 주의 (감점)
- VIX > 35 + 연속 하락: "공포 극대화" - 역발상 전문가의 핵심 기회 구간

### 5. 일목균형표 전문가 → 一目山人 원전 + 삼역호전

| 분석 요소 | 원전 원칙 | 구현 |
|-----------|----------|------|
| 구름 위/아래 | 수준론 기반 추세 판단 | 구름 위치 ±3 |
| TK 크로스 | 전환선-기준선 관계 | 골든/데드 ±2 |
| 후행스팬 | 26일전 대비 확인 | 현재가 vs 26일전 ±1 |
| 삼역호전 | 3조건 동시 충족 = 최강 | 구름위+TK매수+후행확인 → +3 보너스 |
| 삼역역전 | 3조건 동시 충족 = 최약 | 구름아래+TK매도+후행확인 → -3 보너스 |
| 전환선 빗각 | 빗각이론 추세 강도 | 각도별 ±2 |
| 기준선 빗각 | 중기 추세 방향 | 강한 각도 ±1 |

**해석 가이드**:
- 삼역호전 발생: "원전에서 가장 강한 매수 신호" - 모든 시간축 정렬
- 삼역역전 발생: "원전에서 가장 강한 매도 신호" - 전면 하락
- 구름 내부: "전환 임박" - 방향성 확인 후 진입 필요

## 시장 사이클 판별 (Howard Marks)

집계 단계에서 시장 전체 환경을 판별합니다:

| 사이클 | 조건 | 영향 |
|--------|------|------|
| 강세장 | VIX<15 + 금리하락 + S&P500 상승 | 추세/모멘텀 강화 |
| 보통 | 중립 환경 | 기본 가중치 |
| 주의 | VIX 상승 또는 금리 상승 | 확신도 주의 |
| 약세장 | VIX>35 + 금리상승 + S&P500 하락 | 매수 확신도 -10 감점 |

## 출력 형식

```
🎯 NVDA 전문가별 투자 기법 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 현재가: $142.50 | 시장 사이클: 보통
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 추세추종 (Livermore) → 매수 | 확신도 78%
   핵심: 정배열(5>20>60) + 거래량 2.1x 급증 = "진짜 돌파"
   점수: MA+3, Vol+1, ADX+2, MACD+2 = 총 +8

2️⃣ 가치분석 (Buffett/Lynch) → 홀드 | 확신도 45%
   핵심: ROE 28% (탁월) + PEG 2.8 (성장 대비 고평가)
   점수: 52주+1, PBR-1, ROE+2, PEG-1, EPS+2, 마진+1 = 총 +4

3️⃣ 모멘텀 (O'Neil CANSLIM) → 매수 | 확신도 71%
   핵심: 상대강도 S&P대비 +12%p (Leader)
   점수: RSI+2, Vol+2, RS+2, OBV+1 = 총 +7

4️⃣ 역발상 (Howard Marks) → 홀드 | 확신도 40%
   핵심: BB 중립, RSI 정상 범위 → 역발상 기회 아님
   점수: BB 0, RSI 0, VIX 0 = 총 0

5️⃣ 일목균형표 (一目山人) → 매수 | 확신도 85%
   핵심: ★ 삼역호전 발생 → 최강 매수 신호
   점수: 구름+3, TK+2, 후행+1, 삼역+3, 빗각+2 = 총 +11
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 투자자 원칙 종합:
- Livermore: 거래량 확인된 돌파 → 진입 적기
- Buffett: ROE 우수하나 밸류에이션 부담
- O'Neil: 시장 대비 강한 상대강도 → Leader 종목
- Marks: 역발상 기회 아님 (정상 구간)
- 一目山人: 삼역호전 = 가장 강한 매수 신호
```

## 부분 분석

특정 전문가만 분석할 수도 있습니다:

- "NVDA 추세추종 기법 분석" → analyze_single_expert(expert_name="trend")만
- "AAPL Buffett 관점 분석" → analyze_single_expert(expert_name="value")만
- "TSLA 일목 삼역호전 확인" → analyze_single_expert(expert_name="ichimoku")만

## 필요 MCP 서버

- stock-data-collector (필수)
- technical-analysis (필수)
- expert-analysis (필수)
