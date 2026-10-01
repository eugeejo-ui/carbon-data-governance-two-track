"""금융1-2 종속 금융회사 추출 — 지배회사: 코스피 금융사 확정 명단(fin_listed)

- 입력: data/processed/fin_listed.csv (먼저 python src/fin/fin1_sector.py 실행)
- 추출 로직은 fin1_list.py의 extract_subsidiaries()를 그대로 씀 (금융1-2b와 같은 함수)
  1) DART 타법인 출자현황(otrCprInvstmntSttus)으로 출자 법인·지분율·총자산을 받음
  2) 보통주 지분율 50% 초과 → 종속. 우선주 등 행은 지배력 판단에 쓰지 않음
  3) 30% 초과 ~ 50% 이하이면서 자산 1조 이상 → 실질 지배 검토 파일로
     (현대카드처럼 지분 36.96%여도 모회사 연결 종속기업인 곳이 있음)
     data/manual/fin_control_decisions.csv에 "포함"으로 적으면 다음 실행 때 명단에 들어감
  4) 펀드·SPC·신탁 상품·명목회사·해외 법인·이미 명단에 있는 곳을 뺌
  5) 같은 회사가 여러 지배회사 밑에 있으면 지분율이 가장 큰 쪽 하나로
  6) 업권 판정(코드 우선, 없으면 이름) 후 금융업 아님·중간지주·기금·지분 100% 초과·
     포트폴리오 없는 법인(GA·손해사정·IT·대부업)을 뺌
- 자산 하한은 두지 않음 (2026-09-30 결정: 전부 채점하고 순위로 거름)
- 한계: 지배회사가 직접 출자한 1단계만 봄. 종속회사의 종속회사는 잡지 않음

출력
  - data/processed/fin_subsidiaries.csv : 종속 금융회사
  - data/manual/fin_sub_control_review.csv : 실질 지배 검토 (지분 30~50%·자산 1조 이상)
  - data/manual/fin_sub_review.csv : 이름으로만 판정했거나 비금융 추정인 법인
  - data/processed/fin_sub_excluded.csv : 뺀 행과 사유
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402
from fin.fin1_list import extract_subsidiaries, key, report  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
SRC = PROC / "fin_listed.csv"
OUT = PROC / "fin_subsidiaries.csv"
CTRL = MANUAL / "fin_sub_control_review.csv"
REVIEW = MANUAL / "fin_sub_review.csv"
EXCL = PROC / "fin_sub_excluded.csv"


def main():
    listed = pd.read_csv(SRC, dtype=str).fillna("")
    parents = listed[["account", "corp_code", "induty_code"]].to_dict("records")
    have = set(listed["account"].map(key))          # 상장사는 자체 공시 의무가 있어 상장 계정으로 둠
    print(f"지배회사 {len(parents)}곳(코스피 금융사 확정 명단) — 타법인 출자현황 조회")
    fin, ctrl, ex, need = extract_subsidiaries(get_json, corp_codes(), parents, have,
                                               listed_label="비상장 종속")
    report("종속 금융회사", fin, ctrl, ex, need, OUT, CTRL, EXCL, REVIEW)


if __name__ == "__main__":
    main()
