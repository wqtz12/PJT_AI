"""
P2-3 테스트: 섹터별 밸류에이션 기준
- get_sector_criteria() 매핑 동작
- 섹터별 PBR/부채/현금 기준이 다른지 검증
- ValueAnalyst가 섹터 기준을 반영하는지 검증
- 폴백(섹터 불명) 동작
"""
import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.sector_valuation import get_sector_criteria, get_available_sectors


class TestGetSectorCriteria:
    """get_sector_criteria() 기본 동작"""

    def test_returns_dict(self):
        result = get_sector_criteria("Technology")
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = get_sector_criteria("Technology")
        required = ["pbr_low", "pbr_high", "debt_healthy", "debt_warning",
                     "cash_rich", "cash_poor", "eps_label", "sector_matched"]
        for key in required:
            assert key in result, f"키 누락: {key}"

    def test_none_returns_default(self):
        result = get_sector_criteria(None)
        assert result["sector_matched"] == "기본"

    def test_empty_string_returns_default(self):
        result = get_sector_criteria("")
        assert result["sector_matched"] == "기본"

    def test_unknown_sector_returns_default(self):
        result = get_sector_criteria("Unknown Alien Sector")
        assert result["sector_matched"] == "기본"


class TestSectorSpecificValues:
    """섹터별 기준값이 다른지 검증"""

    def test_tech_higher_pbr_than_default(self):
        tech = get_sector_criteria("Technology")
        default = get_sector_criteria(None)
        assert tech["pbr_low"] > default["pbr_low"]
        assert tech["pbr_high"] > default["pbr_high"]

    def test_energy_lower_pbr_than_tech(self):
        tech = get_sector_criteria("Technology")
        energy = get_sector_criteria("Energy")
        assert energy["pbr_low"] < tech["pbr_low"]

    def test_financial_high_debt_tolerance(self):
        fin = get_sector_criteria("Financial Services")
        default = get_sector_criteria(None)
        assert fin["debt_healthy"] > default["debt_healthy"]
        assert fin["debt_warning"] > default["debt_warning"]

    def test_healthcare_high_cash_threshold(self):
        health = get_sector_criteria("Healthcare")
        default = get_sector_criteria(None)
        assert health["cash_rich"] >= default["cash_rich"]

    def test_utilities_moderate_pbr(self):
        util = get_sector_criteria("Utilities")
        assert util["pbr_low"] < 1.5
        assert util["pbr_high"] < 5.0


class TestSectorNameMapping:
    """yfinance 섹터명 → config key 매핑 검증"""

    def test_technology(self):
        result = get_sector_criteria("Technology")
        assert result["sector_matched"] == "기술"

    def test_energy(self):
        result = get_sector_criteria("Energy")
        assert result["sector_matched"] == "에너지"

    def test_healthcare(self):
        result = get_sector_criteria("Healthcare")
        assert result["sector_matched"] == "헬스케어"

    def test_financial_services(self):
        result = get_sector_criteria("Financial Services")
        assert result["sector_matched"] == "금융"

    def test_financials_alias(self):
        """yfinance가 'Financials'로 반환하는 경우도 매핑"""
        result = get_sector_criteria("Financials")
        assert result["sector_matched"] == "금융"

    def test_consumer_cyclical(self):
        result = get_sector_criteria("Consumer Cyclical")
        assert result["sector_matched"] == "경기소비재"

    def test_consumer_discretionary_alias(self):
        result = get_sector_criteria("Consumer Discretionary")
        assert result["sector_matched"] == "경기소비재"

    def test_consumer_defensive(self):
        result = get_sector_criteria("Consumer Defensive")
        assert result["sector_matched"] == "필수소비재"

    def test_consumer_staples_alias(self):
        result = get_sector_criteria("Consumer Staples")
        assert result["sector_matched"] == "필수소비재"

    def test_industrials(self):
        result = get_sector_criteria("Industrials")
        assert result["sector_matched"] == "산업재"

    def test_case_insensitive(self):
        """대소문자 무관하게 매핑"""
        r1 = get_sector_criteria("TECHNOLOGY")
        r2 = get_sector_criteria("technology")
        r3 = get_sector_criteria("Technology")
        assert r1["sector_matched"] == r2["sector_matched"] == r3["sector_matched"]

    def test_basic_materials(self):
        result = get_sector_criteria("Basic Materials")
        assert result["sector_matched"] == "소재"

    def test_materials_alias(self):
        result = get_sector_criteria("Materials")
        assert result["sector_matched"] == "소재"


class TestGetAvailableSectors:
    """get_available_sectors() 검증"""

    def test_returns_list(self):
        sectors = get_available_sectors()
        assert isinstance(sectors, list)

    def test_has_minimum_sectors(self):
        sectors = get_available_sectors()
        assert len(sectors) >= 5  # 최소 5개 섹터 정의

    def test_no_default_in_list(self):
        sectors = get_available_sectors()
        assert "default" not in sectors

    def test_technology_in_list(self):
        sectors = get_available_sectors()
        assert "technology" in sectors


# ─── ValueAnalyst 섹터 연동 검증 ───

def _make_df(price=10.0, rows=50):
    """테스트용 DataFrame 생성"""
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    return pd.DataFrame({
        "Open": price, "High": price*1.02, "Low": price*0.98,
        "Close": price, "Volume": 1000000,
    }, index=dates)


class TestValueAnalystSectorIntegration:
    """ValueAnalyst가 섹터별 기준을 실제로 사용하는지 검증"""

    def test_tech_sector_pbr_scoring(self):
        """기술주에서 PBR 2.5는 저평가, 일반 기준에서는 적정"""
        from expert_strategies.value_analyst import ValueAnalyst
        df = _make_df(price=10.0)

        # 기술 섹터: PBR 2.5 < pbr_low(3.0) → 저평가 (+2)
        info_tech = {"섹터": "Technology", "PBR": 2.5, "52주_최고": 15, "52주_최저": 5}
        result_tech = ValueAnalyst.analyze(df, info_tech)
        assert "섹터 대비 저평가" in result_tech.rationale

        # 기본 섹터: PBR 2.5 > pbr_low(1.0) → 적정
        info_default = {"PBR": 2.5, "52주_최고": 15, "52주_최저": 5}
        result_default = ValueAnalyst.analyze(df, info_default)
        assert "섹터 대비 저평가" not in result_default.rationale

    def test_financial_sector_debt_tolerance(self):
        """금융 섹터에서 부채비율 150%는 건전, 일반 기준에서는 과다"""
        from expert_strategies.value_analyst import ValueAnalyst
        df = _make_df(price=10.0)

        # 금융: 부채비율 150% < debt_healthy(200%) → 건전
        info_fin = {"섹터": "Financial Services", "부채비율": 150.0,
                    "52주_최고": 15, "52주_최저": 5}
        result_fin = ValueAnalyst.analyze(df, info_fin)
        assert "건전" in result_fin.rationale

        # 기본: 부채비율 150% > debt_warning(100%) → 과다
        info_default = {"부채비율": 150.0, "52주_최고": 15, "52주_최저": 5}
        result_default = ValueAnalyst.analyze(df, info_default)
        assert "과다" in result_default.rationale

    def test_energy_sector_label_in_rationale(self):
        """에너지 섹터일 때 rationale에 섹터 정보가 포함"""
        from expert_strategies.value_analyst import ValueAnalyst
        df = _make_df(price=10.0)
        info = {"섹터": "Energy", "PBR": 1.5, "52주_최고": 15, "52주_최저": 5}
        result = ValueAnalyst.analyze(df, info)
        assert "에너지" in result.rationale

    def test_no_sector_uses_default(self):
        """섹터 정보 없으면 기본 기준 사용"""
        from expert_strategies.value_analyst import ValueAnalyst
        df = _make_df(price=10.0)
        info = {"PBR": 0.5, "52주_최고": 15, "52주_최저": 5}
        result = ValueAnalyst.analyze(df, info)
        # 섹터 라인 없고, PBR 0.5 < 1.0(기본) → 저평가
        assert "섹터 대비 저평가" in result.rationale

    def test_healthcare_cash_criteria(self):
        """헬스케어 섹터에서 현금비율 기준이 더 높음"""
        from expert_strategies.value_analyst import ValueAnalyst
        df = _make_df(price=10.0)

        # 헬스케어: cash_rich = 0.30, 현금비율 25% < 30% → 풍부하지 않음
        info_health = {
            "섹터": "Healthcare", "현금": 250_000_000,
            "시가총액": 1_000_000_000, "52주_최고": 15, "52주_최저": 5
        }
        result_health = ValueAnalyst.analyze(df, info_health)
        assert "풍부" not in result_health.rationale

        # 기본: cash_rich = 0.20, 현금비율 25% > 20% → 풍부
        info_default = {
            "현금": 250_000_000,
            "시가총액": 1_000_000_000, "52주_최고": 15, "52주_최저": 5
        }
        result_default = ValueAnalyst.analyze(df, info_default)
        assert "풍부" in result_default.rationale


class TestConfigSectorSection:
    """config.yaml의 sector_valuation 섹션 검증"""

    def test_config_has_sector_valuation(self):
        from common.config import get_config
        cfg = get_config()
        assert "sector_valuation" in cfg

    def test_config_has_default_sector(self):
        from common.config import get_config
        cfg = get_config()
        assert "default" in cfg["sector_valuation"]

    def test_config_has_technology(self):
        from common.config import get_config
        cfg = get_config()
        assert "technology" in cfg["sector_valuation"]

    def test_config_default_has_required_keys(self):
        from common.config import get_config
        cfg = get_config()
        default = cfg["sector_valuation"]["default"]
        assert "pbr_low" in default
        assert "pbr_high" in default
        assert "debt_healthy" in default
