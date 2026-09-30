"""제조2-3 ④ IT 예산: 정보보호 공시의 정보기술부문 투자액(A)

- 값: 2026 공시(2025년 투자)를 먼저 쓰고, 없으면 2025 공시(2024년 투자)를 씀. 0 이하는 값 없음으로 봄
- 매칭: 이름 정리 후 정확 일치(영문 약자의 한글 읽기 포함). 상장사는 cbam 레포가 찾은 공시 기업명도 함께 씀
- 3등분: 중견 / 대기업(대기업·대기업 계열·외국계)을 따로 나눔. 값 있는 n곳을 큰 순서로 정렬해
  앞 ⌈n/3⌉곳 2점, 다음 ⌈n/3⌉곳 1점, 나머지 0점. 경계에 같은 값이 걸리면 높은 점수로 묶음
- 값이 없는 계정은 0점과 "④ 자료 없음" (공시 대상이 아니라는 뜻이며 예산이 작다는 뜻이 아님)

출력: data/processed/mfg2_it_score.csv
"""
from math import ceil
from pathlib import Path
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "mfg"))
from mfg2_factory import hangul_reading, key  # noqa: E402

PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
EXT = ROOT / "data" / "external" / "cbam"
OUT = PROC / "mfg2_it_score.csv"
BIG = {"대기업", "대기업 계열", "외국계 대기업 계열"}


def load(year):
    x = pd.read_excel(RAW / f"{year}_정보보호_공시_이행_기업리스트.xlsx", dtype=str)
    x = x.rename(columns={"공시연도(yyyy)": "year", "기업명": "name", "자율/의무": "duty",
                          "투자현황_정보기술부문 투자액(A)": "it"})
    x["k"] = x["name"].map(key)
    x["k_read"] = x["k"].map(hangul_reading)
    x["it_won"] = pd.to_numeric(x["it"].str.replace(",", ""), errors="coerce")
    return x[x["it_won"] > 0][["year", "name", "k", "k_read", "it_won", "duty"]]


def kisa_names():
    """cbam 레포가 상장사별로 찾아 둔 정보보호 공시 기업명 (corp_code → 이름 목록)"""
    it = pd.read_csv(EXT / "it_spend_matched.csv", dtype=str).fillna("")
    m = pd.read_csv(EXT / "mfg_final_reviewed.csv", dtype=str).fillna("")
    it = it.merge(m[["stock_code", "corp_code"]], on="stock_code", how="left").fillna("")
    it = it[(it["kisa_name"] != "") & (it["corp_code"] != "")]
    return it.groupby("corp_code")["kisa_name"].apply(lambda s: [key(v) for v in s]).to_dict()


def tertile(values):
    """값이 큰 순서로 2·1·0점. 경계의 같은 값은 높은 점수로 묶음"""
    order = values.sort_values(ascending=False)
    step = ceil(len(order) / 3)
    pos = {i: (2 if n < step else 1 if n < 2 * step else 0) for n, i in enumerate(order.index)}
    best = {}
    for i, v in order.items():
        best[v] = max(best.get(v, 0), pos[i])
    return values.map(best)


def main():
    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    years = [load(2026), load(2025)]
    kisa = kisa_names()

    rows = []
    for r in base.itertuples():
        names = {key(r.account)} | set(kisa.get(r.corp_code, []))
        names |= {hangul_reading(n) for n in names}
        hit = None
        for d in years:
            h = d[d["k"].isin(names) | d["k_read"].isin(names)]
            if len(h):
                hit = h.iloc[0]
                break
        rows.append(dict(account=r.account, size=r.size, group="대기업" if r.size in BIG else "중견",
                         it_year=hit["year"] if hit is not None else "",
                         it_name=hit["name"] if hit is not None else "",
                         it_eok=round(hit["it_won"] / 1e8, 1) if hit is not None else None,
                         duty=hit["duty"] if hit is not None else ""))
    df = pd.DataFrame(rows)
    df["s4"] = 0
    for g in ("중견", "대기업"):
        has = (df["group"] == g) & df["it_eok"].notna()
        df.loc[has, "s4"] = tertile(df.loc[has, "it_eok"])
        df.loc[(df["group"] == g), "n_group"] = int(has.sum())
    df["s4_note"] = df["it_eok"].isna().map({True: "④ 자료 없음", False: ""})
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(f"계정 {len(df)}곳, 값 있음 {df['it_eok'].notna().sum()}곳 → {OUT.relative_to(ROOT)}")
    print(pd.crosstab([df["group"], df["it_eok"].notna().map({True: "값 있음", False: "자료 없음"})],
                      df["s4"], margins=True, margins_name="합계"))
    for g in ("대기업", "중견"):
        x = df[(df["group"] == g) & df["it_eok"].notna()].sort_values("it_eok", ascending=False)
        print(f"\n[{g} 값 있는 {len(x)}곳]")
        print(x[["account", "it_year", "it_eok", "duty", "s4"]].to_string(index=False))


if __name__ == "__main__":
    main()