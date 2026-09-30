"""제조2-0·2-1 채점 대상 확정과 ② 점수

- 입력: data/processed/mfg_wave1_list.csv (95곳), data/manual/mfg2_changes.csv (변동 판정)
- 변동 반영: 제외는 뺌, 교체는 이전 계정 행을 이어받아 새 계정으로 바꿈, 표시는 change_flag 열에 적음
- ② 총량-제품별 대조: 정부 검증 총량(배출권 할당대상 또는 온실가스 목표관리업체)이 있으면 2점, 아니면 1점 (모두 CBAM 1차 업종)
- 목표관리업체는 data/manual/mfg2_kets_managed.csv (산업부 고시 2025-100호 기준, 2026-71호 반영)로 대조함

출력: data/processed/mfg2_base.csv
"""
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "mfg2_base.csv"

# 교체 계정에서 이전 계정 값을 덮어쓸 항목 (근거는 mfg2_changes.csv)
REPLACE = {
    "(주)포스코에스피": dict(
        corp_code="", jurir_no="1314110060766", group="포스코",
        cbam_item="스테인리스 냉연 정밀재·판재",
        cbam_basis="2026-07-31 포스코모빌리티솔루션 STS 사업 양수",
        kets_note="배출권 명단(2026-01-01)에는 포스코모빌리티솔루션(IB002200008 업종 24122)으로 등재. "
                  "냉간압연 사업장이 STS 사업과 함께 넘어간 것으로 봄(추정)",
        eu_export="미확인", eu_signal="없음",
        eu_evidence="2026-07 사업 양수로 생긴 계정이라 공시 근거 없음",
        eu_source="", eu_caution="", eu_exemption_note="",
        source="변동 교체 (제조2-0)",
    ),
}


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def main():
    df = pd.read_csv(PROC / "mfg_wave1_list.csv", dtype=str).fillna("")
    ch = pd.read_csv(MANUAL / "mfg2_changes.csv", dtype=str).fillna("")
    df["k"] = df["account"].map(key)
    df["change_flag"], df["kets_note"] = "", ""

    rows = []
    for r in df.to_dict("records"):
        c = ch[ch["account"].map(key) == r["k"]]
        action = c["action"].iloc[0] if len(c) else ""
        if action == "제외":
            continue
        if action == "교체":
            new = c["new_account"].iloc[0]
            r = {**r, **REPLACE.get(new, {}), "account": new,
                 "change_flag": f"{r['account']} 사업 양수로 교체 ({c['published'].iloc[0]})"}
        elif action == "표시":
            r["change_flag"] = c["flag"].iloc[0]
        rows.append(r)

    out = pd.DataFrame(rows).drop(columns="k")
    out["s2"] = out["kets"].map({"대상": 2}).fillna(1).astype(int)
    out["s2_basis"] = out["kets"].map({"대상": "CBAM + 배출권 할당대상"}).fillna("CBAM만")

    # 온실가스 목표관리업체도 정부 검증 총량이 있으므로 2점 (산업부 지정고시 대조 결과)
    mg = pd.read_csv(MANUAL / "mfg2_kets_managed.csv", dtype=str).fillna("")
    out["k"] = out["account"].map(key)
    designated = out["k"].isin(mg.loc[mg["status"] == "지정", "account"].map(key))
    cancelled = out["k"].isin(mg.loc[mg["status"] == "취소", "account"].map(key))
    m = designated & (out["s2"] == 1)
    out.loc[m, "s2"] = 2
    out.loc[m, "s2_basis"] = "CBAM + 온실가스 목표관리업체(산업부 고시 2025-100호)"
    out.loc[cancelled, "s2_basis"] = "CBAM만 (2025년까지 목표관리업체, 고시 2026-71호 지정취소)"
    out = out.drop(columns="k")
    out.loc[out["kets_note"] != "", "s2_basis"] += " (추정: 승계)"
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(f"채점 대상 {len(out)}곳 → {OUT.relative_to(ROOT)}")
    print(pd.crosstab(out["size"], out["s2"], margins=True, margins_name="합계"))
    print("\n[변동 표시]")
    print(out.loc[out["change_flag"] != "", ["account", "change_flag"]].to_string(index=False))


if __name__ == "__main__":
    main()