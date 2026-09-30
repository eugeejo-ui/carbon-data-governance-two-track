"""고려제강 유럽 매출의 생산지 구성 확인용: 사업보고서 원문에서 관련 문장 추출"""
import io, os, re, zipfile
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/kiswire_eu_check.txt"
CACHE = ROOT / "data/raw/dart/docs"
ACCOUNT = "고려제강(주)"
KEYWORDS = ["유럽", "구주", "지역별", "수출", "KISWIRE CORD CZECH", "체코"]
WIN = 250  # 키워드 앞뒤로 자를 글자 수
MAX_HITS = 15  # 키워드별 최대 출력 수


def api_key():
    for name in ("DART_API_KEY", "OPENDART_API_KEY", "DART_KEY"):
        if os.getenv(name):
            return os.getenv(name)
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() in ("DART_API_KEY", "OPENDART_API_KEY", "DART_KEY"):
                return v.strip().strip('"').strip("'")
    raise SystemExit("API 키를 찾지 못함: 환경변수 DART_API_KEY 또는 .env 확인")


def latest_annual_report(key, corp_code):
    r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
        "crtfc_key": key, "corp_code": corp_code, "bgn_de": "20260101",
        "end_de": "20261231", "pblntf_detail_ty": "A001", "page_count": 100})
    items = [x for x in r.json().get("list", []) if "사업보고서" in x["report_nm"]]
    if not items:
        raise SystemExit("2026년 제출 사업보고서를 찾지 못함")
    items.sort(key=lambda x: x["rcept_no"], reverse=True)
    return items[0]["rcept_no"], items[0]["report_nm"]


def load_text(key, rcept_no):
    CACHE.mkdir(parents=True, exist_ok=True)
    zpath = CACHE / f"{rcept_no}.zip"
    if not zpath.exists():
        r = requests.get("https://opendart.fss.or.kr/api/document.xml",
                         params={"crtfc_key": key, "rcept_no": rcept_no})
        zpath.write_bytes(r.content)
    texts = []
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            raw = z.read(name)
            for enc in ("utf-8", "cp949"):
                try:
                    texts.append(raw.decode(enc))
                    break
                except UnicodeDecodeError:
                    continue
    text = re.sub(r"<[^>]+>", " ", " ".join(texts))
    return re.sub(r"\s+", " ", text)


def main():
    base = pd.read_csv(ROOT / "data/processed/mfg2_base.csv", dtype=str)
    corp_code = base.loc[base["account"] == ACCOUNT, "corp_code"].iloc[0]
    key = api_key()
    rcept_no, report_nm = latest_annual_report(key, corp_code)
    text = load_text(key, rcept_no)

    lines = [f"{ACCOUNT} {report_nm} rcept_no={rcept_no}",
             f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}", ""]
    for kw in KEYWORDS:
        hits = [m.start() for m in re.finditer(re.escape(kw), text)]
        lines.append(f"## {kw} ({len(hits)}건 중 최대 {MAX_HITS}건)")
        for pos in hits[:MAX_HITS]:
            lines.append("- " + text[max(0, pos - WIN): pos + WIN])
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"저장: {OUT}  (문서 길이 {len(text):,}자)")


if __name__ == "__main__":
    main()