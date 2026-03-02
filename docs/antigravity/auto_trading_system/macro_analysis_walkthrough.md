# Stock & Coin Analyst - Walkthrough

## Quick Start
```bash
cd src && python3 analyze_stock.py SMR
```

---

## 🚀 analyze_stock.py (NEW)
**4 Skills 통합 분석 CLI 도구**

### Usage
```bash
python3 analyze_stock.py <SYMBOL>

# Examples
python3 analyze_stock.py SMR     # NuScale Power
python3 analyze_stock.py AAPL    # Apple
python3 analyze_stock.py NVDA    # NVIDIA
```

### Output Structure
```
📰 SKILL 1: 뉴스 수집
  - SMR 관련 뉴스 5건

🌍 SKILL 2: 거시경제 분석
  🎯 Market Sentiment: RISK-OFF
  📈 S&P500: 중립 (50%)
  🔴 NASDAQ: 하락 (60%)
  🟢 Bond (TLT): 상승 (60%)
  🟢 Gold: 상승 (60%)

📊 SKILL 3 & 4: 기술적 분석 + 전문가 전략
  🎓 Alan Farley: HOLD
  🎓 Jesse Livermore: HOLD
  🎓 Nicolas Darvas: HOLD
  🎓 BNF: HOLD

🎯 CONSENSUS DECISION: HOLD
  📥 진입가: $17.53
  🎯 목표가: $19.65 (+12.1%)
  🛑 손절가: $16.83 (-4.0%)
```

---

## 📁 Key Files
| File | Description |
|------|-------------|
| `analyze_stock.py` | 4 Skills 통합 분석 CLI |
| `main_system.py` | 키워드 기반 분석 (테마) |
| `macro_agent/macro_analyzer.py` | 거시경제 상관관계 + 예측 |
| `macro_agent/macro_news_collector.py` | 뉴스 컨텍스트 수집 |
| `expert_agent/strategies/*.py` | 전문가 4인 전략 |

---

## Run Commands
```bash
# 개별 종목 분석 (추천)
cd src && python3 analyze_stock.py SMR

# 키워드/테마 분석
cd src && python3 main_system.py
```
