# 00 준비 단계 — 세부 진행 계획서

- 상태: 완료 (2026-09-29)
- 작성: 2026-09-29 / 종료 갱신: 2026-09-29
- 관련: docs/project_plan.md 9-1

## 1. 목적

- 새 레포에서 바로 작업할 수 있도록 자료·환경·기록 체계를 갖춤
- 채점 전에 결론을 바꿀 수 있는 사실(V1~V5)을 먼저 확인함

## 2. 작업 목록

| 번호 | 할 일 | 산출물 | 상태 |
|---|---|---|---|
| 준비-1 | 이전 레포에서 필요한 파일 가져오기, 출처 기록 | data/external/, data/raw/, data/README.md | 완료: 11개 파일 크기 일치 (기준 커밋 55524b0). 종료 때 cbam 문장 파일 1개 추가 (cbam 커밋 001ca4c) |
| 준비-2 | 원자료 정리: a 등록공장 CSV 배치 / b 파이썬 환경 / c 자료 점검표 / d 원 출처 확인 | data/raw/, requirements.txt, src/prep_check_data.py, data/README.md | 완료: a 21,265,082바이트 / b .venv, requirements.txt / c 행 수를 아는 7개 파일 일치 / d cbam 레포 기록으로 출처 확인 |
| 준비-3 | Git·GitHub 정리: a 로컬 첫 커밋 / b GitHub 새 레포에 올리기 / c 이전 레포 정리·보관 | GitHub 새 레포, 이전 레포 보관 | 완료: a·b 첫 커밋 60dda36, GitHub에서 내려받아 해시 12/12 일치 확인 / c 정리 커밋 d690b8a, 보관 처리는 GitHub 화면에서 진행 |
| 준비-4 | V1 확인: ESG 공시의 K-ETS 숫자 활용 | project_plan 5-1·7-3 반영 | 완료 |
| 준비-5 | V2·V3 확인: 인증 범위, CBAM 50톤 면제 | project_plan 5-1·7-1·7-2 반영 | 완료 |
| 준비-6 | V5 확인: IBM 계보 지원 범위, 체험판 | 이 문서 5-2 | 완료 |
| 준비-7 | 일정 최신화: 비료 유예, 하류 확대, 법안 | project_plan 5-2 반영 | 완료, 채점 직전 재확인 |
| 준비-8 | 판정 기준 고정 | project_plan.md 첫 커밋 | 완료 (60dda36) |

## 3. 세부 작업

### 준비-1 이전 레포 파일 가져오기

- 기준 커밋: mfg-energy-entry-ladder `55524b0` (2026-09-28)
- 방법: 임시 폴더에 줄바꿈 자동 변환 없이 받은 뒤 필요한 파일만 복사
- cbam 파일 2개는 cbam-mfg-data-layer-entry 커밋 `001ca4c`의 data/interim 파일과 Git 해시가 같음을 확인함 → 이전 레포 사본을 그대로 씀

| 새 위치 | 원래 위치 (이전 레포) | 크기 (바이트) |
|---|---|---|
| data/external/energy_ladder/target_firms.csv | data/processed/ | 6,189 |
| data/external/energy_ladder/step1_unlisted_final.csv | data/processed/ | 6,929 |
| data/external/energy_ladder/step1_firm_types_final.csv | data/processed/ | 22,308 |
| data/external/uci/steel_15min_clean.csv | data/processed/ | 2,567,799 |
| data/external/cbam/mfg_final_reviewed.csv | data/external/cbam/ | 737,130 |
| data/external/cbam/it_spend_matched.csv | data/external/cbam/ | 141,604 |
| data/raw/2025_정보보호_공시_이행_기업리스트.xlsx | data/raw/ | 260,473 |
| data/raw/2026_정보보호_공시_이행_기업리스트.xlsx | data/raw/ | 304,120 |
| data/raw/배출권거래제 할당대상업체 현황_260101기준.xlsx | data/raw/ | 42,726 |
| data/raw/기업집단별 개요.xlsx | data/raw/ | 14,747 |
| data/raw/소속회사 개요.xlsx | data/raw/ | 517,353 |
| data/external/cbam/report_keyword_snippets.csv (종료 때 추가) | cbam 레포 001ca4c data/interim/ | 427,345 |

### 준비-2 원자료 정리

- a. 등록공장 CSV: 다운로드 폴더에서 찾아 복사함 (21,265,082바이트, CP949, 217,048행)
- b. 파이썬 환경: .venv, requirements.txt (pandas, openpyxl, matplotlib, seaborn, requests, python-dotenv). 버전은 고정하지 않음
- c. 자료 점검표: src/prep_check_data.py가 파일별 인코딩·머리글 행·행·열 수·앞쪽 열 이름·해시를 data/README.md에 기록함
- d. 원 출처: cbam-mfg-data-layer-entry의 진행 기록(step1·step2·step3)에 적힌 출처로 채움. 원 다운로드일은 기록되어 있지 않아 "cbam 커밋 001ca4c(2026-09-25) 이전"으로 적음

### 준비-3 Git·GitHub 정리

- a·b. 로컬 Git 초기화 → 첫 커밋 60dda36 → GitHub `carbon-data-governance-two-track`에 올림
- c. 이전 레포: 빈 파일 10개 삭제, README를 중단 기록으로 채움 (커밋 d690b8a), GitHub 설정에서 보관(Archive) 처리
- .gitattributes로 CSV·엑셀의 줄바꿈 변환을 막아 점검표 해시가 유지되게 함
- DART API 키는 루트의 .env에 DART_API_KEY로 저장함 (GitHub 제외 확인, 키 길이 40)

### 준비-6 V5 IBM 계보 지원 범위

- 방법: IBM 공식 제품 페이지·문서를 우선으로 보고, 개발사 논문과 지원 문서를 보조로 씀
- 결과: 5-2

## 4. 진행 순서 (실제)

1. 계획서 저장 → 2. 파일 가져오기 → 3. 파이썬 환경·자료 점검표 → 4. Git·GitHub → 5. 이전 레포 정리 → 6. V5 조사 → 7. 원 출처 확인·종료 갱신

## 5. 결과

### 5-1. 이 문서 작성 전에 확인한 사실 (2026-09-29)

- V1: "ESG 공시에 K-ETS 숫자를 그대로 쓴다"는 방침은 확인되지 않음. KSSB는 배출권거래제 산정 방법을 허용하지만 조직경계 등 조정이 필요함
- V2: 제3자 인증은 2030년부터 의무이나 범위·수준은 미정임
- V3: CBAM 수입자별 연 50톤 이하 면제 확인 (전기·수소 제외)
- 일정: 하류 확대는 이사회·의회 입장 채택 후 3자 협상 단계, 비료 유예 결정 없음, 자본시장법 개정안 미통과 (9월 말 기준)

### 5-2. 준비-6 결과 (V5 IBM 계보 기능)

| 확인 항목 | 결과 | 판정 | 출처 (계획서 부록 B) |
|---|---|---|---|
| 지원 원천 | DB, ETL, 리포팅·분석, 모델링 도구, 프로그래밍 언어용 스캐너 기본 제공. 50개 이상 연동, OpenLineage, 사용자 정의 매핑, 공개 API | 지원 | B33, B34, B39 |
| Java·C# | 바이트코드·소스 코드를 분석하는 스캐너 있음 | 지원 | B35 |
| Python | 지원 언어로 소개되나, IBM 지원 문서(2024)는 주석을 단 스크립트를 읽는 방식으로 설명함 | 부분 지원 (주석 필요) | B35, B36 |
| 엑셀 | 2024 IBM 문서의 스캔 대상 목록에 있으나, 그 제품 구성에서는 카탈로그에 저장되지 않는 항목으로 분류됨 | 부분 (체험판에서 확인) | B36 |
| 외부 계보 받기·내보내기 | OpenLineage 호환 원천 연결, OpenLineage 형식 내보내기 | 지원 | B33, B38 |
| 체험판 | 30일 무료, 계보는 데이터 원천 정의 3개·테이블 5,000개까지, 30일 후 데이터 삭제 | 가능 | B37 |
| Envizi와의 관계 (V14) | 이번 조사 범위 밖 | 남음 | — |

- 영향: H4의 불리한 근거를 고침 (계획서 6장). 시연은 IBM 제품 직접 시연이 유력하며, 체험판은 시연 자료를 준비한 뒤 신청함

### 5-3. 계획 대비 바뀐 점

| 바뀐 점 | 이유 | 반영 위치 |
|---|---|---|
| 배출권 명단 대조를 법인등록번호 대신 업체코드로 함 | 배출권 명단에 법인등록번호가 없음 (열: NO, 업체코드, 업체명, KSIC 코드) | 계획서 9-3 제조2-1 |
| 원 출처(준비-2d)를 cbam 레포 기록으로 채움 | cbam 진행 기록에 같은 파일의 출처가 있고, 행 수(기업집단 102, 소속회사 3,539)도 일치함 | data/README.md |
| cbam 레포의 사업보고서 '유럽' 문장 파일을 추가로 가져옴 | 상장 중견의 EU 수출 판정에 그대로 쓸 수 있음 → 제조-1에서 DART를 새로 조회할 회사가 약 95곳에서 약 37곳으로 줄어듦 | 계획서 9-2 제조1-4 |
| H4 불리한 근거 수정 | V5 확인 결과 | 계획서 2장·5-1·6장 |
| 코드 전달 방식 변경: 파일 내용은 VS Code에서 붙여 넣고, 터미널에는 짧은 실행 명령만 씀 | 긴 코드를 터미널에 붙여 넣던 중 패키지 설치가 중단된 일이 있었음 | 계획서 9장 |
| 다른 도구(Claude Code)의 동시 작업 흔적 정리 | 같은 폴더에서 Git 초기화와 파일 추가가 동시에 일어나 .git이 사라지는 일이 있었음. 잔여 파일이 없음을 확인하고 Git을 새로 시작함. 이후 그 도구는 다른 폴더에서 작업함 | 이 문서 |

## 6. 주의

- Git 줄바꿈 자동 변환(autocrlf) 때문에 CSV 크기가 바뀔 수 있음 → .gitattributes로 막음
- PowerShell 기본 저장 방식은 한글이 깨질 수 있음 → 문서는 VS Code로 저장함
- 등록공장 CSV는 CP949라서 읽을 때 인코딩을 지정해야 함
- 엑셀을 읽을 때 "기본 서식 없음" 경고가 나오지만 데이터에는 영향 없음
- 등록공장 CSV의 원 다운로드 경로는 아직 확인하지 못함

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-09-29 | 최초 작성. 준비-4·5·7은 작성 전에 완료됨 |
| 2026-09-29 | 단계 종료 갱신: 전체 작업 완료, 5장 결과 작성 |
