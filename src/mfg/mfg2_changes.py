"""제조2-0 변동 확인: 2026년 공시에서 합병·분할·양수도·생산 중단 등을 찾음

- 대상: data/processed/mfg_wave1_list.csv 95곳
- DART 고유번호: 명단 파일 → mfg1_report_links.csv(1-5b 실행분) → DART 이름 검색 순으로 찾음
- 공시 종류: 주요사항보고(B), 거래소공시(I), 공정위공시(J)
- 보고서명에 변동 관련 단어가 있는 공시만 남김. 판정은 하지 않음
- 비상장 외감법인은 이런 공시를 거의 내지 않으므로, 걸리지 않았다고 변동이 없다는 뜻은 아님

출력: data/processed/mfg2_change_screen.csv
"""
from datetime import date
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
LIST = PROC / "mfg_wave1_list.csv"
LINKS = PROC / "mfg1_report_links.csv"
OUT = PROC / "mfg2_change_screen.csv"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="

BGN = "20260101"
KINDS = {"B": "주요사항보고", "I": "거래소공시", "J": "공정위공시"}
# 계정 자체의 변동을 뜻하는 단어 (다른 회사 지분을 사고파는 '타법인' 공시는 뺌)
CHANGE = re.compile(r"합병|분할|영업양수|영업양도|자산양수|자산양도|유형자산양도|최대주주변경|최대주주 변경|"
                    r"생산중단|생산 중단|조업중단|영업정지|해산|회생|파산|상장폐지|공개매수|계열회사 변경|소속회사변동")
EXCLUDE = re.compile(r"타법인")


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def resolve_codes(df):
    """계정별 DART 고유번호. 못 찾으면 빈 값"""
    codes = dict(zip(df["account"].map(key), df["corp_code"]))
    if LINKS.exists():
        links = pd.read_csv(LINKS, dtype=str).fillna("")
        for n, c in zip(links["name"], links["corp_code"]):
            k = key(re.sub(r"\(상장.*\)", "", n))
            if not codes.get(k) and c:
                codes[k] = c
    missing = [k for k, c in codes.items() if not c]
    if missing:
        cc = corp_codes()
        cc["k"] = cc["corp_name"].map(key)
        for k in missing:
            hit = cc[cc["k"] == k]
            if len(hit) == 1:
                codes[k] = hit["corp_code"].iloc[0]
    return codes


def filings(corp_code, kind):
    end = date.today().strftime("%Y%m%d")
    out, page = [], 1
    while True:
        d = get_json("list", corp_code=corp_code, bgn_de=BGN, end_de=end, pblntf_ty=kind,
                     last_reprt_at="Y", page_count="100", page_no=str(page))
        out += d.get("list", [])
        if page >= int(d.get("total_page", 1) or 1):
            return out
        page += 1


def main():
    df = pd.read_csv(LIST, dtype=str).fillna("")
    codes = resolve_codes(df)
    rows, nocode = [], []
    for r in df.itertuples():
        code = codes.get(key(r.account), "")
        if not code:
            nocode.append(r.account)
            continue
        for kind, label in KINDS.items():
            for x in filings(code, kind):
                nm = x.get("report_nm", "").strip()
                if CHANGE.search(nm) and not EXCLUDE.search(nm):
                    rows.append(dict(account=r.account, listed=r.listed, size=r.size, corp_code=code,
                                     kind=label, rcept_dt=x.get("rcept_dt", ""), report_nm=nm,
                                     filer=x.get("flr_nm", ""), link=VIEWER + x.get("rcept_no", "")))
        print(f"{r.account} 조회 완료")

    out = pd.DataFrame(rows, columns=["account", "listed", "size", "corp_code", "kind", "rcept_dt",
                                      "report_nm", "filer", "link"])
    out = out.sort_values(["account", "rcept_dt"])
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n조회 {len(df) - len(nocode)}곳, 변동 관련 공시 {len(out)}건 ({out['account'].nunique()}곳) → {OUT.relative_to(ROOT)}")
    if len(out):
        print(out[["account", "kind", "rcept_dt", "report_nm"]].to_string(index=False))
    print("\n[DART 고유번호 없음] " + (", ".join(nocode) if nocode else "없음"))


if __name__ == "__main__":
    main()