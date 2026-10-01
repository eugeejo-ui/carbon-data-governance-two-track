"""금융2-4 ③-1 ④ 합치기와 점수 — 제조업 노출 비중, 3등분

- 입력 (같은 회사가 여러 곳에 있으면 아래쪽 우선)
  FISIS(은행·저축은행·보험) · 공공금융기관(data/manual/fin_public_institutions.csv) · 채움분 fin_s31_fill.csv ·
  다시 읽기 고정분 fin_s31_audit_fixed2.csv · 3~5차 읽기 고정분 fin_s31_audit_fixed3·4·5.csv ·
  감사보고서 고정분 fin_s31_audit_fixed.csv · 수동 입력 data/manual/fin_s31_audit_manual.csv
- 비중: 제조업 노출(억 원) ÷ 총자산(명단 assets_jo, 조 → 억) × 100 (2026-10-01 분모 통일)
  감사보고서 표의 합계가 총자산보다 크면(카드 미사용 한도·칸 중복) 분모 = 표 합계 — 총자산과 표 합계 중 큰 쪽
- 업권별 결정 (2026-10-01 확정)
  ① 공공금융기관: 금융-1 조사 "보유액 대비 제조업 비중"을 그대로 씀 (보증·보험 잔액이 총자산을 넘어 총자산 대비는 100% 초과)
     → 3등분 선 계산에서 제외, 점수만 그 선으로
  ② 보험사: 전부 FISIS 업종별 대출(대출만)로 통일 — 감사보고서 값은 참고 칸 ref_audit_share
     → 선 계산에서 제외(대출만이라 잣대가 다름). 한계: 채권 투자 노출 미포함으로 과소
  ③ 금융지주: 표를 읽지 않고 자회사 실측 제조업 노출 합 ÷ 연결 총자산 (실측 안 된 자회사는 빠지므로 하한)
     연결 총자산이 아닌 지주(1-3A 농협금융지주 — 명단 값은 공정위 별도)는 FISIS 금융지주 연결 재무상태표(SL003 A)에서 받음
- 추정: 값이 없는 회사는 같은 비교 집단의 실측 가운데 값(실측 3곳 이상), 아니면 "자료 없음" 0점. "기타" 집단은 추정 안 함
- 점수: 선 계산 대상(공공·보험 제외) 실측 값으로 3등분(큰 순 위 1/3 → 2점, 가운데 1/3 → 1점, 나머지 0점)
        → 총자산 2조 미만 최대 1점 · 추정 최대 1점 · 자료 없음 0점
- 출력: data/processed/fin_s31.csv
"""
from pathlib import Path
import math
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402
from fin.fin2_s31_audit import GROUP  # noqa: E402
from fin.fin2_s31_freeze import fnum  # noqa: E402

PROC = ROOT / "data" / "processed"
MAN = ROOT / "data" / "manual"
OUT = PROC / "fin_s31.csv"
CAP_ASSETS_JO = 2.0
MIN_PEERS = 3
NO_ESTIMATE = {"기타"}
OUT_OF_CUT = {"공공", "생명보험", "손해보험"}           # ①·② 선 계산 제외
INSURER = {"생명보험", "손해보험"}


def read(p):
    return pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame()


def group_assets_fisis(account):
    """FISIS 금융지주 연결 자산총계(조) — 명단 값이 연결이 아닌 지주용"""
    try:
        from fin.fin1_indep import asset_of  # noqa: E402
        C = read(PROC / "fisis" / "companies.csv")
        hit = C[(C["part"] == "L") & (C["finance_nm"].map(key) == key(account))]
        if hit.empty:
            hit = C[(C["part"] == "L") & C["finance_nm"].map(key).str.contains(key(account).replace("(주)", ""), regex=False)]
        if hit.empty:
            return None, "FISIS 금융지주 목록에 없음"
        v, unit, st = asset_of(hit["finance_cd"].iloc[0], "SL003", "A")
        return (v, "FISIS SL003 연결") if st == "ok" else (None, f"FISIS 조회 {st}")
    except Exception as ex:  # noqa: BLE001
        return None, f"FISIS 조회 오류 {type(ex).__name__}"


def main():
    L = read(PROC / "fin_list.csv")
    F = read(PROC / "fin_s31_fisis.csv")
    layers = [(read(PROC / "fin_s31_fill.csv"), "채움"), (read(PROC / "fin_s31_audit_fixed5.csv"), "5차 읽기"),
              (read(PROC / "fin_s31_audit_fixed4.csv"), "4차 읽기"),
              (read(PROC / "fin_s31_audit_fixed3.csv"), "3차 읽기"),
              (read(PROC / "fin_s31_audit_fixed2.csv"), "다시 읽기"), (read(PROC / "fin_s31_audit_fixed.csv"), "고정")]
    RV = read(PROC / "fin_s31_review.csv")
    M = read(MAN / "fin_s31_audit_manual.csv")
    P = read(MAN / "fin_public_institutions.csv")
    fis = {key(a): r for a, r in zip(F.get("account", []), F.to_dict("records"))} if len(F) else {}
    review = {key(a) for a in RV.get("account", [])}
    li = {key(a): r for a, r in zip(L["account"], L.to_dict("records"))}

    def group_of(r):
        f = fis.get(key(r["account"]), {})
        if r["layer"] == "공공금융기관":
            return "공공"
        if f.get("group") in ("은행", "저축은행"):
            return f["group"]
        return {"H": "생명보험", "I": "손해보험"}.get(f.get("part", ""), GROUP.get(r["sector"], "기타"))
    grp = {key(a): group_of(r) for a, r in zip(L["account"], L.to_dict("records"))}

    # 1) 값 모으기 — key → dict(mfg, basis, source, check, share_override)
    val, ref_audit = {}, {}
    for k, r in fis.items():
        if grp.get(k) in ("은행", "저축은행") and r.get("status") == "ok" and fnum(r.get("mfg_eok")) is not None:
            val[k] = dict(mfg=float(r["mfg_eok"]), basis="FISIS",
                          source="FISIS 2025-12 " + ("SA044 A2" if r["group"] == "은행" else "SE036 A1"))
    for D, tag in layers:
        for _, r in D.iterrows():
            k, m = key(r["account"]), fnum(r.get("mfg_eok"))
            if m is None:
                continue
            if grp.get(k) in INSURER and not str(r.get("value_basis", "")).startswith("FISIS"):
                a = fnum(li.get(k, {}).get("assets_jo"))
                ref_audit[k] = round(m / (a * 1e4) * 100, 3) if a else None      # ② 감사보고서 값은 참고만
                continue
            note = ""                                       # 분모 = 총자산과 표 합계 중 큰 쪽 (2026-10-01)
            if fnum(r.get("mfg_eok_raw")) is None:          # 4차 고정분은 이미 반영돼 있음
                a = fnum(li.get(k, {}).get("assets_jo"))
                ratio, st = fnum(r.get("total_to_assets")), fnum(r.get("share_table"))
                if ratio is None and st and st > 0 and a:
                    ratio = (m * 100 / st) / (a * 1e4)
                if ratio and ratio > 1.0:
                    note, m = f"분모 = 표 합계(총자산의 {ratio:.2f}배)", m / ratio
            val[k] = dict(mfg=m, basis=r.get("value_basis", tag), source=r.get("source", "") or r.get("report_nm", ""),
                          check=" · ".join(x for x in (r.get("check", ""), note, r.get("audit_note", "")) if x))
    for k, r in fis.items():                            # ② 보험은 FISIS로 통일
        if grp.get(k) in INSURER and r.get("mfg_eok", "") != "":
            val[k] = dict(mfg=float(r["mfg_eok"]), basis="FISIS 업종별 대출(대출만)",
                          source="FISIS 2025-12 " + ("SH122 B" if grp[k] == "생명보험" else "SI122 B"))
    for _, r in P.iterrows():                           # ① 공공 — 보유액 대비 제조업 비중
        h, pct = fnum(r.get("holding_jo")), fnum(r.get("mfg_ratio_pct"))
        if h is not None and pct is not None:
            val[key(r["account"])] = dict(mfg=h * 1e4 * pct / 100, basis="공공(금융-1 조사)", share=pct,
                                          source=f"보유액 {h}조 × 제조업 {pct}% ({r.get('mfg_ratio_type', '')}) — 보유액 대비")
    for _, r in M.iterrows():                           # 수동 입력 최우선
        k = key(r["account"])
        if r.get("action") == "set" and fnum(r.get("mfg_eok")) is not None:
            val[k] = dict(mfg=float(r["mfg_eok"]), basis="수동 입력", source=r.get("source", ""), check=r.get("note", ""))
        elif r.get("action") == "none":
            val[k] = dict(mfg=0.0, basis="수동 입력(노출 없음)", source=r.get("source", ""), check=r.get("note", ""))

    # 2) ③ 금융지주 — 자회사 실측 합
    parent = {key(a): key(p) for a, p in zip(L["account"], L.get("parent", [""] * len(L))) if p}
    hold = [k for k, g in grp.items() if g == "금융지주"]
    gname = {key(a): g for a, g in zip(L["account"], L.get("group", [""] * len(L)))}

    def top_holding(k):
        seen = set()
        while k in parent and k not in seen:
            seen.add(k)
            k = parent[k]
            if k in hold:
                return k
        return None
    subs = {h: [] for h in hold}
    for k in grp:
        if k in hold:
            continue
        h = top_holding(k)
        if h is None and li.get(k, {}).get("layer") == "비상장 비종속(대기업집단)":      # 1-3A — 같은 기업집단 지주
            h = next((x for x in hold if gname.get(x) and gname.get(x) == gname.get(k)), None)
        if h:
            subs[h].append(k)
    hold_note = {}
    for h in hold:
        if h in val and val[h]["basis"].startswith("수동"):
            continue
        meas = [(k, val[k]["mfg"]) for k in subs[h] if k in val]
        a_basis = li.get(h, {}).get("assets_basis", "")
        a = fnum(li.get(h, {}).get("assets_jo"))
        a_src = f"명단({a_basis})"
        if "연결" not in a_basis:
            v, why = group_assets_fisis(li.get(h, {}).get("account", ""))
            if v:
                a, a_src = v, why
            else:
                a_src = f"명단({a_basis}) — 연결 총자산 못 받음: {why}"
        if meas:
            val[h] = dict(mfg=sum(m for _, m in meas), basis="자회사 합산(하한)", assets_override=a,
                          source=f"자회사 {len(meas)}/{len(subs[h])}곳: " + ", ".join(li[k]["account"] for k, _ in meas)[:150],
                          check=f"분모 {a_src}")
        else:
            val.pop(h, None)
        hold_note[h] = f"자회사 {len(subs[h])}곳 중 실측 {len(meas)}곳 · 분모 {a_src}"

    # 3) 회사별 비중
    rows = []
    for _, r in L.iterrows():
        k = key(r["account"])
        g = grp[k]
        a = fnum(r.get("assets_jo"))
        row = dict(account=r["account"], layer=r["layer"], sector=r["sector"], group=g, assets_jo=a,
                   in_cut=g not in OUT_OF_CUT, ref_audit_share=ref_audit.get(k),
                   share_loans_ref=fnum(fis.get(k, {}).get("share_total")) if g in ("은행", "저축은행") else None,
                   hold_note=hold_note.get(k, ""))
        v = val.get(k)
        den = v.get("assets_override", a) if v else a
        if v and (v.get("share") is not None or den):
            share = v["share"] if v.get("share") is not None else v["mfg"] / (den * 1e4) * 100
            row.update(mfg_eok=round(v["mfg"], 2), share=round(share, 3), share_basis="보유액 대비" if v.get("share") is not None
                       else ("연결 총자산 대비" if g == "금융지주" else "총자산 대비"),
                       value_basis=v["basis"], source=v.get("source", ""), check=v.get("check", ""), measured=True)
        else:
            row.update(value_basis="검토 대기" if k in review else ("총자산 없음" if not a else "값 없음"), measured=False)
        rows.append(row)
    D = pd.DataFrame(rows)

    # 4) 3등분 선 — 선 계산 대상 실측만
    cut_vals = sorted(D[D["measured"] & D["in_cut"]]["share"].dropna().tolist(), reverse=True)
    n = len(cut_vals)
    kk = math.ceil(n / 3) if n else 0
    hi, lo = (cut_vals[kk - 1], cut_vals[min(2 * kk, n) - 1]) if n else (float("inf"), float("inf"))

    def tier(v):
        return 2 if v >= hi else (1 if v >= lo else 0)
    med = D[D["measured"]].groupby("group")["share"].agg(["median", "count"])
    out = []
    for r in D.to_dict("records"):
        caps = []
        if r["measured"]:
            s = tier(r["share"])
        else:
            g = r["group"]
            if g in med.index and med.at[g, "count"] >= MIN_PEERS and g not in NO_ESTIMATE:
                r["share"] = round(float(med.at[g, "median"]), 3)
                r["value_basis"] = f"추정({r['value_basis']}) — {g} 실측 {int(med.at[g, 'count'])}곳 가운데 값"
                s = min(tier(r["share"]), 1)
                caps.append("추정 최대 1점")
            else:
                r["value_basis"] = f"자료 없음({r['value_basis']})"
                s = 0
        if r.get("assets_jo") is not None and r["assets_jo"] < CAP_ASSETS_JO and s > 1:
            s = 1
            caps.append("총자산 2조 미만 최대 1점")
        r.update(s31=s, cap=" · ".join(caps), cut_2pt=hi, cut_1pt=lo)
        out.append(r)
    R = pd.DataFrame(out)
    cols = ["account", "layer", "sector", "group", "assets_jo", "mfg_eok", "share", "share_basis", "s31", "cap",
            "value_basis", "source", "check", "in_cut", "hold_note", "ref_audit_share", "share_loans_ref", "cut_2pt", "cut_1pt"]
    R = R.reindex(columns=cols).sort_values(["s31", "share"], ascending=False)
    R.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 300)
    pd.set_option("display.max_colwidth", 60)
    print(f"명단 {len(R)}곳 → {OUT.relative_to(ROOT)}")
    print(f"\n[1] 3등분 선 (선 계산 대상 실측 {n}곳 — 공공·보험 제외): 2점 ≥ {hi:.3f}% · 1점 ≥ {lo:.3f}%")
    R["_vb"] = R["value_basis"].str.replace(r"\(.*", "", regex=True).str.replace(r" —.*", "", regex=True)
    print("\n[2] 집단 × 값 종류")
    print(R.pivot_table(index="group", columns="_vb", values="account", aggfunc="count", fill_value=0).to_string())
    print("\n[3] 집단 × 점수")
    print(R.pivot_table(index="group", columns="s31", values="account", aggfunc="count", fill_value=0).to_string())
    print("\n[4] 점수 분포: " + " · ".join(f"{s}점 {int((R['s31'] == s).sum())}곳" for s in (2, 1, 0)))
    print("\n[5] 집단별 실측 가운데 값 (%) — 추정에 씀")
    print(med.round(3).to_string())
    print("\n[6] 금융지주 — 자회사 합산")
    hd = R[R["group"] == "금융지주"]
    print(hd[["account", "mfg_eok", "share", "s31", "hold_note"]].to_string(index=False))
    print("\n[7] 실측 상위 25 (선 계산 대상)")
    print(R[~R["value_basis"].str.startswith(("추정", "자료 없음")) & R["in_cut"]]
          .head(25)[["account", "group", "assets_jo", "mfg_eok", "share", "s31", "cap", "value_basis"]].to_string(index=False))
    adj = R[R["check"].fillna("").str.contains("분모 = 표 합계")]
    print(f"\n[9] 분모 = 표 합계로 바꾼 곳 {len(adj)}곳")
    if len(adj):
        print(adj[["account", "group", "mfg_eok", "share", "s31", "check"]].to_string(index=False))
    print("\n[8] 보험 — FISIS 대출 기준과 감사보고서 참고값")
    ins = R[R["group"].isin(INSURER)]
    print(ins[["account", "group", "share", "s31", "ref_audit_share", "value_basis"]].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
