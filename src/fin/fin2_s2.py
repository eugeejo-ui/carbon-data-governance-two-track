"""금융2-3 ② 현재 빈칸 — 금융배출량 공시 수준 점수 (278곳)

- 입력: data/manual/fin_s2_evidence.csv (조사 결과) · data/processed/fin_groups.csv (account → report_unit)
- 점수 (계획서 7-4, 운영 규칙 A~D + A 연장)
  - 2점: 미공시 — 공시 안 함이 확인된 곳(disclosed=N) + 근거를 찾지 못한 곳(U·목록에 없음, 7-5 "없음이 답")
  - 0점: 공시하고 커버리지(금액 기준) 50% 이상 "이고" 품질 3.5 미만이 둘 다 확인된 곳
  - 1점: 공시는 하는데 위 0점 조건이 확인되지 않은 곳 (둘 중 하나라도 공개 안 됨 → 1점)
- 근거 강도 (2026-10-01 확정): 확인(회사 이름이 명시된 수치·산정 결과·공식 홈페이지) · 약함(측정 시스템·감축 목표 공개,
  여러 회사 합계에만 포함, 그룹 보고서 범위) = 공시로 봄 / 없음(PCAF 가입만, "관리에 초점" 같은 일반 서술) = 2점
- 그룹 보고서 범위 보정 (2026-10-01 확정): 상장 자회사라 따로 보고 단위가 된 곳도 지배회사 그룹 보고서 범위에
  들면 그룹 값 — 증거 줄을 그 자회사 이름으로 추가해 적용 (①은 본인 상장 여부 그대로)
- 적용: 근거 줄은 명단 이름(account·aliases)으로 278곳에 이어 붙인 뒤, 그 회사의 보고 단위 값을 단위 전체에 적용
  - 대표 회사 줄이 있으면 그 값, 없으면 단위 안 자회사 줄 값(표시)
- 출력: data/processed/fin_s2.csv
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

EV = ROOT / "data" / "manual" / "fin_s2_evidence.csv"
GROUPS = ROOT / "data" / "processed" / "fin_groups.csv"
OUT = ROOT / "data" / "processed" / "fin_s2.csv"
COV_CUT, DQ_CUT = 50.0, 3.5


def num(x):
    try:
        return float(str(x).replace("%", "").strip())
    except ValueError:
        return None


def score(r):
    if r["disclosed"] != "Y":
        return 2
    cov, dq = num(r["coverage_pct"]), num(r["dq_score"])
    return 0 if (cov is not None and dq is not None and cov >= COV_CUT and dq < DQ_CUT) else 1


def main():
    E = pd.read_csv(EV, dtype=str).fillna("")
    G = pd.read_csv(GROUPS, dtype=str).fillna("")
    E["s2"] = E.apply(score, axis=1)
    by_key = {key(a): a for a in G["account"]}
    unit_of = dict(zip(G["account"], G["report_unit"]))
    hit, miss = [], []
    for r in E.to_dict("records"):
        names = [r["account"]] + [a for a in r["aliases"].split("|") if a]
        acc = next((by_key[key(n)] for n in names if key(n) in by_key), None)
        (hit if acc else miss).append({**r, "matched": acc or ""})
    H = pd.DataFrame(hit)
    H["unit"] = H["matched"].map(unit_of)
    rows, notes = {}, []
    for unit, g in H.groupby("unit"):
        own = g[g["matched"] == unit]
        pick = own.iloc[0] if len(own) else g.sort_values("s2").iloc[0]
        if not len(own):
            notes.append(f"  {unit}: 대표 회사 줄 없음 → 자회사 {pick['matched']} 값 사용")
        if len(g) > 1 and g["s2"].nunique() > 1:
            notes.append(f"  {unit}: 단위 안 근거 점수가 다름 {dict(zip(g['matched'], g['s2']))} → {pick['matched']} 값")
        rows[unit] = pick
    out = []
    for r in G.to_dict("records"):
        p = rows.get(r["report_unit"])
        if p is None:
            out.append(dict(account=r["account"], report_unit=r["report_unit"], s2=2, s2_basis="근거 없음(미공시로 봄)",
                            disclosed="", coverage_pct="", dq_score="", data_year="", evidence_from="", source="", recheck=""))
        else:
            basis = {"N": "미공시 확인", "U": "근거 없음(미공시로 봄)"}.get(p["disclosed"], f"공시({p['strength']})")
            out.append(dict(account=r["account"], report_unit=r["report_unit"], s2=int(p["s2"]), s2_basis=basis,
                            disclosed=p["disclosed"], coverage_pct=p["coverage_pct"], dq_score=p["dq_score"],
                            data_year=p["data_year"], evidence_from=p["matched"], source=p["source"], recheck=p["recheck"]))
    O = pd.DataFrame(out)
    O.to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 40)
    print(f"근거 {len(E)}줄 → 명단에 이어짐 {len(H)} · 못 이음 {len(miss)}")
    for m in miss:
        print(f"  [못 이음] {m['account']} (aliases: {m['aliases']}) — 명단 이름 확인 필요")
    if notes:
        print("[단위 처리 메모]")
        print("\n".join(notes))
    print(f"\n→ {OUT.relative_to(ROOT)}  ({len(O)}곳)")
    print("\n[1] 점수 분포 (278곳)")
    print(O["s2"].value_counts().sort_index(ascending=False).rename("곳 수").to_string())
    print("\n[2] 점수 근거별")
    print(O.groupby(["s2", "s2_basis"]).size().rename("곳 수").to_string())
    print("\n[3] 근거가 붙은 보고 단위 — 단위별 회사 수")
    U = O[O["evidence_from"] != ""].groupby(["report_unit", "s2", "s2_basis", "coverage_pct", "dq_score", "data_year"]).size()
    print(U.rename("회사 수").reset_index().to_string(index=False))
    print(f"\n[4] 보고 단위 기준 분포 ({O['report_unit'].nunique()}개 단위)")
    print(O.drop_duplicates("report_unit")["s2"].value_counts().sort_index(ascending=False).rename("단위 수").to_string())
    print("\n[5] 원문 대조 1순위 (recheck=1): " + ", ".join(E.loc[E["recheck"] == "1", "account"]))


if __name__ == "__main__":
    main()
