"""금융2-4 ③-1 ② 감사보고서 실패분 채우기

- 입력: fin_s31_todo.csv (fin2_s31_freeze.py) · fin_s31_fisis.csv · fin_list.csv
- 처리 (2026-10-01 확정)
  1) 원문 오류 — 정정 공시([기재정정]·[첨부정정])의 원문 파일이 없음(DART 014)
     → 같은 회사의 다른 공시(원래 공시 등)를 사업보고서 → 감사보고서 → 연결감사보고서, 최신순으로 받아 같은 규칙으로 읽음
     → 성공·분자 채택이면 채움, 아니면 검토 목록
  2) 보험사(생명·손해)로 남은 곳 → FISIS 업종별 대출의 제조업 대출을 분자로 ("대출만" 표시, 확정 규칙)
  3) 숫자 검토 → fin_s31_review.csv (핵심 숫자 · 사유 · 후보 표 파일) — 원문 확인 후
     data/manual/fin_s31_audit_manual.csv 에 입력 (account, action=set|none, mfg_eok, basis, source, note)
  4) 표 없음 · 보고서 없음 · 표 못 읽음 → 채우지 않음 (합치기 단계에서 업권 가운데 값 추정)
- 출력: fin_s31_fill.csv · fin_s31_review.csv
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key, name2  # noqa: E402
from fin.fin2_lenders import UNIT_X, files_of  # noqa: E402
from fin.fin2_s31_audit import PREFIX, REPORT_FROM, REPORT_TO, candidates, pick_table, region  # noqa: E402
from fin.fin2_s31_freeze import classify, fnum  # noqa: E402

PROC = ROOT / "data" / "processed"
TODO = PROC / "fin_s31_todo.csv"
TODO2 = PROC / "fin_s31_todo2.csv"                  # fin2_s31_retry.py 결과
TODO3 = PROC / "fin_s31_todo3.csv"                  # fin2_s31_retry2.py 결과
TODO4 = PROC / "fin_s31_todo4.csv"                  # fin2_s31_retry3.py 결과
TODO5 = PROC / "fin_s31_todo5.csv"                  # fin2_s31_retry4.py 결과 — 가장 최신 할 일 목록을 씀
OUT = PROC / "fin_s31_fill.csv"
REVIEW = PROC / "fin_s31_review.csv"
DUMP = PROC / "s31_audit_tables"
KIND_ORDER = (("A", r"^사업보고서"), ("F", r"^감사보고서"), ("F", r"^연결감사보고서"))


def other_reports(codes, get_json, skip):
    """다른 공시 접수번호 목록 (보고서 종류 순, 각 종류 안에서 최신순) — skip은 실패한 접수번호"""
    out = []
    for code in codes:
        rows = []
        for ty in ("A", "F"):
            d = get_json("list", corp_code=code, bgn_de=REPORT_FROM, end_de=REPORT_TO, pblntf_ty=ty, page_count="100")
            rows += [(ty, str(r.get("rcept_no", "")), str(r.get("report_nm", "")).strip()) for r in d.get("list", []) or []]
        for ty, pat in KIND_ORDER:
            hit = sorted([(rno, nm) for t, rno, nm in rows if t == ty and re.search(pat, PREFIX.sub("", nm))], reverse=True)
            out += [(rno, nm) for rno, nm in hit if rno != skip and (rno, nm) not in out]
        if out:
            break
    return out


def analyze(files, grp, assets_jo):
    """원문 → (분자 억 원, 표 합계/총자산, 메모, 단위) 또는 (None, …, 사유)"""
    x, s, e, basis = region(files, grp == "금융지주")
    picked, info, why = pick_table(candidates(x, s, e))
    outside = False
    if not picked:
        allc = []
        for _, xx, _ in files:
            allc += [c for c in candidates(xx, 0, len(xx)) if not (xx is x and s <= c["pos"] < e)]
        picked, info, why2 = pick_table(allc)
        outside = bool(picked)
        why = why or why2
    if not picked:
        return None, None, why or "표 없음", ""
    ux = UNIT_X.get(picked["unit"])
    notes = []
    if outside:
        notes.append("표 위치: 주석 밖")
    if info["sum_ok"] is False:
        notes.append("검산①: 업종 줄 합 ≠ 합계")
    if not ux:
        notes.append("단위 못 찾음")
    if "(확인)" in info["basis"]:
        notes.append("열 판정 불확실")
    share = info["mfg"] / info["total"] * 100 if info["total"] else None
    if share is None or not (0 < share <= 100):
        notes.append("비중 범위 밖")
    mfg = info["mfg"] * ux / 1e8 if ux else None
    ratio = (info["total"] * ux / 1e8) / (assets_jo * 1e4) if (ux and assets_jo) else None
    return mfg, ratio, " · ".join(notes), f"{basis} · {info['basis']} · {info['mfg_rows']}"


def main():
    from dart_api import corp_codes, document_zip, get_json  # noqa: E402
    src = next(p_ for p_ in (TODO5, TODO4, TODO3, TODO2, TODO) if p_.exists())
    T = pd.read_csv(src, dtype=str).fillna("")
    print(f"입력 {src.relative_to(ROOT)} {len(T)}곳", flush=True)
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    info_of = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}
    F = pd.read_csv(PROC / "fin_s31_fisis.csv", dtype=str).fillna("")
    fis = {key(a): r for a, r in zip(F["account"], F.to_dict("records"))}
    cc = corp_codes()
    by_k, by_n2 = {}, {}
    for c_, n_ in zip(cc["corp_code"], cc["corp_name"]):
        by_k.setdefault(key(n_), []).append(str(c_))
        by_n2.setdefault(name2(n_), []).append(str(c_))

    fill, review = [], []
    for r in T.to_dict("records"):
        acc, grp, kind = r["account"], r["group"], r["fail_type"]
        li = info_of.get(key(acc), {})
        assets = fnum(li.get("assets_jo"))
        done = False
        if kind == "원문 오류":                                  # 1) 다른 공시로 다시
            codes = ([li["corp_code"]] if li.get("corp_code") else []) + by_k.get(key(acc), [])[:5] + by_n2.get(name2(acc), [])[:5]
            codes = list(dict.fromkeys(codes))
            try:
                reps = other_reports(codes, get_json, r["rcept_no"])
            except Exception as ex:  # noqa: BLE001
                reps, r["reason"] = [], f"목록 조회 오류 {type(ex).__name__}"
            for rno, nm in reps:
                try:
                    files = files_of(document_zip(rno))
                except Exception:  # noqa: BLE001 — 이 공시도 원문이 없으면 다음 공시
                    continue
                mfg, ratio, note, where = analyze(files, grp, assets)
                if mfg is None and not note.startswith(("검산", "단위", "열", "비중", "표 위치")):
                    r.update(fail_type="표 없음(다른 공시)", reason=f"{nm}: {note}")
                    break
                k2, why = classify(note, ratio, mfg)
                print(f"  원문 오류 → {acc}: {nm} — {k2} {why}", flush=True)
                if k2 in ("성공", "분자 채택"):
                    fill.append(dict(account=acc, group=grp, mfg_eok=round(mfg, 2), assets_jo=assets,
                                     share_assets=round(mfg / (assets * 1e4) * 100, 3) if assets else None,
                                     value_basis="감사보고서(다른 공시)", check=k2, check_note=why, source=f"{nm} {rno}",
                                     detail=where))
                    done = True
                else:
                    r.update(fail_type="숫자 검토", reason=why, mfg_eok=mfg, total_to_assets=ratio, rcept_no=rno, report_nm=nm)
                break
            if done:
                continue
            if r["fail_type"] == "원문 오류":
                r["reason"] = r.get("reason") or "다른 공시도 원문 없음"
        f = fis.get(key(acc), {})
        if grp in ("생명보험", "손해보험") and f.get("mfg_eok", "") != "":   # 2) 보험 → FISIS 제조업 대출
            m = float(f["mfg_eok"])
            fill.append(dict(account=acc, group=grp, mfg_eok=m, assets_jo=assets,
                             share_assets=round(m / (assets * 1e4) * 100, 3) if assets else None,
                             value_basis="FISIS 업종별 대출(대출만)", check="대체",
                             check_note=f"감사보고서 {r['fail_type']} — {r['reason']}"[:120],
                             source=f"FISIS {'SH122' if grp == '생명보험' else 'SI122'} 2025-12", detail=""))
            continue
        if r["fail_type"] in ("검토", "숫자 검토") and grp != "금융지주":   # 3) 검토 목록 (금융지주는 자회사 합산이라 제외)
            dump = DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}.txt"
            review.append(dict(account=acc, group=grp, assets_jo=assets, mfg_eok=r.get("mfg_eok"),
                               share_table=r.get("share_table"), total_to_assets=r.get("total_to_assets"),
                               reason=r["reason"], report_nm=r.get("report_nm", ""), rcept_no=r.get("rcept_no", ""),
                               dump=str(dump.relative_to(ROOT)) if dump.exists() else ""))
    FL, RV = pd.DataFrame(fill), pd.DataFrame(review)
    FL.to_csv(OUT, index=False, encoding="utf-8-sig")
    RV.to_csv(REVIEW, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 230)
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.max_colwidth", 60)
    print(f"\n채움 {len(FL)}곳 → {OUT.relative_to(ROOT)} · 검토 {len(RV)}곳 → {REVIEW.relative_to(ROOT)}")
    if len(FL):
        print("\n[채움] 값 출처별")
        print(FL["value_basis"].value_counts().to_string())
    rest = T[~T["account"].map(key).isin({key(a) for a in FL.get("account", [])} | {key(a) for a in RV.get("account", [])})]
    print("\n[추정 대상 — 합치기 단계에서 업권 가운데 값] 실패 유형별")
    col = "pattern" if "pattern" in rest.columns else "fail_type"
    print(rest[col].str.replace(r" — .*", "", regex=True).value_counts().to_string() if len(rest) else "  없음")
    if len(RV):
        print("\n[검토 목록] 자산 큰 순 — 원문 확인 후 수동 입력 (후보 표는 dump 파일)")
        RV["_a"] = pd.to_numeric(RV["assets_jo"], errors="coerce")
        print(RV.sort_values("_a", ascending=False)[["account", "group", "assets_jo", "mfg_eok", "total_to_assets", "reason"]]
              .to_string(index=False))


if __name__ == "__main__":
    main()
