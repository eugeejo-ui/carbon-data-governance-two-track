"""제조2-5 합산과 순위표

- 입력
  - data/processed/mfg2_base.csv (② s2, 규모·품목·EU 표시)
  - data/processed/mfg2_factory_score.csv (③ s3)
  - data/processed/mfg2_it_score.csv (④ s4)
  - data/manual/mfg_competition_evidence.csv (⑤ s5, competitor_layer, evidence_source)
  - data/manual/cbam_eu_exposure.csv (⑥ 산출용 cbam_eu_exposure, exposure_type, eu_item_match)
  - data/manual/mfg2_overseas.csv (참고 칸, 점수 아님)
- ⑥ EU 노출: 확인·신규 2점 / 축소·불명 1점(exposure_type이 전구물질이면 2점) / 미확인·없음 0점
- 합계 만점 10점, 동점 처리는 ② → ⑥ → ④ 순

출력: data/processed/mfg2_rank.csv
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "mfg2_rank.csv"

S6 = {"확인": 2, "신규": 2, "축소": 1, "불명": 1, "미확인": 0, "없음": 0}


def key(s):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(s))
    return re.sub(r"\s", "", s)


def pick(df, cols, prefix):
    """계정 키를 붙이고 필요한 열만 남김 (없는 열은 빈 값)"""
    df = df.copy()
    df["k"] = df["account"].map(key)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[["k"] + cols].rename(columns={c: f"{prefix}{c}" for c in cols if c == "account"})


def main():
    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    fac = pd.read_csv(PROC / "mfg2_factory_score.csv", dtype=str).fillna("")
    it = pd.read_csv(PROC / "mfg2_it_score.csv", dtype=str).fillna("")
    comp = pd.read_csv(MANUAL / "mfg_competition_evidence.csv", dtype=str).fillna("")
    eu = pd.read_csv(MANUAL / "cbam_eu_exposure.csv", dtype=str).fillna("")
    ov = pd.read_csv(MANUAL / "mfg2_overseas.csv", dtype=str).fillna("")

    comp_score = comp.columns[1]  # s5 또는 score
    base["k"] = base["account"].map(key)
    df = base.merge(pick(fac, ["s3", "s3_note", "sido_n", "sidos"], ""), on="k", how="left")
    df = df.merge(pick(it, ["s4", "it_eok", "it_year", "duty", "s4_note"], ""), on="k", how="left")
    df = df.merge(
        pick(comp, [comp_score, "competitor_layer", "evidence_source"], "").rename(
            columns={comp_score: "s5"}), on="k", how="left")
    df = df.merge(
        pick(eu, ["cbam_eu_exposure", "exposure_type", "eu_item_match"], ""), on="k", how="left")
    df = df.merge(pick(ov, ["overseas_ratio"], ""), on="k", how="left")
    df = df.fillna("")

    # ⑥ EU 노출 점수
    df["cbam_eu_exposure"] = df["cbam_eu_exposure"].replace("", "미확인")
    df["s6"] = df["cbam_eu_exposure"].map(S6).fillna(0).astype(int)
    df.loc[df["exposure_type"] == "전구물질", "s6"] = 2

    for c in ("s2", "s3", "s4", "s5"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["total"] = df[["s2", "s3", "s4", "s5", "s6"]].sum(axis=1)

    df = df.sort_values(["total", "s2", "s6", "s4", "account"],
                        ascending=[False, False, False, False, True]).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    cols = ["rank", "account", "size", "group", "cbam_item",
            "s2", "s3", "s4", "s5", "s6", "total",
            "cbam_eu_exposure", "exposure_type", "eu_item_match",
            "competitor_layer", "evidence_source", "overseas_ratio",
            "sido_n", "it_eok", "duty", "change_flag", "s2_basis", "s3_note", "s4_note"]
    df[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(f"{len(df)}곳 → {OUT.relative_to(ROOT)}")
    print("\n[점수 분포]")
    for c in ("s2", "s3", "s4", "s5", "s6"):
        print(f"  {c}: {df[c].value_counts().sort_index().to_dict()}")
    print("\n[합계 분포]")
    print(df["total"].value_counts().sort_index(ascending=False).to_string())
    print("\n[상위 25곳]")
    print(df.head(25)[["rank", "account", "size", "cbam_item", "s2", "s3", "s4", "s5", "s6",
                       "total", "cbam_eu_exposure", "competitor_layer"]].to_string(index=False))
    print("\n[규모별 평균]")
    print(df.groupby("size")["total"].agg(["count", "mean", "max"]).round(2).to_string())


if __name__ == "__main__":
    main()