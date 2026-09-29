"""제조1-3 규모 재확인 선별, 신원 확인 자료

A. 상장 중소(확인 대기): DART 최대주주 현황(2025 사업보고서)에서 지분율이 가장 큰 주주를 뽑음.
   그 주주가 법인이고 30% 이상이면 그 법인의 자산총액을 찾음 (공정위 소속회사 → DART 재무 순).
   자산이 5,000억 원 미만이면 그 법인의 최다 주주까지 한 단계 더 봄 (간접 소유 = 두 지분율의 곱).
   결과는 후보 선별이며, 최종 판정은 사용자가 data/manual/mfg1_size_checks.csv에 기록함
B. 비상장 중소 4곳: 감사보고서 주석 '일반사항' 열람 대상으로 표시
C. 신원 확인(피엔알, 동남): DART 동명 회사(법인등록번호·주소·업종)와 등록공장(생산품·주소)을 나란히 뽑음

출력: data/processed/mfg1_size_screen.csv, data/processed/mfg1_identity_candidates.csv
"""
from pathlib import Path
import re
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
MERGED = PROC / "mfg1_merged.csv"
FTC = RAW / "소속회사 개요.xlsx"
FACTORY = RAW / "한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv"

YEAR, REPRT = "2025", "11011"   # 2025 사업보고서
LIMIT_EOK = 5000                 # 자산총액 5,000억 원
SHARE = 30.0                     # 지분 30%

CORP_MARK = re.compile(
    r"\(주\)|㈜|주식회사|유한|홀딩스|지주|법인|조합|재단|은행|증권|보험|캐피탈|투자|공사|공단|"
    r"co\.|corp|inc|ltd|llc|limited|holdings|gmbh|s\.a|pte|b\.v", re.I)

# 신원 확인: 이름과 배출권 업종에 맞는 생산품 단서
IDENTITY = {
    "피엔알": {"ftc_jurir": "1717110076545", "hint": r"환원철|HBI|DRI|펠릿|더스트"},
    "동남": {"ftc_jurir": "", "hint": r"알루미|알미늄|알류미|AL괴|비철"},
}


def key(name):
    if pd.isna(name):
        return ""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def is_corp(nm):
    """법인 여부 (추정): 법인 표지가 있거나 한글 2~4자 이름이 아니면 법인으로 봄"""
    nm = str(nm).strip()
    return bool(CORP_MARK.search(nm)) or not re.fullmatch(r"[가-힣]{2,4}", nm)


def is_foreign(nm):
    return bool(re.search(r"[A-Za-z]", nm)) and not re.search(r"[가-힣]", nm)


def top_holder(corp_code):
    """최대주주 현황에서 지분율이 가장 큰 주주 1명 (우선주 행 제외). 없으면 None"""
    d = get_json("hyslrSttus", corp_code=corp_code, bsns_year=YEAR, reprt_code=REPRT)
    if d.get("status") != "000":
        return None
    rows = []
    for x in d.get("list", []):
        nm = str(x.get("nm", "")).strip()
        if nm in ("", "계", "합계", "소계", "-") or "우선" in str(x.get("stock_knd", "")):
            continue
        p = num(x.get("trmend_posesn_stock_qota_rt"))
        if p is not None:
            rows.append((nm, p))
    return max(rows, key=lambda r: r[1]) if rows else None


def assets(name, ftc, codes):
    """법인의 자산총액(억 원), 출처, DART 고유번호"""
    k = key(name)
    r = ftc[ftc["k"] == k]
    if len(r):
        v = num(r["자산총액"].iloc[0])        # 백만 원
        return (round(v / 100) if v is not None else None), "공정위 소속회사 2026-05", ""
    c = codes[codes["k"] == k]
    if len(c) != 1:
        return None, f"DART 이름 일치 {len(c)}곳 (수동 특정 필요)", ""
    cc = c["corp_code"].iloc[0]
    d = get_json("fnlttSinglAcnt", corp_code=cc, bsns_year=YEAR, reprt_code=REPRT)
    if d.get("status") == "000":
        for fs in ("OFS", "CFS"):
            for x in d.get("list", []):
                if x.get("fs_div") == fs and x.get("account_nm") == "자산총계":
                    v = num(x.get("thstrm_amount"))
                    if v is not None:
                        return round(v / 1e8), f"DART {YEAR} 사업보고서 {fs}", cc
    return None, "DART 재무 없음 (감사보고서 확인)", cc


def screen_listed(row, ftc, codes):
    out = dict(name=row["name"], corp_code=row["corp_code"], method="DART 최대주주 현황")
    h = top_holder(row["corp_code"])
    if h is None:
        return {**out, "result": "수동 확인", "why": f"{YEAR} 사업보고서 최대주주 현황 없음"}
    nm, p = h
    out.update(holder=nm, share=p)
    if not is_corp(nm):
        return {**out, "result": "해당 없음", "why": "최다 주주가 개인 (추정)"}
    if p < SHARE:
        return {**out, "result": "해당 없음", "why": f"법인 최다 주주 {p}% (30% 미만, 직접 기준)"}
    if is_foreign(nm):
        return {**out, "result": "수동 확인", "why": "외국 법인 30% 이상: 규칙 2 확인 (모회사 자산)"}
    a, src, cc = assets(nm, ftc, codes)
    out.update(holder_assets_eok=a, assets_source=src)
    if a is None:
        return {**out, "result": "수동 확인", "why": "최다 주주 법인 자산 미확인"}
    if a >= LIMIT_EOK:
        return {**out, "result": "후보: 중견 전환", "why": "규칙 4 (직접)"}
    # 한 단계 더: 최다 주주 법인의 최다 주주
    h2 = top_holder(cc) if cc else None
    if h2 is None:
        return {**out, "result": "수동 확인", "why": "주주 법인 자산 5,000억 미만. 그 위 주주 자료 없음"}
    nm2, p2 = h2
    ind = round(p * p2 / 100, 2)
    out.update(upper_holder=nm2, upper_share=p2, indirect_share=ind)
    if not is_corp(nm2) or ind < SHARE:
        return {**out, "result": "해당 없음", "why": f"간접 소유 {ind}% 또는 위 주주가 개인"}
    a2, src2, _ = assets(nm2, ftc, codes)
    out.update(upper_assets_eok=a2)
    if a2 is None:
        return {**out, "result": "수동 확인", "why": "위 주주 법인 자산 미확인"}
    if a2 >= LIMIT_EOK:
        return {**out, "result": "후보: 중견 전환", "why": "규칙 4 (간접 한 단계)"}
    return {**out, "result": "해당 없음", "why": "직접·간접 모두 5,000억 미만 법인"}


def identity(codes, fac):
    rows = []
    for name, cfg in IDENTITY.items():
        for c in codes[codes["k"] == name].itertuples():
            d = get_json("company", corp_code=c.corp_code)
            rows.append(dict(target=name, source="DART", corp_code=c.corp_code,
                             name=d.get("corp_name", c.corp_name), jurir_no=d.get("jurir_no", ""),
                             address=d.get("adres", ""), detail=f"업종 {d.get('induty_code', '')}",
                             ftc_jurir_match="일치" if cfg["ftc_jurir"] and d.get("jurir_no") == cfg["ftc_jurir"] else ""))
        for f in fac[fac["k"] == name].itertuples():
            rows.append(dict(target=name, source="등록공장 2024-12", corp_code="", name=f.회사명,
                             jurir_no="", address=f.공장주소, detail=f"{f.단지명 or ''} / {f.생산품}",
                             product_hint="단서 있음" if re.search(cfg["hint"], str(f.생산품)) else ""))
    return pd.DataFrame(rows)


def main():
    df = pd.read_csv(MERGED, dtype=str).fillna("")
    ftc = pd.read_excel(FTC, dtype=str)
    ftc["k"] = ftc["소속회사명"].map(key)
    codes = corp_codes()
    codes["k"] = codes["corp_name"].map(key)

    todo = df[(df["status"] == "확인 대기") & (df["size"] == "중소")]
    res = []
    for _, r in todo.iterrows():
        if r["listed"] == "상장":
            res.append(screen_listed(r, ftc, codes))
        else:
            res.append(dict(name=r["name"], corp_code=r["corp_code"], method="감사보고서 열람",
                            result="수동 확인", why="주석 '일반사항'의 최대주주·지분율 → 최대주주 자산"))
    size = pd.DataFrame(res)

    fac = pd.read_csv(FACTORY, encoding="cp949", dtype=str).fillna("")
    fac["k"] = fac["회사명"].map(key)
    iden = identity(codes, fac)

    PROC.mkdir(parents=True, exist_ok=True)
    size.to_csv(PROC / "mfg1_size_screen.csv", index=False, encoding="utf-8-sig")
    iden.to_csv(PROC / "mfg1_identity_candidates.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 50)
    print(f"[A·B 규모 재확인 {len(size)}곳]")
    print(size["result"].value_counts().to_string())
    cols = [c for c in ["name", "holder", "share", "holder_assets_eok", "result", "why"] if c in size]
    print("\n" + size[size["result"] != "해당 없음"][cols].to_string(index=False))
    print(f"\n[C 신원 확인 자료 {len(iden)}행]")
    show = iden[(iden["source"] == "DART") | (iden.get("product_hint", "") == "단서 있음")]
    print(show[["target", "source", "name", "jurir_no", "address", "detail"]].to_string(index=False))


if __name__ == "__main__":
    main()