"""
설정 관리 모듈 - config.yaml 로드 및 접근

사용법:
    from common.config import get_config
    cfg = get_config()
    period = cfg["defaults"]["period"]
    rsi_window = cfg["indicators"]["rsi_window"]

설정 우선순위:
    1. config.yaml 파일 값
    2. 내장 기본값 (yaml 파일이 없거나 키 누락 시)
"""
import os
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# ─── 내장 기본값 (config.yaml 없을 때 폴백) ───
_DEFAULTS = {
    "database": {
        "enabled": True,
        "host": "localhost",
        "port": 5432,
        "name": "stock_analysis",
        "user": "stock_user",
        "password": "stock_pass_dev_2024",
        "fallback_to_json": True,
        "session_ttl_hours": 24,
    },
    "defaults": {
        "ticker": "PLUG",
        "period": "6mo",
        "output_dir": "output",
        "log_level": "INFO",
        "log_to_file": True,
    },
    "data": {
        "min_rows": {"1mo": 15, "3mo": 40, "6mo": 80, "1y": 180, "2y": 350, "5y": 800},
        "required_columns": ["Open", "High", "Low", "Close", "Volume"],
        "max_nan_ratio": 0.10,
        "stale_data_days": 5,
        "zero_volume_warn_ratio": 0.20,
        "max_news_articles": 10,
        "max_analyst_ratings": 8,
    },
    "indicators": {
        "sma_windows": [5, 20, 60, 120],
        "ema_windows": [12, 26],
        "rsi_window": 14,
        "bb_window": 20,
        "bb_std_dev": 2,
        "atr_window": 14,
        "adx_window": 14,
        "ichimoku": {
            "tenkan_window": 9,
            "kijun_window": 26,
            "senkou_b_window": 52,
            "chikou_shift": 26,
        },
        "min_rows_per_indicator": {
            "moving_averages": 5, "rsi": 15, "macd": 27,
            "bollinger_bands": 21, "stochastic": 15,
            "atr": 15, "adx": 30, "obv": 2,
            "ichimoku": 53, "ichimoku_angles": 53,
        },
    },
    "thresholds": {
        "rsi": {
            "overbought": 70, "oversold": 30,
            "extreme_high": 75, "extreme_low": 25,
            "momentum_high": 60, "momentum_low": 45,
            "contrarian_high": 65, "contrarian_low": 35,
        },
        "bollinger": {
            "upper_breach": 1.0, "upper_near": 0.85,
            "lower_breach": 0.0, "lower_near": 0.15,
            "squeeze_ratio": 0.6, "expand_ratio": 1.5,
        },
        "adx": {"strong": 30, "moderate": 20},
        "stochastic": {"overbought": 80, "oversold": 20},
        "ichimoku": {
            "cloud_thick_ratio": 0.02,
            "cloud_thin_ratio": 0.005,
            "angle_strong": 26,
            "angle_flat": 10,
            "angle_window": 5,
        },
        "volume": {"surge_ratio": 2.0, "active_ratio": 1.3, "dry_ratio": 0.5},
        "range_52w": {"low_zone": 0.25, "mid_low": 0.40, "high_zone": 0.80},
        "return_5d": {"strong": 5.0, "moderate": 2.0, "decline": -2.0, "crash": -5.0},
        "score": {"buy_threshold": 3, "sell_threshold": -3, "sell_threshold_value": -2},
        "atr": {"sell_multiplier": 3.0, "stop_multiplier": 2.0, "default_ratio": 0.05},
    },
    "confidence": {
        "max": 90,
        "base_buy": 50, "base_sell": 50, "base_hold": 35,
        "weight_buy": 7, "weight_sell": 7, "weight_hold": 5,
        "no_data": 10,
    },
    "sentiment": {
        "positive_keywords": ["surge", "rally", "gain", "rise", "bullish", "upgrade", "beat", "record", "growth", "strong", "buy"],
        "negative_keywords": ["drop", "fall", "decline", "bearish", "downgrade", "miss", "loss", "weak", "sell", "cut", "concern"],
        "positive_keywords_kr": ["상승", "급등", "호실적", "수주", "매수", "목표가 상향", "사상 최고", "영업이익 증가", "성장", "흑자", "수혜"],
        "negative_keywords_kr": ["하락", "급락", "적자", "실적 부진", "매도", "목표가 하향", "손실", "감소", "하향", "리스크", "우려"],
    },
    "chart": {
        "dpi": 150,
        "candlestick_figsize": [16, 10],
        "dashboard_figsize": [16, 20],
        "performance_figsize": [14, 10],
        "sma_colors": {"SMA_5": "#FF6B6B", "SMA_20": "#4ECDC4", "SMA_60": "#45B7D1", "SMA_120": "#96CEB4"},
        "candle_up": "red",
        "candle_down": "blue",
    },
    "sector_valuation": {
        "default": {
            "pbr_low": 1.0, "pbr_high": 3.0,
            "debt_healthy": 50, "debt_warning": 100,
            "cash_rich": 0.20, "cash_poor": 0.05,
            "eps_label": "일반",
        },
        "technology": {
            "pbr_low": 3.0, "pbr_high": 10.0,
            "debt_healthy": 40, "debt_warning": 80,
            "cash_rich": 0.25, "cash_poor": 0.10,
            "eps_label": "기술",
        },
        "energy": {
            "pbr_low": 0.8, "pbr_high": 2.0,
            "debt_healthy": 60, "debt_warning": 120,
            "cash_rich": 0.15, "cash_poor": 0.05,
            "eps_label": "에너지",
        },
        "healthcare": {
            "pbr_low": 2.0, "pbr_high": 8.0,
            "debt_healthy": 40, "debt_warning": 80,
            "cash_rich": 0.30, "cash_poor": 0.10,
            "eps_label": "헬스케어",
        },
        "financial_services": {
            "pbr_low": 0.7, "pbr_high": 2.0,
            "debt_healthy": 200, "debt_warning": 500,
            "cash_rich": 0.10, "cash_poor": 0.02,
            "eps_label": "금융",
        },
        "industrials": {
            "pbr_low": 1.5, "pbr_high": 4.0,
            "debt_healthy": 60, "debt_warning": 120,
            "cash_rich": 0.15, "cash_poor": 0.05,
            "eps_label": "산업재",
        },
    },
    "macro": {
        "indicators": {
            "vix": {"ticker": "^VIX", "name": "VIX (변동성지수)"},
            "treasury_10y": {"ticker": "^TNX", "name": "10년 국채금리"},
            "sp500": {"ticker": "^GSPC", "name": "S&P 500"},
            "oil": {"ticker": "CL=F", "name": "WTI 원유"},
            "gold": {"ticker": "GC=F", "name": "금"},
            "dollar": {"ticker": "DX-Y.NYB", "name": "달러 인덱스"},
        },
        "cache_ttl_minutes": 120,
        "fetch_period": "3mo",
        "vix_levels": {"low": 15, "normal": 20, "elevated": 25, "high": 35},
        "trend_window": 5,
        "trend_threshold_pct": 1.0,
        "score_impact_max": 3,
        "vix_weight": 1.0,
        "rate_weight": 1.0,
    },
    "backtest": {
        "var_confidence": 0.95,
        "var_holding_days": 1,
        "risk_free_rate": 0.04,
        "trading_days_per_year": 252,
    },
    "report": {
        "max_news_display": 8,
        "rationale_max_length": 60,
    },
    "error_tracking": {
        "enabled": True,
        "log_dir": "output/error_logs",
        "retention_days": 30,
        "auto_analysis": {
            "enabled": True,
            "auto_correct": True,
        },
        "pattern_detection": {
            "recurring_threshold": 3,
            "module_instability_types": 2,
        },
        "correction_limits": {
            "max_cache_ttl": 480,
            "min_cache_ttl": 5,
            "max_retry": 5,
            "max_timeout_sec": 120,
        },
    },
    "price_validation": {
        "enabled": True,
        "threshold_pct": 5.0,
        "auto_refresh": True,
        "stale_days_warning": 3,
    },
    "cache": {
        "market_aware_ttl": True,
        "us_market_hours": {"open": "09:30", "close": "16:00", "tz": "US/Eastern"},
        "kr_market_hours": {"open": "09:00", "close": "15:30", "tz": "Asia/Seoul"},
        "after_hours_multiplier": 4,
        "weekend_multiplier": 16,
    },
    "opinion_filters": {
        "enabled": True,
        "trend_confirmation": {
            "enabled": True,
            "downtrend_return_5d_threshold": -5.0,
            "consec_down_days_threshold": 3,
        },
        "value_trap": {
            "enabled": True,
            "range_52w_threshold": 0.30,
            "falling_return_threshold": -5.0,
        },
        "oversold_bounce": {
            "enabled": True,
            "rsi_threshold": 30,
            "adx_strong_threshold": 25,
        },
    },
    "expert_aggregation": {
        "weighted": True,
        "base_weight": 1.0,
        "trend_boost_adx_threshold": 30,
        "value_boost_adx_threshold": 20,
        "contrarian_boost_vix_threshold": 25,
        "boost_multiplier": 1.5,
    },
    "split_entry": {
        "conservative_atr_mult": 2.0,
        "moderate_atr_mult": 1.0,
        "aggressive_atr_mult": 0.0,
        "conservative_sell_atr": 1.5,
        "moderate_sell_atr": 3.0,
        "aggressive_sell_atr": 5.0,
    },
}

# ─── 싱글턴 캐시 ───
_config_cache = None
_config_path = None


def _deep_merge(base: dict, override: dict) -> dict:
    """딥 머지 - override 값이 base 위에 덮어쓰기"""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(config_path: str = None) -> dict:
    """
    config.yaml 로드 (없으면 내장 기본값 사용)

    Args:
        config_path: yaml 파일 경로 (None이면 자동 탐색)

    Returns:
        dict: 설정 딕셔너리
    """
    global _config_cache, _config_path

    # 경로 결정
    if config_path is None:
        # Stock_Analysis 루트의 config.yaml
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.yaml")

    # yaml 파일 로드 시도
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}
            config = _deep_merge(_DEFAULTS, yaml_config)
            logger.info(f"설정 로드: {config_path}")
        except ImportError:
            logger.warning("PyYAML 미설치 → 내장 기본값 사용")
            config = deepcopy(_DEFAULTS)
        except Exception as e:
            logger.warning(f"config.yaml 파싱 실패 ({e}) → 내장 기본값 사용")
            config = deepcopy(_DEFAULTS)
    else:
        logger.info(f"config.yaml 없음 ({config_path}) → 내장 기본값 사용")
        config = deepcopy(_DEFAULTS)

    _config_cache = config
    _config_path = config_path
    return config


def get_config() -> dict:
    """캐시된 설정 반환 (없으면 자동 로드)"""
    global _config_cache
    if _config_cache is None:
        return load_config()
    return _config_cache


def reload_config(config_path: str = None) -> dict:
    """설정 리로드 (캐시 무효화)"""
    global _config_cache
    _config_cache = None
    return load_config(config_path)
