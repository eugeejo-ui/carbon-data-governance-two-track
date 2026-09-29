# 자료 출처 기록

| 파일 | 출처 | 기준일 | 가져온 곳 (레포·커밋) | 받은 날짜 |
|---|---|---|---|---|
| external/energy_ladder/target_firms.csv | mfg-energy-entry-ladder 1단계: 중견 CBAM 1차 업종 73곳 | 2026-09-28 | mfg-energy-entry-ladder@55524b0 data/processed/target_firms.csv | 2026-09-29 |
| external/energy_ladder/step1_unlisted_final.csv | mfg-energy-entry-ladder 1단계: 비상장 배출권 1차 업종 32곳 규모 판정 (대기업 계열 9곳 포함) | 2026-09-28 | mfg-energy-entry-ladder@55524b0 data/processed/step1_unlisted_final.csv | 2026-09-29 |
| external/energy_ladder/step1_firm_types_final.csv | mfg-energy-entry-ladder 1단계: 공장 종류 판정 (시연 참고용) | 2026-09-28 | mfg-energy-entry-ladder@55524b0 data/processed/step1_firm_types_final.csv | 2026-09-29 |
| external/uci/steel_15min_clean.csv | UCI Steel Industry Energy Consumption (dataset 851, CC BY 4.0) 0단계 보정본 | 2018년 자료 | mfg-energy-entry-ladder@55524b0 data/processed/steel_15min_clean.csv | 2026-09-29 |
| external/cbam/mfg_final_reviewed.csv | cbam-mfg-data-layer-entry 상장 제조사 1,610곳 규모·CBAM 판정. 커밋 001ca4c data/interim 원본과 동일 (해시 확인) | 2026-09-25 | mfg-energy-entry-ladder@55524b0 data/external/cbam/mfg_final_reviewed.csv | 2026-09-29 |
| external/cbam/it_spend_matched.csv | cbam-mfg-data-layer-entry 정보보호 공시 IT 투자액 매칭. 커밋 001ca4c data/interim 원본과 동일 (해시 확인) | 2026-09-25 | mfg-energy-entry-ladder@55524b0 data/external/cbam/it_spend_matched.csv | 2026-09-29 |
| external/cbam/report_keyword_snippets.csv | cbam-mfg-data-layer-entry 사업보고서 키워드 문맥 (중견 645곳 대상, '유럽' 등 7개 키워드, 1,400문장) | 2026-09-25 | cbam-mfg-data-layer-entry@001ca4c data/interim/report_keyword_snippets.csv | 2026-09-29 |
| raw/2025_정보보호_공시_이행_기업리스트.xlsx | 한국인터넷진흥원(KISA) 정보보호 공시 이행 기업 명단. 출처 기록: cbam 레포 step3 | 2025년 공시 (2024년 실적) | mfg-energy-entry-ladder@55524b0 data/raw/2025_정보보호_공시_이행_기업리스트.xlsx | 2026-09-29 |
| raw/2026_정보보호_공시_이행_기업리스트.xlsx | 한국인터넷진흥원(KISA) 정보보호 공시 이행 기업 명단. 출처 기록: cbam 레포 step3 | 2026년 공시 (2025년 실적) | mfg-energy-entry-ladder@55524b0 data/raw/2026_정보보호_공시_이행_기업리스트.xlsx | 2026-09-29 |
| raw/배출권거래제 할당대상업체 현황_260101기준.xlsx | 기후에너지환경부 사전정보공표, 배출권거래제 4차 계획기간 할당대상업체 772곳. 출처 기록: cbam 레포 step1 | 2026-01-01 | mfg-energy-entry-ladder@55524b0 data/raw/배출권거래제 할당대상업체 현황_260101기준.xlsx | 2026-09-29 |
| raw/기업집단별 개요.xlsx | 공정거래위원회 기업집단포털, 102개 집단. 출처 기록: cbam 레포 step2 | 2026 (파일의 자료시점 열) | mfg-energy-entry-ladder@55524b0 data/raw/기업집단별 개요.xlsx | 2026-09-29 |
| raw/소속회사 개요.xlsx | 공정거래위원회 기업집단포털, 3,539개 회사 (법인등록번호 포함). 출처 기록: cbam 레포 step2 | 2026-05 (파일의 공개년월 열) | mfg-energy-entry-ladder@55524b0 data/raw/소속회사 개요.xlsx | 2026-09-29 |
| raw/한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv | 한국산업단지공단 전국 등록공장 현황 (원 다운로드 경로 확인 필요) | 2024-12-31 | 로컬 다운로드 파일 | 2026-09-29 |

- 받은 날짜는 이 레포로 가져온 날짜임
- 공개 원자료 5개는 cbam-mfg-data-layer-entry 커밋 001ca4c(2026-09-25) 이전에 받은 파일이며, 원 다운로드일은 기록되어 있지 않음

## 자료 점검표 (2026-09-29)

- 엑셀의 머리글 행은 자동 판별값임 (값이 가장 많이 찬 줄의 절반 이상 찬 첫 줄)
- 해시는 SHA-256 앞 12자리이며, 파일이 바뀌었는지 확인할 때 씀

| 파일 | 시트 | 인코딩 | 머리글 행 | 행 수 | 열 수 | 행 수 확인 | 앞쪽 열 이름 | 해시 |
|---|---|---|---|---|---|---|---|---|
| raw/2025_정보보호_공시_이행_기업리스트.xlsx | 2025 | 엑셀 | 1 | 773 | 30 | - | 공시연도(yyyy), 기업명, 업종, 자율/의무, 사전점검 수행여부, 투자현황_정보기술부문 투자액(A) | d1eeed2f0d6d |
| raw/2026_정보보호_공시_이행_기업리스트.xlsx | 2026 | 엑셀 | 1 | 826 | 30 | - | 공시연도(yyyy), 기업명, 업종, 자율/의무, 사전점검 수행여부, 투자현황_정보기술부문 투자액(A) | 42b1d34aa8c1 |
| raw/기업집단별 개요.xlsx | 기업집단별 개요 | 엑셀 | 1 | 102 | 13 | - | 자료시점, 기업집단, 순위, 소속회사수, 상장소속회사수, 비상장소속회사수 | ac942924c510 |
| raw/배출권거래제 할당대상업체 현황_260101기준.xlsx | sheet | 엑셀 | 1 | 772 | 4 | - | NO, 업체코드, 업체명, KSIC 코드 | 3f63b2f6e636 |
| raw/소속회사 개요.xlsx | 소속회사 개요 | 엑셀 | 1 | 3,539 | 21 | - | 공개년월, 기업집단명, 소속회사명, 대표자, 설립일, 계열편입일 | 032f9d437f4e |
| raw/한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv | - | CP949 | 1 | 217,048 | 5 | 일치 | 순번, 회사명, 단지명, 생산품, 공장주소 | 2858c56a9023 |
| external/cbam/it_spend_matched.csv | - | UTF-8 (BOM) | 1 | 1,610 | 13 | 일치 | stock_code, corp_name, size_class, is_holding, wave_group_reviewed, induty_code | 28a323b66c71 |
| external/cbam/mfg_final_reviewed.csv | - | UTF-8 (BOM) | 1 | 1,610 | 49 | 일치 | corp_code, corp_name, stock_code, corp_cls, induty_code, jurir_no | 28b3a40e6f8e |
| external/cbam/report_keyword_snippets.csv | - | UTF-8 (BOM) | 1 | 1,400 | 5 | - | stock_code, corp_name, wave_group, keyword, context | 5c586b9ebd49 |
| external/energy_ladder/step1_firm_types_final.csv | - | UTF-8 (BOM) | 1 | 73 | 35 | 일치 | source, corp_code, name, kets_name, ksic, kets_member | b932f7e76ec8 |
| external/energy_ladder/step1_unlisted_final.csv | - | UTF-8 (BOM) | 1 | 32 | 16 | 일치 | kets_code, kets_name, kets_ksic, corp_code, dart_name, report | 91c218e39d04 |
| external/energy_ladder/target_firms.csv | - | UTF-8 (BOM) | 1 | 73 | 10 | 일치 | source, corp_code, name, kets_name, ksic, kets_member | 78e51f003e40 |
| external/uci/steel_15min_clean.csv | - | UTF-8 (BOM) | 1 | 35,040 | 10 | 일치 | interval_start, kwh, kw, co2, load_type_raw, weekday | 3a126fb7fe77 |
