"""금융2-4 ③-1 ③' 감사보고서 실패분 4차 읽기 — 이번 성공분은 fin_s31_audit_fixed4.csv 에 따로 고정

- 입력: fin_s31_todo3.csv (fin2_s31_retry2.py) · fin_list.csv
- 대상: 검토 · 표 못 읽음 중 보험사·금융지주가 아닌 곳 (업종표 없음·보고서 없음·원문 오류는 그대로 넘김)
- 3차 실패 패턴과 수정 (2026-10-01)
  A 표 합계 > 총자산 (카드사 미사용 한도가 한 칸에 섞임, 칸 중복) → 분모 = 총자산과 표 합계 중 큰 쪽
    표 합계가 더 크면 표 안 제조업 비율을 씀 (분자·분모가 같은 비율로 부풀어도 비율은 맞음). 믿을 수 있는 위치면 채택
  B 주석 밖 표 → 표 바로 앞의 목차 제목(<TITLE>)으로 장을 판정 (주석·연결 주석·사업의 내용이면 믿을 수 있는 위치)
  C 숫자 정규화 → 각주 "(*1)"·"주1)", 음수 "△·▲", 띄어쓴 숫자를 정리한 뒤 읽음 ("본문 줄 부족" 9곳)
  D 고른 제조 줄이 모두 "제조원가·제조경비" 같은 줄이면 버림
- 위치 찾기 순서는 3차와 같음: 위험관리 주석 → 자산 주석 → 주석 구역 → 사업의 내용 → 연결 주석 → 문서 전체
- 출력: fin_s31_audit_fixed4.csv (이번 성공) · fin_s31_todo4.csv (남은 실패) · s31_audit_tables/*_v5.txt
"""
from collections import Counter
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_audit import _plain  # noqa: E402
from fin.fin1_list import key  # noqa: E402
from fin.fin2_lenders import UNIT, UNIT_X, choose, files_of  # noqa: E402
from fin.fin2_s31_audit import compact, region  # noqa: E402
from fin.fin2_s31_freeze import fnum  # noqa: E402
from fin.fin2_s31_retry import business_ranges  # noqa: E402
from fin.fin2_s31_retry2 import (ASSET_TITLE, RISK_TITLE, SKIP_GROUPS, TRUSTED, candidates3, read_table3,  # noqa: E402
                                 titled_ranges)

PROC = ROOT / "data" / "processed"
TODO3 = PROC / "fin_s31_todo3.csv"
FIXED4 = PROC / "fin_s31_audit_fixed4.csv"
TODO4 = PROC / "fin_s31_todo4.csv"
DUMP = PROC / "s31_audit_tables"
NUMISH = re.compile(r"^[\s\d,.\-()△▲−–*주]+$")
NOT_INDUSTRY = re.compile(r"제조(원가|경비|비용|간접|공정|원)")


def norm_cell(c):
    """C 숫자 정규화 — 각주·삼각형 음수·띄어쓴 숫자"""
    s = str(c).strip()
    if not s or not re.search(r"\d", s):
        return s
    t = re.sub(r"\(\s*\*\s*\d*\s*\)|\(\s*주\s*\d*\s*\)|주\s*\d+\)|\*+\d*", "", s)
    if not NUMISH.match(t):
        return s
    t = re.sub(r"\s+", "", t).replace("△", "-").replace("▲", "-").replace("−", "-").replace("–", "-")
    if re.match(r"^-\(.*\)$", t):
        t = t[1:]
    return t


def norm_grid(g):
    return [[norm_cell(c) for c in r] for r in g]


def section_of(x, pos):
    """B 표 바로 앞의 목차 제목 → (위치 이름, 제목)"""
    t = ""
    for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x[:pos], re.S):
        t = compact(re.sub(r"<[^>]+>", "", m.group(1)))
    if "주석" in t:
        return ("연결 주석" if "연결" in t else "주석 구역"), t
    if re.search(r"사업의내용|영업|여신|자산운용", t):
        return "사업의 내용", t
    return "문서 전체", t


def pick4(cands, thr):
    why = ""
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["score"] < thr:
            break
        info, w = read_table3(norm_grid(c["grid"]))
        if info and info["total"]:
            labels = [x.strip() for x in info["mfg_rows"].split(" + ")]
            if labels and all(NOT_INDUSTRY.search(compact(x)) for x in labels):
                why = why or "제조 줄이 원가·경비 줄"
                continue
            return c, info, ""
        why = why or (w or "합계 0")
    return None, None, why or ("산업별 문맥·업종 이름 부족(점수 미달)" if cands else "")


def classify4(where, info, share, ratio, mfg, unote, joined, title):
    notes, review, caution = [], [], []
    trusted = where in TRUSTED
    if title and where != "위험관리 주석":
        notes.append(f"장: {title[:30]}")
    if where == "연결 주석":
        notes.append("연결 기준 표")
    if where == "문서 전체":
        review.append("표 위치: 주석 밖")
    if joined:
        notes.append("나뉜 표 붙임")
    notes += info["memo"]
    if unote:
        notes.append(unote)
    if "(확인)" in info["basis"]:
        review.append("열 판정 불확실")
    if share > 100 or share < 0:
        review.append("비중 범위 밖")
    elif share == 0:
        (notes if trusted else review).append("제조업 0" + (" (믿을 수 있는 위치 — 실측 0)" if trusted else ""))
    eff = None
    if mfg is None:
        review.append("단위 못 찾음")
    elif ratio is not None and ratio > 1.0:                      # A 분모 = 표 합계
        eff = mfg / ratio
        (notes if trusted or ratio <= 1.7 else review).append(f"분모 = 표 합계(총자산의 {ratio:.2f}배)")
    elif ratio is not None and ratio < 0.05:
        (notes if trusted else review).append(f"기업 부문 표(표 합계/총자산 {ratio:.3f})")
    if info["sum_ok"] is False:
        caution.append("검산①: 업종 줄 합 ≠ 합계")
    if review:
        return "검토", " · ".join(review), " · ".join(notes), eff
    return ("분자 채택" if caution else "성공"), " · ".join(caution), " · ".join(notes), eff


def dump(acc, cands, picked, info):
    DUMP.mkdir(parents=True, exist_ok=True)
    lines = [f"# {acc} — {info}"]
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])[:5], 1):
        mark = " ◀ 선택" if c is picked else ""
        lines += [f"\n## 후보 {i} (위치 {c['where']}, 점수 {c['score']}, 단위 {c['unit'] or '?'}){mark}",
                  f"[앞 문맥] …{c['ctx'][-200:]}"]
        lines += [" | ".join(r) for r in norm_grid(c["grid"])[:45]]
    (DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}_v5.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    from dart_api import document_zip  # noqa: E402
    T = pd.read_csv(TODO3, dtype=str).fillna("")
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    li_of = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}
    go = T["fail_type"].isin(["검토", "표 못 읽음"]) & ~T["group"].isin(SKIP_GROUPS) & (T["rcept_no"] != "")
    print(f"4차 읽기 {int(go.sum())}곳 / 남은 {len(T)}곳", flush=True)
    fixed, todo = [], []
    for i, r in enumerate(T.to_dict("records")):
        if not go.iloc[i]:
            todo.append(r)
            continue
        acc, grp, rno = r["account"], r["group"], r["rcept_no"]
        assets = fnum(li_of.get(key(acc), {}).get("assets_jo"))
        try:
            files = files_of(document_zip(rno))
        except Exception as ex:  # noqa: BLE001
            todo.append(dict(r, pattern=f"원문 오류 {str(ex)[:40]}"))
            continue
        x, s, e, basis = choose(files)
        rr, area = titled_ranges(x, s, e, RISK_TITLE)
        ar, _ = titled_ranges(x, s, e, ASSET_TITLE)
        ns, ne = (area[1], area[2]) if area else (s, e)
        units = Counter(m.group(1) for m in UNIT.finditer(_plain(x[ns:ne])))
        cx, cs, ce, cb = region(files, True)
        conso = [(cx, cs, ce, "연결 주석")] if cb in ("연결감사보고서", "사업보고서 연결 주석") else []
        levels = [("위험관리 주석", [(x, a, b, "위험관리 주석") for a, b, _ in rr], 0),
                  ("자산 주석", [(x, a, b, "자산 주석") for a, b, _ in ar], 0),
                  ("주석 구역", [(x, ns, ne, "주석 구역")], 1),
                  ("사업의 내용", business_ranges(files), 1),
                  ("연결 주석", conso, 1),
                  ("문서 전체", [(xx, 0, len(xx), "문서 전체") for _, xx, _ in files], 1)]
        seen, allc, picked, info, why, where, title = set(), [], None, None, "", "", ""
        for label, spans, thr in levels:
            cands = []
            for sp in spans:                                    # 표가 어느 문서에 있는지 기억 (B 장 판정용)
                for c in candidates3([sp], seen, units):
                    c["x"] = sp[0]
                    cands.append(c)
            allc += cands
            picked, info, w = pick4(cands, thr)
            why = why or w
            if picked:
                where = label
                if label == "문서 전체":
                    where, title = section_of(picked["x"], picked["pos"])
                break
        dump(acc, allc, picked, f"{r.get('report_nm', '')} · {basis} · 위치 {where or '실패'} {title}")
        print(f"  {acc} — {where or '실패'} {title[:30]}", flush=True)
        if not picked:
            todo.append(dict(r, fail_type="표 못 읽음" if allc else "표 없음",
                             pattern=f"표 못 읽음 — {why}" if allc else "업종표 없음 — 4차"))
            continue
        ux = UNIT_X.get(picked["unit"])
        share = info["mfg"] / info["total"] * 100 if info["total"] else -1
        mfg = info["mfg"] * ux / 1e8 if ux else None
        ratio = (info["total"] * ux / 1e8) / (assets * 1e4) if (ux and assets) else None
        kind, why2, memo, eff = classify4(where, info, share, ratio, mfg, picked["unote"], picked["joined"], title)
        use_mfg = eff if eff is not None else mfg
        base = dict(account=acc, group=grp, layer=r["layer"], sector=r["sector"],
                    mfg_eok=round(use_mfg, 2) if use_mfg is not None else None,
                    mfg_eok_raw=round(mfg, 2) if mfg is not None else None, assets_jo=assets,
                    share_table=round(share, 3), total_to_assets=round(ratio, 4) if ratio else None,
                    col_basis=info["basis"], cols=info["heads"], mfg_rows=info["mfg_rows"], unit=picked["unit"],
                    location=where, section=title, rcept_no=rno, report_nm=r.get("report_nm", ""), audit_note=memo)
        if kind in ("성공", "분자 채택"):
            fixed.append(dict(base, share_assets=round(use_mfg / (assets * 1e4) * 100, 3) if assets else None,
                              check=kind, check_note=why2, value_basis="감사보고서(4차 읽기)"))
        else:
            todo.append(dict(r, mfg_eok=base["mfg_eok"], total_to_assets=base["total_to_assets"], fail_type="검토",
                             reason=why2, pattern=f"검토 — {why2}"))

    F4, T4 = pd.DataFrame(fixed), pd.DataFrame(todo)
    F4.to_csv(FIXED4, index=False, encoding="utf-8-sig")
    T4.to_csv(TODO4, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 300)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n이번 성공 {len(F4)}곳 → {FIXED4.relative_to(ROOT)} · 남은 {len(T4)}곳 → {TODO4.relative_to(ROOT)}")
    if len(F4):
        print("\n[1] 이번 성공 목록")
        print(F4[["account", "group", "share_assets", "total_to_assets", "location", "check", "audit_note"]].to_string(index=False))
    print("\n[2] 남은 실패 — 패턴별")
    if len(T4):
        p = T4["pattern"].fillna("").str.replace(r"(검토) — .*", r"\1", regex=True).str.replace(r"(원문 오류) .*", r"\1", regex=True)
        print(T4.assign(p=p).groupby("p").size().rename("곳").to_string())
    chk = T4[(T4["fail_type"] == "검토") & ~T4["group"].isin(SKIP_GROUPS)] if len(T4) else T4
    if len(chk):
        print("\n[3] 검토 목록 (보험·금융지주 제외)")
        print(chk[["account", "group", "mfg_eok", "total_to_assets", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
