"""금융-1 한 번에 실행 — 단계를 순서대로 돌리고 확인할 것만 요약함

사용법
  python src/fin/run_fin1.py           # 금융1-2 → 1-2b → 1-3A → 1-3C(총자산·대조 → 소유 구조) (보통 이것만)
  python src/fin/run_fin1.py --all     # 금융1-1 → 1-1b부터 전부 (기준표를 고쳤을 때)
  python src/fin/run_fin1.py --fisis   # 1-3C 1단계(FISIS 목록)도 다시 받을 때 (--all과 함께 써도 됨)

- 각 단계의 전체 출력은 logs/fin1/<단계>.log에 저장하고, 화면에는 성공·실패와 요약만 보여 줌
- 한 단계라도 실패하면 거기서 멈추고 로그 끝부분을 보여 줌
- 인증키는 각 단계가 .env에서 읽음 (이 파일은 키를 다루지 않음)
"""
from pathlib import Path
import os
import subprocess
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "fin"
PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
LOGS = ROOT / "logs" / "fin1"

BASE = ["fin1_subsidiary", "fin1_nonfin_sub", "fin1_unlisted", "fin1_indep", "fin1_owner"]
LABEL = {"fin1_list": "금융1-1 상장 금융사 후보", "fin1_sector": "금융1-1b 코스피 확정",
         "fin1_subsidiary": "금융1-2 금융 모회사의 종속", "fin1_nonfin_sub": "금융1-2b 명단 밖 모회사의 종속",
         "fin1_unlisted": "금융1-3A 대기업집단 비상장", "fin1_fisis_catalog": "금융1-3C 1단계 FISIS 목록",
         "fin1_indep": "금융1-3C 2단계 총자산·대조", "fin1_owner": "금융1-3C 3단계 소유 구조"}
FIN_WORDS = "금융|증권|캐피탈|보험|은행|지주|홀딩스|투자|신탁|카드|저축"


def steps(argv):
    s = (["fin1_list", "fin1_sector"] if "--all" in argv else []) + BASE
    if "--fisis" in argv:
        s.insert(s.index("fin1_indep"), "fin1_fisis_catalog")
    return s


def run(step):
    LOGS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    p = subprocess.run([sys.executable, str(SRC / f"{step}.py")], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = LOGS / f"{step}.log"
    log.write_text(p.stdout + ("\n[stderr]\n" + p.stderr if p.stderr.strip() else ""), encoding="utf-8")
    sec = time.time() - t0
    if p.returncode != 0:
        print(f"  ✗ {LABEL[step]} — 실패 ({sec:.0f}초). 로그: {log.relative_to(ROOT)}")
        tail = (p.stdout + "\n" + p.stderr).strip().splitlines()[-25:]
        print("\n".join("    " + x for x in tail))
        sys.exit(1)
    print(f"  ✓ {LABEL[step]} ({sec:.0f}초) → {log.relative_to(ROOT)}")


def read(path):
    return pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()


def summary():
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.max_colwidth", 60)
    L, S, N = read(PROC / "fin_listed.csv"), read(PROC / "fin_subsidiaries.csv"), read(PROC / "fin_nonfin_subs.csv")
    A, B, C = read(PROC / "fin_unlisted_group.csv"), read(MANUAL / "fin_public_institutions.csv"), \
        read(PROC / "fin_indep_candidates.csv")
    OL, OM = read(PROC / "fin_indep_list.csv"), read(PROC / "fin_indep_moved.csv")
    sub_m = OM[OM["layer"].str.startswith("종속")] if len(OM) else OM
    pub_m = OM[OM["layer"] == "공공기관 종속"] if len(OM) else OM
    rows = [("코스피 상장 (1-1)", len(L)), ("금융 모회사의 종속 (1-2)", len(S)),
            ("  + 손자회사 (1-3C에서 이동)", len(sub_m)),
            ("명단 밖 코스피 모회사의 종속 (1-2b)", len(N)), ("대기업집단 비상장 (1-3A)", len(A)),
            ("공공금융기관 (1-3B)", len(B)), ("  + 공공기관 종속 (1-3C에서 이동)", len(pub_m)),
            ("독립·외국계 (1-3C)", len(OL) if len(OL) else len(C))]
    print("\n════════ 요약 ════════")
    print("[1] 층별 곳 수")
    for k, v in rows:
        print(f"    {k:28s} {v:>4}")
    print(f"    {'합계':28s} {sum(v for _, v in rows):>4}")

    if len(S):
        man = S[S["period"].str.startswith("원문 수동 입력")] if "period" in S else S.iloc[0:0]
        print(f"\n[2] 1-2 원문 수동 입력으로 들어온 곳 {len(man)}: " + ", ".join(man["account"]))
        print(f"    이름으로 업권을 정한 곳 — 1-2 {int((S['sector_by'] == '이름').sum())} · "
              f"1-2b {int((N['sector_by'] == '이름').sum()) if len(N) else 0}")

    print("\n[3] 신용정보사 처리")
    for nm, df in (("1-2 명단", S), ("1-2b 명단", N)):
        hit = df[df["account"].str.contains("신용정보")] if len(df) else df
        for r in hit.to_dict("records"):
            print(f"    {nm}: {r['account']} — 업권 {r['sector']} ({r['sector_by']})")
    for nm, f in (("1-2 제외", "fin_sub_excluded.csv"), ("1-2b 제외", "fin_nonfin_excluded.csv")):
        e = read(PROC / f)
        hit = e[e["account"].str.contains("신용정보")] if len(e) else e
        for r in hit.to_dict("records"):
            print(f"    {nm}: {r['account']} — {r['reason'].split(' — ')[0]} ({r['parent']})")

    print("\n[4] 출자현황을 못 받은 지배회사")
    for nm, f in (("1-2", "fin_sub_excluded.csv"), ("1-2b", "fin_nonfin_excluded.csv")):
        e = read(PROC / f)
        nd = e[e["reason"].str.startswith("출자현황")] if len(e) else e
        fin = nd[nd["parent"].str.contains(FIN_WORDS)] if len(nd) else nd
        print(f"    {nm}: {len(nd)}곳 — 그중 이름에 금융 단어가 든 곳 {len(fin)}")
        for p in fin["parent"]:
            print(f"      · {p}")

    big = read(PROC / "fisis" / "fisis_big.csv")
    if len(big):
        print(f"\n[5] 1-3C 판정 (FISIS 자산 2조 이상 {len(big)}곳)")
        print("    " + " · ".join(f"{k} {v}" for k, v in big["where"].str.split(" — ").str[0].value_counts().items()))
        rule = big[big["where"].str.startswith(("제외", "이미 명단 — 자산"))]
        for r in rule.to_dict("records"):
            print(f"      · {r['finance_nm']} {float(r['assets_jo']):.2f}조 — {r['where'].split(' — ', 1)[1]}")
    if len(C):
        print(f"\n[6] 1-3C 후보 {len(C)}곳 (자산 조)")
        for part, g in C.groupby("part_nm", sort=False):
            print(f"    {part}: " + " · ".join(f"{a} {float(v):.2f}" for a, v in zip(g["account"], g["assets_jo"])))
        chk = C[(C["similar_in_list"] != "") | (C["corp_code"] == "")]
        if len(chk):
            print("    확인 필요 — " + " · ".join(
                f"{a}({'DART 고유번호 없음' if not c else '비슷한 이름: ' + s})"
                for a, c, s in zip(chk["account"], chk["corp_code"], chk["similar_in_list"])))


def owner_summary():
    a = read(PROC / "fin_indep_owners.csv")
    if not len(a):
        return
    print(f"\n[7] 1-3C 소유 구조 ({len(a)}곳) — 근거: " + " · ".join(
        f"{k} {v}" for k, v in a["confirmed"].value_counts().items()))
    mv = a[a["layer"] != "비상장 비종속(독립·외국계)"]
    for r in mv.to_dict("records"):
        print(f"    → {r['layer']}: {r['account']} ({r['owner']} {r['owner_rate']}%, 등급 {r['source_grade']})")
    keep = a[(a["layer"] == "비상장 비종속(독립·외국계)") & (a["confirmed"] != "미확인")]
    for t, g in keep.groupby(keep["owner_type"].replace("", "유형 미정"), sort=False):
        print(f"    {t}: " + " · ".join(f"{x}({o} {rt}%, {gr})" for x, o, rt, gr in
                                       zip(g["account"], g["owner"], g["owner_rate"], g["source_grade"])))
    pend = a[a["pending"] != ""]
    if len(pend):
        print("    변동 예정:")
        for x, p in zip(pend["account"], pend["pending"]):
            print(f"      · {x}: {p}")
    gap = a[a["rate_gap"] != ""]
    if len(gap):
        print("    지분율 차이 — " + " · ".join(f"{x}: {g}" for x, g in zip(gap["account"], gap["rate_gap"])))
    low = a[a["source_grade"] != "1"]
    if len(low):
        print("    1등급으로 확인 못 한 곳:")
        for r in low.to_dict("records"):
            why = r["audit_status"] or r["api_status"]
            print(f"      · {r['account']} — {why} | {str(r['audit_snippet'])[:120]}")
    pd_ = read(PROC / "fin_indep_pending_disclosures.csv")
    if len(pd_):
        print("    상장 인수자 공시 (DART): " + " · ".join(
            f"{a_} {d_} {n_}" for a_, d_, n_ in zip(pd_["acquirer"], pd_["rcept_dt"], pd_["report_nm"])))


def main():
    todo = steps(sys.argv[1:])
    print(f"금융-1 실행 — {len(todo)}단계")
    for s in todo:
        run(s)
    summary()
    owner_summary()


if __name__ == "__main__":
    main()
