-- ═══════════════════════════════════════════════════════════════
-- Stock Analysis DB Schema
-- PostgreSQL 16 - 초기화 스크립트
-- ═══════════════════════════════════════════════════════════════

-- 1. 분석 세션 레지스트리
CREATE TABLE IF NOT EXISTS analysis_sessions (
    id              VARCHAR(36) PRIMARY KEY,
    session_type    VARCHAR(30) NOT NULL,                -- 'ohlcv', 'full_analysis', 'company_info', 'expert', 'signals', 'macro'
    ticker          VARCHAR(20) NOT NULL,
    interval        VARCHAR(5)  NOT NULL DEFAULT '1d',   -- '1d', '1wk', '1mo'
    period          VARCHAR(10),
    parent_id       VARCHAR(36) REFERENCES analysis_sessions(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE,
    metadata        JSONB DEFAULT '{}',
    status          VARCHAR(10) NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_sessions_ticker ON analysis_sessions(ticker, session_type);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON analysis_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_parent ON analysis_sessions(parent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON analysis_sessions(status) WHERE status = 'active';

-- 2. OHLCV 주가 데이터
CREATE TABLE IF NOT EXISTS stock_ohlcv (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    ticker          VARCHAR(20) NOT NULL,
    interval        VARCHAR(5)  NOT NULL DEFAULT '1d',
    trade_date      DATE NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION NOT NULL,
    volume          BIGINT,
    dividends       DOUBLE PRECISION DEFAULT 0,
    stock_splits    DOUBLE PRECISION DEFAULT 0,

    UNIQUE(ticker, interval, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_session ON stock_ohlcv(session_id);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON stock_ohlcv(ticker, interval, trade_date DESC);

-- 3. 기술적 지표 (34개 컬럼)
CREATE TABLE IF NOT EXISTS technical_indicators (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    ticker          VARCHAR(20) NOT NULL,
    interval        VARCHAR(5)  NOT NULL DEFAULT '1d',
    trade_date      DATE NOT NULL,

    -- OHLCV (조인 편의를 위해 포함)
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          BIGINT,

    -- 이동평균
    sma_5           DOUBLE PRECISION,
    sma_20          DOUBLE PRECISION,
    sma_60          DOUBLE PRECISION,
    sma_120         DOUBLE PRECISION,
    ema_12          DOUBLE PRECISION,
    ema_26          DOUBLE PRECISION,

    -- RSI
    rsi             DOUBLE PRECISION,

    -- MACD
    macd            DOUBLE PRECISION,
    macd_signal     DOUBLE PRECISION,
    macd_hist       DOUBLE PRECISION,

    -- 볼린저밴드
    bb_upper        DOUBLE PRECISION,
    bb_middle       DOUBLE PRECISION,
    bb_lower        DOUBLE PRECISION,
    bb_width        DOUBLE PRECISION,
    bb_pct          DOUBLE PRECISION,

    -- 스토캐스틱
    stoch_k         DOUBLE PRECISION,
    stoch_d         DOUBLE PRECISION,

    -- 변동성 & 추세
    atr             DOUBLE PRECISION,
    adx             DOUBLE PRECISION,
    adx_pos         DOUBLE PRECISION,
    adx_neg         DOUBLE PRECISION,

    -- 거래량
    obv             DOUBLE PRECISION,

    -- 일목균형표
    ichimoku_tenkan         DOUBLE PRECISION,
    ichimoku_kijun          DOUBLE PRECISION,
    ichimoku_senkou_a       DOUBLE PRECISION,
    ichimoku_senkou_b       DOUBLE PRECISION,
    ichimoku_chikou         DOUBLE PRECISION,
    ichimoku_cloud_top      DOUBLE PRECISION,
    ichimoku_cloud_bottom   DOUBLE PRECISION,
    ichimoku_tenkan_angle   DOUBLE PRECISION,
    ichimoku_kijun_angle    DOUBLE PRECISION,
    ichimoku_senkou_a_angle DOUBLE PRECISION,

    UNIQUE(session_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_ti_session ON technical_indicators(session_id);
CREATE INDEX IF NOT EXISTS idx_ti_ticker_date ON technical_indicators(ticker, interval, trade_date DESC);

-- 4. 기업 기본 정보
CREATE TABLE IF NOT EXISTS company_info (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    ticker          VARCHAR(20) NOT NULL,
    fetched_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    name            VARCHAR(200),
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    market_cap      BIGINT,
    week_52_high    DOUBLE PRECISION,
    week_52_low     DOUBLE PRECISION,
    per             DOUBLE PRECISION,
    pbr             DOUBLE PRECISION,
    eps             DOUBLE PRECISION,
    dividend_yield  DOUBLE PRECISION,
    beta            DOUBLE PRECISION,
    analyst_target  DOUBLE PRECISION,
    recommendation  VARCHAR(30),
    total_revenue   BIGINT,
    operating_income BIGINT,
    debt_to_equity  DOUBLE PRECISION,
    total_cash      BIGINT,
    raw_json        JSONB
);

CREATE INDEX IF NOT EXISTS idx_ci_session ON company_info(session_id);
CREATE INDEX IF NOT EXISTS idx_ci_ticker ON company_info(ticker, fetched_at DESC);

-- 5. 전문가 분석 결과
CREATE TABLE IF NOT EXISTS expert_opinions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    analysis_id     VARCHAR(36) REFERENCES analysis_sessions(id),
    ticker          VARCHAR(20) NOT NULL,
    expert_name     VARCHAR(50) NOT NULL,
    expert_style    VARCHAR(100),
    position        VARCHAR(10) NOT NULL,
    confidence      DOUBLE PRECISION,
    buy_price       DOUBLE PRECISION,
    sell_price      DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    rationale       TEXT,
    key_indicators  JSONB,
    buy_prices      JSONB,
    sell_prices     JSONB,
    aggregated      JSONB,
    filters_applied JSONB
);

CREATE INDEX IF NOT EXISTS idx_eo_session ON expert_opinions(session_id);
CREATE INDEX IF NOT EXISTS idx_eo_analysis ON expert_opinions(analysis_id);

-- 6. 매크로 경제 지표
CREATE TABLE IF NOT EXISTS macro_indicators (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    fetched_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    indicator_key   VARCHAR(30) NOT NULL,
    indicator_name  VARCHAR(100),
    current_value   DOUBLE PRECISION,
    change_pct      DOUBLE PRECISION,
    sma_20          DOUBLE PRECISION,
    trend           VARCHAR(20),
    raw_json        JSONB
);

CREATE INDEX IF NOT EXISTS idx_macro_session ON macro_indicators(session_id);
CREATE INDEX IF NOT EXISTS idx_macro_key ON macro_indicators(indicator_key, fetched_at DESC);

-- 7. 뉴스 감성 분석
CREATE TABLE IF NOT EXISTS news_sentiment (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    ticker          VARCHAR(20) NOT NULL,
    fetched_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    title           TEXT,
    source          VARCHAR(200),
    url             TEXT,
    published       VARCHAR(50),
    summary         TEXT,
    sentiment       VARCHAR(20),
    relevance       DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_news_session ON news_sentiment(session_id);
CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_sentiment(ticker, fetched_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- 뷰: 최신 분석 세션 (종목별)
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE VIEW v_latest_analysis AS
SELECT DISTINCT ON (ticker, interval)
    s.id AS session_id,
    s.ticker,
    s.interval,
    s.period,
    s.created_at,
    s.metadata
FROM analysis_sessions s
WHERE s.session_type = 'full_analysis'
AND s.status = 'active'
ORDER BY s.ticker, s.interval, s.created_at DESC;

-- 뷰: 최신 지표값 (세션별 마지막 행)
CREATE OR REPLACE VIEW v_latest_indicators AS
SELECT DISTINCT ON (ti.session_id)
    ti.*
FROM technical_indicators ti
JOIN analysis_sessions s ON ti.session_id = s.id
WHERE s.status = 'active'
ORDER BY ti.session_id, ti.trade_date DESC;

-- ═══════════════════════════════════════════════════════════════
-- 만료 세션 정리 함수
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION cleanup_expired_sessions() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    WITH expired AS (
        UPDATE analysis_sessions
        SET status = 'expired'
        WHERE status = 'active'
        AND expires_at IS NOT NULL
        AND expires_at < NOW()
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_count FROM expired;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
