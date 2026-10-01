"""금융2-4 ③-1 FISIS 1단계 — 업종별 통계표·항목·회사코드 찾기 (조회만, 점수 계산 없음)

- 목적: 2단계(업종별 대출 수집)에 쓸 통계코드·항목코드·회사코드를 추측하지 않고 조회로 찾음
  1) 모든 권역 × 모든 통계표분류에서 이름에 "업종·산업"(분자 후보) 또는 "대출"(분모 후보)이 들어간 통계표
     — 금융-1의 tables.csv는 재무현황 분류(B)만 받아, 다른 분류(영업활동 등)를 다시 찾음
  2) 그 통계표들의 계정항목 전부 (제조업 항목 이름·합계 항목 확인용)
  3) 명단 계정 ↔ FISIS 금융회사코드 대조 (은행·저축은행·생명보험·손해보험 업권)
- 계산 기준 (2026-10-01 확정, 04 문서 반영 대기)
  - 은행·저축은행: 제조업 대출 ÷ 전체 대출(가계 포함) — 분모 후보 표도 여기서 찾음
  - 보험: 감사보고서 우선, 표가 없을 때만 FISIS 업종별 대출금으로 대신
- 호출: fin1_fisis_catalog.call 그대로 사용 (인증키 .env · 캐시 data/raw/fisis/ · 일일 한도 처리)
- 호출 수: 통계목록 14권역 × 10분류 = 140회 + 찾은 통계표의 항목 조회 — 일일 한도(10,000회) 안
- 출력 (data/processed/fisis/)
  - s31_tables.csv : 찾은 통계표 (권역 · 분류 · 통계코드 · 이름 · 용도 업종/대출)
  - s31_accounts.csv : 그 통계표의 계정항목 전부
  - s31_company_map.csv : 명단 계정과 FISIS 금융회사코드 대조 결과
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_fisis_catalog import PARTS, LimitReached, call, rows  # noqa: E402
from fin.fin1_list import key, name2  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fisis"
# 권역별 통계표분류 코드 — FISIS OPEN API 명세 "금융권역 분류표" 그대로 (2026-10-01 확인)
#   A 일반현황 · B 재무현황 · C 주요경영지표 · D 주요영업활동 · P 보도자료통계 (부동산신탁의 주요경영지표만 E)
#   이전 판은 A~J를 짐작해 넣어 없는 코드(G~J) 56건이 오류로 나오고, 실제 있는 P를 빠뜨렸음
SML_BY_PART = {
    "A": "ABCDP", "H": "ABCDP", "I": "ABCDP", "F": "ABCDP", "W": "ABCDP", "G": "ABCD", "D": "ABC",
    "C": "ABCDP", "K": "ABCDP", "T": "ABCDP", "N": "ABCDP", "E": "ABCP", "M": "ABE", "L": "ABCP",
}
NUMER = re.compile(r"업종|산업")                    # 분자 후보: 업종별 표
DENOM = re.compile(r"대출")                         # 분모 후보: 대출금 표
SECTOR_PART = {                                     # 명단 업권 → FISIS 권역
    "은행": ["A"], "은행·기타 예금기관": ["A", "D"], "저축은행·신협": ["E"],
    # 보험사는 생명·손해 두 권역 모두에서 찾음 — 명단 업권이 실제와 다른 경우가 있음
    # (비엔피파리바카디프생명이 "재보험"으로 적혀 손해보험 권역에서만 찾다 실패, 2026-10-01)
    "생명보험": ["H", "I"], "손해보험": ["H", "I"], "보증보험": ["H", "I"], "재보험": ["H", "I"],
}
MANUAL_CD = {                                       # 이름 대조로 안 잡히는 회사 — 명단 이름 → (권역, FISIS 회사코드)
    "키움YES저축은행": ("E", "0010359"),             # FISIS "키움예스저축은행" (키움저축은행 0010456과 다른 회사)
}


def find_tables(errs):
    tabs = []
    for part, pname in PARTS.items():
        if part == "J":                             # 외은지점 — 명단 대상 아님
            continue
        for sd in SML_BY_PART.get(part, ""):
            res = call("statisticsListSearch", lrgDiv=part, smlDiv=sd)
            if res.get("err_cd") != "000":
                errs.append((part, sd, res.get("err_cd"), res.get("err_msg")))
                continue
            for t in rows(res):
                ln, nm = str(t.get("list_no", "")), str(t.get("list_nm", ""))
                use = "업종" if NUMER.search(nm) else ("대출" if DENOM.search(nm) else "")
                if use:
                    tabs.append(dict(part=part, part_nm=pname, sml_div=sd, list_no=ln, list_nm=nm, use=use))
    return pd.DataFrame(tabs, columns=["part", "part_nm", "sml_div", "list_no", "list_nm", "use"]).drop_duplicates("list_no")


def find_accounts(T):
    accs = []
    for _, t in T.iterrows():
        res = call("accountListSearch", listNo=t["list_no"])
        for a in rows(res):
            accs.append(dict(part=t["part"], list_no=t["list_no"], list_nm=t["list_nm"], use=t["use"],
                             account_cd=a.get("account_cd", ""), account_nm=str(a.get("account_nm", ""))))
    return pd.DataFrame(accs, columns=["part", "list_no", "list_nm", "use", "account_cd", "account_nm"])


def company_map():
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    C = pd.read_csv(OUT / "companies.csv", dtype=str).fillna("")
    C = C[C["closed"].str.lower() != "true"].copy()
    C["k"], C["k2"] = C["finance_nm"].map(key), C["finance_nm"].map(name2)
    out = []
    manual = {key(a): v for a, v in MANUAL_CD.items()}
    for _, r in L[L["sector"].isin(SECTOR_PART)].iterrows():
        parts = SECTOR_PART[r["sector"]]
        P = C[C["part"].isin(parts)]
        k, k2 = key(r["account"]), name2(r["account"])
        if k in manual:                                                       # 0) 직접 연결
            pt, cd = manual[k]
            hit = C[(C["part"] == pt) & (C["finance_cd"] == cd)]
            out.append(dict(account=r["account"], sector=r["sector"], layer=r["layer"], parts=pt,
                            finance_cd=";".join(hit["finance_cd"]), finance_nm=";".join(hit["finance_nm"]),
                            match="직접 연결" if len(hit) == 1 else "직접 연결 실패"))
            continue
        how, hit = "일치", P[P["k"] == k]                                     # 1) 이름 그대로
        if hit.empty:
            how, hit = "음역 일치", P[P["k2"] == k2]                          # 2) 음역 대조 (SBI ↔ 에스비아이)
        if hit.empty:                                                         # 3) 한쪽 이름이 다른 쪽에 포함 (KB국민은행 ↔ 국민은행)
            how = "포함 일치(확인 필요)"
            hit = P[P["k"].map(lambda x: bool(x) and (x in k or k in x))]
        match = how if len(hit) == 1 else ("없음" if hit.empty else "여러 곳")
        out.append(dict(account=r["account"], sector=r["sector"], layer=r["layer"], parts="/".join(parts),
                        finance_cd=";".join(hit["finance_cd"]), finance_nm=";".join(hit["finance_nm"]), match=match))
    return pd.DataFrame(out, columns=["account", "sector", "layer", "parts", "finance_cd", "finance_nm", "match"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errs = []
    try:
        T = find_tables(errs)
        A = find_accounts(T)
    except LimitReached as e:
        print(f"\n[멈춤] {e}")
        return
    M = company_map()
    T.to_csv(OUT / "s31_tables.csv", index=False, encoding="utf-8-sig")
    A.to_csv(OUT / "s31_accounts.csv", index=False, encoding="utf-8-sig")
    M.to_csv(OUT / "s31_company_map.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 400)
    pd.set_option("display.max_colwidth", 60)
    total = sum(len(SML_BY_PART.get(p, "")) for p in PARTS if p != "J")
    print(f"[0] 통계목록 조회 {total}건 (명세의 권역별 분류만): 정상 {total - len(errs)}건 · 오류 {len(errs)}건")
    for (pt, sd, cd, msg) in errs:                    # 오류는 하나씩 코드와 FISIS 설명을 그대로 보여 줌
        print(f"  오류 — 권역 {pt} 분류 {sd}: err {cd} {msg}")
    print(f"\n[1] 업종·산업 통계표 (분자 후보) {int((T['use'] == '업종').sum())}개")
    print(T[T["use"] == "업종"].to_string(index=False))
    print("\n[2] 업종 표의 제조업·합계 항목")
    a = A[(A["use"] == "업종") & A["account_nm"].str.contains("제조|합계|총계|^계$|소계", regex=True)]
    print(a[["list_no", "account_cd", "account_nm"]].to_string(index=False) if len(a) else "  (없음)")
    print("\n[3] 은행·저축은행 대출 표 (분모 후보) — 이름에 '대출금' 또는 합계가 있는 항목만")
    d = A[(A["use"] == "대출") & A["part"].isin(["A", "E"])
          & A["account_nm"].str.contains("대출금|합계|총계|^계$", regex=True)]
    print(d[["list_no", "list_nm", "account_cd", "account_nm"]].to_string(index=False) if len(d) else "  (없음)")
    print(f"\n[4] 명단 ↔ FISIS 회사코드 대조 ({len(M)}곳)")
    print(M.groupby(["sector", "match"]).size().rename("곳").reset_index().to_string(index=False))
    chk = M[~M["match"].isin(["일치", "음역 일치", "직접 연결"])]
    if len(chk):
        print("  확인할 계정:", ", ".join(f"{a}({m}{' → ' + f if f else ''})"
                                         for a, m, f in zip(chk["account"], chk["match"], chk["finance_nm"])))
    print(f"\n출력 → {OUT.relative_to(ROOT)}/s31_tables.csv · s31_accounts.csv · s31_company_map.csv")


if __name__ == "__main__":
    main()
