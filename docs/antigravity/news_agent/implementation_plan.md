# Phase 6: Stock Price Data + Expert Strategies

주가 데이터 연동 및 4명의 전문가 매매기법 구현 계획입니다.

## 전문가별 핵심 전략

### 1. Alan Farley (스윙 트레이딩)
| 지표 | 사용법 |
|------|--------|
| RSI (14) | 과매도 (<30) 매수, 과매수 (>70) 매도 |
| MACD | 시그널 크로스로 추세 전환 감지 |
| 50 EMA | 지지/저항선, 가격 위치 확인 |
| Fibonacci | 38.2%, 50%, 61.8% 되돌림 레벨 |
| Volume | 돌파 시 거래량 확인 |

### 2. Jesse Livermore (피벗 포인트)
| 전략 | 설명 |
|------|------|
| Pivot Point | 신고가 돌파 시 매수 |
| Breakout | 저항선 돌파 + 거래량 증가 |
| Trend Following | 추세 방향으로만 매매 |
| Cut Loss | -5~7% 손절 엄수 |

### 3. Nicolas Darvas (박스 이론)
| 전략 | 설명 |
|------|------|
| 52주 신고가 | 모멘텀 종목 필터링 |
| Box 형성 | 3일간 신고가 미갱신 시 박스 상단 |
| Breakout | 박스 상단 돌파 + 거래량 매수 |
| Stop Loss | 박스 하단 이탈 시 매도 |

### 4. BNF - Kotegawa Takashi (패닉 바이)
| 전략 | 설명 |
|------|------|
| 25MA 이격 | 25일선 대비 -20~35% 하락 시 매수 |
| RSI 극단 | RSI 15 이하 과매도 |
| Bollinger | 하단 밴드 터치 시 매수 고려 |
| Buy Panic | 공포에 매수, 안도에 매도 |

---

## Proposed Changes

### [NEW] `stock_data_fetcher.py`
주가 데이터 수집 모듈
- Yahoo Finance (yfinance) 연동
- OHLCV, 이평선, 거래량 계산
- 실시간/일봉 데이터 지원

### [NEW] `technical_indicators.py`
기술적 지표 계산 모듈
- RSI, MACD, SMA/EMA
- Bollinger Bands
- Pivot Points
- Darvas Box

### [NEW] `expert_strategies/`
```
expert_strategies/
├── __init__.py
├── farley_swing.py      # Alan Farley 스윙트레이딩
├── livermore_pivot.py   # Jesse Livermore 피벗포인트
├── darvas_box.py        # Nicolas Darvas 박스이론
└── bnf_panic.py         # BNF 패닉바이
```

### [NEW] `signal_generator.py`
매매 시그널 생성기
- 뉴스 테마 + 기술적 지표 결합
- 전문가 전략별 신호 생성
- 매수/매도 시점 판단

### [NEW] `SKILL_EXPERT_STRATEGIES.md`
스킬 문서화

---

## 데이터 소스

| 소스 | 용도 | 라이브러리 |
|------|------|-----------|
| Yahoo Finance | 미국주식 OHLCV | `yfinance` |
| 네이버 증권 | 한국주식 OHLCV | 웹 스크래핑 |
| Binance | 코인 OHLCV | `python-binance` |

---

## Verification Plan

### 테스트 케이스
1. 주가 데이터 수집 테스트 (NVDA, 삼성전자)
2. 기술적 지표 계산 검증 (RSI, MACD)
3. 각 전략별 시그널 생성 테스트
4. 뉴스 테마 + 기술적 시그널 통합 테스트
