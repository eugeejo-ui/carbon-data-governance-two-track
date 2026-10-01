"""금융2-6 합산 — ① 공시 지위 + ② 현재 빈칸 + ③ 제조 포트폴리오 노출 + ⑤ IBM 관계 → 순위표 (각 0~2점, 최대 8점)

- 입력 (data/processed/)
  - fin_s1.csv          ① s1 (fin2_s1.py) · 공시 시점(disclosure_year)
  - fin_s2.csv          ② s2 (fin2_s2.py) · report_unit
  - fin_s3_compare.csv  ③-1·③-2·③-3 s31·s32·s33 (fin2_s3_compare.py)
  - fin_exposure.csv    ③-2·③-3 거래 곳 수 n32·n33 (fin2_exposure.py)
  - fin_s5.csv          ⑤ s5 (fin2_s5.py)
- ③ = 세 층 중 높은 쪽 (2026-10-01 확정, 다. 높은 쪽)
- 동점 처리 (계획서 7-5, v1.9): 합계 → ② → ③ → ③-3 점수 → ③-3 곳 수 → ③-2 곳 수 → (마지막은 이름순, 규칙 아님·재현용)
- 출력: data/processed/fin_scores.csv (rank 포함)
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fin_scores.csv"
UNITS_DOC = 153            # 계획서·04 문서에 적힌 보고 단위 수 — 실제 값과 대조


def load(name, cols):
    df = pd.read_csv(PROC / name, dtype={"account": str})
    miss = [c for c in cols if c not in df.columns]
    if miss:
        sys.exit(f"{name}에 칸이 없음: {miss} — 해당 단계 코드를 먼저 실행")
    df = df[["account"] + cols].copy()
    df["k"] = df["account"].map(key)
    dup = df[df["k"].duplicated(keep=False)]
    if len(dup):
        print(f"  [주의] {name} 이름 겹침 {len(dup)}줄 — 첫 줄 사용: " + ", ".join(dup['account'].head(6)))
    return df.drop_duplicates("k").drop(columns="account")


def main():
    S1 = load("fin_s1.csv", ["layer", "disclosure_year", "s1"])
    S2 = load("fin_s2.csv", ["report_unit", "s2", "s2_basis"])
    S3 = load("fin_s3_compare.csv", ["group", "assets_jo", "s31", "s32", "s33", "s3_max"])
    EX = load("fin_exposure.csv", ["n32", "n33"])
    S5 = load("fin_s5.csv", ["s5", "s5_basis", "field"])
    base = pd.read_csv(PROC / "fin_s1.csv", dtype={"account": str})[["account"]]
    base["k"] = base["account"].map(key)
    D = base.drop_duplicates("k")
    for name, df in (("①", S1), ("②", S2), ("③", S3), ("차입처", EX), ("⑤", S5)):
        before = len(D)
        D = D.merge(df, on="k", how="left")
        lost = D[df.columns.drop("k")[0]].isna().sum()
        if lost:
            print(f"  [주의] {name} 값 없는 곳 {lost}곳 (명단 {before}곳 중) — 0점 처리")
    for c in ("s1", "s2", "s31", "s32", "s33", "s3_max", "s5", "n32", "n33"):
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0).astype(int)
    D["s3"] = D[["s31", "s32", "s33"]].max(axis=1)
    bad = D[D["s3"] != D["s3_max"]]
    if len(bad):
        print(f"  [주의] ③ 다시 계산한 값과 비교 파일 s3_max가 다른 곳 {len(bad)}곳 — 다시 계산한 값 사용")
    D["total"] = D[["s1", "s2", "s3", "s5"]].sum(axis=1)
    D = D.sort_values(["total", "s2", "s3", "s33", "n33", "n32", "account"],
                      ascending=[False, False, False, False, False, False, True]).reset_index(drop=True)
    D["rank"] = D.index + 1
    cols = ["rank", "account", "layer", "group", "report_unit", "total", "s1", "s2", "s3", "s5",
            "s31", "s32", "s33", "n33", "n32", "assets_jo", "disclosure_year", "s2_basis", "s5_basis", "field"]
    D[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 230)
    pd.set_option("display.max_colwidth", 22)
    print(f"→ {OUT.relative_to(ROOT)}  ({len(D)}곳)")
    print("\n[1] 기준별 점수 분포 (곳 수)")
    print(pd.DataFrame({c: D[c].value_counts().reindex([2, 1, 0], fill_value=0) for c in ("s1", "s2", "s3", "s5")})
          .rename(columns={"s1": "① 공시 지위", "s2": "② 현재 빈칸", "s3": "③ 노출(높은 쪽)", "s5": "⑤ IBM 관계"}).to_string())
    print("\n[2] 합계 분포 (최대 8점)")
    print(D["total"].value_counts().sort_index(ascending=False).rename("곳 수").to_string())
    print("\n[3] 상위 30곳")
    print(D.head(30)[["rank", "account", "group", "total", "s1", "s2", "s3", "s5", "s33", "n33", "n32"]].to_string(index=False))
    print("\n[4] 업권별 평균")
    print(D.groupby("group")[["total", "s1", "s2", "s3", "s5"]].mean().round(2)
          .assign(곳수=D.groupby("group").size()).sort_values("total", ascending=False).to_string())
    U = D.groupby("report_unit").agg(total_max=("total", "max"), s2=("s2", "max"), n=("account", "size"))
    print(f"\n[5] 보고 단위 {len(U)}개 (문서 기록 {UNITS_DOC}개, 차이 {UNITS_DOC - len(U)}) — 단위별 최고 합계 분포")
    print(U["total_max"].value_counts().sort_index(ascending=False).rename("단위 수").to_string())
    print("\n[6] H3 판정용 — ② 1점 이상 비율")
    print(f"  계정 기준 {int((D['s2'] >= 1).sum())}/{len(D)} = {(D['s2'] >= 1).mean():.1%} · "
          f"보고 단위 기준 {int((U['s2'] >= 1).sum())}/{len(U)} = {(U['s2'] >= 1).mean():.1%}")
    tie = D.groupby(["total", "s2", "s3", "s33", "n33", "n32"]).size()
    print(f"\n[7] 동점 처리 뒤에도 같은 묶음 {int((tie > 1).sum())}개 (가장 큰 묶음 {int(tie.max())}곳 — 이름순으로만 갈림)")


if __name__ == "__main__":
    main()
