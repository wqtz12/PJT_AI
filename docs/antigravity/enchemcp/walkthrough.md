# Walkthrough: Business Logic Enhancement (2026-02-25)

## 변경된 사양 및 구현 결과

| 요구사항 | 구현 결과 |
|----------|----------|
| Sold 매핑: UD구분=Y→UD, SI→SI, SM→SM | ✅ `assign_sold_code(ud_value, wbs_type)` |
| PM 사용자 정의 매핑 | ✅ `config/code_mappings.json` → `assign_pm_mapping()` |
| 프로젝트 코드 그룹핑 (Object코드+상세코드) | ✅ `assign_project_code()` |
| 다차원 합계 (연간/분기/월별/고객사/WBS유형/PM/Sold/프로젝트) | ✅ `aggregator.py` |
| 전주/전월 대비 차이 | ✅ `aggregator.calculate_diff()` |
| 이전 버전(v1→v2) 대비 차이 | ✅ `_detect_version()` + `_load_previous_version()` |
| 3종 별도 엑셀 저장 | ✅ `report_writer.py` |

## 신규/수정 파일

| 파일 | 상태 | 핵심 내용 |
|------|------|----------|
| [config/code_mappings.json](file:///Users/jbs/PJT_AI/EnChemCP/config/code_mappings.json) | **신규** | PM 매핑, 프로젝트 그룹핑 설정 |
| [src/aggregator.py](file:///Users/jbs/PJT_AI/EnChemCP/src/aggregator.py) | **신규** | 기간별/그룹별/프로젝트별 합계 + 범용 diff 엔진 |
| [src/report_writer.py](file:///Users/jbs/PJT_AI/EnChemCP/src/report_writer.py) | **신규** | 주간/월간/작업데이터 3종 엑셀 저장 |
| [src/processor.py](file:///Users/jbs/PJT_AI/EnChemCP/src/processor.py) | 수정 | Sold/PM/프로젝트코드 매핑 갱신 |
| [EnChemCP.py](file:///Users/jbs/PJT_AI/EnChemCP/EnChemCP.py) | 수정 | 7단계 파이프라인 + 버전 관리 |

## 주간 모드 검증 (1주차 vs 2주차)

```
python3 EnChemCP.py --mode week --current 2026_1월_2주차 --previous 2026_1월_1주차
```

**Phase 3 집계 결과:**
| 집계 유형 | 금주 | 전주 |
|----------|------|------|
| 고객사별 | 2건 | 2건 |
| WBS유형별 | 3건 | 3건 |
| PM별 | 1건 | 1건 |
| Sold별 | 4건 | 3건 |
| 프로젝트별 | 4건 | 3건 |

**Phase 5 결과 파일:**
- `2026_1월_2주차_주간비교.xlsx` — **8시트** (금주/전주/고객사별/WBS유형별/PM별/Sold별/프로젝트별/변동분석)

**버전 관리 테스트:**
- 1회차 실행 → `v1` 생성, `작업데이터_v1.xlsx`(1시트)
- 2회차 실행 → `v2` 감지, v1 로드하여 비교, `작업데이터_v2.xlsx`(2시트: v2데이터 + v1데이터)

## 생성된 전체 결과물 (11건)

```
결과데이터/2026_1월_2주차/2026_1월_2주차_주간비교.xlsx
결과데이터/2026_1월_2주차/2026_1월_2주차_작업데이터_v1.xlsx
결과데이터/2026_1월_2주차/2026_1월_2주차_작업데이터_v2.xlsx
결과데이터/2026_1월_2주차/2026_1월_2주차_결산_final.xlsx
결과데이터/2026_1월_2주차/history.json
결과데이터/2026_2월/2026_2월_결산_final.xlsx
결과데이터/2026_2월/history.json
```
