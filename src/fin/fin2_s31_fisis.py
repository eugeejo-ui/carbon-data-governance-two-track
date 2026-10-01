"""금융2-4 ③-1 FISIS 2단계 — 회사별 제조업 대출 비중 (은행·저축은행), 보험은 숫자만 받아 둠

- 먼저 fin2_s31_fisis_probe.py(1단계)를 실행해 두어야 함 — 회사코드 대조 함수를 함께 씀
- 기준 시점: 2025년 12월 말. 분기(Q) 자료가 없으면 반기(H) → 연(Y) 순으로 찾음
- 계산식 (2026-10-01 확정, 04 문서 반영 대기)
  - 은행: 제조업 대출 SA044·A2 ÷ 전체 대출 SA047·D(원화대출금, 은행간 대여금 제외)
  - 저축은행: 제조업 대출 SE036·A1 ÷ 전체 대출 SE020·D(용도별 대출 합계)
  - 참고 비중: 기업대출 중 제조업(SA044·A / SE036·A 대비) — 점수에 쓰지 않음, 한국은행 통계와 비교하는 검산용
  - 보험: SH122·SI122 제조업(B)·기업대출 계(I)만 받아 둠 — 계가 기업대출만이라 확정 기준과 어긋나 비중 계산은 보류
- 검산
  - 기업대출 계 ≤ 전체 대출
  - 같은 전체 대출을 다른 기준으로 나눈 합계와 같은지 (은행 SA045·D·SA046·D, 저축은행 SE021·E) — 차이 0.5% 넘으면 표시
- 출력: data/processed/fin_s31_fisis.csv (금액은 억 원)
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_fisis_catalog import LimitReached, call, rows  # noqa: E402
from fin.fin2_s31_fisis_probe import company_map  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fin_s31_fisis.csv"
BASE_MM = "202512"
TERMS = ("Q", "H", "Y")
TOL = 0.005
BANK_GAP_MAX = 0.05                                # 은행: 다른 기준 합계 − 전체 대출 = 은행간 대여금으로 봄 (0 이상 5% 이하면 정상)
UNIT_EOK = {"조원": 1e4, "억원": 1.0, "백만원": 1e-2, "천원": 1e-5, "원": 1e-8}
BOK_CORP_MFG = 502.7 / 2026.1                      # 한국은행 2025년 말 산업별대출금 중 제조업 비중 (약 24.8%)

# 권역 → 받을 값: 이름 → (통계코드, 항목코드)
SPEC = {
    "A": {"group": "은행", "mfg": ("SA044", "A2"), "corp": ("SA044", "A"), "total": ("SA047", "D"),
          "alt": [("SA045", "D"), ("SA046", "D")]},
    "E": {"group": "저축은행", "mfg": ("SE036", "A1"), "corp": ("SE036", "A"), "total": ("SE020", "D"),
          "alt": [("SE021", "E")]},
    "H": {"group": "생명보험", "mfg": ("SH122", "B"), "corp": ("SH122", "I")},
    "I": {"group": "손해보험", "mfg": ("SI122", "B"), "corp": ("SI122", "I")},
}
COLS_SEEN = {}                                     # 통계코드 → 값을 읽은 칸 이름 (확인용 출력)


def value(fcd, list_no, acc):
    """(억 원, 상태, 기간) — 상태: ok / no_data / bad_unit / err_XXX"""
    last = "no_data"
    for term in TERMS:
        res = call("statisticsInfoSearch", financeCd=fcd, listNo=list_no, accountCd=acc,
                   term=term, startBaseMm=BASE_MM, endBaseMm=BASE_MM)
        if res.get("err_cd") != "000":                     # 오류 번호와 FISIS 설명을 함께 남김
            last = f"err_{res.get('err_cd')}({str(res.get('err_msg', '')).strip()})"
            continue
        rs = rows(res)
        if not rs:
            continue
        desc = res.get("description") or []
        if isinstance(desc, dict):
            cols, units_raw = desc.get("column") or [], desc.get("unit") or res.get("unit", "")
        else:
            cols, units_raw = desc, res.get("unit", "")
        cols = [cols] if isinstance(cols, dict) else list(cols)
        units = [u.strip() for u in str(units_raw).split(",")]
        idx = next((i for i, c in enumerate(cols) if re.search(r"잔액|금액|합계", str(c.get("column_nm", "")))), 0)
        col = cols[idx].get("column_id", "a") if cols else "a"
        COLS_SEEN.setdefault(list_no, [str(c.get("column_nm", "")) for c in cols] + [f"→ 사용: {idx + 1}번째"])
        unit = units[idx] if idx < len(units) else (units[0] if units else "")
        if unit not in UNIT_EOK:
            return None, f"bad_unit({unit})", term
        try:
            v = float(str(rs[0].get(col, "")).replace(",", ""))
        except ValueError:
            continue
        return round(v * UNIT_EOK[unit], 2), "ok", term
    return None, last, ""


def collect(M):
    out = []
    for _, r in M.iterrows():
        cds, nms = r["finance_cd"].split(";"), r["finance_nm"].split(";")
        if r["match"] in ("없음", "여러 곳", "직접 연결 실패") or not cds[0]:
            out.append(dict(account=r["account"], sector=r["sector"], status=f"회사코드 {r['match']}"))
            continue
        part = r["parts"] if len(r["parts"]) == 1 else None
        if part is None:                                   # 여러 권역에서 찾은 경우 — 실제 권역은 회사 목록에서
            C = pd.read_csv(PROC / "fisis" / "companies.csv", dtype=str)
            part = C.loc[C["finance_cd"] == cds[0], "part"].iloc[0]
        sp = SPEC.get(part)
        if sp is None:
            out.append(dict(account=r["account"], sector=r["sector"], part=part, status="업종 표 없는 권역"))
            continue
        row = dict(account=r["account"], sector=r["sector"], layer=r["layer"], part=part, group=sp["group"],
                   finance_cd=cds[0], finance_nm=nms[0], match=r["match"])
        notes = []
        for k in ("mfg", "corp", "total"):
            if k in sp:
                v, st, term = value(cds[0], *sp[k])
                row[f"{k}_eok"] = v
                if st != "ok":
                    notes.append(f"{k} {st}")
                elif term != "Q":
                    notes.append(f"{k} {term}기준")
        for i, (ln, ac) in enumerate(sp.get("alt", []), 1):
            v, st, _ = value(cds[0], ln, ac)
            row[f"alt{i}_eok"] = v
        m, c, t = row.get("mfg_eok"), row.get("corp_eok"), row.get("total_eok")
        if "total" in sp and m is not None and t:
            row["share_total"] = round(m / t * 100, 2)
        if m is not None and c:
            row["share_corp"] = round(m / c * 100, 2)
        if c is not None and t is not None and c > t * (1 + TOL):
            notes.append("검산: 기업대출 계 > 전체 대출")
        for i in (1, 2):
            a = row.get(f"alt{i}_eok")
            if a is None or not t:
                continue
            gap = (a - t) / t
            if part == "A":
                # 은행 용도별·담보별 합계(SA045·SA046)는 은행간 대여금을 포함하고, 분모 SA047·D는 뺀 값 → 차이가 0 이상이 정상
                if gap < -TOL or gap > BANK_GAP_MAX:
                    notes.append(f"검산: 다른 기준 합계{i} 차이 {gap * 100:+.1f}%")
                elif i == 1 and gap > TOL:
                    row["interbank_pct"] = round(gap * 100, 2)
            elif abs(gap) > TOL:
                notes.append(f"검산: 다른 기준 합계{i} 차이 {gap * 100:+.1f}%")
        if part in ("H", "I"):
            notes.append("보험 — 분모 미정, 숫자만 받아 둠")
        row["status"] = "ok" if not [x for x in notes if not x.startswith("보험")] else "확인"
        row["note"] = " · ".join(notes)
        out.append(row)
    cols = ["account", "sector", "layer", "part", "group", "finance_cd", "finance_nm", "match",
            "mfg_eok", "corp_eok", "total_eok", "alt1_eok", "alt2_eok", "interbank_pct", "share_total", "share_corp",
            "status", "note"]
    return pd.DataFrame(out).reindex(columns=cols)


def main():
    M = company_map()
    try:
        D = collect(M)
    except LimitReached as e:
        print(f"\n[멈춤] {e}")
        return
    D.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 300)
    print(f"기준 {BASE_MM} · 대상 {len(D)}곳 → {OUT.relative_to(ROOT)}\n")
    print("[1] 값을 읽은 칸 (통계코드별 — 칸이 여러 개면 금액 칸을 골랐는지 확인)")
    for ln, cs in COLS_SEEN.items():
        print(f"  {ln}: {' | '.join(cs)}")
    print("\n[2] 집단별 수집 결과")
    print(D.groupby(["group", "status"], dropna=False).size().rename("곳").reset_index().to_string(index=False))
    bank = D[D["group"].isin(["은행", "저축은행"]) & D["share_total"].notna()]
    print("\n[3] 제조업 비중 분포 (전체 대출 대비, %) — 점수용")
    if len(bank):
        print(bank.groupby("group")["share_total"].describe()[["count", "min", "25%", "50%", "75%", "max"]].round(1).to_string())
    print("\n[4] 한국은행 통계와 비교 (집단 합산)")
    for g, x in bank.groupby("group"):
        corp = x["mfg_eok"].sum() / x["corp_eok"].sum() * 100 if x["corp_eok"].sum() else float("nan")
        tot = x["mfg_eok"].sum() / x["total_eok"].sum() * 100
        print(f"  {g}: 기업대출 중 제조업 {corp:.1f}% (한국은행 예금취급기관 {BOK_CORP_MFG * 100:.1f}%) · 전체 대출 중 제조업 {tot:.1f}%")
    ib = D[D["interbank_pct"].notna()] if "interbank_pct" in D else D.iloc[0:0]
    if len(ib):
        print("\n[4-1] 은행간 대여금으로 보이는 차이 (용도별 합계 − 전체 대출, 정상 범위)")
        print("  " + " · ".join(f"{a} {v:.1f}%" for a, v in zip(ib["account"], ib["interbank_pct"])))
    print("\n[5] 확인할 계정")
    chk = D[D["status"] != "ok"]
    print(chk[["account", "group", "status", "note"]].to_string(index=False) if len(chk) else "  없음")
    print("\n[6] 은행·저축은행 비중 (큰 순)")
    print(bank.sort_values("share_total", ascending=False)[
        ["account", "group", "mfg_eok", "corp_eok", "total_eok", "share_total", "share_corp"]].to_string(index=False))


if __name__ == "__main__":
    main()
