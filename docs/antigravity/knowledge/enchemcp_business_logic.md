# EnChemCP Business Logic

The pipeline implements specific business rules for data classification and grouping.

## 1. SOLD Mapping Rules
The `assign_sold_code` function in `processor.py` applies the following logic:
- If `UD구분` == 'Y' (or 'YES' / 'Yes'), the SOLD code is set to **"UD"**.
- Otherwise, based on `사업유형`:
    - 'SI' -> **"SI"**
    - 'SM' -> **"SM"**
- Default/Fallback logic is applied if criteria are not met.

## 2. PM Mapping (User Defined)
The system uses a configuration file (`config/code_mappings.json`) to map raw PM names to standardized names. 
Example mapping: `{"전병순 책임": "전병순"}`.
The `assign_pm_mapping` function ensures consistency across the reports.

## 3. Project Code Grouping
The `assign_project_code` function groups data based on a combination of `Object코드` and `Object상세코드`.
Rules are defined in `config/code_mappings.json`.
- Grouping: `Object코드` + `Object상세코드` -> Unified Project Identifier.

## 4. Multi-dimensional Aggregation
The `DataAggregator` computes totals across several dimensions:
- **Time Periods**: Annual, Quarterly, Monthly.
- **Groups**: Customer (고객사), WBS Type, PM, SOLD, Project Code.
- **Financial Metrics**: Revenue (매출), Profit (영업이익), Cost (비용).
