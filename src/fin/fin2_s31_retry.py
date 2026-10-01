"""금융2-4 ③-1 ② 감사보고서 실패분 다시 읽기 — 이번 성공분은 fin_s31_audit_fixed2.csv 에 따로 고정

- 입력: fin_s31_todo.csv (fin2_s31_freeze.py) · fin_list.csv
- 1차 실패 195곳의 패턴과 수정 (2026-10-01)
  P1 위치 — 차입처 조사의 위치 찾기 원칙을 ③-1에 적용
     ① DART 목차 제목(<TITLE>)으로 주석 구역 → ② 주석 목차(번호 사슬)에서 제목에 위험관리·신용위험이 있는 주석
     → ③ 그 주석 구간의 표만 → ④ 주석 구역 전체 → ⑤ 사업보고서 "사업의 내용" → ⑥ 문서 전체(안전망, 검토)
  P2 가로형 표의 당기·전기 중복 — 돌리기 전에 원래 방향에서 "<전기>" 묶음 아래를 잘라 당기만 남김
     (표 합계가 총자산의 1.8~5.3배로 부풀던 원인)
  P3 나뉜 표 — 머리글만 있는 표 바로 뒤(400자 안)에 본문 표가 이어지면 붙여 읽음 ("본문 줄 부족")
  P4 출처 — "사업의 내용" 업종별 표는 출처를 적고 채택, 문서 전체에서만 찾은 표는 검토
  P5 보고서 없음 — DART 고유번호 목록에서 별칭(EZ→이지, 농협→NH농협)·이름 포함(한 곳만 걸릴 때)으로 다시 찾음
  P6 실제로 없음 — 위험관리 주석에 업종표 없음 / 업종표에 제조업 구분 없음(정부·금융·기업·개인만) /
     문서에 업종표 없음을 구분해 기록 → 합치기 단계에서 추정 대상
- 성공·분자 채택·검토 기준은 fin2_s31_freeze.classify 와 같음 (원문 오류는 fin2_s31_fill.py 가 처리하도록 그대로 넘김)
- 출력: fin_s31_audit_fixed2.csv (이번 성공) · fin_s31_todo2.csv (남은 실패와 패턴) · s31_audit_tables/*_v3.txt
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_audit import _plain  # noqa: E402
from fin.fin1_list import key, name2  # noqa: E402
from fin.fin2_lenders import UNIT, UNIT_X, files_of, toc_area  # noqa: E402
from fin.fin2_s31_audit import (BAD_CTX, CURR, INDUSTRY_CTX, MFG, PREV, compact, find_report, grid, is_num,  # noqa: E402
                                read_table, region)
from fin.fin2_s31_freeze import classify, fnum  # noqa: E402

PROC = ROOT / "data" / "processed"
TODO = PROC / "fin_s31_todo.csv"
FIXED2 = PROC / "fin_s31_audit_fixed2.csv"
TODO2 = PROC / "fin_s31_todo2.csv"
DUMP = PROC / "s31_audit_tables"
RISK_TITLE = re.compile(r"위험관리|금융위험|신용위험|위험의관리|재무위험")
IND_WORDS = re.compile(r"건설|도소매|도매|부동산|금융|숙박|운수|서비스|공공|정부|가계|개인|기타")
PERIOD_PREV = re.compile(r"^<?\(?(전기|전년|전기말|2024)")
ALIAS = [("EZ", "이지"), ("이지", "EZ")]


def note_chain(x, s, e):
    """주석 목차 — (번호, 제목, 시작) 목록. 표 안 글자는 지우고 1부터 차례로 이어지는 번호만"""
    seg = re.sub(r"<TABLE\b.*?</TABLE>", lambda m: " " * len(m.group(0)), x[s:e], flags=re.S | re.I)
    chain = []
    for m in re.finditer(r">\s*(\d{1,2})\s?\.\s?([가-힣][^<(:\d]{1,40})", seg):
        k = int(m.group(1))
        if (not chain and k == 1) or (chain and k == chain[-1][0] + 1):
            chain.append((k, m.group(2).strip(), s + m.start()))
    return chain


def risk_ranges(x, s, e):
    """위험관리·신용위험 주석 구간 [(시작, 끝, 제목)] — 목차 구역이 있으면 그 안에서"""
    area = toc_area(x, s, e)
    ns, ne = (area[1], area[2]) if area else (s, e)
    chain = note_chain(x, max(s, ns - 300), ne)
    if len(chain) < 5:
        return [], area
    out = []
    for i, (k, t, p) in enumerate(chain):
        if RISK_TITLE.search(compact(t)[:15]):
            out.append((p, chain[i + 1][2] if i + 1 < len(chain) else ne, f"{k}. {t}"))
    return out, area


def business_ranges(files):
    out = []
    for _, x, _ in files:
        titles = [(m.start(), compact(re.sub(r"<[^>]+>", "", m.group(1))))
                  for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
        for i, (p, t) in enumerate(titles):
            if re.search(r"사업의내용", t):
                end = next((q for q, tt in titles[i + 1:] if re.match(r"^(III|Ⅲ|3)\.|재무에관한", tt)), len(x))
                out.append((x, p, end, "사업의 내용"))
    return out


def trim_periods(g):
    """한 표 안 당기·전기 묶음 — 두 번째 묶음(전기) 머리 줄부터 잘라냄 (돌리기 전에)"""
    for i, r in enumerate(g[1:], 1):
        first = compact(next((c for c in r if c), ""))
        if PERIOD_PREV.match(first) and sum(is_num(c) for c in r) <= 1:
            return g[:i]
    return g


def tables_in(x, a, b):
    return [(a + m.start(), a + m.end(), m.group(0)) for m in re.finditer(r"<TABLE\b.*?</TABLE>", x[a:b], flags=re.S | re.I)]


def candidates2(spans, seen):
    """spans: [(본문, 시작, 끝, 표시)] → 후보 표 (나뉜 표는 붙임)"""
    out = []
    for x, a, b, label in spans:
        tl = tables_in(x, a, b)
        for i, (p, q, tb) in enumerate(tl):
            if (id(x), p) in seen:
                continue
            g = grid(tb)
            joined = False
            small = len(g) < 4 or not any(is_num(c) for r in g for c in r[1:])
            if small and i + 1 < len(tl) and tl[i + 1][0] - q < 400:
                g2 = grid(tl[i + 1][2])
                if g2:
                    g, joined = g + g2, True
            if len(g) < 4 or not MFG.search(compact(" ".join(" ".join(r) for r in g))):
                continue
            seen.add((id(x), p))
            ctx = _plain(x[max(0, p - 1500):p])[-400:]
            head = " ".join(" ".join(r) for r in g[:3])
            near, hc = compact(ctx[-250:]), compact(head)
            score = 3 if INDUSTRY_CTX.search(near + hc) else 0
            score -= 2 if BAD_CTX.search(near) else 0
            score += 1 if CURR.search(compact(ctx[-150:]) + hc) else 0
            score -= 3 if PREV.search(compact(ctx[-120:]) + hc) and not CURR.search(compact(ctx[-120:]) + hc) else 0
            unit = UNIT.search(ctx[-250:] + " " + head)
            out.append(dict(pos=p, ctx=ctx, grid=g, score=score, unit=unit.group(1) if unit else "", where=label,
                            joined=joined))
    return out


def pick2(cands, thr):
    why = ""
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["score"] < thr:
            break
        info, w = read_table(trim_periods(c["grid"]))
        if info and info["total"]:
            return c, info, ""
        why = why or (w or "합계 0")
    return None, None, why


def industry_tables_without_mfg(spans):
    n = 0
    for x, a, b, _ in spans:
        for _, _, tb in tables_in(x, a, b):
            t = compact(_plain(tb))
            if not MFG.search(t) and len(set(IND_WORDS.findall(t))) >= 4:
                n += 1
    return n


def lookup_codes(acc, by_k, by_n2, names):
    """고유번호 후보 — 이름 · 음역 · 별칭 · 이름 포함(한 곳만)"""
    k = key(acc)
    cand = by_k.get(k, [])[:5] + by_n2.get(name2(acc), [])[:5]
    for a, b in ALIAS:
        if a in k:
            cand += by_k.get(k.replace(a, b), [])[:3]
    if k.startswith("농협"):
        cand += by_k.get("NH" + k, [])[:3] + by_k.get("엔에이치" + k, [])[:3]
    if len(k) >= 4:
        hit = [c for n_, c in names if k in n_ or (len(n_) >= 4 and n_ in k)]
        if 0 < len(hit) <= 3:
            cand += hit
    return list(dict.fromkeys(cand))


def dump(acc, cands, picked, info):
    DUMP.mkdir(parents=True, exist_ok=True)
    lines = [f"# {acc} — {info}"]
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])[:4], 1):
        mark = " ◀ 선택" if c is picked else ""
        lines += [f"\n## 후보 {i} (위치 {c['where']}, 점수 {c['score']}, 단위 {c['unit'] or '?'}"
                  f"{', 나뉜 표 붙임' if c['joined'] else ''}){mark}", f"[앞 문맥] …{c['ctx'][-200:]}"]
        lines += [" | ".join(r) for r in c["grid"][:45]]
    (DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}_v3.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    from dart_api import corp_codes, document_zip, get_json  # noqa: E402
    T = pd.read_csv(TODO, dtype=str).fillna("")
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    li_of = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}
    cc = corp_codes()
    by_k, by_n2, names = {}, {}, []
    for c_, n_ in zip(cc["corp_code"], cc["corp_name"]):
        by_k.setdefault(key(n_), []).append(str(c_))
        by_n2.setdefault(name2(n_), []).append(str(c_))
        names.append((key(n_), str(c_)))
    print(f"다시 읽기 {len(T)}곳 (원문 오류 {int((T['fail_type'] == '원문 오류').sum())}곳은 채우기 단계로 넘김)", flush=True)
    fixed, todo = [], []
    for i, r in enumerate(T.to_dict("records"), 1):
        acc, grp, kind = r["account"], r["group"], r["fail_type"]
        li = li_of.get(key(acc), {})
        assets = fnum(li.get("assets_jo"))
        if kind == "원문 오류":
            todo.append(dict(r, pattern="원문 오류 — 채우기 단계"))
            continue
        rno, rnm = r.get("rcept_no", ""), r.get("report_nm", "")
        if not rno:                                          # P5 보고서 다시 찾기
            for c_ in lookup_codes(acc, by_k, by_n2, names):
                try:
                    a_, b_, _ = find_report(c_, get_json)
                except Exception:  # noqa: BLE001
                    continue
                if a_:
                    rno, rnm = a_, b_
                    break
        if not rno:
            todo.append(dict(r, pattern="보고서 없음 — " + ("2025-07 이후 공시 없음" if r.get("code_src") != "고유번호 없음"
                                                          else "DART 고유번호 못 찾음")))
            continue
        try:
            files = files_of(document_zip(rno))
        except Exception as ex:  # noqa: BLE001
            todo.append(dict(r, fail_type="원문 오류", rcept_no=rno, report_nm=rnm, pattern=f"원문 오류 {str(ex)[:40]}"))
            continue
        x, s, e, basis = region(files, grp == "금융지주")
        rr, area = risk_ranges(x, s, e)
        levels = [("위험관리 주석", [(x, a, b, "위험관리 주석") for a, b, _ in rr], 0),
                  ("주석 구역", [(x, area[1], area[2], "주석 구역")] if area else [(x, s, e, "별도·연결 구역")], 1),
                  ("사업의 내용", business_ranges(files), 1),
                  ("문서 전체", [(xx, 0, len(xx), "문서 전체") for _, xx, _ in files], 1)]
        seen, allc, picked, info, why, where = set(), [], None, None, "", ""
        for label, spans, thr in levels:
            cands = candidates2(spans, seen)
            allc += cands
            picked, info, w = pick2(cands, thr)
            why = why or w
            if picked:
                where = label
                break
        rtitle = " / ".join(t for _, _, t in rr)[:60]
        dump(acc, allc, picked, f"{rnm} · {basis} · 위험관리 주석: {rtitle or '못 찾음'}")
        print(f"  [{i}/{len(T)}] {acc} — {where or '실패'}", flush=True)
        if not picked:
            no_mfg = industry_tables_without_mfg([(x, a, b, "") for a, b, _ in rr] or [(x, s, e, "")])
            pat = ("업종표에 제조업 구분 없음(거래상대방 유형만)" if no_mfg else
                   "위험관리 주석 있음 — 업종표 없음" if rr else
                   "위험관리 주석 못 찾음 — 문서에 업종표 없음" if not allc else f"표 못 읽음 — {why}")
            todo.append(dict(r, fail_type="표 없음" if not allc else "표 못 읽음", rcept_no=rno, report_nm=rnm, pattern=pat))
            continue
        ux = UNIT_X.get(picked["unit"])
        notes = []
        if where == "사업의 내용":
            notes.append("출처: 사업의 내용")
        elif where == "문서 전체":
            notes.append("표 위치: 주석 밖")
        if picked["joined"]:
            notes.append("나뉜 표 붙임")
        if info["sum_ok"] is False:
            notes.append("검산①: 업종 줄 합 ≠ 합계")
        if not ux:
            notes.append("단위 못 찾음")
        if "(확인)" in info["basis"]:
            notes.append("열 판정 불확실")
        share = info["mfg"] / info["total"] * 100
        if not (0 < share <= 100):
            notes.append("비중 범위 밖")
        mfg = info["mfg"] * ux / 1e8 if ux else None
        ratio = (info["total"] * ux / 1e8) / (assets * 1e4) if (ux and assets) else None
        k2, wy = classify(" · ".join(notes), ratio, mfg)
        base = dict(account=acc, group=grp, layer=r["layer"], sector=r["sector"], mfg_eok=round(mfg, 2) if mfg else mfg,
                    assets_jo=assets, share_table=round(share, 3), total_to_assets=round(ratio, 3) if ratio else None,
                    col_basis=info["basis"], cols=info["heads"], mfg_rows=info["mfg_rows"], unit=picked["unit"],
                    location=where, risk_note=rtitle, rcept_no=rno, report_nm=rnm, audit_note=" · ".join(notes))
        if k2 in ("성공", "분자 채택"):
            fixed.append(dict(base, share_assets=round(mfg / (assets * 1e4) * 100, 3) if assets else None,
                              check=k2, check_note=wy, value_basis="감사보고서(다시 읽기)"))
        else:
            todo.append(dict(r, **{k: v for k, v in base.items() if k in ("mfg_eok", "share_table", "total_to_assets",
                                                                            "rcept_no", "report_nm")},
                             fail_type="검토", reason=wy, pattern=f"검토 — {wy}"))

    F2, T2 = pd.DataFrame(fixed), pd.DataFrame(todo)
    F2.to_csv(FIXED2, index=False, encoding="utf-8-sig")
    T2.to_csv(TODO2, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 230)
    pd.set_option("display.max_rows", 300)
    pd.set_option("display.max_colwidth", 60)
    print(f"\n이번 성공 {len(F2)}곳 → {FIXED2.relative_to(ROOT)} · 남은 {len(T2)}곳 → {TODO2.relative_to(ROOT)}")
    if len(F2):
        print("\n[1] 이번 성공 — 집단 × 표 위치")
        print(F2.pivot_table(index="group", columns="location", values="account", aggfunc="count", fill_value=0).to_string())
        print("\n[2] 이번 성공 목록")
        print(F2[["account", "group", "share_assets", "total_to_assets", "location", "check", "audit_note"]].to_string(index=False))
    print("\n[3] 남은 실패 — 패턴별")
    if len(T2):
        T2["p"] = T2["pattern"].str.replace(r"(검토) — .*", r"\1", regex=True).str.replace(r"(원문 오류) .*", r"\1", regex=True)
        print(T2.groupby(["p", "group"]).size().rename("곳").reset_index().to_string(index=False))
    else:
        print("  없음")
    chk = T2[T2["fail_type"] == "검토"]
    if len(chk):
        print("\n[4] 검토 목록")
        print(chk[["account", "group", "mfg_eok", "total_to_assets", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
