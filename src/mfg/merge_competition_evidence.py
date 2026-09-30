"""⑤ 근거 파일 일괄 반영 (제조2-5 직전)

- data/manual/mfg_competition_new_rows.csv 의 행을 mfg_competition_evidence.csv에 합침
  (이미 있는 계정은 교체, 없으면 추가)
- competitor_layer, evidence_source 열을 추가하고 기존 행도 채움
- 점수가 바뀌는 기존 행은 UPDATE 표대로 고침 (⑤ A안: 원문+보도 0점 / 하나만 1점 / 둘 다 없음 2점.
  단 증거 강도 배점은 경쟁 층이 2층·1~2층인 계정에만 적용, 3층은 경쟁이 아니라 2점)
- 실행 전 원본을 .bak으로 복사함
"""
import re
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/manual/mfg_competition_evidence.csv"
NEW = ROOT / "data/manual/mfg_competition_new_rows.csv"
BASE = ROOT / "data/processed/mfg2_base.csv"

UPDATE = {  # key: (⑤ 점수, 경쟁 층, 증거 출처)
    "포스코": (1, "2층", "보도만"),
    "현대제철": (1, "1~3층", "보도만"),
    "세아베스틸": (2, "3층", "보도만"),
    "세아창원특수강": (2, "3층", "보도만"),
    "두산에너빌리티": (1, "1~3층", "보도만"),
    "삼아알미늄": (1, "1~3층", "보도만"),
    "동국제강": (1, "1~2층", "보도만"),
    "노벨리스코리아": (1, "기준 G", "추정"),
    "울산알루미늄": (1, "기준 G", "추정"),
    "동국씨엠": (0, "1~3층", "원문+보도"),
    "아주스틸": (0, "1~3층", "원문+보도"),
    "포스코스틸리온": (2, "3층", "원문만"),
    "아세아시멘트": (2, "설비", "없음"),
    "쌍용씨앤이": (2, "설비", "없음"),
    "SIMPAC": (2, "설비", "없음"),
}


def key(s):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(s))
    return re.sub(r"\s", "", s)


def main():
    old = pd.read_csv(P, dtype=str).fillna("")
    new = pd.read_csv(NEW, dtype=str).fillna("")
    cols = list(old.columns)
    print("기존 열:", cols)
    if len(cols) < 9:
        raise SystemExit("기존 열이 9개 미만이라 멈춤 — 위 열 이름을 알려 주세요")
    acc_col, score_col = cols[0], cols[1]

    shutil.copy(P, P.with_suffix(".csv.bak"))
    new = new.rename(columns=dict(zip(new.columns[:9], cols[:9])))
    for c in ("competitor_layer", "evidence_source"):
        if c not in old.columns:
            old[c] = ""

    old["_k"], new["_k"] = old[acc_col].map(key), new[acc_col].map(key)
    replaced = sorted(set(old["_k"]) & set(new["_k"]))
    out = pd.concat([old[~old["_k"].isin(new["_k"])], new], ignore_index=True)

    changed, missing = [], []
    for kk, (s, layer, src) in UPDATE.items():
        m = out["_k"] == kk
        if not m.any():
            missing.append(kk)
            continue
        before = out.loc[m, score_col].iloc[0]
        if before != str(s):
            changed.append(f"{kk}: {before}→{s}")
        out.loc[m, [score_col, "competitor_layer", "evidence_source"]] = [str(s), layer, src]
    out["competitor_layer"] = out["competitor_layer"].replace("", "없음")
    out["evidence_source"] = out["evidence_source"].replace("", "없음")

    base_keys = set(pd.read_csv(BASE, dtype=str)["account"].map(key))
    out_keys = set(out["_k"])
    out.drop(columns="_k").to_csv(P, index=False, encoding="utf-8")

    print(f"\n저장 {len(out)}행 → {P.relative_to(ROOT)}")
    print(f"교체 {len(replaced)}: {replaced}")
    print(f"점수 변경 {len(changed)}: {changed}")
    print(f"UPDATE 대상인데 파일에 없음: {missing}")
    print(f"명단(94)에 없는 행: {sorted(out_keys - base_keys)}")
    print(f"명단인데 근거 행이 없는 계정: {sorted(base_keys - out_keys)}")
    print("⑤ 점수 분포:", out[score_col].value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()