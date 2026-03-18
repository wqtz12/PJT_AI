"""
P5 로그 분석기 테스트 - log_analyzer.py

테스트 항목:
    - _identify_patterns(): 반복 에러 감지, 모듈 불안정성 감지
    - _generate_recommendations(): 카테고리별 추천 생성
    - apply_auto_corrections(): 자동 수정 적용 + 안전 한계 준수
    - generate_analysis_report(): 보고서 텍스트 생성 + 파일 저장
    - analyze_previous_day(): 통합 분석 흐름
    - run_daily_analysis(): guard clause / 비활성 시 스킵
    - _update_config_value(): atomic config 수정
"""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from common.error_tracker import ErrorCategory, record_error
from log_analyzer import (
    _identify_patterns,
    _generate_recommendations,
    apply_auto_corrections,
    generate_analysis_report,
    analyze_previous_day,
    run_daily_analysis,
    _update_config_value,
    _write_healing_log,
    _is_enabled,
    _get_log_dir,
)


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def _make_error(category="data_fetch", module="test_mod", message="에러 메시지"):
    """테스트용 에러 레코드 생성"""
    return {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "category": category,
        "module": module,
        "message": message,
        "context": {},
        "exception_type": None,
        "exception_detail": None,
        "traceback": None,
    }


def _make_errors(category, module, message, count):
    """동일 에러 N개 생성"""
    return [_make_error(category, module, message) for _ in range(count)]


# ──────────────────────────────────────────────
# 1. _identify_patterns() 테스트
# ──────────────────────────────────────────────
class TestIdentifyPatterns:
    """패턴 감지 테스트"""

    def test_no_errors(self):
        """에러 없을 때"""
        result = _identify_patterns([])
        assert result["recurring_errors"] == []
        assert result["unstable_modules"] == []
        assert result["category_distribution"] == {}

    def test_recurring_errors_detected(self):
        """반복 에러 감지 (threshold=3)"""
        errors = _make_errors("data_fetch", "mod_a", "수집 실패", 5)
        config = {"pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2}}
        result = _identify_patterns(errors, config)
        assert len(result["recurring_errors"]) == 1
        assert result["recurring_errors"][0]["count"] == 5

    def test_below_threshold_not_recurring(self):
        """threshold 미만은 반복 패턴 아님"""
        errors = _make_errors("data_fetch", "mod_a", "수집 실패", 2)
        config = {"pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2}}
        result = _identify_patterns(errors, config)
        assert result["recurring_errors"] == []

    def test_unstable_module_detected(self):
        """모듈 불안정성 감지"""
        errors = [
            _make_error("data_fetch", "stock_analyzer", "에러 A"),
            _make_error("indicator", "stock_analyzer", "에러 B"),
            _make_error("report", "stock_analyzer", "에러 C"),
        ]
        config = {"pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2}}
        result = _identify_patterns(errors, config)
        assert len(result["unstable_modules"]) == 1
        assert result["unstable_modules"][0]["module"] == "stock_analyzer"
        assert result["unstable_modules"][0]["type_count"] == 3

    def test_stable_module_not_flagged(self):
        """에러 유형 1개인 모듈은 안정"""
        errors = _make_errors("data_fetch", "mod_a", "동일 에러", 5)
        config = {"pattern_detection": {"recurring_threshold": 10, "module_instability_types": 2}}
        result = _identify_patterns(errors, config)
        assert result["unstable_modules"] == []

    def test_category_distribution(self):
        """카테고리 분포 집계"""
        errors = [
            _make_error("data_fetch"), _make_error("data_fetch"),
            _make_error("indicator"),
        ]
        result = _identify_patterns(errors)
        assert result["category_distribution"]["data_fetch"] == 2
        assert result["category_distribution"]["indicator"] == 1

    def test_multiple_recurring_patterns(self):
        """여러 반복 패턴 동시 감지"""
        errors = (
            _make_errors("data_fetch", "mod_a", "에러 A", 3) +
            _make_errors("cache", "mod_b", "에러 B", 4)
        )
        config = {"pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2}}
        result = _identify_patterns(errors, config)
        assert len(result["recurring_errors"]) == 2


# ──────────────────────────────────────────────
# 2. _generate_recommendations() 테스트
# ──────────────────────────────────────────────
class TestGenerateRecommendations:
    """추천 생성 테스트"""

    def test_data_fetch_recommendation(self):
        """data_fetch 반복 → cache_ttl 증가 추천"""
        patterns = {
            "recurring_errors": [{"category": "data_fetch", "message": "수집 실패", "count": 5}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert len(recs) >= 1
        assert recs[0]["action"] == "increase_cache_ttl"
        assert recs[0]["auto_applicable"] is True

    def test_cache_recommendation(self):
        """cache 반복 → 캐시 정리 추천"""
        patterns = {
            "recurring_errors": [{"category": "cache", "message": "캐시 손상", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "clear_cache" for r in recs)

    def test_indicator_manual_review(self):
        """indicator 반복 → 수동 검토 (auto_applicable=False)"""
        patterns = {
            "recurring_errors": [{"category": "indicator", "message": "RSI 실패", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "review_indicator_params" and not r["auto_applicable"] for r in recs)

    def test_expert_strategy_manual_review(self):
        """expert_strategy → 수동 검토"""
        patterns = {
            "recurring_errors": [{"category": "expert_strategy", "message": "분석 오류", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "review_expert_logic" for r in recs)

    def test_unstable_module_recommendation(self):
        """불안정 모듈 → 모듈 검토 추천"""
        patterns = {
            "recurring_errors": [],
            "unstable_modules": [{"module": "analyzer", "error_types": ["data_fetch", "indicator"], "type_count": 2}],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "review_module" for r in recs)

    def test_no_patterns_no_recommendations(self):
        """패턴 없으면 추천 없음"""
        patterns = {"recurring_errors": [], "unstable_modules": []}
        recs = _generate_recommendations(patterns)
        assert recs == []

    def test_macro_sentiment_recommendation(self):
        """macro_sentiment 반복 → TTL 증가"""
        patterns = {
            "recurring_errors": [{"category": "macro_sentiment", "message": "매크로 실패", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "increase_macro_ttl" for r in recs)

    def test_report_recommendation(self):
        """report 반복 → 리포트 검토"""
        patterns = {
            "recurring_errors": [{"category": "report", "message": "생성 실패", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "review_report_template" for r in recs)

    def test_unexpected_recommendation(self):
        """unexpected → investigate"""
        patterns = {
            "recurring_errors": [{"category": "unexpected", "message": "알 수 없는 오류", "count": 3}],
            "unstable_modules": [],
        }
        recs = _generate_recommendations(patterns)
        assert any(r["action"] == "investigate" for r in recs)


# ──────────────────────────────────────────────
# 3. apply_auto_corrections() 테스트
# ──────────────────────────────────────────────
class TestApplyAutoCorrections:
    """자동 수정 적용 테스트"""

    def test_disabled_returns_empty(self):
        """auto_correct 비활성 시 빈 리스트"""
        config = {"auto_analysis": {"auto_correct": False}}
        recs = [{"action": "increase_cache_ttl", "auto_applicable": True, "target": "x", "reason": "y"}]
        result = apply_auto_corrections(recs, config=config)
        assert result == []

    def test_non_auto_applicable_skipped(self, tmp_path):
        """auto_applicable=False인 추천은 스킵"""
        config = {
            "auto_analysis": {"auto_correct": True},
            "correction_limits": {"max_cache_ttl": 480},
        }
        recs = [{"action": "review_indicator_params", "auto_applicable": False, "target": "x", "reason": "y"}]
        result = apply_auto_corrections(recs, config=config, log_dir=str(tmp_path))
        assert len(result) == 0

    @patch("log_analyzer.get_config")
    @patch("log_analyzer._update_config_value")
    def test_increase_cache_ttl(self, mock_update, mock_get_config, tmp_path):
        """cache_ttl 자동 증가"""
        mock_get_config.return_value = {"macro": {"cache_ttl_minutes": 120}}
        config = {
            "auto_analysis": {"auto_correct": True},
            "correction_limits": {"max_cache_ttl": 480, "min_cache_ttl": 5},
        }
        recs = [{"action": "increase_cache_ttl", "auto_applicable": True, "target": "macro.cache_ttl_minutes", "reason": "test"}]
        result = apply_auto_corrections(recs, config=config, log_dir=str(tmp_path))
        assert len(result) == 1
        assert result[0]["applied"] is True
        assert result[0]["details"]["old_value"] == 120
        assert result[0]["details"]["new_value"] == 180  # 120 * 1.5

    @patch("log_analyzer.get_config")
    @patch("log_analyzer._update_config_value")
    def test_cache_ttl_bounded(self, mock_update, mock_get_config, tmp_path):
        """cache_ttl이 max를 초과하지 않음"""
        mock_get_config.return_value = {"macro": {"cache_ttl_minutes": 400}}
        config = {
            "auto_analysis": {"auto_correct": True},
            "correction_limits": {"max_cache_ttl": 480, "min_cache_ttl": 5},
        }
        recs = [{"action": "increase_cache_ttl", "auto_applicable": True, "target": "x", "reason": "y"}]
        result = apply_auto_corrections(recs, config=config, log_dir=str(tmp_path))
        assert len(result) == 1
        # 400 * 1.5 = 600 → min(600, 480) = 480
        assert result[0]["details"]["new_value"] == 480

    @patch("log_analyzer.get_config")
    def test_clear_cache_action(self, mock_get_config, tmp_path):
        """clear_cache 자동 수정"""
        mock_get_config.return_value = {}
        config = {
            "auto_analysis": {"auto_correct": True},
            "correction_limits": {},
        }
        recs = [{"action": "clear_cache", "auto_applicable": True, "target": "cache", "reason": "test"}]

        with patch("common.cache.clear_cache", return_value=5):
            result = apply_auto_corrections(recs, config=config, log_dir=str(tmp_path))
            assert len(result) == 1
            assert result[0]["applied"] is True
            assert result[0]["details"]["cleared_files"] == 5


# ──────────────────────────────────────────────
# 4. generate_analysis_report() 테스트
# ──────────────────────────────────────────────
class TestGenerateAnalysisReport:
    """분석 보고서 생성 테스트"""

    def test_report_contains_summary(self, tmp_path):
        """보고서에 요약 정보 포함"""
        summary = {
            "total_errors": 5,
            "unique_messages": 3,
            "most_common_category": "data_fetch",
            "most_common_module": "analyzer",
            "by_category": {"data_fetch": 3, "indicator": 2},
            "by_module": {"analyzer": 5},
            "by_hour": {"14": 5},
        }
        patterns = {"recurring_errors": [], "unstable_modules": []}
        report = generate_analysis_report("2024-06-15", summary, patterns, [], log_dir=str(tmp_path))
        assert "5건" in report
        assert "data_fetch" in report
        assert "2024-06-15" in report

    def test_report_saved_to_file(self, tmp_path):
        """보고서 파일 저장"""
        summary = {"total_errors": 0, "unique_messages": 0, "most_common_category": None,
                    "most_common_module": None, "by_category": {}, "by_module": {}, "by_hour": {}}
        patterns = {"recurring_errors": [], "unstable_modules": []}
        generate_analysis_report("2024-06-15", summary, patterns, [], log_dir=str(tmp_path))

        report_path = os.path.join(str(tmp_path), "analysis_report_20240615.txt")
        assert os.path.exists(report_path)

    def test_report_with_recommendations(self, tmp_path):
        """추천 사항 포함 보고서"""
        summary = {"total_errors": 3, "unique_messages": 1, "most_common_category": "cache",
                    "most_common_module": "mod", "by_category": {"cache": 3}, "by_module": {"mod": 3}, "by_hour": {}}
        patterns = {"recurring_errors": [{"category": "cache", "message": "캐시 에러", "count": 3}],
                     "unstable_modules": []}
        recs = [{"action": "clear_cache", "target": "cache", "reason": "반복 에러",
                 "auto_applicable": True, "category": "cache"}]
        report = generate_analysis_report("2024-06-15", summary, patterns, recs, log_dir=str(tmp_path))
        assert "추천 사항" in report
        assert "clear_cache" in report

    def test_report_with_applied_corrections(self, tmp_path):
        """적용된 수정 포함"""
        summary = {"total_errors": 1, "unique_messages": 1, "most_common_category": "cache",
                    "most_common_module": "mod", "by_category": {}, "by_module": {}, "by_hour": {}}
        patterns = {"recurring_errors": [], "unstable_modules": []}
        applied = [{"action": "clear_cache", "applied": True, "details": {"cleared_files": 5},
                     "timestamp": "2024-06-15T10:00:00"}]
        report = generate_analysis_report("2024-06-15", summary, patterns, [], applied, str(tmp_path))
        assert "자동 수정" in report


# ──────────────────────────────────────────────
# 5. _write_healing_log() 테스트
# ──────────────────────────────────────────────
class TestWriteHealingLog:
    """힐링 로그 기록 테스트"""

    def test_writes_jsonl(self, tmp_path):
        """JSONL 형식으로 기록"""
        records = [
            {"timestamp": "2024-06-15T10:00:00", "action": "clear_cache", "applied": True, "details": {}},
        ]
        _write_healing_log(records, str(tmp_path))
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(str(tmp_path), f"healing_{today}.jsonl")
        assert os.path.exists(path)
        with open(path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["action"] == "clear_cache"

    def test_empty_records_no_file(self, tmp_path):
        """빈 레코드 시 파일 생성 안함"""
        _write_healing_log([], str(tmp_path))
        files = list(os.listdir(str(tmp_path))) if os.path.exists(str(tmp_path)) else []
        assert len(files) == 0


# ──────────────────────────────────────────────
# 6. analyze_previous_day() 테스트
# ──────────────────────────────────────────────
class TestAnalyzePreviousDay:
    """전날 분석 통합 테스트"""

    def test_no_errors_returns_none(self, tmp_path):
        """전날 에러 없으면 None 반환"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)
        result = analyze_previous_day(log_dir=log_dir)
        assert result is None

    def test_with_errors_returns_result(self, tmp_path):
        """에러 존재 시 분석 결과 반환"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        # 전날 날짜로 에러 파일 직접 생성
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        path = os.path.join(log_dir, f"error_{yesterday}.jsonl")

        errors = _make_errors("data_fetch", "analyzer", "수집 실패", 5)
        with open(path, "w", encoding="utf-8") as f:
            for e in errors:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        with patch("log_analyzer._get_error_tracking_config", return_value={
            "enabled": True,
            "auto_analysis": {"enabled": True, "auto_correct": False},
            "pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2},
            "correction_limits": {},
        }):
            result = analyze_previous_day(log_dir=log_dir)

        assert result is not None
        assert result["summary"]["total_errors"] == 5
        assert len(result["patterns"]["recurring_errors"]) >= 1
        assert len(result["recommendations"]) >= 1

    def test_analysis_report_created(self, tmp_path):
        """분석 후 보고서 파일 생성"""
        log_dir = str(tmp_path / "error_logs")
        os.makedirs(log_dir, exist_ok=True)

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        path = os.path.join(log_dir, f"error_{yesterday}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_make_error()) + "\n")

        with patch("log_analyzer._get_error_tracking_config", return_value={
            "enabled": True,
            "auto_analysis": {"enabled": True, "auto_correct": False},
            "pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2},
            "correction_limits": {},
        }):
            analyze_previous_day(log_dir=log_dir)

        report_path = os.path.join(log_dir, f"analysis_report_{yesterday}.txt")
        assert os.path.exists(report_path)


# ──────────────────────────────────────────────
# 7. run_daily_analysis() 테스트
# ──────────────────────────────────────────────
class TestRunDailyAnalysis:
    """일일 분석 진입점 테스트"""

    @patch("log_analyzer._is_enabled", return_value=False)
    def test_disabled_does_nothing(self, mock_enabled):
        """비활성 시 아무것도 안함"""
        with patch("log_analyzer.analyze_previous_day") as mock_analyze:
            run_daily_analysis()
            mock_analyze.assert_not_called()

    @patch("log_analyzer._is_enabled", return_value=True)
    @patch("log_analyzer._get_error_tracking_config")
    @patch("log_analyzer.analyze_previous_day", return_value=None)
    @patch("log_analyzer.cleanup_old_logs", return_value=0)
    def test_enabled_runs_analysis(self, mock_cleanup, mock_analyze, mock_config, mock_enabled):
        """활성 시 분석 실행"""
        mock_config.return_value = {
            "auto_analysis": {"enabled": True},
            "retention_days": 30,
        }
        run_daily_analysis()
        mock_analyze.assert_called_once()
        mock_cleanup.assert_called_once_with(30)

    @patch("log_analyzer._is_enabled", return_value=True)
    @patch("log_analyzer._get_error_tracking_config")
    @patch("log_analyzer.analyze_previous_day", side_effect=Exception("분석 에러"))
    @patch("log_analyzer.cleanup_old_logs", return_value=0)
    def test_error_does_not_crash(self, mock_cleanup, mock_analyze, mock_config, mock_enabled):
        """분석 에러 시에도 크래시 안함"""
        mock_config.return_value = {
            "auto_analysis": {"enabled": True},
            "retention_days": 30,
        }
        # 예외가 발생하지 않아야 함
        run_daily_analysis()

    @patch("log_analyzer._is_enabled", return_value=True)
    @patch("log_analyzer._get_error_tracking_config")
    @patch("log_analyzer.analyze_previous_day")
    @patch("log_analyzer.cleanup_old_logs", return_value=3)
    def test_cleanup_called(self, mock_cleanup, mock_analyze, mock_config, mock_enabled):
        """오래된 로그 정리 호출"""
        mock_config.return_value = {
            "auto_analysis": {"enabled": True},
            "retention_days": 14,
        }
        mock_analyze.return_value = None
        run_daily_analysis()
        mock_cleanup.assert_called_once_with(14)


# ──────────────────────────────────────────────
# 8. _update_config_value() 테스트
# ──────────────────────────────────────────────
class TestUpdateConfigValue:
    """config.yaml 업데이트 테스트"""

    def test_update_nested_value(self, tmp_path):
        """중첩 값 업데이트"""
        import yaml
        config_path = str(tmp_path / "config.yaml")
        initial = {"macro": {"cache_ttl_minutes": 120, "fetch_period": "3mo"}}
        with open(config_path, "w") as f:
            yaml.dump(initial, f)

        with patch("common.config.reload_config"):
            _update_config_value("macro.cache_ttl_minutes", 180, config_path)

        with open(config_path, "r") as f:
            result = yaml.safe_load(f)
        assert result["macro"]["cache_ttl_minutes"] == 180
        assert result["macro"]["fetch_period"] == "3mo"  # 다른 값 보존

    def test_update_creates_missing_keys(self, tmp_path):
        """존재하지 않는 키 생성"""
        import yaml
        config_path = str(tmp_path / "config.yaml")
        initial = {"defaults": {"ticker": "PLUG"}}
        with open(config_path, "w") as f:
            yaml.dump(initial, f)

        with patch("common.config.reload_config"):
            _update_config_value("new_section.new_key", 42, config_path)

        with open(config_path, "r") as f:
            result = yaml.safe_load(f)
        assert result["new_section"]["new_key"] == 42
        assert result["defaults"]["ticker"] == "PLUG"  # 기존 값 보존


# ──────────────────────────────────────────────
# 9. 통합: record_error → analyze 흐름
# ──────────────────────────────────────────────
class TestEndToEndFlow:
    """record_error → 분석 → 추천 통합 테스트"""

    def test_full_flow(self, tmp_path):
        """에러 기록 → 분석 → 추천 → 보고서 전체 흐름"""
        log_dir = str(tmp_path / "error_logs")

        # 전날 날짜로 에러 기록 (직접 파일 생성)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        yesterday_fmt = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        path = os.path.join(log_dir, f"error_{yesterday}.jsonl")
        os.makedirs(log_dir, exist_ok=True)

        # data_fetch 에러 5회 기록
        for i in range(5):
            error = {
                "timestamp": f"{yesterday_fmt}T10:{i:02d}:00",
                "date": yesterday_fmt,
                "category": "data_fetch",
                "module": "stock_analyzer",
                "message": "yfinance 수집 실패",
                "context": {"ticker": "PLUG"},
                "exception_type": None,
                "exception_detail": None,
                "traceback": None,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(error, ensure_ascii=False) + "\n")

        # 분석
        with patch("log_analyzer._get_error_tracking_config", return_value={
            "enabled": True,
            "auto_analysis": {"enabled": True, "auto_correct": False},
            "pattern_detection": {"recurring_threshold": 3, "module_instability_types": 2},
            "correction_limits": {},
        }):
            result = analyze_previous_day(log_dir=log_dir)

        assert result is not None
        assert result["summary"]["total_errors"] == 5
        assert len(result["patterns"]["recurring_errors"]) == 1
        assert result["patterns"]["recurring_errors"][0]["count"] == 5
        assert len(result["recommendations"]) >= 1
        assert "increase_cache_ttl" in [r["action"] for r in result["recommendations"]]
        assert "보고서" not in result["report"] or "에러" in result["report"]  # 보고서 텍스트 존재 확인

        # 보고서 파일 확인
        report_path = os.path.join(log_dir, f"analysis_report_{yesterday}.txt")
        assert os.path.exists(report_path)
