"""
데이터 가공 및 정제 모듈 (processor.py)

원본 CSV/Excel(요약손익계산서, 월별손익계산서)을 로드하고
공통코드 매핑, 구분자 추가, 분기별 합산 등 가공 처리를 수행한다.

실제 원천데이터 컬럼 매핑:
  - 요약손익계산서 (Weekly): Object코드=WBS, 대표고객=고객사, 사업유형=WBS유형, 리더/PM=PM
  - 월별손익계산서 (Monthly): 매출 1월~12월, 정산전영업이익 1월~12월 등
"""
import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

# 설정 파일 로드 (PM 매핑, 프로젝트 코드 그룹핑)
CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'code_mappings.json'


def _load_config() -> dict:
    """config/code_mappings.json을 로드한다. 파일 없으면 빈 dict 반환."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    logger.warning("설정 파일 없음: %s", CONFIG_PATH)
    return {}


# ──────────────────────────────────────────────
# 원천데이터 → 가공데이터 컬럼 매핑 (요약손익계산서)
# ──────────────────────────────────────────────
WEEKLY_COLUMN_MAP = {
    'Object코드': 'WBS',
    'Object명': 'WBS명',
    'Object상세코드': 'WBS상세코드',
    'Object구분코드': 'Object구분코드',
    'obejct구분': 'Object구분',       # 원본 오타 그대로 보존
    '대표고객': '고객사명',
    '사업유형': 'WBS유형',
    '리더/PM': 'PM',
    '매출': '수익',
    '정산전영업이익': '영업이익',
    '정산후영업이익': '정산후영업이익',
    '총계약액': '총계약액',
    '공헌이익': '공헌이익',
    '한계이익': '한계이익',
    'WBS상태': 'WBS상태',
    'SOLD일자': 'Sold일자',
    '확정CP일자': '계약체결',
    'UD구분': 'UD구분',
    '작성자': '작성자',
    '구분': '원본구분',
}


# ──────────────────────────────────────────────
# 공통코드 매핑 함수
# ──────────────────────────────────────────────

def assign_customer_code(customer_name: str) -> str:
    """
    고객사 코드 매핑.
    LG에너지솔루션, LG화학, LG생활건강 외에는 '기타'로 분류.
    """
    if pd.isna(customer_name):
        return '기타'
    name = str(customer_name).strip()
    if '에너지솔루션' in name or '엔솔' in name or name == 'LGES':
        return 'LG에너지솔루션'
    elif '화학' in name or name == 'LGC':
        return 'LG화학'
    elif '생활건강' in name or name == 'LGHH':
        return 'LG생활건강'
    return '기타'


def assign_wbs_type_code(wbs_type: str) -> str:
    """WBS 유형 코드 정규화."""
    if pd.isna(wbs_type):
        return '미분류'
    return str(wbs_type).strip()


def classify_profit_rate(profit_rate: float) -> str:
    """이익률 구간 코드 매핑."""
    if pd.isna(profit_rate):
        return '미확인'
    if profit_rate >= 20:
        return '고수익'
    elif profit_rate >= 5:
        return '정상'
    elif profit_rate >= 0:
        return '저수익'
    return '적자'


def assign_sold_code(ud_value: str, wbs_type: str) -> str:
    """
    Sold 코드 매핑 — 비즈니스 규칙:
    UD구분=Y → UD, 사업유형 SI → SI, SM → SM.
    """
    ud = str(ud_value).strip() if not pd.isna(ud_value) else ''
    wbs = str(wbs_type).strip() if not pd.isna(wbs_type) else ''
    if ud.upper() == 'Y':
        return 'UD'
    if wbs == 'SI':
        return 'SI'
    if wbs == 'SM':
        return 'SM'
    return '기타'


def assign_contract_code(contract_value: str) -> str:
    """계약체결 코드 매핑 — 확정일자 존재 여부로 완료/미완료."""
    if pd.isna(contract_value) or str(contract_value).strip() == '':
        return '미완료'
    return '완료'


def assign_pm_mapping(pm_raw: str, pm_map: dict) -> str:
    """
    PM 사용자 정의 매핑.
    config/code_mappings.json의 pm_mapping을 참조하여 원본 PM → 표준 담당자명으로 변환.
    매핑이 없으면 원본 값 그대로 반환.
    """
    if pd.isna(pm_raw) or str(pm_raw).strip() == '':
        return '미지정'
    raw = str(pm_raw).strip()
    return pm_map.get(raw, raw)


def assign_project_code(wbs: str, wbs_detail: str) -> str:
    """
    프로젝트 코드 매핑 — Object코드 + Object상세코드를 그룹핑.
    같은 Object코드를 가진 상세코드들을 하나의 프로젝트 그룹으로 묶는다.
    """
    code = str(wbs).strip() if not pd.isna(wbs) else ''
    detail = str(wbs_detail).strip() if not pd.isna(wbs_detail) else ''
    if not code:
        return '미분류'
    # Object코드가 곧 프로젝트 코드 (상세코드 그룹핑 기준)
    return code


# ──────────────────────────────────────────────
# 파일 로드 유틸 (Guard Clause + CSV/XLSX 자동 감지)
# ──────────────────────────────────────────────

def _find_data_file(data_dir: Path, prefix: str) -> Optional[Path]:
    """
    디렉토리에서 prefix로 시작하는 파일을 자동 탐색한다.
    CSV와 XLSX 모두 지원. 가장 최신 파일을 반환.

    macOS는 한글 파일명을 NFD Unicode로 저장하므로
    NFC로 정규화하여 비교한다.

    Args:
        data_dir (Path): 탐색 대상 디렉토리
        prefix (str): 파일명 접두사 (예: '요약손익계산서')

    Returns:
        Optional[Path]: 찾은 파일 경로, 없으면 None
    """
    import unicodedata

    if not data_dir.exists():
        logger.warning("디렉토리가 존재하지 않습니다: %s", data_dir)
        return None

    # macOS NFD ↔ NFC 정규화 비교
    prefix_nfc = unicodedata.normalize('NFC', prefix)
    allowed_exts = {'.csv', '.xlsx'}

    found_files = []
    for f in data_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in allowed_exts:
            continue
        # 파일명을 NFC로 정규화하여 prefix 비교
        name_nfc = unicodedata.normalize('NFC', f.stem)
        if name_nfc.startswith(prefix_nfc):
            found_files.append(f)

    if not found_files:
        logger.warning("'%s*' 파일을 찾을 수 없습니다: %s", prefix, data_dir)
        return None

    latest = max(found_files, key=os.path.getmtime)
    logger.info("데이터 파일 발견: %s", latest)
    return latest


def _load_data_file(file_path: Path) -> Optional[pd.DataFrame]:
    """
    CSV 또는 XLSX 파일을 안전하게 로드한다.
    BOM(UTF-8-BOM) 인코딩을 자동 처리한다.

    Args:
        file_path (Path): 대상 파일 경로

    Returns:
        Optional[pd.DataFrame]: 로드된 DataFrame 또는 None
    """
    if not file_path.exists():
        logger.warning("파일이 존재하지 않습니다: %s", file_path)
        return None

    ext = file_path.suffix.lower()
    logger.info("파일 로드 중 (%s): %s", ext, file_path)

    if ext == '.csv':
        # BOM 처리를 위해 utf-8-sig 사용
        return pd.read_csv(file_path, encoding='utf-8-sig')
    elif ext == '.xlsx':
        return pd.read_excel(file_path, engine='openpyxl')
    else:
        logger.error("지원하지 않는 파일 형식: %s", ext)
        return None


# ──────────────────────────────────────────────
# 분기 합산 헬퍼 (월별손익계산서용)
# ──────────────────────────────────────────────

QUARTER_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12],
}


def _add_quarterly_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    월별 매출/정산전영업이익 컬럼을 분기별로 합산한다.
    컬럼 형식: '매출 1월', '매출 2월', ..., '정산전영업이익 1월', ...
    """
    for quarter, months in QUARTER_MONTHS.items():
        # 매출 분기합산
        revenue_cols = [f'매출 {m}월' for m in months if f'매출 {m}월' in df.columns]
        profit_cols = [f'정산전영업이익 {m}월' for m in months if f'정산전영업이익 {m}월' in df.columns]

        q_label = f'{quarter}분기'
        df = df.assign(**{
            f'{q_label}매출': df[revenue_cols].sum(axis=1) if revenue_cols else 0,
            f'{q_label}정산전영업이익': df[profit_cols].sum(axis=1) if profit_cols else 0,
        })

    return df


# ──────────────────────────────────────────────
# 메인 프로세서 클래스
# ──────────────────────────────────────────────

class DataProcessor:
    """원본 데이터를 읽고 정제, 가공 및 통합하는 프로세싱 클래스."""

    def __init__(self, data_path: Path):
        if not data_path.exists():
            logger.warning("데이터 경로가 존재하지 않습니다: %s", data_path)
        self.data_path = data_path

    # ─── 주간 요약손익계산서 ───

    def process_weekly_data(self, week_identifier: str) -> pd.DataFrame:
        """
        주간 요약손익계산서 데이터 로드 → 컬럼 매핑 → 공통코드 적용 → 정제.

        Args:
            week_identifier (str): 구분자 (예: '2026_1월_1주차')

        Returns:
            pd.DataFrame: 정제된 DataFrame
        """
        logger.info("주간 데이터 처리 시작: %s", week_identifier)

        # Guard Clause: 파일 탐색
        file_path = _find_data_file(self.data_path, "요약손익계산서")
        if file_path is None:
            logger.error("요약손익계산서 파일을 찾을 수 없습니다. 빈 DataFrame을 반환합니다.")
            return pd.DataFrame()

        df_raw = _load_data_file(file_path)
        if df_raw is None or df_raw.empty:
            logger.error("요약손익계산서 파일이 비어있습니다.")
            return pd.DataFrame()

        logger.info("원본 데이터 로드 완료: %d행 × %d열", len(df_raw), len(df_raw.columns))

        # 1. 컬럼 리네임 (원천 → 가공)
        rename_map = {k: v for k, v in WEEKLY_COLUMN_MAP.items() if k in df_raw.columns}
        df_renamed = df_raw.rename(columns=rename_map)

        # 2. 숫자형 컬럼 타입 보정 — CSV에서 콤마가 섞였을 수 있음
        numeric_targets = ['수익', '영업이익', '정산후영업이익', '총계약액', '공헌이익', '한계이익']
        for col in numeric_targets:
            if col in df_renamed.columns:
                df_renamed[col] = pd.to_numeric(
                    df_renamed[col].astype(str).str.replace(',', ''),
                    errors='coerce',
                ).fillna(0)

        # 3. Guard Clause: WBS 필수 컬럼 확인
        if 'WBS' not in df_renamed.columns:
            logger.error("'WBS'(Object코드) 컬럼이 없습니다. 원본 컬럼: %s", list(df_raw.columns[:10]))
            return pd.DataFrame()

        # 4. 사용자 정의 설정 로드
        config = _load_config()
        pm_map = config.get('pm_mapping', {})

        # 5. Method Chaining으로 공통코드 매핑 + 가공
        df_processed = (
            df_renamed
            .assign(주차=week_identifier)
            .assign(고객사=lambda x: x.get('고객사명', pd.Series('', index=x.index)).apply(assign_customer_code))
            .assign(WBS유형코드=lambda x: x.get('WBS유형', pd.Series('', index=x.index)).apply(assign_wbs_type_code))
            .assign(이익률=lambda x: (
                x['영업이익'].div(x['수익'].replace(0, pd.NA)) * 100
            ).fillna(0).round(2))
            .assign(이익률등급=lambda x: x['이익률'].apply(classify_profit_rate))
            .assign(Sold코드=lambda x: x.apply(
                lambda row: assign_sold_code(
                    row.get('UD구분', ''),
                    row.get('WBS유형', ''),
                ), axis=1))
            .assign(계약체결코드=lambda x: x.get('계약체결', pd.Series('', index=x.index)).apply(assign_contract_code))
            .assign(담당자=lambda x: x.get('PM', pd.Series('', index=x.index)).apply(
                lambda v: assign_pm_mapping(v, pm_map)))
            .assign(프로젝트코드=lambda x: x.apply(
                lambda row: assign_project_code(
                    row.get('WBS', ''),
                    row.get('WBS상세코드', ''),
                ), axis=1))
        )

        # 6. 비용 컬럼 산출 (원본에 없으므로: 비용 = 매출 - 영업이익)
        if '비용' not in df_processed.columns:
            df_processed = df_processed.assign(비용=lambda x: x['수익'] - x['영업이익'])

        logger.info("주간 데이터 처리 완료: %d건", len(df_processed))
        return df_processed

    # ─── 월별 손익계산서 ───

    def process_monthly_data(self, month_identifier: str) -> pd.DataFrame:
        """
        월별 손익계산서 데이터 로드 → 분기별 합산 → 공통코드 적용.

        Args:
            month_identifier (str): 구분자 (예: '2026_1월')

        Returns:
            pd.DataFrame: 분기별 합산이 포함된 DataFrame
        """
        logger.info("월별 데이터 처리 시작: %s", month_identifier)

        file_path = _find_data_file(self.data_path, "월별손익계산서")
        if file_path is None:
            logger.error("월별손익계산서 파일을 찾을 수 없습니다.")
            return pd.DataFrame()

        df_raw = _load_data_file(file_path)
        if df_raw is None or df_raw.empty:
            logger.error("월별손익계산서 파일이 비어있습니다.")
            return pd.DataFrame()

        logger.info("원본 데이터 로드 완료: %d행 × %d열", len(df_raw), len(df_raw.columns))

        # 숫자형 컬럼 변환 (매출 1월 ~ 정산전영업이익 12월)
        month_pattern_cols = [c for c in df_raw.columns if any(
            kw in c for kw in ['매출', '공헌이익', '한계이익', '정산전영업이익', '정산후영업이익']
        )]
        for col in month_pattern_cols:
            df_raw[col] = pd.to_numeric(
                df_raw[col].astype(str).str.replace(',', ''),
                errors='coerce',
            ).fillna(0)

        # WBS 컬럼 매핑 (월별손익계산서도 Object코드 사용)
        rename_map = {k: v for k, v in WEEKLY_COLUMN_MAP.items() if k in df_raw.columns}
        df_renamed = df_raw.rename(columns=rename_map)

        # 분기별 합산 컬럼 추가
        df_monthly = (
            _add_quarterly_columns(df_renamed)
            .assign(월=month_identifier)
            .assign(고객사=lambda x: x.get('고객사명', pd.Series('', index=x.index)).apply(assign_customer_code))
        )

        logger.info("월별 데이터 처리 완료: %d건", len(df_monthly))
        return df_monthly

    # ─── 엑셀 저장 ───

    def export_data(self, df_target: pd.DataFrame, output_path: Path) -> None:
        """가공된 DataFrame을 Excel 파일로 저장."""
        if df_target.empty:
            logger.warning("DataFrame이 비어 있어 저장을 건너뜁니다.")
            return

        os.makedirs(output_path.parent, exist_ok=True)
        logger.info("엑셀 파일 저장 중: %s", output_path)
        df_target.to_excel(output_path, index=False, engine='openpyxl')
        logger.info("저장 완료: %d행", len(df_target))
