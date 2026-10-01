"""금융2-4 ③-1 ③ 감사보고서 실패분 3차 읽기 — 이번 성공분은 fin_s31_audit_fixed3.csv 에 따로 고정

- 입력: fin_s31_todo2.csv (fin2_s31_retry.py) · fin_list.csv
- 대상: 검토 · 표 없음 · 표 못 읽음 중 보험사·금융지주가 아닌 곳
  (보험은 FISIS 대출, 금융지주는 자회사 합산으로 정했으므로 다시 읽지 않음. 원문 오류·보고서 없음은 그대로 넘김)
- 2차 실패 패턴과 수정 (2026-10-01)
  A·B 칸 중복 — 위치는 맞는데 표 합계가 총자산의 1.7~5배: 조사한 "합계 구조 찾기"를 칸에도 적용
       ① 값이 같은 칸은 하나만 ② 한 칸이 다른 칸들의 합이면 그 칸 하나만
  C   작은 표 — 믿을 수 있는 위치(위험관리·자산·연결 주석, 주석 구역)면 표 합계가 총자산의 0.05배 미만이어도 채택
       ("기업 부문 표" 표시 — 분모가 총자산이라 분자는 그대로 유효)
  D   제조업 0 — 믿을 수 있는 위치면 실측 0으로 채택, 그 밖은 검토
  E   연결 주석 — 상장사 사업보고서의 연결 주석을 별도 단계로 두고 "연결 기준 표"로 채택
  F   자산 주석 — 주석 목차에서 대출채권·여신·금융자산·유가증권·할부·리스 주석도 찾음 (위치 찾기 원칙 3·5단계 확장)
  G   내용 기반 업종표 판정 — 첫 칸(또는 머리글)에 업종 이름이 3개 이상이면 산업별 문맥이 없어도 업종표로 인정
  H   단위 — 표 앞 3,000자 → 그 구역에서 가장 많이 쓴 단위 순
  버그 — 후보 표가 있었는데 못 읽은 곳을 "업종표 없음"으로 적던 순서 오류 수정
- 위치 찾기 순서: 위험관리 주석 → 자산 주석 → 주석 구역 → 사업의 내용 → 연결 주석 → 문서 전체(안전망, 검토)
- 출력: fin_s31_audit_fixed3.csv (이번 성공) · fin_s31_todo3.csv (남은 실패와 패턴) · s31_audit_tables/*_v4.txt
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
from fin.fin2_lenders import UNIT, UNIT_X, choose, files_of, to_num, toc_area  # noqa: E402
from fin.fin2_s31_audit import (BAD_CTX, COL_LOAN, COL_OFF, COL_SKIP, CURR, HOUSEHOLD, INDUSTRY_CTX, MFG, PREV,  # noqa: E402
                                SUBTOTAL_ROW, TOTAL_ROW, compact, grid, is_num, region, split_header, transpose)
from fin.fin2_s31_freeze import fnum  # noqa: E402
from fin.fin2_s31_retry import business_ranges, note_chain, tables_in, trim_periods  # noqa: E402

PROC = ROOT / "data" / "processed"
TODO2 = PROC / "fin_s31_todo2.csv"
FIXED3 = PROC / "fin_s31_audit_fixed3.csv"
TODO3 = PROC / "fin_s31_todo3.csv"
DUMP = PROC / "s31_audit_tables"
RISK_TITLE = re.compile(r"위험관리|금융위험|신용위험|위험의관리|재무위험")
ASSET_TITLE = re.compile(r"대출채권|여신|대출금|금융자산|유가증권|할부|리스|상각후원가|매출채권|카드자산|채무증권")
IND_WORDS = re.compile(r"건설|도소매|도매|소매|부동산|금융|보험|숙박|음식|운수|운송|창고|정보통신|서비스|공공|정부|전기|가스|"
                       r"농업|어업|광업|가계|개인|사업시설|전문|과학")
TRUSTED = {"위험관리 주석", "자산 주석", "주석 구역", "사업의 내용", "연결 주석"}
SKIP_GROUPS = {"생명보험", "손해보험", "금융지주"}


def val(r, cols):
    s = 0.0
    for j in cols:
        v = to_num(r[j]) if j < len(r) else None
        s += v or 0.0
    return s


def column_structure(body, use):
    """칸 구조 찾기 — (남길 칸, 메모). ① 값이 같은 칸은 하나만 ② 한 칸이 다른 칸들의 합이면 그 칸만"""
    memo = []
    keep = []
    for j in use:
        vj = [val(r, [j]) for _, _, r in body]
        dup = False
        for k in keep:
            vk = [val(r, [k]) for _, _, r in body]
            pairs = [(a, b) for a, b in zip(vj, vk) if a or b]
            if len(pairs) >= 3 and sum(abs(a - b) <= max(1.0, abs(a) * 0.01) for a, b in pairs) >= 0.8 * len(pairs):
                dup = True
                break
        if not dup:
            keep.append(j)
    if len(keep) < len(use):
        memo.append(f"같은 값 칸 {len(use) - len(keep)}개 제외")
    use = keep
    if len(use) >= 3:
        for j in use:
            others = [k for k in use if k != j]
            nz = [(val(r, [j]), val(r, others)) for _, _, r in body if val(r, [j])]
            if len(nz) >= 3 and sum(abs(a - b) <= max(1.0, abs(a) * 0.01) for a, b in nz) >= 0.8 * len(nz):
                memo.append("다른 칸의 합인 칸 하나만 씀")
                return [j], memo
    return use, memo


def read_table3(g, transposed=False):
    """표 → (dict, "") 또는 (None, 사유). fin2_s31_audit.read_table + 칸 구조 찾기 + 업종 이름 수"""
    g = trim_periods(g)
    h, lab = split_header(g)
    if h >= len(g) - 2:
        return None, "본문 줄 부족"
    width = max(len(r) for r in g)
    heads = []
    for j in range(width):
        parts = []
        for r in g[:h]:
            t = r[j] if j < len(r) else ""
            if t and t not in parts:
                parts.append(t)
        heads.append(" ".join(parts))
    hc = [compact(x) for x in heads]
    body = []
    for r in g[h:]:
        name = " ".join(dict.fromkeys(c for c in r[:lab] if c)).strip()
        cn = compact(name)
        if re.match(r"^<?\(?(전기|전년|2024)", cn):
            break
        if re.match(r"^<?\(?(당기|당년|2025)", cn) and not any(is_num(c) for c in r[lab:]):
            continue
        body.append((name, cn, r))
    if len(body) < 3:
        return None, "본문 줄 부족"
    num_cols = [j for j in range(lab, width) if sum(is_num(r[j]) for _, _, r in body if j < len(r)) >= 2]
    if not num_cols:
        return None, "금액 열 없음"
    if any(CURR.search(hc[j]) for j in num_cols) and any(PREV.search(hc[j]) for j in num_cols):
        num_cols = [j for j in num_cols if not PREV.search(hc[j])]
    use = [j for j in num_cols if not COL_OFF.search(hc[j]) and not COL_SKIP.search(hc[j])]
    if any("총장부" in hc[j] for j in use):
        use = [j for j in use if not re.search(r"순장부|순액", hc[j])]
    basis = "장부 자산 열 합"
    if not any(hc[j] for j in num_cols):
        use, basis = num_cols, "머리글 없음"
    elif not use:
        tot = [j for j in num_cols if re.search(r"합계|총계|^계$", hc[j]) and not COL_OFF.search(hc[j])]
        use, basis = (tot[-1:], "합계 열 기준") if tot else (num_cols[:1], "첫 금액 열(확인)")
    use, memo = column_structure(body, use) if len(use) >= 2 else (use, [])
    if basis == "머리글 없음":
        basis = "머리글 없음 — 칸 구조로 판정" if memo else ("단일 금액 열" if len(use) == 1 else "머리글 없음(확인)")
    elif len(use) == 1 and basis == "장부 자산 열 합":
        basis = "단일 금액 열"
    mfg_rows = [(n, c, r) for n, c, r in body if MFG.search(c) and not TOTAL_ROW.match(c)]
    if not mfg_rows:
        if not transposed and any(MFG.search(x) for x in hc):
            info, why = read_table3(transpose(g), True)
            if info:
                info["basis"] += " (가로형 표)"
            return info, why
        return None, "제조업 줄 없음"
    tot_rows = [(n, c, r) for n, c, r in body if TOTAL_ROW.match(c)]
    data = [(n, c, r) for n, c, r in body if not TOTAL_ROW.match(c) and not SUBTOTAL_ROW.search(c)]
    vals = [val(r, use) for _, _, r in data]
    total = val(tot_rows[-1][2], use) if tot_rows else None
    parent = [False] * len(data)
    if total is None or abs(sum(vals) - total) > max(1.0, abs(total) * 0.01):
        for i, vi in enumerate(vals):                      # 줄의 합계 구조
            if vi <= 0:
                continue
            acc = 0.0
            for k in range(i + 1, min(len(vals), i + 40)):
                acc += vals[k]
                if k - i >= 2 and abs(acc - vi) <= max(1.0, vi * 0.005):
                    parent[i] = True
                    memo.append("상위 줄 제외")
                    break
                if acc > vi * 1.005 + 1:
                    break
    data_sum = sum(v for v, p in zip(vals, parent) if not p)
    total = data_sum if total is None else total
    is_par = {id(r): p for (_, _, r), p in zip(data, parent)}
    subs = [x for x in mfg_rows if SUBTOTAL_ROW.search(x[1])]
    mpar = [x for x in mfg_rows if is_par.get(id(x[2]))]
    pick = subs[:1] or mpar or mfg_rows
    ind = len(set(IND_WORDS.findall(" ".join(c for _, c, _ in body))))
    return dict(heads=" | ".join(heads[j] or "?" for j in use), basis=basis, mfg=sum(val(r, use) for _, _, r in pick),
                total=total, mfg_rows=" + ".join(n for n, _, _ in pick), has_total=bool(tot_rows),
                sum_ok=(abs(data_sum - total) <= max(1.0, abs(total) * 0.01)) if tot_rows else None,
                household=any(HOUSEHOLD.search(c) and "도소매" not in c for _, c, _ in body), memo=memo, ind=ind,
                loan=bool([j for j in use if COL_LOAN.search(hc[j])])), ""


def unit_of(x, p, region_units):
    m = list(UNIT.finditer(_plain(x[max(0, p - 3000):p])))
    if m:
        return m[-1].group(1), ""
    if region_units:
        return region_units.most_common(1)[0][0], "단위: 구역 기본값"
    return "", ""


def candidates3(spans, seen, region_units):
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
            first_col = compact(" ".join(r[0] for r in g if r))
            ind = max(len(set(IND_WORDS.findall(first_col))), len(set(IND_WORDS.findall(hc))))
            score = 3 if INDUSTRY_CTX.search(near + hc) else 0
            score += 2 if ind >= 3 else 0                       # G 내용 기반 업종표 판정
            score -= 2 if BAD_CTX.search(near) else 0
            score += 1 if CURR.search(compact(ctx[-150:]) + hc) else 0
            score -= 3 if PREV.search(compact(ctx[-120:]) + hc) and not CURR.search(compact(ctx[-120:]) + hc) else 0
            unit, unote = unit_of(x, p, region_units)
            out.append(dict(pos=p, ctx=ctx, grid=g, score=score, unit=unit, unote=unote, where=label, joined=joined))
    return out


def pick3(cands, thr):
    why = ""
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["score"] < thr:
            break
        info, w = read_table3(c["grid"])
        if info and info["total"]:
            return c, info, ""
        why = why or (w or "합계 0")
    return None, None, why or ("산업별 문맥·업종 이름 부족(점수 미달)" if cands else "")


def titled_ranges(x, s, e, pat):
    area = toc_area(x, s, e)
    ns, ne = (area[1], area[2]) if area else (s, e)
    chain = note_chain(x, max(s, ns - 300), ne)
    if len(chain) < 5:
        return [], area
    out = []
    for i, (k, t, p) in enumerate(chain):
        if pat.search(compact(t)[:18]):
            out.append((p, chain[i + 1][2] if i + 1 < len(chain) else ne, f"{k}. {t}"))
    return out, area


def classify3(where, info, share, ratio, mfg, unote, joined):
    """(분류, 사유, 메모) — 위치 신뢰도를 반영"""
    notes, review, caution = [], [], []
    trusted = where in TRUSTED
    if where == "사업의 내용":
        notes.append("출처: 사업의 내용")
    if where == "연결 주석":
        notes.append("연결 기준 표")
    if where == "문서 전체":
        review.append("표 위치: 주석 밖")
    if joined:
        notes.append("나뉜 표 붙임")
    notes += info["memo"]
    if unote:
        notes.append(unote)
    if mfg is None:
        review.append("단위 못 찾음")
    if "(확인)" in info["basis"]:
        review.append("열 판정 불확실")
    if share > 100 or share < 0:
        review.append("비중 범위 밖")
    elif share == 0:
        (notes if trusted else review).append("제조업 0" + (" (믿을 수 있는 위치 — 실측 0)" if trusted else ""))
    if ratio is not None:
        if ratio > 1.7:
            review.append(f"표 합계/총자산 {ratio:.2f}")
        elif ratio > 1.2:
            caution.append(f"표 합계/총자산 {ratio:.2f}")
        elif ratio < 0.05:
            (notes if trusted else review).append(f"기업 부문 표(표 합계/총자산 {ratio:.3f})" if trusted
                                                  else f"표 합계/총자산 {ratio:.3f}")
    if info["sum_ok"] is False:
        caution.append("검산①: 업종 줄 합 ≠ 합계")
    if review:
        return "검토", " · ".join(review), " · ".join(notes)
    return ("분자 채택" if caution else "성공"), " · ".join(caution), " · ".join(notes)


def dump(acc, cands, picked, info):
    DUMP.mkdir(parents=True, exist_ok=True)
    lines = [f"# {acc} — {info}"]
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])[:5], 1):
        mark = " ◀ 선택" if c is picked else ""
        lines += [f"\n## 후보 {i} (위치 {c['where']}, 점수 {c['score']}, 단위 {c['unit'] or '?'}"
                  f"{', 나뉜 표 붙임' if c['joined'] else ''}){mark}", f"[앞 문맥] …{c['ctx'][-200:]}"]
        lines += [" | ".join(r) for r in c["grid"][:45]]
    (DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}_v4.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    from dart_api import document_zip  # noqa: E402
    T = pd.read_csv(TODO2, dtype=str).fillna("")
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    li_of = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}
    go = T["fail_type"].isin(["검토", "표 없음", "표 못 읽음"]) & ~T["group"].isin(SKIP_GROUPS) & (T["rcept_no"] != "")
    print(f"3차 읽기 {int(go.sum())}곳 / 남은 {len(T)}곳 (보험·금융지주·원문 오류·보고서 없음은 그대로 넘김)", flush=True)
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
        seen, allc, picked, info, why, where = set(), [], None, None, "", ""
        for label, spans, thr in levels:
            cands = candidates3(spans, seen, units)
            allc += cands
            picked, info, w = pick3(cands, thr)
            why = why or w
            if picked:
                where = label
                break
        titles = " / ".join(t for _, _, t in rr + ar)[:80]
        dump(acc, allc, picked, f"{r.get('report_nm', '')} · {basis} · 주석: {titles or '못 찾음'}")
        print(f"  {acc} — {where or '실패'}", flush=True)
        if not picked:
            pat = (f"표 못 읽음 — {why}" if allc else
                   "업종표 없음 — 위험관리·자산 주석 있음" if (rr or ar) else "업종표 없음 — 주석 목차 못 찾음")
            todo.append(dict(r, fail_type="표 못 읽음" if allc else "표 없음", pattern=pat))
            continue
        ux = UNIT_X.get(picked["unit"])
        share = info["mfg"] / info["total"] * 100 if info["total"] else -1
        mfg = info["mfg"] * ux / 1e8 if ux else None
        ratio = (info["total"] * ux / 1e8) / (assets * 1e4) if (ux and assets) else None
        kind, why2, memo = classify3(where, info, share, ratio, mfg, picked["unote"], picked["joined"])
        base = dict(account=acc, group=grp, layer=r["layer"], sector=r["sector"], mfg_eok=round(mfg, 2) if mfg is not None else None,
                    assets_jo=assets, share_table=round(share, 3), total_to_assets=round(ratio, 4) if ratio else None,
                    col_basis=info["basis"], cols=info["heads"], mfg_rows=info["mfg_rows"], unit=picked["unit"],
                    location=where, notes_found=titles, rcept_no=rno, report_nm=r.get("report_nm", ""), audit_note=memo)
        if kind in ("성공", "분자 채택"):
            fixed.append(dict(base, share_assets=round(mfg / (assets * 1e4) * 100, 3) if assets else None,
                              check=kind, check_note=why2, value_basis="감사보고서(3차 읽기)"))
        else:
            todo.append(dict(r, mfg_eok=base["mfg_eok"], total_to_assets=base["total_to_assets"], fail_type="검토",
                             reason=why2, pattern=f"검토 — {why2}"))

    F3, T3 = pd.DataFrame(fixed), pd.DataFrame(todo)
    F3.to_csv(FIXED3, index=False, encoding="utf-8-sig")
    T3.to_csv(TODO3, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 300)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n이번 성공 {len(F3)}곳 → {FIXED3.relative_to(ROOT)} · 남은 {len(T3)}곳 → {TODO3.relative_to(ROOT)}")
    if len(F3):
        print("\n[1] 이번 성공 — 집단 × 표 위치")
        print(F3.pivot_table(index="group", columns="location", values="account", aggfunc="count", fill_value=0).to_string())
        print("\n[2] 이번 성공 목록")
        print(F3[["account", "group", "share_assets", "total_to_assets", "location", "check", "col_basis", "audit_note"]]
              .to_string(index=False))
    print("\n[3] 남은 실패 — 패턴별")
    if len(T3):
        p = T3["pattern"].fillna("").str.replace(r"(검토) — .*", r"\1", regex=True).str.replace(r"(원문 오류) .*", r"\1", regex=True)
        print(T3.assign(p=p).groupby(["p", "group"]).size().rename("곳").reset_index().to_string(index=False))
    chk = T3[T3["fail_type"] == "검토"] if len(T3) else T3
    if len(chk):
        print("\n[4] 검토 목록 (보험·금융지주 제외)")
        c2 = chk[~chk["group"].isin(SKIP_GROUPS)]
        print(c2[["account", "group", "mfg_eok", "total_to_assets", "reason"]].to_string(index=False) if len(c2) else "  없음")


if __name__ == "__main__":
    main()
