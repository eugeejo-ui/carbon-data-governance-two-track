# 00 준비 단계 — 세부 진행 계획서

- 상태: 진행 중
- 작성: 2026-09-29
- 관련: docs/project_plan.md 9-1

## 1. 목적

- 새 레포에서 바로 작업할 수 있도록 자료·환경·기록 체계를 갖춤
- 채점 전에 결론을 바꿀 수 있는 사실(V1~V5)을 먼저 확인함

## 2. 작업 목록

| 번호 | 할 일 | 산출물 | 상태 |
|---|---|---|---|
| 준비-1 | 이전 레포에서 필요한 파일 가져오기, 출처 기록 | data/external/, data/raw/, data/README.md | 완료 (2026-09-29): 11개 파일 크기 일치, 기준 커밋 55524b0 |
| 준비-2 | 원자료 정리: a 등록공장 CSV 배치 / b 파이썬 환경 / c 자료 점검표 / d 원 출처 확인 | data/raw/, requirements.txt, data/README.md | a 완료 (등록공장 CSV 21,265,082바이트), b·c 진행 중 |
| 준비-3 | Git·GitHub 정리: a 로컬 첫 커밋 / b GitHub 새 레포에 올리기 / c 이전 레포 정리·보관 | GitHub 새 레포, 이전 레포 보관 | 남음 |
| 준비-4 | V1 확인: ESG 공시의 K-ETS 숫자 활용 | project_plan 5-1·7-3 반영 | 완료 (2026-09-29) |
| 준비-5 | V2·V3 확인: 인증 범위, CBAM 50톤 면제 | project_plan 5-1·7-1·7-2 반영 | 완료 (2026-09-29) |
| 준비-6 | V5 확인: IBM 계보 지원 범위, 체험판 | 이 문서 5장 | 남음 |
| 준비-7 | 일정 최신화: 비료 유예, 하류 확대, 법안 | project_plan 5-2 반영 | 완료 (2026-09-29), 채점 직전 재확인 |
| 준비-8 | 판정 기준 고정 | project_plan.md 첫 커밋 | 준비-3a에서 완료 |

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

- 완료 기준: 파일 크기가 표와 같고, data/README.md에 파일별 출처 행이 추가됨

### 준비-2 원자료 정리

- a. 등록공장 CSV (약 21MB, CP949): 준비-1 코드가 다운로드 폴더에서 찾아 복사함. 못 찾으면 위치를 확인해 복사
- b. 파이썬 환경: 레포 안에 .venv 생성, requirements.txt 작성 (pandas, openpyxl, matplotlib, seaborn, requests, python-dotenv)
- c. 자료 점검표: 파일별 행·열 수, 인코딩, 주요 열 이름, 기준일을 스크립트로 확인해 data/README.md에 기록
- d. 원 출처 확인: 원 출처가 기록되지 않은 5개 파일(정보보호 공시 2개, 배출권 명단, 기업집단·소속회사 개요)의 발행 기관·다운로드 경로를 확인해 기록. 확인 전까지는 "확인 필요"로 표시
- 완료 기준: data/README.md의 모든 행에 출처·기준일이 있고, 점검표가 있음

### 준비-3 Git·GitHub 정리

- a. 로컬 Git 초기화 → 첫 커밋 (폴더 구조, 계획서, 가져온 자료)
- b. GitHub에서 빈 공개 레포 `carbon-data-governance-two-track` 생성 (README·.gitignore 추가 없이) → 연결 후 올리기
- c. 이전 레포 정리: 빈 파일 11개 삭제, README에 중단 사유와 후속 레포 링크 작성, 올린 뒤 GitHub 설정에서 보관(Archive) 처리. 공개는 유지함
- 참고: 로컬 폴더 이름(`_two_track`)과 레포 이름(`-two-track`)이 다르지만 동작에는 문제 없음
- 완료 기준: 새 레포 첫 화면에 README와 계획서가 보이고, 이전 레포에 보관 표시가 뜸

### 준비-6 V5 IBM 계보 지원 범위

- 확인 항목
  - 계보 수집기(스캐너)가 지원하는 원천 목록 (DB, ETL 도구, BI 등)
  - Python·Java·엑셀 계산의 계보 추적 가능 여부
  - 외부 계보 정보(OpenLineage 등) 수신 여부
  - 체험판·무료 사용 가능 여부
  - Envizi와의 관계 (V14 참고용)
- 방법: IBM 공식 문서·제품 페이지를 우선으로 보고, 기능 요청 게시판·파트너 자료는 보조로 씀
- 결과 반영: 이 문서 5장 기록 → project_plan 5-1 V5 상태 갱신 → 시연-1(시연 방식) 판단 근거
- 완료 기준: 항목마다 "지원 / 미지원 / 확인 불가"와 출처가 기록됨

## 4. 진행 순서

1. 이 문서 저장
2. 준비-1·2a 실행 (파일 가져오기)
3. 준비-2b·2c (파이썬 환경, 자료 점검표)
4. 준비-3 (Git·GitHub, 이전 레포 보관)
5. 준비-6 (조사, 다른 작업과 병행 가능)
6. 준비-2d (원 출처 확인)
7. 단계 종료: 5장 결과 작성, 계획서 갱신

## 5. 결과 (단계 종료 시 갱신)

### 5-1. 이 문서 작성 전에 확인한 사실 (2026-09-29)

- V1: "ESG 공시에 K-ETS 숫자를 그대로 쓴다"는 방침은 확인되지 않음. KSSB는 배출권거래제 산정 방법을 허용하지만 조직경계 등 조정이 필요함
- V2: 제3자 인증은 2030년부터 의무이나 범위·수준은 미정임
- V3: CBAM 수입자별 연 50톤 이하 면제 확인 (전기·수소 제외)
- 일정: 하류 확대는 이사회·의회 입장 채택 후 3자 협상 단계, 비료 유예 결정 없음, 자본시장법 개정안 미통과 (9월 말 기준)

### 5-2. 준비-6 결과

- (작성 전)

### 5-3. 계획 대비 바뀐 점

- (작성 전)

## 6. 주의

- Git 줄바꿈 자동 변환(autocrlf) 때문에 CSV 크기가 바뀔 수 있음 → 가져올 때 변환을 끔
- PowerShell 기본 저장 방식은 한글이 깨질 수 있음 → UTF-8(BOM 없음)으로 저장
- 등록공장 CSV는 CP949라서 읽을 때 인코딩을 지정해야 함
- 원 출처가 확인되지 않은 파일은 data/README.md에 "확인 필요"로 남겨 둠

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-09-29 | 최초 작성. 준비-4·5·7은 작성 전에 완료됨 |