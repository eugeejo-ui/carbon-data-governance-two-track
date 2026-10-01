"""금융2-4e ③-2·③-3 집계 — 금융회사별 고탄소·CBAM 차주 거래 곳 수와 점수

- 입력 (차입처 조사 결과 — 이 코드는 읽기만 함, 조사 코드는 동결)
  - data/processed/fin_list.csv             금융-1 명단 278곳
  - data/processed/fin_mfg_lenders.csv      제조 94곳 차입처 (③-3)
  - data/processed/fin_ets_lenders_b1.csv   할당대상 1차 62곳 (③-2)
  - data/processed/fin_ets_lenders_b2.csv   할당대상 2차 44곳 (③-2)
  - data/processed/fin_ets_targets.csv      할당대상 기업 701곳 — 제조 94곳과 겹치는 54곳 표시(in_mfg94)
  - (있으면) data/processed/mfg2_verdict.csv    제조 EU 노출 판정 — 설명 칸
  - (있으면) data/raw/4차_사전할당_*.csv         차주 할당량 — 설명 칸
- 판정 기준 (04 문서 3-7, 2026-10-01 확정)
  1. 셈하는 거래: 명단 금융회사가 직접 빌려준 것, 2025년 말 잔액 > 0
     - 증권사(CP·전단채 중개 추정)·사채·유동화 SPC·외국 금융회사·명단 밖은 곳 수에서 뺌 (증권사는 별도 칸)
     - "○○ 외" 묶음은 이름이 나온 곳만 곳 수에 넣음 — 금액은 점수에 쓰지 않음
  2. ③-3 = 제조 94곳 중 거래한 곳 수 / ③-2 = 할당대상(1·2차 106곳 + 제조 94곳 중 할당대상 54곳) 중 거래한 곳 수
     — 금융회사 계정별 (그룹 합계는 설명 칸 아님 — 대표 회사 값 적용 안 함)
  3. 문턱: ③-3 16곳 이상 2점 · ③-2 30곳 이상 2점 · 1곳 이상 1점 (두 층 모두 자연 경계)
  4. ③ 합치기: 평균(가)·높은 쪽(다)을 함께 냄 — ③-1을 모은 뒤 하나를 고름. ③-3 가중(나)은 ③-2를 지워 제외
  5. 동점 순서: ③-3 점수 → ③-3 곳 수 → ③-2 곳 수
- 출력
  - data/processed/fin_exposure.csv          278곳 × (곳 수·점수·설명 칸)
  - data/processed/fin_borrower_edges.csv    차주–금융회사 연결 (관계도 그림용)
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = PROC / "fin_exposure.csv"
OUT_EDGES = PROC / "fin_borrower_edges.csv"

# ── 설정값 (결정이 바뀌면 여기만 고침) ──
T33_HIGH = 16                     # ③-3 2점 문턱 (곳)
T32_HIGH = 30                     # ③-2 2점 문턱 (곳)
COUNT_CLASS = "명단 금융회사"       # 곳 수에 넣는 차입처 분류
BROKER_ROLE = "증권사(CP·전단채 중개 추정)"
BROKER_NAME = re.compile(r"증권|자산운용")   # role 칸이 없는 옛 결과 파일용


def lender_type(name):
    """관계도 색 구분용 업권"""
    if re.search(r"은행|뱅크", name):
        return "은행"
    if re.search(r"생명|화재|손해|보험", name):
        return "보험"
    if re.search(r"캐피탈|카드|커머셜", name):
        return "카드·캐피탈"
    if BROKER_NAME.search(name):
        return "증권·운용"
    return "기타"


def load_rows(path, scope):
    d = pd.read_csv(path, dtype=str).fillna("")
    d["amount_eok"] = pd.to_numeric(d["amount_won"], errors="coerce").fillna(0) / 1e8
    if "role" not in d:
        d["role"] = d["lender_account"].map(lambda a: BROKER_ROLE if BROKER_NAME.search(a) else "")
    d.loc[d["lender_account"].str.contains(BROKER_NAME), "role"] = BROKER_ROLE
    d["scope"] = scope
    return d[["account", "lender_account", "lender_class", "role", "amount_eok", "scope"]]


def load_optional():
    """제조 EU 노출 판정·사전할당량 — 없으면 설명 칸만 비움"""
    eu, item = set(), {}
    v = PROC / "mfg2_verdict.csv"
    if v.exists():
        m = pd.read_csv(v, dtype=str).fillna("")
        eu = {key(a) for a, e in zip(m["account"], m.get("cbam_eu_exposure", "")) if e == "확인"}
        item = {key(a): i for a, i in zip(m["account"], m.get("cbam_item", ""))}
    alloc = None
    try:
        from fin import fin2_ets as E  # noqa: E402
        look, _ = E.load_alloc()
        alloc = lambda n: look.get(key(n), look.get(E.name2(n), look.get(E.translit(n))))  # noqa: E731
    except (Exception, SystemExit) as e:  # noqa: BLE001 — load_alloc은 파일이 없으면 SystemExit
        print(f"  (사전할당량 없음 — 할당량 칸 비움: {type(e).__name__})")
    return eu, item, alloc


def score(n, high):
    return 2 if n >= high else 1 if n >= 1 else 0


def main():
    fin = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    mfg = load_rows(PROC / "fin_mfg_lenders.csv", "제조94")
    ets = pd.concat([load_rows(PROC / f"fin_ets_lenders_b{b}.csv", "할당대상") for b in (1, 2)
                     if (PROC / f"fin_ets_lenders_b{b}.csv").exists()])
    tg = pd.read_csv(PROC / "fin_ets_targets.csv", dtype=str).fillna("")
    ets_mfg = {key(a) for a, f in zip(tg["account"], tg["in_mfg94"]) if f == "True"}   # 제조 94곳 중 할당대상
    ets_group = {key(a): g for a, g in zip(tg["account"], tg.get("group", ""))}          # 배출권 업종 구분
    eu, item, alloc = load_optional()

    # 1. 셈하는 거래만 — 명단 금융회사 · 잔액 > 0 · 증권사 제외 (증권사는 별도)
    allrows = pd.concat([mfg, ets])
    ok = allrows[(allrows["lender_class"] == COUNT_CLASS) & (allrows["amount_eok"] > 0)]
    lend, brok = ok[ok["role"] != BROKER_ROLE], ok[ok["role"] == BROKER_ROLE]

    # 2. 층별 차주 집합 — ③-3 = 제조 94곳 / ③-2 = 할당대상 1·2차 + 제조 중 할당대상
    def layers(d):
        e33 = d[d["scope"] == "제조94"]
        e32 = pd.concat([d[d["scope"] == "할당대상"], e33[e33["account"].map(lambda a: key(a) in ets_mfg)]])
        return e33, e32
    e33, e32 = layers(lend)
    b33, b32 = layers(brok)

    def agg(e, tag):
        g = e.groupby("lender_account")
        return pd.DataFrame({f"n{tag}": g["account"].nunique(), f"eok{tag}": g["amount_eok"].sum().round(1)})
    A = fin[["account"]].set_index("account")
    A = A.join(agg(e33, "33")).join(agg(e32, "32"))
    A["n33_eu"] = e33[e33["account"].map(lambda a: key(a) in eu)].groupby("lender_account")["account"].nunique()
    if alloc:
        al = e32.drop_duplicates(["lender_account", "account"]).copy()
        al["t"] = al["account"].map(alloc)
        A["alloc32_mt"] = (al.groupby("lender_account")["t"].sum() / 1e6).round(2)
    A["n_broker33"] = b33.groupby("lender_account")["account"].nunique()
    A["n_broker32"] = b32.groupby("lender_account")["account"].nunique()
    A = A.fillna(0)
    for c in ("n33", "n32", "n33_eu", "n_broker33", "n_broker32"):
        A[c] = A[c].astype(int)

    # 3. 점수 — 문턱 · 합치기(가 평균 · 다 높은 쪽) · 동점 순서
    A["s33"] = A["n33"].map(lambda n: score(n, T33_HIGH))
    A["s32"] = A["n32"].map(lambda n: score(n, T32_HIGH))
    A["s3_avg"] = ((A["s33"] + A["s32"]) / 2 + 0.5).astype(int)     # 0.5 올림
    A["s3_max"] = A[["s33", "s32"]].max(axis=1)
    A["lender_type"] = [lender_type(a) for a in A.index]
    A = A.sort_values(["s3_max", "s33", "n33", "n32"], ascending=False)
    A["exposure_order"] = range(1, len(A) + 1)
    A.reset_index().to_csv(OUT, index=False, encoding="utf-8-sig")

    # 4. 관계도용 연결 (차주–금융회사, 같은 쌍은 금액 합)
    ed = lend.copy()
    ed["in33"] = ed["scope"] == "제조94"
    ed["in32"] = (ed["scope"] == "할당대상") | ed["account"].map(lambda a: key(a) in ets_mfg)
    E_ = ed.groupby(["account", "lender_account"]).agg(amount_eok=("amount_eok", "sum"),
                                                      in33=("in33", "max"), in32=("in32", "max")).reset_index()
    E_["borrower_scope"] = E_.apply(lambda r: "둘 다" if r.in33 and r.in32 else "제조94" if r.in33 else "할당대상", axis=1)
    E_["eu_confirmed"] = E_["account"].map(lambda a: "Y" if key(a) in eu else "")
    E_["cbam_item"] = E_["account"].map(lambda a: item.get(key(a), ""))
    E_["borrower_sector"] = [item.get(key(a)) or ets_group.get(key(a), "") or ("제조(CBAM)" if s_ != "할당대상" else "")
                             for a, s_ in zip(E_["account"], E_["borrower_scope"])]     # 관계도 묶음: CBAM 품목 → 배출권 업종
    E_["lender_type"] = E_["lender_account"].map(lender_type)
    E_["amount_eok"] = E_["amount_eok"].round(1)
    E_.rename(columns={"account": "borrower", "lender_account": "lender"}).drop(columns=["in33", "in32"]) \
        .to_csv(OUT_EDGES, index=False, encoding="utf-8-sig")

    # ── 보고 ──
    pd.set_option("display.width", 220)
    N = len(A)
    miss = sorted(set(lend["lender_account"]) - set(fin["account"]))
    print(f"명단 {N}곳 · 셈한 거래 {len(lend)}행 → 차주–금융회사 연결 {len(E_)}쌍 → {OUT.relative_to(ROOT)}, {OUT_EDGES.relative_to(ROOT)}")
    print(f"  차주: ③-3 {e33['account'].nunique()}곳 · ③-2 {e32['account'].nunique()}곳 (제조 중 할당대상 {len(ets_mfg)}곳 포함)")
    if miss:
        print(f"  [점검] 명단에 없는 차입처 이름 {len(miss)}개: {miss[:8]}")
    print(f"\n[문턱] ③-3 {T33_HIGH}곳 이상 2점 · ③-2 {T32_HIGH}곳 이상 2점 · 1곳 이상 1점")
    rows = []
    for c, lab in (("s33", "③-3 CBAM 연결"), ("s32", "③-2 고탄소 노출"), ("s3_avg", "③ 가. 평균"), ("s3_max", "③ 다. 높은 쪽")):
        v = A[c].value_counts().reindex([0, 1, 2], fill_value=0)
        rows.append({"구분": lab, "0점": v[0], "1점": v[1], "2점": v[2], "0점 비율": f"{v[0] / N * 100:.1f}%"})
    print(pd.DataFrame(rows).to_string(index=False))
    same = int((A["s3_avg"] != A["s3_max"]).sum())
    print(f"  가·다가 다른 곳: {same}곳 (③-1을 모은 뒤 고름)")
    show = A[A["s3_max"] > 0].reset_index()
    cols = ["exposure_order", "account", "lender_type", "n33", "n33_eu", "n32", "s33", "s32", "s3_max", "n_broker33", "n_broker32"]
    if "alloc32_mt" in A:
        cols.insert(6, "alloc32_mt")
    print(f"\n[거래가 잡힌 금융회사 {len(show)}곳 — 동점 순서 적용]")
    print(show[cols].to_string(index=False))
    print(f"\n[업권별] {show.groupby('lender_type').size().to_dict()}")
    br = A[(A["n_broker33"] + A["n_broker32"]) > 0]
    print(f"[증권사 — 곳 수 제외, 별도 칸] {len(br)}곳: " + ", ".join(f"{a}({r.n_broker33}·{r.n_broker32})" for a, r in br.iterrows()))


if __name__ == "__main__":
    main()
