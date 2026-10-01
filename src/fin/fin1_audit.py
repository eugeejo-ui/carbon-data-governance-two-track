"""DART 원문 조회 — 감사보고서 주주 현황 · 인수자 공시 목록 (금융1-3C 소유 구조 확인용)

- 최대주주 현황 API(hyslrSttus)는 사업보고서를 내는 회사만 됨. 사업보고서가 없는 비상장 금융회사는
  외부감사 대상이라 감사보고서를 냄 → 감사보고서 원문 주석(일반사항)의 주주 현황 표를 읽음 (근거 1등급)
- 쓰는 API (OpenDART)
  - 공시검색 list.json : 회사별 감사보고서 접수번호 찾기 (공시유형 F = 외부감사관련)
  - 공시서류원본파일 document.xml : 접수번호로 원문 ZIP 받기
- 이 프로젝트에서 처음 쓰는 API라, 응답을 data/raw/dart_docs/에 그대로 저장하고
  표를 못 찾으면 "주주"가 들어간 문장을 그대로 보여 줌 (사람이 원문으로 확인)
- 인증키는 .env의 DART_API_KEY에서 읽음. 저장 파일 이름·출력에는 키를 남기지 않음
"""
from pathlib import Path
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "dart_docs"
BASE = "https://opendart.fss.or.kr/api"
SEARCH_FROM = "20250101"                       # 감사보고서 검색 시작일 (2025 사업연도 보고서가 2026년 3~4월 접수)
PCT = re.compile(r"^\s*(\d{1,3}(?:\.\d+)?)\s*%?\s*$")


def dart_key():
    k = os.environ.get("DART_API_KEY", "").strip()
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DART_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        raise SystemExit(".env에 DART_API_KEY가 없음")
    return k


def _get(url, timeout=60):
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"DART 호출 실패 — {type(last).__name__}")


def dart_json(endpoint, cache=True, **params):
    """OpenDART JSON — cache=False면 매번 새로 받음 (공시 목록처럼 바뀌는 자료)"""
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    path = CACHE / f"{endpoint}_{tag}.json"
    if cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    q = urllib.parse.urlencode({"crtfc_key": dart_key(), **params})
    body = json.loads(_get(f"{BASE}/{endpoint}.json?{q}").decode("utf-8"))
    if cache and body.get("status") in ("000", "013"):
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return body


def latest_audit(corp_code):
    """가장 최근 감사보고서 (접수번호, 보고서명, 접수일) — 없으면 ("", 사유, "")"""
    today = dt.date.today().strftime("%Y%m%d")
    d = dart_json("list", corp_code=corp_code, bgn_de=SEARCH_FROM, end_de=today,
                  pblntf_ty="F", page_count="100")
    if d.get("status") != "000":
        return "", f"감사보고서 목록 없음({d.get('status', '')})", ""
    reps = [r for r in d.get("list") or [] if "감사보고서" in str(r.get("report_nm", ""))]
    if not reps:
        return "", "감사보고서 목록 없음", ""
    reps.sort(key=lambda r: str(r.get("rcept_no", "")), reverse=True)
    sep = [r for r in reps if "연결" not in str(r.get("report_nm", ""))]   # 별도 감사보고서를 먼저 봄
    r = (sep or reps)[0]
    return str(r["rcept_no"]), str(r.get("report_nm", "")).strip(), str(r.get("rcept_dt", ""))


def document_texts(rcept_no):
    """원본 ZIP 안의 XML 문서들을 글자로 돌려줌. ZIP이 아니면 (None, 응답 앞부분)"""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{rcept_no}.zip"
    if not path.exists():
        q = urllib.parse.urlencode({"crtfc_key": dart_key(), "rcept_no": rcept_no})
        raw = _get(f"{BASE}/document.xml?{q}", timeout=120)
        if not zipfile.is_zipfile(io.BytesIO(raw)):
            return None, raw[:300].decode("utf-8", "replace")
        path.write_bytes(raw)
    out = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            b = z.read(n)
            for enc in ("utf-8", "cp949", "euc-kr"):
                try:
                    out.append(b.decode(enc))
                    break
                except UnicodeDecodeError:
                    continue
    return out, ""


def _plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def tables(xml):
    """XML 문서의 표 → [[셀 글자, ...], ...] 목록"""
    out = []
    for t in re.findall(r"<TABLE\b.*?</TABLE>", xml, flags=re.S | re.I):
        rows = []
        for tr in re.findall(r"<TR\b.*?</TR>", t, flags=re.S | re.I):
            cells = [_plain(c) for c in re.findall(r"<T[DHEU]\b[^>]*>(.*?)</T[DHEU]>", tr, flags=re.S | re.I)]
            if any(cells):
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


NAME = r"([A-Za-z가-힣0-9][A-Za-z가-힣0-9\.\,\(\)&'\-/ ]{1,90}?)"
# 2026-10-01 실제 감사보고서 16건에서 확인한 서술 형식 (앞에서부터 시도)
SENTENCES = [
    (re.compile(r"주주는\s*(?:[가-힣]{1,10}의\s*)?" + NAME + r"\s*\(\s*지분율\s*(\d{1,3}(?:\.\d+)?)\s*%\s*\)"), "주주는 ○○ (지분율 ○%)"),
    (re.compile(NAME + r"(?:가|이)\s*(?:당사|회사)의\s*지분(?:을|의)?\s*(\d{1,3}(?:\.\d+)?)\s*%\s*(?:를|을)?\s*소유"), "○○가 회사의 지분을 ○% 소유"),
    (re.compile(NAME + r"(?:가|이)\s*(\d{1,3}(?:\.\d+)?)\s*%\s*(?:\([^)]{0,30}\))?\s*의?\s*지분을\s*(?:소유|보유)"), "○○가 ○%의 지분을 소유"),
    (re.compile(r"발행주식\s*[\d,]+\s*주\s*(?:전체|전부)를\s*(?:[가-힣]{1,10}\s*법인인\s*)?" + NAME + r"(?:가|이)\s*(?:소유|보유)"), "발행주식 전체를 ○○가 소유"),
    (re.compile(r"자본금은\s*전액\s*" + NAME + r"\s*(?:본점)?\s*(?:으로|로)부터\s*(?:조달|출자|납입)"), "자본금 전액을 ○○로부터 조달"),
    (re.compile(r"최대주주는\s*" + NAME + r"(?:로서|으로서|이며|이고|이다|입니다)(.{0,80}?)(\d{1,3}(?:\.\d+)?)\s*%"), "최대주주는 ○○로서 ○%"),
]
PARENT = re.compile(r"(?:지배회사는|지배기업은|지배회사|지배기업)\s+(?![의은는이가])" + NAME + r"(?:이며|입니다|이고|\s(?:기타|최상위|종속|관계))")


def _num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _from_table(rows):
    """주주 표 → (최대주주, 지분율). 머리글 줄을 찾아 칸을 맞추고, 지분율 칸이 없으면 주식수로 계산
    실제 원문 형식: 첫 줄이 "(단위: 주)" 제목 / 머리글 두 줄(당기말·전기말 아래 주식수·지분율) / 우선주 이어짐 줄"""
    ns = [[re.sub(r"\s", "", c) for c in r] for r in rows]
    h = next((i for i, r in enumerate(ns[:4]) if any(re.search(r"주주|성명", c) for c in r)), None)
    if h is None:
        return None
    heads = [ns[h]]
    b0 = h + 1
    if b0 < len(ns) and not any(_num(c) is not None for c in ns[b0]):      # 머리글 두 번째 줄
        heads.append(ns[b0])
        b0 += 1
    body = [r for r in rows[b0:] if r and re.search(r"[A-Za-z가-힣]", r[0])
            and not re.search(r"^(합계|계|소계|기타|보통주|우선주)$", re.sub(r"\s", "", r[0]))]
    if not body:
        return None
    width = max(len(r) for r in body)

    def col(pat):
        for hd in reversed(heads):                                           # 아래 줄 머리글을 먼저
            for j, c in enumerate(hd):
                if re.search(pat, c):
                    return j + (width - len(hd))                             # 칸 수가 모자라면 오른쪽 정렬
        return None
    rc = col(r"지분율|소유비율|비율|%")
    if rc is not None:
        best = None
        for r in body:
            v = _num(r[rc]) if rc < len(r) else None
            if v is not None and 0 < v <= 100 and (best is None or v > best[1]):
                best = (r[0].strip(), v)
        if best:
            return best
    qc = col(r"보통주|주식수")
    if qc is None:
        return None
    q = [(r[0].strip(), _num(r[qc]) if qc < len(r) else None) for r in body]
    q = [(n, v) for n, v in q if v]
    tot = sum(v for _, v in q)
    if not tot:
        return None
    n, v = max(q, key=lambda x: x[1])
    return n, round(v / tot * 100, 2)


CUT = re.compile(r"다\.\s|현재\s|지분이\s|되어\s|되었으며\s|으며\s|하였고,?\s|로\s매각")


def _clean_name(x):
    """서술 문장에서 잡은 이름의 앞쪽 군더더기를 뗌 — 마지막 문장 경계 뒤만 남김"""
    parts = CUT.split(x)
    return parts[-1].strip(" ,") if parts else x.strip(" ,")


def shareholder_table(texts):
    """주주 현황 → (최대주주, 지분율, 근거 요약). 표 → 서술 문장 → 지배회사(지분율 없음) 순서로 찾음"""
    for xml in texts:
        for rows in tables(xml):
            flat = re.sub(r"\s", "", " ".join(" ".join(r) for r in rows))
            if "주주" not in flat or not re.search(r"지분율|소유비율|주식수|%", flat):
                continue
            got = _from_table(rows)
            if got:
                return got[0], got[1], ("표: " + " / ".join(" | ".join(r) for r in rows[:4]))[:300]
    plain = " ".join(_plain(x) for x in texts)
    for pat, label in SENTENCES:
        ms = list(pat.finditer(plain))
        if not ms:
            continue
        # 같은 형식이 여러 번이면 지분 이동 이력일 수 있음 — "현재"가 붙은 문장, 없으면 마지막 문장 (메트라이프 사례)
        cur = [x for x in ms if "현재" in plain[max(0, x.start() - 40): x.start() + len(x.group(0))][:60 + len(x.group(1))]]
        m = cur[-1] if cur else ms[-1]
        name = _clean_name(m.group(1))
        rate = 100.0 if label in ("발행주식 전체를 ○○가 소유", "자본금 전액을 ○○로부터 조달") else float(m.groups()[-1])
        if rate <= 100:
            return name, rate, f"문장({label}): " + m.group(0)[:260]
    m = PARENT.search(plain)
    if m:
        return m.group(1).strip(" ,"), None, "지배회사만 확인(지분율 표기 없음): " + m.group(0)[:200]
    m = re.search(r".{0,120}(최대주주|주요 주주|주주는).{0,160}", plain)
    return "", None, (m.group(0)[:300] if m else "")


def audit_owner(corp_code):
    """감사보고서 원문에서 최대주주 — dict(owner, rate, report, rcept_no, rcept_dt, status, snippet)"""
    rno, rnm, rdt = latest_audit(corp_code)
    if not rno:
        return dict(owner="", rate=None, report="", rcept_no="", rcept_dt="", status=rnm, snippet="")
    texts, err = document_texts(rno)
    if texts is None:
        return dict(owner="", rate=None, report=rnm, rcept_no=rno, rcept_dt=rdt,
                    status=f"원본파일 아님 — {err[:80]}", snippet="")
    owner, rate, snip = shareholder_table(texts)
    st = ("ok" if owner and rate is not None
          else "지배회사만 확인(지분율 표기 없음)" if owner
          else "표 못 찾음 — 문장 확인" if snip else "주주 내용 못 찾음")
    return dict(owner=owner, rate=rate, report=rnm, rcept_no=rno, rcept_dt=rdt, status=st, snippet=snip)


# 인수자가 상장사인 매각 건 — 인수자 공시 목록에서 관련 공시를 찾음 (근거 1등급)
# 이름은 DART 등록명이 바뀔 수 있어 종목코드로 찾음 (한화생명 — 2026-10-01 이름으로 못 찾은 사례)
PENDING_ACQUIRERS = [
    ("071050", "한국금융지주", r"케이디비생명|KDB생명|우선협상|자율공시|투자판단|타법인주식및출자증권취득"),
    ("088350", "한화생명", r"애큐온|우선협상|자율공시|투자판단|타법인주식및출자증권취득|조회공시"),
]
PENDING_FROM = "20260601"


def acquirer_disclosures(corp_codes_df):
    """[(인수자, 접수일, 보고서명, 접수번호)] — 공시 목록은 매번 새로 받음"""
    out = []
    today = dt.date.today().strftime("%Y%m%d")
    for stock, nm, pat in PENDING_ACQUIRERS:
        hit = corp_codes_df[corp_codes_df["stock_code"].astype(str).str.strip() == stock]
        if not len(hit):
            out.append((nm, "", f"DART 고유번호 목록에서 종목코드 {stock}를 못 찾음", ""))
            continue
        d = dart_json("list", cache=False, corp_code=hit.iloc[0]["corp_code"], bgn_de=PENDING_FROM,
                      end_de=today, page_count="100")
        for r in d.get("list") or []:
            if re.search(pat, str(r.get("report_nm", ""))):
                out.append((nm, str(r.get("rcept_dt", "")), str(r.get("report_nm", "")).strip(),
                            str(r.get("rcept_no", ""))))
    return out
