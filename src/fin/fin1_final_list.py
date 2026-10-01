"""금융1-5 명단 파일 — 일곱 층을 같은 칸으로 합쳐 data/processed/fin_list.csv를 만듦

- 층과 입력
  1-1 코스피 상장 (fin_listed) · 1-2 금융 모회사의 종속 (fin_subsidiaries) · 1-2b 명단 밖 코스피 모회사의 종속
  (fin_nonfin_subs) · 1-3A 대기업집단 비상장 (fin_unlisted_group) · 1-3B 공공금융기관 (data/manual/
  fin_public_institutions) · 1-3C에서 옮긴 손자회사·공공기관 종속 (fin_indep_moved) · 1-3C 독립·외국계 (fin_indep_list)
- 공시 연도 (2026-07-08 금융위 최종안: 연결자산 10조 → 2028, 5조 → 2029, 2조 → 2030 검토)
  - 상장: 자체 값 / 종속: 지배회사의 공시 연도를 따름 (종속회사는 지배회사 연결 공시에 들어감)
  - 1-2b 지배회사(현대자동차 등 제조사)는 연결자산총액을 DART에서 받아 같은 기준으로 정함 (fin1_sector.assets)
  - 손자회사(메리츠캐피탈)는 지배회사의 지배회사 연도 / 비상장 비종속은 "대상 아님" / 공공은 "알리오"
- 업권: 1-3C는 DART 표준산업분류 코드로 정함 (fin1_list.final_sector). 코드가 없으면 FISIS 권역으로
- 제조 연계(mfg_link): 제조 35곳(data/manual/mfg_bank_borrowing.csv)의 main_banks(상위 6곳)와 policy_bank를 합쳐
  은행별 거래 곳 수를 셈. 전체 차입 조각·금액 재집계는 금융-2 ③-3에서 제조 94곳으로 함 (2026-10-01 결정)
  외국 은행(HSBC·Mizuho 등)은 명단에서 뺀 서울지점이라 따로 세어 출력만 함
- 검산: 합계, 층 사이 중복(법인등록번호·고유번호·이름), 공시 연도 빈칸

출력
  - data/processed/fin_list.csv : 금융 트랙 채점 대상 명단
  - data/processed/fin_mfg_link_unmatched.csv : 명단에 없는 제조 35곳 차입처 (외국 은행 등)
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import final_sector, key, s3_basis  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "fin_list.csv"
OUT_UNM = PROC / "fin_mfg_link_unmatched.csv"

LAYER = {
    "1-1": "상장", "1-2": "비상장 종속", "1-2b": "비상장 종속(명단 밖 코스피 모회사)",
    "1-3A": "비상장 비종속(대기업집단)", "1-3B": "공공금융기관", "move_sub": "비상장 종속(손자회사)",
    "move_pub": "공공기관 종속", "1-3C": "비상장 비종속(독립·외국계)"}
PART_SECTOR = {"국내은행": "은행", "생명보험": "생명보험", "손해보험": "손해보험", "증권사": "증권", "선물사": "선물",
               "신용카드사": "카드·할부금융", "할부금융사": "카드·할부금융", "리스사": "금융리스",
               "신기술금융사": "기타 여신금융", "상호저축은행": "저축은행·신협", "자산운용사": "신탁·집합투자",
               "부동산신탁": "신탁·집합투자", "종합금융회사": "은행·기타 예금기관", "금융지주회사": "금융지주"}
# 제조 35곳 차입처 표기 → 명단 계정 (법인 표기를 뗀 이름으로 대조)
BANK_ALIAS = {
    "산업은행": "한국산업은행", "KDB산업은행": "한국산업은행", "수출입은행": "한국수출입은행",
    "기업은행": "중소기업은행", "IBK기업은행": "중소기업은행", "하나은행": "하나은행", "KEB하나은행": "하나은행",
    "신한은행": "신한은행", "우리은행": "우리은행", "국민은행": "국민은행", "KB국민은행": "국민은행",
    "농협은행": "농협은행", "NH농협은행": "농협은행", "부산은행": "부산은행", "경남은행": "경남은행",
    "광주은행": "광주은행", "전북은행": "전북은행", "대구은행": "iM뱅크", "iM뱅크": "iM뱅크", "아이엠뱅크": "iM뱅크",
    "제주은행": "제주은행", "수협은행": "수협은행", "SC제일은행": "한국스탠다드차타드은행",
    "스탠다드차타드은행": "한국스탠다드차타드은행", "SC제일": "한국스탠다드차타드은행",
    "씨티은행": "한국씨티은행", "한국씨티은행": "한국씨티은행"}
# 영문 "Citi"는 한국씨티은행(국내 법인)이 아니라 씨티은행 해외 본·지점일 수 있어 연결하지 않음
NOT_LENDER = re.compile(r"사채|직접금융|회사채|CP|기업어음|^없음$|^-$")
# 특정 회사가 아니라 업권 이름만 적힌 차입처 — 명단 대조 대상이 아님 (2026-10-01 실제 기록에서 확인)
GENERIC = re.compile(r"^(저축은행|캐피탈|새마을금고|신협|보험사|증권사|카드사|은행|기타|금융기관|기타 금융기관)$")
YEAR_RANK = {"2028": 0, "2029": 1, "2030(검토)": 2}
COLS = ["account", "layer", "sector", "parent", "group", "assets_jo", "assets_basis", "disclosure_basis",
        "disclosure_year", "s3_basis", "mfg_link", "owner", "owner_rate", "owner_type", "pending",
        "source_grade", "corp_code", "jurir_no", "induty_code", "note"]


def read(path):
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def year_of(won):
    if won >= 10e12:
        return "2028"
    if won >= 5e12:
        return "2029"
    if won >= 2e12:
        return "2030(검토)"
    return "대상 아님(지배회사 2조 미만)"


def nonfin_parent_years(parents):
    """1-2b 지배회사(코스피, 업종 무관)의 연결자산 → 공시 연도. DART 재무제표 API (캐시 사용)
    지배회사 이름은 회사개황의 정식 이름(네이버(주)·엔에이치엔(주))이고 고유번호 목록은 다른 표기(NAVER·NHN)라
    이름끼리 대조하면 못 찾음 → 상장사 회사개황(1-2b 단계가 이미 받아 캐시함)으로 정식 이름 → 고유번호 표를 만듦 (2026-10-01)"""
    from dart_api import corp_codes, get_json  # noqa: E402
    from fin.fin1_sector import assets  # noqa: E402
    cc = corp_codes()
    cc = cc[cc["stock_code"].astype(str).str.strip() != ""]
    # 1) 회사개황 정식 이름 → 고유번호 (1-2b가 지배회사 이름을 여기서 가져왔으므로 가장 정확). 코스피(Y)만
    #    고유번호 목록의 이름을 먼저 쓰면 상장폐지된 같은 이름의 옛 법인을 고를 위험이 있음
    want, by = {key(p) for p in parents}, {}
    for c in cc["corp_code"]:
        try:
            d = get_json("company", corp_code=c)
        except Exception:  # noqa: BLE001
            continue
        if d.get("status") != "000" or d.get("corp_cls") != "Y":
            continue
        k = key(d.get("corp_name", ""))
        if k in want and k not in by:
            by[k] = c
            if len(by) == len(want):
                break
    # 2) 그래도 못 찾으면 고유번호 목록 이름으로 (예비)
    for n_, c in zip(cc["corp_name"], cc["corp_code"]):
        k = key(n_)
        if k in want:
            by.setdefault(k, c)
    out = {}
    for p in sorted(set(parents)):
        code = by.get(key(p), "")
        won, basis = assets(code) if code else (0, "")
        out[key(p)] = (year_of(won) if won else "확인 필요(자산 조회 실패)", round(won / 1e12, 2) if won else "",
                       basis)
    return out


def mfg_links(fin_accounts):
    """은행 계정 key → 제조 35곳 중 거래 곳 수, 그리고 명단에 없는 차입처 집계"""
    m = read(MANUAL / "mfg_bank_borrowing.csv")
    if not len(m):
        return {}, pd.DataFrame(columns=["lender", "mfg_n"])
    have = {key(a): a for a in fin_accounts}
    cnt, unm = {}, {}
    for r in m.to_dict("records"):
        toks = set()
        for col in ("main_banks", "policy_bank"):
            toks |= {t.strip() for t in re.split(r"[·,;/|]", str(r.get(col, ""))) if t.strip()}
        hit = set()
        for t in toks:
            if NOT_LENDER.search(t):
                continue
            if GENERIC.match(t):
                unm[f"{t} (업권 이름 — 특정 회사 아님)"] = unm.get(f"{t} (업권 이름 — 특정 회사 아님)", 0) + 1
                continue
            canon = BANK_ALIAS.get(t, t)
            k = key(canon)
            if k in have:
                hit.add(k)
            else:
                unm[t] = unm.get(t, 0) + 1
        for k in hit:
            cnt[k] = cnt.get(k, 0) + 1
    u = pd.DataFrame(sorted(unm.items(), key=lambda x: -x[1]), columns=["lender", "mfg_n"])
    return cnt, u


def main():
    L = read(PROC / "fin_listed.csv")
    S = read(PROC / "fin_subsidiaries.csv")
    N = read(PROC / "fin_nonfin_subs.csv")
    A = read(PROC / "fin_unlisted_group.csv")
    B = read(MANUAL / "fin_public_institutions.csv")
    M = read(PROC / "fin_indep_moved.csv")
    C = read(PROC / "fin_indep_list.csv")
    cand = read(PROC / "fin_indep_candidates.csv")
    ind = {key(a): c for a, c in zip(cand.get("account", []), cand.get("induty_code", []))}
    jur = {key(a): j for a, j in zip(cand.get("account", []), cand.get("jurir_no", []))}

    rows = []
    year_listed = {key(a): y for a, y in zip(L["account"], L["disclosure_year"])}
    for r in L.to_dict("records"):
        rows.append(dict(account=r["account"], layer=LAYER["1-1"], sector=r["sector"], assets_jo=r["assets_jo"],
                         assets_basis=r.get("assets_basis", ""), disclosure_basis="자본시장법",
                         disclosure_year=r["disclosure_year"], s3_basis=r["s3_basis"], corp_code=r["corp_code"],
                         jurir_no=r.get("jurir_no", ""), induty_code=r["induty_code"], note=r.get("note", "")))
    sub_parent = {}
    for r in S.to_dict("records"):
        y = year_listed.get(key(r["parent"]), "확인 필요")
        sub_parent[key(r["account"])] = r["parent"]
        rows.append(dict(account=r["account"], layer=LAYER["1-2"], sector=r["sector"], parent=r["parent"],
                         assets_jo=r["assets_jo"], assets_basis="출자현황 총자산", disclosure_basis="지배회사 연결 공시",
                         disclosure_year=y, s3_basis=r["s3_basis"], corp_code=r["corp_code"],
                         induty_code=r["induty_code"], note=r.get("note", "")))
    py = nonfin_parent_years(N["parent"]) if len(N) else {}
    for r in N.to_dict("records"):
        y, pa, pb = py.get(key(r["parent"]), ("확인 필요", "", ""))
        rows.append(dict(account=r["account"], layer=LAYER["1-2b"], sector=r["sector"], parent=r["parent"],
                         assets_jo=r["assets_jo"], assets_basis="출자현황 총자산", disclosure_basis="지배회사 연결 공시",
                         disclosure_year=y, s3_basis=r["s3_basis"], corp_code=r["corp_code"],
                         induty_code=r["induty_code"],
                         note=(r.get("note", "") + f" 지배회사 연결자산 {pa}조({pb})").strip() if pa else r.get("note", "")))
    for r in A.to_dict("records"):
        rows.append(dict(account=r["account"], layer=LAYER["1-3A"], sector=r["sector"], group=r["group"],
                         assets_jo=r["assets_jo"], assets_basis="공정위(별도로 보임)", disclosure_basis="없음",
                         disclosure_year="대상 아님", s3_basis=r["s3_basis"], jurir_no=r["jurir_no"],
                         induty_code=r.get("ftc_code", ""), note=r.get("note", "")))
    for r in B.to_dict("records"):
        rows.append(dict(account=r["account"], layer=LAYER["1-3B"], sector=r.get("sector", ""),
                         assets_jo=r.get("assets_jo", ""), assets_basis=r.get("assets_basis", ""),
                         disclosure_basis="알리오", disclosure_year="알리오",
                         s3_basis="제조업 여신·보증·보험 (보유액 × 제조업 비중)", source_grade=r.get("source_grade", ""),
                         note=f"보유액 {r.get('holding_jo', '')}조 · 제조업 {r.get('mfg_ratio_pct', '')}%"
                              f"({r.get('mfg_ratio_type', '')})"))
    for r in M.to_dict("records"):
        is_pub = r["layer"] == "공공기관 종속"
        par = r["parent"]
        gp = sub_parent.get(key(par), "")                         # 손자회사면 지배회사의 지배회사
        y = "알리오" if is_pub else year_listed.get(key(gp), year_listed.get(key(par), "확인 필요"))
        sec = final_sector(r["account"], ind.get(key(r["account"]), "")) if ind.get(key(r["account"])) \
            else PART_SECTOR.get(r["part_nm"], "확인 필요")
        rows.append(dict(account=r["account"], layer=LAYER["move_pub" if is_pub else "move_sub"], sector=sec,
                         parent=par, assets_jo=r["assets_jo"], assets_basis="FISIS 2025-12",
                         disclosure_basis="지배회사 연결 공시" + (" (알리오)" if is_pub else ""), disclosure_year=y,
                         s3_basis=s3_basis(sec), owner=r["owner"], owner_rate=r["owner_rate"],
                         owner_type=r["owner_type"], pending=r["pending"], source_grade=r["source_grade"],
                         corp_code=r["corp_code"], jurir_no=jur.get(key(r["account"]), ""),
                         induty_code=ind.get(key(r["account"]), ""),
                         note=f"손자회사 — {gp}" if gp else ""))
    for r in C.to_dict("records"):
        code = ind.get(key(r["account"]), "")
        sec = final_sector(r["account"], code) if code else PART_SECTOR.get(r["part_nm"], "확인 필요")
        rows.append(dict(account=r["account"], layer=LAYER["1-3C"], sector=sec, assets_jo=r["assets_jo"],
                         assets_basis="FISIS 2025-12", disclosure_basis="없음", disclosure_year="대상 아님",
                         s3_basis=s3_basis(sec), owner=r["owner"], owner_rate=r["owner_rate"],
                         owner_type=r["owner_type"], pending=r["pending"], source_grade=r["source_grade"],
                         corp_code=r["corp_code"], jurir_no=jur.get(key(r["account"]), ""), induty_code=code))

    f = pd.DataFrame(rows).reindex(columns=COLS).fillna("")
    cnt, unm = mfg_links(f["account"])
    f["mfg_link"] = [str(cnt.get(key(a), "")) for a in f["account"]]
    f["n"] = pd.to_numeric(f["assets_jo"], errors="coerce")
    f = f.sort_values(["layer", "n"], ascending=[True, False]).drop(columns="n")
    PROC.mkdir(parents=True, exist_ok=True)
    f.to_csv(OUT, index=False, encoding="utf-8-sig")
    unm.to_csv(OUT_UNM, index=False, encoding="utf-8-sig")

    # 검산
    dup = []
    for col, label in (("jurir_no", "법인등록번호"), ("corp_code", "고유번호")):
        v = f[f[col].str.replace("-", "") != ""]
        d = v[v[col].str.replace("-", "").duplicated(keep=False)]
        if len(d):
            dup.append((label, d[["account", "layer", col]]))
    kk = f["account"].map(key)
    d = f[kk.duplicated(keep=False)]
    if len(d):
        dup.append(("이름", d[["account", "layer"]]))
    blank = f[f["disclosure_year"].isin(["", "확인 필요"]) | f["disclosure_year"].str.startswith("확인 필요")]

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 100)
    print(f"명단 {len(f)}곳 → {OUT.relative_to(ROOT)}")
    print("\n[층별]")
    print(f["layer"].value_counts().reindex(list(LAYER.values())).fillna(0).astype(int).to_string())
    print("\n[공시 연도]")
    print(f["disclosure_year"].value_counts().to_string())
    print("\n[층 사이 중복]", "없음" if not dup else "")
    for label, d in dup:
        print(f"  {label}:")
        print(d.to_string(index=False))
    if len(blank):
        print(f"\n[공시 연도 확인 필요 {len(blank)}곳]")
        print(blank[["account", "layer", "parent", "disclosure_year"]].to_string(index=False))
    link = f[f["mfg_link"] != ""].sort_values("mfg_link", key=lambda s: s.astype(int), ascending=False)
    print("\n[제조 연계 — 제조 35곳 중 거래 곳 수]")
    print(link[["account", "layer", "mfg_link"]].to_string(index=False) if len(link) else "  없음")
    if len(unm):
        print(f"\n[명단에 없는 차입처 — 외국 은행 서울지점 등, 참고] → {OUT_UNM.relative_to(ROOT)}")
        print(unm.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
