"""제조1-6 제조 트랙 1차 업종 명단 파일 작성

- 대상: mfg1_merged.csv에서 status_final이 '포함'이고, mfg1_cbam_check.csv에서 cbam_status가 '대상'인 계정
- 붙이는 것: 규모·기업집단·배출권 여부·CBAM 부문·품목·비료 표시·EU 수출 판정과 근거·주의 표시
- EU 판정은 data/manual/eu_export_evidence.csv (사람 확정)에서 가져옴

출력: data/processed/mfg_wave1_list.csv
"""
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "mfg_wave1_list.csv"


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def flags(r):
    """주의 표시: 대기업·외국계·비료·대형 고객 조직 담당 가능성(추정)"""
    f = []
    if r["size_final"] in ("대기업", "대기업 계열"):
        f += ["대기업", "대형 고객 조직 담당 가능성(추정)"]
    if r["size_final"] == "외국계 대기업 계열":
        f += ["외국계", "대형 고객 조직 담당 가능성(추정)"]
    if r["fertilizer_flag"]:
        f.append(f"비료 {r['fertilizer_flag']}")
    return " / ".join(f)


def main():
    m = pd.read_csv(PROC / "mfg1_merged.csv", dtype=str).fillna("")
    c = pd.read_csv(PROC / "mfg1_cbam_check.csv", dtype=str).fillna("")
    e = pd.read_csv(MANUAL / "eu_export_evidence.csv", dtype=str).fillna("")
    for d in (m, c, e):
        d["k"] = d["name"].map(key)

    df = m[m["status_final"] == "포함"].merge(
        c[["k", "cbam_sector", "cbam_item", "cbam_basis", "cbam_status", "cbam_note", "fertilizer_flag"]],
        on="k", how="left").fillna("")
    df = df[df["cbam_status"] == "대상"].copy()
    df = df.merge(e.drop(columns="name").add_prefix("eu_").rename(columns={"eu_k": "k"}),
                  on="k", how="left").fillna("")
    df["flags"] = df.apply(flags, axis=1)
    df["kets_member"] = df["kets_member"].replace({"True": "대상", "False": "아님"})

    cols = ["name", "listed", "size_final", "group_2605", "corp_code", "kets_code", "ksic", "kets_member",
            "cbam_sector", "cbam_item", "cbam_basis", "cbam_note", "fertilizer_flag",
            "eu_eu_export", "eu_signal", "eu_evidence", "eu_source", "eu_caution", "eu_exemption_note",
            "flags", "source", "final_note", "note_prev"]
    out = df[cols].rename(columns={
        "name": "account", "size_final": "size", "group_2605": "group", "kets_member": "kets",
        "eu_eu_export": "eu_export", "eu_signal": "eu_signal", "final_note": "size_note"})
    out = out.sort_values(["listed", "size", "account"], ascending=[False, True, True])
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(f"제조 트랙 1차 업종 명단 {len(out)}곳 → {OUT.relative_to(ROOT)}")
    print("\n[상장·규모]")
    print(pd.crosstab(out["size"], out["listed"], margins=True, margins_name="합계"))
    print("\n[CBAM 부문 × 배출권]")
    print(pd.crosstab(out["cbam_sector"], out["kets"], margins=True, margins_name="합계"))
    print("\n[EU 수출 판정 × 규모]")
    print(pd.crosstab(out["size"], out["eu_export"].replace("", "미판정"), margins=True, margins_name="합계"))
    print("\n[EU 신호 종류] " + str(out["eu_signal"].value_counts().to_dict()))
    miss = out[out["eu_export"] == ""]
    print("\n[EU 미판정] " + (", ".join(miss["account"]) if len(miss) else "없음"))
    print("[비료 표시] " + ", ".join(out.loc[out["fertilizer_flag"] != "", "account"]))


if __name__ == "__main__":
    main()