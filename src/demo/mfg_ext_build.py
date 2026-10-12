"""09 제조 시연 ③ 외부 파일 만들기 (클로드 코드 1회차)

docs/progress/09_demo_mfg.md 4-8-5 표의 공개 자료 값을 글자 그대로 옮겨 적음 (계산하지 않음)

출력
- data/demo/mfg/ext/mfg_ext_anchor.csv, mfg_ext_factors.xlsx, mfg_ext_stats.csv, mfg_ext_disclosed.csv
"""
# LINEAGE-STEP: mfg_ext_build (H4 시험 대상 아님 — 공개 자료 옮겨 적기)
# LINEAGE-INPUT: docs/progress/09_demo_mfg.md 4-8-5 표 (코드 안 상수)
# LINEAGE-OUTPUT: ext/mfg_ext_anchor.csv: 전 칸
# LINEAGE-OUTPUT: ext/mfg_ext_factors.xlsx#eu_defaults: 전 칸
# LINEAGE-OUTPUT: ext/mfg_ext_factors.xlsx#gov_factors: 전 칸
# LINEAGE-OUTPUT: ext/mfg_ext_factors.xlsx#markup: 전 칸
# LINEAGE-OUTPUT: ext/mfg_ext_stats.csv: 전 칸
# LINEAGE-OUTPUT: ext/mfg_ext_disclosed.csv: 전 칸
import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mfg_common import EXT, MONTHS, write_csv

# 아래 표는 09 4-8-5 표를 줄 그대로 옮긴 것임. `빈칸` = 빈 값, `같음` = 바로 위 줄 같은 칸 (09 4-8-0)

ANCHOR_TABLE = """
| company_id | disclosed_name | agency | designation | sector | year | emissions_tco2eq | energy_tj | verifier |
|---|---|---|---|---|---|---|---|---|
| KG | 케이지스틸 주식회사 | 기후에너지환경부 | 업체 | 1차 철강 제조업 | 2025 | 402537 | 8685 | (재)한국품질재단 |
| TW | (주)태웅 | 기후에너지환경부 | 업체 | 1차 철강 제조업 | 2025 | 151271 | 2753 | (재)한국품질재단 |
| HBG | 현대비앤지스틸(주) | 기후에너지환경부 | 사업장 | 1차 철강 제조업 | 2025 | 64871 | 1420 | ㈜디엔브이비즈니스어슈어런스코리아 |
| SA | 삼아알미늄주식회사 | 산업통상부 | 사업장 | 비철금속 | 2025 | 23731 | 475 | 한국표준협회 |
| HI | 한일시멘트 주식회사 | 기후에너지환경부 | 업체 | 시멘트, 석회, 플라스터 및 그 외 제품 제조업 | 2025 | 6178096 | 41976 | 한국표준협회 |
"""
ANCHOR_COLUMNS = ["company_id", "disclosed_name", "agency", "designation", "sector", "year",
                  "emissions_tco2eq", "energy_tj", "verifier", "source", "location", "sha256",
                  "data_nature", "note"]
ANCHOR_SOURCE = "온실가스 에너지 목표관리 명세서 주요정보 (온실가스종합정보센터, 대상년도 2025, 1,173행, 내려받음 2026-10-08)"
ANCHOR_LOCATION = "명세서 주요정보 해당 법인 행"
ANCHOR_SHA256 = "2ed8c33e1a1754c032e0c30f6651b087a082522bd538c929b557b351b73b935d"
ANCHOR_NATURE = "실측"
ANCHOR_NOTE = {"HBG": "지정구분 사업장 — 사업보고서 전 사업장 합계와 배출 차이 0.05%"}

EU_DEFAULTS_TABLE = """
| cn | description | case | route | total_t_per_t | annex | label |
|---|---|---|---|---|---|---|
| 7208 | 탄소강 열연 판 (폭 600mm 이상) | 원산지 불명 | C | 8.230 | 부속서 II (2025/2621 부속서 IV 교체본) | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7208 | 탄소강 열연 판 (폭 600mm 이상) | 한국 | C | 2.118 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
| 7209 | 탄소강 냉연 판 (폭 600mm 이상) | 원산지 불명 | C | 8.250 | 부속서 II | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7209 | 탄소강 냉연 판 (폭 600mm 이상) | 한국 | C | 2.144 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
| 7210 | 도금·도장 판 (폭 600mm 이상) | 원산지 불명 | C | 8.250 | 부속서 II | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7210 | 도금·도장 판 (폭 600mm 이상) | 한국 | C | 2.144 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
| 7219 | 스테인리스 열연 판 (폭 600mm 이상) | 원산지 불명 | 빈칸 | 8.670 | 부속서 II | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7219 | 스테인리스 열연 판 (폭 600mm 이상) | 한국 | 빈칸 | 3.630 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
| 7220 | 스테인리스 열연 판 (폭 600mm 미만) | 원산지 불명 | 빈칸 | 8.670 | 부속서 II | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7220 | 스테인리스 열연 판 (폭 600mm 미만) | 한국 | 빈칸 | 3.630 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
| 7606 | 알루미늄 판·스트립 (0.2mm 초과) | 원산지 불명 | K | 4.986 | 부속서 II | 원산지 불명 최고값 — 특정 공장 값 아님 |
| 7606 | 알루미늄 판·스트립 (0.2mm 초과) | 한국 | L | 1.950 | 부속서 I 한국 표 | 국가 평균값 — 특정 공장 값 아님 |
"""
EU_DEFAULTS_COLUMNS = ["cn", "description", "case", "route", "total_t_per_t", "regulation",
                       "annex", "location", "label"]
EU_REGULATION = "Implementing Regulation (EU) 2026/1740 (2026-07-31 관보, 2026-01-01 적용)"
EU_LOCATION = "09 4-6-4 (사용자 PDF 발췌 — 한국 표 PDF 836~838쪽 등, 원산지 불명 표 PDF 1883~1913쪽)"

GOV_FACTORS_TABLE = """
| factor_id | value | unit | co2 | ch4 | n2o | gwp_ch4 | gwp_n2o | detail | source |
|---|---|---|---|---|---|---|---|---|---|
| ELEC_EF | 0.4594106 | tCO2eq/MWh | 0.4567 | 0.0036 | 0.0085 | 21 | 310 | value = co2 + ch4 × gwp_ch4 ÷ 1000 + n2o × gwp_n2o ÷ 1000 (CH₄·N₂O는 kg/MWh). 2025 배출 = 3차 계획기간 할당 계수 (결정 30) | 온실가스 배출권거래제 보고·인증 지침 [별표6] <표-69> ('14~'16 평균), GWP는 [별지11] |
| GAS_EF | 56.1 | tCO2/TJ | 56.1 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 천연가스·LNG CO₂ 56,100 kg/TJ, 순발열량 기준 (2006 IPCC 기본값). CH₄·N₂O는 넣지 않음 | 온실가스 배출권거래제 보고·인증 지침 [별표6] <표-4>·<표-8> |
| LNG_GCV | 42.7 | MJ/Nm3 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 도시가스(LNG) 총발열량 | 에너지법 시행규칙 [별표] 에너지열량 환산기준 (개정 2022-11-21) |
| LNG_NCV | 38.5 | MJ/Nm3 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 도시가스(LNG) 순발열량 | 에너지법 시행규칙 [별표] 에너지열량 환산기준 (개정 2022-11-21) |
| ELEC_MJ_PER_KWH | 9.6 | MJ/kWh | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 전기(소비기준) | 에너지법 시행규칙 [별표] 에너지열량 환산기준 (개정 2022-11-21) |
| EAF_EF | 0.08 | tCO2/t-steel | 0.08 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 전기로(EAF) Tier1, 고철 원료 (2006 IPCC) | 온실가스 배출권거래제 보고·인증 지침 [별표6] <표-25> |
"""
GOV_FACTORS_COLUMNS = ["factor_id", "value", "unit", "co2", "ch4", "n2o", "gwp_ch4", "gwp_n2o",
                       "detail", "source"]

MARKUP_TABLE = """
| year | sector | rate | source |
|---|---|---|---|
| 2026 | 시멘트·철강·알루미늄·수소 | 0.10 | 2026/1740 부속서 I 머리말 |
| 2027 | 시멘트·철강·알루미늄·수소 | 0.20 | 같음 |
| 2028 | 시멘트·철강·알루미늄·수소 (2028년부터) | 0.30 | 같음 |
| 2026 | 비료 (2026년부터) | 0.01 | 같음 |
| 2026 | 원산지 불명 전구물질 값에도 적용 | 빈칸 | 2026/1740 부속서 IV 머리말 (원산지 아는 값은 원문상 구분 없음) |
"""
MARKUP_COLUMNS = ["year", "sector", "rate", "source"]

# 엑셀 숫자 칸 (09 4-8-3 엑셀 쓰기) — 그 밖의 칸은 문자열 셀, year는 정수 셀
XLSX_NUMBER_COLUMNS = {"total_t_per_t", "value", "co2", "ch4", "n2o", "gwp_ch4", "gwp_n2o", "rate"}

STATS_TABLE = """
| stat_id | item | 월 | value | unit | source | location | note |
|---|---|---|---|---|---|---|---|
| M1_NATION | 전국 제조업 월별 전력사용량 | 월 | 아래 M1 표 전국 줄 (쉼표 뺀 정수) | kWh | 한국전력공사 전력데이터 개방포털 "산업분류별 월별 전력사용량" (출처 표기 한국전력통계, 20261009 현재) | 09 4-5-9 (sha256 a133168bb0d71a8dcad4bbf4b114fbb73c5603392e90314933c7e91d576ced75) | 제조업(KSIC 대분류) — 1차금속·시멘트 구분 없음 |
| M1_CHUNGNAM | 충남 제조업 월별 전력사용량 | 월 | M1 표 충남 줄 | kWh | 같음 | 같음 | 같음 |
| M1_INCHEON | 인천 제조업 월별 전력사용량 | 월 | M1 표 인천 줄 | kWh | 같음 | 같음 | 같음 |
| M1_BUSAN | 부산 제조업 월별 전력사용량 | 월 | M1 표 부산 줄 | kWh | 같음 | 같음 | 같음 |
| M1_GYEONGNAM | 경남 제조업 월별 전력사용량 | 월 | M1 표 경남 줄 | kWh | 같음 | 같음 | 같음 |
| M1_GWANGJU | 광주 제조업 월별 전력사용량 | 월 | M1 표 광주 줄 | kWh | 같음 | 같음 | 같음 |
| M1_GYEONGGI | 경기 제조업 월별 전력사용량 | 월 | M1 표 경기 줄 | kWh | 같음 | 같음 | 같음 |
| M1_CHUNGBUK | 충북 제조업 월별 전력사용량 | 월 | M1 표 충북 줄 | kWh | 같음 | 같음 | 같음 |
| M1_GANGWON | 강원 제조업 월별 전력사용량 | 월 | M1 표 강원 줄 | kWh | 같음 | 같음 | 같음 |
| P_COLD | 냉연강판 생산 (스테인리스 포함) | 월 | 797, 614, 667, 726, 699, 699, 752, 751, 751, 697, 570, 651 | 천톤 | 한국철강협회 철강통계월보 2025년 12월 | 09 4-5-4·4-5-9 | 월별 전체 값이 있는 품목 |
| P_STEEL1 | 1차 철강 생산지수 (2020=100) | 월 | 93.0, 85.3, 93.7, 95.3, 95.7, 94.3, 96.1, 91.8, 94.9, 88.2, 88.2, 92.4 | 지수 | 에너지경제연구원 에너지통계월보 2026년 2월호 8.2 (자료 국가데이터처) | 09 4-5-4·4-5-9 | 단조·잉곳 대리 (결정 8) |
| P_CEMENT | 시멘트·석회·플라스터 및 그 제품 산업생산지수 (2020=100) | 월 | 55.6, 55.7, 75.8, 87.0, 79.9, 77.2, 72.4, 63.9, 72.7, 63.4, 78.3, 75.3 | 지수 | 같음 | 같음 | 레미콘 등 제품 포함 업종 지수 (추정) |
| P_ALFOIL | 알루미늄박 생산 | 월 | 7854, 7902, 7912, 8467, 8726, 8662, 9126, 8344, 8845, 7528, 7132, 7720 | M/T | 국가데이터처 KOSIS DT_1F02012 (광업제조업동향조사) | 09 4-5-4·4-5-9 | 빈칸 |
| M2_24122_FUEL | 24122 냉간압연 및 압출 제품 연료비 (10인 이상, 2024년 기준) | — | 26216 | 백만원 | 국가데이터처 광업제조업조사보고서 표5 | 09 4-5-5 | 빈칸 |
| M2_24122_ELEC | 24122 냉간압연 및 압출 제품 전력비 (10인 이상, 2024년 기준) | — | 63490 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_24112_FUEL | 24112 제강 연료비 (10인 이상, 2024년 기준) | — | 19143 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_24112_ELEC | 24112 제강 전력비 (10인 이상, 2024년 기준) | — | 65930 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_25912_FUEL | 25912 금속 단조제품 연료비 (10인 이상, 2024년 기준) | — | 111679 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_25912_ELEC | 25912 금속 단조제품 전력비 (10인 이상, 2024년 기준) | — | 181864 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_24222_FUEL | 24222 알루미늄 압연·압출 및 연신제품 연료비 (10인 이상, 2024년 기준) | — | 148768 | 백만원 | 같음 | 같음 | 빈칸 |
| M2_24222_ELEC | 24222 알루미늄 압연·압출 및 연신제품 전력비 (10인 이상, 2024년 기준) | — | 229898 | 백만원 | 같음 | 같음 | 빈칸 |
| PRICE_ELEC_2024 | 전력 고압 판매단가 2024 | — | 164.0 | 원/kWh | KESIS 에너지통계월보 2026년 2월호 7.2 | 09 4-5-5 | 빈칸 |
| PRICE_GAS_2024 | 도시가스 산업용 단가 2024 | — | 20.8 | 원/MJ | KESIS 에너지통계월보 2026년 2월호 7.3 | 09 4-5-5 | 연료 = 도시가스 가정 (결정 7) |
| INT_24112 | 24112 제강 업종 평균 에너지 원단위 | — | 0.0078977 | TJ/백만원 | 국가데이터처 광업제조업조사보고서 표5 + KESIS 단가 환산 | 09 4-7-1 결정 18 | 빈칸 |
| INT_25912 | 25912 금속 단조제품 업종 평균 에너지 원단위 | — | 0.0045227 | TJ/백만원 | 같음 | 09 4-7-1 결정 18 | 빈칸 |
| INT_24122 | 24122 냉간압연 및 압출 제품 업종 평균 에너지 원단위 | — | 0.0009411 | TJ/백만원 | 같음 | 09 4-7-1 결정 19 | 빈칸 |
| INT_30310 | 30310 자동차 엔진용 부품 업종 평균 에너지 원단위 | — | 0.0014351 | TJ/백만원 | 같음 | 09 4-7-1 결정 19 | 빈칸 |
| JRC_HR_PER_CR | 냉연 판 1 t당 열연 판 투입 | — | 1.04 | t/t | JRC134682 (EU 집행위 공동연구센터, 2023) p.16 | 09 4-6-7 | KG 기타 코일 수량 계산에만 씀 (결정 10) |
"""
STATS_COLUMNS = ["stat_id", "item", "month", "value", "unit", "source", "location",
                 "data_nature", "note"]
STATS_NATURE = "공식 자료"

# M1 원값 (kWh, 2025 제조업 — 09 4-8-5. 쉼표는 읽기용이라 파일에는 빼고 씀, 연간 칸은 쓰지 않음)
M1_TABLE = """
| 지역 | 1월 | 2월 | 3월 | 4월 | 5월 | 6월 | 7월 | 8월 | 9월 | 10월 | 11월 | 12월 | 연간 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 전국 | 21,423,569,141 | 19,962,745,128 | 21,362,049,442 | 20,793,251,733 | 20,575,390,184 | 20,700,014,383 | 22,108,085,976 | 21,689,788,016 | 21,824,276,897 | 19,719,478,476 | 19,787,100,968 | 20,804,475,782 | 250,750,226,126 |
| 충남 | 2,876,525,211 | 2,711,906,614 | 2,898,145,257 | 2,808,592,166 | 2,777,539,667 | 2,864,949,732 | 3,062,066,360 | 2,960,101,862 | 2,971,425,630 | 2,694,846,149 | 2,644,140,249 | 2,865,773,985 | 34,136,012,882 |
| 인천 | 901,644,511 | 874,230,830 | 902,082,872 | 831,966,064 | 865,352,683 | 880,361,356 | 925,367,537 | 897,290,252 | 932,081,266 | 810,595,025 | 867,144,985 | 907,529,633 | 10,595,647,014 |
| 부산 | 563,724,311 | 546,518,157 | 567,049,961 | 567,545,264 | 529,015,003 | 539,633,616 | 587,849,672 | 568,266,962 | 601,367,336 | 497,733,375 | 527,856,119 | 559,012,709 | 6,655,572,485 |
| 경남 | 1,462,025,240 | 1,469,566,034 | 1,498,418,810 | 1,487,720,301 | 1,415,835,477 | 1,446,585,272 | 1,554,918,183 | 1,432,246,306 | 1,569,472,824 | 1,300,010,769 | 1,415,803,649 | 1,498,892,542 | 17,551,495,407 |
| 광주 | 232,857,554 | 231,147,952 | 233,161,645 | 232,353,158 | 212,850,942 | 216,612,120 | 242,930,170 | 231,439,925 | 240,224,441 | 198,227,650 | 205,916,815 | 220,746,813 | 2,698,469,185 |
| 경기 | 5,866,899,543 | 5,457,539,641 | 5,878,619,614 | 5,502,886,602 | 5,367,536,675 | 5,606,482,213 | 6,154,280,259 | 6,150,960,398 | 5,989,332,275 | 5,502,494,763 | 5,557,245,001 | 5,833,170,626 | 68,867,447,610 |
| 충북 | 1,258,158,140 | 1,208,379,664 | 1,434,183,749 | 1,279,513,354 | 1,259,795,598 | 1,320,510,240 | 1,400,048,481 | 1,371,319,070 | 1,393,256,372 | 1,300,821,084 | 1,261,454,349 | 1,339,433,176 | 15,826,873,277 |
| 강원 | 343,700,883 | 314,958,088 | 383,873,100 | 369,410,080 | 362,718,603 | 346,977,085 | 340,806,610 | 336,366,683 | 347,932,829 | 332,447,889 | 364,059,236 | 374,986,806 | 4,218,237,892 |
"""
M1_REGION = {"M1_NATION": "전국", "M1_CHUNGNAM": "충남", "M1_INCHEON": "인천",
             "M1_BUSAN": "부산", "M1_GYEONGNAM": "경남", "M1_GWANGJU": "광주",
             "M1_GYEONGGI": "경기", "M1_CHUNGBUK": "충북", "M1_GANGWON": "강원"}

DISCLOSED_TABLE = """
| company_id | item_id | item | value | unit | year | source | data_nature |
|---|---|---|---|---|---|---|---|
| KG | PROD_DJ | 생산실적 당진 | 1606 | 천t | 2025 | KG스틸 2025 사업보고서 II-3 생산실적 | 공개값 |
| KG | PROD_IC | 생산실적 인천 | 601 | 천t | 2025 | 같음 | 공개값 |
| KG | HR_AMT | 원재료 매입액 HR COIL | 1509441 | 백만원 | 2025 | KG스틸 2025 사업보고서 II-3 (p.21) | 공개값 |
| KG | HR_PRICE | HR COIL 평균 단가 | 739 | 천원/t | 2025 | 같음 | 공개값 |
| KG | OTHER_COIL_AMT | 원재료 매입액 기타 COIL | 220135 | 백만원 | 2025 | 같음 | 공개값 |
| KG | EPD_GIGA_A3 | EPD A3 GWP-total (GI/GA) | 108 | kgCO2e/t | 2021 | KG Steel EPD S-P-06893 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_SGL_A3 | EPD A3 GWP-total (SGL) | 123 | kgCO2e/t | 2021 | KG Steel EPD S-P-06909 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_MGCOT_A3 | EPD A3 GWP-total (MgCOT) | 166 | kgCO2e/t | 2021 | KG Steel EPD S-P-06910 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_EG_A3 | EPD A3 GWP-total (EG) | 180 | kgCO2e/t | 2021 | KG Steel EPD S-P-06911 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_ALCOT_A3 | EPD A3 GWP-total (ALCOT) | 310 | kgCO2e/t | 2021 | KG Steel EPD S-P-06912 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_TFS_A3 | EPD A3 GWP-total (TFS) | 244 | kgCO2e/t | 2021 | KG Steel EPD S-P-06917 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_GIGA_A1A3 | EPD A1~A3 GWP-total (GI/GA) | 2520 | kgCO2e/t | 2021 | KG Steel EPD S-P-06893 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_SGL_A1A3 | EPD A1~A3 GWP-total (SGL) | 2760 | kgCO2e/t | 2021 | KG Steel EPD S-P-06909 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_MGCOT_A1A3 | EPD A1~A3 GWP-total (MgCOT) | 2660 | kgCO2e/t | 2021 | KG Steel EPD S-P-06910 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_EG_A1A3 | EPD A1~A3 GWP-total (EG) | 2660 | kgCO2e/t | 2021 | KG Steel EPD S-P-06911 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_ALCOT_A1A3 | EPD A1~A3 GWP-total (ALCOT) | 3120 | kgCO2e/t | 2021 | KG Steel EPD S-P-06912 (environdec) | 참고값 — 경계 다름 |
| KG | EPD_TFS_A1A3 | EPD A1~A3 GWP-total (TFS) | 2890 | kgCO2e/t | 2021 | KG Steel EPD S-P-06917 (environdec) | 참고값 — 경계 다름 |
| TW | PROD_FORGE | 생산실적 단조 (녹산, 단조사업부) | 68165 | t | 2025 | 태웅 2025 사업보고서 II-3 생산실적 | 공개값 |
| TW | PROD_STEEL | 생산실적 제강 (화전, 제강사업부) | 180710 | t | 2025 | 같음 | 공개값 |
| TW | FORGE_RAW_USE | 단조 원재료 사용액 (탄소강·합금강·STS 잉곳·블룸) | 141508 | 백만원 | 2025 | 태웅 2025 사업보고서 II-3 | 공개값 |
| TW | FORGE_SALES | 자유형 단조품 매출 | 333870 | 백만원 | 2025 | 태웅 2025 사업보고서 매출 실적 (사업부별) | 공개값 |
| TW | SCRAP_AMT | 원재료 매입액 철스크랩 외 | 141443 | 백만원 | 2025 | 태웅 2025 사업보고서 II-3 (p.12~13) | 공개값 |
| TW | SCRAP_PRICE | 철스크랩 단가 | 677 | 원/kg | 2025 | 같음 | 공개값 |
| TW | WIND_SHARE | 풍력 매출 비중 | 49.1 | % | 2025 | 태웅 2025 사업보고서 (풍력 171,820백만원) | 공개값 |
| TW | RULING_7308 | 타워 플랜지 품목번호 (태웅 주장 7307.91 배척) | 7308.40 | 품목번호 | 2014 | 대법원 2014-05-29 선고 2011두12290 (판례 검색 사이트 albup — 법원 원문 대조 남음) | 공개값 |
| HBG | S1 | Scope1 | 12551 | tCO2e | 2025 | 현대비앤지스틸 2025 사업보고서 녹색경영 (p.274~275) | 공개값 |
| HBG | S2 | Scope2 | 52351 | tCO2e | 2025 | 같음 | 공개값 |
| HBG | FUEL_TJ | 에너지 연료 | 235 | TJ | 2025 | 같음 | 공개값 |
| HBG | ELEC_TJ | 에너지 전기 | 1094 | TJ | 2025 | 같음 | 공개값 |
| HBG | PROD_CW | 생산실적 스테인리스 강판 (창원) | 239432 | t | 2025 | 현대비앤지스틸 2025 사업보고서 II-3 (p.16~17) | 공개값 |
| HBG | PROD_GJ | 생산실적 자동차부품 등 | 142170 | 개 | 2025 | 같음 | 공개값 |
| HBG | SALES_GJ | 자동차부품 매출 | 9145 | 백만원 | 2025 | 현대비앤지스틸 2025 사업보고서 매출 실적 | 공개값 |
| HBG | PROC_REV_SA | 가공수입 | 2753 | 백만원 | 2025 | 같음 | 공개값 |
| HBG | CAP_SA | 송악 스테인리스 표면 가공품 생산능력 | 31000 | t/년 | 2023 | 현대비앤지스틸 2024 지속가능경영보고서 사업장 현황 (2023-12-31 기준) | 공개값 |
| HBG | STS_PRICE | 열간압연 STS강대 단가 | 2158 | 원/kg | 2025 | 현대비앤지스틸 2025 사업보고서 II-3 | 공개값 |
| HBG | MAT_USE | 원재료와 소모품 사용액 | 485894535877 | 원 | 2025 | 현대비앤지스틸 2025 사업보고서 연결 주석 29 | 공개값 |
| SA | PROD_ROLL | 생산실적 압연 | 15457 | t | 2025 | 삼아알미늄 2025 사업보고서 (p.12~14) | 공개값 |
| SA | PROD_PROC | 생산실적 가공 | 118955 | km | 2025 | 같음 | 공개값 |
| HI | CEM_S1 | 시멘트 Scope1 | 5712566 | tCO2eq | 2025 | 한일 2025 지속가능경영보고서 p.37·p.122 (배출권 제출 시 배출량 기준) | 공개값 |
| HI | CEM_S2 | 시멘트 Scope2 | 370165 | tCO2eq | 2025 | 같음 | 공개값 |
| HI | SEC_S1 | 2차제품 Scope1 | 54947 | tCO2eq | 2025 | 같음 | 공개값 |
| HI | SEC_S2 | 2차제품 Scope2 | 40418 | tCO2eq | 2025 | 같음 | 공개값 |
| HI | ELEC_TJ | 에너지 일반 전력 | 9319 | TJ | 2025 | 한일 2025 지속가능경영보고서 p.122 | 공개값 |
| HI | CLINKER | 클링커 생산량 | 7430004 | t | 2025 | 같음 | 공개값 |
| HI | SLAG_CAP | 슬래그미분말 생산 설비 (평택·당진 등) | 1580 | 천t/년 | 2025 | 한일 2025 지속가능경영보고서 p.51 | 공개값 |
| HI | CAP_CEM | 생산능력 시멘트 (시멘트 + 슬래그파우더, 단양공장 외) | 15674 | 천t | 2025 | 한일시멘트 2025 사업보고서 p.32 | 공개값 |
| HI | PROD_CEM | 생산실적 시멘트 외 | 9260 | 천t | 2025 | 같음 | 공개값 |
| HI | PROD_REMICON | 생산실적 레미콘 | 2022 | 천㎥ | 2025 | 같음 | 공개값 |
| HI | PROD_REMITAL | 생산실적 레미탈 | 3222 | 천t | 2025 | 같음 | 공개값 |
| SUP | POSCO_HR_EPD | POSCO 열연 EPD A1~A3 GWP-total | 2150 | kgCO2e/t | 2023 | EPD-IES-0015085:001 (09 4-6-5) | 참고값(회사 평균) — 경계 다름 |
| SUP | POSCO_STS300 | POSCO STS300 EPD A1~A3 GWP-total | 5360 | kgCO2e/t | 2024 | EPD-IES-0016771:004 (09 4-6-5) | 참고값(회사 평균) — 경계 다름 |
| SUP | POSCO_STS400 | POSCO STS400 EPD A1~A3 GWP-total | 3870 | kgCO2e/t | 2023 | EPD-IES-0016772:001 (09 4-6-5) | 참고값(회사 평균) — 경계 다름 |
| SUP | NOVELIS_FRP | Novelis FRP 출하 원단위 | 3.64 | tCO2e/t | FY2025 | Novelis Inc. FY2025 보고서 GHG 지표표 (09 4-6-5) | 참고값(회사 평균) — 경계 다름 |
"""
DISCLOSED_COLUMNS = ["company_id", "item_id", "item", "value", "unit", "year", "source",
                     "location", "data_nature", "note"]


def _md_rows(text):
    """마크다운 표(머리글 줄 + 구분 줄 + 값 줄)를 칸 이름 → 값 사전 목록으로 바꿈 (09 4-8-0 표 읽는 법)"""
    lines = [ln.strip() for ln in text.strip().splitlines()]
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) != len(head):
            raise ValueError(f"표 칸 수가 머리글과 다름: {ln}")
        if rows:
            cells = [rows[-1][i] if c == "같음" else c for i, c in enumerate(cells)]
        rows.append(cells)
    return [{h: (None if c == "빈칸" else c) for h, c in zip(head, r)} for r in rows]


def write_anchor():
    """앵커 CSV를 씀 (09 4-8-5)"""
    rows = []
    for r in _md_rows(ANCHOR_TABLE):
        rows.append({**r, "source": ANCHOR_SOURCE, "location": ANCHOR_LOCATION,
                     "sha256": ANCHOR_SHA256, "data_nature": ANCHOR_NATURE,
                     "note": ANCHOR_NOTE.get(r["company_id"])})
    write_csv(EXT / "mfg_ext_anchor.csv", ANCHOR_COLUMNS, rows)
    return len(rows)


def write_factors():
    """H4 엑셀 시트 3개를 씀 (09 4-8-5)"""
    eu = [{**r, "regulation": EU_REGULATION, "location": EU_LOCATION}
          for r in _md_rows(EU_DEFAULTS_TABLE)]
    sheets = [("eu_defaults", EU_DEFAULTS_COLUMNS, eu),
              ("gov_factors", GOV_FACTORS_COLUMNS, _md_rows(GOV_FACTORS_TABLE)),
              ("markup", MARKUP_COLUMNS, _md_rows(MARKUP_TABLE))]
    wb = Workbook()
    wb.remove(wb.active)
    counts = {}
    for name, columns, rows in sheets:
        ws = wb.create_sheet(name)
        ws.append(columns)
        for r in rows:
            out = []
            for c in columns:
                v = r[c]
                if v is None:
                    out.append(None)
                elif c == "year":
                    out.append(int(v))
                elif c in XLSX_NUMBER_COLUMNS:
                    out.append(float(v))
                else:
                    out.append(str(v))
            ws.append(out)
        counts[name] = len(rows)
    EXT.mkdir(parents=True, exist_ok=True)
    wb.save(EXT / "mfg_ext_factors.xlsx")
    return counts


def write_stats():
    """공개 통계 CSV를 씀 (09 4-8-5)"""
    m1 = {r["지역"]: [r[f"{m}월"].replace(",", "") for m in range(1, 13)]
          for r in _md_rows(M1_TABLE)}
    rows = []
    for r in _md_rows(STATS_TABLE):
        base = {"stat_id": r["stat_id"], "item": r["item"], "unit": r["unit"],
                "source": r["source"], "location": r["location"],
                "data_nature": STATS_NATURE, "note": r["note"]}
        if r["월"] == "월":
            if r["stat_id"] in M1_REGION:
                values = m1[M1_REGION[r["stat_id"]]]
            else:
                values = r["value"].split(", ")
            if len(values) != 12:
                raise ValueError(f"{r['stat_id']} 월 값이 12개가 아님")
            rows.extend({**base, "month": m, "value": v} for m, v in zip(MONTHS, values))
        else:
            rows.append({**base, "month": None, "value": r["value"]})
    write_csv(EXT / "mfg_ext_stats.csv", STATS_COLUMNS, rows)
    return len(rows)


def write_disclosed():
    """회사·납품사 공개값 CSV를 씀 (09 4-8-5)"""
    rows = [{**r, "location": None, "note": None} for r in _md_rows(DISCLOSED_TABLE)]
    write_csv(EXT / "mfg_ext_disclosed.csv", DISCLOSED_COLUMNS, rows)
    return len(rows)


def main():
    """③ 파일 4개를 차례로 씀"""
    print(f"mfg_ext_anchor.csv: {write_anchor()}행")
    counts = write_factors()
    print("mfg_ext_factors.xlsx: " + " · ".join(f"{k} {v}행" for k, v in counts.items()))
    print(f"mfg_ext_stats.csv: {write_stats()}행")
    print(f"mfg_ext_disclosed.csv: {write_disclosed()}행")


if __name__ == "__main__":
    main()
