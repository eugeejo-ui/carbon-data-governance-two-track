"""금융1-3C 2단계 — FISIS 회사별 총자산 수집 → 자산 2조 이상 → 이미 명단에 있는 곳 제외

- 1단계(fin1_fisis_catalog.py) 결과 companies.csv의 영업 중 회사(외은지점 제외)를 대상으로 함
- 권역별 총자산 통계코드·항목코드는 1단계 결과를 보고 확정함 (2026-10-01)
  - 연결 우선: 국내은행 SA022 → 없으면 SA003, 금융지주 SL003 → 없으면 SL019
  - 신탁계정(SA007·SM006)·실적배당형 특별계정(SH152·SI148)은 고객 자산이라 쓰지 않음
- 기준 시점 2025년 12월 말(분기 Q, 202512)
- 이미 명단에 있는지는 법인등록번호로 대조함 (2026-10-01 결정). FISIS에는 법인등록번호가 없으므로
  1) 2조 이상 회사를 DART 고유번호 목록에서 이름으로 찾고 (법인 표기 제거 후 일치 → 안 되면 음역 변환 후 일치)
  2) DART 회사개황에서 법인등록번호를 받아
  3) 확정 명단(상장·종속·1-3A)의 법인등록번호와 대조함. 번호가 없는 곳(공공 5곳 등)은 이름으로 보조 대조
- DART에서 같은 이름이 여럿이면 금융업 코드(64·65·66)인 곳을 고름. 그래도 여럿이거나 못 찾으면 "확인 필요"로 표시
- 새 후보에는 DART 고유번호가 붙어 이후 감사보고서 조회에 씀
- 2조 이상인데 명단에 없는 곳 중 아래는 새 후보에서 뺌 (2026-10-01 검토 결과를 규칙으로 옮김)
  - 외국 증권사·은행의 "서울지점" — 한국 법인이 아닌 지점이라 결정은 본사 (외은지점과 같은 원칙)
  - 코스닥·코넥스 상장 — 금융1-1 코스피 한정 원칙과 같게
  - 코스피 상장 — 금융1-1에서 이미 판단하고 뺀 곳 (일반 지주·2조 미만 등)
  - DART에서 못 찾았으나 자산이 명단의 한 계정과 0.5% 안에서 같고 업권도 같음 — 이름만 바꾼 같은 회사로 추정
    (예: FISIS "디지비금융지주" = 명단 "아이엠금융지주", 둘 다 금융지주 98.86조)
    DART에 같은 이름이 여럿인 경우에는 쓰지 않음 — BMW파이낸셜(리스 9.474조)이 우리투자증권(증권 9.47조)과
    우연히 맞아 잘못 빠진 사례에서 두 조건을 추가함 (2026-10-01)
- 음역 대조(name2)는 fin1_list.py의 공통 음역표를 씀
- 출처: 금융감독원 FISIS OPEN API (업무보고서 기반, 국가승인통계 아님)

출력
  - data/processed/fisis/fisis_assets.csv : 영업 중 전 회사의 2025년 12월 말 총자산
  - data/processed/fisis/fisis_big.csv : 자산 2조 이상 전체와 판정(이미 명단·제외·새 후보) — 추적용
  - data/processed/fin_indep_candidates.csv : 2조 이상이면서 명단에 없는 회사 (1-3C 후보)
"""
from pathlib import Path
import difflib
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_fisis_catalog import OUT as FOUT, LimitReached, call, rows  # noqa: E402
from fin.fin1_unlisted import jurir_of  # noqa: E402
from fin.fin1_list import key, name2  # noqa: E402
from dart_api import corp_codes, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
ASSETS_OUT = FOUT / "fisis_assets.csv"
BIG_OUT = FOUT / "fisis_big.csv"                    # 2조 이상 전체와 판정 (추적용)
CAND_OUT = PROC / "fin_indep_candidates.csv"

BASE_MM = "202512"
ASSET_MIN_JO = 2.0
# 권역 → [(통계코드, 자산총계 항목코드, 기준)] 앞에서부터 시도
ASSET_TABLE = {
    "A": [("SA022", "A", "연결"), ("SA003", "A", "은행계정")],
    "H": [("SH150", "A", "전체")], "I": [("SI146", "A", "전체")],
    "F": [("SF303", "I", "별도")], "W": [("SW303", "I", "별도")], "G": [("SG202", "A", "별도")],
    "C": [("SC103", "A", "별도")], "K": [("SK103", "A", "별도")], "T": [("ST103", "A", "별도")],
    "N": [("SN103", "A", "별도")], "E": [("SE003", "A", "별도")], "D": [("SD103", "A8", "별도")],
    "M": [("SM005", "A", "고유계정")],
    "L": [("SL003", "A", "연결"), ("SL019", "A", "개별")],
}
UNIT = {"조원": 1, "억원": 1e4, "백만원": 1e6, "천원": 1e9, "원": 1e12}
FUZZY_MIN = 0.75
SAME_ASSET_TOL = 0.005                              # 자산 일치 판단 허용 오차 0.5%
BRANCH = re.compile(r"지점$|서울지점")
# FISIS 권역 → 같은 회사로 볼 수 있는 명단 업권 (자산 일치 규칙에서 업권이 맞는지 볼 때만 씀)
PART_SECTORS = {
    "A": {"은행", "은행·기타 예금기관"}, "H": {"생명보험"}, "I": {"손해보험", "보증보험", "재보험"},
    "F": {"증권"}, "W": {"선물", "증권"}, "G": {"신탁·집합투자", "금융지원 서비스"},
    "C": {"카드·할부금융"}, "K": {"금융리스", "카드·할부금융", "기타 여신금융", "여신금융"},
    "T": {"카드·할부금융", "여신금융", "기타 여신금융", "금융리스"},
    "N": {"기타 여신금융", "신탁·집합투자", "여신금융", "카드·할부금융", "금융리스"},
    "E": {"저축은행·신협"}, "D": {"은행·기타 예금기관", "그외 기타 금융"},
    "M": {"신탁·집합투자", "그외 기타 금융"}, "L": {"금융지주"},
}
HAVE_FILES = [PROC / "fin_listed.csv", PROC / "fin_subsidiaries.csv", PROC / "fin_nonfin_subs.csv",
              PROC / "fin_unlisted_group.csv", MANUAL / "fin_public_institutions.csv"]


FIN_WORDS = ("은행", "보험", "생명", "화재", "증권", "캐피탈", "카드", "저축", "금융", "투자",
             "자산운용", "신탁", "파이낸셜", "리스", "선물", "종합금융")


def dart_index():
    """DART 고유번호 목록 → (법인표기 뗀 이름 → [corp_code]), (음역 변환 이름 → [corp_code]), 금융 이름 목록"""
    cc = corp_codes()
    by_key, by_norm = {}, {}
    for code, nm in zip(cc["corp_code"], cc["corp_name"]):
        by_key.setdefault(key(nm), []).append((code, nm))
        by_norm.setdefault(norm(nm), []).append((code, nm))
    fin_names = {}                                   # 음역 변환 이름 → DART 원래 이름 (못 찾았을 때 추천용)
    for code, nm in zip(cc["corp_code"], cc["corp_name"]):
        if any(w in nm for w in FIN_WORDS):
            fin_names.setdefault(norm(nm), nm)
    return by_key, by_norm, fin_names


def dart_company(corp_code):
    try:
        c = get_json("company", corp_code=corp_code)
    except Exception:  # noqa: BLE001
        return {}
    return c if c.get("status") == "000" else {}


def match_dart(fisis_nm, by_key, by_norm, fin_names):
    """FISIS 회사명 → (corp_code, DART 이름, 회사개황, 대조 근거)"""
    for basis, pool, k in (("DART 이름 일치", by_key, key(fisis_nm)), ("DART 음역 일치", by_norm, norm(fisis_nm))):
        hits = pool.get(k, [])
        if not hits:
            continue
        infos = [(code, nm, dart_company(code)) for code, nm in hits]
        fin = [x for x in infos if str(x[2].get("induty_code", "")).startswith(("64", "65", "66"))]
        pick = fin if fin else infos
        if len(pick) == 1:
            return pick[0][0], pick[0][1], pick[0][2], basis
        return "", " / ".join(nm for _, nm, _ in pick), {}, f"{basis} — 같은 이름 {len(pick)}곳, 확인 필요"
    near = difflib.get_close_matches(norm(fisis_nm), list(fin_names), n=1, cutoff=FUZZY_MIN)
    hint = f"비슷한 DART 이름: {fin_names[near[0]]}" if near else "비슷한 DART 이름 없음"
    return "", "", {}, f"DART에서 못 찾음 — 확인 필요 ({hint})"


def norm(name):
    """이름 대조 키 — fin1_list.name2와 같음 (공통 음역표)"""
    return name2(name)


def asset_of(fcd, list_no, acc):
    """(총자산 조, 단위, 상태) — 상태: ok / no_data / bad_unit / err_XXX"""
    res = call("statisticsInfoSearch", financeCd=fcd, listNo=list_no, accountCd=acc,
               term="Q", startBaseMm=BASE_MM, endBaseMm=BASE_MM)
    if res.get("err_cd") != "000":
        return None, "", f"err_{res.get('err_cd')}"
    rs = rows(res)
    if not rs:
        return None, "", "no_data"
    # 실제 JSON 구조(2026-10-01 확인): description = [{column_id, column_nm}, ...],
    # unit은 result 바로 아래에 컬럼 순서대로 쉼표 구분("원,%"). 금액 컬럼 이름은 "잔액"
    desc = res.get("description") or []
    if isinstance(desc, dict):                      # XML식 구조로 올 때 대비
        cols, units_raw = desc.get("column") or [], desc.get("unit") or res.get("unit", "")
    else:
        cols, units_raw = desc, res.get("unit", "")
    cols = [cols] if isinstance(cols, dict) else list(cols)
    units = [u.strip() for u in str(units_raw).split(",")]
    idx = next((i for i, c in enumerate(cols) if re.search(r"잔액|금액|합계", str(c.get("column_nm", "")))), 0)
    col = cols[idx].get("column_id", "a") if cols else "a"
    unit = units[idx] if idx < len(units) else (units[0] if units else "")
    try:
        v = float(str(rs[0].get(col, "")).replace(",", ""))
    except ValueError:
        return None, unit, "no_data"
    if unit not in UNIT:
        return None, unit, "bad_unit"
    return round(v / UNIT[unit], 4), unit, "ok"


def main():
    comp = pd.read_csv(FOUT / "companies.csv", dtype=str).fillna("")
    comp = comp[(comp["closed"].str.lower() != "true") & (comp["part"] != "J")]
    print(f"대상 {len(comp)}곳 (영업 중, 외은지점 제외) — 기준 {BASE_MM}")
    out = []
    try:
        for i, r in enumerate(comp.to_dict("records"), 1):
            if i % 100 == 0:
                print(f"  {i}/{len(comp)} …")
            val, unit, st, used = None, "", "no_table", ""
            for list_no, acc, basis in ASSET_TABLE.get(r["part"], []):
                val, unit, st = asset_of(r["finance_cd"], list_no, acc)
                if st == "ok":
                    used = f"{list_no}({basis})"
                    break
            out.append({**r, "assets_jo": val, "unit": unit, "status": st, "table": used})
    except LimitReached as e:
        print(f"\n[멈춤] {e}")
    a = pd.DataFrame(out)
    a.to_csv(ASSETS_OUT, index=False, encoding="utf-8-sig")

    # 확정 명단의 법인등록번호·이름
    have_j, have_n, have_a = set(), {}, []
    for p in HAVE_FILES:
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str).fillna("")
        have_n.update({norm(x): x for x in df["account"]})
        acol = "assets_jo" if "assets_jo" in df.columns else ("holding_jo" if "holding_jo" in df.columns else "")
        if acol:
            secs = df["sector"] if "sector" in df.columns else [""] * len(df)
            have_a += [(x, float(v), sc) for x, v, sc in zip(df["account"], df[acol], secs) if str(v).strip()]
        if "jurir_no" in df.columns:
            have_j |= set(df["jurir_no"].str.replace("-", "")) - {""}
        if "corp_code" in df.columns:
            have_j |= {jurir_of(c) for c in df["corp_code"] if c} - {""}

    big = a[a["assets_jo"].fillna(0) >= ASSET_MIN_JO].copy()
    by_key, by_norm, fin_names = dart_index()
    recs = []
    for r in big.to_dict("records"):
        code, dname, info, basis = match_dart(r["finance_nm"], by_key, by_norm, fin_names)
        j = str(info.get("jurir_no", "")).replace("-", "")
        same = [x for x, v, sc in have_a
                if v and abs(r["assets_jo"] - v) <= SAME_ASSET_TOL * v
                and sc in PART_SECTORS.get(r["part"], set())] \
            if basis.startswith("DART에서 못 찾음") else []
        cls = str(info.get("corp_cls", ""))
        if j and j in have_j:
            where = "이미 명단 — 법인등록번호 일치"
        elif norm(r["finance_nm"]) in have_n or (dname and norm(dname) in have_n):
            where = "이미 명단 — 이름 일치"
        elif len(same) == 1:
            where = f"이미 명단 — 자산 일치(옛 이름 추정: {same[0]}, 확인 필요)"
        elif BRANCH.search(str(r["finance_nm"])):
            where = "제외 — 외국 금융회사 서울지점 (결정은 본사)"
        elif cls in ("K", "N"):
            where = "제외 — 코스닥·코넥스 상장 (금융1-1 코스피 한정 원칙)"
        elif cls == "Y":
            where = "제외 — 코스피 상장 (금융1-1에서 이미 판단)"
        else:
            where = "새 후보"
        recs.append({**r, "dart_name": dname, "corp_code": code, "jurir_no": j,
                     "induty_code": info.get("induty_code", ""), "corp_cls": info.get("corp_cls", ""),
                     "dart_match": basis, "where": where})
    b = pd.DataFrame(recs)
    if len(b):
        b.sort_values("assets_jo", ascending=False).to_csv(BIG_OUT, index=False, encoding="utf-8-sig")
    new = b[b["where"] == "새 후보"].copy() if len(b) else b
    fz = []
    for k in new["finance_nm"].map(norm) if len(new) else []:
        m = difflib.get_close_matches(k, list(have_n), n=1, cutoff=FUZZY_MIN)
        fz.append((have_n[m[0]], round(difflib.SequenceMatcher(None, k, m[0]).ratio(), 2)) if m else ("", ""))
    if len(new):
        new["similar_in_list"] = [x[0] for x in fz]
        new["similarity"] = [x[1] for x in fz]
    cols = ["finance_nm", "part_nm", "assets_jo", "table", "dart_name", "corp_code", "jurir_no",
            "induty_code", "corp_cls", "dart_match", "similar_in_list", "similarity", "finance_cd"]
    (new.sort_values("assets_jo", ascending=False)[cols] if len(new) else pd.DataFrame(columns=cols)).rename(
        columns={"finance_nm": "account"}).to_csv(CAND_OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 300)
    print(f"\n총자산 수집 {len(a)}곳 → {ASSETS_OUT.relative_to(ROOT)}")
    print(a["status"].value_counts().to_string())
    print(f"\n자산 {ASSET_MIN_JO:.0f}조 이상 {len(b)}곳")
    if len(b):
        print(b["where"].str.split(" — ").str[0].value_counts().to_string())
        print(f"  (판정 전체 → {BIG_OUT.relative_to(ROOT)})")
        drop = b[b["where"].str.startswith(("제외", "이미 명단 — 자산"))]
        if len(drop):
            print("\n[규칙으로 뺀 곳 — 사유 확인]")
            print(drop[["finance_nm", "assets_jo", "where"]].to_string(index=False))
        print("\n[DART 대조 근거]")
        print(b["dart_match"].value_counts().to_string())
        print("\n[권역별 2조 이상 / 새 후보]")
        print(pd.DataFrame({"2조이상": b.groupby("part_nm").size(),
                            "새후보": new.groupby("part_nm").size()}).fillna(0).astype(int).to_string())
        print(f"\n[1-3C 후보 — 자산 순] → {CAND_OUT.relative_to(ROOT)}")
        print(new.sort_values("assets_jo", ascending=False)[
            ["finance_nm", "part_nm", "assets_jo", "dart_name", "corp_cls", "dart_match"]].to_string(index=False))
        chk = new[(new["similar_in_list"] != "") | (new["corp_code"] == "")]
        if len(chk):
            print("\n[확인 필요 — DART에서 못 찾았거나, 명단에 비슷한 이름이 있음]")
            print(chk[["finance_nm", "dart_name", "dart_match", "similar_in_list", "similarity", "assets_jo"]].to_string(index=False))
    bad = a[~a["status"].isin(["ok", "no_data"])]
    if len(bad):
        print("\n[자산을 못 읽은 회사 — 단위·오류 확인]")
        print(bad[["part_nm", "finance_nm", "status", "unit"]].to_string(index=False))


if __name__ == "__main__":
    main()
