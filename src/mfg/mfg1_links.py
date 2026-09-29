"""제조1-3 확인용 2025 사업보고서·감사보고서 DART 링크

- 인자 없이 실행: mfg1_size_screen.csv의 '수동 확인' 회사 + (주)동남(마산 법인)
- 5b: 제조1-5b 대상(CBAM 대상 중 상장 중견을 뺀 계정)과 대기업 계열의 상장 모회사
  (예: python src/mfg/mfg1_links.py 5b)
- 회사 이름을 인자로 주면 그 회사들을 찾음 (예: python src/mfg/mfg1_links.py 삼보광업 에스폼)
  명단(mfg1_merged.csv)에 있으면 그 고유번호를, 없으면 DART 고유번호 목록에서 이름으로 찾음
- 2026-01-01 이후 제출된 사업보고서(A001)·감사보고서(F001) 링크와,
  사업보고서가 있으면 2025 자산총계(별도, 억 원)를 함께 출력함
- 결과는 data/processed/mfg1_report_links.csv에 저장 (실행할 때마다 덮어씀)
"""
from datetime import date
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
DONGNAM_JURIR = "1901110004321"   # 주식회사 동남 (마산 자유무역6길 157)
# 제조1-3 신원 확인으로 특정한 법인 (동명 회사가 있어 이름으로 찾지 않음)
IDENTIFIED = {"피엔알": "1717110076545", "동남": DONGNAM_JURIR}
KINDS = {"A001": "사업보고서", "F001": "감사보고서"}
# 비상장 대기업 계열의 상장 모회사(지주회사 포함). 지역별 매출 확인용
PARENTS = ["포스코홀딩스", "세아베스틸지주", "세아제강지주", "현대제철"]


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def default_targets():
    s = pd.read_csv(PROC / "mfg1_size_screen.csv", dtype=str).fillna("")
    t = s[s["result"] == "수동 확인"][["name", "corp_code"]]
    i = pd.read_csv(PROC / "mfg1_identity_candidates.csv", dtype=str).fillna("")
    d = i[i["jurir_no"] == DONGNAM_JURIR][["name", "corp_code"]]
    return pd.concat([t, d], ignore_index=True)


def targets_5b():
    c = pd.read_csv(PROC / "mfg1_cbam_check.csv", dtype=str).fillna("")
    t = c[(c["cbam_status"] == "대상") & ~((c["listed"] == "상장") & (c["size_final"] == "중견"))]
    names = list(t["name"]) + [p for p in PARENTS if key(p) not in set(t["name"].map(key))]
    return named_targets(names)


def identified_codes():
    """신원 확인 자료에서 법인등록번호로 특정한 회사의 DART 고유번호"""
    i = pd.read_csv(PROC / "mfg1_identity_candidates.csv", dtype=str).fillna("")
    out = {}
    for k, jurir in IDENTIFIED.items():
        hit = i[i["jurir_no"] == jurir]
        if len(hit):
            out[k] = (hit["name"].iloc[0], hit["corp_code"].iloc[0])
    return out


def named_targets(names):
    known = identified_codes()
    merged = pd.read_csv(PROC / "mfg1_merged.csv", dtype=str).fillna("")
    merged["k"] = merged["name"].map(key)
    codes = corp_codes()
    codes["k"] = codes["corp_name"].map(key)
    rows = []
    for n in names:
        if key(n) in known:
            label, code = known[key(n)]
            rows.append(dict(name=label, corp_code=code))
            continue
        hit = merged[(merged["k"] == key(n)) & (merged["corp_code"] != "")]
        if len(hit):
            rows.append(dict(name=hit["name"].iloc[0], corp_code=hit["corp_code"].iloc[0]))
            continue
        c = codes[codes["k"] == key(n)]
        if c.empty:
            rows.append(dict(name=n, corp_code=""))
        for x in c.itertuples():
            label = f"{x.corp_name} (상장 {x.stock_code})" if x.stock_code else x.corp_name
            rows.append(dict(name=label, corp_code=x.corp_code))
    return pd.DataFrame(rows)


def assets_eok(corp_code):
    d = get_json("fnlttSinglAcnt", corp_code=corp_code, bsns_year="2025", reprt_code="11011")
    for fs in ("OFS", "CFS"):
        for x in d.get("list", []):
            if x.get("fs_div") == fs and x.get("account_nm") == "자산총계":
                v = str(x.get("thstrm_amount", "")).replace(",", "")
                if v.lstrip("-").isdigit():
                    return f"{round(int(v) / 1e8):,}억 ({fs})"
    return ""


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "5b":
        t = targets_5b()
    elif len(sys.argv) > 1:
        t = named_targets(sys.argv[1:])
    else:
        t = default_targets()
    end = date.today().strftime("%Y%m%d")
    rows = []
    for r in t.itertuples():
        if not r.corp_code:
            rows.append(dict(name=r.name, corp_code="", kind="", report_nm="DART에서 이름을 못 찾음",
                             rcept_dt="", assets="", link=""))
            continue
        found = False
        for code, kind in KINDS.items():
            d = get_json("list", corp_code=r.corp_code, bgn_de="20260101", end_de=end,
                         pblntf_detail_ty=code, last_reprt_at="Y", page_count="100")
            for x in d.get("list", []):
                found = True
                rows.append(dict(name=r.name, corp_code=r.corp_code, kind=kind,
                                 report_nm=x["report_nm"].strip(), rcept_dt=x["rcept_dt"],
                                 assets=assets_eok(r.corp_code) if code == "A001" else "",
                                 link=VIEWER + x["rcept_no"]))
        if not found:
            rows.append(dict(name=r.name, corp_code=r.corp_code, kind="",
                             report_nm="2026년 제출 보고서 없음", rcept_dt="", assets="", link=""))
    out = pd.DataFrame(rows)
    out.to_csv(PROC / "mfg1_report_links.csv", index=False, encoding="utf-8-sig")
    for r in out.itertuples():
        extra = f" | 자산총계 {r.assets}" if r.assets else ""
        print(f"{r.name} | {r.report_nm} | {r.rcept_dt}{extra}\n  {r.link}")


if __name__ == "__main__":
    main()