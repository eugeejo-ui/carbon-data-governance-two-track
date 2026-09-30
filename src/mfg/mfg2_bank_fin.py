"""제조2-6b 차입금 금액 수집과 차입처 집계 (점수 아님)

- 입력
  - data/processed/mfg2_rank.csv (대상: 합계 MIN_TOTAL 이상)
  - data/processed/bank_scan/*.txt (차입처 이름 집계용, 먼저 mfg2_bank.py 실행)
- 금액: DART 재무제표 API(fnlttSinglAcntAll)에서 재무상태표의 차입금 계정을 원 단위로 받음
  - 회사마다 계정명이 달라(예: 포스코 "장기차입금(사채포함),총액") 이름을 고정하지 않고
    재무상태표에서 차입·사채가 들어간 계정을 모두 잡은 뒤 이름으로 나눔
  - 별도(OFS)와 연결(CFS)을 모두 보고 차입금 계정을 실제로 찾은 쪽을 씀.
    어느 쪽인지 fs_div 칸에 적음 (고려제강·포스코스틸리온은 연결에만 있음)
  - 양쪽 모두 차입금 계정이 없으면 무차입(0원)으로 확정함 (한국철강·홍덕산업)
  - API에 자료가 없거나 0으로 나오는 계정은 MANUAL_AMT의 원문 판독값을 씀
- 차입처: bank_scan 조각에서 차입처 이름을 세어 많이 나온 순으로 적음 (금액 배분은 하지 않음)
- 출력: data/manual/mfg_bank_borrowing.csv
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
SCAN = PROC / "bank_scan"
OUT = MANUAL / "mfg_bank_borrowing.csv"

MIN_TOTAL = 7        # 합계 7점 이상을 대상으로 함
YEAR = "2025"
REPRT = "11011"      # 사업보고서
BUCKETS = ("short", "current_long", "long", "bond", "other")

# 재무상태표에서 차입·사채가 들어간 계정을 모두 잡은 뒤 이름으로 나눔
CATCH = re.compile(r"차입|사채")
SKIP = re.compile(r"리스|충당|이연|파생|보증금|이자|수익|비용|자산|증가|감소")

BANKS = ["산업은행", "기업은행", "수출입은행", "국민은행", "KB국민", "신한은행", "우리은행",
         "하나은행", "KEB하나", "농협은행", "NH농협", "씨티은행", "한국씨티", "SC제일",
         "부산은행", "대구은행", "경남은행", "광주은행", "전북은행", "제주은행", "iM뱅크",
         "수협은행", "수협", "새마을금고", "신협", "저축은행", "캐피탈",
         # 외국계·직접금융
         "JP Morgan", "JPMorgan", "HSBC", "Citi", "CITI", "Standard Chartered",
         "Mizuho", "MUFG", "BNP", "중국은행", "공모사채", "회사채", "글로벌본드"]
SAME = {"KB국민": "국민은행", "KEB하나": "하나은행", "NH농협": "농협은행",
        "iM뱅크": "대구은행", "수협": "수협은행", "한국씨티": "씨티은행",
        "JPMorgan": "JP Morgan", "CITI": "Citi",
        "공모사채": "사채(직접금융)", "회사채": "사채(직접금융)",
        "글로벌본드": "사채(직접금융)"}
POLICY = {"산업은행", "수출입은행", "기업은행"}

# API에 차입금 계정이 없거나 0으로 나오는 계정 (원문 차입금 주석에서 읽음, 단위 억 원)
MANUAL_AMT = {
    "고려강선": dict(short=19.5, current_long=0, long=0, bond=0, other=0,
                  note="부산은행 담보부차입 19.5억(2.72~4.11%, 만기 2026-03-27)·"
                       "전기 164.6억에서 88% 감소·약정 한도 국민 150억/신한 USD14,000천/"
                       "부산 USD31,000천·감사보고서만 제출해 API 미등재",
                  src="감사보고서 2025.12 주석 18 단기차입금"),
    "일진제강": dict(short=417.5, current_long=0, long=0, bond=0, other=0,
                  note="하나은행 L/C Nego 87.5억·산업은행 기업운전자금 280억(3.21%)·"
                       "수출입은행 수출성장자금 50억(3.38%)·장기차입금 없음·"
                       "감사보고서만 제출해 API 미등재",
                  src="감사보고서 2025.12 주석 18 차입금"),
    "홍덕산업": dict(short=0, current_long=0, long=0, bond=0, other=0,
                  note="기말 차입금 0(기중 2,580.7억 유입·동액 상환)·"
                       "약정 한도 신한+한국씨티 440억 중 실행 3.66억·무차입 경영·"
                       "감사보고서만 제출해 API 미등재",
                  src="감사보고서 2025.12 주석 22 약정사항"),
    "대호에이엘": dict(short=497.5, current_long=0, long=0, bond=0, other=0,
                   note="산업은행 일반대출 155.6억(4.50~4.74%)·산업은행 공급자금융약정 311.9억"
                        "(4.18~5.47%)·수출입은행 포괄무역금융 30억(3.20%)·별도 466.9억·"
                        "API 재무상태표에는 차입금 계정이 없어 원문 주석을 씀",
                   src="사업보고서 2025.12 주석 17 단기차입금(연결)"),
}


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def to_won(x):
    x = str(x).replace(",", "").strip()
    if x in ("", "-"):
        return 0
    neg = x.startswith("(") and x.endswith(")")
    x = x.strip("()")
    try:
        v = int(float(x))
    except ValueError:
        return 0
    return -v if neg else v


def bucket(nm):
    """계정명을 단기·유동성장기·장기·사채·기타로 나눔 (앞의 조건이 우선)

    포스코 '차입금', 세아제강 '차입부채'처럼 수식어가 없는 계정이 있음.
    재무상태표는 유동부채를 먼저 싣고 비유동에는 '비유동·장기'를 붙이므로
    수식어가 없으면 유동(short)으로 봄
    """
    if "유동성" in nm:
        return "current_long"
    if nm.startswith("비유동") or nm.startswith("장기") or "장기차입" in nm:
        return "long"
    if nm.startswith("단기") or "단기차입" in nm:
        return "short"
    if "사채" in nm:
        return "bond"
    if nm in ("차입금", "차입부채", "차입금및사채", "사채및차입금"):
        return "short"
    return "other"


def borrowings(corp_code):
    """(금액 dict, fs_div, 계정명 목록). 자료가 없으면 (None, '', [])

    별도(OFS)와 연결(CFS)을 모두 보고, 차입금 계정을 실제로 찾은 쪽을 먼저 씀.
    어느 쪽에서도 못 찾았고 재무상태표는 읽었으면 무차입(0원)으로 확정함
    (한국철강처럼 차입금이 정말 없는 곳을 "자료 없음"과 구분하기 위함)
    """
    zero = None
    for fs in ("OFS", "CFS"):
        data = get_json("fnlttSinglAcntAll", corp_code=corp_code, bsns_year=YEAR,
                        reprt_code=REPRT, fs_div=fs)
        rows = data.get("list") or []
        if not rows:
            continue
        got = {k: 0 for k in BUCKETS}
        names, bs_seen = [], False
        for r in rows:
            if r.get("sj_div") != "BS":
                continue
            bs_seen = True
            nm = re.sub(r"\s", "", str(r.get("account_nm", "")))
            if SKIP.search(nm) or not CATCH.search(nm):
                continue
            got[bucket(nm)] += to_won(r.get("thstrm_amount"))
            names.append(f"{nm}:{r.get('thstrm_amount')}")
        # 계정명만 있고 금액이 0이면 확정하지 않음 (별도 0 · 연결에 실제 차입금이 있는 경우)
        if names and any(got.values()):
            return got, fs, names
        if bs_seen and zero is None:
            zero = (got, fs, names or ["차입금 계정 없음(무차입)"])
    return zero if zero else (None, "", [])


def bank_names(account):
    p = SCAN / (re.sub(r"[\\/:*?\"<>|()]", "", account) + ".txt")
    if not p.exists():
        return [], 0
    t = p.read_text(encoding="utf-8")
    cnt = {}
    for b in BANKS:
        n = t.count(b)
        if n:
            k = SAME.get(b, b)
            cnt[k] = cnt.get(k, 0) + n
    return [b for b, _ in sorted(cnt.items(), key=lambda x: -x[1])], t.count("\n\n- ")


def main():
    rank = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    rank["total_n"] = pd.to_numeric(rank["total"], errors="coerce").fillna(0)
    target = rank[rank["total_n"] >= MIN_TOTAL].copy()

    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    code_map = {key(a): c for a, c in zip(base["account"], base["corp_code"]) if c}
    missing = [a for a in target["account"] if key(a) not in code_map]
    if missing:
        cc = corp_codes()
        cc["k"] = cc["corp_name"].map(key)
        by_name = dict(zip(cc["k"], cc["corp_code"]))
        for a in missing:
            if by_name.get(key(a)):
                code_map[key(a)] = by_name[key(a)]
        still = [a for a in missing if key(a) not in code_map]
        print(f"이름으로 채운 고유번호 {len(missing) - len(still)}곳"
              + (f" · 못 찾음 {still}" if still else ""))

    rows = []
    for i, r in enumerate(target.to_dict("records"), 1):
        acc = r["account"]
        banks, pieces = bank_names(acc)
        code = code_map.get(key(acc), "")
        got, fs, names = (None, "", [])
        if code:
            try:
                got, fs, names = borrowings(code)
            except Exception as e:  # noqa: BLE001
                print(f"[{i}] {acc} 재무제표 오류: {str(e)[:90]}")

        # API에 자료가 없거나 차입금이 0으로 나오면 원문에서 읽은 값을 씀
        man = MANUAL_AMT.get(key(acc))
        if man and (got is None or sum(got.values()) == 0):
            got = {k: man[k] * 1e8 for k in BUCKETS}
            fs = "원문"
            names = [man["src"]]
        used_manual = man is not None and fs == "원문"
        total = sum(got.values()) if got else None
        rows.append(dict(
            rank=r["rank"], account=acc, size=r["size"], score_total=r["total"],
            main_banks="·".join(banks[:6]),
            policy_bank="·".join([b for b in banks if b in POLICY]) or "없음",
            bank_n=len(banks),
            short_eok=round(got["short"] / 1e8, 1) if got else "",
            current_long_eok=round(got["current_long"] / 1e8, 1) if got else "",
            long_eok=round(got["long"] / 1e8, 1) if got else "",
            bond_eok=round(got["bond"] / 1e8, 1) if got else "",
            other_eok=round(got["other"] / 1e8, 1) if got else "",
            borrowing_eok=round(total / 1e8, 1) if got else "",
            fs_div=fs or "원문 확인",
            basis_date=f"{YEAR}-12-31" if got else "",
            pieces=pieces,
            accounts_found="; ".join(names[:10]),
            note=man["note"] if used_manual else "",
            source=(man["src"] if used_manual else
                    f"DART 재무제표 API {YEAR} 사업보고서 ({fs})" if got
                    else f"bank_scan/{acc}.txt 차입금 주석"),
        ))
        mark = f"{rows[-1]['borrowing_eok']}억" if got else "원문 확인"
        print(f"[{i}/{len(target)}] {acc} · 은행 {len(banks)} · {mark}")

    out = pd.DataFrame(rows)
    out["rank"] = pd.to_numeric(out["rank"], errors="coerce")
    out = out.sort_values("rank")
    out.to_csv(OUT, index=False, encoding="utf-8")

    pd.set_option("display.width", 250)
    need = out[out["fs_div"] == "원문 확인"]["account"].tolist()
    odd = out[(out["fs_div"] != "원문 확인") & (out["other_eok"] != 0)]["account"].tolist()
    zero_acc = out[out["borrowing_eok"] == 0.0]["account"].tolist()
    print(f"\n{len(out)}곳 → {OUT.relative_to(ROOT)}")
    print(f"재무제표 API {len(out) - len(need)}곳 · 원문 확인 필요 {len(need)}곳: {need}")
    print(f"원문 판독값 사용 {(out['fs_div'] == '원문').sum()}곳 · 무차입(0억) {len(zero_acc)}곳: {zero_acc}")
    if odd:
        print(f"분류 확인 필요(other 값 있음) {len(odd)}곳: {odd}")
    print("\n[결과]")
    print(out[["rank", "account", "score_total", "main_banks", "policy_bank",
               "borrowing_eok", "fs_div"]].to_string(index=False))
    print("\n[정책금융 거래]")
    print(out["policy_bank"].value_counts().to_string())


if __name__ == "__main__":
    main()