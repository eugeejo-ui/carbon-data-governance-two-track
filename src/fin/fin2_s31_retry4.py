"""금융2-4 ③-1 ③'' 감사보고서 실패분 5차 읽기 — 이번 성공분은 fin_s31_audit_fixed5.csv 에 따로 고정

- 입력: fin_s31_todo4.csv (fin2_s31_retry3.py) · fin_list.csv
- 대상: 검토 · 표 못 읽음 중 보험사·금융지주가 아닌 곳
- 4차 실패 패턴과 수정 (2026-10-01)
  ① 장 판정을 목차 위계로 — 표 바로 앞 제목이 위험관리·자산 주석이면 그 주석(상위 제목이나 자기 제목에 "연결"이 있으면
     연결 주석), 그 밖은 상위 제목(주석·사업의 내용)과 표 내용(첫 칸 업종 이름 3개 이상)으로 판정
     (대신증권 "4. 금융위험의 관리(연결)"을 주석 밖으로 보던 문제)
  ② 관련 없는 장의 표는 건너뛰고 다음 후보를 봄 — 출자·우발부채·종속기업·관계기업·회사 개요·주주·임원·소송·담보·계열
     (안전망이 "제조" 글자가 든 아무 표나 잡던 문제 — 미래에셋증권·IBK캐피탈·LS증권·신한자산신탁·현대차증권)
  ③ 업종표다운 내용이면 문맥 감점을 빼줌 — 첫 칸에 업종 이름 3개 이상이면 "손상·연체" 문맥 감점 무시 ("점수 미달")
  ④ 진단 — 끝까지 못 읽은 곳은 가장 점수 높은 후보 표의 첫 6줄을 출력
  ⑤ (5차 진단 반영) 업종표 판정에 머리글(위 3줄)도 봄 — 업종이 칸 이름인 표(메리츠증권)를 "관련 없는 표"로 버리던 문제
  ⑥ (5차 진단 반영) 맨 위 반복 줄 제거 — 모든 칸이 "(단위: 천원)"·"당기말"처럼 같은 글자인 줄은 지움(돌린 표에서 이름 칸으로
     잘못 잡히던 문제, 우리투자증권). 표 안 단위 표시를 표 앞 문맥보다 우선
- 분모 = 총자산과 표 합계 중 큰 쪽, 숫자 정규화, 칸 구조 찾기 등은 4차와 같음
- 출력: fin_s31_audit_fixed5.csv (이번 성공) · fin_s31_todo5.csv (남은 실패) · s31_audit_tables/*_v6.txt
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
from fin.fin2_s31_audit import BAD_CTX, compact, region  # noqa: E402
from fin.fin2_s31_freeze import fnum  # noqa: E402
from fin.fin2_s31_retry import business_ranges  # noqa: E402
from fin.fin2_s31_retry2 import (ASSET_TITLE, IND_WORDS, RISK_TITLE, SKIP_GROUPS, candidates3, read_table3,  # noqa: E402
                                 titled_ranges)
from fin.fin2_s31_audit import is_num  # noqa: E402
from fin.fin2_s31_retry import trim_periods  # noqa: E402
from fin.fin2_s31_retry3 import NOT_INDUSTRY, classify4, norm_grid  # noqa: E402

PROC = ROOT / "data" / "processed"
TODO4 = PROC / "fin_s31_todo4.csv"
FIXED5 = PROC / "fin_s31_audit_fixed5.csv"
TODO5 = PROC / "fin_s31_todo5.csv"
DUMP = PROC / "s31_audit_tables"
TITLE = re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.S)
MAJOR = re.compile(r"주석|사업의내용|재무에관한|회사의개요|이사의경영진단|감사인|주주|임원|계열회사")
OFF_TOPIC = re.compile(r"출자|우발|종속기업|관계기업|회사의개요|주주|임원|소송|담보|계열|특수관계|대주주|약정|보증")


def ind_of(g):
    """업종 이름 수 — 첫 칸과 머리글(위 3줄) 중 많은 쪽 (⑤)"""
    first = compact(" ".join(r[0] for r in g if r))
    head = compact(" ".join(" ".join(r) for r in g[:3]))
    return max(len(set(IND_WORDS.findall(first))), len(set(IND_WORDS.findall(head))))


def banner(r):
    vals = {compact(c) for c in r if str(c).strip()}
    return len(vals) == 1 and not any(is_num(c) for c in r)


def clean(g):
    """⑥ 전기 묶음을 자른 뒤(줄 이름에 기대므로 먼저) 모든 칸이 같은 글자인 줄을 지움"""
    g = trim_periods(norm_grid(g))
    return [r for r in g if not banner(r)] or g


def section2(x, pos, g):
    """① 목차 위계로 장 판정 → (위치 이름 또는 None, 바로 앞 제목)"""
    titles = [compact(re.sub(r"<[^>]+>", "", m.group(1))) for m in TITLE.finditer(x[:pos])]
    imm = titles[-1] if titles else ""
    major = next((t for t in reversed(titles) if MAJOR.search(t)), "")
    conso = "연결" in imm or "연결" in major
    if RISK_TITLE.search(imm):
        return ("연결 주석" if conso else "위험관리 주석"), imm
    if ASSET_TITLE.search(imm):
        return ("연결 주석" if conso else "자산 주석"), imm
    if OFF_TOPIC.search(imm):                                # ② 관련 없는 장
        return None, imm
    if ind_of(g) >= 3:
        if "주석" in major:
            return ("연결 주석" if conso else "주석 구역"), imm
        if "사업의내용" in major:
            return "사업의 내용", imm
    return None, imm


def rescore(cands):
    """③ 업종표다운 내용이면 문맥 감점 무시"""
    for c in cands:
        if ind_of(c["grid"]) >= 3 and BAD_CTX.search(compact(c["ctx"][-250:])):
            c["score"] += 2
    return cands


def pick5(cands, thr, check):
    why, skipped = "", []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["score"] < thr:
            break
        if check:
            where, title = section2(c["x"], c["pos"], c["grid"])
            if where is None:
                skipped.append(title[:20])
                continue
            c["where2"], c["title"] = where, title
        info, w = read_table3(clean(c["grid"]))
        if info and info["total"]:
            labels = [x.strip() for x in info["mfg_rows"].split(" + ")]
            if labels and all(NOT_INDUSTRY.search(compact(x)) for x in labels):
                why = why or "제조 줄이 원가·경비 줄"
                continue
            return c, info, "", skipped
        why = why or (w or "합계 0")
    if not why and skipped:
        why = "관련 없는 장의 표만 있음(" + ", ".join(dict.fromkeys(skipped))[:60] + ")"
    return None, None, why or ("산업별 문맥·업종 이름 부족(점수 미달)" if cands else ""), skipped


def dump(acc, cands, picked, info):
    DUMP.mkdir(parents=True, exist_ok=True)
    lines = [f"# {acc} — {info}"]
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])[:5], 1):
        mark = " ◀ 선택" if c is picked else ""
        lines += [f"\n## 후보 {i} (위치 {c['where']}, 점수 {c['score']}, 단위 {c['unit'] or '?'}){mark}",
                  f"[앞 문맥] …{c['ctx'][-200:]}"]
        lines += [" | ".join(r) for r in norm_grid(c["grid"])[:45]]
    (DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}_v6.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    from dart_api import document_zip  # noqa: E402
    T = pd.read_csv(TODO4, dtype=str).fillna("")
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    li_of = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}
    go = T["fail_type"].isin(["검토", "표 못 읽음"]) & ~T["group"].isin(SKIP_GROUPS) & (T["rcept_no"] != "")
    print(f"5차 읽기 {int(go.sum())}곳 / 남은 {len(T)}곳", flush=True)
    fixed, todo, diag = [], [], []
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
        levels = [("위험관리 주석", [(x, a, b, "위험관리 주석") for a, b, _ in rr], 0, False),
                  ("자산 주석", [(x, a, b, "자산 주석") for a, b, _ in ar], 0, False),
                  ("주석 구역", [(x, ns, ne, "주석 구역")], 1, True),
                  ("사업의 내용", business_ranges(files), 1, False),
                  ("연결 주석", conso, 1, True),
                  ("문서 전체", [(xx, 0, len(xx), "문서 전체") for _, xx, _ in files], 1, True)]
        seen, allc, picked, info, why, where, title = set(), [], None, None, "", "", ""
        for label, spans, thr, check in levels:
            cands = []
            for sp in spans:
                for c in candidates3([sp], seen, units):
                    c["x"] = sp[0]
                    cands.append(c)
            cands = rescore(cands)
            allc += cands
            picked, info, w, _ = pick5(cands, thr, check)
            why = why or w
            if picked:
                where, title = (picked.get("where2", label), picked.get("title", "")) if check else (label, "")
                break
        dump(acc, allc, picked, f"{r.get('report_nm', '')} · {basis} · 위치 {where or '실패'} {title}")
        print(f"  {acc} — {where or '실패'} {title[:30]}", flush=True)
        if not picked:
            todo.append(dict(r, fail_type="표 못 읽음" if allc else "표 없음",
                             pattern=f"표 못 읽음 — {why}" if allc else "업종표 없음 — 5차"))
            if allc:
                top = sorted(allc, key=lambda c: -c["score"])[0]
                diag.append((acc, why, top["where"], top["score"], norm_grid(top["grid"])[:6]))
            continue
        inner = UNIT.search(" ".join(" ".join(r) for r in picked["grid"][:2]))     # ⑥ 표 안 단위 우선
        if inner:
            picked["unit"], picked["unote"] = inner.group(1), ""
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
                              check=kind, check_note=why2, value_basis="감사보고서(5차 읽기)"))
        else:
            todo.append(dict(r, mfg_eok=base["mfg_eok"], total_to_assets=base["total_to_assets"], fail_type="검토",
                             reason=why2, pattern=f"검토 — {why2}"))

    F5, T5 = pd.DataFrame(fixed), pd.DataFrame(todo)
    F5.to_csv(FIXED5, index=False, encoding="utf-8-sig")
    T5.to_csv(TODO5, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 300)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n이번 성공 {len(F5)}곳 → {FIXED5.relative_to(ROOT)} · 남은 {len(T5)}곳 → {TODO5.relative_to(ROOT)}")
    if len(F5):
        print("\n[1] 이번 성공 목록")
        print(F5[["account", "group", "share_assets", "total_to_assets", "location", "section", "check", "audit_note"]]
              .to_string(index=False))
    print("\n[2] 남은 실패 — 패턴별")
    if len(T5):
        p = T5["pattern"].fillna("").str.replace(r"(검토) — .*", r"\1", regex=True).str.replace(r"(원문 오류) .*", r"\1", regex=True)
        p = p.str.replace(r"\(.*\)$", "", regex=True)
        print(T5.assign(p=p).groupby("p").size().rename("곳").to_string())
    chk = T5[(T5["fail_type"] == "검토") & ~T5["group"].isin(SKIP_GROUPS)] if len(T5) else T5
    if len(chk):
        print("\n[3] 검토 목록 (보험·금융지주 제외)")
        print(chk[["account", "group", "mfg_eok", "total_to_assets", "reason"]].to_string(index=False))
    if diag:
        print("\n[4] 진단 — 못 읽은 곳의 가장 점수 높은 후보 표 첫 6줄")
        for acc, why, wh, sc, rows in diag:
            print(f"\n  ■ {acc} — {why} (위치 {wh}, 점수 {sc})")
            for row in rows:
                print("    " + " | ".join(c[:14] for c in row[:8]))


if __name__ == "__main__":
    main()
