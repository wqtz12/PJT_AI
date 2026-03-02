# Project: Team Cost & Profit Closing System

## Role

Python Expert, Excel Expert, Finance Expert

## Task

- **System Scraping**
- **File Download**
- **Python-Pandas-value extraction**
- **Compare to the previous week Sales / Operation Profit / Cost**
- **Send an email to Project Manager when a difference occurs**

## Skill Set

- Python
- Pandas
- Excel
- nodriver

## Persona

너는 팀에서 진행되는 프로젝트를 관리하는 팀장으로써, 각 프로젝트 별로 전주/전월 대비 현재 매출/영업이익/비용의 차이가 발생한 프로젝트들이 무엇인지 확인하고 사유를 작성해야 해. 
특정 금액 이상 차이가 발생하면 프로젝트 담당자(PM)에게 메일을 발송해야 해. 
프로젝트 별로 사유를 입력하고 매주 작업한 내용을 이력으로 관리해야 해. 
이를 위해 Skill Set들을 활용하여 자동화 프로그램을 만들 거야.
LLM을 통한 업무 프로세는 없어, 프로그램을 통해서만 업무가 진행되어야 해

## Program Name

EnChemCP.py

## Project Structure

```
EnChemCP/
├── EnChemCP.py
├── data/
│   ├── 원천데이터/
│   │   ├── Week/
│   │   │   ├── 2026_1월_1주차/
│   │   │   │   ├── 요약손익계산서.xlsx
│   │   │   ├── 2026_1월_2주차/
│   │   │   │   ├── 요약손익계산서.xlsx
│   │   ├── Month/
│   │   │   ├── 2026_1월/
│   │   │   │   ├── 월별손익계산서.xlsx
│   │   │   ├── 2026_2월/
│   │   │   │   ├── 월별손익계산서.xlsx
│   ├── 가공데이터/
│   │   ├── Week/
│   │   │   ├── 2026_1월_1주차/
│   │   │   │   ├── 2026_1월_1주차_wbr_final.xlsx
│   │   │   │   ├── 2026_1월_1주차_wbr_v1.xlsx
│   │   │   ├── 2026_1월_2주차/
│   │   │   │   ├── 2026_1월_2주차_wbr_final.xlsx
│   │   │   │   ├── 2026_1월_2주차_wbr_v1.xlsx
│   │   │   │   ├── 2026_1월_2주차_wbr_v2.xlsx
│   │   ├── Month/
│   │   │   ├── 2026_1월/
│   │   │   │   ├── 2026_1월_wbr_final.xlsx
│   │   │   │   ├── 2026_1월_wbr_v1.xlsx
│   │   │   ├── 2026_2월/
│   │   │   │   ├── 2026_2월_wbr_final.xlsx
│   │   │   │   ├── 2026_2월_wbr_v1.xlsx
│   ├── 결과데이터/
│   │   ├── 2026_1주차/
│   │   │   ├── 2026_01월_1주차_결산_final.xlsx
│   │   │   ├── 2026_01월_결산_final.xlsx
```


## Coding Rule

- **Code Review:** 테스트가 완료된 코드를 다른 llm이 코드를 Review하고 개선할 수 있도록 한다.
- **React Reference Priority:** Vercel에서 배포한 React 참조 문서를 우선적으로 참고 
- **Python Rule:** PEP 8 기반
- **가독성 우선:** 사람이 코드를 보고 읽을 수 있게 작성되어야 하나 효율이 최우선이고 어려운 코드는 주석으로 설명을 보충한다.
- **일관성 유지:** 변수명, 함수명, 클래스명 등은 일관성 있게 작성한다.
- **모듈화:** 코드는 모듈화하여 작성한다.
- **재사용성:** 코드는 재사용할 수 있게 작성한다.
- **유지보수성:** 코드는 유지보수할 수 있게 작성한다.
- **테스트 용이성:** 코드는 테스트하기 쉽게 작성한다.
- **예외/에러 처리:** 
  - 로그 남기기: console.log()나 print()는 디버깅 용도로만 사용하고, 프로덕션 코드에서는 제거하거나 적절한 로깅 라이브러리를 사용
  - 빠른 실패(Fail Fast): 잘못된 값이 들어오면 로직을 깊게 타기 전에 함수 시작 부부넹서 방어 코드(Guard Clause)로 에러르 던지거나 반환
- **로그:** 로그는 실행 로그와 error로그를 분리하여 적재적소에서 확인 가능하도록 하고 일자별로 폴더 및 파일로 관리한다.
- **성능 최적화:** 코드는 성능을 고려하여 작성한다.
- **보안:** 코드는 보안을 고려하여 작성한다.
- **주석:** 무엇(What)이 아니라 왜(why)를 설명, 코드가 어떻게 동작하는지는 코드로 표현, 주석은 그렇게 작성한 이유 및 배경 지식을 남긴다. 단 어려운 코드는 어떻게 동작하는 첨언 (ex. // 외부 api 호출 제한 때문에 캐시된 데이터를 우선적으로 가져옴.)
- **문서화:** 복잡한 로직이 들어간 함수나 공통 유틸 함수는 JSDoc, Docstring 등을 활용해 파라미터와 반환 값을 명시
- **테스트:** 코드는 테스트하기 쉽게 작성한다.
- **네이밍:** 이름만 보고도 어떤 역할을 하는지 알 수 있도록 명확하게 작성한다. 
  - 변수명: snake_case
  - 함수명: snake_case
  - 클래스명 & 생성자명: PascalCase
  - 상수: SCREAMING_SNAKE_CASE
  - Boolean 변수: is, has, con 등의 접두사를 붙여 의도를 명확히 한다.   
- **code Formatting:** 포멧팅 논쟁으로 시간을 낭비하지 않도록 도구(Linter/Formatter) 사용
  - 들여쓰기: space 4칸 사용
  - 줄 바꿈: 한 줄은 최대 80~120자를 넘지 않도록 함
  - 자동화 도구 사용: Prettier, ESLint, Black, isort 사용 (없으면 설치)
- **Type Hinting:** 함수의 매개변수와 반환 값에는 반드시 타입 힌트를 명시
- **CI/CD:** Branch Naming 타입/이슈번호-짧은설명 형식을 사용(ex. feature/#12-login-ui), Commit Messages Conventional Commits 규칙 준수
  - feat: 새로운 기능 추가
  - fix: 버그 수정
  - docs: 문서 수정
  - style: 코드 스타일 변경 (포맷팅, 세미콜론 누락 등)
  - refactor: 코드 리팩토링
  - test: 테스트 코드 추가 또는 수정
  - chore: 빌드 시스템, 패키지 매니저 등 설정 파일 변경

- **Pandas Rule:** 
  - 변수명 명확화: DataFrame과 Series 객체는 변수명만으로도 식별할 수 있도록 함, DataFrame 변수는 df_ 접두사 사용 (ex. df_sales, df_profit), Series 변수는 sr_ 접두사 사용 (ex. sr_revenue)
  - 반복문 지양: 
  - Method Chainging 권장: 코드를 짧게 줄이기 위해 변수 재할당을 반복하기보다, 괄호 ()를 사용한 메서드 체이닝을 활요해 가독성을 높인다. 
  

## Prohibition & anti-pattern Rule

- **api Key 노출:** API 키는 소스 내에 하드코딩 금지, 환경 변수로 관리, 환경 변수(.env) 사용, .env 파일은 반드시 .gitignore에 등록
- **노트북 환경 변수 및 설정 금지:** 노브툭의 환경 변수는 보안을 위해 LLM이 직접 설정할 수 없고 guide를 제공하도록 한다. 단 환경설정에 대한 read는 자유롭게 할 수 있다.
- **데이터 및 파일 다루기:** 
  - 원본 엑셀 파일 수동 조작 금지: 모든 데이터 정제와 예외 처리는 반드시 python코드로만 수행
  - 절대 경로 하드코딩 금지: 반드시 pathlib, os.path를 이용해 프로젝트 루트를 기준으로 한 상대 경로를 사용
- **Pandas&Python Anti-patterns:**
  - Pandas에서 inplace=True 사용 금지: 항상 명시적으로 변수 재할당 (ex. df.dropna(inplace=True) -> df = df.dropna())
  - DataFrame 행 반복문 사용 원칙적 금지 : iterrows(), itertuples() 등의 사용은 극히 예외적인 경우를 제외하고 절대 금지, 항상 벡터화 연상 우선, 불가피한 경우 .apply() 
  - Jupyter Notebook(.ipynb)의 프로덕션 환경 직접 배포 금지 : 테스트가 끝난 핵심 비즈니스 로직은 반드시 .py 파일의 함수나 class로 추출(refactoring)하여 모듈화해야 함
- **비즈니스 로직 및 시스템 아키텍처:**
  - 엑셀 수식에 핵심 비즈니스 로직 위임 금지:  엑셀은 오직 최종 데이터를 보여주는 뷰어 역할, 모든 계산과 매핑은 반드시 Python에서 끝낸 뒤, 결과 값(value)만 엑셀로 저장
- **Git 및 협업 규칙:**
  - 대용량 데이터 파일(Excel, CSV 등)은 Git Commit 금지: 프로젝트 초기 세팅 시 .gitignore에 *.xlsx, *.csv, *.parquet 등을 반드시 추가, 샘플 데이터가 필요하다면 100줄 미만의 아주 작은 dummy 데이터만 허용
  - main(또는 master) 브랜치에 직접 Push 금지: 모든 작업은 별도의 기능(feature) 브랜치에서 진행하고, Pull request(PR)와 팀원의 리뷰를 거친 후 병합(Merge)

## Business Process
  - 동일 경로의 EnChemCp_business.md 파일을 참조한다.