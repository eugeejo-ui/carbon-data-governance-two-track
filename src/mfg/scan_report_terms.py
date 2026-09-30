"""⑤ 근거·품목 확인용 원문 용어 스캔 (94곳 소급 적용)

- 탄소 키워드: 계정이 탄소 시스템을 언급하는지 원문에서 직접 확인 (⑤ 기준 D 누락 방지)
- 품목 키워드: 제품별 매출·생산실적 표를 뽑아 CBAM 대상 품목을 확인
- 이미 받은 원문 zip은 캐시를 재사용함
- 특정 계정만: python src/mfg/scan_report_terms.py "동국산업(주)"

출력: data/processed/term_scan/<계정>.txt, _summary.csv, _failures.csv
"""
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_eu_composition import (ROOT, api_key, annual_report_candidates,
                                  fetch_doc, scan)

OUT_DIR = ROOT / "data/processed/term_scan"
RCEPT_OVERRIDE = ROOT / "data/manual/eu_check_rcept.csv"
SUMMARY = OUT_DIR / "_summary.csv"
FAIL_LOG = OUT_DIR / "_failures.csv"

CARBON_KW = {"탄소": 8, "온실가스": 8, "CBAM": 6, "배출량": 6,
             "LCA": 4, "전과정평가": 4, "탄소발자국": 4,
             "환경성적표지": 3, "EPD": 3, "저탄소": 3}
PRODUCT_KW = {"주요 제품": 4, "생산실적": 4, "매출실적": 4, "품 목": 4}
SYS = re.compile(r"시스템|플랫폼|구축|솔루션|도입|산정")


def run_one(key, acc, corp_code, override=None):
    if override:
        candidates = [(override, "수동 지정")]
    else:
        candidates = annual_report_candidates(key, corp_code)

    zpath = rcept_no = report_nm = None
    errs = []
    for rn, nm in candidates:
        try:
            zpath = fetch_doc(key, rn)
            rcept_no, report_nm = rn, nm
            break
        except Exception as e:
            errs.append(f"{rn}: {e}")
    if zpath is None:
        raise RuntimeError(" / ".join(errs) or "내려받을 보고서가 없음")

    wanted = dict(CARBON_KW)
    wanted.update(PRODUCT_KW)
    hits = scan(zpath, wanted)

    sys_lines = [s for k in CARBON_KW for s in hits[k] if SYS.search(s)]
    lines = [f"# {acc} {report_nm} rcept_no={rcept_no}",
             f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}", "",
             f"## 탄소 + 시스템 단어가 함께 나온 문장 {len(sys_lines)}개"]
    lines += ["- " + s for s in sys_lines]
    for group, kws in (("탄소 키워드", CARBON_KW), ("품목 키워드", PRODUCT_KW)):
        lines.append(f"\n# {group}")
        for k in kws:
            if hits[k]:
                lines.append(f"## {k}")
                lines += ["- " + s for s in hits[k]]
    safe = re.sub(r"[^\w가-힣]", "", acc)
    (OUT_DIR / f"{safe}.txt").write_text("\n".join(lines), encoding="utf-8")
    return dict(account=acc, rcept_no=rcept_no, report=report_nm,
                carbon_hits=sum(len(hits[k]) for k in CARBON_KW),
                system_sentences=len(sys_lines),
                product_hits=sum(len(hits[k]) for k in PRODUCT_KW))


def main():
    force = "--force" in sys.argv
    picked = [a for a in sys.argv[1:] if not a.startswith("--")]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(ROOT / "data/processed/mfg2_base.csv", dtype=str)
    targets = picked or base["account"].tolist()

    overrides = {}
    if RCEPT_OVERRIDE.exists():
        ov = pd.read_csv(RCEPT_OVERRIDE, dtype=str)
        overrides = dict(zip(ov["account"], ov["rcept_no"]))

    key = api_key()
    rows, failed, skipped = [], [], 0
    if SUMMARY.exists():
        prev = pd.read_csv(SUMMARY)
        prev["rcept_no"] = prev["rcept_no"].astype(str)
        for c in ("carbon_hits", "system_sentences", "product_hits"):
            prev[c] = pd.to_numeric(prev[c], errors="coerce").fillna(0).astype(int)
        rows = prev.to_dict("records")
    done = {r["account"] for r in rows}

    for i, acc in enumerate(targets, 1):
        if not force and acc in done:
            skipped += 1
            continue
        row = base.loc[base["account"] == acc]
        override = overrides.get(acc)
        if row.empty and not override:
            failed.append((acc, "명단에 없음"))
            continue
        print(f"[{i}/{len(targets)}] {acc}", flush=True)
        try:
            corp_code = None if row.empty else row["corp_code"].iloc[0]
            if not override and (corp_code is None or pd.isna(corp_code)):
                raise RuntimeError("corp_code 없음 — eu_check_rcept.csv에 보고서 번호 필요")
            r = run_one(key, acc, corp_code, override)
            rows = [x for x in rows if x["account"] != acc] + [r]
            print(f"    탄소 {r['carbon_hits']} · 탄소+시스템 {r['system_sentences']} "
                  f"· 품목 {r['product_hits']}", flush=True)
        except Exception as e:
            failed.append((acc, f"{type(e).__name__}: {e}"))
            print(f"    실패: {type(e).__name__}: {e}", flush=True)
        time.sleep(0.5)

    if rows:
        df = pd.DataFrame(rows)
        for c in ("carbon_hits", "system_sentences", "product_hits"):
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        df = df.sort_values(["system_sentences", "carbon_hits"], ascending=False)
        df.to_csv(SUMMARY, index=False, encoding="utf-8-sig")
    if failed:
        pd.DataFrame(failed, columns=["account", "reason"]).to_csv(
            FAIL_LOG, index=False, encoding="utf-8-sig")
    print(f"\n완료 {len(rows)} · 건너뜀 {skipped} · 실패 {len(failed)}")


if __name__ == "__main__":
    main()