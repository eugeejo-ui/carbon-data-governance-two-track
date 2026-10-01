"""금융2-4 ③-1 감사보고서 — 산업별(업종별) 신용위험 표에서 제조업 비중 (FISIS로 안 되는 업권) · 2판

- 대상: 명단 278곳 − FISIS로 끝난 은행·저축은행(fin_s31_fisis.csv의 ok) − 공공금융기관(금융-1 조사 값 사용)
- 방법론 (2026-10-01 확정): OCR·LLM 없이 원문 XML 표 구조 그대로, 숫자는 항상 원문 칸에서만 읽음
  - 열(결정 A): 지급보증·약정·합계·비율·충당금 열을 뺀 장부 자산 열의 합. 없으면 합계 열
  - 분모(결정 B): 표 전체 합계(가계·개인 포함). 가계·개인 줄이 없으면 "기업만" → 확인
  - 제조업(결정 C): 제조업 줄이 여러 개면 합산, 소계·상위 줄이 있으면 그 값
  - 검증: ① 업종 줄 합 = 합계 ② 표 합계 ÷ 총자산 0.05~1.2 ③ 보험: 대출 열 제조업 ↔ FISIS(±10%)
- 2판 수정 (1차 실행 진단, 2026-10-01)
  - 고유번호가 비면(1-3A 층 전부) 이름 → 음역으로 DART 고유번호 목록에서 다시 찾음 (차입처 조사와 같은 방식)
  - 보고서: "[기재정정]" 허용, 결산월이 12월이 아닌 회사도 찾도록 2025-07부터
  - 줄 이름·머리글은 공백을 지운 뒤 비교 ("제 조 업", "합 계")
  - 업종이 머리글에 있는 가로형 표는 돌려서 다시 읽음
  - 합계 구조: 아래 줄들의 합과 같은 줄은 상위 줄로 보고 합계 계산에서 제외 (줄 합이 합계와 다를 때·합계 줄이 없을 때만)
  - 주석에서 못 찾으면 문서 전체에서 찾고 "주석 밖"으로 표시
  - 진단 기록: 고유번호 출처 · 찾은 공시 종류 · 제조 표/산업별 문구 출현 수 · 못 읽은 사유
  - FISIS 대조에서 0으로 나누던 오류 수정, 참고 칸 "제조업 ÷ 총자산"
- 수동 입력: data/manual/fin_s31_audit_manual.csv (account, action=set|none, mfg_eok, total_eok, basis, source, note)
- 출력: data/processed/fin_s31_audit.csv · 회사별 후보 표 data/processed/s31_audit_tables/*.txt
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_audit import _plain  # noqa: E402
from fin.fin1_list import key, name2  # noqa: E402
from fin.fin2_lenders import UNIT, UNIT_X, choose, files_of, to_num  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual" / "fin_s31_audit_manual.csv"
OUT = PROC / "fin_s31_audit.csv"
DUMP = PROC / "s31_audit_tables"
REPORT_FROM, REPORT_TO = "20250701", "20261231"

GROUP = {
    "카드·할부금융": "카드·캐피탈", "금융리스": "카드·캐피탈", "여신금융": "카드·캐피탈", "기타 여신금융": "카드·캐피탈",
    "생명보험": "생명보험", "손해보험": "손해보험", "보증보험": "손해보험", "재보험": "손해보험",
    "보험(확인 필요)": "손해보험", "증권": "증권", "선물": "증권", "신탁·집합투자": "자산운용·신탁",
    "금융지주": "금융지주", "은행": "은행", "은행·기타 예금기관": "은행", "저축은행·신협": "저축은행",
}
# 아래 정규식은 모두 공백을 지운 글자에 씀
INDUSTRY_CTX = re.compile(r"산업별|업종별|산업(구분|분류|집중|유형)|업종(구분|분류|집중)")
BAD_CTX = re.compile(r"연체|손상|대손|충당금|부도|등급별|만기|잔존|이자율|민감도|담보별|지역별|국가별")
MFG = re.compile(r"(?<!비)제조")
TOTAL_ROW = re.compile(r"^(합계|총계|계|총합계|전체|합계\(.*\))$")
SUBTOTAL_ROW = re.compile(r"소계")
HOUSEHOLD = re.compile(r"가계|개인|소매금융|리테일|소비자")
PREV = re.compile(r"전기|전년|2024")
CURR = re.compile(r"당기|당년|2025")
COL_OFF = re.compile(r"지급보증|보증|미사용|약정|한도|난외|확정")
COL_SKIP = re.compile(r"합계|총계|^계$|소계|비율|비중|구성비|%|충당금|대손|손상|조정|이연|할인|현재가치|담보")
COL_LOAN = re.compile(r"대출|여신")
NUM = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$")
PREFIX = re.compile(r"^\[[^\]]*\]\s*")                    # "[기재정정]" 등


def compact(s):
    return re.sub(r"\s+", "", str(s))


def grid(tb):
    """<TABLE> 하나 → 합쳐진 칸(COLSPAN·ROWSPAN)을 펼친 2차원 목록"""
    rows, pend = [], {}
    for tr in re.findall(r"<TR\b.*?</TR>", tb, flags=re.S | re.I):
        out = {}
        for c in list(pend):
            left, txt = pend[c]
            out[c] = txt
            if left <= 1:
                del pend[c]
            else:
                pend[c] = (left - 1, txt)
        col = 0
        for tag, attrs, inner in re.findall(r"<(T[DHEU])\b([^>]*)>(.*?)</\1>", tr, flags=re.S | re.I):
            while col in out:
                col += 1
            cs = re.search(r"COLSPAN\s*=\s*\"?(\d+)", attrs, re.I)
            rs = re.search(r"ROWSPAN\s*=\s*\"?(\d+)", attrs, re.I)
            cs, rs = (int(cs.group(1)) if cs else 1), (int(rs.group(1)) if rs else 1)
            txt = _plain(inner)
            for k in range(cs):
                out[col + k] = txt
                if rs > 1:
                    pend[col + k] = (rs - 1, txt)
            col += cs
        if out and any(v for v in out.values()):
            rows.append([out.get(i, "") for i in range(max(out) + 1)])
    return rows


def transpose(g):
    w = max(len(r) for r in g)
    p = [r + [""] * (w - len(r)) for r in g]
    return [[p[i][j] for i in range(len(p))] for j in range(w)]


def is_num(c):
    c = str(c).replace(" ", "")
    return bool(c) and bool(NUM.match(c))


def split_header(g):
    h = 0
    for r in g:
        if sum(is_num(c) or c.strip() in ("-", "–") for c in r[1:]) >= 1 and not CURR.search(compact(" ".join(r))):
            break
        h += 1
    lab = 1
    body = g[h:h + 5]
    if body and all(len(r) > 2 and not is_num(r[1]) and r[1].strip() not in ("-", "–", "") for r in body):
        lab = 2
    return h, lab


def read_table(g, transposed=False):
    """표 → (dict, "") 또는 (None, 못 읽은 사유)"""
    h, lab = split_header(g)
    if h >= len(g) - 2:
        return None, "본문 줄 부족"

    def val(r, cols):
        s = 0.0
        for j in cols:
            v = to_num(r[j]) if j < len(r) else None
            s += v or 0.0
        return s
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
        if len(num_cols) == 1:
            use, basis = num_cols, "단일 금액 열"
        else:
            last, others = num_cols[-1], num_cols[:-1]
            hit = sum(abs(val(r, [last]) - val(r, others)) <= max(1.0, abs(val(r, [last])) * 0.01) for _, _, r in body)
            use, basis = (others, "머리글 없음 — 마지막 열을 합계로 봄") if hit >= 0.8 * len(body) \
                else (num_cols[:1], "머리글 없음 — 첫 열(확인)")
    elif not use:
        tot = [j for j in num_cols if re.search(r"합계|총계|^계$", hc[j]) and not COL_OFF.search(hc[j])]
        use, basis = (tot[-1:], "합계 열 기준") if tot else (num_cols[:1], "첫 금액 열(확인)")
    elif len(use) == 1:
        basis = "단일 금액 열"

    mfg_rows = [(n, c, r) for n, c, r in body if MFG.search(c) and not TOTAL_ROW.match(c)]
    if not mfg_rows:
        if not transposed and any(MFG.search(x) for x in hc):        # 업종이 머리글에 있는 가로형 표
            info, why = read_table(transpose(g), True)
            if info:
                info["basis"] += " (가로형 표)"
            return info, (why if not info else "")
        return None, "제조업 줄 없음"
    tot_rows = [(n, c, r) for n, c, r in body if TOTAL_ROW.match(c)]
    data = [(n, c, r) for n, c, r in body if not TOTAL_ROW.match(c) and not SUBTOTAL_ROW.search(c)]
    vals = [val(r, use) for _, _, r in data]
    plain_sum = sum(vals)
    total = val(tot_rows[-1][2], use) if tot_rows else None
    parent = [False] * len(data)
    hier = False
    if total is None or abs(plain_sum - total) > max(1.0, abs(total) * 0.01):
        for i, vi in enumerate(vals):                       # 합계 구조 — 아래 줄들의 합과 같으면 상위 줄
            if vi <= 0:
                continue
            acc = 0.0
            for k in range(i + 1, min(len(vals), i + 40)):
                acc += vals[k]
                if k - i >= 2 and abs(acc - vi) <= max(1.0, vi * 0.005):
                    parent[i] = hier = True
                    break
                if acc > vi * 1.005 + 1:
                    break
    data_sum = sum(v for v, p in zip(vals, parent) if not p)
    if total is None:
        total = data_sum
    is_par = {id(r): p for (_, _, r), p in zip(data, parent)}
    subs = [x for x in mfg_rows if SUBTOTAL_ROW.search(x[1])]
    mpar = [x for x in mfg_rows if is_par.get(id(x[2]))]
    pick = subs[:1] or mpar or mfg_rows
    mfg = sum(val(r, use) for _, _, r in pick)
    loan_cols = [j for j in use if COL_LOAN.search(hc[j])]
    return dict(
        heads=" | ".join(heads[j] or "?" for j in use), basis=basis, mfg=mfg, total=total,
        mfg_rows=" + ".join(n for n, _, _ in pick), has_total=bool(tot_rows), hier=hier,
        household=any(HOUSEHOLD.search(c) and "도소매" not in c for _, c, _ in body),
        sum_ok=(abs(data_sum - total) <= max(1.0, abs(total) * 0.01)) if tot_rows else None,
        mfg_loan=(sum(val(r, loan_cols) for _, _, r in pick) if loan_cols else None), n_rows=len(body)), ""


def region(files, group_basis):
    """(본문, 시작, 끝, 기준) — 금융지주는 연결 주석, 나머지는 별도"""
    if group_basis:
        for n, x, dn in files:
            if dn == "연결감사보고서":
                return x, 0, len(x), "연결감사보고서"
        for n, x, dn in files:
            titles = [(m.start(), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip())
                      for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
            for i, (pos, t) in enumerate(titles):
                if re.match(r"^\d+\.\s*연결재무제표\s*주석$", t):
                    end = next((p for p, tt in titles[i + 1:] if re.match(r"^(\d+\.|[IVX]+\.)", tt)), len(x))
                    return x, pos, end, "사업보고서 연결 주석"
    return choose(files)


def candidates(x, s, e):
    out = []
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", x[s:e], flags=re.S | re.I):
        a = s + m.start()
        tb = m.group(0)
        if not MFG.search(compact(_plain(tb))):
            continue
        g = grid(tb)
        if len(g) < 4:
            continue
        ctx = _plain(x[max(s, a - 1500):a])[-400:]
        head_txt = " ".join(" ".join(r) for r in g[:3])
        near, hcmp = compact(ctx[-250:]), compact(head_txt)
        score = 3 if INDUSTRY_CTX.search(near + hcmp) else 0
        score -= 2 if BAD_CTX.search(near) else 0
        score += 1 if CURR.search(compact(ctx[-150:]) + hcmp) else 0
        score -= 3 if PREV.search(compact(ctx[-120:]) + hcmp) and not CURR.search(compact(ctx[-120:]) + hcmp) else 0
        unit = UNIT.search(ctx[-250:] + " " + head_txt)
        out.append(dict(pos=a, ctx=ctx, grid=g, score=score, unit=unit.group(1) if unit else ""))
    return out


def pick_table(cands):
    """점수 1 이상 후보를 차례로 읽음 → (후보, 정보, 첫 실패 사유)"""
    why = ""
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["score"] < 1:
            break
        info, w = read_table(c["grid"])
        if info and info["total"]:
            return c, info, ""
        why = why or (w or "합계 0")
    return None, None, why or ("산업별 문맥 없음" if cands else "")


def find_report(code, get_json):
    """(접수번호, 보고서명, 찾은 공시 종류) — 사업보고서 → 감사보고서 → 연결감사보고서, 최신"""
    rows = []
    for ty in ("A", "F"):
        d = get_json("list", corp_code=code, bgn_de=REPORT_FROM, end_de=REPORT_TO, pblntf_ty=ty, page_count="100")
        rows += [(ty, str(r.get("rcept_no", "")), str(r.get("report_nm", "")).strip()) for r in d.get("list", []) or []]
    kinds = sorted({re.sub(r"\s*\(.*", "", PREFIX.sub("", nm)) for _, _, nm in rows})
    for ty, pat in (("A", r"^사업보고서"), ("F", r"^감사보고서"), ("F", r"^연결감사보고서")):
        hit = [(rno, nm) for t, rno, nm in rows if t == ty and re.search(pat, PREFIX.sub("", nm))]
        if hit:
            rno, nm = max(hit)
            return rno, nm, kinds
    return "", "", kinds


def count_mfg_tables(x, s, e):
    n = 0
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", x[s:e], flags=re.S | re.I):
        if MFG.search(compact(_plain(m.group(0)))):
            n += 1
    return n


def dump(acc, cands, picked, info):
    DUMP.mkdir(parents=True, exist_ok=True)
    lines = [f"# {acc} — {info}"]
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])[:4], 1):
        mark = " ◀ 선택" if c is picked else ""
        lines += [f"\n## 후보 {i} (점수 {c['score']}, 단위 {c['unit'] or '?'}){mark}", f"[앞 문맥] …{c['ctx'][-200:]}"]
        lines += [" | ".join(r) for r in c["grid"][:45]]
    (DUMP / f"{re.sub(r'[^0-9A-Za-z가-힣]', '_', acc)[:40]}.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    from dart_api import corp_codes, document_zip, get_json  # noqa: E402
    L = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    F = pd.read_csv(PROC / "fin_s31_fisis.csv", dtype=str).fillna("") if (PROC / "fin_s31_fisis.csv").exists() else pd.DataFrame()
    done = {key(a) for a, g, s in zip(F.get("account", []), F.get("group", []), F.get("status", []))
            if g in ("은행", "저축은행") and s == "ok"}
    fis = {key(a): r for a, r in zip(F.get("account", []), F.to_dict("records"))} if len(F) else {}
    T = L[(L["layer"] != "공공금융기관") & ~L["account"].map(key).isin(done)].copy()
    man = pd.read_csv(MANUAL, dtype=str).fillna("") if MANUAL.exists() else pd.DataFrame(columns=["account", "action"])
    man_of = {key(a): r for a, r in zip(man["account"], man.to_dict("records"))}
    cc = corp_codes()
    by_k, by_n2 = {}, {}
    for c_, n_ in zip(cc["corp_code"], cc["corp_name"]):
        by_k.setdefault(key(n_), []).append(str(c_))
        by_n2.setdefault(name2(n_), []).append(str(c_))
    print(f"대상 {len(T)}곳 (명단 {len(L)} − FISIS 완료 {len(done)} − 공공금융기관 {int((L['layer'] == '공공금융기관').sum())}) "
          f"· 명단 고유번호 빈칸 {int((T['corp_code'] == '').sum())}곳", flush=True)
    out = []
    for i, r in enumerate(T.to_dict("records"), 1):
        acc, sec = r["account"], r["sector"]
        f = fis.get(key(acc), {})
        grp = {"H": "생명보험", "I": "손해보험"}.get(f.get("part", ""), GROUP.get(sec, "기타"))
        row = dict(account=acc, sector=sec, layer=r["layer"], group=grp, assets_jo=r.get("assets_jo", ""))
        mm = man_of.get(key(acc))
        if mm and mm.get("action") in ("set", "none"):
            row.update(status="수동", basis=mm.get("basis", ""), note=mm.get("note", ""), source=mm.get("source", ""))
            if mm["action"] == "set":
                row["mfg_eok"], row["total_eok"] = float(mm["mfg_eok"]), float(mm["total_eok"])
                row["share_total"] = round(row["mfg_eok"] / row["total_eok"] * 100, 2) if row["total_eok"] else None
            out.append(row)
            continue
        tries = [(r["corp_code"], "명단")] if r.get("corp_code") else []
        tries += [(c_, "이름") for c_ in by_k.get(key(acc), [])[:5]]
        tries += [(c_, "음역") for c_ in by_n2.get(name2(acc), [])[:5]]
        seen, rno, rnm, kinds, src = set(), "", "", [], "없음"
        for c_, how in tries:
            if c_ in seen:
                continue
            seen.add(c_)
            try:
                a_, b_, k_ = find_report(c_, get_json)
            except Exception as ex:  # noqa: BLE001 — 조회 오류 한 건으로 전체가 멈추지 않게
                a_, b_, k_ = "", "", [f"조회 오류 {type(ex).__name__}"]
            if not kinds:
                kinds = k_
            if a_:
                rno, rnm, kinds, src = a_, b_, k_, how + ("" if how == "명단" or not r.get("corp_code") else "(명단 번호에 보고서 없음)")
                break
        row.update(rcept_no=rno, report_nm=rnm, code_src=src if rno else ("고유번호 없음" if not tries else "보고서 없음"),
                   found_kinds=" · ".join(kinds[:6]))
        print(f"  [{i}/{len(T)}] {acc} — {rnm or '보고서 없음'}", flush=True)
        if not rno:
            row["status"] = "보고서 없음"
            out.append(row)
            continue
        try:
            files = files_of(document_zip(rno))
            x, s, e, basis = region(files, grp == "금융지주")
            cands = candidates(x, s, e)
            n_doc = sum(count_mfg_tables(xx, 0, len(xx)) for _, xx, _ in files)
            ind_note = len(INDUSTRY_CTX.findall(compact(_plain(x[s:e]))))
        except Exception as ex:  # noqa: BLE001
            row.update(status="원문 오류", note=str(ex)[:80])
            out.append(row)
            continue
        row.update(doc_basis=basis, n_cand=len(cands),
                   diag=f"주석 제조 표 {len(cands)} · 문서 전체 제조 표 {n_doc} · 주석 '산업별·업종별' {ind_note}")
        picked, info, why = pick_table(cands)
        outside = False
        if not picked and n_doc > len(cands):                 # 주석에서 못 찾으면 문서 전체에서
            allc = []
            for _, xx, _ in files:
                allc += [c for c in candidates(xx, 0, len(xx)) if not (xx is x and s <= c["pos"] < e)]
            p2, i2, w2 = pick_table(allc)
            if p2:
                picked, info, outside = p2, i2, True
                cands = cands + allc
            why = why or w2
        dump(acc, cands, picked, f"{rnm} · {basis} · {row['diag']}")
        if not picked:
            row["status"] = "표 없음" if not cands else "표 못 읽음"
            row["fail_reason"] = why or ("문서에 제조 표 없음" if n_doc == 0 else "")
            out.append(row)
            continue
        ux = UNIT_X.get(picked["unit"], None)
        row.update(unit=picked["unit"] or "?", cols=info["heads"], col_basis=info["basis"], mfg_rows=info["mfg_rows"],
                   household="Y" if info["household"] else "N", n_rows=info["n_rows"],
                   share_total=round(info["mfg"] / info["total"] * 100, 2))
        notes = []
        if ux:
            row["mfg_eok"], row["total_eok"] = round(info["mfg"] * ux / 1e8, 2), round(info["total"] * ux / 1e8, 2)
        if outside:
            notes.append("표 위치: 주석 밖")
        if info["hier"]:
            notes.append("합계 구조 적용(상위 줄 제외)")
        if info["sum_ok"] is False:
            notes.append("검산①: 업종 줄 합 ≠ 합계")
        if not info["has_total"]:
            notes.append("합계 줄 없음 — 줄 합을 합계로")
        if not info["household"]:
            notes.append("가계·개인 줄 없음(기업만)")
        if not (0 < row["share_total"] <= 100):
            notes.append("비중 범위 밖")
        try:
            assets = float(r.get("assets_jo") or 0) * 1e4
            if ux and assets:
                ratio = row["total_eok"] / assets
                row["total_to_assets"] = round(ratio, 3)
                row["share_assets"] = round(row["mfg_eok"] / assets * 100, 2)
                if not (0.05 <= ratio <= 1.2):
                    notes.append(f"검산②: 표 합계/총자산 {ratio:.2f}")
        except (ValueError, TypeError):
            pass
        if not ux:
            notes.append("단위 못 찾음 — 비중만")
        fm = f.get("mfg_eok", "")
        if grp in ("생명보험", "손해보험") and fm != "" and info["mfg_loan"] is not None and ux:
            ml, fv = info["mfg_loan"] * ux / 1e8, float(fm)
            row["fisis_mfg_eok"], row["audit_mfg_loan_eok"] = fv, round(ml, 2)
            if fv < 1 and ml < 10:
                notes.append("검산③: FISIS 일치(둘 다 거의 0)")
            elif fv < 1:
                notes.append("검산③: FISIS 차이(FISIS 0)")
            else:
                gap = abs(ml - fv) / fv
                notes.append("검산③: FISIS 일치" if gap <= 0.10 else f"검산③: FISIS 차이 {gap * 100:.0f}%")
        if "(확인)" in info["basis"]:
            notes.append("열 판정 불확실")
        hard = ("검산①", "검산②", "비중", "검산③: FISIS 차이", "가계·개인 줄 없음", "열 판정", "표 위치")
        row["note"] = " · ".join(notes)
        row["status"] = "ok" if not [n for n in notes if n.startswith(hard)] else "확인"
        out.append(row)

    cols = ["account", "sector", "layer", "group", "status", "share_total", "share_assets", "mfg_eok", "total_eok",
            "assets_jo", "total_to_assets", "col_basis", "cols", "mfg_rows", "household", "unit", "n_rows",
            "fisis_mfg_eok", "audit_mfg_loan_eok", "doc_basis", "n_cand", "diag", "fail_reason", "code_src",
            "found_kinds", "rcept_no", "report_nm", "source", "note"]
    D = pd.DataFrame(out).reindex(columns=cols)
    D.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 400)
    pd.set_option("display.max_colwidth", 70)
    print(f"\n→ {OUT.relative_to(ROOT)} · 후보 표 {DUMP.relative_to(ROOT)}/")
    print("\n[1] 비교 집단 × 결과")
    print(D.pivot_table(index="group", columns="status", values="account", aggfunc="count", fill_value=0).to_string())
    print("\n[2] 고유번호 출처")
    print(D["code_src"].value_counts().to_string())
    ok = D[D["status"].isin(["ok", "확인", "수동"]) & D["share_total"].notna()]
    print("\n[3] 열 판정 방식")
    print(ok["col_basis"].value_counts().to_string())
    print("\n[4] 비중 분포 (표를 읽은 곳, %)")
    if len(ok):
        print(ok.groupby("group")["share_total"].describe()[["count", "min", "25%", "50%", "75%", "max"]].round(1).to_string())
    print("\n[5] 확인 사유별 곳 수")
    reasons = D["note"].dropna().str.split(" · ").explode()
    print(reasons[reasons != ""].str.replace(r"\s[\d.]+%?$|[\d.]+$", "", regex=True).value_counts().to_string())
    print("\n[6] 보험 FISIS 대조")
    ins = D[D["fisis_mfg_eok"].notna()]
    print(ins[["account", "fisis_mfg_eok", "audit_mfg_loan_eok", "note"]].to_string(index=False) if len(ins) else "  (대조한 곳 없음)")
    print("\n[7] 못 찾은 원인")
    nf = D[D["status"].isin(["표 없음", "표 못 읽음"])]
    print(nf["fail_reason"].fillna("").replace("", "(사유 없음)").value_counts().to_string())
    print("\n[8] 보고서 없음 — 찾은 공시 종류")
    nr = D[D["status"] == "보고서 없음"]
    print(nr["code_src"].value_counts().to_string())
    print(nr["found_kinds"].fillna("").replace("", "(2025-07 이후 공시 없음)").value_counts().head(10).to_string())
    print("\n[9] 확인할 계정 (상위 40)")
    chk = D[D["status"] == "확인"]
    print(chk[["account", "group", "share_total", "share_assets", "col_basis", "note"]].head(40).to_string(index=False)
          if len(chk) else "  없음")
    for st in ("표 없음", "표 못 읽음", "보고서 없음", "원문 오류"):
        x = D[D["status"] == st]
        if len(x):
            print(f"\n[{st}] {len(x)}곳: " + ", ".join(x["account"]))


if __name__ == "__main__":
    main()
