"""
엑셀 스타일링 유틸 (excel_styler.py)

openpyxl을 사용하여 결산/비교 엑셀에
보고서 수준의 스타일(테두리, 헤더 볼드, 음영, 숫자 포맷)을 적용한다.
"""
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
    numbers,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.utils import setup_logger

logger = setup_logger(__name__)

# ──────────────────────────────────────────────
# 디자인 토큰
# ──────────────────────────────────────────────

HEADER_FONT = Font(name='맑은 고딕', bold=True, size=10, color='FFFFFF')
DATA_FONT = Font(name='맑은 고딕', size=10)
HEADER_ALIGNMENT = Alignment(horizontal='center', vertical='center', wrap_text=True)
DATA_ALIGNMENT = Alignment(vertical='center', wrap_text=False)

# 테마 색상 정의 (매출=파랑, 영업이익=주황, 비용=초록, 일반=회색)
THEMES = {
    'revenue': {
        'header': PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid'),
        'zebra': PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='B4C6E7'), right=Side(style='thin', color='B4C6E7'),
            top=Side(style='thin', color='B4C6E7'), bottom=Side(style='thin', color='B4C6E7'),
        )
    },
    'profit': {
        'header': PatternFill(start_color='ED7D31', end_color='ED7D31', fill_type='solid'),
        'zebra': PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='F4B083'), right=Side(style='thin', color='F4B083'),
            top=Side(style='thin', color='F4B083'), bottom=Side(style='thin', color='F4B083'),
        )
    },
    'cost': {
        'header': PatternFill(start_color='548235', end_color='548235', fill_type='solid'),
        'zebra': PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='C6E0B4'), right=Side(style='thin', color='C6E0B4'),
            top=Side(style='thin', color='C6E0B4'), bottom=Side(style='thin', color='C6E0B4'),
        )
    },
    'default': {
        'header': PatternFill(start_color='595959', end_color='595959', fill_type='solid'),
        'zebra': PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'),
        )
    }
}

# 차이 양수/음수 강조 (양수=진파랑 글씨, 음수=빨강 글씨, 배경 없음)
POSITIVE_FONT = Font(name='맑은 고딕', bold=True, size=10, color='1F4E79')
NEGATIVE_FONT = Font(name='맑은 고딕', bold=True, size=10, color='CC0000')

# 얼룩말 패턴 (연한 회색 통일)
ZEBRA_LIGHT = PatternFill(start_color='F5F5F5', end_color='F5F5F5', fill_type='solid')

# 비교 시트 전용 — 기간 구분 헤더 테마 (전주=회색, 금주=파랑, 차이=보라)
PERIOD_THEMES = {
    'prev': {
        'header': PatternFill(start_color='808080', end_color='808080', fill_type='solid'),
        'zebra': PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'),
        )
    },
    'curr': {
        'header': PatternFill(start_color='00838F', end_color='00838F', fill_type='solid'),
        'zebra': PatternFill(start_color='E0F7FA', end_color='E0F7FA', fill_type='solid'),
        'border': Border(
            left=Side(style='thin', color='80CBC4'), right=Side(style='thin', color='80CBC4'),
            top=Side(style='thin', color='80CBC4'), bottom=Side(style='thin', color='80CBC4'),
        )
    },
    'diff': {
        'header': PatternFill(start_color='C0392B', end_color='C0392B', fill_type='solid'),
        'zebra': ZEBRA_LIGHT,
        'border': Border(
            left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'),
        )
    },
}

# 숫자 포맷 (천 단위 콤마)
NUMBER_FORMAT = '#,##0'
RATE_FORMAT = '#,##0.00'

# 전주/전월 = prev, 금주/당월 = curr 판별 키워드
_PREV_KEYWORDS = ('_전주', '_전월')
_CURR_KEYWORDS = ('_금주', '_당월')
_DIFF_KEYWORDS = ('_차이',)


def _get_theme_for_column(header_val: str, is_comparison: bool = False) -> dict:
    """컬럼 이름을 바탕으로 적용할 색상 테마를 반환한다."""
    h = str(header_val or '')

    # 비교 시트라면 기간 접미사 우선 판별 (전주/금주/차이)
    if is_comparison:
        if any(k in h for k in _PREV_KEYWORDS):
            return PERIOD_THEMES['prev']
        if any(k in h for k in _CURR_KEYWORDS):
            return PERIOD_THEMES['curr']
        if any(k in h for k in _DIFF_KEYWORDS):
            return PERIOD_THEMES['diff']

    # 일반 시트 — 매출/이익/비용 구분
    if '매출' in h or '수익' in h:
        return THEMES['revenue']
    if '이익' in h:
        return THEMES['profit']
    if '비용' in h:
        return THEMES['cost']
    return THEMES['default']


# ──────────────────────────────────────────────
# 스타일 적용 함수
# ──────────────────────────────────────────────

def style_worksheet(ws: Worksheet, is_comparison: bool = False) -> None:
    """
    워크시트에 보고서 스타일을 적용한다.

    Args:
        ws (Worksheet): 대상 워크시트
        is_comparison (bool): 비교 시트 여부 (차이 컬럼 강조 적용)
    """
    if ws.max_row is None or ws.max_row < 1:
        return

    max_col = ws.max_column or 1
    max_row = ws.max_row or 1

    # 컬럼별 테마 맵핑 수집 (인덱스)
    col_themes = {}
    diff_col_indices = set()

    for col_idx in range(1, max_col + 1):
        header_val = ws.cell(row=1, column=col_idx).value
        col_themes[col_idx] = _get_theme_for_column(header_val, is_comparison)
        if is_comparison and header_val and '차이' in str(header_val):
            diff_col_indices.add(col_idx)

    # 1. 헤더 스타일
    for col_idx in range(1, max_col + 1):
        cell = ws.cell(row=1, column=col_idx)
        theme = col_themes[col_idx]
        cell.font = HEADER_FONT
        cell.fill = theme['header']
        cell.alignment = HEADER_ALIGNMENT
        cell.border = theme['border']

    # 2. 데이터 행 스타일 + 얼룩말 패턴
    for row_idx in range(2, max_row + 1):
        is_even = (row_idx % 2 == 0)

        for col_idx in range(1, max_col + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            theme = col_themes[col_idx]
            cell.border = theme['border']
            cell.font = DATA_FONT
            cell.alignment = DATA_ALIGNMENT

            # 숫자 포맷 적용
            if isinstance(cell.value, (int, float)):
                header_val = str(ws.cell(row=1, column=col_idx).value or '')
                if '이익률' in header_val or '률' in header_val:
                    cell.number_format = RATE_FORMAT
                else:
                    cell.number_format = NUMBER_FORMAT

            # 차이 컬럼 양수/음수 강조 (비교 시트, 글씨색만 변경)
            if col_idx in diff_col_indices and isinstance(cell.value, (int, float)):
                if cell.value > 0:
                    cell.font = POSITIVE_FONT
                elif cell.value < 0:
                    cell.font = NEGATIVE_FONT
                else:
                    pass
                # 짝수행이면 연한 회색 배경
                if is_even:
                    cell.fill = ZEBRA_LIGHT
            else:
                # 얼룩말 패턴 (짝수행 연한 회색)
                if is_even:
                    cell.fill = ZEBRA_LIGHT

    # 3. 열 너비 자동 조정 (최소 10, 최대 40)
    for col_idx in range(1, max_col + 1):
        max_length = 10
        col_letter = get_column_letter(col_idx)

        for row_idx in range(1, min(max_row + 1, 50)):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if cell_value is not None:
                # 한글은 2칸, 영문/숫자는 1칸 기준
                text = str(cell_value)
                length = sum(2 if ord(c) > 127 else 1 for c in text)
                max_length = max(max_length, min(length + 2, 40))

        ws.column_dimensions[col_letter].width = max_length

    # 4. 행 높이 (헤더)
    ws.row_dimensions[1].height = 25

    logger.info("스타일 적용 완료: 시트='%s', %d행 × %d열", ws.title, max_row, max_col)


def style_workbook(filepath: str, comparison_sheets: list = None) -> None:
    """
    저장된 엑셀 파일을 열어 모든 시트에 스타일을 적용하고 다시 저장한다.

    Args:
        filepath (str): 엑셀 파일 경로
        comparison_sheets (list): 비교 시트 이름 목록 ('차이' 컬럼 강조 적용 대상)
    """
    from openpyxl import load_workbook

    if comparison_sheets is None:
        comparison_sheets = []

    wb = load_workbook(filepath)

    for ws in wb.worksheets:
        is_comparison = ws.title in comparison_sheets or '비교' in ws.title or '변동' in ws.title
        style_worksheet(ws, is_comparison=is_comparison)

    wb.save(filepath)
    logger.info("워크북 스타일링 완료: %s", filepath)
