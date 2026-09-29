"""제조1-4 CBAM 1차 업종·품목 재확인, 비료 표시

대상: data/processed/mfg1_merged.csv에서 status_final이 '포함'인 계정
- 상장: cbam 판정 품목(cbam_wave1_item)을 씀
- 비상장: 배출권 명단 업종코드(KSIC)로 분류함
- 합금철 업종(24113)은 품목에 따라 CBAM 대상 여부가 갈려 '확인 필요'로 표시함
  (대상: 페로망간·페로크롬·페로니켈 / 제외: 페로실리콘·실리코망간 등)
- 앞 단계에서 품목을 확인한 회사는 그 결과를 씀
- 사람 판정: data/manual/mfg1_cbam_items.csv (있으면 반영)

출력: data/processed/mfg1_cbam_check.csv
"""
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
MERGED = PROC / "mfg1_merged.csv"
CBAM = ROOT / "data" / "external" / "cbam" / "mfg_final_reviewed.csv"
ITEMS = ROOT / "data" / "manual" / "mfg1_cbam_items.csv"
OUT = PROC / "mfg1_cbam_check.csv"

FERRO = "24113"   # 합금철

# 비상장: 업종코드 앞 4자리 → (부문, 품목)
KSIC4 = {
    "2411": ("철강", "제철·제강·합금철"), "2412": ("철강", "압연·압출"),
    "2413": ("철강", "강관"), "2419": ("철강", "기타 1차 철강"),
    "2421": ("알루미늄", "비철 제련·합금"), "2422": ("알루미늄", "비철 압연·압출"),
    "2331": ("시멘트", "시멘트"), "2031": ("비료", "비료"),
    "2599": ("철강", "금속 용기 등"),
}

# 앞 단계에서 품목을 확인한 회사 (이름 → 부문, 품목, 근거)
CONFIRMED = {
    "에스엔엔씨": ("철강", "페로니켈 (CN 7202 60 00)", "제조1-2 확인 (보도·CBAM 부속서)"),
    "피엔알": ("철강", "직접환원철 HBI·DRI (CN 7203)", "제조1-3 확인 (등록공장)"),
}

# 상장 cbam 품목 → 부문 (구조물·탱크·볼트는 철강 제품)
ITEM_SECTOR = {"알루미늄": "알루미늄", "시멘트": "시멘트", "비료": "비료"}


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def classify(r):
    k = key(r["name"])
    if k in CONFIRMED:
        sec, item, basis = CONFIRMED[k]
        return sec, item, basis, "대상"
    ksic = str(r["ksic"])
    ferro = ksic.startswith(FERRO)
    if r["listed"] == "상장" and r["cbam_wave1_item"]:
        item = r["cbam_wave1_item"]
        sec, basis = ITEM_SECTOR.get(item, "철강"), "cbam 판정 (사업보고서 품목)"
    else:
        sec, item = KSIC4.get(ksic[:4], ("", ""))
        basis = "배출권 명단 업종코드"
    if ferro:
        return sec, "합금철", basis, "확인 필요"
    if not sec:
        return "", "", basis, "확인 필요"
    return sec, item, basis, "대상"


def main():
    df = pd.read_csv(MERGED, dtype=str).fillna("")
    df = df[df["status_final"] == "포함"].copy()
    m = pd.read_csv(CBAM, dtype=str).fillna("")
    df = df.merge(m[["corp_code", "cbam_wave1_item"]], on="corp_code", how="left").fillna("")

    out = df[["name", "listed", "size_final", "ksic", "corp_code", "kets_code"]].copy()
    res = df.apply(classify, axis=1, result_type="expand")
    out[["cbam_sector", "cbam_item", "cbam_basis", "cbam_status"]] = res
    out["cbam_note"] = ""

    # 사람 판정 반영
    if ITEMS.exists():
        it = pd.read_csv(ITEMS, dtype=str).fillna("")
        for r in it.itertuples():
            hit = out["name"].map(key) == key(r.name)
            out.loc[hit, ["cbam_item", "cbam_status", "cbam_basis", "cbam_note"]] = [
                r.products, r.cbam_status, r.source, r.note]

    out["fertilizer_flag"] = out["cbam_sector"].eq("비료").map({True: "유예 논의 중", False: ""})
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(f"포함 계정 {len(out)}곳")
    print(pd.crosstab(out["cbam_sector"], out["cbam_status"], margins=True, margins_name="합계"))
    print("\n[확인 필요]")
    x = out[out["cbam_status"] == "확인 필요"]
    print(x[["name", "listed", "ksic", "cbam_basis"]].to_string(index=False) if len(x) else "없음")
    print("\n[CBAM 대상 아님]")
    y = out[out["cbam_status"] == "대상 아님"]
    print(y[["name", "cbam_item", "cbam_note"]].to_string(index=False) if len(y) else "없음")
    print("\n[비료 표시] " + ", ".join(out.loc[out["fertilizer_flag"] != "", "name"]))


if __name__ == "__main__":
    main()