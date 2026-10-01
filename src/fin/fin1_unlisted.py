"""금융1-3A 대기업집단 소속 비상장 비종속 금융보험사 추출 — 공정위 소속회사 개요

- 입력
  - data/raw/ftc/소속회사_개요.xlsx : 공정거래위원회 기업집단포털 소속회사 개요 (2026-05 공개)
  - data/processed/fin_listed.csv · fin_subsidiaries.csv · fin_nonfin_subs.csv : 이미 확정한 218곳
- 공정위 "구분" 칸이 "금융보험업"인 회사만 봄 — 공정거래법상 금융보험사를 공정위가 직접 분류한 값
  (업종코드가 K여도 "일반회사"로 분류된 포스코홀딩스·SK·LG·롯데지주 등 일반 지주는 여기서 빠짐)
- 이미 명단에 있는 곳은 법인등록번호로 대조해 뺌. 공정위는 이름을 한글 음역으로 적어
  (디비손해보험·엔에이치투자증권) 이름 대조가 불안정하므로 법인등록번호를 먼저 쓰고 이름은 보조로 씀
  - 확정 명단 쪽 법인등록번호: fin_listed의 jurir_no, 종속회사는 corp_code로 회사개황을 조회해 얻음
- 제외: 자산 2조 미만(2026-09-30 결정) · 펀드·SPC·명목회사 · GA·손해사정 등 서비스 법인 ·
  금융지주가 아닌 지주·개인 투자회사(이름에 홀딩스·지주)
- 업권은 공정위 업종코드(4자리 KSIC)로 정하고, "여신금융"처럼 넓게 잡히면 이름 키워드로 좁힘
- 공정위 파일에는 모회사가 없으므로 기업집단명만 적음. ① 공시 지위는 비상장 비종속(0점)으로 봄

출력
  - data/processed/fin_unlisted_group.csv : 대기업집단 소속 비상장 비종속 금융보험사 (자산 2조 이상)
  - data/processed/fin_unlisted_group_excluded.csv : 뺀 행과 사유
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from dart_api import get_json  # noqa: E402
from fin.fin1_list import (FUND, SHELL, final_sector, name2, s3_basis,  # noqa: E402
                           sector_by_name, service_reason)

PROC = ROOT / "data" / "processed"
FTC = ROOT / "data" / "raw" / "ftc" / "소속회사_개요.xlsx"
LISTED = PROC / "fin_listed.csv"
SUBS = PROC / "fin_subsidiaries.csv"
NONFIN = PROC / "fin_nonfin_subs.csv"
OUT = PROC / "fin_unlisted_group.csv"
EXCL = PROC / "fin_unlisted_group_excluded.csv"

ASSET_MIN_MIL = 2_000_000          # 2조 원 — 공정위 자산총액 단위는 백만원
FTC_SOURCE = "공정위 기업집단포털 소속회사 개요(2026-05)"

# 음역 대조(name2)는 fin1_list.py의 공통 음역표를 씀 (2026-10-01 통합)
HOLDING_NAME = re.compile(r"홀딩스|지주")


def jurir_of(corp_code):
    if not corp_code:
        return ""
    try:
        c = get_json("company", corp_code=corp_code)
        return str(c.get("jurir_no") or "").replace("-", "") if c.get("status") == "000" else ""
    except Exception:  # noqa: BLE001
        return ""


def main():
    ftc = pd.read_excel(FTC, dtype=str).fillna("")
    f = ftc[ftc["구분"] == "금융보험업"].drop_duplicates("법인등록번호").copy()
    f["assets_mil"] = pd.to_numeric(f["자산총액"].str.replace(",", ""), errors="coerce").fillna(0)
    print(f"공정위 금융보험사 {len(f)}곳 ({FTC_SOURCE})")

    # 확정 명단 218곳의 법인등록번호·이름 키
    frames = [pd.read_csv(p, dtype=str).fillna("") for p in (LISTED, SUBS, NONFIN)]
    have_j, have_n = set(), set()
    for df in frames:
        have_n |= set(df["account"].map(name2))
        if "jurir_no" in df.columns:
            have_j |= set(df["jurir_no"].str.replace("-", "")) - {""}
        if "corp_code" in df.columns:
            have_j |= {jurir_of(c) for c in df["corp_code"] if c} - {""}
    print(f"확정 명단 {sum(len(x) for x in frames)}곳 — 법인등록번호 {len(have_j)}개 확보")

    out, excl = [], []
    for r in f.to_dict("records"):
        nm, code4 = r["소속회사명"], r["업종코드"][1:]
        sec = final_sector(nm, code4)
        if sec in ("여신금융", "그외 기타 금융", "확인 필요"):
            sec = sector_by_name(nm) or sec
        row = dict(account=nm, group=r["기업집단명"], sector=sec, ftc_code=r["업종코드"],
                   ftc_industry=r["영위업종"], assets_jo=round(r["assets_mil"] / 1e6, 2),
                   ipo_date=r["기업공개일"], jurir_no=r["법인등록번호"])
        if r["법인등록번호"] in have_j:
            excl.append({**row, "reason": "이미 명단에 있음 — 법인등록번호 일치"})
            continue
        if name2(nm) in have_n:
            excl.append({**row, "reason": "이미 명단에 있음 — 이름 일치(음역 변환)"})
            continue
        if r["assets_mil"] < ASSET_MIN_MIL:
            excl.append({**row, "reason": "자산 2조 미만 — 2026-09-30 결정"})
            continue
        if FUND.search(nm) or SHELL.search(nm):
            excl.append({**row, "reason": "펀드·SPC·명목회사 — 계획서 7-2"})
            continue
        reason = service_reason(nm, sec)
        if reason:
            excl.append({**row, "reason": reason})
            continue
        if HOLDING_NAME.search(nm) and sec != "금융지주":
            excl.append({**row, "reason": "지주·개인 투자회사 — 금융지주회사법상 금융지주 아님"})
            continue
        out.append({**row,
                    "listed": "비상장 비종속(대기업집단 소속)" if not r["기업공개일"] else "상장(코스피 명단 밖)",
                    "parent": "", "control": "",
                    "disclosure_basis": "없음 — 비상장 비종속",
                    "s3_basis": s3_basis(sec),
                    "source": FTC_SOURCE,
                    "note": ("업권이 넓게 잡힘 — 실제 영위 업무 확인 필요"
                             if sec in ("그외 기타 금융", "금융지원 서비스", "여신금융") else "")})

    res = pd.DataFrame(out).sort_values("assets_jo", ascending=False)
    cols = ["account", "sector", "listed", "group", "parent", "control", "assets_jo",
            "disclosure_basis", "s3_basis", "ftc_code", "ftc_industry", "ipo_date",
            "jurir_no", "source", "note"]
    res[cols].to_csv(OUT, index=False, encoding="utf-8-sig")
    ex = pd.DataFrame(excl)
    ex.to_csv(EXCL, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print(f"\n대기업집단 소속 비상장 비종속 금융보험사 {len(res)}곳 → {OUT.relative_to(ROOT)}")
    print(f"뺀 행 {len(ex)}건 → {EXCL.relative_to(ROOT)}")
    print(ex["reason"].str.split(" — ").str[0].value_counts().to_string())
    print("\n[업권별]")
    print(res["sector"].value_counts().to_string())
    print("\n[전체 — 자산 순]")
    print(res[["account", "group", "sector", "assets_jo", "listed"]].to_string(index=False))
    big_ex = ex[(ex["assets_jo"] >= 2) & ~ex["reason"].str.startswith("이미")]
    if len(big_ex):
        print("\n[2조 이상인데 뺀 곳 — 사유 확인]")
        print(big_ex[["account", "group", "assets_jo", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
