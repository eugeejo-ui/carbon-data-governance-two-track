"""EU 매출 구성 확인: 계정별로 지역별 매출·비유동자산·EU/비EU 유럽 법인 문장 추출

- 한 계정이 실패해도 다음 계정을 계속 처리하고, 실패 사유를 _failures.csv에 남김
- 이미 저장된 계정은 건너뜀 (다시 받으려면 --force)
- zip 안의 파일을 하나씩 처리해 큰 사업보고서에서도 메모리를 적게 씀
- 특정 계정만: python src/mfg/check_eu_composition.py "현대제철(주)"
"""
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/processed/eu_check"
CACHE = ROOT / "data/raw/dart/docs"
FAIL_LOG = OUT_DIR / "_failures.csv"
RCEPT_OVERRIDE = ROOT / "data/manual/eu_check_rcept.csv"

ACCOUNTS = [
    # EU 확인 (제조1-5 판정) — eu_item_match 재검토 대상
    "고려제강(주)", "씨에스윈드(주)", "두산에너빌리티(주)", "에스케이오션플랜트(주)",
    "(주)SIMPAC", "(주)태웅", "현대제철(주)", "주식회사 포스코", "아주스틸(주)",
    "주식회사 세아베스틸", "포스코스틸리온(주)", "KG스틸(주)", "(주)TCC스틸",
    "동국산업(주)", "동국씨엠 주식회사", "삼아알미늄(주)", "(주)세아제강",
    "현대비앤지스틸(주)", "남해화학(주)", "주식회사 세아창원특수강",
    "DSR제강(주)", "만호제강(주)", "고려강선(주)", "홍덕산업(주)",
    "(주)알루코", "조일알미늄(주)", "한주라이트메탈(주)", "(주)대호에이엘",
    "하이호경금속주식회사", "(주)케이피에프", "(주)태광", "(주)성광벤드",
    "(주)유니온", "디씨엠(주)", "(주)대양금속", "케이비아이동양철관(주)",
    "일진제강(주)", "디케이동신주식회사",
    # 이번 조사에서 불명으로 올라간 계정
    "(주)대륙제관", "(주)태양",
]
REGION_KW = {"지역별": 6, "비유동자산": 4, "유럽": 6, "특수관계자": 4,
             "수출": 4, "매출액": 4,
             "주요 제품": 4, "생산실적": 4, "매출실적": 4, "품 목": 4}
EU = ["독일", "네덜란드", "폴란드", "체코", "슬로바키아", "헝가리", "포르투갈", "스페인",
      "이탈리아", "프랑스", "벨기에", "룩셈부르크", "덴마크", "스웨덴", "핀란드",
      "오스트리아", "슬로베니아", "루마니아", "아일랜드"]
NON_EU = ["영국", "스위스", "노르웨이", "튀르키예", "터키"]
WIN, MAX_COUNTRY = 220, 2
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def api_key():
    import os
    for name in ("DART_API_KEY", "OPENDART_API_KEY", "DART_KEY"):
        if os.getenv(name):
            return os.getenv(name)
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() in ("DART_API_KEY", "OPENDART_API_KEY", "DART_KEY"):
                return v.strip().strip('"').strip("'")
    raise RuntimeError("API 키를 찾지 못함: 환경변수 DART_API_KEY 또는 .env 확인")


def api_json(url, params, tries=3):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"조회 실패: {last}")


def annual_report_candidates(key, corp_code):
    """사업보고서를 최신순으로 찾고, 없으면 감사보고서로 넓힘 (비상장 대응)"""
    out = []
    for detail_ty, want in (("A001", "사업보고서"), ("F001", "감사보고서")):
        for bgn, end in (("20260101", "20261231"), ("20250101", "20261231")):
            j = api_json("https://opendart.fss.or.kr/api/list.json", {
                "crtfc_key": key, "corp_code": corp_code, "bgn_de": bgn, "end_de": end,
                "pblntf_detail_ty": detail_ty, "page_count": 100})
            if j.get("status") == "013":
                continue
            if j.get("status") != "000":
                raise RuntimeError(f"목록 오류 {j.get('status')} {j.get('message')}")
            items = [x for x in j.get("list", []) if want in x["report_nm"]]
            if items:
                items.sort(key=lambda x: x["rcept_no"], reverse=True)
                out = [(x["rcept_no"], x["report_nm"]) for x in items]
                break
        if out:
            break
    if not out:
        raise RuntimeError("사업보고서·감사보고서를 찾지 못함")
    return out


def fetch_doc(key, rcept_no):
    """원문 zip을 내려받아 경로 반환. 깨진 응답은 저장하지 않음"""
    CACHE.mkdir(parents=True, exist_ok=True)
    zpath = CACHE / f"{rcept_no}.zip"
    if zpath.exists():
        if zipfile.is_zipfile(zpath):
            return zpath
        zpath.unlink()  # 이전에 잘못 저장된 캐시 제거
    tmp = zpath.with_suffix(".part")
    with requests.get("https://opendart.fss.or.kr/api/document.xml",
                      params={"crtfc_key": key, "rcept_no": rcept_no},
                      timeout=300, stream=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    if not zipfile.is_zipfile(tmp):
        head = tmp.read_bytes()[:300].decode("utf-8", "ignore").replace("\n", " ")
        tmp.unlink()
        raise RuntimeError(f"원문이 zip이 아님(DART 응답): {head}")
    tmp.replace(zpath)
    return zpath


def decode(raw):
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def scan(zpath, wanted):
    """zip 안 파일을 하나씩 훑어 키워드별 문장을 모음. wanted: {키워드: 최대 개수}"""
    hits = {kw: [] for kw in wanted}
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if all(len(hits[kw]) >= wanted[kw] for kw in wanted):
                break
            text = WS.sub(" ", TAG.sub(" ", decode(z.read(name))))
            for kw, cap in wanted.items():
                if len(hits[kw]) >= cap:
                    continue
                for m in re.finditer(re.escape(kw), text):
                    hits[kw].append(text[max(0, m.start() - WIN): m.start() + WIN])
                    if len(hits[kw]) >= cap:
                        break
            del text
    return hits


def run_one(key, acc, corp_code, override=None):
    if override:
        candidates = [(override, "수동 지정")]
    else:
        candidates = annual_report_candidates(key, corp_code)

    zpath = rcept_no = report_nm = None
    errs = []
    for rn, nm in candidates:
        try:
            zpath = fetch_doc(key, rn)
            rcept_no, report_nm = rn, nm
            break
        except Exception as e:  # 정정본에 원문이 없으면 다음 후보(원본)로
            errs.append(f"{rn}: {e}")
    if zpath is None:
        raise RuntimeError(" / ".join(errs) or "내려받을 보고서가 없음")

    wanted = dict(REGION_KW)
    wanted.update({c: MAX_COUNTRY for c in EU + NON_EU})
    hits = scan(zpath, wanted)

    lines = [f"# {acc} {report_nm} rcept_no={rcept_no}",
             f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}", ""]
    for kw in REGION_KW:
        if hits[kw]:
            lines.append(f"## {kw}")
            lines += ["- " + s for s in hits[kw]]
    for group, names in (("EU 국가", EU), ("비EU 유럽", NON_EU)):
        found = [c for c in names if hits[c]]
        lines.append(f"## {group}: {', '.join(found) if found else '없음'}")
        for c in found:
            lines += [f"- ({c}) " + s for s in hits[c]]
    safe = re.sub(r"[^\w가-힣]", "", acc)
    (OUT_DIR / f"{safe}.txt").write_text("\n".join(lines), encoding="utf-8")
    return safe


def main():
    force = "--force" in sys.argv
    picked = [a for a in sys.argv[1:] if not a.startswith("--")]
    targets = picked or ACCOUNTS

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(ROOT / "data/processed/mfg2_base.csv", dtype=str)
    key = api_key()
    overrides = {}
    if RCEPT_OVERRIDE.exists():
        ov = pd.read_csv(RCEPT_OVERRIDE, dtype=str)
        overrides = dict(zip(ov["account"], ov["rcept_no"]))
    done, skipped, failed = [], [], []

    for i, acc in enumerate(targets, 1):
        safe = re.sub(r"[^\w가-힣]", "", acc)
        if not force and (OUT_DIR / f"{safe}.txt").exists():
            skipped.append(acc)
            print(f"[{i}/{len(targets)}] 건너뜀(이미 있음): {acc}", flush=True)
            continue
        row = base.loc[base["account"] == acc]
        override = overrides.get(acc)
        if row.empty and not override:
            failed.append((acc, "명단에 없음"))
            print(f"[{i}/{len(targets)}] 실패: {acc} — 명단에 없음", flush=True)
            continue
        print(f"[{i}/{len(targets)}] 처리 중: {acc}", flush=True)
        try:
            corp_code = None if row.empty else row["corp_code"].iloc[0]
            if not override and (corp_code is None or pd.isna(corp_code)):
                raise RuntimeError("corp_code 없음 — eu_check_rcept.csv에 보고서 번호를 넣어 주세요")
            run_one(key, acc, corp_code, override)
            done.append(acc)
            print(f"    저장: {safe}.txt", flush=True)
        except Exception as e:  # 한 계정 실패가 전체를 멈추지 않게 함
            failed.append((acc, f"{type(e).__name__}: {e}"))
            print(f"    실패: {type(e).__name__}: {e}", flush=True)
        time.sleep(0.5)

    if failed:
        pd.DataFrame(failed, columns=["account", "reason"]).to_csv(
            FAIL_LOG, index=False, encoding="utf-8-sig")
    print(f"\n완료 {len(done)} · 건너뜀 {len(skipped)} · 실패 {len(failed)}")
    if failed:
        print(f"실패 기록: {FAIL_LOG}")


if __name__ == "__main__":
    main()