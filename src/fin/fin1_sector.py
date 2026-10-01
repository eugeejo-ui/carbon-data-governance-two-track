"""금융1-1b 업권 확정과 연결자산총액 수집

- 입력: data/processed/fin_candidates.csv (먼저 python src/fin/fin1_list.py 실행)
- 업권·제외 기준은 fin1_list.py의 공통 기준표를 그대로 씀 (final_sector·SHELL·service_reason)
- 업권은 후보 파일 값을 믿지 않고 여기서 다시 계산함 (기준표가 바뀌어도 어긋나지 않게)
- 제외 순서
  1) 코스피가 아님 — 계획서 7-2 코스피 한정
  2) 위탁관리 리츠·인프라펀드 — 명목회사, 운용은 AMC (PCAF 상업용 부동산·프로젝트금융 자산군이라
     배출량 산정 대상이기는 하나 구매 주체가 아님. AMC는 종속회사 단계에서 잡음)
  3) 지주회사(64992) 중 금융지주회사법상 금융지주가 아닌 곳
  4) 업권 미상 — 세세분류 없이 649 등으로만 등록돼 실질을 알 수 없는 곳 (대부분 일반 지주)
  5) 포트폴리오가 없는 법인 — 보험 모집·대리(GA), 손해사정, 고객센터·IT, 대부업
     (여신이 없다는 이유만으로는 빼지 않음: 증권=촉진배출량, 보험=보험배출량이 있음)
  6) 자산총액 조회 실패
  7) 연결자산총액 2조 미만 — 반올림 없이 원 단위로 끊음
- 여기서 뺀 코스피 상장사(일반 지주·2조 미만 금융사 등)도 금융1-2b에서 지배회사로 조회함
  (그 자회사 중 금융회사가 있을 수 있으므로)
- 공시 연도는 2026-07-08 금융위 최종안: 2028년 10조 → 2029년 5조 → 2030년 2조(검토)

출력
  - data/processed/fin_listed.csv : 코스피 금융사 확정 명단
  - data/processed/fin_excluded.csv : 제외 계정과 사유
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from dart_api import get_json  # noqa: E402
from fin.fin1_list import (REPRT, SHELL, YEAR, final_sector, s3_basis,  # noqa: E402
                           service_reason, to_won)

PROC = ROOT / "data" / "processed"
SRC = PROC / "fin_candidates.csv"
OUT = PROC / "fin_listed.csv"
EXCL = PROC / "fin_excluded.csv"

ASSET_MIN = 2_000_000_000_000   # 2조 원 (계획서 7-2)


def assets(corp_code):
    """(자산총계 원, 기준) — 연결을 먼저 보고 없으면 별도"""
    for fs, label in (("CFS", "연결"), ("OFS", "별도")):
        try:
            d = get_json("fnlttSinglAcntAll", corp_code=corp_code, bsns_year=YEAR,
                         reprt_code=REPRT, fs_div=fs)
        except Exception:  # noqa: BLE001
            continue
        for r in d.get("list") or []:
            if r.get("sj_div") != "BS":
                continue
            if re.sub(r"\s", "", str(r.get("account_nm", ""))) == "자산총계":
                v = to_won(r.get("thstrm_amount"))
                if v:
                    return v, label
    return 0, ""


def disclosure_year(won):
    if won >= 10_000_000_000_000:
        return "2028"
    if won >= 5_000_000_000_000:
        return "2029"
    if won >= ASSET_MIN:
        return "2030(검토)"
    return "대상 아님"


def main():
    df = pd.read_csv(SRC, dtype=str).fillna("")
    out, excl = [], []

    def drop(r, sec, reason):
        excl.append(dict(account=r["account"], sector=sec, market=r["market"],
                         induty_code=r["induty_code"], corp_code=r["corp_code"], reason=reason))

    for r in df.to_dict("records"):
        acc, code = r["account"], r["induty_code"]
        sec = final_sector(acc, code)

        if r["market"] != "코스피":
            drop(r, sec, f"{r['market']} 상장 — 계획서 7-2 코스피 한정")
            continue
        if SHELL.search(acc):
            drop(r, sec, "위탁관리 명목회사 — 운용은 AMC, 종속회사 단계에서 AMC를 잡음")
            continue
        if sec == "지주회사":
            drop(r, sec, "지주회사(64992) — 금융지주회사법상 금융지주 아님")
            continue
        if "확인 필요" in sec:
            drop(r, sec, f"업권 미상 — 세세분류 없는 코드({code}), 실질은 일반 지주로 보임")
            continue
        reason = service_reason(acc, sec)
        if reason:
            drop(r, sec, reason)
            continue
        out.append(dict(account=acc, sector=sec, market=r["market"], induty_code=code,
                        corp_code=r["corp_code"], stock_code=r["stock_code"],
                        jurir_no=r["jurir_no"], s3_basis=s3_basis(sec)))

    print(f"후보 {len(out)}곳 — 자산총액 조회")
    keep = []
    for i, r in enumerate(out, 1):
        won, basis = assets(r["corp_code"])
        print(f"  [{i}/{len(out)}] {r['account']} · {won / 1e12:.2f}조 ({basis or '실패'})")
        if not won:
            drop(r, r["sector"], "자산총액 조회 실패 — 원문 확인 필요")
            continue
        if won < ASSET_MIN:
            drop(r, r["sector"], f"연결자산총액 {won / 1e12:.4f}조 — 계획서 7-2 자산 2조 미만")
            continue
        r.update(
            assets_won=won,
            assets_jo=round(won / 1e12, 2),
            assets_basis=basis,
            disclosure_year=disclosure_year(won),
            disclosure_basis="자본시장법",
            listed="상장",
            control="",
            parent="",
            mfg_link="",
            note=("연결 자산총액을 API에서 못 받아 별도 기준을 씀 — 경계선이면 원문 확인"
                  if basis == "별도" else ""),
        )
        keep.append(r)

    res = pd.DataFrame(keep).sort_values(["sector", "assets_won"], ascending=[True, False])
    cols = ["account", "sector", "listed", "control", "parent", "assets_jo", "assets_basis",
            "disclosure_year", "disclosure_basis", "s3_basis", "market", "induty_code",
            "corp_code", "stock_code", "jurir_no", "mfg_link", "note"]
    res[cols].to_csv(OUT, index=False, encoding="utf-8-sig")
    ex = pd.DataFrame(excl)
    ex.to_csv(EXCL, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print(f"\n확정 {len(res)}곳 → {OUT.relative_to(ROOT)}")
    print(f"제외 {len(ex)}곳 → {EXCL.relative_to(ROOT)}")
    print("\n[제외 사유 — 코스피만]")
    kx = ex[ex["market"] == "코스피"]
    print(kx["reason"].str.split(" — ").str[0].value_counts().to_string())
    print("\n[업권별]")
    print(res["sector"].value_counts().to_string())
    print("\n[공시 연도]")
    print(res["disclosure_year"].value_counts().to_string())
    print("\n[전체]")
    print(res[["account", "sector", "assets_jo", "assets_basis",
               "disclosure_year", "induty_code"]].to_string(index=False))


if __name__ == "__main__":
    main()
