"""
이력 관리 모듈 (history_tracker.py)

프로젝트별 변동 사유를 입력받고, 매주 작업한 내용을 이력(JSON)으로 관리한다.
결과데이터 폴더에 주차별 결산 엑셀과 이력 JSON을 저장한다.
"""
import json
from typing import Dict
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)


class HistoryTracker:
    """
    주차/월별 작업 이력과 변동 사유를 JSON 파일로 관리하는 클래스.
    """

    def __init__(self, result_dir: Path):
        """
        Args:
            result_dir (Path): 결과데이터 저장 디렉토리 (예: data/결과데이터/2026_1월_2주차/)
        """
        self.result_dir = result_dir
        os.makedirs(self.result_dir, exist_ok=True)
        self.history_file = self.result_dir / "history.json"
        self._history = self._load_history()

    def _load_history(self) -> list:
        """기존 이력 파일이 있으면 로드, 없으면 빈 리스트 반환."""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_history(self) -> None:
        """현재 이력을 JSON 파일로 저장."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)
        logger.info("이력 파일 저장 완료: %s", self.history_file)

    def add_record(
        self,
        identifier: str,
        df_diff: pd.DataFrame,
        reason_map: Optional[dict] = None,
    ) -> None:
        """
        한 주차/월의 분석 결과를 이력에 추가한다.

        Args:
            identifier (str): 주차/월 구분자 (예: '2026_1월_2주차')
            df_diff (pd.DataFrame): 차이 분석 결과 DataFrame
            reason_map (dict, optional): WBS별 사유 딕셔너리 (예: {'P-101': '투입인력 증가'})
        """
        record = {
            "구분": identifier,
            "작업일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "변동건수": len(df_diff),
            "상세": [],
        }

        if not df_diff.empty:
            for _, row in df_diff.iterrows():
                wbs = row.get('WBS', '-')
                detail = {
                    "WBS": wbs,
                    "매출차이": int(row.get('매출차이', 0)),
                    "비용차이": int(row.get('비용차이', 0)),
                    "영업이익차이": int(row.get('영업이익차이', 0)),
                    "사유": reason_map.get(wbs, "사유 미입력") if reason_map else "사유 미입력",
                }
                record["상세"].append(detail)

        self._history.append(record)
        self._save_history()

    def save_closing_excel(
        self,
        identifier: str,
        df_processed: pd.DataFrame,
        df_diff: pd.DataFrame,
        extra_sheets: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> None:
        """
        결산 결과 엑셀을 결과데이터 폴더에 저장한다.
        주간비교 시트(고객사별비교, WBS유형별비교 등)도 함께 포함한다.

        Args:
            identifier (str): 구분자
            df_processed (pd.DataFrame): 가공 완료 데이터
            df_diff (pd.DataFrame): 차이 분석 결과
            extra_sheets (Dict, optional): 추가 시트 {시트명: DataFrame}
        """
        closing_file = self.result_dir / f"{identifier}_결산_final.xlsx"

        with pd.ExcelWriter(closing_file, engine='openpyxl') as writer:
            df_processed.to_excel(writer, sheet_name='가공데이터', index=False)
            if not df_diff.empty:
                df_diff.to_excel(writer, sheet_name='변동분석', index=False)
            # 주간비교 등 추가 시트 기록
            if extra_sheets:
                for sheet_name, df_sheet in extra_sheets.items():
                    if df_sheet is not None and not df_sheet.empty:
                        safe_name = sheet_name[:31]
                        df_sheet.to_excel(writer, sheet_name=safe_name, index=False)

        logger.info("결산 엑셀 저장 완료: %s", closing_file)

        # 보고서 스타일 적용 (테두리, 헤더 볼드, 음영, 숫자 포맷)
        from src.excel_styler import style_workbook
        style_workbook(str(closing_file))

    def get_history(self) -> list:
        """현재까지의 전체 이력을 반환한다."""
        return self._history
