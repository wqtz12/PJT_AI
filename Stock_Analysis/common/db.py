"""
PostgreSQL 데이터베이스 연결 및 Peewee ORM 모델
- psycopg3 + Peewee playhouse.psycopg3_ext
- 프로세스별 싱글턴 DB 연결
- 세션 기반 데이터 관리 (UUID)

사용법:
    from common.db import is_db_available, get_db, create_session
    from common.db import (
        AnalysisSession, StockOHLCV, TechnicalIndicator,
        CompanyInfoRow, ExpertOpinionRow, MacroIndicatorRow, NewsSentimentRow,
    )

    if is_db_available():
        session_id = create_session("ohlcv", "005930.KS", period="6mo")
        # ... 데이터 저장 ...
"""
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# DB 연결 설정
# ═══════════════════════════════════════════════════════════════

_db_instance = None
_db_available = None  # None = 미검사, True/False = 캐시

# Peewee 모델을 위한 지연 임포트
_peewee_imported = False
_pw = None  # peewee 모듈 참조
_Model = None  # BaseModel 클래스


def _get_db_config() -> dict:
    """DB 연결 설정 로드 (config.yaml > 환경변수 > 기본값)"""
    try:
        from common.config import get_config
        cfg = get_config().get("database", {})
    except Exception:
        cfg = {}

    return {
        "host": cfg.get("host") or os.environ.get("DB_HOST", "localhost"),
        "port": int(cfg.get("port") or os.environ.get("DB_PORT", "5432")),
        "database": cfg.get("name") or os.environ.get("DB_NAME", "stock_analysis"),
        "user": cfg.get("user") or os.environ.get("DB_USER", "stock_user"),
        "password": cfg.get("password") or os.environ.get("DB_PASSWORD", "stock_pass_dev_2024"),
    }


def _is_db_enabled() -> bool:
    """config에서 DB 사용 여부 확인"""
    try:
        from common.config import get_config
        cfg = get_config().get("database", {})
        return cfg.get("enabled", True)
    except Exception:
        return True


def get_db():
    """
    Psycopg3Database 싱글턴 반환

    Returns:
        Psycopg3Database 인스턴스 또는 None (DB 불가 시)
    """
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    if not _is_db_enabled():
        logger.info("DB 비활성화 (config.database.enabled=false)")
        return None

    try:
        from playhouse.psycopg3_ext import Psycopg3Database
    except ImportError:
        logger.warning("playhouse.psycopg3_ext 미설치 → DB 비활성화")
        return None

    try:
        config = _get_db_config()
        _db_instance = Psycopg3Database(
            config["database"],
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            autoconnect=False,
        )
        # 연결 테스트
        _db_instance.connect()
        _db_instance.close()
        logger.info(f"DB 연결 성공: {config['host']}:{config['port']}/{config['database']}")
        return _db_instance
    except Exception as e:
        logger.warning(f"DB 연결 실패: {e} → JSON 폴백 모드")
        _db_instance = None
        return None


def is_db_available() -> bool:
    """
    DB 사용 가능 여부 (캐시됨, 프로세스 수명 동안 유지)

    Returns:
        bool: True=DB 사용 가능, False=JSON 폴백
    """
    global _db_available

    if _db_available is not None:
        return _db_available

    db = get_db()
    _db_available = db is not None
    return _db_available


def reset_db_state():
    """DB 상태 리셋 (테스트용)"""
    global _db_instance, _db_available
    if _db_instance is not None:
        try:
            if not _db_instance.is_closed():
                _db_instance.close()
        except Exception:
            pass
    _db_instance = None
    _db_available = None


# ═══════════════════════════════════════════════════════════════
# Peewee ORM 모델 정의
# ═══════════════════════════════════════════════════════════════

def _ensure_peewee():
    """Peewee 모듈 지연 임포트"""
    global _peewee_imported, _pw, _Model

    if _peewee_imported:
        return

    import peewee as pw_mod
    _pw = pw_mod
    _peewee_imported = True

    # DB 프록시 (실제 DB 바인딩은 나중에)
    db_proxy = pw_mod.DatabaseProxy()

    class BaseModel(pw_mod.Model):
        class Meta:
            database = db_proxy

    _Model = BaseModel


def _bind_models():
    """모델에 실제 DB 바인딩"""
    _ensure_peewee()
    db = get_db()
    if db is None:
        return False

    # 모든 모델의 Meta.database에 실제 DB 바인딩
    _Model._meta.database.initialize(db)
    return True


# ─── 세션 레지스트리 ───
class AnalysisSession:
    """분석 세션 (analysis_sessions 테이블)"""
    pass


class StockOHLCV:
    """OHLCV 주가 데이터 (stock_ohlcv 테이블)"""
    pass


class TechnicalIndicator:
    """기술적 지표 (technical_indicators 테이블)"""
    pass


class CompanyInfoRow:
    """기업 기본 정보 (company_info 테이블)"""
    pass


class ExpertOpinionRow:
    """전문가 분석 결과 (expert_opinions 테이블)"""
    pass


class MacroIndicatorRow:
    """매크로 경제 지표 (macro_indicators 테이블)"""
    pass


class NewsSentimentRow:
    """뉴스 감성 분석 (news_sentiment 테이블)"""
    pass


def _define_models():
    """
    Peewee 모델 정의 (지연 초기화)
    SQL 스키마(001_create_schema.sql)와 1:1 매핑
    """
    _ensure_peewee()
    pw = _pw
    Base = _Model

    # JSONB 필드: psycopg3가 dict/list ↔ JSONB 자동 변환
    try:
        from playhouse.psycopg3_ext import BinaryJSONField as _JSONB
    except ImportError:
        _JSONB = pw.TextField  # 폴백: TextField 사용

    # ─── 1. analysis_sessions ───
    class _AnalysisSession(Base):
        id = pw.CharField(primary_key=True, max_length=36)
        session_type = pw.CharField(max_length=30)
        ticker = pw.CharField(max_length=20)
        interval = pw.CharField(max_length=5, default="1d")
        period = pw.CharField(max_length=10, null=True)
        parent_id = pw.ForeignKeyField("self", column_name="parent_id",
                                        null=True, backref="children",
                                        on_delete="SET NULL")
        created_at = pw.DateTimeField(default=datetime.now)
        expires_at = pw.DateTimeField(null=True)
        metadata = _JSONB(default={})  # JSONB
        status = pw.CharField(max_length=10, default="active")

        class Meta:
            table_name = "analysis_sessions"

    # ─── 2. stock_ohlcv ───
    class _StockOHLCV(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="ohlcv_rows", on_delete="CASCADE")
        ticker = pw.CharField(max_length=20)
        interval = pw.CharField(max_length=5, default="1d")
        trade_date = pw.DateField()
        open = pw.DoubleField(null=True)
        high = pw.DoubleField(null=True)
        low = pw.DoubleField(null=True)
        close = pw.DoubleField()
        volume = pw.BigIntegerField(null=True)
        dividends = pw.DoubleField(default=0)
        stock_splits = pw.DoubleField(default=0)

        class Meta:
            table_name = "stock_ohlcv"
            indexes = (
                (("ticker", "interval", "trade_date"), True),  # UNIQUE
            )

    # ─── 3. technical_indicators ───
    class _TechnicalIndicator(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="indicator_rows", on_delete="CASCADE")
        ticker = pw.CharField(max_length=20)
        interval = pw.CharField(max_length=5, default="1d")
        trade_date = pw.DateField()
        # OHLCV
        open = pw.DoubleField(null=True)
        high = pw.DoubleField(null=True)
        low = pw.DoubleField(null=True)
        close = pw.DoubleField(null=True)
        volume = pw.BigIntegerField(null=True)
        # 이동평균
        sma_5 = pw.DoubleField(null=True)
        sma_20 = pw.DoubleField(null=True)
        sma_60 = pw.DoubleField(null=True)
        sma_120 = pw.DoubleField(null=True)
        ema_12 = pw.DoubleField(null=True)
        ema_26 = pw.DoubleField(null=True)
        # RSI
        rsi = pw.DoubleField(null=True)
        # MACD
        macd = pw.DoubleField(null=True)
        macd_signal = pw.DoubleField(null=True)
        macd_hist = pw.DoubleField(null=True)
        # 볼린저밴드
        bb_upper = pw.DoubleField(null=True)
        bb_middle = pw.DoubleField(null=True)
        bb_lower = pw.DoubleField(null=True)
        bb_width = pw.DoubleField(null=True)
        bb_pct = pw.DoubleField(null=True)
        # 스토캐스틱
        stoch_k = pw.DoubleField(null=True)
        stoch_d = pw.DoubleField(null=True)
        # 변동성 & 추세
        atr = pw.DoubleField(null=True)
        adx = pw.DoubleField(null=True)
        adx_pos = pw.DoubleField(null=True)
        adx_neg = pw.DoubleField(null=True)
        # 거래량
        obv = pw.DoubleField(null=True)
        # 일목균형표
        ichimoku_tenkan = pw.DoubleField(null=True)
        ichimoku_kijun = pw.DoubleField(null=True)
        ichimoku_senkou_a = pw.DoubleField(null=True)
        ichimoku_senkou_b = pw.DoubleField(null=True)
        ichimoku_chikou = pw.DoubleField(null=True)
        ichimoku_cloud_top = pw.DoubleField(null=True)
        ichimoku_cloud_bottom = pw.DoubleField(null=True)
        ichimoku_tenkan_angle = pw.DoubleField(null=True)
        ichimoku_kijun_angle = pw.DoubleField(null=True)
        ichimoku_senkou_a_angle = pw.DoubleField(null=True)

        class Meta:
            table_name = "technical_indicators"
            indexes = (
                (("session_id", "trade_date"), True),  # UNIQUE
            )

    # ─── 4. company_info ───
    class _CompanyInfoRow(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="company_info_rows", on_delete="CASCADE")
        ticker = pw.CharField(max_length=20)
        fetched_at = pw.DateTimeField(default=datetime.now)
        name = pw.CharField(max_length=200, null=True)
        sector = pw.CharField(max_length=100, null=True)
        industry = pw.CharField(max_length=100, null=True)
        market_cap = pw.BigIntegerField(null=True)
        week_52_high = pw.DoubleField(null=True)
        week_52_low = pw.DoubleField(null=True)
        per = pw.DoubleField(null=True)
        pbr = pw.DoubleField(null=True)
        eps = pw.DoubleField(null=True)
        dividend_yield = pw.DoubleField(null=True)
        beta = pw.DoubleField(null=True)
        analyst_target = pw.DoubleField(null=True)
        recommendation = pw.CharField(max_length=30, null=True)
        total_revenue = pw.BigIntegerField(null=True)
        operating_income = pw.BigIntegerField(null=True)
        debt_to_equity = pw.DoubleField(null=True)
        total_cash = pw.BigIntegerField(null=True)
        raw_json = _JSONB(null=True)  # JSONB

        class Meta:
            table_name = "company_info"

    # ─── 5. expert_opinions ───
    class _ExpertOpinionRow(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="expert_rows", on_delete="CASCADE")
        analysis_id = pw.ForeignKeyField(_AnalysisSession, column_name="analysis_id",
                                          null=True, backref="+", on_delete="SET NULL")
        ticker = pw.CharField(max_length=20)
        expert_name = pw.CharField(max_length=50)
        expert_style = pw.CharField(max_length=100, null=True)
        position = pw.CharField(max_length=10)
        confidence = pw.DoubleField(null=True)
        buy_price = pw.DoubleField(null=True)
        sell_price = pw.DoubleField(null=True)
        stop_loss = pw.DoubleField(null=True)
        rationale = pw.TextField(null=True)
        key_indicators = _JSONB(null=True)   # JSONB
        buy_prices = _JSONB(null=True)        # JSONB
        sell_prices = _JSONB(null=True)        # JSONB
        aggregated = _JSONB(null=True)         # JSONB
        filters_applied = _JSONB(null=True)    # JSONB

        class Meta:
            table_name = "expert_opinions"

    # ─── 6. macro_indicators ───
    class _MacroIndicatorRow(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="macro_rows", on_delete="CASCADE")
        fetched_at = pw.DateTimeField(default=datetime.now)
        indicator_key = pw.CharField(max_length=30)
        indicator_name = pw.CharField(max_length=100, null=True)
        current_value = pw.DoubleField(null=True)
        change_pct = pw.DoubleField(null=True)
        sma_20 = pw.DoubleField(null=True)
        trend = pw.CharField(max_length=20, null=True)
        raw_json = _JSONB(null=True)  # JSONB

        class Meta:
            table_name = "macro_indicators"

    # ─── 7. news_sentiment ───
    class _NewsSentimentRow(Base):
        id = pw.BigAutoField(primary_key=True)
        session_id = pw.ForeignKeyField(_AnalysisSession, column_name="session_id",
                                         backref="news_rows", on_delete="CASCADE")
        ticker = pw.CharField(max_length=20)
        fetched_at = pw.DateTimeField(default=datetime.now)
        title = pw.TextField(null=True)
        source = pw.CharField(max_length=200, null=True)
        url = pw.TextField(null=True)
        published = pw.CharField(max_length=50, null=True)
        summary = pw.TextField(null=True)
        sentiment = pw.CharField(max_length=20, null=True)
        relevance = pw.DoubleField(null=True)

        class Meta:
            table_name = "news_sentiment"

    # 글로벌 클래스 교체 (모듈 레벨에서 접근 가능하도록)
    global AnalysisSession, StockOHLCV, TechnicalIndicator
    global CompanyInfoRow, ExpertOpinionRow, MacroIndicatorRow, NewsSentimentRow

    AnalysisSession = _AnalysisSession
    StockOHLCV = _StockOHLCV
    TechnicalIndicator = _TechnicalIndicator
    CompanyInfoRow = _CompanyInfoRow
    ExpertOpinionRow = _ExpertOpinionRow
    MacroIndicatorRow = _MacroIndicatorRow
    NewsSentimentRow = _NewsSentimentRow

    return True


# ═══════════════════════════════════════════════════════════════
# 초기화 & 테이블 관리
# ═══════════════════════════════════════════════════════════════

_models_initialized = False


def ensure_models() -> bool:
    """
    Peewee 모델 초기화 + DB 바인딩 (lazy, 1회만)

    Returns:
        bool: 성공 여부
    """
    global _models_initialized

    if _models_initialized:
        return True

    if not is_db_available():
        return False

    try:
        _define_models()
        _bind_models()
        _models_initialized = True
        logger.info("Peewee 모델 초기화 완료")
        return True
    except Exception as e:
        logger.warning(f"Peewee 모델 초기화 실패: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# 세션 헬퍼 함수
# ═══════════════════════════════════════════════════════════════

def create_session(
    session_type: str,
    ticker: str,
    interval: str = "1d",
    period: str = None,
    parent_id: str = None,
    ttl_hours: float = 24,
    metadata: dict = None,
) -> Optional[str]:
    """
    새 분석 세션 생성

    Args:
        session_type: 세션 유형 (ohlcv, full_analysis, company_info, expert, signals, macro)
        ticker: 종목 코드
        interval: 데이터 간격 (1d, 1wk, 1mo)
        period: 수집 기간 (6mo, 1y 등)
        parent_id: 부모 세션 ID (계보 추적)
        ttl_hours: 만료 시간 (시간)
        metadata: 추가 메타데이터

    Returns:
        str: 세션 UUID 또는 None (DB 불가 시)
    """
    if not ensure_models():
        return None

    session_id = str(uuid.uuid4())
    now = datetime.now()

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        AnalysisSession.create(
            id=session_id,
            session_type=session_type,
            ticker=ticker,
            interval=interval,
            period=period,
            parent_id=parent_id,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours) if ttl_hours else None,
            metadata=metadata or {},  # BinaryJSONField → dict 직접 전달
            status="active",
        )
        logger.debug(f"세션 생성: {session_id[:8]}... [{session_type}] {ticker}")
        return session_id
    except Exception as e:
        logger.error(f"세션 생성 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


def get_session(session_id: str) -> Optional[dict]:
    """
    세션 정보 조회

    Args:
        session_id: 세션 UUID

    Returns:
        dict: 세션 정보 또는 None
    """
    if not ensure_models():
        return None

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        session = AnalysisSession.get_or_none(AnalysisSession.id == session_id)
        if session is None:
            return None
        return {
            "id": session.id,
            "session_type": session.session_type,
            "ticker": session.ticker,
            "interval": session.interval,
            "period": session.period,
            "parent_id": session.parent_id_id if session.parent_id else None,
            "created_at": str(session.created_at),
            "status": session.status,
        }
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ═══════════════════════════════════════════════════════════════
# DataFrame ↔ DB 변환 유틸리티
# ═══════════════════════════════════════════════════════════════

# DataFrame 컬럼명 → DB 컬럼명 매핑
OHLCV_COL_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "stock_splits",
}

# 기술적 지표 컬럼명 매핑 (DataFrame → DB)
INDICATOR_COL_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
    # 이동평균
    "SMA_5": "sma_5",
    "SMA_20": "sma_20",
    "SMA_60": "sma_60",
    "SMA_120": "sma_120",
    "EMA_12": "ema_12",
    "EMA_26": "ema_26",
    # RSI
    "RSI": "rsi",
    # MACD
    "MACD": "macd",
    "MACD_Signal": "macd_signal",
    "MACD_Hist": "macd_hist",
    # 볼린저밴드
    "BB_Upper": "bb_upper",
    "BB_Middle": "bb_middle",
    "BB_Lower": "bb_lower",
    "BB_Width": "bb_width",
    "BB_%B": "bb_pct",
    # 스토캐스틱
    "Stoch_K": "stoch_k",
    "Stoch_D": "stoch_d",
    # 변동성 & 추세
    "ATR": "atr",
    "ADX": "adx",
    "ADX_Pos": "adx_pos",
    "ADX_Neg": "adx_neg",
    # 거래량
    "OBV": "obv",
    # 일목균형표
    "Ichimoku_Tenkan": "ichimoku_tenkan",
    "Ichimoku_Kijun": "ichimoku_kijun",
    "Ichimoku_Senkou_A": "ichimoku_senkou_a",
    "Ichimoku_Senkou_B": "ichimoku_senkou_b",
    "Ichimoku_Chikou": "ichimoku_chikou",
    "Ichimoku_Cloud_Top": "ichimoku_cloud_top",
    "Ichimoku_Cloud_Bottom": "ichimoku_cloud_bottom",
    "Ichimoku_Tenkan_Angle": "ichimoku_tenkan_angle",
    "Ichimoku_Kijun_Angle": "ichimoku_kijun_angle",
    "Ichimoku_Senkou_A_Angle": "ichimoku_senkou_a_angle",
}

# 역매핑 (DB → DataFrame)
INDICATOR_COL_MAP_REVERSE = {v: k for k, v in INDICATOR_COL_MAP.items()}


def store_ohlcv(df, ticker: str, interval: str, session_id: str) -> int:
    """
    DataFrame OHLCV 데이터를 DB에 벌크 INSERT (ON CONFLICT UPDATE)

    Args:
        df: pandas DataFrame (Date 인덱스, OHLCV 컬럼)
        ticker: 종목 코드
        interval: 데이터 간격
        session_id: 세션 UUID

    Returns:
        int: 저장된 행 수
    """
    if not ensure_models():
        return 0

    import numpy as np

    db = get_db()
    rows = []
    for date, row in df.iterrows():
        trade_date = date.date() if hasattr(date, 'date') else date
        row_data = {
            "session_id": session_id,
            "ticker": ticker,
            "interval": interval,
            "trade_date": trade_date,
        }
        for df_col, db_col in OHLCV_COL_MAP.items():
            val = row.get(df_col)
            if val is not None and not (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                if db_col == "volume":
                    row_data[db_col] = int(val) if val == val else None
                else:
                    row_data[db_col] = float(val)
            else:
                row_data[db_col] = None
        rows.append(row_data)

    if not rows:
        return 0

    try:
        db.connect(reuse_if_open=True)
        # 벌크 INSERT, 50행씩 배치
        with db.atomic():
            for batch_start in range(0, len(rows), 50):
                batch = rows[batch_start:batch_start + 50]
                StockOHLCV.insert_many(batch).on_conflict(
                    conflict_target=[StockOHLCV.ticker, StockOHLCV.interval, StockOHLCV.trade_date],
                    update={
                        StockOHLCV.session_id: _pw.EXCLUDED.session_id,
                        StockOHLCV.open: _pw.EXCLUDED.open,
                        StockOHLCV.high: _pw.EXCLUDED.high,
                        StockOHLCV.low: _pw.EXCLUDED.low,
                        StockOHLCV.close: _pw.EXCLUDED.close,
                        StockOHLCV.volume: _pw.EXCLUDED.volume,
                        StockOHLCV.dividends: _pw.EXCLUDED.dividends,
                        StockOHLCV.stock_splits: _pw.EXCLUDED.stock_splits,
                    },
                ).execute()

        logger.info(f"OHLCV 저장: {ticker} {interval} {len(rows)}행")
        return len(rows)
    except Exception as e:
        logger.error(f"OHLCV 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_ohlcv(session_id: str = None, ticker: str = None,
               interval: str = "1d"):
    """
    DB에서 OHLCV 데이터를 DataFrame으로 복원

    Args:
        session_id: 세션 UUID (우선)
        ticker: 종목 코드 (session_id 없을 때 최신 세션)
        interval: 데이터 간격

    Returns:
        pandas.DataFrame 또는 None
    """
    if not ensure_models():
        return None

    import pandas as pd

    db = get_db()
    try:
        db.connect(reuse_if_open=True)

        if session_id:
            query = (StockOHLCV
                     .select()
                     .where(StockOHLCV.session_id == session_id)
                     .order_by(StockOHLCV.trade_date))
        elif ticker:
            # 최신 세션의 데이터 로드
            latest_session = (AnalysisSession
                              .select()
                              .where(
                                  (AnalysisSession.ticker == ticker) &
                                  (AnalysisSession.interval == interval) &
                                  (AnalysisSession.session_type == "ohlcv") &
                                  (AnalysisSession.status == "active")
                              )
                              .order_by(AnalysisSession.created_at.desc())
                              .first())
            if latest_session is None:
                return None
            query = (StockOHLCV
                     .select()
                     .where(StockOHLCV.session_id == latest_session.id)
                     .order_by(StockOHLCV.trade_date))
        else:
            return None

        rows = list(query.dicts())
        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("Date").sort_index()

        # DB 컬럼명 → DataFrame 컬럼명 역매핑
        rename_map = {v: k for k, v in OHLCV_COL_MAP.items() if v in df.columns}
        df = df.rename(columns=rename_map)

        # 불필요 컬럼 제거
        drop_cols = ["id", "session_id", "ticker", "interval", "trade_date"]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        return df

    except Exception as e:
        logger.error(f"OHLCV 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


def store_indicators(df, ticker: str, interval: str, session_id: str) -> int:
    """
    기술적 지표 DataFrame을 DB에 벌크 INSERT

    Args:
        df: pandas DataFrame (기술적 지표 포함)
        ticker: 종목 코드
        interval: 데이터 간격
        session_id: 분석 세션 UUID

    Returns:
        int: 저장된 행 수
    """
    if not ensure_models():
        return 0

    import numpy as np

    db = get_db()
    rows = []
    for date, row in df.iterrows():
        trade_date = date.date() if hasattr(date, 'date') else date
        row_data = {
            "session_id": session_id,
            "ticker": ticker,
            "interval": interval,
            "trade_date": trade_date,
        }
        for df_col, db_col in INDICATOR_COL_MAP.items():
            val = row.get(df_col)
            if val is not None and not (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                if db_col == "volume":
                    row_data[db_col] = int(val) if val == val else None
                else:
                    row_data[db_col] = float(val)
            else:
                row_data[db_col] = None
        rows.append(row_data)

    if not rows:
        return 0

    try:
        db.connect(reuse_if_open=True)
        with db.atomic():
            for batch_start in range(0, len(rows), 50):
                batch = rows[batch_start:batch_start + 50]
                TechnicalIndicator.insert_many(batch).on_conflict(
                    conflict_target=[TechnicalIndicator.session_id, TechnicalIndicator.trade_date],
                    update={col: getattr(_pw.EXCLUDED, col)
                            for col in INDICATOR_COL_MAP.values()},
                ).execute()

        logger.info(f"지표 저장: {ticker} {interval} {len(rows)}행")
        return len(rows)
    except Exception as e:
        logger.error(f"지표 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_indicators(session_id: str):
    """
    DB에서 기술적 지표를 DataFrame으로 복원

    Args:
        session_id: 분석 세션 UUID

    Returns:
        pandas.DataFrame 또는 None
    """
    if not ensure_models():
        return None

    import pandas as pd

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        query = (TechnicalIndicator
                 .select()
                 .where(TechnicalIndicator.session_id == session_id)
                 .order_by(TechnicalIndicator.trade_date))

        rows = list(query.dicts())
        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("Date").sort_index()

        # DB 컬럼명 → DataFrame 컬럼명 역매핑
        df = df.rename(columns=INDICATOR_COL_MAP_REVERSE)

        # 불필요 컬럼 제거
        drop_cols = ["id", "session_id", "ticker", "interval", "trade_date"]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        return df

    except Exception as e:
        logger.error(f"지표 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ═══════════════════════════════════════════════════════════════
# Phase 3: company_info, news_sentiment, macro, expert_opinions
# ═══════════════════════════════════════════════════════════════

def _parse_price(val):
    """'$123.45' 또는 '—' → float or None"""
    if val is None or val in ("—", "N/A", ""):
        return None
    try:
        return float(str(val).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_confidence(val):
    """'85%' → 85.0"""
    if val is None:
        return None
    try:
        return float(str(val).replace("%", ""))
    except (ValueError, TypeError):
        return None


# ─── company_info ───

_COMPANY_INFO_FIELD_MAP = {
    "이름": "name", "섹터": "sector", "산업": "industry",
    "시가총액": "market_cap", "52주_최고": "week_52_high",
    "52주_최저": "week_52_low", "PER": "per", "PBR": "pbr",
    "EPS": "eps", "배당수익률": "dividend_yield", "베타": "beta",
    "애널리스트_목표가": "analyst_target", "추천": "recommendation",
    "총매출": "total_revenue", "영업이익": "operating_income",
    "부채비율": "debt_to_equity", "현금": "total_cash",
}
_COMPANY_INFO_INT_FIELDS = {"market_cap", "total_revenue", "operating_income", "total_cash"}
_COMPANY_INFO_REVERSE_MAP = {v: k for k, v in _COMPANY_INFO_FIELD_MAP.items()}


def store_company_info(info_dict: dict, ticker: str, session_id: str) -> int:
    """
    기업 기본정보를 DB에 저장

    Args:
        info_dict: fetch_company_info 반환 dict (한국어 키)
        ticker: 종목 코드
        session_id: 세션 UUID

    Returns:
        int: 저장된 행 수 (0 또는 1)
    """
    if not ensure_models():
        return 0

    row_data = {"session_id": session_id, "ticker": ticker}
    for kr_key, db_col in _COMPANY_INFO_FIELD_MAP.items():
        val = info_dict.get(kr_key)
        if val is not None and db_col in _COMPANY_INFO_INT_FIELDS:
            try:
                row_data[db_col] = int(val)
            except (ValueError, TypeError):
                row_data[db_col] = None
        else:
            row_data[db_col] = val
    # BinaryJSONField는 dict를 직접 받아 JSONB로 변환
    row_data["raw_json"] = info_dict

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        with db.atomic():
            CompanyInfoRow.create(**row_data)
        logger.info(f"기업정보 저장: {ticker}")
        return 1
    except Exception as e:
        logger.error(f"기업정보 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_company_info(session_id: str = None, ticker: str = None):
    """
    DB에서 기업정보 로드

    Args:
        session_id: 세션 UUID (우선)
        ticker: 종목 코드 (session_id 없을 시 최신 조회)

    Returns:
        dict 또는 None
    """
    if not ensure_models():
        return None

    db = get_db()
    try:
        db.connect(reuse_if_open=True)

        if session_id:
            row = CompanyInfoRow.get_or_none(CompanyInfoRow.session_id == session_id)
        elif ticker:
            latest_session = (
                AnalysisSession.select()
                .where(
                    (AnalysisSession.ticker == ticker) &
                    (AnalysisSession.session_type == "company_info") &
                    (AnalysisSession.status == "active")
                )
                .order_by(AnalysisSession.created_at.desc())
                .first()
            )
            if latest_session is None:
                return None
            row = CompanyInfoRow.get_or_none(
                CompanyInfoRow.session_id == latest_session.id
            )
        else:
            return None

        if row is None:
            return None

        # raw_json 우선 (BinaryJSONField → dict 직접 반환)
        if row.raw_json and isinstance(row.raw_json, dict):
            return row.raw_json

        # 폴백: 컬럼에서 재구성
        result = {}
        for db_col, kr_key in _COMPANY_INFO_REVERSE_MAP.items():
            result[kr_key] = getattr(row, db_col, None)
        return result

    except Exception as e:
        logger.error(f"기업정보 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ─── news_sentiment ───

_NEWS_FIELD_MAP = {
    "제목": "title", "출처": "source", "URL": "url",
    "발행일": "published", "요약": "summary",
    "감성": "sentiment", "관련도": "relevance",
}
_NEWS_REVERSE_MAP = {v: k for k, v in _NEWS_FIELD_MAP.items()}


def store_news_sentiment(articles_list: list, ticker: str, session_id: str) -> int:
    """
    뉴스 감성 데이터를 DB에 배치 저장

    Args:
        articles_list: Article.to_dict() 리스트 (한국어 키)
        ticker: 종목 코드
        session_id: 세션 UUID

    Returns:
        int: 저장된 행 수
    """
    if not ensure_models():
        return 0

    rows = []
    for art_dict in articles_list:
        row_data = {"session_id": session_id, "ticker": ticker}
        for kr_key, db_col in _NEWS_FIELD_MAP.items():
            row_data[db_col] = art_dict.get(kr_key)
        rows.append(row_data)

    if not rows:
        return 0

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        with db.atomic():
            for batch_start in range(0, len(rows), 50):
                batch = rows[batch_start:batch_start + 50]
                NewsSentimentRow.insert_many(batch).execute()
        logger.info(f"뉴스감성 저장: {ticker} {len(rows)}건")
        return len(rows)
    except Exception as e:
        logger.error(f"뉴스감성 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_news_sentiment(session_id: str = None, ticker: str = None):
    """
    DB에서 뉴스 감성 데이터 로드

    Args:
        session_id: 세션 UUID (우선)
        ticker: 종목 코드 (session_id 없을 시 최신 조회)

    Returns:
        list[dict] 또는 None
    """
    if not ensure_models():
        return None

    db = get_db()
    try:
        db.connect(reuse_if_open=True)

        if session_id:
            query = (NewsSentimentRow.select()
                     .where(NewsSentimentRow.session_id == session_id))
        elif ticker:
            latest_session = (
                AnalysisSession.select()
                .where(
                    (AnalysisSession.ticker == ticker) &
                    (AnalysisSession.session_type == "news") &
                    (AnalysisSession.status == "active")
                )
                .order_by(AnalysisSession.created_at.desc())
                .first()
            )
            if latest_session is None:
                return None
            query = (NewsSentimentRow.select()
                     .where(NewsSentimentRow.session_id == latest_session.id))
        else:
            return None

        rows = list(query.dicts())
        if not rows:
            return None

        result = []
        for row in rows:
            art = {}
            for db_col, kr_key in _NEWS_REVERSE_MAP.items():
                art[kr_key] = row.get(db_col)
            result.append(art)
        return result

    except Exception as e:
        logger.error(f"뉴스감성 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ─── macro_indicators ───

_MACRO_INDICATOR_KEYS = ["vix", "treasury_10y", "sp500", "oil", "gold", "dollar"]


def store_macro_indicators(macro_dict: dict, session_id: str) -> int:
    """
    매크로 경제 지표를 DB에 저장 (6개 지표 → 6행)

    Args:
        macro_dict: fetch_macro_indicators 반환 dict
        session_id: 세션 UUID

    Returns:
        int: 저장된 행 수
    """
    if not ensure_models():
        return 0

    rows = []
    for key in _MACRO_INDICATOR_KEYS:
        data = macro_dict.get(key)
        if data is None:
            continue
        rows.append({
            "session_id": session_id,
            "indicator_key": key,
            "indicator_name": data.get("name"),
            "current_value": data.get("current"),
            "change_pct": data.get("change_pct"),
            "sma_20": data.get("avg_20d"),
            "trend": data.get("trend"),
            "raw_json": data,  # BinaryJSONField → dict 직접 전달
        })

    if not rows:
        return 0

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        with db.atomic():
            MacroIndicatorRow.insert_many(rows).execute()
        logger.info(f"매크로지표 저장: {len(rows)}개 지표")
        return len(rows)
    except Exception as e:
        logger.error(f"매크로지표 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_macro_indicators(session_id: str):
    """
    DB에서 매크로 지표 로드

    Args:
        session_id: 세션 UUID

    Returns:
        dict 또는 None (원래 구조 복원)
    """
    if not ensure_models():
        return None

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        query = (MacroIndicatorRow.select()
                 .where(MacroIndicatorRow.session_id == session_id))
        rows = list(query.dicts())
        if not rows:
            return None

        result = {}
        for row in rows:
            key = row["indicator_key"]
            rj = row.get("raw_json")
            if rj and isinstance(rj, dict):
                result[key] = rj
                continue
            result[key] = {
                "current": row.get("current_value"),
                "change_pct": row.get("change_pct"),
                "avg_20d": row.get("sma_20"),
                "trend": row.get("trend"),
                "name": row.get("indicator_name"),
            }
        return result

    except Exception as e:
        logger.error(f"매크로지표 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ─── expert_opinions ───

def store_expert_opinions(opinions_list: list, aggregated: dict,
                          filters: list, ticker: str, session_id: str,
                          analysis_id: str = None) -> int:
    """
    전문가 의견 + 집계 결과를 DB에 저장

    Args:
        opinions_list: ExpertOpinion.to_dict() 리스트 (한국어 키)
        aggregated: 가중 집계 dict
        filters: 적용된 필터 리스트
        ticker: 종목 코드
        session_id: 세션 UUID
        analysis_id: 기술분석 세션 UUID (선택)

    Returns:
        int: 저장된 행 수
    """
    if not ensure_models():
        return 0

    rows = []
    for op_dict in opinions_list:
        row_data = {
            "session_id": session_id,
            "analysis_id": analysis_id,
            "ticker": ticker,
            "expert_name": op_dict.get("전문가", ""),
            "expert_style": op_dict.get("스타일"),
            "position": op_dict.get("포지션", "홀드"),
            "confidence": _parse_confidence(op_dict.get("확신도")),
            "buy_price": _parse_price(op_dict.get("매수가")),
            "sell_price": _parse_price(op_dict.get("매도가")),
            "stop_loss": _parse_price(op_dict.get("손절가")),
            "rationale": op_dict.get("근거"),
        }
        # BinaryJSONField: dict/list 직접 전달
        ki = op_dict.get("핵심지표")
        if ki:
            row_data["key_indicators"] = ki
        bp = op_dict.get("3분할_매수")
        if bp:
            row_data["buy_prices"] = bp
        sp = op_dict.get("3분할_매도")
        if sp:
            row_data["sell_prices"] = sp
        rows.append(row_data)

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        count = 0
        with db.atomic():
            # 전문가 행 배치 INSERT
            if rows:
                ExpertOpinionRow.insert_many(rows).execute()
                count = len(rows)

            # 집계 행 별도 INSERT (aggregated/filters_applied JSONB 포함)
            ExpertOpinionRow.create(
                session_id=session_id,
                analysis_id=analysis_id,
                ticker=ticker,
                expert_name="__aggregated__",
                position=aggregated.get("dominant", "홀드"),
                aggregated=aggregated,         # BinaryJSONField → dict 직접
                filters_applied=filters or [],  # BinaryJSONField → list 직접
            )
            count += 1

        logger.info(f"전문가의견 저장: {ticker} {count - 1}명 + 집계")
        return count
    except Exception as e:
        logger.error(f"전문가의견 저장 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()


def load_expert_opinions(session_id: str):
    """
    DB에서 전문가 의견 로드

    Args:
        session_id: 세션 UUID

    Returns:
        dict: {"experts": [...], "aggregated": {...}, "filters_applied": [...]} 또는 None
    """
    if not ensure_models():
        return None

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        query = (ExpertOpinionRow.select()
                 .where(ExpertOpinionRow.session_id == session_id))
        rows = list(query.dicts())
        if not rows:
            return None

        experts = []
        aggregated = {}
        filters_applied = []

        for row in rows:
            if row["expert_name"] == "__aggregated__":
                # BinaryJSONField → dict/list 직접 반환
                agg_val = row.get("aggregated")
                if agg_val and isinstance(agg_val, dict):
                    aggregated = agg_val
                else:
                    aggregated = {"dominant": row.get("position", "홀드")}
                filt_val = row.get("filters_applied")
                if filt_val and isinstance(filt_val, list):
                    filters_applied = filt_val
            else:
                ki = row.get("key_indicators")
                expert_dict = {
                    "전문가": row.get("expert_name"),
                    "스타일": row.get("expert_style"),
                    "포지션": row.get("position"),
                    "확신도": f"{row['confidence']:.0f}%" if row.get("confidence") else "0%",
                    "매수가": f"${row['buy_price']:.2f}" if row.get("buy_price") else "—",
                    "매도가": f"${row['sell_price']:.2f}" if row.get("sell_price") else "—",
                    "손절가": f"${row['stop_loss']:.2f}" if row.get("stop_loss") else "—",
                    "근거": row.get("rationale", ""),
                    "핵심지표": ki if isinstance(ki, list) else [],
                }
                bp = row.get("buy_prices")
                if bp and isinstance(bp, list):
                    expert_dict["3분할_매수"] = bp
                sp = row.get("sell_prices")
                if sp and isinstance(sp, list):
                    expert_dict["3분할_매도"] = sp
                experts.append(expert_dict)

        return {
            "experts": experts,
            "aggregated": aggregated,
            "filters_applied": filters_applied,
        }

    except Exception as e:
        logger.error(f"전문가의견 로드 실패: {e}")
        return None
    finally:
        if not db.is_closed():
            db.close()


# ═══════════════════════════════════════════════════════════════
# 세션 만료 정리
# ═══════════════════════════════════════════════════════════════

def cleanup_expired_sessions() -> int:
    """만료된 세션 정리 (status='expired'로 변경)"""
    if not ensure_models():
        return 0

    db = get_db()
    try:
        db.connect(reuse_if_open=True)
        now = datetime.now()
        count = (AnalysisSession
                 .update(status="expired")
                 .where(
                     (AnalysisSession.status == "active") &
                     (AnalysisSession.expires_at.is_null(False)) &
                     (AnalysisSession.expires_at < now)
                 )
                 .execute())
        if count > 0:
            logger.info(f"만료 세션 정리: {count}건")
        return count
    except Exception as e:
        logger.error(f"세션 정리 실패: {e}")
        return 0
    finally:
        if not db.is_closed():
            db.close()
