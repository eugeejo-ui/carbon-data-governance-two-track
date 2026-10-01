"""금융1-2b 명단 밖 코스피 상장사의 금융 자회사 추출

- 계획서 7-2 포함 규정 세 번째 줄 "비금융 상장사의 금융 자회사"를 뽑음
- 지배회사: 코스피 상장사 전체에서 금융1-1 확정 명단(fin_listed) 40곳만 뺀 나머지 전부
  - 업종을 가리지 않음. 제조사(현대자동차 → 현대캐피탈), 일반 지주(SK·LG·롯데지주 등 64992),
    금융1-1에서 2조 미만·명목회사·GA로 빠진 금융사(한국자산신탁 → 한국자산캐피탈 등)도 포함
  - 이전 버전은 금융업 코드(64·65·66) 회사를 지배회사에서 뺐으나, 그러면 일반 지주 51곳과
    2조 미만 금융사의 자회사를 놓치므로 고침 (2026-09-30)
- 추출 로직은 fin1_list.py의 extract_subsidiaries()를 그대로 씀 (금융1-2와 같은 함수)
- 이미 명단에 있는 계정(상장 40곳 + 금융1-2 종속)은 다시 넣지 않음
- 실질 지배 검토(지분 30~50%·자산 1조 이상)는 data/manual/fin_control_decisions.csv로 판단함
  (현대카드: 현대자동차 36.96%, 현대차 연결 종속기업)

출력
  - data/processed/fin_nonfin_subs.csv : 명단 밖 코스피 상장사의 금융 자회사
  - data/manual/fin_nonfin_control_review.csv : 실질 지배 검토
  - data/manual/fin_nonfin_review.csv : 이름으로만 판정했거나 비금융 추정인 법인
  - data/processed/fin_nonfin_excluded.csv : 뺀 행과 사유
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
LISTED = PROC / "fin_listed.csv"
SUBS = PROC / "fin_subsidiaries.csv"
OUT = PROC / "fin_nonfin_subs.csv"
CTRL = MANUAL / "fin_nonfin_control_review.csv"
REVIEW = MANUAL / "fin_nonfin_review.csv"
EXCL = PROC / "fin_nonfin_excluded.csv"


def main():
    listed = pd.read_csv(LISTED, dtype=str).fillna("")
    subs = pd.read_csv(SUBS, dtype=str).fillna("")
    have = set(listed["account"].map(key)) | set(subs["account"].map(key))
    done = set(listed["corp_code"])                 # 금융1-2에서 지배회사로 이미 조회함

    cc = corp_codes()
    pool = cc[cc["stock_code"].astype(str).str.strip() != ""]
    parents = []
    print(f"상장사 {len(pool)}곳 — 명단 밖 코스피 상장사 선별 (업종 무관)")
    for i, r in enumerate(pool.to_dict("records"), 1):
        if i % 500 == 0:
            print(f"  {i}/{len(pool)} …")
        if r["corp_code"] in done:
            continue
        try:
            d = get_json("company", corp_code=r["corp_code"])
        except Exception:  # noqa: BLE001
            continue
        if d.get("status") != "000" or d.get("corp_cls") != "Y":
            continue
        parents.append(dict(account=d.get("corp_name", r["corp_name"]),
                            corp_code=r["corp_code"],
                            induty_code=str(d.get("induty_code") or "")))

    print(f"\n지배회사 {len(parents)}곳 — 타법인 출자현황 조회")
    fin, ctrl, ex, need = extract_subsidiaries(get_json, cc, parents, have,
                                               listed_label="비상장 종속(명단 밖 코스피 모회사)",
                                               progress=100)
    report("명단 밖 코스피 상장사의 금융 자회사", fin, ctrl, ex, need, OUT, CTRL, EXCL, REVIEW)


if __name__ == "__main__":
    main()
