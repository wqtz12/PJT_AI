"""
일일 에러 로그 분석 & 자동 수정 엔진

기능:
    - 전날 에러 로그 분석 (패턴 감지, 추천 생성)
    - 반복 에러 패턴 감지 (동일 에러 N회 이상)
    - 모듈 불안정성 감지 (같은 모듈 다수 에러 유형)
    - 자동 수정 적용 (config.yaml 안전 범위 내 조정)
    - 분석 보고서 & 힐링 로그 기록

사용법:
    from log_analyzer import run_daily_analysis
    run_daily_analysis()  # main() 시작 시 호출

파일 구조:
    output/error_logs/
        error_YYYYMMDD.jsonl       — 일일 에러 로그
        healing_YYYYMMDD.jsonl     — 자동 수정 기록
        analysis_report_YYYYMMDD.txt — 분석 보고서
"""
import json
import os
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional

from common.config import get_config
from common.error_tracker import (
    ErrorCategory,
    get_daily_errors,
    get_daily_summary,
    cleanup_old_logs,
    ERROR_LOG_DIR,
)

logger = logging.getLogger(__name__)

# ─── 기본 상수 ───
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_error_tracking_config() -> dict:
    """에러 추적 설정 조회"""
    cfg = get_config()
    return cfg.get("error_tracking", {})


def _is_enabled() -> bool:
    """에러 추적 기능 활성화 여부"""
    et_cfg = _get_error_tracking_config()
    return et_cfg.get("enabled", False)


def _get_log_dir() -> str:
    """에러 로그 디렉토리 경로"""
    et_cfg = _get_error_tracking_config()
    log_dir = et_cfg.get("log_dir", "output/error_logs")
    if os.path.isabs(log_dir):
        return log_dir
    return os.path.join(_BASE_DIR, log_dir)


# ──────────────────────────────────────────────
# 패턴 분석
# ──────────────────────────────────────────────
def _identify_patterns(errors: list, config: dict = None) -> dict:
    """
    에러 목록에서 패턴 감지

    Args:
        errors: 에러 레코드 리스트
        config: error_tracking 설정 (None이면 자동 로드)

    Returns:
        dict: {
            "recurring_errors": [...],      # 반복 에러 패턴
            "unstable_modules": [...],      # 불안정 모듈
            "category_distribution": {...}, # 카테고리 분포
        }
    """
    if config is None:
        config = _get_error_tracking_config()

    pd_cfg = config.get("pattern_detection", {})
    recurring_threshold = pd_cfg.get("recurring_threshold", 3)
    instability_threshold = pd_cfg.get("module_instability_types", 2)

    # ── 반복 에러 감지 (같은 category + message 조합) ──
    error_counts = {}
    for e in errors:
        key = (e.get("category", ""), e.get("message", ""))
        error_counts[key] = error_counts.get(key, 0) + 1

    recurring_errors = [
        {"category": cat, "message": msg, "count": cnt}
        for (cat, msg), cnt in error_counts.items()
        if cnt >= recurring_threshold
    ]

    # ── 모듈 불안정성 감지 (같은 모듈에서 다수 에러 유형) ──
    module_categories = {}
    for e in errors:
        mod = e.get("module", "unknown")
        cat = e.get("category", "unknown")
        if mod not in module_categories:
            module_categories[mod] = set()
        module_categories[mod].add(cat)

    unstable_modules = [
        {"module": mod, "error_types": list(cats), "type_count": len(cats)}
        for mod, cats in module_categories.items()
        if len(cats) >= instability_threshold
    ]

    # ── 카테고리 분포 ──
    category_distribution = {}
    for e in errors:
        cat = e.get("category", "unknown")
        category_distribution[cat] = category_distribution.get(cat, 0) + 1

    return {
        "recurring_errors": recurring_errors,
        "unstable_modules": unstable_modules,
        "category_distribution": category_distribution,
    }


def _generate_recommendations(patterns: dict) -> list:
    """
    감지된 패턴으로부터 수정 추천 생성

    Args:
        patterns: _identify_patterns() 결과

    Returns:
        list[dict]: 추천 목록 [{action, target, reason, auto_applicable}]
    """
    recommendations = []

    # ── 반복 에러 → 추천 ──
    for rec_err in patterns.get("recurring_errors", []):
        cat = rec_err["category"]
        msg = rec_err["message"]
        count = rec_err["count"]

        if cat == "data_fetch":
            recommendations.append({
                "action": "increase_cache_ttl",
                "target": "macro.cache_ttl_minutes",
                "reason": f"데이터 수집 에러 {count}회 반복 → 캐시 TTL 증가 권장",
                "auto_applicable": True,
                "category": cat,
            })
        elif cat == "cache":
            recommendations.append({
                "action": "clear_cache",
                "target": "cache",
                "reason": f"캐시 에러 {count}회 반복 → 캐시 정리 권장",
                "auto_applicable": True,
                "category": cat,
            })
        elif cat == "indicator":
            recommendations.append({
                "action": "review_indicator_params",
                "target": "indicators",
                "reason": f"지표 계산 에러 {count}회 반복: {msg[:50]}",
                "auto_applicable": False,
                "category": cat,
            })
        elif cat == "expert_strategy":
            recommendations.append({
                "action": "review_expert_logic",
                "target": "expert_strategies",
                "reason": f"전문가 전략 에러 {count}회 반복: {msg[:50]}",
                "auto_applicable": False,
                "category": cat,
            })
        elif cat == "macro_sentiment":
            recommendations.append({
                "action": "increase_macro_ttl",
                "target": "macro.cache_ttl_minutes",
                "reason": f"매크로/감성 에러 {count}회 반복 → TTL 증가 권장",
                "auto_applicable": True,
                "category": cat,
            })
        elif cat == "report":
            recommendations.append({
                "action": "review_report_template",
                "target": "report",
                "reason": f"리포트 생성 에러 {count}회 반복: {msg[:50]}",
                "auto_applicable": False,
                "category": cat,
            })
        else:
            recommendations.append({
                "action": "investigate",
                "target": "unknown",
                "reason": f"미분류 에러 {count}회 반복: {msg[:50]}",
                "auto_applicable": False,
                "category": cat,
            })

    # ── 불안정 모듈 → 추천 ──
    for unstable in patterns.get("unstable_modules", []):
        mod = unstable["module"]
        types = unstable["error_types"]
        recommendations.append({
            "action": "review_module",
            "target": mod,
            "reason": f"모듈 '{mod}'에서 {len(types)}가지 에러 유형 발생 → 안정성 검토 필요",
            "auto_applicable": False,
            "category": "module_instability",
        })

    return recommendations


# ──────────────────────────────────────────────
# 자동 수정
# ──────────────────────────────────────────────
def apply_auto_corrections(
    recommendations: list,
    config: dict = None,
    config_path: str = None,
    log_dir: str = None,
) -> list:
    """
    자동 적용 가능한 추천 사항을 config.yaml에 반영

    Args:
        recommendations: 추천 목록
        config: error_tracking 설정
        config_path: config.yaml 경로
        log_dir: 힐링 로그 디렉토리

    Returns:
        list[dict]: 적용된 수정 내역
    """
    if config is None:
        config = _get_error_tracking_config()

    auto_cfg = config.get("auto_analysis", {})
    if not auto_cfg.get("auto_correct", False):
        logger.info("자동 수정 비활성화 → 추천 사항만 기록")
        return []

    limits = config.get("correction_limits", {})
    max_cache_ttl = limits.get("max_cache_ttl", 480)
    min_cache_ttl = limits.get("min_cache_ttl", 5)

    applied = []
    full_config = get_config()

    for rec in recommendations:
        if not rec.get("auto_applicable", False):
            continue

        action = rec["action"]
        healing_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": rec["target"],
            "reason": rec["reason"],
            "applied": False,
            "details": {},
        }

        try:
            if action == "increase_cache_ttl":
                current_ttl = full_config.get("macro", {}).get("cache_ttl_minutes", 120)
                new_ttl = min(int(current_ttl * 1.5), max_cache_ttl)
                if new_ttl > current_ttl:
                    _update_config_value(
                        "macro.cache_ttl_minutes",
                        new_ttl,
                        config_path=config_path,
                    )
                    healing_record["applied"] = True
                    healing_record["details"] = {
                        "field": "macro.cache_ttl_minutes",
                        "old_value": current_ttl,
                        "new_value": new_ttl,
                    }
                    logger.info(f"자동 수정: cache_ttl {current_ttl} → {new_ttl}분")

            elif action == "increase_macro_ttl":
                current_ttl = full_config.get("macro", {}).get("cache_ttl_minutes", 120)
                new_ttl = min(int(current_ttl * 1.3), max_cache_ttl)
                if new_ttl > current_ttl:
                    _update_config_value(
                        "macro.cache_ttl_minutes",
                        new_ttl,
                        config_path=config_path,
                    )
                    healing_record["applied"] = True
                    healing_record["details"] = {
                        "field": "macro.cache_ttl_minutes",
                        "old_value": current_ttl,
                        "new_value": new_ttl,
                    }
                    logger.info(f"자동 수정: macro cache_ttl {current_ttl} → {new_ttl}분")

            elif action == "clear_cache":
                try:
                    from common.cache import clear_cache
                    cleared = clear_cache()
                    healing_record["applied"] = True
                    healing_record["details"] = {"cleared_files": cleared}
                    logger.info(f"자동 수정: 캐시 정리 ({cleared}개 파일)")
                except Exception as e:
                    healing_record["details"]["error"] = str(e)

        except Exception as e:
            healing_record["details"]["error"] = str(e)
            logger.warning(f"자동 수정 실패 ({action}): {e}")

        applied.append(healing_record)

    # 힐링 로그 기록
    _write_healing_log(applied, log_dir)

    return applied


def _update_config_value(dotted_key: str, value, config_path: str = None):
    """
    config.yaml의 특정 값을 안전하게 업데이트 (atomic write)

    Args:
        dotted_key: 점 표기 키 (e.g. "macro.cache_ttl_minutes")
        value: 새 값
        config_path: config.yaml 경로
    """
    if config_path is None:
        config_path = os.path.join(_BASE_DIR, "config.yaml")

    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML 미설치 → config 자동 수정 불가")
        return

    # 현재 config 로드
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    # 점 표기로 값 설정
    keys = dotted_key.split(".")
    target = config_data
    for k in keys[:-1]:
        if k not in target or not isinstance(target[k], dict):
            target[k] = {}
        target = target[k]
    target[keys[-1]] = value

    # atomic write (temp → rename)
    dir_name = os.path.dirname(config_path)
    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        shutil.move(tmp_path, config_path)
    except Exception:
        # 실패 시 임시 파일 정리
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    # 설정 캐시 무효화
    from common.config import reload_config
    reload_config(config_path)


def _write_healing_log(records: list, log_dir: str = None):
    """힐링 로그 기록"""
    if not records:
        return

    target_dir = log_dir or _get_log_dir()
    os.makedirs(target_dir, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    path = os.path.join(target_dir, f"healing_{today}.jsonl")

    try:
        with open(path, "a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning(f"힐링 로그 기록 실패: {e}")


# ──────────────────────────────────────────────
# 분석 보고서 생성
# ──────────────────────────────────────────────
def generate_analysis_report(
    date_str: str,
    summary: dict,
    patterns: dict,
    recommendations: list,
    applied: list = None,
    log_dir: str = None,
) -> str:
    """
    일일 분석 보고서 텍스트 생성 및 파일 저장

    Args:
        date_str: 분석 대상 날짜
        summary: 에러 요약 (get_daily_summary 결과)
        patterns: 패턴 분석 결과
        recommendations: 추천 목록
        applied: 적용된 수정 내역
        log_dir: 보고서 저장 디렉토리

    Returns:
        str: 보고서 텍스트
    """
    report = []
    report.append(f"{'═' * 60}")
    report.append(f"  에러 로그 일일 분석 보고서 — {date_str}")
    report.append(f"{'═' * 60}")
    report.append("")

    # 1. 요약
    report.append(f"▶ 에러 요약")
    report.append(f"  총 에러: {summary.get('total_errors', 0)}건")
    report.append(f"  고유 메시지: {summary.get('unique_messages', 0)}개")
    report.append(f"  최다 카테고리: {summary.get('most_common_category', 'N/A')}")
    report.append(f"  최다 모듈: {summary.get('most_common_module', 'N/A')}")
    report.append("")

    # 2. 카테고리별 분포
    by_cat = summary.get("by_category", {})
    if by_cat:
        report.append(f"▶ 카테고리별 분포")
        for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
            report.append(f"  {cat:25s}: {cnt}건")
        report.append("")

    # 3. 패턴 감지
    recurring = patterns.get("recurring_errors", [])
    unstable = patterns.get("unstable_modules", [])

    if recurring:
        report.append(f"▶ 반복 에러 패턴 ({len(recurring)}건)")
        for r in recurring:
            report.append(f"  [{r['category']}] {r['message'][:50]} — {r['count']}회")
        report.append("")

    if unstable:
        report.append(f"▶ 불안정 모듈 ({len(unstable)}건)")
        for u in unstable:
            report.append(f"  {u['module']}: {u['type_count']}가지 에러 유형 {u['error_types']}")
        report.append("")

    # 4. 추천 사항
    if recommendations:
        report.append(f"▶ 추천 사항 ({len(recommendations)}건)")
        for i, rec in enumerate(recommendations, 1):
            auto_mark = "✅ 자동적용" if rec.get("auto_applicable") else "📋 수동검토"
            report.append(f"  {i}. [{auto_mark}] {rec['action']}")
            report.append(f"     대상: {rec['target']}")
            report.append(f"     사유: {rec['reason']}")
        report.append("")

    # 5. 적용된 수정
    if applied:
        applied_true = [a for a in applied if a.get("applied")]
        if applied_true:
            report.append(f"▶ 자동 수정 적용 ({len(applied_true)}건)")
            for a in applied_true:
                details = a.get("details", {})
                report.append(f"  • {a['action']}: {details}")
            report.append("")

    report.append(f"{'═' * 60}")
    report_text = "\n".join(report)

    # 파일 저장
    target_dir = log_dir or _get_log_dir()
    os.makedirs(target_dir, exist_ok=True)
    date_compact = date_str.replace("-", "")
    report_path = os.path.join(target_dir, f"analysis_report_{date_compact}.txt")

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info(f"분석 보고서 저장: {report_path}")
    except Exception as e:
        logger.warning(f"분석 보고서 저장 실패: {e}")

    return report_text


# ──────────────────────────────────────────────
# 전날 분석 실행 (메인 진입점)
# ──────────────────────────────────────────────
def analyze_previous_day(
    log_dir: str = None,
    config_path: str = None,
) -> Optional[dict]:
    """
    전날 에러 로그를 분석하고 보고서 생성 + 자동 수정

    Args:
        log_dir: 에러 로그 디렉토리 (테스트용)
        config_path: config.yaml 경로 (테스트용)

    Returns:
        dict: 분석 결과 또는 None (에러 없음)
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    effective_log_dir = log_dir or _get_log_dir()

    # 전날 에러 로드
    errors = get_daily_errors(yesterday, effective_log_dir)
    if not errors:
        logger.info(f"전날({yesterday}) 에러 없음 → 분석 스킵")
        return None

    logger.info(f"전날({yesterday}) 에러 {len(errors)}건 분석 시작...")

    # 요약 생성
    summary = get_daily_summary(yesterday, effective_log_dir)

    # 패턴 감지
    et_config = _get_error_tracking_config()
    patterns = _identify_patterns(errors, et_config)

    # 추천 생성
    recommendations = _generate_recommendations(patterns)

    # 자동 수정
    applied = apply_auto_corrections(
        recommendations,
        config=et_config,
        config_path=config_path,
        log_dir=effective_log_dir,
    )

    # 보고서 생성
    report_text = generate_analysis_report(
        date_str=yesterday,
        summary=summary,
        patterns=patterns,
        recommendations=recommendations,
        applied=applied,
        log_dir=effective_log_dir,
    )

    logger.info(f"분석 완료: 패턴 {len(patterns.get('recurring_errors', []))}건, "
                f"추천 {len(recommendations)}건, "
                f"자동수정 {sum(1 for a in applied if a.get('applied'))}건")

    return {
        "date": yesterday,
        "summary": summary,
        "patterns": patterns,
        "recommendations": recommendations,
        "applied": applied,
        "report": report_text,
    }


def run_daily_analysis():
    """
    main() 시작 시 호출되는 일일 분석 진입점

    - error_tracking.enabled가 False이면 아무것도 하지 않음
    - 전날 에러 분석 + 자동 수정 + 오래된 로그 정리
    """
    if not _is_enabled():
        return

    logger.info("── 일일 에러 로그 분석 시작 ──")

    try:
        # 전날 분석
        et_config = _get_error_tracking_config()
        auto_cfg = et_config.get("auto_analysis", {})

        if auto_cfg.get("enabled", False):
            result = analyze_previous_day()
            if result:
                total = result["summary"]["total_errors"]
                applied_count = sum(1 for a in result.get("applied", []) if a.get("applied"))
                logger.info(f"  전날 에러 {total}건 분석 완료 (자동수정 {applied_count}건)")
            else:
                logger.info("  전날 에러 없음")

        # 오래된 로그 정리
        retention = et_config.get("retention_days", 30)
        deleted = cleanup_old_logs(retention)
        if deleted > 0:
            logger.info(f"  오래된 로그 {deleted}개 정리 (보관 {retention}일)")

    except Exception as e:
        # 분석 실패가 메인 파이프라인을 중단시키지 않도록
        logger.warning(f"일일 에러 분석 실패 (계속 진행): {e}")

    logger.info("── 일일 에러 로그 분석 완료 ──")
