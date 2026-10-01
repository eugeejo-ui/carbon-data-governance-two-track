"""금융2-4 ③-1 ① 감사보고서 추출 결과 중 성공분 고정 (한 번만 실행)

- 입력: data/processed/fin_s31_audit.csv (fin2_s31_audit.py 2판 결과) · fin_list.csv(총자산)
- 분모 (2026-10-01 확정): 278곳 모두 제조업 노출 ÷ 총자산 → 제조업 줄(분자)만 맞으면 성공
- 분류
  - 성공: 표를 읽었고 단위를 찾았으며 검토 사유가 없음
           (가계·개인 줄 없음 · 합계 줄 없음 · 합계 구조 적용 · FISIS 일치는 성공 — 분모를 총자산으로 바꿔 영향 없음)
  - 분자 채택: 표 합계 쪽 문제만 있는 경우 — 업종 줄 합 ≠ 합계, 표 합계/총자산 1.2~1.7배(상위 줄 중복으로 합계만 커짐)
               → 성공과 함께 고정하고 "확인 권장" 표시
  - 검토: 표 합계/총자산 1.7배 초과(칸 중복 — 분자도 커졌을 수 있음) · 0.05배 미만(일부만 담은 표) · 비중 범위 밖 ·
          FISIS 차이 · 주석 밖 표 · 단위 못 찾음 · 열 판정 불확실
- 출력: fin_s31_audit_fixed.csv (성공·분자 채택) · fin_s31_todo.csv (나머지 + 실패 유형)
- 고정 파일이 이미 있으면 덮어쓰지 않음 — 다시 만들려면 --force
"""
from pathlib import Path
import math
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
AUDIT = PROC / "fin_s31_audit.csv"
FIXED = PROC / "fin_s31_audit_fixed.csv"
TODO = PROC / "fin_s31_todo.csv"
REVIEW_NOTE = ("비중 범위 밖", "검산③: FISIS 차이", "표 위치", "단위 못 찾음", "열 판정")
RATIO_HI, RATIO_OK, RATIO_LO = 1.7, 1.2, 0.05


def fnum(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def classify(note, ratio, mfg_eok):
    """("성공"|"분자 채택"|"검토", 사유)"""
    notes = [n.strip() for n in str(note or "").split(" · ") if n.strip()]
    review = [n for n in notes if n.startswith(REVIEW_NOTE)]
    if mfg_eok is None:
        review.append("제조업 금액 없음(단위 없음)")
    if ratio is not None and (ratio > RATIO_HI or ratio < RATIO_LO):
        review.append(f"표 합계/총자산 {ratio:.2f}")
    if review:
        return "검토", " · ".join(dict.fromkeys(review))
    caution = [n for n in notes if n.startswith("검산①")]
    if ratio is not None and ratio > RATIO_OK:
        caution.append(f"표 합계/총자산 {ratio:.2f}")
    return ("분자 채택", " · ".join(caution)) if caution else ("성공", "")


def main(argv):
    if FIXED.exists() and "--force" not in argv:
        print(f"{FIXED.relative_to(ROOT)} 이미 있음 — 고정본을 지키기 위해 멈춤 (다시 만들려면 --force)")
        return
    A = pd.read_csv(AUDIT, dtype=str).fillna("")
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    assets = {key(a): fnum(x) for a, x in zip(L["account"], L["assets_jo"])}
    fixed, todo = [], []
    for r in A.to_dict("records"):
        acc, st = r["account"], r["status"]
        mfg = fnum(r.get("mfg_eok"))
        if st in ("ok", "확인"):
            kind, why = classify(r.get("note", ""), fnum(r.get("total_to_assets")), mfg)
        else:
            kind, why = {"원문 오류": "원문 오류", "보고서 없음": "보고서 없음", "표 없음": "표 없음",
                         "표 못 읽음": "표 못 읽음"}.get(st, st or "기타"), r.get("fail_reason", "") or r.get("note", "")
        if kind in ("성공", "분자 채택"):
            a = assets.get(key(acc))
            fixed.append(dict(account=acc, group=r["group"], layer=r["layer"], sector=r["sector"], mfg_eok=mfg,
                              assets_jo=a, share_assets=round(mfg / (a * 1e4) * 100, 3) if a else None,
                              share_table=fnum(r.get("share_total")), check=kind, check_note=why,
                              value_basis="감사보고서", col_basis=r.get("col_basis", ""), cols=r.get("cols", ""),
                              mfg_rows=r.get("mfg_rows", ""), unit=r.get("unit", ""), doc_basis=r.get("doc_basis", ""),
                              rcept_no=r.get("rcept_no", ""), report_nm=r.get("report_nm", ""), audit_note=r.get("note", "")))
        else:
            todo.append(dict(account=acc, group=r["group"], layer=r["layer"], sector=r["sector"], fail_type=kind,
                             reason=why, mfg_eok=mfg, share_table=fnum(r.get("share_total")),
                             total_to_assets=fnum(r.get("total_to_assets")), rcept_no=r.get("rcept_no", ""),
                             report_nm=r.get("report_nm", ""), code_src=r.get("code_src", ""),
                             found_kinds=r.get("found_kinds", ""), diag=r.get("diag", "")))
    F, T = pd.DataFrame(fixed), pd.DataFrame(todo)
    F.to_csv(FIXED, index=False, encoding="utf-8-sig")
    T.to_csv(TODO, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print(f"고정 {len(F)}곳 → {FIXED.relative_to(ROOT)} · 할 일 {len(T)}곳 → {TODO.relative_to(ROOT)}\n")
    print("[고정] 집단 × 분류")
    if len(F):
        print(F.pivot_table(index="group", columns="check", values="account", aggfunc="count", fill_value=0).to_string())
    print("\n[할 일] 집단 × 실패 유형")
    if len(T):
        print(T.pivot_table(index="group", columns="fail_type", values="account", aggfunc="count", fill_value=0).to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
