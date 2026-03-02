# Excel Styling Engine (Openpyxl)

A highly configurable styling engine for automated Excel reports, implemented in `excel_styler.py`. It provides professional formatting with a focus on financial data presentation.

## Key Features

- **Theme-Based Styling**: Automatically applies color themes based on column header keywords.
    - **Revenue (매출/수익)**: Blue theme.
    - **Profit (영업이익/이익)**: Orange theme.
    - **Cost (비용)**: Green theme.
    - **Default**: Gray theme.
- **Comparison Period Themes**: Distinct header colors for different periods in comparison sheets.
    - **Previous Period (_전주 / _전월)**: Gray.
    - **Current Period (_금주 / _당월)**: Teal.
    - **Difference (_차이)**: Red/Maroon.
- **Conditional Font Coloring**:
    - **Positive Difference**: Dark Blue font.
    - **Negative Difference**: Red font.
- **Row-Level Formatting**:
    - **Zebra Striping**: Light gray backgrounds on even rows for better readability.
    - **Borders**: Thin, theme-consistent borders around all cells.
- **Automation Utilities**:
    - **Auto-Column Width**: Calculates optimal width based on content (including CJK character handling).
    - **Number Formatting**: Applies standard comma separators and two-decimal rate formats.
    - **Header Row Stabilization**: Fixed height and center-aligned bold headers.

## Row Filtering
The aggregator logic complements the styler by filtering out rows with zero differences in comparison sheets, ensuring the reports only highlight relevant changes.
