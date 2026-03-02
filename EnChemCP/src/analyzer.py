"""
데이터 분석 모듈 (analyzer.py)

전주/금주 또는 전월/금월 데이터를 비교하여
기준 금액 이상 차이가 발생한 프로젝트를 검출한다.
"""
import pandas as pd
from typing import Dict, List

from src.utils import get_config, setup_logger

logger = setup_logger(__name__)

THRESHOLD_AMOUNT = float(get_config("THRESHOLD_AMOUNT", "1000000"))


class DataAnalyzer:
    """
    전주/금주 (혹은 전월/금월) 데이터를 비교 분석하는 클래스.
    """

    def __init__(self, threshold: float = THRESHOLD_AMOUNT):
        self.threshold = threshold

    # ────────────────── 비교 분석 ──────────────────

    def compare_data(
        self,
        df_prev: pd.DataFrame,
        df_curr: pd.DataFrame,
        key_column: str = 'WBS',
    ) -> pd.DataFrame:
        """
        전주/금주(또는 전월/금월) 매출·영업이익·비용 차이를 계산하고
        임계치를 초과하는 건만 필터링하여 반환한다.

        Args:
            df_prev (pd.DataFrame): 이전 기간 가공 데이터
            df_curr (pd.DataFrame): 현재 기간 가공 데이터
            key_column (str): Merge 기준 컬럼 (기본값: 'WBS')

        Returns:
            pd.DataFrame: 차이 분석 결과 (임계치 초과 건)
        """
        # Guard Clause
        if df_prev is None or df_curr is None:
            logger.error("비교 대상 DataFrame이 None입니다.")
            return pd.DataFrame()

        if df_prev.empty and df_curr.empty:
            logger.warning("양쪽 DataFrame 모두 비어 있습니다.")
            return pd.DataFrame()

        # 한쪽만 비어있어도 전량 변동으로 간주하여 비교 진행
        logger.info("데이터 비교 시작 (key=%s, threshold=₩%s)", key_column, f"{self.threshold:,.0f}")

        # Outer Merge — 신규/종료 프로젝트도 검출
        df_merged = pd.merge(
            df_prev,
            df_curr,
            on=key_column,
            how='outer',
            suffixes=('_prev', '_curr'),
        )

        # 숫자형 컬럼만 0으로 채움 (문자열 컬럼 보존)
        numeric_cols = df_merged.select_dtypes(include='number').columns
        df_merged[numeric_cols] = df_merged[numeric_cols].fillna(0)

        # 차액 계산 — 컬럼이 존재하는지 안전하게 확인
        has_revenue = '수익_prev' in df_merged.columns and '수익_curr' in df_merged.columns
        has_cost = '비용_prev' in df_merged.columns and '비용_curr' in df_merged.columns
        has_profit = '영업이익_prev' in df_merged.columns and '영업이익_curr' in df_merged.columns

        if has_revenue:
            df_merged = df_merged.assign(매출차이=lambda x: x['수익_curr'] - x['수익_prev'])
        if has_cost:
            df_merged = df_merged.assign(비용차이=lambda x: x['비용_curr'] - x['비용_prev'])
        if has_profit:
            df_merged = df_merged.assign(영업이익차이=lambda x: x['영업이익_curr'] - x['영업이익_prev'])

        # 차이 컬럼 중 존재하는 것만 필터 조건 구성
        diff_cols = [c for c in ['매출차이', '비용차이', '영업이익차이'] if c in df_merged.columns]
        if not diff_cols:
            logger.warning("차이 계산에 사용할 컬럼이 없습니다. 원본 컬럼명을 확인해 주세요.")
            return pd.DataFrame()

        # 임계치 초과 필터
        mask = pd.Series(False, index=df_merged.index)
        for col in diff_cols:
            mask = mask | (df_merged[col].abs() >= self.threshold)

        df_filtered = df_merged.loc[mask].copy()
        logger.info("임계치 초과 건수: %d / 전체 %d", len(df_filtered), len(df_merged))
        return df_filtered

    # ────────────────── PM별 알림 데이터 변환 ──────────────────

    def prepare_notification_records(self, df_diff: pd.DataFrame) -> Dict[str, List[dict]]:
        """
        PM별로 보낼 알림 대상 데이터를 딕셔너리로 변환한다.

        Args:
            df_diff (pd.DataFrame): 차이 분석 결과

        Returns:
            Dict[str, List[dict]]: {PM이름: [변동 내역 dict, ...]}
        """
        if df_diff.empty:
            return {}

        # PM 컬럼 결정 (Merge 후 suffix가 붙었을 수 있음)
        pm_column = None
        for candidate in ['PM_curr', 'PM_prev', 'PM']:
            if candidate in df_diff.columns:
                pm_column = candidate
                break

        if pm_column is None:
            logger.warning("PM 컬럼을 찾을 수 없습니다. 전체를 '미지정'으로 처리합니다.")
            return {"미지정": df_diff[['WBS']].to_dict('records')}

        # PM 값이 NaN이거나 0(fillna 결과)이면 '미지정'으로 치환
        df_diff = df_diff.copy()
        df_diff[pm_column] = df_diff[pm_column].apply(
            lambda v: '미지정' if pd.isna(v) or v == 0 or str(v).strip() == '' else str(v)
        )

        notification_map: Dict[str, List[dict]] = {}
        diff_detail_cols = [c for c in ['WBS', '매출차이', '비용차이', '영업이익차이'] if c in df_diff.columns]

        for pm_name, group_df in df_diff.groupby(pm_column):
            notification_map[str(pm_name)] = group_df[diff_detail_cols].to_dict('records')

        return notification_map
