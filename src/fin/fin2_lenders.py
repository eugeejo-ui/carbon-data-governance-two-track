"""금융2-2 ③-3 CBAM 연결 — 제조 94곳 차입금 주석에서 차입처별 금액을 읽음

- 대상: data/processed/mfg2_rank.csv (제조-2 순위표 94곳), 고유번호는 mfg2_base.csv
- 원문: 2026년에 낸 최신 사업보고서(없으면 감사보고서) 원본파일 — dart_api.document_zip (제조-2 캐시 재사용)
- 어느 재무제표를 읽나 (그 회사 자신의 차입 = 별도를 먼저)
  1) 사업보고서 zip 안의 별도 "감사보고서" 첨부 파일
  2) 없으면 사업보고서 본문의 "재무제표 주석" 구간 (연결 주석 구간은 건너뜀 — 포스코)
  3) 감사보고서만 내는 회사는 별도 "감사보고서"를 먼저, 없으면 "연결감사보고서" (doc_basis에 표시)
- 표 고르기 (2026-10-01 실제 원문 7건에서 확인한 형식)
  - 표 바로 앞 글에 "차입금" 또는 "사채"가 있고, 파생상품·약정한도·지급보증·리스 문맥이 아님
  - 머리글에 차입처(금융기관·대출기관)와 기간(당기말·금액·(당)·날짜)이 있음. 약정한도·계약금액 표는 뺌
  - 전기말만 따로 보여 주는 표는 뺌
- 금액: 행에서 "금액처럼 생긴 칸"(숫자·괄호·"-") 중 끝에서 두 번째가 당기말 (당기 → 전기 순).
  이자율(%·~·소수)과 날짜는 금액에서 뺌. 외화표(외화금액·원화금액)는 당기 원화금액을 씀
- 단위: 표 첫 줄·앞 글의 "(단위: 천원)" 또는 머리글의 "(원화: 원)"
- 차입처: 법인 표기·"(*)"를 떼고 명단(fin_list.csv) 계정으로 맞춤. "○○ 등"·"○○ 외"는 다른 은행 몫이 섞인
  금액이라 includes_others로 표시. 사채·회사채는 직접금융, 외국 은행·공단·조합은 따로 분류
- 검산: 회사별로 읽은 합계를 제조-2의 DART 재무제표 API 차입금(mfg_bank_borrowing.csv, 35곳)과 비교

출력
  - data/processed/fin_mfg_lenders.csv : 회사 × 차입처 × 금액 (행 단위, 근거 표 번호 포함)
  - data/processed/fin_mfg_lender_check.csv : 회사별 읽은 합계·검산·문서 기준
"""
from pathlib import Path
import re
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from fin.fin1_list import key  # noqa: E402
from fin.fin1_audit import _plain, tables  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "fin_mfg_lenders.csv"
OUT_CHECK = PROC / "fin_mfg_lender_check.csv"
# 회사 한 곳에만 있는 표 모양은 코드를 고치지 않고 원문을 보고 적음 (2026-10-01 원칙 — 고치면 다른 회사가 깨짐)
# 칸: account, action(replace=그 회사 행을 통째로 바꿈 / add=더함 / none=차입금 없음 확정), lender, kind, amount_eok,
#     check_eok(재무상태표에 차입 줄이 없을 때 원문에서 확인한 기준값 — 대호에이엘), source(접수번호·주석·표), note
MANUAL_FILE = MANUAL / "fin_mfg_lenders_manual.csv"

CTX = re.compile(r"차입금|사채")
BAD_CTX = re.compile(r"파생|통화선도|스왑|약정|한도|지급보증|공급자금융|리스부채|담보로 제공|이자율이|100bp|순차입금|자본조달비율|"
                     r"보고기간\s*후|후속\s*사건|특수관계자|채권\s*[ㆍ·및]?\s*채무|이자부|금융부채|고정이자율|변동이자율|"
                     r"담보(?!부)|변동\s*내역|증감\s*내역")   # 변동내역(기초·상각·기말)은 잔액 표가 아님 (TCC스틸 전환사채)          # "제공된 담보자산"·"담보제공내역" (남선알미늄·대한시멘트). "담보부차입금"은 대출 종류라 예외   # 보고기간 후 새로 발행한 사채는 기말 잔액이 아님 (현대제철 42번 주석)
HEAD_LENDER = re.compile(r"차입처|금융기관|대출기관|차입기관")
HEAD_PERIOD = re.compile(r"당기|금액|\(당\)|2025\.12\.31|2025년\s*12월|기말|잔액")   # "2025년 12월 31일"(와이케이스틸)
HEAD_BAD = re.compile(r"약정한도|계약금액|계약잔액|통화선도|한도액|채권최고액|설정액")   # 담보 전용 표의 칸만 — 차입처 표 안 "담보제공내역" 칸은 예외(대한제강)
# 합계·소계 행 — "단기차입금 합계", "장기차입금 소계"처럼 끝에 붙는 경우도 뺌. "유동성장기차입금"·"유동성분류"는
# 장기차입금 중 1년 안에 갚을 몫이라 장기 표에 이미 들어 있음 (KBI동양철관·케이피에프 이중 계산, 2026-10-01)
SKIP_ROW = re.compile(r"(합계|소계|총계|계)$|^(계|차감|조정|가산|\(\*|\(주\d|주\d*\)|\(?단위)")   # "은행 차입금 계"(에스엔엔씨)
# 각주 "(주1)"만 뺌 — "(주)국민은행"처럼 법인 표기로 시작하는 은행 이름은 남김 (삼표시멘트 574억 누락, 2026-10-01)
# "유동성장기차입금"처럼 은행 이름 없이 금액만 있는 행은 장기 표와 겹치는 몫이라 뺌(KBI). 은행 이름이 있으면 진짜 차입 행(대창스틸)
CURRENT_ROW = re.compile(r"^(유동성|1년이내)")
# 전환사채·신주인수권부사채 표의 구성 행 — 장부금액(부채요소)만 차입으로 봄 (삼아알미늄)
BOND_PART = re.compile(r"발행가액|액면|자본요소|전환권|상환할증|신주인수권조정|할증금|할인")
# 첫 칸이 대출 종류면 차입처 칸이 위 행과 합쳐진 것 — 위 행의 차입처를 이어받음 (KG스틸 장기차입금 표)
LOAN_KIND = re.compile(r"자금|대출|차월|론$|Loan|LOAN|Usance|USANCE|무역금융|구매|수출|수입|당좌|할인|팩토링|시설|운전|일반|긴급|"
                       r"신디케이티드|한도|어음|매출채권|외담대|L/?C|신용장|기한부|D/A|D/P|NEGO|Nego|네고")   # 삼보산업 "기한부L/C"
LENDERISH = re.compile(r"은행|뱅크|금융(?!$)|캐피탈|보험|증권|공사|공단|기금|조합|유동화|\(유\)|Bank|BANK|모건|아그리콜|사채|본드|"
                       r"Bond|(등|외)$|금고|신협|카드")
AMT = re.compile(r"^\(?-?[\d,]+\)?$|^[-–]$")
UNIT = re.compile(r"(?:단위|원화)\s*[:：]?\s*(?:[^)\]]{0,20}?[,\s/])?(백만원|천원|억원|원)(?![가-힣])")   # "원화"의 "원"은 단위 아님(세아제강)   # "(원화: 천원)"·"(단위: 달러, 천원)"(세아씨엠)
FX_CELL = re.compile(r"^([\d,]+)\([\d,.]+\)$")                       # "8,212,383(894,955,870)" — 원화(외화)
UNIT_X = {"원": 1, "천원": 1e3, "백만원": 1e6, "억원": 1e8}
SEP_TITLE = re.compile(r"^\d+\.\s*재무제표\s*주석$")
MARK = re.compile(r"(?:^|[\s.)])(?:\(\d{1,2}\)|[①-⑳]|[가-하]\.|\d{1,2}\.\s|\d{1,2}\)\s)")   # "…있습니다.(3)"처럼 붙은 것도 (남선알미늄)
# 자본관리 표의 회사 자신이 밝힌 차입금 총계 — 검산 기준 (제조-2 API 값이 이중 계산된 회사가 있음, 조일알미늄)
TOTAL_ROW = re.compile(r"^(총차입금|차입금총계|차입금및사채총계|차입금및사채|차입금\(사채포함\)|차입금및사채합계|이자부부채|차입금계)$")


SUBHEAD_CELL = re.compile(r"이자율|금액|당기|전기|통화|외화|원화|유동|비유동|만기|^\d{4}|^\(")


def is_subheader(row):
    """머리글 아래 둘째 머리글 줄 — 금액·은행 이름 없이 '당기말·전기말', '유동·비유동', '연이자율·금액' 같은 칸만 (쌍용씨앤이)"""
    cells = [re.sub(r"\s", "", c) for c in (row or []) if c.strip()]
    return bool(cells) and not any(AMT.match(c) or STRICT_BANK.search(c) for c in cells) and \
        all(SUBHEAD_CELL.search(c) or re.match(r"^[\d.\-~]+$", c) for c in cells)


def context(pre):
    """표 앞 글에서 마지막 소제목 표시((1)·①·가.·15.) 뒤만 — 이전 문단의 말에 걸리지 않게"""
    ms = list(MARK.finditer(pre))
    return pre[ms[-1].start():] if ms else pre[-100:]


STRICT_BANK = re.compile(r"은행|뱅크|금융공사|공단|캐피탈|증권|보험|Bank|BANK|모건|아그리콜|조합|금고")
# 종류별 합계 요약표 — 첫 칸이 차입 종류 이름이면 은행별 표가 아님 (동국제강·한일시멘트 "차입금의 내역" 첫 표)
SUMMARY_ROW = re.compile(r"^(단기차입금|장기차입금|사채|단기사채|차입금|유동성장기차입금|유동성사채|전환사채|신주인수권부사채)(\(\*\d*\))?$")
# 종류 이름과 정확히 같은 행만 — 사채 표 안의 "유동성 대체"·"비유동 사채" 같은 조정 행은 해당 없음 (세아제강)


def bank_col(rows, start):
    """머리글에 차입처 말이 없을 때 — 은행·공사·공단 이름이 나오는 칸 (조일알미늄 '차입종류' 오타). 요약표면 None"""
    body = [r for r in rows[start:] if r]
    if sum(1 for r in body if SUMMARY_ROW.match(re.sub(r"\s", "", r[0]))) >= 2:
        return None
    cnt = {}
    for r in body:
        for j, c in enumerate(r):
            if STRICT_BANK.search(c) and not SKIP_ROW.search(re.sub(r"\s", "", c)):
                cnt[j] = cnt.get(j, 0) + 1
    return max(cnt, key=cnt.get) if cnt else None

BANK_ALIAS = {
    "산업은행": "한국산업은행", "KDB산업은행": "한국산업은행", "수출입은행": "한국수출입은행",
    "기업은행": "중소기업은행", "IBK기업은행": "중소기업은행", "KEB하나은행": "하나은행",
    "KB국민은행": "국민은행", "NH농협은행": "농협은행", "농협": "농협은행", "대구은행": "iM뱅크",
    "아이엠뱅크": "iM뱅크", "SC제일은행": "한국스탠다드차타드은행", "SC제일": "한국스탠다드차타드은행",
    "스탠다드차타드은행": "한국스탠다드차타드은행", "씨티은행": "한국씨티은행"}
FOREIGN = re.compile(r"제이피모건|JP\s?Morgan|JPM|모건|HSBC|홍콩상하이|Citi|CITI|크레디아그리콜|Credit\s?Agricole|CA-?CIB|"
                     r"Mizuho|미즈호|MUFG|미쓰비시|SMBC|스미토모|BNP|비엔피|소시에테|Societe|도이치|Deutsche|"
                     r"ING|ANZ|DBS|중국은행|Bank of China|공상은행|건설은행|Natixis|나티시스|Bank|BANK", re.I)
BOND = re.compile(r"사채|회사채|공모|사모|CP|기업어음|전자단기|단기사채|본드|Bond|BOND|채권")
PUBLIC = re.compile(r"공단|공사|진흥원|기금|재단|정부|중소벤처")
FUND = re.compile(r"조합|펀드|투자")


def clean_lender(s):
    s = re.sub(r"\(\*\d*\)|\(주\d*\)|\*\d*", "", str(s))
    s = re.sub(r"\(주\)|㈜|주식회사|\s+", "", s)
    others = bool(re.search(r"(등|외)(\d+(개|곳|개사)?)?$", s))      # "산업은행 외 2"(대창스틸)·"하나은행 등 3개"
    s = re.sub(r"(등|외)(\d+(개|곳|개사)?)?$", "", s)
    return s, others


def lender_class(name, have):
    canon = BANK_ALIAS.get(name, name)
    if key(canon) in have:
        return have[key(canon)], "명단 금융회사"
    if BOND.search(name):
        return "", "사채(직접금융)"
    if FOREIGN.search(name):
        return "", "외국 금융회사"
    if PUBLIC.search(name):
        return "", "공공기관·정책기금(명단 밖)"
    if FUND.search(name):
        return "", "투자조합 등"
    if re.search(r"은행|캐피탈|보험|증권|저축|금고|신협", name):
        return "", "금융회사(명단 밖)"
    return "", "기타(확인 필요)"


def files_of(zip_path):
    out = []
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            b = z.read(n)
            for enc in ("utf-8", "cp949", "euc-kr"):
                try:
                    x = b.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                x = b.decode("utf-8", "replace")
            m = re.search(r"<DOCUMENT-NAME[^>]*>(.*?)</DOCUMENT-NAME>", x, re.S)
            out.append((n, x, re.sub(r"\s+", "", m.group(1)) if m else ""))
    return out


def choose(files):
    """(본문, 시작, 끝, 기준) — 별도를 먼저"""
    for n, x, dn in files:
        if dn == "감사보고서":
            return x, 0, len(x), "별도 감사보고서"
    for n, x, dn in files:
        titles = [(m.start(), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip())
                  for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
        for i, (pos, t) in enumerate(titles):
            if SEP_TITLE.match(t):
                end = next((p for p, tt in titles[i + 1:] if re.match(r"^(\d+\.|[IVX]+\.)", tt)), len(x))
                return x, pos, end, "사업보고서 별도 주석"
    n, x, dn = files[0]
    return x, 0, len(x), (dn or "원문") + ("(별도 없음)" if "연결" in dn else "")


# ── 차입금 주석 위치 찾기 (2026-10-01 개정: 문서 전체를 훑지 않고 위치부터 특정) ──────────────
# 1 맨 앞 목차·첫 주석 제목으로 주석 구역 시작 → 2 재무상태표 "주석" 칸(색인)의 차입 항목 번호
# → 3 (색인이 없으면) 주석 목차(번호 사슬)의 차입·사채 제목 → 4 그 주석 구간의 표만 읽음
# → 5 구간 안 "주석 ○ 참조"도 차입·사채·금융부채 주석이면 함께 → 6 모두 실패하면 전체 훑기(안전망)
# 원문 44건 시험: 색인으로 25곳, 색인 없는 4곳은 목차로 — 차입금 있는 29곳 전부 위치 특정
NOTE_CELL = re.compile(r"^\s*\d{1,2}(\s*[,ㆍ·]\s*\d{1,2})*\s*$")
DEBT_TITLE = re.compile(r"차입|사채")
REF_TITLE = re.compile(r"차입|사채|금융부채")
FIRST_NOTE = re.compile(r"(?<![\d.,%])1\s*\.\s*(?:<[^>]+>\s*)*(일반|회사|보고기업|당사의?\s*개요|연결회사|기업\s*개요)")


def _heading(n):
    return re.compile(rf"(?<![\d.,%])({n})\s*\.\s*(?:<[^>]+>\s*)*([가-힣][가-힣ㆍ·, 및]{{0,18}})")


def _outside(pos, spans):
    return not any(a <= pos < b for a, b in spans)


def note_ranges(x, s, e):
    """차입·사채 주석 구간 [(시작, 끝, 표시)], 찾은 방법"""
    spans = [(m.start(), m.end()) for m in re.finditer(r"<TABLE\b.*?</TABLE>", x[s:e], flags=re.S | re.I)]
    spans = [(a + s, b + s) for a, b in spans]
    fm = next((m for m in FIRST_NOTE.finditer(x, s, e) if _outside(m.start(), spans)), None)
    notes_start = fm.start() if fm else s

    def find_title(k, pat, start=None):
        for m in _heading(k).finditer(x, start if start is not None else notes_start, e):
            if _outside(m.start(), spans) and pat.search(m.group(2)[:9]):   # 제목 뒤에 본문이 붙은 경우(담보제공자산당기말…차입)
                return m
        return None

    def end_of(k, pos):
        for step in (1, 2, 3):
            for m in re.finditer(rf"(?<![\d.,%])({k + step})\s*\.\s*(?:<[^>]+>\s*)*[가-힣]", x[pos + 5:e]):
                if _outside(pos + 5 + m.start(), spans):
                    return pos + 5 + m.start()
        return e

    # 2 재무상태표 색인 — 주석 구역 앞의 표(재무제표 본표)에서 차입·사채 항목의 주석 번호
    nums = set()
    for a, b in spans:
        if fm and a > notes_start:
            break
        tb = tables(x[a:b])
        for r in (tb[0] if tb else []):
            if r and DEBT_TITLE.search(r[0]) and len(r) >= 2 and NOTE_CELL.match(r[1]):
                nums |= {int(k) for k in re.findall(r"\d+", r[1])}
    found, method = {}, ""
    for k in sorted(nums):
        m = find_title(k, DEBT_TITLE)
        if m:
            found[k] = m
    if found:
        method = "색인"
    else:                                          # 3 주석 목차(번호 사슬)
        chain = []
        # 1번 제목 앞의 문단 표시(>)까지 포함하도록 조금 앞에서 자름 (그대로 자르면 1번을 못 찾아 사슬이 시작되지 않음)
        seg_nt = re.sub(r"<TABLE\b.*?</TABLE>", lambda mm: " " * len(mm.group(0)),
                        x[max(s, notes_start - 300):e], flags=re.S | re.I)
        for m in re.finditer(r">\s*(\d{1,2})\s?\.\s?([가-힣][^<(:\d]{1,28})", seg_nt):
            k = int(m.group(1))
            if (not chain and k == 1) or (chain and k == chain[-1][0] + 1):
                chain.append((k, m.group(2)))
        if len(chain) >= 8:                            # 주석이 적은 짧은 보고서도 인정 (진양특수강 9개)
            for k, t in chain:
                if DEBT_TITLE.search(t[:9]) and "차입원가" not in t:
                    mm = find_title(k, DEBT_TITLE)
                    if mm:
                        found[k] = mm
            method = "목차" if found else "목차 — 차입금 주석 없음"
    # 5 참조 따라가기
    for k, m in list(found.items()):
        body = _plain(x[m.start():end_of(k, m.start())])
        for r_ in re.findall(r"주석\s*(\d{1,2})(?![.\d]*\d)", body):
            r_ = int(r_)
            if r_ not in found:
                mm = find_title(r_, REF_TITLE)
                if mm and DEBT_TITLE.search(mm.group(2)[:9]):
                    found[r_] = mm
                    method += f" + 참조 {r_}"
    out = [(m.start(), end_of(k, m.start()), f"{k}. {m.group(2).strip()}") for k, m in sorted(found.items())]
    return out, method


def to_num(c):
    c = str(c).strip()
    if c in ("-", "–", ""):
        return 0.0
    neg = c.startswith("(") and c.endswith(")")
    try:
        v = float(c.strip("()").replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


def is_rate(c):
    return "%" in c or "~" in c or bool(re.match(r"^\d{1,2}\.\d+$", c.strip()))


def parse_doc(zip_path, have):
    """원문 하나 → (행 목록, 문서 기준 · 위치 찾은 방법)"""
    x, s, e, basis = choose(files_of(zip_path))
    ranges, method = note_ranges(x, s, e)
    if method == "목차 — 차입금 주석 없음":
        return [], f"{basis} · 차입금 주석 없음"
    where = (f"{method}: " + ", ".join(t for _, _, t in ranges)) if ranges else "전체 훑기(위치 못 찾음)"
    basis = f"{basis} · {where}"
    out, deduct_tables, summary_bonds, summary_tno = [], set(), {}, {}
    for ti, m in enumerate(re.finditer(r"<TABLE\b.*?</TABLE>", x, flags=re.S | re.I)):
        if m.start() < s or m.start() > e:
            continue
        if ranges and not any(a <= m.start() < b for a, b, _ in ranges):
            continue                                   # 차입·사채 주석 구간 밖의 표는 보지 않음
        pre = _plain(x[max(0, m.start() - 600):m.start()])[-200:]
        near = context(pre)
        if not CTX.search(near) or BAD_CTX.search(near):
            continue
        if re.search(r"전기말|\(전\)\s*기", near[-70:]) and not re.search(r"당기|\(당\)", near[-70:]):
            continue
        tb = tables(m.group(0))
        if not tb:
            continue
        rows = tb[0]
        if ranges or CTX.search(near):                   # 종류별 구성내역 요약표 — 사채 금액만 기록해 둠 (대한시멘트·TCC스틸)
            summ = [r for r in rows if r and SUMMARY_ROW.match(re.sub(r"\s", "", r[0]))]
            if len(summ) >= 2 and not any(HEAD_LENDER.search(re.sub(r"\s", "", " ".join(r))) for r in rows[:4]):
                um0 = UNIT.search(" ".join(" ".join(r) for r in rows[:2]) + " " + pre)
                sub0 = "".join(re.sub(r"\s", "", c) for c in (rows[2] if len(rows) > 2 else []) + (rows[1] if len(rows) > 1 else []))
                for r in summ:
                    lab = re.sub(r"\s|\(\*\d*\)", "", r[0])
                    typ = "전환사채" if "전환" in lab else "신주인수권부사채" if "신주인수권" in lab else "교환사채" if "교환" in lab \
                        else "사채" if "사채" in lab else None
                    if not typ or not um0:
                        continue
                    am = [to_num(c) for c in r[1:] if AMT.match(c.strip())]
                    am = [a for a in am if a is not None]
                    if not am:
                        continue
                    v = sum(am[:2]) if ("유동" in sub0 and "비유동" in sub0 and len(am) >= 4) else am[0]   # 당기 유동+비유동
                    summary_bonds[typ] = summary_bonds.get(typ, 0) + v * UNIT_X[um0.group(1)]
                    summary_tno.setdefault(typ, ti)
        hi = next((i for i, r in enumerate(rows[:4]) if HEAD_LENDER.search(re.sub(r"\s", "", " ".join(r)))), None)
        explicit = hi is not None                        # 머리글에 차입처가 분명히 있는 표
        bond_mode, li_guess = False, None
        if hi is None and re.search(r"차입금", near):     # 머리글 오타 등 — 은행 이름이 몰린 칸이 있으면 그 칸
            h2 = next((i for i, r in enumerate(rows[:4])
                       if HEAD_PERIOD.search(re.sub(r"\s", "", " ".join(r))) and len(r) >= 3), None)
            if h2 is not None:
                li_guess = bank_col(rows, h2 + 1)
                if li_guess is not None:
                    hi = h2
        if hi is None:                                   # 차입처 칸이 없는 사채 표 (현대제철)
            if not re.search(r"사채[^.]{0,20}(내역|현황)", near[-90:]) or re.search(r"차입금\s*(및|과)\s*사채|발행\s*(내역|조건)", near):
                continue                                 # "차입금 및 사채 내역"은 종류별 요약표 (한일시멘트)
            if sum(1 for r in rows if r and SUMMARY_ROW.match(re.sub(r"\s", "", r[0]))) >= 2:
                continue
            hi = next((i for i, r in enumerate(rows[:4])
                       if HEAD_PERIOD.search(re.sub(r"\s", "", " ".join(r))) and len(r) >= 3), None)
            if hi is None:
                continue
            bond_mode = True
        head = [re.sub(r"\s", "", c) for c in rows[hi]]
        if not explicit and not bond_mode and \
                sum(1 for r in rows[hi + 1:] if r and SUMMARY_ROW.match(re.sub(r"\s", "", r[0]))) >= 2 \
                and not any(STRICT_BANK.search(c) for r in rows[hi + 1:] for c in r):
            continue                                       # 은행 이름이 하나도 없는 종류별 요약표
        flat = "".join(head) + "".join(re.sub(r"\s", "", " ".join(r)) for r in rows[hi + 1:hi + 2])
        if not HEAD_PERIOD.search(flat) or HEAD_BAD.search(flat):
            continue
        um = UNIT.search(" ".join(" ".join(r) for r in rows[:hi + 1]) + " " + "".join(head)) or UNIT.search(pre)
        unit = um.group(1) if um else ("원" if "원화:원" in "".join(head) else "")
        if not unit:
            continue
        foreign = "외화금액" in flat or "원화금액" in flat
        # 외화금액(당기·전기) → 원화금액(당기·전기) 배치면 끝에서 두 번째, 당기(외화·원화) → 전기 배치면 두 번째 (세아제강·대한제강)
        col_major = bool(re.search(r"외화금액.*원화금액", "".join(head)))
        # 기간마다 유동·비유동 칸이 나뉜 표 — 당기 기간의 칸을 합침 (동국제강 장기차입금·사채)
        sub = "".join(re.sub(r"\s", "", c) for c in (rows[hi + 1] if hi + 1 < len(rows) else []))
        split = "유동" in sub and "비유동" in sub
        nxt = rows[hi + 1] if hi + 1 < len(rows) else []
        has_sub = is_subheader(nxt)
        # 머리글에 기간이 3개 이상(당기말·전기말·전기초)이면 당기는 끝에서 기간 수만큼 앞 (쌍용씨앤이)
        p3 = sum(1 for c in head if re.search(r"당기|전기|\(당\)|\(전\)|\d{4}\.\d{1,2}\.\d{1,2}|\d{4}년", c)
                 and not re.search(r"이자율|금리|율|만기|발행", c))     # "당기말연이자율"은 기간 칸 아님(두산에너빌리티)
        periods = max(1, sum(1 for c in head if re.search(r"\d{4}\.\d{1,2}\.\d{1,2}|\d{4}년|당기|전기|\(당\)|\(전\)", c)))
        li = 0 if bond_mode else li_guess if li_guess is not None else \
            next(i for i, c in enumerate(head) if HEAD_LENDER.search(c))
        width = len(head)
        sub_row = rows[hi + 1] if hi + 1 < len(rows) else []
        has_sub_early = is_subheader(sub_row)
        if has_sub_early:   # 금액이 당기·전기로 나뉘어 데이터 행이 머리글보다 김 — 폭은 가장 긴 데이터 행 (남선알미늄)
            width = max([width] + [len(r) for r in rows[hi + 2:] if len(r) >= 2])
        tail = near[-90:]
        pos = {k: tail.rfind(k) for k in ("단기", "장기", "사채")}
        kind = max(pos, key=pos.get) if max(pos.values()) >= 0 else "차입금"   # 가장 가까운 말
        prev = ""
        if any(r and re.search(r"(차감|유동성).{0,6}(대체|분류)|유동성대체", re.sub(r"\s", "", r[0])) for r in rows[hi + 1:]):
            deduct_tables.add(ti)
        for r in rows[hi + 1:]:
            if len(r) < 2 or SKIP_ROW.search(re.sub(r"\s", "", r[0])):
                continue
            if CURRENT_ROW.search(re.sub(r"\s", "", r[0])) and not any(STRICT_BANK.search(c) for c in r):
                continue
            if bond_mode and BOND_PART.search(r[0]):
                continue
            if all(re.match(r"^[\d.\s~\-]+$|^(당기|전기|통화|외화금액|원화금액)", c.strip()) for c in r if c.strip()):
                continue                                            # 머리글 두 번째 줄
            # 행이 짧으면 왼쪽으로. 길면 — 둘째 머리글로 금액 칸이 나뉜 표(대한·동국·세아제강)는 그대로,
            # 둘째 머리글 없이 왼쪽 "구분"이 두 칸을 덮은 표(대창스틸)는 오른쪽으로
            j = li - max(0, width - len(r)) if (len(r) <= width or has_sub or has_sub_early) else li + (len(r) - width)
            cand = r[j] if 0 <= j < len(r) else ""
            if j < 0 and prev and not re.search(r"[가-힣A-Za-z]", r[0]):
                cand = prev                                # 이름 칸이 위 줄과 합쳐져 날짜로 시작하는 줄 (한일시멘트 사채)
            if not bond_mode and (not cand or (LOAN_KIND.search(cand) and not LENDERISH.search(cand))):
                first = r[0]
                if LENDERISH.search(first) and not LOAN_KIND.search(first):
                    cand = first
                elif LOAN_KIND.search(first) and prev:        # 차입처 칸이 위 행과 합쳐진 대출 종류 행만 이어받음
                    cand = prev
                else:
                    continue                                  # 모르는 행은 은행 몫으로 더하지 않음
            if not cand or not re.search(r"[가-힣A-Za-z]", cand) or is_rate(cand):
                continue
            r = [FX_CELL.match(c.strip()).group(1) if FX_CELL.match(c.strip()) else c for c in r]
            amts = [c for c in r if AMT.match(c.strip()) and not is_rate(c)]
            if not cand or not amts:
                continue
            if split and len(amts) >= 2:
                k = max(1, len(amts) // periods)
                parts = [to_num(a) for a in amts[:k]]
                v = None if any(p is None for p in parts) else sum(parts)
            else:
                if foreign and len(amts) >= 4 and not col_major:
                    raw = amts[1]
                elif p3 >= 3 and len(amts) >= p3:
                    raw = amts[-p3]
                else:
                    raw = amts[-2] if len(amts) >= 2 else amts[0]
                v = to_num(raw)
            if v is None:
                continue
            prev = cand
            name, others = clean_lender(cand)
            acc, cls = lender_class(name, have)
            if bond_mode:
                acc, cls = "", "사채(직접금융)"
            row_kind = "사채" if cls == "사채(직접금융)" else ("장기" if kind == "사채" else kind)
            out.append(dict(table_no=ti, row_label=re.sub(r"\s", "", r[0]), kind=row_kind, lender_raw=cand.strip(), lender=name,
                            lender_account=acc, lender_class=cls, includes_others=others,
                            amount_won=v * UNIT_X[unit], unit=unit, foreign_table=foreign))
    # 장기 표가 총액을 보이고 "유동성 대체(차감)"로 1년 안 갚을 몫을 빼는 회사면, 다른 표의 "유동성장기…" 줄은
    # 같은 몫을 한 번 더 보인 것 (NI스틸 국민은행 외 98억). 차감 줄이 없는 회사(대창스틸)는 그대로 둠
    if out and deduct_tables:
        out = [r for r in out if not (r["table_no"] not in deduct_tables and re.match(r"^유동성장기", r["row_label"]))]
    # 상세표가 없는 사채 종류는 요약표 금액으로 보충 — 사채는 은행이 없는 직접금융이라 상세표를 안 두는 회사가 있음
    for typ, v in summary_bonds.items():
        bonds = [r for r in out if r["lender_class"] == "사채(직접금융)"]
        if typ == "사채":
            covered = any(r["amount_won"] and not re.search(r"전환|신주인수권|교환", r["lender_raw"] + r["row_label"]) for r in bonds)
        else:
            covered = any(r["amount_won"] and typ[:2] in (r["lender_raw"] + r["row_label"]) for r in bonds)
        if v and not covered:
            out.append(dict(table_no=summary_tno[typ], row_label=typ, kind="사채", lender_raw=f"{typ}(구성내역 표)", lender=typ,
                            lender_account="", lender_class="사채(직접금융)", includes_others=False, amount_won=v,
                            unit="", foreign_table=False))
    return out, basis


GOOD_NUM = re.compile(r"^\(?-?\d{1,3}(,\d{3})*\)?$")      # 세 자리 쉼표 — 주석 번호 "5,18,19,31"은 금액이 아님 (TCC스틸)
TOTAL_CTX = [(re.compile(r"자본관리|자본조달|순부채|부채비율|순차입금"), "자본관리 표"),
             (re.compile(r"장부금액"), "금융상품 장부금액 표"),
             (re.compile(r"금융부채의?\s*범주별"), "금융부채 범주별 표")]     # 두산에너빌리티


def doc_total(zip_path):
    """같은 원문(별도)의 차입금 총계 (원, 출처) — 자본관리 표 → 금융상품 장부금액 표 순. 만기 분석·재무상태표는 쓰지 않음"""
    x, s, e, _ = choose(files_of(zip_path))
    found = {}
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", x, flags=re.S | re.I):
        if m.start() < s or m.start() > e:
            continue
        pre = _plain(x[max(0, m.start() - 600):m.start()])
        ctx = pre[-400:]                                  # 자본관리 문단은 표 앞 설명이 길어 넓게 봄 (두산에너빌리티)
        if re.search(r"만기|현금흐름|할인하지", pre[-200:]):
            continue
        if re.search(r"전기말|\(전\)\s*기", pre[-40:]) and not re.search(r"당기|\(당\)", pre[-40:]):
            continue                                       # 전기말만 보여 주는 표
        tb = tables(m.group(0))
        if not tb:
            continue
        rows = tb[0]
        for r in rows:
            if not r or not (TOTAL_ROW.match(re.sub(r"\s|:", "", r[0])) or re.sub(r"\s", "", r[0]) == "차입금"):
                continue
            amts = [c for c in r[1:] if GOOD_NUM.match(c.strip()) or c.strip() in ("-", "–")]   # 당기 "-"는 0
            um = UNIT.search(" ".join(" ".join(rr) for rr in rows[:2]) + " " + ctx[-120:])
            if not amts or not um:
                continue
            for k, (pat, label) in enumerate(TOTAL_CTX):
                if pat.search(ctx) and k not in found:
                    found[k] = (to_num(amts[0]) * UNIT_X[um.group(1)], label)
    return found[min(found)] if found else (None, "")


# 재무상태표 차입 줄 — "단기차입금및유동성장기차입금"(삼아알미늄)·"차입금 및 사채"(한국특강)처럼 합친 이름도 포함
BS_DEBT = re.compile(r"^(?:(?:외화|원화)?(?:단기|장기|유동성장기|유동성|비유동|유동|장ㆍ단기|장단기)?"
                     r"(?:차입금|차입부채|장기부채|사채|전환사채|신주인수권부사채|교환사채)(?:및|ㆍ|,)?)+$")


def bs_total(zip_path):
    """같은 원문 재무상태표의 차입금·사채 줄 당기 합계 (원) — 모든 감사보고서에 있는 기준값. 없으면 None
    재무상태표 = 주석 구역 앞의 표 중 '부채총계'가 있는 첫 표. 리스부채는 넣지 않음"""
    x, s, e, basis = choose(files_of(zip_path))
    s0 = s
    if basis == "사업보고서 별도 주석":                 # 본문은 "N. 재무제표" 구간에 재무상태표가 있음 (포스코)
        t = [m.start() for m in re.finditer(r"<TITLE[^>]*>\s*\d+\.\s*재무제표\s*</TITLE>", x[:s])]
        s0 = t[-1] if t else max(0, s - 400000)
    fm = next((m for m in FIRST_NOTE.finditer(x, s, e)), None)
    stop = fm.start() if fm else e
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", x[s0:stop], flags=re.S | re.I):
        tb = tables(m.group(0))
        if not tb:
            continue
        rows = tb[0]
        if not any(r and re.sub(r"\s", "", r[0]).startswith("부채총계") for r in rows):
            continue
        pre = _plain(x[max(0, s0 + m.start() - 400):s0 + m.start()])
        um = UNIT.search(" ".join(" ".join(r) for r in rows[:3]) + " " + pre[-200:])
        if not um:
            return None
        vals_all = []
        for r in rows:
            k = re.sub(r"\(\s*주석?[\s\d,ㆍ·]*\)|\((비?유동)\)", "", r[0]) if r else ""   # "(주석 4,5…)"·"(주 4,5…)"·"(유동)"
            k = re.sub(r"\s|\(\*\d*\)|\(주\d*\)|[ⅠⅡⅢⅣ\d.]", "", k)
            cells = r[1:]
            if cells and NOTE_CELL.match(cells[0]) and not GOOD_NUM.match(cells[0].strip()):
                cells = cells[1:]                        # 주석 번호 칸
            elif cells and NOTE_CELL.match(cells[0]) and len(cells) >= 3 and "," not in cells[0]:
                cells = cells[1:]
            vals = [c for c in cells if GOOD_NUM.match(c.strip()) or c.strip() in ("-", "–")]
            if not vals:
                continue
            v = to_num(vals[0]) or 0.0
            if BS_DEBT.match(k) and "리스" not in k:
                vals_all.append(v)
        if not vals_all:
            return None                                  # 차입 줄을 못 찾음 — 0으로 두면 잘못된 "일치"가 됨
        tot = sum(vals_all)
        for v in vals_all:                               # 어떤 줄이 나머지의 합이면 소계 — 한 번만 셈
            if v and abs(v - (tot - v)) <= max(1.0, abs(v) * 0.001):
                tot = v
                break
        return tot * UNIT_X[um.group(1)]
    return None


def report_for(code, get_json):
    """최신 사업보고서 → 없으면 별도 감사보고서 → 연결감사보고서 (2026년 접수)"""
    for ty, want in (("A", r"^사업보고서"), ("F", r"^감사보고서"), ("F", r"연결감사보고서")):
        d = get_json("list", corp_code=code, bgn_de="20260101", end_de="20261231", pblntf_ty=ty, page_count="100")
        for row in d.get("list", []) or []:
            if re.search(want, str(row.get("report_nm", "")).strip()):
                return row["rcept_no"], row["report_nm"].strip()
    return "", ""


def main():
    from dart_api import document_zip, get_json  # noqa: E402
    rank = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    code_of = {key(a): c for a, c in zip(base["account"], base["corp_code"]) if c}
    fin = pd.read_csv(PROC / "fin_list.csv", dtype=str).fillna("")
    have = {key(a): a for a in fin["account"]}
    api = pd.read_csv(MANUAL / "mfg_bank_borrowing.csv", dtype=str).fillna("") \
        if (MANUAL / "mfg_bank_borrowing.csv").exists() else pd.DataFrame(columns=["account", "borrowing_eok", "fs_div"])
    api_of = {key(a): (b, f) for a, b, f in zip(api["account"], api.get("borrowing_eok", ""), api.get("fs_div", ""))}

    # 제조-2가 받은 원문 접수번호 (bank_scan 첫 줄) — 고유번호가 비어 있는 회사도 이걸로 찾음 (포스코·세아베스틸)
    scan_rno = {}
    for f in (PROC / "bank_scan").glob("*.txt"):
        head = f.read_text(encoding="utf-8").splitlines()[:1]
        m = re.match(r"#\s*(.+?)\s+rcept_no=(\d+)", head[0]) if head else None
        if m:
            scan_rno[key(m.group(1))] = m.group(2)
    from dart_api import corp_codes  # noqa: E402
    cc = corp_codes()
    by_name = {}
    for c_, n_ in zip(cc["corp_code"], cc["corp_name"]):
        by_name.setdefault(key(n_), []).append(c_)

    man = pd.read_csv(MANUAL_FILE, dtype=str).fillna("") if MANUAL_FILE.exists() else pd.DataFrame()
    rows, checks = [], []
    print(f"제조 {len(rank)}곳 — 차입금 주석의 차입처별 금액", flush=True)
    for i, r in enumerate(rank.to_dict("records"), 1):
        acc = r["account"]
        code = code_of.get(key(acc), "")
        rno, rnm = report_for(code, get_json) if code else ("", "")
        if not rno and scan_rno.get(key(acc)):
            rno, rnm = scan_rno[key(acc)], "제조-2 원문"
        if not rno:
            for c_ in by_name.get(key(acc), [])[:5]:           # 고유번호가 비어 있으면 이름으로 (같은 이름 여럿이면 보고서가 있는 쪽)
                rno, rnm = report_for(c_, get_json)
                if rno:
                    break
        print(f"  [{i}/{len(rank)}] {acc} — {rnm or '보고서 없음'}", flush=True)
        parsed, basis, dt, dsrc, bs = [], "", None, "", None
        if rno:
            try:
                zp = document_zip(rno)
                parsed, basis = parse_doc(zp, have)
                dt, dsrc = doc_total(zp)
                bs = bs_total(zp)
            except Exception as e:  # noqa: BLE001
                basis = f"원문 오류 {str(e)[:60]}"
        mm = man[man["account"].map(key) == key(acc)] if len(man) else man
        man_check = None
        if len(mm):                                       # 수동 입력 — 원문을 보고 적은 값
            if mm["action"].isin(["replace", "none"]).any():
                parsed = []
            if "check_eok" in mm.columns and (mm["check_eok"] != "").any():
                man_check = float(mm.loc[mm["check_eok"] != "", "check_eok"].iloc[0]) * 1e8
            for q in mm[mm["action"] != "none"].to_dict("records"):
                name, others = clean_lender(q["lender"])
                a_, c_ = lender_class(name, have)
                parsed.append(dict(table_no=-1, row_label="수동 입력", kind=q.get("kind", ""), lender_raw=q["lender"],
                                   lender=name, lender_account=a_, lender_class=c_, includes_others=others,
                                   amount_won=float(q["amount_eok"] or 0) * 1e8, unit="억원", foreign_table=False))
            basis += (" · 차입금 없음(수동 확인)" if (mm["action"] == "none").all()
                      else " · 수동 입력(" + ",".join(sorted(set(mm["action"]))) + ")")
            if man_check is not None and dt is None:
                dt, dsrc = man_check, "수동 확인 기준값"
        for p in parsed:
            rows.append(dict(account=acc, rank=r.get("rank", ""), rcept_no=rno, report=rnm, doc_basis=basis, **p))
        tot = sum(p["amount_won"] for p in parsed) / 1e8
        b, f = api_of.get(key(acc), ("", ""))

        def pct(base):
            if base is None:
                return None
            return 0.0 if base == 0 and tot == 0 else (None if base == 0 else (tot - base) / base * 100)
        g_doc = pct(None if dt is None else dt / 1e8)
        g_bs = pct(None if bs is None else bs / 1e8)            # 재무상태표 차입금·사채 줄 합계 — 모든 감사보고서에 있음
        g_api = pct(float(b)) if b and f in ("OFS", "CFS") else None
        best = min([abs(x) for x in (g_doc, g_bs, g_api) if x is not None], default=None)
        status = ("기준값 없음" if best is None else "일치(1% 안)" if best <= 1 else "근접(1~11%)" if best <= 11 else "확인 필요")
        if not parsed and dt == 0:
            status = "차입금 없음(원문 총계 0)"
        elif not parsed and "차입금 주석 없음" in basis:
            status = "차입금 없음(주석 없음)"             # 주석 목차에 차입·사채 주석이 없음
        elif not parsed and "차입금 없음(수동 확인)" in basis:
            status = "차입금 없음(수동 확인)"
        checks.append(dict(account=acc, rank=r.get("rank", ""), report=rnm, rcept_no=rno, doc_basis=basis,
                           rows=len(parsed), parsed_eok=round(tot, 1),
                           doc_total_eok="" if dt is None else round(dt / 1e8, 1), doc_total_src=dsrc,
                           gap_doc="" if g_doc is None else f"{g_doc:+.1f}%",
                           bs_total_eok="" if bs is None else round(bs / 1e8, 1),
                           gap_bs="" if g_bs is None else f"{g_bs:+.1f}%", api_eok=b, api_fs=f,
                           gap_api="" if g_api is None else f"{g_api:+.1f}%", check=status,
                           named_lenders=len({p["lender"] for p in parsed})))
    a = pd.DataFrame(rows)
    c = pd.DataFrame(checks)
    a.to_csv(OUT, index=False, encoding="utf-8-sig")
    c.to_csv(OUT_CHECK, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 120)
    print(f"\n{len(c)}곳 · 차입처 행 {len(a)} → {OUT.relative_to(ROOT)}")
    print("\n[문서 기준]")
    print(c["doc_basis"].replace("", "없음").value_counts().to_string())
    if len(a):
        print("\n[차입처 분류 — 금액(억)]")
        print((a.groupby("lender_class")["amount_won"].sum() / 1e8).round(0).sort_values(ascending=False).to_string())
        top = a[a["lender_account"] != ""].groupby("lender_account").agg(
            companies=("account", "nunique"), eok=("amount_won", lambda s: round(s.sum() / 1e8, 0)))
        print("\n[명단 금융회사별 — 거래 제조사 수 · 금액(억)]")
        print(top.sort_values(["companies", "eok"], ascending=False).to_string())
    print("\n[검산 — 읽은 합계 vs 재무상태표 차입금·사채 줄 · 원문 차입금 총계 · DART 재무제표(제조-2) 중 가까운 쪽]")
    print(c["check"].value_counts().to_string())
    bad = c[c["check"].isin(["근접(1~11%)", "확인 필요", "기준값 없음"]) & (c["rows"] > 0)]
    if len(bad):
        print(bad[["account", "parsed_eok", "bs_total_eok", "gap_bs", "doc_total_eok", "gap_doc", "api_eok", "gap_api",
                   "check"]].to_string(index=False))
    none = c[(c["rows"] == 0) & (~c["check"].str.startswith("차입금 없음"))]
    if len(none):
        print(f"\n[차입처 행 0개 — 차입금이 없거나 표 형식이 다름, 원문 확인 {len(none)}곳]")
        print(none[["account", "report", "doc_basis", "doc_total_eok"]].to_string(index=False))


if __name__ == "__main__":
    main()
