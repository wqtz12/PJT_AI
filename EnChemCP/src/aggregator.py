"""
집계 엔진 모듈 (aggregator.py)

요약손익계산서와 월별손익계산서의 가공 데이터를 사용하여
다차원 합계(연간/분기/월별, 고객사/WBS유형/PM/Sold/프로젝트별)를 산출한다.
"""
from typing import Dict, List, Optional

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)


class DataAggregator:
    """다차원 합계 산출 엔진."""

    # ──────── 기간별 합계 (연간/분기/월별) ────────

    @staticmethod
    def calculate_period_totals(
        df_weekly: pd.DataFrame,
        df_monthly: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        """
        연간/분기/월별 매출·영업이익 합계를 산출한다.

        Args:
            df_weekly: 주간 가공 데이터 (요약손익계산서 기반)
            df_monthly: 월별 가공 데이터 (월별손익계산서 기반)

        Returns:
            Dict[str, pd.DataFrame]: {'연간': df, '분기별': df, '월별': df}
        """
        result: Dict[str, pd.DataFrame] = {}

        # 연간 합계 — 요약손익계산서 기준
        if not df_weekly.empty:
            sr_annual = df_weekly[['수익', '영업이익', '비용']].sum()
            result['연간'] = pd.DataFrame([{
                '구분': '연간합계',
                '매출합계': sr_annual.get('수익', 0),
                '영업이익합계': sr_annual.get('영업이익', 0),
                '비용합계': sr_annual.get('비용', 0),
            }])

        # 분기별/월별 합계 — 월별손익계산서 기준
        if not df_monthly.empty:
            quarter_cols = [c for c in df_monthly.columns if '분기' in c]
            if quarter_cols:
                result['분기별'] = df_monthly[['WBS'] + quarter_cols].copy()

            month_revenue_cols = [c for c in df_monthly.columns if c.startswith('매출') and '월' in c and '합계' not in c]
            month_profit_cols = [c for c in df_monthly.columns if '정산전영업이익' in c and '월' in c and '합계' not in c]
            month_cols = month_revenue_cols + month_profit_cols
            if month_cols:
                result['월별'] = df_monthly[['WBS'] + month_cols].copy()

        logger.info("기간별 합계 산출 완료: 종류=%s", list(result.keys()))
        return result

    # ──────── 그룹별 합계 (고객사/WBS유형/PM/Sold) ────────

    @staticmethod
    def calculate_group_totals(
        df_weekly: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        """
        고객사/WBS유형/PM/Sold별 매출·영업이익 합계를 산출한다.

        Args:
            df_weekly: 주간 가공 데이터

        Returns:
            Dict[str, pd.DataFrame]: 그룹 키 → 합계 DataFrame
        """
        if df_weekly.empty:
            return {}

        result: Dict[str, pd.DataFrame] = {}
        sum_cols = ['수익', '영업이익', '비용']
        # 존재하는 합산 대상 컬럼만 사용
        valid_sum = [c for c in sum_cols if c in df_weekly.columns]

        group_keys = {
            '고객사별': '고객사',
            'WBS유형별': 'WBS유형코드',
            'PM별': '담당자',
            'Sold별': 'Sold코드',
        }

        for label, col in group_keys.items():
            if col in df_weekly.columns:
                df_grouped = (
                    df_weekly
                    .groupby(col, as_index=False)[valid_sum]
                    .sum()
                    .rename(columns={'수익': '매출합계', '영업이익': '영업이익합계', '비용': '비용합계'})
                )
                result[label] = df_grouped
                logger.info("%s 합계: %d건", label, len(df_grouped))

        return result

    # ──────── 프로젝트 코드별 합계 ────────

    @staticmethod
    def calculate_project_totals(
        df_weekly: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        프로젝트 코드(Object코드 그룹핑)별 매출·영업이익 합계를 산출한다.

        Args:
            df_weekly: 주간 가공 데이터

        Returns:
            pd.DataFrame: 프로젝트 코드별 합계
        """
        if df_weekly.empty or '프로젝트코드' not in df_weekly.columns:
            return pd.DataFrame()

        sum_cols = [c for c in ['수익', '영업이익', '비용'] if c in df_weekly.columns]

        df_project = (
            df_weekly
            .groupby('프로젝트코드', as_index=False)[sum_cols]
            .sum()
            .rename(columns={'수익': '매출합계', '영업이익': '영업이익합계', '비용': '비용합계'})
        )

        logger.info("프로젝트코드별 합계: %d건", len(df_project))
        return df_project

    # ──────── 차이 계산 (전주/전월/이전버전 대비) ────────

    @staticmethod
    def calculate_diff(
        df_current: pd.DataFrame,
        df_previous: pd.DataFrame,
        label_current: str = '금주',
        label_previous: str = '전주',
    ) -> pd.DataFrame:
        """
        두 기간의 합계 데이터 차이를 계산한다.
        첫 번째 컬럼을 키로 merge 후 차이 컬럼을 추가한다.

        Args:
            df_current: 현재 기간 합계 DataFrame
            df_previous: 이전 기간 합계 DataFrame
            label_current: 현재 기간 라벨
            label_previous: 이전 기간 라벨

        Returns:
            pd.DataFrame: 차이 분석 DataFrame
        """
        if df_current.empty or df_previous.empty:
            logger.warning("비교 대상 중 하나가 비어있어 빈 DataFrame 반환")
            return pd.DataFrame()

        # 첫 번째 컬럼을 키로 사용
        key_col = df_current.columns[0]
        numeric_cols = df_current.select_dtypes(include='number').columns.tolist()

        df_merged = pd.merge(
            df_previous, df_current,
            on=key_col, how='outer',
            suffixes=(f'_{label_previous}', f'_{label_current}'),
        )

        # 숫자 컬럼 fillna
        for col in df_merged.select_dtypes(include='number').columns:
            df_merged[col] = df_merged[col].fillna(0)

        # 차이 컬럼 추가
        for col in numeric_cols:
            col_prev = f'{col}_{label_previous}'
            col_curr = f'{col}_{label_current}'
            if col_prev in df_merged.columns and col_curr in df_merged.columns:
                df_merged[f'{col}_차이'] = df_merged[col_curr] - df_merged[col_prev]

        logger.info("차이 계산 완료: %s vs %s → %d건", label_previous, label_current, len(df_merged))
        return df_merged
