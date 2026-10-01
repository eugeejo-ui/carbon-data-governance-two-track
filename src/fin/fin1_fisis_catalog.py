"""금융1-3C 1단계 — FISIS(금융감독원 금융통계정보시스템) 권역별 목록 확인

- 목적: 2단계(회사별 총자산 수집)에 쓸 값을 찾음
  1) 권역별 전체 금융회사 목록과 금융회사코드 (금융회사 API)
  2) 권역별 재무현황 통계표 목록 (통계목록 API, 통계표분류 B = 재무현황)
  3) 재무상태표류 통계표의 "자산총계" 항목 후보 (계정항목 API)
- 총자산이 들어 있는 통계코드·항목코드는 권역마다 달라 추측하지 않고 조회로 찾음.
  이 결과를 보고 사람이 권역별 코드를 확정한 뒤 2단계를 실행함
- 인증키는 .env의 FISIS_API_KEY에서 읽음. 캐시 파일 이름·출력에는 키를 남기지 않음
- 응답은 data/raw/fisis/에 캐시함 (비영리 일일 호출 한도 10,000회 — 한도에 걸리면 멈추고 다음 날 이어 받음)
- 출처: 금융감독원 FISIS OPEN API 명세 (fisis.fss.or.kr/page/api-spec.jsp)

출력 (data/processed/fisis/)
  - companies.csv : 권역·금융회사코드·회사명·경로·폐업 여부
  - tables.csv : 권역별 재무현황 통계표 목록
  - asset_accounts.csv : 재무상태표류 통계표의 자산총계 항목 후보
"""
from pathlib import Path
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "fisis"
OUT = ROOT / "data" / "processed" / "fisis"
BASE = "http://fisis.fss.or.kr/openapi"

# 받을 권역 (2026-10-01 결정) — 코드는 FISIS 금융권역 분류표
PARTS = {
    "A": "국내은행", "H": "생명보험", "I": "손해보험", "F": "증권사", "W": "선물사",
    "G": "자산운용사", "C": "신용카드사", "K": "리스사", "T": "할부금융사",
    "N": "신기술금융사", "E": "상호저축은행", "D": "종합금융회사",
    "M": "부동산신탁", "L": "금융지주회사",
    "J": "외은지점",            # 목록만 — 한국 법인이 아닌 지점이라 1-3C 대상에서 제외, 참고용
}
# 제외 권역: 신용협동조합(O)·농업협동조합(Q)·수산업협동조합(P)·산림조합(S) — 단위조합 조합원 대상,
#           투자자문·일임(X) — 자기 자산이 작음. 공통(B·R)은 회사 목록이 아님
FIN_TABLE_DIV = "B"                                   # 통계표분류: 재무현황
TABLE_NAME = re.compile(r"재무상태|대차대조|요약.*재무")   # 재무상태표류 통계표 이름
ASSET_NAME = re.compile(r"^\s*(자산\s*(총계|합계|계)|총\s*자산)\s*$")  # 자산총계 항목만 (유형자산 등 제외)
CLOSED = re.compile(r"\[폐\]|\(구\)")                  # 폐업·옛 이름 표시


class LimitReached(Exception):
    """일일 호출 한도 초과(err 020) — 캐시된 것까지 저장하고 멈춤"""


def api_key():
    key = os.environ.get("FISIS_API_KEY", "").strip()
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("FISIS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit(".env에 FISIS_API_KEY가 없음")
    return key


def call(service, **params):
    """FISIS API 호출 — 캐시가 있으면 읽고, 없으면 받아서 저장. result 부분을 돌려줌"""
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    path = CACHE / f"{service}_{tag}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    q = urllib.parse.urlencode({"lang": "kr", "auth": api_key(), **params})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{BASE}/{service}.json?{q}", timeout=30) as r:
                body = json.loads(r.read().decode("utf-8"))
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"{service} 호출 실패 — {type(last).__name__}")
    res = body.get("result", body)
    code = str(res.get("err_cd", ""))
    if code == "020":
        raise LimitReached("일일 호출 한도 초과 — 내일 다시 실행하면 캐시 다음부터 이어 받음")
    if code in ("010", "011", "012", "013"):
        raise SystemExit(f"인증키 오류 {code} {res.get('err_msg', '')} — .env의 FISIS_API_KEY 확인")
    if code == "000":                                  # 정상 응답만 캐시
        path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def rows(res):
    """list가 하나면 dict로, 여러 개면 list로 올 수 있어 항상 list로 맞춤"""
    lst = res.get("list") or []
    if isinstance(lst, dict):
        lst = lst.get("row", lst)
    return [lst] if isinstance(lst, dict) else list(lst)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    comp, tabs, accs, errs = [], [], [], []
    try:
        for part, pname in PARTS.items():
            res = call("companySearch", partDiv=part)
            if res.get("err_cd") != "000":
                errs.append((part, "companySearch", res.get("err_cd"), res.get("err_msg")))
                continue
            for r in rows(res):
                nm = str(r.get("finance_nm", ""))
                comp.append(dict(part=part, part_nm=pname, finance_cd=r.get("finance_cd", ""),
                                 finance_nm=nm, finance_path=r.get("finance_path", ""),
                                 closed=bool(CLOSED.search(nm))))
            if part == "J":                            # 외은지점은 목록만
                continue
            res = call("statisticsListSearch", lrgDiv=part, smlDiv=FIN_TABLE_DIV)
            if res.get("err_cd") != "000":
                errs.append((part, "statisticsListSearch", res.get("err_cd"), res.get("err_msg")))
                continue
            for t in rows(res):
                ln, nm = t.get("list_no", ""), str(t.get("list_nm", ""))
                is_bs = bool(TABLE_NAME.search(nm))
                tabs.append(dict(part=part, part_nm=pname, list_no=ln, list_nm=nm, balance_sheet=is_bs))
                if not is_bs:
                    continue
                ra = call("accountListSearch", listNo=ln)
                for a in rows(ra):
                    an = str(a.get("account_nm", ""))
                    if ASSET_NAME.search(an):
                        accs.append(dict(part=part, part_nm=pname, list_no=ln, list_nm=nm,
                                         account_cd=a.get("account_cd", ""), account_nm=an))
    except LimitReached as e:
        print(f"\n[멈춤] {e}")

    c = pd.DataFrame(comp, columns=["part", "part_nm", "finance_cd", "finance_nm", "finance_path", "closed"])
    t = pd.DataFrame(tabs, columns=["part", "part_nm", "list_no", "list_nm", "balance_sheet"])
    a = pd.DataFrame(accs, columns=["part", "part_nm", "list_no", "list_nm", "account_cd", "account_nm"])
    c.to_csv(OUT / "companies.csv", index=False, encoding="utf-8-sig")
    t.to_csv(OUT / "tables.csv", index=False, encoding="utf-8-sig")
    a.to_csv(OUT / "asset_accounts.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 300)
    print(f"회사 {len(c)}곳 (영업 {(~c['closed']).sum()} · 폐업 표시 {c['closed'].sum()}) → {(OUT / 'companies.csv').relative_to(ROOT)}")
    print("\n[권역별 회사 수 — 영업 중]")
    print(c[~c["closed"]].groupby(["part", "part_nm"]).size().to_string())
    print("\n[권역별 재무상태표류 통계표와 자산총계 항목 후보] — 2단계 코드 확정용")
    if len(a):
        print(a.to_string(index=False))
    miss = sorted(set(PARTS) - {"J"} - set(a["part"]))
    if miss:
        print(f"\n[자산총계 후보를 못 찾은 권역] {', '.join(f'{m}({PARTS[m]})' for m in miss)}")
        mt = t[t["part"].isin(miss)]
        if len(mt):
            print("  → 이 권역들의 재무현황 통계표 이름 (사람이 보고 총자산 표를 고름)")
            print(mt.to_string(index=False))
    if errs:
        print("\n[오류 응답]", errs)
    print(f"\n호출 캐시 {len(list(CACHE.glob('*.json')))}건 → {CACHE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
