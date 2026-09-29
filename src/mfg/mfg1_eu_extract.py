"""제조1-5b EU 수출 근거 문장 추출

- 입력: data/processed/mfg1_report_links.csv (먼저 python src/mfg/mfg1_links.py 5b 실행)
- 회사마다 사업보고서가 있으면 사업보고서, 없으면 감사보고서의 DART 원문 파일을 받아
  "유럽·EU·EUR·유로·구주"와 EU 회원국 이름이 들어간 문장을 뽑음 (문서 제목 위치 포함)
- 정정 공시에 원문 파일이 없으면(DART 014) 같은 해 원본·다른 정정본을 차례로 씀
- 한 회사에서 오류가 나도 멈추지 않고 요약에 적은 뒤 다음 회사로 넘어감
- 판정은 하지 않음. 뽑힌 문장을 보고 사용자가 3-3 기준으로 판정함
- 출력
  - data/processed/mfg1_eu_snippets.csv: 뽑힌 문장 전체
  - data/processed/mfg1_eu_snippets.md: 회사별로 우선순위가 높은 문장만 추린 검토용 문서
"""
from datetime import date
from html import unescape
from pathlib import Path
import re
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import document_zip, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
LINKS = PROC / "mfg1_report_links.csv"
OUT_CSV = PROC / "mfg1_eu_snippets.csv"
OUT_MD = PROC / "mfg1_eu_snippets.md"

PARENTS = {"포스코홀딩스", "세아베스틸지주", "세아제강지주"}   # 모회사 참고용 (현대제철은 자체 대상)
MAX_SHOW = 8             # md에 회사별로 보여 줄 문장 수
BEFORE, AFTER = 70, 110  # 키워드 앞뒤 글자 수

EU_COUNTRIES = ["독일", "프랑스", "이탈리아", "스페인", "네덜란드", "벨기에", "폴란드", "체코",
                "헝가리", "슬로바키아", "스웨덴", "핀란드", "덴마크", "오스트리아", "포르투갈",
                "루마니아", "슬로베니아", "크로아티아", "그리스", "불가리아", "아일랜드"]
KEYWORDS = re.compile(r"유럽|구주|유로|(?<![A-Za-z])EU(?![A-Za-z])|(?<![A-Za-z])EUR(?![A-Za-z])|"
                      + "|".join(EU_COUNTRIES))
SALES = re.compile(r"매출|수출|판매|납품|거래처|고객|수주|선적")
NUMBER = re.compile(r"\d{1,3}(,\d{3})+")
OUTLOOK = re.compile(r"전망|동향|예상|경기|위기|전쟁|규제|정책|인증")


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def clean(raw):
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def read_member(z, name):
    b = z.read(name)
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="ignore")


def snippets(zip_path):
    """(제목 위치, 키워드, 문장) 목록. 앞 문장 범위와 겹치는 키워드는 건너뛰고, 같은 문장은 한 번만"""
    out, seen = [], set()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            raw = read_member(z, member)
            parts = re.split(r"(<TITLE[^>]*>.*?</TITLE>)", raw, flags=re.S | re.I)
            title = ""
            for part in parts:
                if re.match(r"<TITLE", part, re.I):
                    title = clean(part)
                    continue
                text = clean(part)
                covered = -1
                for m in KEYWORDS.finditer(text):
                    if m.start() <= covered:
                        continue
                    covered = m.end() + AFTER - 30
                    s = text[max(0, m.start() - BEFORE): m.end() + AFTER]
                    k = s[20:120]
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append((title, m.group(0), s))
    return out


def priority(s):
    score = 0
    score += 3 if SALES.search(s) else 0
    score += 2 if len(NUMBER.findall(s)) >= 2 else 0
    score += 1 if "지역" in s else 0
    score -= 2 if OUTLOOK.search(s) else 0
    return score


def pick_report(g):
    for kind in ("사업보고서", "감사보고서"):
        h = g[g["kind"] == kind]
        if len(h):
            r = h.iloc[0]
            return kind, r["report_nm"], r["link"], r["corp_code"]
    return "", "", "", ""


def fetch_zip(corp_code, rcept_no, kind):
    """원문 zip 경로와 실제로 쓴 접수번호. 정정 공시에 파일이 없으면 다른 판을 시도함"""
    try:
        return document_zip(rcept_no), rcept_no
    except RuntimeError as e:
        if "014" not in str(e):
            raise
    code = "A001" if kind == "사업보고서" else "F001"
    d = get_json("list", corp_code=corp_code, bgn_de="20260101", end_de=date.today().strftime("%Y%m%d"),
                 pblntf_detail_ty=code, last_reprt_at="N", page_count="100")
    for x in sorted(d.get("list", []), key=lambda x: x["rcept_no"], reverse=True):
        if x["rcept_no"] == rcept_no:
            continue
        try:
            return document_zip(x["rcept_no"]), x["rcept_no"]
        except RuntimeError as e:
            if "014" not in str(e):
                raise
    return None, ""


def main():
    links = pd.read_csv(LINKS, dtype=str).fillna("")
    rows, summary = [], []
    for name, g in links.groupby("name", sort=False):
        role = "모회사 참고" if key(re.sub(r"\(상장.*\)", "", name)) in PARENTS else "판정 대상"
        kind, report_nm, link, corp_code = pick_report(g)
        if not link:
            summary.append(dict(name=name, role=role, report_nm="보고서 없음", link="", hits=0))
            continue
        rcept_no = link.split("rcpNo=")[1]
        try:
            path, used = fetch_zip(corp_code, rcept_no, kind)
        except RuntimeError as e:
            summary.append(dict(name=name, role=role, report_nm=f"{report_nm} (오류: {e})", link=link, hits=0))
            print(f"{name} | 오류: {e}")
            continue
        if path is None:
            summary.append(dict(name=name, role=role, report_nm=f"{report_nm} (원문 파일 없음)", link=link, hits=0))
            print(f"{name} | 원문 파일 없음")
            continue
        if used != rcept_no:
            report_nm = f"{report_nm} → 원문은 {used}"
            link = link.split("rcpNo=")[0] + "rcpNo=" + used
        found = snippets(path)
        for title, kw, s in found:
            rows.append(dict(name=name, role=role, report_nm=report_nm, link=link, section=title,
                             keyword=kw, priority=priority(s), snippet=s))
        summary.append(dict(name=name, role=role, report_nm=report_nm, link=link, hits=len(found)))
        print(f"{name} | {report_nm} | 문장 {len(found)}개")

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    lines = [f"# 제조1-5b EU 문장 추출 ({date.today()})", "",
             "- 회사별로 우선순위(매출·수출 단어, 숫자 표, '지역' 포함 가점 / 전망·규제 문장 감점)가 높은 문장만 보여 줌",
             f"- 전체 문장은 {OUT_CSV.name}에 있음", ""]
    for s in summary:
        lines.append(f"## {s['name']} ({s['role']})")
        lines.append(f"- {s['report_nm']} {s['link']}")
        sub = df[df["name"] == s["name"]] if len(df) else df
        if not len(sub):
            lines += ["- 찾은 문장 없음", ""]
            continue
        sub = sub.sort_values("priority", ascending=False).head(MAX_SHOW)
        lines.append(f"- 문장 {s['hits']}개 중 {len(sub)}개 표시")
        for i, r in enumerate(sub.itertuples(), 1):
            lines.append(f"{i}. [{r.section}] ({r.keyword}) {r.snippet}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n회사 {len(summary)}곳, 문장 {len(df)}개 → {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()