"""금융2-1 ① 공시 지위 채점

- 입력: data/processed/fin_list.csv (금융-1 명단 278곳 — layer · disclosure_basis · disclosure_year 칸)
- 기준 (계획서 7-4, 04 문서 3-4 — 확정)
  - 2점: 상장 — 자본시장법상 공시 주체
  - 1점: 비상장 종속(금융 모회사·손자회사·명단 밖 코스피 모회사) — 지배회사 연결 공시에 포함
          공공금융기관 · 공공기관 종속 — 알리오 통합공시(강제력이 자본시장법보다 약함)
  - 0점: 비상장 비종속(대기업집단·독립·외국계) — 공시 의무 없음
          지배회사 연결자산 2조 미만인 종속(disclosure_year "대상 아님(지배회사 2조 미만)", 28곳 예상) — 지배회사가 공시 대상 아님
- 비고: 핀크는 주력이 중개업이나 온라인투자연계금융 상품에 법인 투자가 있어 명단 유지 (2026-10-01 결정, 04 문서 3-8)
- 출력: data/processed/fin_s1.csv (account · layer · disclosure_basis · disclosure_year · s1 · s1_reason · s1_note)
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fin_s1.csv"

RULE = {                                           # 층 → (점수, 근거)
    "상장": (2, "상장 — 자본시장법상 공시 주체"),
    "비상장 종속": (1, "금융 모회사의 종속 — 지배회사 연결 공시에 포함"),
    "비상장 종속(손자회사)": (1, "손자회사 — 최상위 지배회사 연결 공시에 포함"),
    "비상장 종속(명단 밖 코스피 모회사)": (1, "코스피 모회사의 종속 — 지배회사 연결 공시에 포함"),
    "공공금융기관": (1, "공공금융기관 — 알리오 통합공시(자본시장법보다 강제력 약함)"),
    "공공기관 종속": (1, "공공금융기관의 종속 — 지배기관 연결에 포함"),
    "비상장 비종속(대기업집단)": (0, "비상장 비종속 — 공시 의무 없음"),
    "비상장 비종속(독립·외국계)": (0, "비상장 비종속 — 공시 의무 없음"),
}
UNDER2 = "대상 아님(지배회사 2조 미만)"
NOTE = {key("핀크"): "주력 중개업 · 온라인투자연계금융 상품 법인 투자 — 명단 유지(2026-10-01)"}
EXPECT = {2: 40, 1: 163, 0: 75}                    # 금융-1 층별 곳 수로 계산한 예상 분포


def score(r):
    layer, year = str(r["layer"]).strip(), str(r.get("disclosure_year", "")).strip()
    if layer not in RULE:
        return None, f"확인 필요 — 알 수 없는 층 '{layer}'"
    s, why = RULE[layer]
    if s == 1 and year == UNDER2:
        return 0, "지배회사 연결자산 2조 미만 — 지배회사가 공시 대상 아님 (03 문서 2-27)"
    return s, why


def main():
    d = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    res = d.apply(score, axis=1, result_type="expand")
    d["s1"], d["s1_reason"] = res[0], res[1]
    d["s1_note"] = d["account"].map(lambda a: NOTE.get(key(a), ""))
    cols = ["account", "layer", "disclosure_basis", "disclosure_year", "s1", "s1_reason", "s1_note"]
    d[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(f"명단 {len(d)}곳 → {OUT.relative_to(ROOT)}\n")
    print("[층별 점수]")
    print(d.groupby(["layer", "s1"], dropna=False).size().rename("곳").reset_index().to_string(index=False))
    v = d["s1"].value_counts(dropna=False).to_dict()
    print("\n[분포] " + " · ".join(f"{k}점 {v.get(k, 0)}곳 (예상 {EXPECT[k]})" for k in (2, 1, 0)))
    bad = d[d["s1"].isna()]
    if len(bad):
        print(f"\n[점검] 층을 알 수 없는 계정 {len(bad)}곳:", ", ".join(bad["account"]))
    odd = d[((d["s1"] == 1) & (d["disclosure_basis"] == "없음")) |
            ((d["s1"] == 0) & d["disclosure_basis"].isin(["자본시장법", "지배회사 연결 공시"]) & (d["disclosure_year"] != UNDER2))]
    print(f"[점검] 점수와 공시 근거 칸이 어긋나는 계정 {len(odd)}곳" + (": " + ", ".join(odd["account"]) if len(odd) else ""))
    print(f"[비고] {', '.join(d.loc[d['s1_note'] != '', 'account']) or '없음'}")


if __name__ == "__main__":
    main()
