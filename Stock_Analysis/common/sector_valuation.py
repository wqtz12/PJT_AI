"""
섹터별 밸류에이션 기준 모듈

yfinance info["sector"] 값을 기반으로 해당 섹터의 적정 PBR/부채비율/현금비율 기준을 제공합니다.

사용법:
    from common.sector_valuation import get_sector_criteria
    criteria = get_sector_criteria("Technology")
    if pbr < criteria["pbr_low"]:
        score += 2  # 섹터 대비 저평가
"""
import logging
from common.config import get_config

logger = logging.getLogger(__name__)

# yfinance sector 이름 → config key 매핑
# yfinance는 "Technology", "Energy" 등 영문으로 반환
_SECTOR_KEY_MAP = {
    "technology": "technology",
    "energy": "energy",
    "healthcare": "healthcare",
    "financial services": "financial_services",
    "financials": "financial_services",
    "industrials": "industrials",
    "consumer cyclical": "consumer_cyclical",
    "consumer discretionary": "consumer_cyclical",
    "consumer defensive": "consumer_defensive",
    "consumer staples": "consumer_defensive",
    "utilities": "utilities",
    "real estate": "real_estate",
    "communication services": "communication_services",
    "basic materials": "basic_materials",
    "materials": "basic_materials",
}

# 내장 기본값 (config.yaml 없을 때)
_DEFAULT_CRITERIA = {
    "pbr_low": 1.0,
    "pbr_high": 3.0,
    "debt_healthy": 50,
    "debt_warning": 100,
    "cash_rich": 0.20,
    "cash_poor": 0.05,
    "eps_label": "일반",
}


def get_sector_criteria(sector: str = None) -> dict:
    """
    섹터별 밸류에이션 기준 반환

    Args:
        sector: yfinance info["sector"] 문자열 (예: "Technology", "Energy")
                None이면 기본값 반환

    Returns:
        dict: {
            "pbr_low": float,       # PBR 저평가 기준
            "pbr_high": float,      # PBR 고평가 기준
            "debt_healthy": float,  # 건전 부채비율 (%)
            "debt_warning": float,  # 경고 부채비율 (%)
            "cash_rich": float,     # 풍부한 현금비율
            "cash_poor": float,     # 부족한 현금비율
            "eps_label": str,       # 섹터 라벨
            "sector_matched": str,  # 매칭된 섹터명
        }
    """
    cfg = get_config()
    sector_cfg = cfg.get("sector_valuation", {})
    default = sector_cfg.get("default", _DEFAULT_CRITERIA)

    if sector is None or not isinstance(sector, str) or not sector.strip():
        result = {**_DEFAULT_CRITERIA, **default}
        result["sector_matched"] = "기본"
        return result

    # yfinance 섹터명 → config key 변환
    sector_lower = sector.strip().lower()
    config_key = _SECTOR_KEY_MAP.get(sector_lower)

    if config_key and config_key in sector_cfg:
        criteria = sector_cfg[config_key]
        result = {**_DEFAULT_CRITERIA, **default, **criteria}
        result["sector_matched"] = criteria.get("eps_label", sector)
        logger.info(f"섹터별 기준 적용: {sector} → {config_key}")
        return result

    # 매핑 실패 시 부분 매칭 시도
    for key, config_name in _SECTOR_KEY_MAP.items():
        if key in sector_lower or sector_lower in key:
            if config_name in sector_cfg:
                criteria = sector_cfg[config_name]
                result = {**_DEFAULT_CRITERIA, **default, **criteria}
                result["sector_matched"] = criteria.get("eps_label", sector)
                logger.info(f"섹터별 기준 부분매칭: {sector} → {config_name}")
                return result

    # 완전 실패 → 기본값
    result = {**_DEFAULT_CRITERIA, **default}
    result["sector_matched"] = "기본"
    logger.info(f"섹터 '{sector}' 매칭 실패 → 기본 기준 사용")
    return result


def get_available_sectors() -> list:
    """config에 정의된 섹터 목록 반환 (디버깅용)"""
    cfg = get_config()
    sector_cfg = cfg.get("sector_valuation", {})
    return [k for k in sector_cfg.keys() if k != "default"]
