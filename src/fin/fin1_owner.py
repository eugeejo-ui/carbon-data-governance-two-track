"""금융1-3C 3단계 — 후보의 소유 구조 확인 → 층 확정

- 입력: data/processed/fin_indep_candidates.csv (fin1_indep.py 결과), data/manual/fin_indep_decisions.csv (판단 파일)
- 최대주주·지분율은 근거 등급이 높은 순서로 고름 (2026-10-01 원칙 점검 후 개정)
  1) DART 최대주주 현황(hyslrSttus) — 사업보고서 원문, 1등급
     2025 사업보고서 → 3분기 → 반기 → 2024 사업보고서
  2) DART 감사보고서 원문의 주주 현황 표 — 1등급 (fin1_audit.py). 사업보고서를 내지 않는 비상장 금융회사용
     DART 고유번호가 여럿이면(같은 이름) 모두 조회해 가장 최근 감사보고서를 씀
  3) 판단 파일의 값 — 신용평가(3)·언론 등. 1·2가 모두 안 될 때만 씀
- 층·소유 유형·매각 진행은 판단 파일의 결정을 따름 (손자회사·공공기관 종속 이동 등)
  판단 파일 지분율과 1등급 값이 2%p 넘게 다르면 "지분율 차이"로 표시
- 매각 진행 중 상장 인수자(한국금융지주·한화생명)의 공시 목록을 DART에서 새로 받아 함께 저장함

출력
  - data/processed/fin_indep_owners.csv : 후보 전체의 최대주주·근거·층
  - data/processed/fin_indep_list.csv : 1-3C 확정 명단 (이동한 곳 제외)
  - data/processed/fin_indep_moved.csv : 다른 층으로 옮긴 곳
  - data/processed/fin_indep_pending_disclosures.csv : 인수자 공시 목록
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402
from fin.fin1_list import FALLBACK_REPORTS, YEAR, key, to_f  # noqa: E402
from fin.fin1_audit import acquirer_disclosures, audit_owner  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
CAND = PROC / "fin_indep_candidates.csv"
DECISIONS = MANUAL / "fin_indep_decisions.csv"
OUT_ALL = PROC / "fin_indep_owners.csv"
OUT_LIST = PROC / "fin_indep_list.csv"
OUT_MOVED = PROC / "fin_indep_moved.csv"
OUT_PENDING = PROC / "fin_indep_pending_disclosures.csv"

RATE_GAP = 2.0
TOTAL_ROW = re.compile(r"^(합\s*계|계|소\s*계)$")


def periods():
    return [(YEAR, "11011", f"{YEAR} 사업보고서")] + \
           [(YEAR, rc, f"{YEAR} {nm}") for rc, nm in FALLBACK_REPORTS] + \
           [(str(int(YEAR) - 1), "11011", f"{int(YEAR) - 1} 사업보고서")]


def owners_api(corp_code):
    """(최대주주, 지분율, 상위 3명, 기준 보고서, 상태) — 사업보고서 최대주주 현황, 보통주 기말"""
    tried = []
    for y, rc, label in periods():
        try:
            d = get_json("hyslrSttus", corp_code=corp_code, bsns_year=y, reprt_code=rc)
        except Exception as e:  # noqa: BLE001
            tried.append(f"{label} 오류 {str(e)[:30]}")
            continue
        rows = []
        for r in d.get("list") or []:
            nm = str(r.get("nm") or "").strip()
            if not nm or TOTAL_ROW.match(nm) or "우선" in str(r.get("stock_knd") or ""):
                continue
            rate = to_f(r.get("trmend_posesn_stock_qota_rt")) or to_f(r.get("bsis_posesn_stock_qota_rt"))
            if rate > 0:
                rows.append((nm, rate, str(r.get("relate") or "").strip()))
        if d.get("status") == "000" and rows:
            rows.sort(key=lambda x: -x[1])
            top3 = " · ".join(f"{n} {v:.2f}%" + (f"({rl})" if rl else "") for n, v, rl in rows[:3])
            return rows[0][0], rows[0][1], top3, label, "ok"
        tried.append(f"{label} {d.get('status', '')}")
    return "", None, "", "", "사업보고서 없음 — " + "; ".join(tried)


def codes_for(row, cc):
    """후보의 DART 고유번호 목록 — 비어 있으면(같은 이름 여럿) 이름으로 모두 찾음"""
    if row["corp_code"]:
        return [row["corp_code"]]
    k = key(row["account"])
    return [c for c, n in zip(cc["corp_code"], cc["corp_name"]) if key(n) == k]


def main():
    cand = pd.read_csv(CAND, dtype=str).fillna("")
    dec = pd.read_csv(DECISIONS, dtype=str).fillna("") if DECISIONS.exists() else pd.DataFrame(columns=["account"])
    decmap = {key(r["account"]): r for r in dec.to_dict("records")}
    cc = corp_codes()
    print(f"1-3C 후보 {len(cand)}곳 — ① DART 최대주주 현황 → ② 감사보고서 원문 → ③ 판단 파일 순 · 판단 파일 {len(dec)}행")

    out = []
    for i, r in enumerate(cand.to_dict("records"), 1):
        codes = codes_for(r, cc)
        o_nm, o_rate, top3, per, st = ("", None, "", "", "DART 고유번호 없음")
        if codes and r["corp_code"]:
            o_nm, o_rate, top3, per, st = owners_api(r["corp_code"])
        au = dict(owner="", rate=None, report="", rcept_no="", rcept_dt="", status="", snippet="")
        if st != "ok" and codes:
            tries = [audit_owner(c) | {"corp": c} for c in codes]
            okk = [t for t in tries if t["status"] == "ok"]
            au = max(okk or tries, key=lambda t: t["rcept_dt"])
        d = decmap.get(key(r["account"]), {})
        if st == "ok":
            owner, rate, basis, grade = o_nm, f"{o_rate:.2f}", f"DART 최대주주 현황({per})", "1"
        elif au["status"] == "ok" or au["status"].startswith("지배회사만"):
            owner, rate = au["owner"], (f"{au['rate']:.2f}" if au["rate"] is not None else "")
            basis, grade = f"감사보고서 원문({au['report']}, 접수 {au['rcept_dt']}, {au['rcept_no']})", "1"
        else:
            owner, rate = d.get("owner", ""), d.get("owner_rate", "")
            basis, grade = d.get("source", ""), d.get("source_grade", "")
        gap = ""
        if grade == "1" and d.get("owner_rate") and rate and abs(to_f(d["owner_rate"]) - to_f(rate)) > RATE_GAP:
            gap = f"판단 파일 {d['owner_rate']}% / 1등급 {rate}%"
        decision = d.get("decision", "") or "1-3C 유지(판단 전)"
        layer = ("종속(명단 회사의 손자회사)" if decision.startswith("종속으로")
                 else "공공기관 종속" if decision.startswith("공공기관 종속")
                 else "비상장 비종속(독립·외국계)")
        out.append(dict(
            account=r["account"], part_nm=r["part_nm"], assets_jo=r["assets_jo"],
            corp_code=r["corp_code"] or (au.get("corp", "") if au.get("status") == "ok" else ""),
            decision=decision, layer=layer, owner_type=d.get("owner_type", ""),
            owner=owner, owner_rate=rate, owner_basis=basis, source_grade=grade,
            parent=d.get("parent", ""), pending=d.get("pending", ""),
            api_status=st, api_top3=top3,
            audit_status=au["status"], audit_report=au["report"], audit_rcept_no=au["rcept_no"],
            audit_snippet=au["snippet"], decision_source=d.get("source", ""), rate_gap=gap,
            confirmed=("1등급" if grade == "1" and rate else "1등급(지분율 표기 없음)" if grade == "1"
                       else f"{grade}등급" if grade in ("2", "3", "4", "5") and (rate or owner)
                       else "등급 외" if grade and (rate or owner) else "미확인")))
        if i % 10 == 0:
            print(f"  {i}/{len(cand)} …")

    a = pd.DataFrame(out)
    a["n"] = pd.to_numeric(a["assets_jo"], errors="coerce")
    a = a.sort_values("n", ascending=False).drop(columns="n")
    a.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")
    moved = a[a["layer"] != "비상장 비종속(독립·외국계)"]
    keep = a[a["layer"] == "비상장 비종속(독립·외국계)"]
    keep.to_csv(OUT_LIST, index=False, encoding="utf-8-sig")
    moved.to_csv(OUT_MOVED, index=False, encoding="utf-8-sig")

    pend = pd.DataFrame(acquirer_disclosures(cc), columns=["acquirer", "rcept_dt", "report_nm", "rcept_no"])
    pend.to_csv(OUT_PENDING, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n1-3C 확정 {len(keep)}곳 → {OUT_LIST.relative_to(ROOT)} / 이동 {len(moved)}곳 → {OUT_MOVED.relative_to(ROOT)}")
    print("\n[근거 등급]")
    print(a["confirmed"].value_counts().to_string())
    print("\n[전체 — 자산 순]")
    print(a[["account", "owner", "owner_rate", "source_grade", "owner_type", "layer"]].to_string(index=False))
    if (a["rate_gap"] != "").any():
        print("\n[지분율 차이 — 판단 파일 확인]")
        print(a[a["rate_gap"] != ""][["account", "rate_gap"]].to_string(index=False))
    chk = a[(a["audit_status"] != "") & (a["audit_status"] != "ok")]
    if len(chk):
        print("\n[감사보고서에서 표를 못 읽은 곳 — 문장·원문 확인]")
        for x in chk.to_dict("records"):
            print(f"  · {x['account']}: {x['audit_status']} | {x['audit_report']} {x['audit_rcept_no']}")
            if x["audit_snippet"]:
                print(f"      └ {x['audit_snippet'][:200]}")
    print(f"\n[매각 진행 — 상장 인수자 공시] → {OUT_PENDING.relative_to(ROOT)}")
    print(pend.to_string(index=False) if len(pend) else "  해당 공시 없음")


if __name__ == "__main__":
    main()
