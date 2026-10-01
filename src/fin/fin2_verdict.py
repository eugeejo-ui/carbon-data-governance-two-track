"""금융2-7 판정 — 선정 표시 · 참고 칸 · 선정 요약 · H3 숫자

- 입력 (data/processed/): fin_scores.csv (fin2_scores.py) · fin_s2.csv (fin2_s2.py) · fin_s5.csv (fin2_s5.py)
         (data/manual/): fin_s2_evidence.csv — 그룹 보고서 범위 보정 줄 찾기용
- 선정 기준 (2026-10-01 확정, B안): 합계 5점 이상 — 점수 구간 경계에서 끊음(제조 8점 이상과 같은 원칙)
- 참고 칸
  - ref_s2      ② 근거 종류: 공시 근거 못 찾음 / 미공시 확인 / 그룹 보고서 범위 적용(보정) / 근거 약함 / 그룹 값
  - ref_recheck 원문 대조 순위: 1순위(근거 약함·간접 근거) / 2순위(공시 근거 못 찾음)
  - ref_s5      ⑤ 근거 종류: 직접 계약 / 그룹 IT 자회사 계약 / 같은 단위 다른 계정 / 공개 자료로 확인 안 됨
  - ref_tie     동점 처리 뒤에도 이름순으로만 갈린 경우
- 출력: data/processed/fin2_verdict.csv (계정별) · data/processed/fin2_selection_notes.csv (항목·값·설명)
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
EV2 = ROOT / "data" / "manual" / "fin_s2_evidence.csv"
OUT = PROC / "fin2_verdict.csv"
NOTES = PROC / "fin2_selection_notes.csv"
CUT = 5                    # 선정 기준: 합계 5점 이상 (B안)
UNITS_DOC = 153            # 문서에 적힌 보고 단위 수 — 실제 값과 대조
TIE = ["total", "s2", "s3", "s33", "n33", "n32"]


def by_key(df, cols):
    d = df.copy()
    d["k"] = d["account"].map(key)
    return d.drop_duplicates("k").set_index("k")[cols]


def ref_s2(r, fix_keys):
    b, src = r["s2_basis"], str(r.get("s2_from", "") or "")
    if b == "근거 없음(미공시로 봄)":
        return "② 공시 근거 못 찾음 — 원문 대조에서 공시가 확인되면 ② 1점·합계 1점 하락"
    if b == "미공시 확인":
        return "② 미공시 확인(근거 있음)"
    if src and key(src) in fix_keys:
        return "② 그룹 보고서 범위 적용(보정 규칙) — 범위 근거가 간접적"
    own = key(src) == key(r["account"]) if src else True
    head = "② 공시 근거 약함" if "약함" in b else "② 공시 확인"
    return head if own else f"{head} — 그룹 값(근거: {src})"


def ref_recheck(r):
    if str(r.get("s2_recheck", "")) == "1":
        return "원문 대조 1순위"
    if r["s2_basis"] == "근거 없음(미공시로 봄)":
        return "원문 대조 2순위(공시 근거 못 찾음)"
    return ""


def ref_s5(r):
    b = r["s5_basis"]
    when = " ".join(x for x in (str(r.get("s5_date", "") or ""), str(r.get("s5_form", "") or "")) if x and x != "nan")
    if b == "직접":
        return f"⑤ 직접 계약({when})"
    if b == "그룹 IT 자회사 계약":
        return f"⑤ 그룹 IT 자회사 계약을 대표 회사 계약으로 봄({when})"
    if b == "같은 보고 단위 다른 계정":
        return f"⑤ 같은 단위 {r.get('s5_from', '')} 근거(최대 1점)"
    return "⑤ 공개 자료로 확인 안 됨"


def main():
    D = pd.read_csv(PROC / "fin_scores.csv", dtype={"account": str})
    S2 = pd.read_csv(PROC / "fin_s2.csv", dtype=str).fillna("")
    S5 = pd.read_csv(PROC / "fin_s5.csv", dtype=str).fillna("")
    E2 = pd.read_csv(EV2, dtype=str).fillna("")
    fix_keys = set()
    for r in E2[E2["report"].str.contains("그룹 값")].to_dict("records"):
        fix_keys |= {key(n) for n in [r["account"]] + [a for a in r["aliases"].split("|") if a]}
    D["k"] = D["account"].map(key)
    s2 = by_key(S2, ["evidence_from", "recheck"]).rename(columns={"evidence_from": "s2_from", "recheck": "s2_recheck"})
    s5 = by_key(S5, ["evidence_from", "event_date", "form"]).rename(
        columns={"evidence_from": "s5_from", "event_date": "s5_date", "form": "s5_form"})
    D = D.join(s2, on="k").join(s5, on="k").fillna({"s2_basis": "", "s5_basis": ""})

    D["selected"] = (D["total"] >= CUT).map({True: "Y", False: ""})
    D["unit_selected_n"] = D.groupby("report_unit")["selected"].transform(lambda s: int((s == "Y").sum()))
    D["ref_s2"] = D.apply(ref_s2, axis=1, fix_keys=fix_keys)
    D["ref_recheck"] = D.apply(ref_recheck, axis=1)
    D["ref_s5"] = D.apply(ref_s5, axis=1)
    size = D.groupby(TIE)["account"].transform("size")
    D["ref_tie"] = [f"동점 처리 뒤 이름순(같은 묶음 {n}곳)" if n > 1 else "" for n in size]
    cols = ["rank", "account", "group", "layer", "report_unit", "total", "s1", "s2", "s3", "s5",
            "s31", "s32", "s33", "n33", "n32", "selected", "unit_selected_n",
            "ref_s2", "ref_recheck", "ref_s5", "ref_tie"]
    D = D.sort_values("rank")
    D[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    # ── 선정 요약 ─────────────────────────────────────────────
    S = D[D["selected"] == "Y"]
    n, N = len(S), len(D)
    U = D.groupby("report_unit").agg(best=("total", "max"), s2=("s2", "max"))
    su = S["report_unit"].nunique()
    dist = " · ".join(f"{t}점 {c}" for t, c in D["total"].value_counts().sort_index(ascending=False).items())
    comp = " · ".join(f"{g} {c}" for g, c in S["group"].value_counts().items())
    units = " · ".join(f"{u}({c})" for u, c in S["report_unit"].value_counts().items())
    none = S["ref_s2"].str.startswith("② 공시 근거 못 찾음")
    fixed = S["ref_s2"].str.startswith("② 그룹 보고서 범위")
    tie = D.groupby(TIE).size()
    big = tie.idxmax()
    rows = [
        ("선정 기준", f"합계 {CUT}점 이상", "점수 구간 경계에서 끊음 — 같은 점수 안에서 정렬 순서로 갈리지 않게(제조 8점 이상과 같은 원칙)"),
        ("선정 수(계정)", f"{n}곳 ({n / N:.1%})", f"전체 {N}곳 중"),
        ("선정 수(보고 단위)", f"{su}개 ({su / len(U):.1%})", f"전체 {len(U)}개 중 — 금융은 그룹으로 묶여 영업 접점이 지주·그룹 전산 자회사로 모임"),
        ("합계 분포", dist, "뚜렷한 끊김 없음(한 칸마다 약 두 배)"),
        ("업권 구성(선정)", comp, ""),
        ("보고 단위 목록(선정)", units, "괄호는 단위 안 선정 계정 수"),
        ("② 공시 근거 못 찾음(선정)", f"{int(none.sum())}곳", "원문 대조에서 공시가 확인되면 합계 1점 하락 — " + " · ".join(S.loc[none, "account"])),
        ("② 미공시 확인(선정)", f"{int((S['ref_s2'] == '② 미공시 확인(근거 있음)').sum())}곳",
         " · ".join(S.loc[S["ref_s2"] == "② 미공시 확인(근거 있음)", "account"])),
        ("② 그룹 보고서 범위 보정(선정)", f"{int(fixed.sum())}곳",
         "상장 자회사라도 지배회사 그룹 보고서 범위에 들면 ②는 그룹 값 — " + " · ".join(S.loc[fixed, "account"])),
        ("원문 대조 1순위(선정)", f"{int((S['ref_recheck'] == '원문 대조 1순위').sum())}곳", ""),
        ("⑤ 분포(선정)", " · ".join(f"{s}점 {c}" for s, c in S["s5"].value_counts().sort_index(ascending=False).items()),
         "0점은 관계 없음이 아니라 공개 자료로 확인 안 됨"),
        ("동점 묶음", f"{int((tie > 1).sum())}개, 최대 {int(tie.max())}곳(합계 {big[0]}점)",
         "선정 기준이 합계 점수 구간이라 한 묶음(같은 합계)이 선정·비선정으로 갈리지 않음 — 선정에 영향 없음"),
        ("보고 단위 수", f"실제 {len(U)}개", f"문서 기록 {UNITS_DOC}개와 {UNITS_DOC - len(U)}개 차이 — 문서 숫자 정정"),
        ("H3 ② 1점 이상", f"계정 {int((D['s2'] >= 1).sum())}/{N} = {(D['s2'] >= 1).mean():.1%} · "
         f"보고 단위 {int((U['s2'] >= 1).sum())}/{len(U)} = {(U['s2'] >= 1).mean():.1%} · "
         f"선정 {int((S['s2'] >= 1).sum())}/{n} = {(S['s2'] >= 1).mean():.1%}", "H3 조건 '② 1점 이상 과반'"),
    ]
    pd.DataFrame(rows, columns=["item", "value", "note"]).to_csv(NOTES, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 60)
    print(f"→ {OUT.relative_to(ROOT)} ({N}곳) · {NOTES.relative_to(ROOT)}")
    print("\n[1] 선정 요약")
    for item, value, note in rows:
        print(f"  {item}: {value}" + (f"  — {note}" if note else ""))
    print(f"\n[2] 선정 {n}곳")
    S = S.assign(ref=S["ref_s2"].str.slice(0, 26))
    print(S[["rank", "account", "group", "report_unit", "total", "s1", "s2", "s3", "s5", "unit_selected_n", "ref"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
