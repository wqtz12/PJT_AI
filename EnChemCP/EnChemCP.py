"""
EnChemCP.py — Team Cost & Profit Closing System 메인 파이프라인

실행 방법:
    python EnChemCP.py --mode week --current 2026_1월_2주차 --previous 2026_1월_1주차
    python EnChemCP.py --mode month --current 2026_2월 --previous 2026_1월
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

import pandas as pd

# 프로젝트 루트를 sys.path에 추가하여 src 패키지 참조 보장
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import setup_logger
from src.processor import DataProcessor
from src.aggregator import DataAggregator
from src.analyzer import DataAnalyzer
from src.notifier import EmailNotifier
from src.history_tracker import HistoryTracker
from src.report_writer import ReportWriter

logger = setup_logger(__name__)

# PM → 이메일 매핑 (실 운영 시 DB나 설정 파일로 분리 권장)
PM_EMAIL_MAP = {
    "전병순": "jbs@example.com",
    "전병순 책임": "jbs@example.com",
    "미지정": "admin@example.com",
}


def parse_args() -> argparse.Namespace:
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(description="Team Cost & Profit Closing System")
    parser.add_argument("--mode", choices=["week", "month"], default="week",
                        help="마감 유형: week(주간) 또는 month(월간)")
    parser.add_argument("--current", type=str, default="2026_1월_2주차",
                        help="현재 기간 식별자")
    parser.add_argument("--previous", type=str, default="2026_1월_1주차",
                        help="이전 기간 식별자")
    parser.add_argument("--mock-email", action="store_true", default=True)
    parser.add_argument("--no-mock-email", dest="mock_email", action="store_false")
    return parser.parse_args()


def _resolve_paths(mode: str, identifier: str) -> tuple:
    """모드와 식별자로부터 원천/가공/결과 데이터 경로를 도출."""
    sub = "Week" if mode == "week" else "Month"
    dir_origin = PROJECT_ROOT / "data" / "원천데이터" / sub / identifier
    dir_processed = PROJECT_ROOT / "data" / "가공데이터" / sub / identifier
    dir_result = PROJECT_ROOT / "data" / "결과데이터" / identifier
    return dir_origin, dir_processed, dir_result


def _detect_version(dir_processed: Path) -> int:
    """
    가공데이터 폴더 내 기존 버전 파일을 탐색하여 다음 버전 번호를 반환한다.
    예: v1 존재 → 2 반환, 없으면 → 1 반환.
    """
    existing = list(dir_processed.glob("*_wbr_v*.xlsx"))
    if not existing:
        return 1

    versions = []
    for f in existing:
        match = re.search(r'_v(\d+)\.xlsx$', f.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) + 1 if versions else 1


def _load_previous_version(dir_processed: Path, current_version: int) -> tuple:
    """이전 버전 가공 데이터 로드. (version-1 파일이 있으면 반환)"""
    import pandas as pd

    if current_version <= 1:
        return None, 0

    prev_version = current_version - 1
    prev_files = list(dir_processed.glob(f"*_wbr_v{prev_version}.xlsx"))
    if not prev_files:
        return None, prev_version

    logger.info("이전 버전(v%d) 파일 로드: %s", prev_version, prev_files[0])
    return pd.read_excel(prev_files[0], engine='openpyxl'), prev_version


async def run_pipeline(args: argparse.Namespace) -> None:
    """메인 파이프라인."""
    logger.info("=" * 60)
    logger.info("EnChemCP Pipeline 시작 — mode=%s, current=%s, previous=%s",
                args.mode, args.current, args.previous)
    logger.info("=" * 60)

    # 경로 해석
    dir_origin_prev, dir_processed_prev, _ = _resolve_paths(args.mode, args.previous)
    dir_origin_curr, dir_processed_curr, dir_result = _resolve_paths(args.mode, args.current)

    # ──── Phase 1: Scraping (현재 비활성) ────
    logger.info("--- Phase 1: Scraping (현재 비활성) ---")

    # ──── Phase 2: Processing ────
    logger.info("--- Phase 2: Data Processing ---")
    processor_prev = DataProcessor(dir_origin_prev)
    processor_curr = DataProcessor(dir_origin_curr)

    if args.mode == "week":
        df_prev = processor_prev.process_weekly_data(args.previous)
        df_curr = processor_curr.process_weekly_data(args.current)

        # 월별손익계산서도 함께 처리 (같은 폴더 내 존재 시)
        df_monthly_prev = processor_prev.process_monthly_data(args.previous)
        df_monthly_curr = processor_curr.process_monthly_data(args.current)
    else:
        df_prev = processor_prev.process_monthly_data(args.previous)
        df_curr = processor_curr.process_monthly_data(args.current)
        df_monthly_prev = df_prev
        df_monthly_curr = df_curr

    # 버전 관리: 현재 버전 번호 결정
    version = _detect_version(dir_processed_curr)
    logger.info("현재 버전: v%d", version)

    # 가공 결과 저장 (final + 버전 파일)
    processor_curr.export_data(df_prev, dir_processed_prev / f"{args.previous}_wbr_final.xlsx")
    processor_curr.export_data(df_curr, dir_processed_curr / f"{args.current}_wbr_final.xlsx")
    processor_curr.export_data(df_curr, dir_processed_curr / f"{args.current}_wbr_v{version}.xlsx")

    # ──── Phase 3: Aggregation ────
    logger.info("--- Phase 3: Aggregation ---")
    aggregator = DataAggregator()

    if args.mode == "week":
        # 그룹별 합계 (고객사/WBS유형/PM/Sold)
        group_totals_curr = aggregator.calculate_group_totals(df_curr)
        group_totals_prev = aggregator.calculate_group_totals(df_prev)

        # 프로젝트 코드별 합계
        project_totals_curr = aggregator.calculate_project_totals(df_curr)
        project_totals_prev = aggregator.calculate_project_totals(df_prev)

        # 기간별 합계 (연간/분기/월별)
        period_totals_curr = aggregator.calculate_period_totals(df_curr, df_monthly_curr)
        period_totals_prev = aggregator.calculate_period_totals(df_prev, df_monthly_prev)
    else:
        group_totals_curr = {}
        group_totals_prev = {}
        project_totals_curr = DataAggregator.calculate_project_totals(df_curr) if hasattr(df_curr, 'columns') and '프로젝트코드' in df_curr.columns else __import__('pandas').DataFrame()
        project_totals_prev = DataAggregator.calculate_project_totals(df_prev) if hasattr(df_prev, 'columns') and '프로젝트코드' in df_prev.columns else __import__('pandas').DataFrame()
        period_totals_curr = aggregator.calculate_period_totals(df_curr, df_monthly_curr)
        period_totals_prev = aggregator.calculate_period_totals(df_prev, df_monthly_prev)

    # ──── Phase 4: Analyzing ────
    logger.info("--- Phase 4: Analyzing ---")
    analyzer = DataAnalyzer()
    df_diff = analyzer.compare_data(df_prev, df_curr, key_column='WBS')

    # ──── Phase 5: Report Writing ────
    logger.info("--- Phase 5: Report Writing ---")
    report_writer = ReportWriter(dir_result)

    # 주간비교 시트를 결산_final에 통합하기 위한 dict 구성
    comparison_sheets = {}

    if args.mode == "week":
        # 그룹별 비교 시트 (고객사/WBS유형/PM/Sold/프로젝트)
        for label in ['고객사별', 'WBS유형별', 'PM별', 'Sold별']:
            curr_df = group_totals_curr.get(label, pd.DataFrame())
            prev_df = group_totals_prev.get(label, pd.DataFrame())
            if not curr_df.empty or not prev_df.empty:
                diff_df = aggregator.calculate_diff(
                    curr_df, prev_df,
                    label_current='금주', label_previous='전주',
                )
                comparison_sheets[f'{label}비교'] = diff_df if not diff_df.empty else curr_df

        # 프로젝트별 비교
        if not project_totals_curr.empty or not project_totals_prev.empty:
            proj_diff = aggregator.calculate_diff(
                project_totals_curr, project_totals_prev,
                label_current='금주', label_previous='전주',
            )
            comparison_sheets['프로젝트별비교'] = proj_diff if not proj_diff.empty else project_totals_curr

        # 전주 원본 데이터도 참조용으로 포함
        if not df_prev.empty:
            comparison_sheets['전주데이터'] = df_prev

        # 작업데이터 (이전 버전 비교)
        df_prev_version, prev_v = _load_previous_version(dir_processed_curr, version)
        if df_prev_version is not None:
            version_diff = analyzer.compare_data(df_prev_version, df_curr, key_column='WBS')
        else:
            version_diff = pd.DataFrame()

        report_writer.write_version_report(
            args.current, version, df_curr, df_prev_version, version_diff,
        )
    else:
        # 월간비교 엑셀 (별도 파일 유지)
        report_writer.write_monthly_report(
            args.current, df_curr, df_prev,
            period_totals_curr, period_totals_prev,
        )

    # ──── Phase 6: History ────
    logger.info("--- Phase 6: History ---")
    tracker = HistoryTracker(dir_result)
    tracker.add_record(args.current, df_diff)
    tracker.save_closing_excel(args.current, df_curr, df_diff, extra_sheets=comparison_sheets)

    # ──── Phase 7: Notification ────
    logger.info("--- Phase 7: Notification ---")
    notifier = EmailNotifier(is_mock=args.mock_email)
    notification_map = analyzer.prepare_notification_records(df_diff)

    for pm_name, records in notification_map.items():
        to_email = PM_EMAIL_MAP.get(pm_name, "admin@example.com")
        notifier.send_alert(to_email, pm_name, records, identifier=args.current)

    logger.info("=" * 60)
    logger.info("EnChemCP Pipeline 완료")
    logger.info("=" * 60)


def main() -> None:
    """엔트리 포인트."""
    args = parse_args()
    try:
        asyncio.run(run_pipeline(args))
    except Exception as e:
        logger.error("파이프라인 비정상 종료: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
