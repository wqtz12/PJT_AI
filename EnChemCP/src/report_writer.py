"""
결과 저장 모듈 (report_writer.py)

3종 엑셀을 각각 별도 파일로 저장한다:
  1) 주간비교 — 금주 vs 전주 정제 데이터 비교
  2) 월간비교 — 당월 vs 전월 비교
  3) 작업데이터 — 동일 주차 이전 버전 대비 비교
"""
import os
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)


class ReportWriter:
    """3종 엑셀 리포트를 결과데이터 폴더에 저장하는 클래스."""

    def __init__(self, result_dir: Path):
        self.result_dir = result_dir
        os.makedirs(self.result_dir, exist_ok=True)

    def _write_excel(
        self,
        filename: str,
        sheets: Dict[str, pd.DataFrame],
    ) -> Path:
        """
        여러 시트를 가진 엑셀 파일을 저장한다.

        Args:
            filename: 파일명
            sheets: {시트명: DataFrame} 딕셔너리

        Returns:
            Path: 저장된 파일 경로
        """
        out_path = self.result_dir / filename
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            for sheet_name, df in sheets.items():
                if df is not None and not df.empty:
                    # 시트명 31자 제한
                    safe_name = sheet_name[:31]
                    df.to_excel(writer, sheet_name=safe_name, index=False)
        logger.info("엑셀 저장: %s (%d 시트)", out_path, len(sheets))

        # 보고서 스타일 적용
        from src.excel_styler import style_workbook
        style_workbook(str(out_path))

        return out_path

    # ────────── 1) 주간비교 엑셀 ──────────

    def write_weekly_report(
        self,
        identifier: str,
        df_curr: pd.DataFrame,
        df_prev: pd.DataFrame,
        group_totals_curr: Dict[str, pd.DataFrame],
        group_totals_prev: Dict[str, pd.DataFrame],
        project_totals_curr: pd.DataFrame,
        project_totals_prev: pd.DataFrame,
        df_diff: pd.DataFrame,
    ) -> Path:
        """
        주간비교 엑셀을 저장한다.
        시트: 금주원본, 전주원본, 고객사별비교, WBS유형별비교, PM별비교,
              Sold별비교, 프로젝트별비교, 변동분석

        Args:
            identifier: 주차 식별자
            df_curr/df_prev: 가공 완료 DataFrame
            group_totals_curr/prev: 그룹별 합계
            project_totals_curr/prev: 프로젝트별 합계
            df_diff: 전주 대비 변동 분석
        """
        sheets: Dict[str, pd.DataFrame] = {
            '금주데이터': df_curr,
            '전주데이터': df_prev,
        }

        # 그룹별 비교 (금주 vs 전주)
        from src.aggregator import DataAggregator
        for label in ['고객사별', 'WBS유형별', 'PM별', 'Sold별']:
            curr_df = group_totals_curr.get(label, pd.DataFrame())
            prev_df = group_totals_prev.get(label, pd.DataFrame())
            if not curr_df.empty or not prev_df.empty:
                diff_df = DataAggregator.calculate_diff(
                    curr_df, prev_df,
                    label_current='금주', label_previous='전주',
                )
                sheets[f'{label}비교'] = diff_df if not diff_df.empty else curr_df

        # 프로젝트별 비교
        if not project_totals_curr.empty or not project_totals_prev.empty:
            proj_diff = DataAggregator.calculate_diff(
                project_totals_curr, project_totals_prev,
                label_current='금주', label_previous='전주',
            )
            sheets['프로젝트별비교'] = proj_diff if not proj_diff.empty else project_totals_curr

        # 변동분석 (임계치 초과)
        if not df_diff.empty:
            sheets['변동분석'] = df_diff

        return self._write_excel(f'{identifier}_주간비교.xlsx', sheets)

    # ────────── 2) 월간비교 엑셀 ──────────

    def write_monthly_report(
        self,
        identifier: str,
        df_curr: pd.DataFrame,
        df_prev: pd.DataFrame,
        period_totals_curr: Dict[str, pd.DataFrame],
        period_totals_prev: Dict[str, pd.DataFrame],
    ) -> Path:
        """
        월간비교 엑셀을 저장한다.
        시트: 당월데이터, 전월데이터, 분기별비교, 월별비교
        """
        sheets: Dict[str, pd.DataFrame] = {
            '당월데이터': df_curr,
            '전월데이터': df_prev,
        }

        from src.aggregator import DataAggregator
        for label in ['분기별', '월별']:
            curr_df = period_totals_curr.get(label, pd.DataFrame())
            prev_df = period_totals_prev.get(label, pd.DataFrame())
            if not curr_df.empty or not prev_df.empty:
                diff_df = DataAggregator.calculate_diff(
                    curr_df, prev_df,
                    label_current='당월', label_previous='전월',
                )
                sheets[f'{label}비교'] = diff_df if not diff_df.empty else curr_df

        return self._write_excel(f'{identifier}_월간비교.xlsx', sheets)

    # ────────── 3) 작업데이터 (버전간 비교) ──────────

    def write_version_report(
        self,
        identifier: str,
        version: int,
        df_curr: pd.DataFrame,
        df_prev_version: Optional[pd.DataFrame],
        df_diff: pd.DataFrame,
    ) -> Path:
        """
        작업데이터 엑셀을 저장한다.
        동일 주차 내 이전 버전(v1→v2) 대비 비교.

        Args:
            identifier: 주차 식별자
            version: 현재 버전 번호 (1, 2, 3...)
            df_curr: 현재 가공 데이터
            df_prev_version: 이전 버전 가공 데이터 (없으면 None)
            df_diff: 버전간 변동 분석
        """
        sheets: Dict[str, pd.DataFrame] = {
            f'v{version}_데이터': df_curr,
        }

        if df_prev_version is not None and not df_prev_version.empty:
            sheets[f'v{version - 1}_데이터'] = df_prev_version

        if not df_diff.empty:
            sheets['버전변동분석'] = df_diff

        return self._write_excel(f'{identifier}_작업데이터_v{version}.xlsx', sheets)
