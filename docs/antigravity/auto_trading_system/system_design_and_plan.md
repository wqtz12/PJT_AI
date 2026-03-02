# Stock & Coin Automatic Trading System - System Design & Development Plan (v2)

## 1. Project Overview
**Objective**: Build an autonomous trading agent that analyzes news and market themes to execute trades based on expert swing trading strategies.
**Core Workflow**: News Scraping -> Theme Analysis -> Stock Selection -> Chart Analysis -> LLM Expert Decision -> Auto Execution.

## 2. Technology Stack
-   **Analysis & Agent**: specialized "Skills" (Nodriver for scraping), LLM (Gemini/Claude)
-   **Frontend**: Next.js (React), Tailwind CSS
-   **Backend**: Node.js (Express)
-   **Database**: Firebase (Firestore - Themes/Stocks/Signals, Realtime DB - Live Status)
-   **Infra**: Cloud Functions / Cloud Run

## 3. System Architecture & Process Workflow

### 3.1 The 8-Step Pipeline
1.  **News Analysis (Nodriver)**:
    -   Scrape Naver Finance, US Markets (CNBC/Bloomberg/Yahoo free tiers).
    -   Tool: `nodriver` (browser automation) + LLM Summarizer.
2.  **Theme Extraction**:
    -   Analyze news content to identify trending themes (e.g., "AI Semiconductors", "Superconductors").
    -   Output: List of Themes with Relevance Score.
3.  **Theme Storage**:
    -   DB Schema: `themes/{date}/{rank}`.
4.  **Stock Mapping**:
    -   Search related companies for each theme.
    -   Mapping: Theme -> [Stock A, Stock B, Stock C].
5.  **Multi-Timeframe Data Collection**:
    -   Fetch Daily/Weekly/Monthly candles for mapped stocks.
    -   Calculate indicators (MA, Bollinger, Volume) required for Expert MCPs.
6.  **LLM Expert Analysis**:
    -   **Input**: News Summary + Theme Strength + Chart Data (Technicals).
    -   **Persona**: Swing Trading Expert (Farley, Livermore, etc.).
    -   **Output**: Buy Price, Sell Price, Stop-loss, Confidence.
7.  **Auto Execution**:
    -   Execute orders via Broker/Exchange API.
8.  **Agentization**:
    -   Modules are wrapped as autonomous agents (Watcher, Analyst, Trader).

### 3.2 High-Level Architecture
```mermaid
graph TD
    News[News Sources] -->|Nodriver| Scraper[News Scraper Agent]
    Scraper -->|Text| ThemeAgent[Theme Analyst Agent]
    ThemeAgent -->|Themes| DB[(Firebase)]
    
    DB -->|Trigger| StockMapper[Stock Mapping Agent]
    StockMapper -->|Stock List| DataCollector[Data Collector]
    DataCollector -->|Candles/Technicals| AnalysisAgent[LLM Expert Analyst]
    
    AnalysisAgent -->|Signal (Buy/Sell Prices)| Trader[Execution Agent]
    Trader -->|API| Exchange[Stock/Coin Exchange]
    
    User -->|Monitor| Dashboard[Next.js Dashboard]
```

## 4. Database Schema (Firebase)

-   **`daily_themes`**
    -   `date`: YYYY-MM-DD
    -   `themes`: [{ name: "AI", rank: 1, related_stocks: ["005930", "000660"] }]
-   **`analyzed_stocks`**
    -   `stock_code`: "005930"
    -   `theme`: "AI"
    -   `analysis`: { expert_opinion: "Strong Buy", buy_price: 70000, sell_price: 75000 }
-   **`trade_signals`**
    -   `status`: "PENDING" | "EXECUTED"
    -   `details`: Order payload.

## 5. Development Plan

### Phase 1: Foundation (Weeks 1-2)
-   [ ] **Project Setup**: Next.js & Express repo setup.
-   [ ] **Database**: Firebase configuration for new schema.
-   [ ] **Agent Core**: Set up basic LangChain/Agent builder structure.

### Phase 2: News & Theme Engine (Weeks 3-4)
-   [ ] **Skill: Nodriver**: Implement safe news scraper.
-   [ ] **Theme Analyzer**: LLM prompt for "News -> Theme" conversion.
-   [ ] **Theme DB**: Workflow to save daily themes.

### Phase 3: Market Data & Mapping (Weeks 5-6)
-   [ ] **Stock Mapper**: Logic to find stocks by keyword (Theme).
-   [ ] **Data Fetcher**: Connect to Stock API (KIS/Upbit) to get D/W/M candles.
-   [ ] **Technical Calc**: Add library for MA, RSI, MACD.

### Phase 4: Expert Agent (Weeks 7-8)
-   [ ] **Prompt Engineering**: Create "Expert Persona" prompts (Farley/Livermore).
-   [ ] **Integration**: Feed News + Chart Data -> LLM -> JSON Decision.

### Phase 5: Execution & System (Week 9+)
-   [ ] **Auto Trader**: API connection for real orders.
-   [ ] **Agent Loop**: Automate the 1-8 steps to run daily/hourly.
-   [ ] **Dashboard**: UI to view Today's Themes & Signals.

## 6. Coding & Convention Rules
-   **Style**: Airbnb ESLint.
-   **Agent**: Modular design (Single Responsibility).
-   **Scraping**: Respect `robots.txt` where possible, rate limiting.
