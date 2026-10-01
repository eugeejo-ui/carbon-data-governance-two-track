"""금융2-4 ③-2 고탄소 노출 (차주 기준) — 배출권거래제 할당대상업체의 차입처 시험 조사

- 바꾼 이유 (2026-10-01 사용자 제안): 금융회사가 탄소 데이터를 필요로 하는 이유는 CBAM만이 아니라 대출해 준 회사
  전체의 배출량(금융배출량)이므로, ③-2를 "한국은행 업권 비중 추정" 대신 할당대상업체를 차주 단위로 실제 측정
  ③-3(CBAM 연결 — 제조 94곳)은 그대로 둠
- 명단: data/raw/배출권거래제 할당대상업체 현황_260101기준.xlsx (772곳 — 업체명·KSIC만 있고 법인등록번호·배출량 없음)
  - 지자체·대학·병원·정부기관은 뺌. "○○공사·공단" 공기업(발전 자회사 등)은 차입이 있을 수 있어 넣음
  - 제조 94곳과 겹치는 회사는 제조-2 조사 결과가 있으므로 표시만 하고 새로 조사하지 않음
- DART 고유번호: 이름(법인 표기 제거 → 음역)으로 후보를 찾고, 회사개황 업종코드 앞 2자리가 명단 KSIC와 같은지 확인
  (명단에 법인등록번호가 없어 같은 이름 다른 회사를 고를 위험 — 업종이 다르면 "확인 필요")
- 시험 60곳: 업종별 정해진 수를 무작위(고정 시드)로 뽑음 — 결과를 보고 고르지 않도록
  발전·에너지 10 · 화학 10 · 전자·반도체 10 · 폐기물 8 · 운수·항공 8 · 제지 8 · 정유 6
- 차입처 조사는 fin2_lenders.run을 그대로 씀 (제조 결과 파일은 건드리지 않음)

실행
  python src/fin/fin2_ets.py --batch 1  사전할당량 누적 85%까지 (1차, 약 62곳) — 2026-10-01 결정
  python src/fin/fin2_ets.py --batch 2  85~90% (2차, 약 44곳)
  python src/fin/fin2_ets.py --pilot    시험 60곳 (업종별 무작위)
  python src/fin/fin2_ets.py --all      매칭된 전체

출력
  data/processed/fin_ets_targets.csv          할당대상 기업 전체 — 업종 묶음·제조 94곳 겹침·DART 매칭
  data/processed/fin_ets_lenders_pilot.csv    시험 60곳 차입처별 금액 (--all이면 fin_ets_lenders.csv)
  data/processed/fin_ets_lender_check_pilot.csv  검산
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key, name2  # noqa: E402
import fin.fin2_lenders as LND  # noqa: E402

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
ETS = RAW / "배출권거래제 할당대상업체 현황_260101기준.xlsx"
OUT_T = PROC / "fin_ets_targets.csv"
COVER = {"1": 0.85, "2": 0.90}     # 2026-10-01 결정 — 사전할당량 누적 90%까지, 1차 85%(62곳)·2차 90%(44곳)
SEED = 20261001
QUOTA = {"발전·에너지": 10, "화학": 10, "전자·반도체": 10, "폐기물": 8, "운수·항공": 8, "제지": 8, "정유": 6}
PUBLIC = re.compile(r"(특별시|광역시|특별자치|[시군구])$|^(경기|강원|충청|전라|경상|제주|서울|부산|대구|인천|광주|대전|울산|세종)"
                    r"(도|특별|광역)?.*[시군구도]$|청$|대학교|대학$|병원|의료원|교육청|군청|국방|육군|해군|공군|부대$|재단$")


def group(ksic):
    k = str(ksic)[:2]
    k = int(k) if k.isdigit() else -1
    return {35: "발전·에너지", 20: "화학", 26: "전자·반도체", 38: "폐기물", 49: "운수·항공", 50: "운수·항공", 51: "운수·항공",
            17: "제지", 19: "정유", 24: "철강·금속", 23: "시멘트·비금속", 30: "자동차", 10: "식품", 22: "고무·플라스틱",
            21: "의약", 25: "금속가공", 29: "기계", 13: "섬유", 36: "수도", 41: "건설", 42: "건설"}.get(
        k, "기타 제조" if 10 <= k <= 33 else "기타 비제조")


def load_ets():
    raw = pd.read_excel(ETS, header=None, dtype=str).fillna("")
    hdr = next(i for i in range(min(15, len(raw))) if "업체명" in "".join(raw.iloc[i]))
    d = pd.read_excel(ETS, header=hdr, dtype=str).fillna("")
    d.columns = [re.sub(r"\s", "", str(c)) for c in d.columns]
    d = d[d["업체명"].str.strip() != ""].copy()
    d["account"] = d["업체명"].str.strip()
    d["ksic"] = d.get("KSIC코드", "")
    d["group"] = d["ksic"].map(group)
    # 이름에 회사 표시((주)·주식회사·(유))가 있으면 공공기관이 아님 — "리뉴에너지충청(주)"·"롯데엠시시 주식회사" 오분류 방지
    corp = d["account"].str.contains(r"\(주\)|㈜|주식회사|\(유\)|유한회사")
    d["public"] = ~corp & d["account"].map(lambda n: bool(PUBLIC.search(re.sub(r"\s", "", n))))
    return d


LETTER = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                  ["에이", "비", "씨", "디", "이", "에프", "지", "에이치", "아이", "제이", "케이", "엘", "엠", "엔", "오", "피", "큐", "알",
                   "에스", "티", "유", "브이", "더블유", "엑스", "와이", "지"]))


def translit(n):
    """영문 약자를 한글 음역으로 — "HS효성첨단소재" ↔ "에이치에스효성첨단소재", "무림P&P" ↔ "무림피앤피" (시험 60곳 중 DART 못 찾은 곳)"""
    n = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\s|[.,·-]", "", str(n)).upper().replace("&", "앤")
    return re.sub(r"[A-Z]", lambda m: LETTER[m.group(0)], n)


def match_dart(d, cc, get_json, only=None):
    """이름으로 후보 → 업종코드 앞 2자리 확인. only가 주어지면 그 회사들만 회사개황을 조회(시험 표본)"""
    by_key, by_n2, by_tr = {}, {}, {}
    listed = {c for c, sc in zip(cc["corp_code"], cc.get("stock_code", [""] * len(cc))) if str(sc).strip()}
    for c, n in zip(cc["corp_code"], cc["corp_name"]):
        by_key.setdefault(key(n), []).append(c)
        by_n2.setdefault(name2(n), []).append(c)
        by_tr.setdefault(translit(n), []).append(c)
    codes, status = [], []
    for r in d.to_dict("records"):
        cands = by_key.get(key(r["account"])) or by_n2.get(name2(r["account"])) or by_tr.get(translit(r["account"])) or []
        if not cands:
            codes.append(""), status.append("DART 이름 못 찾음")
            continue
        if only is not None and r["account"] not in only:
            codes.append(cands[0] if len(cands) == 1 else ""), status.append(f"이름 후보 {len(cands)}개")
            continue
        pick, why = "", "업종 불일치 — 확인 필요"
        for c in cands[:6]:
            try:
                info = get_json("company", corp_code=c)
            except Exception:  # noqa: BLE001
                continue
            if info.get("status") == "000" and str(info.get("induty_code", ""))[:2] == str(r["ksic"])[:2]:
                pick, why = c, "이름+업종 일치"
                break
        if not pick and len(cands) == 1:
            pick = cands[0]
        if not pick:                                   # 같은 이름 법인이 여럿이고 업종으로 못 가림 (한화솔루션 — 과거 법인 포함)
            lc = [c for c in cands if c in listed]
            if len(lc) == 1:
                pick, why = lc[0], "이름 일치(상장사 우선)"     # 상장 코드는 하나뿐
            else:
                for c in cands[:6]:                    # 2026년에 보고서를 낸 후보
                    try:
                        if LND.report_for(c, get_json)[0]:
                            pick, why = c, "이름 일치(2026년 보고서 있는 법인)"
                            break
                    except Exception:  # noqa: BLE001
                        continue
        codes.append(pick), status.append(why if pick else "이름 후보는 있으나 확정 못 함")
    d = d.copy()
    d["corp_code"], d["match"] = codes, status
    return d


def load_alloc():
    """data/raw/*사전할당*.csv — 4차 계획기간 업체별 사전할당량 (2026년 값을 회사 규모로 씀)"""
    files = sorted(RAW.glob("*사전할당*.csv"))
    if not files:
        raise SystemExit("data/raw에 사전할당량 CSV(이름에 '사전할당')가 없습니다")
    raw = files[-1].read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    from io import StringIO
    a = pd.read_csv(StringIO(txt), dtype=str).fillna("")
    a.columns = [c.strip('"') for c in a.columns]
    a["t2026"] = pd.to_numeric(a["2026년"].str.replace(",", ""), errors="coerce").fillna(0)
    look = {}
    for n, t in zip(a["업체명"], a["t2026"]):
        for k in (key(n), name2(n), translit(n)):
            look.setdefault(k, t)
    return look, files[-1].name


def rank_by_alloc(firms):
    """할당량 순위·누적 덮는 비율 (분모 = 기업 전체 할당량, 제조 94곳 몫 포함)"""
    look, fname = load_alloc()
    f = firms.copy()
    f["t2026"] = f["account"].map(lambda n: look.get(key(n), look.get(name2(n), look.get(translit(n)))))
    tot = f["t2026"].sum()
    base = f.loc[f["in_mfg94"], "t2026"].sum() / tot
    g = f[~f["in_mfg94"] & f["t2026"].notna()].sort_values("t2026", ascending=False).copy()
    g["cum"] = base + g["t2026"].cumsum() / tot
    g["batch"] = ""
    for b, cv in COVER.items():
        n_to = int((g["cum"] < cv).sum()) + 1                 # 누적이 기준을 처음 넘는 회사까지
        idx = g.index[:n_to]
        g.loc[[i for i in idx if g.at[i, "batch"] == ""], "batch"] = b
    print(f"사전할당량 {fname} — 기업 할당량 중 제조 94곳 겹침 몫 {base * 100:.1f}% · 할당량 못 찾음 {int(f['t2026'].isna().sum())}곳")
    for b, cv in COVER.items():
        gb = g[g["batch"] == b]
        print(f"  {b}차: {len(gb)}곳 → 누적 {gb['cum'].max() * 100:.1f}% (기준 {int(cv * 100)}%)")
    return g


def main(argv):
    from dart_api import corp_codes, get_json  # noqa: E402
    full = "--all" in argv
    batch = next((argv[i + 1] for i, a in enumerate(argv) if a == "--batch" and i + 1 < len(argv)), "")
    d = load_ets()
    mfg = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    mk = {key(a) for a in mfg["account"]}
    d["in_mfg94"] = d["account"].map(lambda a: key(a) in mk)
    firms = d[~d["public"]].copy()
    print(f"할당대상 {len(d)}곳 — 지자체·대학·병원 등 {int(d['public'].sum())} · 기업 {len(firms)} "
          f"(제조 94곳과 겹침 {int(firms['in_mfg94'].sum())})", flush=True)
    cc = corp_codes()
    pool = firms[~firms["in_mfg94"]]
    if batch:                                          # 할당량 순 1차(85%)·2차(90%) — 2026-10-01 결정
        g = rank_by_alloc(firms)
        target_names = set(g.loc[g["batch"] == batch, "account"])
    elif full:
        target_names = set(pool["account"])
    else:                                              # 업종별 정해진 수를 무작위로 (고정 시드)
        picks = []
        for g, k in QUOTA.items():
            gp = pool[pool["group"] == g]
            picks.append(gp.sample(n=min(k, len(gp)), random_state=SEED))
        target_names = set(pd.concat(picks)["account"])
    m = match_dart(firms, cc, get_json, only=target_names)
    m.to_csv(OUT_T, index=False, encoding="utf-8-sig")
    t = m[m["account"].isin(target_names)].copy()
    print(f"\n{batch + '차' if batch else ('전체' if full else '시험')} {len(t)}곳 — DART 매칭: " +
          " · ".join(f"{k} {v}" for k, v in t["match"].value_counts().items()), flush=True)
    t["rank"] = t["group"]
    run_t = t[["account", "rank", "corp_code"]]       # DART에서 못 찾은 회사도 넣음 — 수동 입력(코오롱인더스트리)·제외(공공기관)가 붙도록
    suffix = f"_b{batch}" if batch else ("" if full else "_pilot")
    a, c = LND.run(run_t, PROC / f"fin_ets_lenders{suffix}.csv", PROC / f"fin_ets_lender_check{suffix}.csv",
                   "배출권 할당대상" + (f" {batch}차" if batch else ("" if full else " 시험")))

    # 시험 요약 — 전체를 돌릴지 판단할 숫자
    print("\n════════ 시험 요약 ════════" if not full else "\n════════ 요약 ════════")
    found = c[c["report"] != ""]
    print(f"[1] 원문 찾음 {len(found)}/{len(t)} (DART 매칭 못 한 곳 {int((t['corp_code'] == '').sum())})")
    loc = found["doc_basis"].str.extract(r"· (색인|목차|차입금 주석 없음|전체 훑기)")[0].fillna("기타")
    print("[2] 차입금 주석 위치: " + " · ".join(f"{k} {v}" for k, v in loc.value_counts().items()))
    print("[3] 검산: " + " · ".join(f"{k} {v}" for k, v in c["check"].value_counts().items()))
    if len(a):
        a["amt"] = pd.to_numeric(a["amount_won"], errors="coerce").fillna(0)
        a["role"] = a.get("role", "")
        p = a[(a["lender_account"] != "") & (a["amt"] > 0) & (a["role"] == "")]
        sec = a[(a["lender_account"] != "") & (a["amt"] > 0) & (a["role"] != "")]
        old = pd.read_csv(PROC / "fin_mfg_lenders.csv", dtype=str).fillna("") \
            if (PROC / "fin_mfg_lenders.csv").exists() else pd.DataFrame(columns=["lender_account", "amount_won"])
        old_amt = pd.to_numeric(old["amount_won"], errors="coerce").fillna(0)
        old_set = set(old.loc[(old["lender_account"] != "") & (old_amt > 0), "lender_account"])
        by = p.groupby("lender_account")["account"].nunique().sort_values(ascending=False)
        new = [x for x in by.index if x not in old_set]
        print(f"[4] 거래가 잡힌 명단 금융회사 {len(by)}곳 — 그중 제조 94곳에선 없던 곳 {len(new)}: {', '.join(new) or '없음'}")
        print("    곳 수: " + " · ".join(f"{k} {v}" for k, v in by.head(15).items()))
        if len(sec):
            print(f"    (따로 표시) 증권사 CP·전단채 중개 추정 {sec['lender_account'].nunique()}곳: " +
                  ", ".join(sorted(sec["lender_account"].unique())))
        print("[5] 차입처 분류(억): " + " · ".join(
            f"{k} {v:,.0f}" for k, v in (a.groupby("lender_class")["amt"].sum() / 1e8).sort_values(ascending=False).items()))
    bad = m[m["account"].isin(target_names) & (m["corp_code"] == "")]
    if len(bad):
        print(f"\n[DART에서 못 찾은 곳 {len(bad)}] " + ", ".join(f"{a}({k})" for a, k in zip(bad["account"], bad["ksic"])))


if __name__ == "__main__":
    if not sys.argv[1:]:
        print("사용: --batch 1 (할당량 누적 85%) · --batch 2 (85~90%) · --pilot (시험 60곳) · --all")
        sys.exit(0)
    main(sys.argv[1:])
