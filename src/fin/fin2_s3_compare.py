"""금융2-4 ③ 합치는 방법 비교 — ③-1 제조업 노출 · ③-2 고탄소 노출 · ③-3 CBAM 연결

- 입력: fin_s31.csv (fin2_s31_merge.py, s31) · fin_exposure.csv (fin2_exposure.py, s32·s33)
- 비교하는 두 방법 (2026-10-01 — "평균 vs 높은 쪽은 ③-1 수집 후 결정"에 따라 둘 다 계산만 하고 고르지 않음)
  가. 평균   = (s31 + s32 + s33) ÷ 3, 0.5 올림 (0.33 → 0, 0.67 → 1, 1.5 → 2)
  다. 높은 쪽 = 세 점수 중 가장 높은 값
- 출력: data/processed/fin_s3_compare.csv · 화면에 분포·교차표·세 층의 상관·두 방법이 갈리는 곳
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fin_s3_compare.csv"


def main():
    S1 = pd.read_csv(PROC / "fin_s31.csv", dtype={"account": str})
    EX = pd.read_csv(PROC / "fin_exposure.csv", dtype={"account": str})
    ex = {key(a): r for a, r in zip(EX["account"], EX.to_dict("records"))}
    rows = []
    for r in S1.to_dict("records"):
        e = ex.get(key(r["account"]), {})
        s31, s32, s33 = int(r["s31"]), int(e.get("s32", 0) or 0), int(e.get("s33", 0) or 0)
        rows.append(dict(account=r["account"], layer=r["layer"], group=r["group"], assets_jo=r["assets_jo"],
                         s31=s31, s32=s32, s33=s33, s31_basis=str(r.get("value_basis", ""))[:20],
                         s3_avg=int((s31 + s32 + s33) / 3 + 0.5), s3_max=max(s31, s32, s33),
                         n32=e.get("n32", 0), n33=e.get("n33", 0), matched=bool(e)))
    D = pd.DataFrame(rows)
    D.sort_values(["s3_max", "s3_avg", "s33", "s32", "s31"], ascending=False).to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print(f"명단 {len(D)}곳 (③-2·③-3 집계와 이름이 맞은 곳 {int(D['matched'].sum())}) → {OUT.relative_to(ROOT)}")
    print("\n[1] 층별 점수 분포")
    print(pd.DataFrame({c: D[c].value_counts().reindex([2, 1, 0], fill_value=0)
                        for c in ("s31", "s32", "s33", "s3_avg", "s3_max")}).rename(
        columns={"s31": "③-1 제조업", "s32": "③-2 고탄소", "s33": "③-3 CBAM", "s3_avg": "가. 평균", "s3_max": "다. 높은 쪽"}).to_string())
    print("\n[2] 세 층의 상관 (순위 상관)")
    print(D[["s31", "s32", "s33"]].corr(method="spearman").round(2).to_string())
    print("\n[3] 가. 평균 × 다. 높은 쪽")
    print(pd.crosstab(D["s3_avg"], D["s3_max"], rownames=["평균"], colnames=["높은 쪽"]).to_string())
    print("\n[4] 업권별 ③ 평균 점수")
    print(D.groupby("group")[["s31", "s32", "s33", "s3_avg", "s3_max"]].mean().round(2).sort_values("s3_max", ascending=False).to_string())
    print("\n[5] 두 방법이 갈리는 곳 — 한 층만 2점이고 나머지가 낮은 경우 (자산 큰 순 25)")
    g = D[(D["s3_max"] == 2) & (D["s3_avg"] <= 1)].sort_values("assets_jo", ascending=False)
    print(f"  {len(g)}곳")
    print(g.head(25)[["account", "group", "s31", "s32", "s33", "s3_avg", "s3_max", "s31_basis"]].to_string(index=False))
    print("\n[6] 세 층 모두 1점 이상 (자산 큰 순 25)")
    a = D[(D[["s31", "s32", "s33"]] >= 1).all(axis=1)].sort_values("assets_jo", ascending=False)
    print(f"  {len(a)}곳")
    print(a.head(25)[["account", "group", "s31", "s32", "s33", "s3_avg", "s3_max"]].to_string(index=False))


if __name__ == "__main__":
    main()
