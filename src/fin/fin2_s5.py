"""금융2-5 ⑤ IBM 관계 — 278곳 점수 (계획서 7-4: 최근 5년 내 공개 계약 2점 / 그 이전 사례만 1점 / 확인 안 됨 0점)

- 입력: data/manual/fin_s5_evidence.csv (사실만 기록: 계약 주체·시점·형태·분야·출처) · data/processed/fin_groups.csv
- 규칙 (바뀌면 아래 설정값만 고침)
  A. 업무협약(MOU)·공동연구는 시점과 관계없이 최대 1점
  B. 파트너 경유 도입도 도입 사례로 인정 (증거 줄에 그대로 기록)
  C. 계약 주체만 해당 점수, 같은 보고 단위의 나머지 계정은 최대 1점. 명단 밖 그룹 IT 자회사 계약은 대표 회사 계약으로 봄
  D. 계약 시점 기준 — "계속 사용 중"만으로는 5년 내 계약이 아님
- 출력: data/processed/fin_s5.csv
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

EV = ROOT / "data" / "manual" / "fin_s5_evidence.csv"
GROUPS = ROOT / "data" / "processed" / "fin_groups.csv"
OUT = ROOT / "data" / "processed" / "fin_s5.csv"
CUTOFF = "2021-10"          # 5년 기준 시점 (계획서 금융2-5)
MOU_CAP = 1                 # 결정 A
SAME_UNIT_CAP = 1           # 결정 C


def row_score(r):
    if r["form"] == "MOU":
        return MOU_CAP
    d = re.match(r"(\d{4})(?:-(\d{2}))?", r["event_date"])
    if not d:
        return 1
    ym = f"{d.group(1)}-{d.group(2) or '01'}"
    return 2 if ym >= CUTOFF else 1


def main():
    E = pd.read_csv(EV, dtype=str).fillna("")
    G = pd.read_csv(GROUPS, dtype=str).fillna("")
    E["score"] = E.apply(row_score, axis=1)
    by_key = {key(a): a for a in G["account"]}
    unit_of = dict(zip(G["account"], G["report_unit"]))
    E["matched"] = [next((by_key[key(n)] for n in [a] + [x for x in al.split("|") if x] if key(n) in by_key), "")
                    for a, al in zip(E["account"], E["aliases"])]
    miss = E[E["matched"] == ""]
    H = E[E["matched"] != ""].copy()
    H["unit"] = H["matched"].map(unit_of)
    own = H.sort_values(["score", "event_date"], ascending=False).drop_duplicates("matched").set_index("matched")
    unit_best = H.sort_values(["score", "event_date"], ascending=False).drop_duplicates("unit").set_index("unit")
    out = []
    for r in G.to_dict("records"):
        a, u = r["account"], r["report_unit"]
        own_s = int(own.loc[a, "score"]) if a in own.index else -1
        unit_s = min(int(unit_best.loc[u, "score"]), SAME_UNIT_CAP) if u in unit_best.index else -1
        if own_s >= 0 and own_s >= unit_s:
            p = own.loc[a]
            out.append(dict(account=a, report_unit=u, s5=own_s, s5_basis="직접" if p["party"] == "직접" else "그룹 IT 자회사 계약",
                            event_date=p["event_date"], form=p["form"], field=p["field"], evidence_from=a, summary=p["summary"]))
        elif unit_s >= 0:
            p = unit_best.loc[u]
            out.append(dict(account=a, report_unit=u, s5=min(int(p["score"]), SAME_UNIT_CAP), s5_basis="같은 보고 단위 다른 계정",
                            event_date=p["event_date"], form=p["form"], field=p["field"], evidence_from=p["matched"], summary=p["summary"]))
        else:
            out.append(dict(account=a, report_unit=u, s5=0, s5_basis="확인 안 됨", event_date="", form="", field="",
                            evidence_from="", summary=""))
    O = pd.DataFrame(out)
    O.to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 46)
    print(f"근거 {len(E)}줄 → 명단에 이어짐 {len(H)} · 못 이음 {len(miss)}")
    for m in miss.to_dict("records"):
        print(f"  [못 이음] {m['account']} (aliases: {m['aliases']}) — 명단 이름 확인 필요")
    print(f"\n→ {OUT.relative_to(ROOT)}  ({len(O)}곳)")
    print("\n[1] 점수 분포")
    print(O["s5"].value_counts().sort_index(ascending=False).rename("곳 수").to_string())
    print("\n[2] 점수 근거별")
    print(O.groupby(["s5", "s5_basis"]).size().rename("곳 수").to_string())
    print("\n[3] 직접 근거가 있는 계정")
    D = O[O["s5_basis"].isin(["직접", "그룹 IT 자회사 계약"])].sort_values(["s5", "event_date"], ascending=False)
    print(D[["account", "s5", "event_date", "form", "field", "summary"]].to_string(index=False))
    print("\n[4] 같은 단위로 점수가 붙은 보고 단위 — 회사 수")
    print(O[O["s5_basis"] == "같은 보고 단위 다른 계정"].groupby(["report_unit", "s5"]).size().rename("회사 수").to_string())
    print(f"\n[5] 보고 단위 기준 최고점 분포 ({O['report_unit'].nunique()}개 단위)")
    print(O.groupby("report_unit")["s5"].max().value_counts().sort_index(ascending=False).rename("단위 수").to_string())


if __name__ == "__main__":
    main()
