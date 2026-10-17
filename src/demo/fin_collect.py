"""10 금융 시연 공개 자료 수집 (클로드 코드 2회차-1)

장부 차주 68곳의 재무·감사의견·매출 구성 후보·에너지 찾는 말·대출 줄·주석·법적 절차 공시·기업개황·직원 수를 DART 공식 API로 받아 기록함 (판정하지 않음, H4 시험 대상 아님)
규칙은 docs/progress/10_demo_fin.md 4-5-4·4-5-5

입력
- DART 공식 API — src/dart_api.py의 get_json·corp_codes·document_zip (저장본이 있으면 다시 씀)
- data/processed/fin_mfg_lenders.csv

출력
- data/collect/fin/fin_collect_targets.csv, fin_collect_financials.csv, fin_collect_audit.csv, fin_collect_sales_mix.csv, fin_collect_loan_lines.csv, fin_collect_legal.csv, fin_collect_log.csv
- data/raw/dart/collect/fin_collect_energy_terms.csv, fin_collect_notes_text.csv (git 제외)
"""
# LINEAGE-STEP: fin_collect (H4 시험 대상 아님 — 원천보다 앞의 공개 자료 수집, 10 4-5-4)
# LINEAGE-INPUT: DART 공식 API: list.json, company.json, fnlttSinglAcntAll.json, accnutAdtorNmNdAdtOpinion.json, empSttus.json, corpCode.xml, document.xml
# LINEAGE-INPUT: data/processed/fin_mfg_lenders.csv: account, rcept_no, doc_basis, lender_raw, lender_account, amount_won, unit
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_targets.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_financials.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_audit.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_sales_mix.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_loan_lines.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_legal.csv: 전 칸
# LINEAGE-OUTPUT: data/collect/fin/fin_collect_log.csv: 전 칸
# LINEAGE-OUTPUT: data/raw/dart/collect/fin_collect_energy_terms.csv: 전 칸
# LINEAGE-OUTPUT: data/raw/dart/collect/fin_collect_notes_text.csv: 전 칸
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import html
import re
import sys
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import dart_api  # noqa: E402
from dart_api import corp_codes, document_zip, get_json  # noqa: E402

OUT_PUB = ROOT / "data" / "collect" / "fin"
OUT_RAW = ROOT / "data" / "raw" / "dart" / "collect"
LENDERS = ROOT / "data" / "processed" / "fin_mfg_lenders.csv"
GITIGNORE = ROOT / ".gitignore"

VERSION = "v1 (10 C-007)"
BANKS = ("한국산업은행", "하나은행", "한국수출입은행")
STATUSES = ("수집", "원문 확인", "자료 없음")

# 4-5-4 나 대상 표 (번호 · 회사 · 고유번호 · 상장 · 재무 공시 · 접수번호 · 매출 구성 · 에너지 항목 · 주석 발췌, `빈칸` = 빈 값)
TARGETS = [
    (1, "(주)NI스틸", "00116301", "상장", "사업보고서 (2025.12)", "20260312001308", "추정 13", "대상", "약정·담보"),
    (2, "(주)SIMPAC", "00138260", "상장", "사업보고서 (2025.12)", "20260318001274", "모의고사 36", "", ""),
    (3, "(주)TCC스틸", "00117300", "상장", "사업보고서 (2025.12)", "20260318000366", "모의고사 36", "", "약정·담보"),
    (4, "(주)대륙제관", "00109587", "상장", "사업보고서 (2025.12)", "20260319000299", "추정 13", "대상", ""),
    (5, "(주)대창스틸", "00112721", "상장", "사업보고서 (2025.12)", "20260323000588", "추정 13", "대상", "약정·담보"),
    (6, "(주)대호에이엘", "00428729", "상장", "사업보고서 (2025.12)", "20260324000005", "모의고사 36", "", "약정·담보"),
    (7, "(주)대호특수강", "00166175", "상장", "사업보고서 (2025.12)", "20260317000646", "", "", ""),
    (8, "(주)덕신이피씨", "00454937", "상장", "사업보고서 (2025.12)", "20260310003096", "추정 13", "대상", ""),
    (9, "(주)동국에스엔씨", "00415594", "상장", "사업보고서 (2025.12)", "20260316001236", "추정 13", "대상", ""),
    (10, "(주)동남", "", "비상장", "감사보고서 (2025.12)", "20260409000647", "모의고사 36", "", ""),
    (11, "(주)삼표시멘트", "00239639", "상장", "사업보고서 (2025.12)", "20260320000882", "", "", "약정·담보"),
    (12, "(주)성광벤드", "00132318", "상장", "사업보고서 (2025.12)", "20260319000739", "추정 13", "대상", ""),
    (13, "(주)세아씨엠", "", "비상장", "감사보고서 (2025.12)", "20260326000276", "모의고사 36", "", "약정·담보"),
    (14, "(주)세아제강", "01325979", "상장", "사업보고서 (2025.12)", "20260312000989", "모의고사 36", "", ""),
    (15, "(주)세진메탈", "00441410", "비상장", "감사보고서 (2025.12)", "20260402001164", "모의고사 36", "", "약정·담보"),
    (16, "(주)알루코", "00117027", "상장", "사업보고서 (2025.12)", "20260318001554", "", "", "약정·담보"),
    (17, "(주)원일특강", "00143907", "상장", "사업보고서 (2025.12)", "20260316000744", "추정 13", "대상", ""),
    (18, "(주)유니온", "00144252", "상장", "사업보고서 (2025.12)", "20260319000893", "모의고사 36", "", ""),
    (19, "(주)케이피에프", "00157636", "상장", "사업보고서 (2025.12)", "20260317000758", "모의고사 36", "", "약정·담보"),
    (20, "(주)태웅", "00186799", "상장", "사업보고서 (2025.12)", "20260318001708", "모의고사 36", "", ""),
    (21, "(주)하이스틸", "00435312", "상장", "사업보고서 (2025.12)", "20260310002913", "추정 13", "대상", "약정·담보"),
    (22, "(주)한국특강", "00124090", "상장", "사업보고서 (2025.12)", "20260323000279", "모의고사 36", "", ""),
    (23, "(주)휴스틸", "00156488", "상장", "사업보고서 (2025.12)", "20260323001458", "모의고사 36", "", "약정·담보"),
    (24, "DSR제강(주)", "00151298", "상장", "사업보고서 (2025.12)", "20260318001149", "추정 13", "대상", "약정·담보 + 주석 10"),
    (25, "KG스틸(주)", "00115676", "상장", "사업보고서 (2025.12)", "20260316001588", "모의고사 36", "", "결정 8 근거"),
    (26, "KG케미칼(주)", "00101220", "상장", "사업보고서 (2025.12)", "20260323001613", "모의고사 36", "", ""),
    (27, "경남스틸(주)", "00206039", "상장", "사업보고서 (2025.12)", "20260309001568", "추정 13", "대상", ""),
    (28, "금강공업(주)", "00105299", "상장", "사업보고서 (2025.12)", "20260312000935", "", "", "약정·담보"),
    (29, "남해화학(주)", "00107987", "상장", "사업보고서 (2025.12)", "20260319000635", "모의고사 36", "", ""),
    (30, "넥스틸(주)", "00220613", "상장", "사업보고서 (2025.12)", "20260320001261", "", "", ""),
    (31, "대한시멘트 주식회사", "00950705", "비상장", "감사보고서 (2025.12)", "20260330001518", "모의고사 36", "", ""),
    (32, "대한제강(주)", "00113225", "상장", "사업보고서 (2025.12)", "20260318000780", "모의고사 36", "", ""),
    (33, "동국산업(주)", "00172680", "상장", "사업보고서 (2025.12)", "20260318001458", "모의고사 36", "", ""),
    (34, "동국씨엠 주식회사", "01765256", "상장", "사업보고서 (2025.12)", "20260316001579", "모의고사 36", "", "결정 8 근거"),
    (35, "동국제강(주)", "01765265", "상장", "사업보고서 (2025.12)", "20260313000519", "", "", "큰 3곳 차입금"),
    (36, "두산에너빌리티(주)", "00159616", "상장", "사업보고서 (2025.12)", "20260320001246", "모의고사 36", "", "큰 3곳 차입금"),
    (37, "디케이동신주식회사", "00760069", "비상장", "감사보고서 (2025.12)", "20260316000184", "모의고사 36", "", ""),
    (38, "만호제강(주)", "00120872", "상장", "사업보고서 (2026.06)", "20260910000496", "모의고사 36", "", ""),
    (39, "삼보산업 주식회사", "00125822", "상장", "사업보고서 (2025.12)", "20260407003361", "모의고사 36", "", ""),
    (40, "삼아알미늄(주)", "00126779", "상장", "사업보고서 (2025.12)", "20260318000860", "모의고사 36", "", ""),
    (41, "삼화왕관(주)", "00129235", "상장", "사업보고서 (2025.12)", "20260319000454", "모의고사 36", "", ""),
    (42, "성신양회(주)", "00132804", "상장", "사업보고서 (2025.12)", "20260318001369", "", "", ""),
    (43, "쌍용씨앤이주식회사", "00138224", "비상장", "사업보고서 (2025.12)", "20260331004655", "", "", ""),
    (44, "씨에스윈드(주)", "00670340", "상장", "사업보고서 (2025.12)", "20260318001110", "", "", ""),
    (45, "아세아시멘트(주)", "00990165", "상장", "사업보고서 (2025.12)", "20260318001310", "", "", ""),
    (46, "아주스틸(주)", "00486705", "상장", "사업보고서 (2025.12)", "20260318001296", "", "", ""),
    (47, "에스케이오션플랜트(주)", "00480367", "상장", "사업보고서 (2025.12)", "20260323000486", "", "", ""),
    (48, "울산알루미늄 주식회사", "01319996", "비상장", "감사보고서 (2026.03)", "20260703000011", "모의고사 36", "", ""),
    (49, "일진제강(주)", "00146658", "비상장", "감사보고서 (2025.12)", "20260413001676", "모의고사 36", "", ""),
    (50, "조일알미늄(주)", "00149239", "상장", "사업보고서 (2025.12)", "20260312000761", "모의고사 36", "", ""),
    (51, "주식회사 세아베스틸", "", "비상장", "제조-2 원문", "20260313000646", "", "", ""),
    (52, "주식회사 세아창원특수강", "", "비상장", "사업보고서 (2025.12)", "20260313000846", "모의고사 36", "", ""),
    (53, "주식회사 신스틸", "00958664", "상장", "사업보고서 (2025.12)", "20260318000805", "추정 13", "대상", ""),
    (54, "주식회사 에스엔엔씨", "", "비상장", "감사보고서 (2025.12)", "20260330000517", "", "", ""),
    (55, "주식회사 포스코", "", "비상장", "제조-2 원문", "20260312001382", "", "", ""),
    (56, "진양특수강(주)", "00150466", "비상장", "감사보고서 (2025.12)", "20260331004512", "모의고사 36", "", ""),
    (57, "케이비아이동양철관(주)", "00117629", "상장", "사업보고서 (2025.12)", "20260318001380", "추정 13", "대상", "약정·담보"),
    (58, "하이호경금속주식회사", "00766814", "비상장", "감사보고서 (2025.12)", "20260402000938", "모의고사 36", "", ""),
    (59, "한국씨엔티(주)", "00156637", "비상장", "감사보고서 (2025.12)", "20260324000081", "모의고사 36", "", ""),
    (60, "한라시멘트(주)", "00257219", "비상장", "감사보고서 (2025.12)", "20260331001063", "", "", ""),
    (61, "한일시멘트(주)", "01319808", "상장", "사업보고서 (2025.12)", "20260317000863", "", "", ""),
    (62, "한일제관(주)", "00163169", "비상장", "감사보고서 (2025.12)", "20260330000576", "모의고사 36", "", ""),
    (63, "한일철강(주)", "00163196", "상장", "사업보고서 (2025.12)", "20260311004523", "추정 13", "대상", ""),
    (64, "한주라이트메탈(주)", "00156600", "상장", "사업보고서 (2025.12)", "20260317000438", "", "", ""),
    (65, "현대비앤지스틸(주)", "00125743", "상장", "사업보고서 (2025.12)", "20260316001374", "모의고사 36", "", ""),
    (66, "현대아이에프씨 주식회사", "01467460", "비상장", "감사보고서 (2025.12)", "20260320000515", "모의고사 36", "", ""),
    (67, "현대제철(주)", "00145880", "상장", "사업보고서 (2025.12)", "20260318001506", "", "", "큰 3곳 차입금"),
    (68, "현대종합특수강 주식회사", "", "비상장", "사업보고서 (2025.12)", "20260330001523", "모의고사 36", "", ""),
]

# 4-5-4 다 8번 보정 4줄 (line_id · 접수번호 · 원래 표기(없으면 금액으로만 찾음) · 원 단위 금액 · 은행 · note)
S_LINES = [
    ("S1-1", "20260703000011", "", 5000000000, "한국산업은행", ""),
    ("S1-2", "20260703000011", "", 10000000000, "한국산업은행", "차입처 칸이 위 줄과 합쳐진 줄 (4-1-11)"),
    ("S2", "20260318001149", "KEB하나은행외(*1),(*2),(*3)", 19227909000, "하나은행", ""),
    ("S3", "20260330001523", "KEB Hana Bank Manila", 28698000000, "하나은행", ""),
]

# 4-5-4 다 3번 "고르는 줄" 규칙 (item · 재무제표 종류 · account_id)
REVENUE_NAMES = ("매출액", "수익(매출액)", "영업수익", "매출")
DEBT_SKIP = ("충당", "이연", "파생", "보증금", "이자", "수익", "비용", "자산", "증가", "감소")
ITEM_RULES = [
    ("자산총계", ("BS",), "ifrs-full_Assets", lambda n: n == "자산총계"),
    ("부채총계", ("BS",), "ifrs-full_Liabilities", lambda n: n == "부채총계"),
    ("자본총계", ("BS",), "ifrs-full_Equity", lambda n: n == "자본총계"),
    ("비지배지분", ("BS",), "ifrs-full_NoncontrollingInterests", lambda n: "비지배지분" in n),
    ("매출", ("IS", "CIS"), "ifrs-full_Revenue", lambda n: n in REVENUE_NAMES),
    ("제품·상품 매출", ("IS", "CIS"), None, lambda n: "매출" in n and ("제품" in n or "상품" in n)),
    ("차입·사채·리스", ("BS",), None,
     lambda n: any(k in n for k in ("차입", "사채", "리스부채", "유동성장기부채"))  # H1 — 유동성장기부채 더함
     and not any(k in n for k in DEBT_SKIP)),
]

# 4-5-4 다 7번 "찾는 말" (영문 말은 앞뒤 글자가 영문이 아닐 때만)
ENERGY_TERMS = ["에너지 사용량", "에너지사용량", "전력 사용량", "전력사용량", "전기 사용량", "전기사용량",
                "연료 사용량", "연료사용량", "MWh", "kWh", "TJ", "toe", "온실가스 배출량", "tCO2"]

# 4-5-4 다 9번 "찾는 주석" · "은행 표기"
NOTE_WORDS = {
    "큰 3곳 차입금": ("차입금", "사채"),
    "약정·담보": ("약정", "담보", "우발"),
    "약정·담보 + 주석 10": ("약정", "담보", "우발", "매출채권"),
    "결정 8 근거": ("약정", "담보", "우발"),
}
BANK_TERMS = [("한국산업은행", ("산업은행", "KDB")), ("하나은행", ("하나은행", "KEB하나", "Hana")),
              ("한국수출입은행", ("수출입은행", "KEXIM"))]

# 4-5-4 다 10번 보고서명 찾는 말
LEGAL_TERMS = ("회생", "파산", "상장폐지", "상장적격성", "관리종목", "매매거래정지", "감사의견", "자본잠식", "부도", "해산")

UNIT_MULT = {"원": 1, "천원": 1000, "백만원": 1000000, "억원": 100000000}

COLS = {
    "targets": ["no", "borrower", "corp_code", "corp_code_source", "stock_code", "listed", "corp_name_official",
                "jurir_no", "address", "induty_code", "acc_mt", "corp_cls", "est_dt", "employees", "report_kind",
                "rcept_no", "report_nm", "latest_rcept_no", "group_sales_mix", "group_energy", "group_notes",
                "status", "note", "collected_at", "version"],
    "financials": ["borrower", "corp_code", "fs_div", "route", "rcept_no", "bsns_year", "sj_div", "item",
                   "account_id", "account_nm", "amount_won", "unit_raw", "location", "status", "note",
                   "collected_at", "version"],
    "audit": ["borrower", "corp_code", "route", "rcept_no", "auditor", "opinion_raw", "accounting_standard",
              "location", "status", "note", "collected_at", "version"],
    "sales_mix": ["borrower", "corp_code", "group", "source", "rcept_no", "table_title", "header_raw", "row_raw",
                  "row_label", "amount_won", "unit_raw", "location", "status", "note", "collected_at", "version"],
    "loan_lines": ["line_id", "borrower", "bank", "rcept_no", "lender_raw", "amount_won_a3", "table_title",
                   "header_raw", "row_raw", "match_count", "location", "status", "note", "collected_at", "version"],
    "legal": ["borrower", "corp_code", "pblntf_ty", "rcept_no", "rcept_dt", "report_nm", "matched_term", "status",
              "note", "collected_at", "version"],
    "log": ["seq", "api", "request", "result_status", "cache_hit", "saved_file", "at"],
    "energy_terms": ["borrower", "corp_code", "rcept_no", "term", "context", "location", "status", "note",
                     "collected_at", "version"],
    "notes_text": ["borrower", "corp_code", "rcept_no", "purpose", "heading", "kind", "text_raw", "bank_mentioned",
                   "location", "status", "note", "collected_at", "version"],
}
FILES = {
    "targets": OUT_PUB / "fin_collect_targets.csv",
    "financials": OUT_PUB / "fin_collect_financials.csv",
    "audit": OUT_PUB / "fin_collect_audit.csv",
    "sales_mix": OUT_PUB / "fin_collect_sales_mix.csv",
    "loan_lines": OUT_PUB / "fin_collect_loan_lines.csv",
    "legal": OUT_PUB / "fin_collect_legal.csv",
    "log": OUT_PUB / "fin_collect_log.csv",
    "energy_terms": OUT_RAW / "fin_collect_energy_terms.csv",
    "notes_text": OUT_RAW / "fin_collect_notes_text.csv",
}

RUN = {"date": "", "end_de": "", "where": "", "gitignore": False}
ROWS = {k: [] for k in COLS}
_MEMO = {"corp": None, "list": {}, "doc": {}, "sales1": {}}


# ── 내부 도우미 ───────────────────────────────────────────────

def _stop(reason):
    where = RUN["where"]
    print(f"[STOP] fin_collect — {reason}" + (f" ({where})" if where else ""))
    sys.exit(1)


def _plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _nospace(s):
    return re.sub(r"\s", "", s or "")


def _item_name(s):
    """원문 줄 이름 — 공백·로마 숫자·번호 제거 (4-5-4 다 4번)"""
    n = _nospace(s)
    n = re.sub(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+\.?", "", n)
    n = re.sub(r"^[IVX]+\.", "", n)
    n = re.sub(r"^\(?\d{1,2}\)\.?|^\d{1,2}\.", "", n)
    return n


_NOTE_REF = re.compile(r"[\(（](?:주석|주)[\d,\-~.와과및]+[\)）]$")  # F1 — '와'·'과'·'및' 허용


def _item_name_doc(s):
    """감사보고서 원문 줄 이름 — 공백 제거 → 로마 숫자·번호 제거 → 끝의 주석 번호 괄호 제거 (D7)"""
    return _NOTE_REF.sub("", _item_name(s))


def _num(t):
    """칸 글자 → Decimal (쉼표 제거, (1,234)·△1,234·-1,234는 음수). 숫자가 아니면 None"""
    s = _nospace(t).replace(",", "")
    neg = False
    if len(s) > 2 and s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s[:1] in ("△", "-"):
        neg, s = True, s[1:]
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None
    v = Decimal(s)
    return -v if neg else v


def _int_text(v):
    """Decimal → 원 단위 정수 글자. 정수가 아니면 None"""
    if v is None or v != v.to_integral_value():
        return None
    return str(int(v))


def _dec(text):
    """입력 파일 금액 글자 → Decimal (실수 계산 없이)"""
    s = (text or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _unit(raw):
    """'(단위 : 천원)' 글자 → 곱할 수 (모르는 단위는 None)"""
    m = re.search(r"\(\s*단\s*위\s*[:：]?\s*([^)]*)\)", raw)
    if not m:
        return None
    first = _nospace(re.split(r"[,;]", m.group(1))[0])
    return UNIT_MULT.get(first)


def _unit_text(s):
    m = re.search(r"\(\s*단\s*위\s*[:：]?[^)]*\)", s)
    return m.group(0) if m else ""


def _join(cells):
    return " | ".join(cells)


def _add_note(old, new):
    return f"{old} · {new}" if old else new


_TABLE = re.compile(r"<TABLE\b.*?</TABLE>", re.S | re.I)
_TEXT = re.compile(r"<(TITLE|P)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
_TR = re.compile(r"<TR\b[^>]*>(.*?)</TR\s*>", re.S | re.I)
_CELL = re.compile(r"<(TD|TH|TE|TU)\b([^>]*)>(.*?)</\1\s*>", re.S | re.I)
_THEAD = re.compile(r"<THEAD\b.*?</THEAD\s*>", re.S | re.I)
_SPAN = re.compile(r"\b(COLSPAN|ROWSPAN)\s*=\s*\"?(\d+)", re.I)


def _parse_table(raw):
    """표 원문 → 줄 목록 [{cells: [(칸 시작, 칸 수, 글자)], head}] (합친 칸 위치 반영)"""
    th = _THEAD.search(raw)
    rows, taken = [], {}
    for ri, m in enumerate(_TR.finditer(raw)):
        head = bool(th and th.start() <= m.start() < th.end())
        cells, col = [], 0
        for c in _CELL.finditer(m.group(1)):
            while (ri, col) in taken:
                col += 1
            spans = {k.upper(): int(v) for k, v in _SPAN.findall(c.group(2))}
            cs, rs = max(spans.get("COLSPAN", 1), 1), max(spans.get("ROWSPAN", 1), 1)
            text = _plain(c.group(3))
            cells.append((col, cs, text))
            for r in range(ri + 1, ri + rs):
                for k in range(col, col + cs):
                    taken[(r, k)] = (col, cs, text)
            col += cs
        # grid = 이 줄의 칸 + 위에서 내려오는 합친 칸(rowspan) 글자 (대출 줄 찾기에만 씀 — D9)
        down = sorted({v for (r, _k), v in taken.items() if r == ri})
        grid = sorted([(c0, cs, tx, False) for c0, cs, tx in cells] + [(c0, cs, tx, True) for c0, cs, tx in down])
        rows.append({"cells": cells, "head": head, "grid": grid})
    return rows


def _blocks(x):
    """파일 글 → 차례대로 [{kind: 제목·글·표, text 또는 rows, n}] (n = 그 파일 안 글·표 순번)"""
    spans = [(m.start(), m.end()) for m in _TABLE.finditer(x)]
    items = [(a, "표", x[a:b]) for a, b in spans]
    j = 0
    for m in _TEXT.finditer(x):
        while j < len(spans) and spans[j][1] <= m.start():
            j += 1
        if j < len(spans) and spans[j][0] <= m.start() < spans[j][1]:
            continue
        t = _plain(m.group(2))
        if t:
            items.append((m.start(), "제목" if m.group(1).upper() == "TITLE" else "글", t))
    items.sort(key=lambda r: r[0])
    out, nt, nx = [], 0, 0
    for pos, kind, val in items:
        if kind == "표":
            nt += 1
            rows = _parse_table(val)
            out.append({"kind": "표", "rows": rows, "n": nt, "pos": pos,
                        "text": " ".join(c[2] for r in rows for c in r["cells"] if c[2])})
        else:
            nx += 1
            out.append({"kind": kind, "text": val, "n": nx, "pos": pos})
    return out


def _doc(rcept_no):
    """원문 압축 파일 → 파일 목록 [{name, docname, blocks}] (document_zip 호출 기록 포함)"""
    if rcept_no in _MEMO["doc"]:
        return _MEMO["doc"][rcept_no]
    path = call_api("document", rcept_no=rcept_no)
    files = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            b = z.read(name)
            for enc in ("utf-8", "cp949", "euc-kr"):
                try:
                    x = b.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                x = b.decode("utf-8", "replace")
            m = re.search(r"<DOCUMENT-NAME[^>]*>(.*?)</DOCUMENT-NAME>", x, re.S)
            blocks = _blocks(x)
            docname = _plain(m.group(1)) if m else next((b_["text"] for b_ in blocks if b_["kind"] == "제목"), "")
            files.append({"name": name, "docname": docname, "blocks": blocks})
    _MEMO["doc"][rcept_no] = files
    return files


def _body(files):
    """감사보고서만 내는 회사의 본문 = 압축 파일의 첫 파일"""
    return files[0] if files else None


def _sep_audit(files):
    """사업보고서 압축 파일 안 별도 감사보고서 (문서 이름에 '감사보고서'가 있고 '연결'이 없는 파일)"""
    return next((f for f in files if "감사보고서" in _nospace(f["docname"]) and "연결" not in f["docname"]), None)


def _main_report(files):
    """사업보고서 본문 (문서 이름에 '사업보고서'가 든 첫 파일)"""
    return next((f for f in files if "사업보고서" in _nospace(f["docname"])), None)


def _loc(f, b):
    return f"{f['name']}#{'표' if b['kind'] == '표' else '글'}{b['n']}"


def _table_title(blocks, i):
    """앞 표가 끝난 뒤부터 이 표 앞까지의 마지막 글 1개 ('(단위'로 시작하는 글·단위 표는 건너뜀)"""
    k = i - 1
    while k >= 0:
        b = blocks[k]
        if b["kind"] == "표":
            if _unit_text(b["text"]) and len(b["rows"]) <= 3:
                k -= 1
                continue
            return ""
        if not re.match(r"^\(\s*단\s*위", b["text"]):
            return b["text"]
        k -= 1
    return ""


def _table_unit(blocks, i):
    """표 안 또는 바로 위(글 3개 안)의 '(단위: …)' 글자"""
    u = _unit_text(blocks[i]["text"])
    k = i - 1
    while not u and k >= 0 and k >= i - 3:
        u = _unit_text(blocks[k]["text"])
        k -= 1
    return u


def _header_cells(rows):
    head = [r for r in rows if r["head"]] or rows[:1]
    return head


def _first_header_raw(rows):
    head = _header_cells(rows)
    return _join([c[2] for c in head[0]["cells"]]) if head else ""


_KISU = re.compile(r"제(\d+)기")


def _current_span(rows):
    """당기 칸 범위 — 머리 줄 '당기'·'(당)' 칸, 없으면 '제 n 기' 칸 중 n이 가장 큰 칸 (F3)
    돌려줌: (범위, 기수로 정한 note, 원문 확인 이유)"""
    heads = _header_cells(rows)
    for h in heads:
        for col, cs, t in h["cells"]:
            tt = _nospace(t)
            if "당기" in tt or "(당)" in tt:
                return (col, col + cs), "", ""
    kisu = []
    for h in heads:
        for col, cs, t in h["cells"]:
            m = _KISU.search(_nospace(t))
            if m:
                kisu.append((int(m.group(1)), col, cs))
    ns = sorted({k[0] for k in kisu}, reverse=True)
    if len(ns) < 2:
        return None, "", ""
    if ns[0] - ns[1] != 1:
        return None, "", f"기수 차이가 1이 아님 (제 {ns[0]} 기 · 제 {ns[1]} 기)"
    n, col, cs = next(k for k in kisu if k[0] == ns[0])
    return (col, col + cs), f"당기 칸 = 제 {n} 기 (기수로 정함)", ""


def _current_value(rows, row):
    """당기 칸 아래의 숫자 — 둘로 나뉘면 숫자가 있는 칸 중 오른쪽 칸
    돌려줌: (글자, 값, 기수 note, 원문 확인 이유, 숫자가 아닌 당기 칸 글자)"""
    span, knote, problem = _current_span(rows)
    if not span:
        return None, None, knote, problem, ""
    best, raw = None, ""
    for col, cs, t in row["cells"]:
        if span[0] <= col < span[1]:
            if _num(t) is not None:
                best = (t, _num(t))
            elif t.strip():
                raw = t.strip()
    if best:
        return best[0], best[1], knote, "", ""
    return None, None, knote, "", raw


def _notes_area(f):
    """주석 구역 [시작, 끝) 블록 번호 — 제목 '주석'부터 다음 제목 앞까지 (제목이 없으면 첫 '1.' 글부터 끝까지)"""
    bl = f["blocks"]
    s = next((i for i, b in enumerate(bl) if b["kind"] == "제목" and _nospace(b["text"]) == "주석"), None)
    if s is not None:
        e = next((i for i in range(s + 1, len(bl)) if bl[i]["kind"] == "제목"
                  and not re.match(r"^\d{1,2}\s*\.", bl[i]["text"])), len(bl))
        return s + 1, e
    s = next((i for i, b in enumerate(bl) if b["kind"] != "표" and re.match(r"^1\s*\.\s*[가-힣]", b["text"])), None)
    return (s, len(bl)) if s is not None else (len(bl), len(bl))


_HEAD = re.compile(r"^(\d{1,2})\s*\.\s*([가-힣].*)")


def _note_heads(f, s, e):
    """주석 제목 (블록 번호, 번호, 제목 앞 9글자) — 1부터 이어지는 번호만 (건너뜀 3까지)"""
    out, last = [], 0
    for i in range(s, e):
        b = f["blocks"][i]
        if b["kind"] == "표":
            continue
        m = _HEAD.match(b["text"])
        if not m:
            continue
        k = int(m.group(1))
        if (last == 0 and k <= 3) or (last and last < k <= last + 3):
            out.append((i, k, m.group(2)[:9]))
            last = k
    return out


def _bank_mentioned(text):
    return " · ".join(b for b, words in BANK_TERMS if any(w in text for w in words))


def _put(name, **kw):
    kw.setdefault("collected_at", RUN["date"])
    kw.setdefault("version", VERSION)
    ROWS[name].append({c: kw.get(c, "") for c in COLS[name]})


# ── 4-5-14 나 함수 ───────────────────────────────────────────

def check_gitignore():
    """.gitignore 두 줄을 확인하고 없으면 멈춤 (결정 43)"""
    lines = {ln.strip() for ln in GITIGNORE.read_text(encoding="utf-8").splitlines()} if GITIGNORE.exists() else set()
    missing = [x for x in ("data/external/demo_fin/", "data/external/demo_mfg/") if x not in lines]
    if missing:
        RUN["where"] = ".gitignore"
        _stop(".gitignore 두 줄 없음 — " + " · ".join(missing))
    RUN["gitignore"] = True


def call_api(api, **params):
    """DART 호출 1번을 하고 호출 기록 줄을 남김 (인증키를 뺀 요청 값)"""
    if api == "corpCode":
        path = dart_api.CACHE / "corpCode.zip"
    elif api == "document":
        path = dart_api.DOCS / f"{params['rcept_no']}.zip"
    else:
        tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        path = dart_api.CACHE / f"{api}_{tag}.json"
    hit = path.exists()
    try:
        if api == "corpCode":
            result, status = corp_codes(), "압축 파일"
        elif api == "document":
            result, status = document_zip(params["rcept_no"]), "압축 파일"
        else:
            result = get_json(api, **params)
            status = result.get("status", "")
    except RuntimeError as e:
        msg = str(e)
        _stop(".env 인증키 없음" if "DART_API_KEY" in msg else msg)
    except requests.RequestException as e:
        _stop(f"접속 실패 ({type(e).__name__}, {api})")
    ROWS["log"].append({
        "seq": str(len(ROWS["log"]) + 1), "api": api,
        "request": "&".join(f"{k}={v}" for k, v in params.items()),
        "result_status": status, "cache_hit": "저장본" if hit else "새로 받음",
        "saved_file": path.relative_to(ROOT).as_posix(), "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return result


def load_targets():
    """대상 표 68곳(코드 안 상수)과 원래 차입처 줄을 읽음 (4-5-4 나)"""
    with open(LENDERS, encoding="utf-8-sig", newline="") as f:
        lenders = list(csv.DictReader(f))
    for i, r in enumerate(lenders, 1):
        r["_line"] = i
    sel = [r for r in lenders if r["lender_account"] in BANKS and (_dec(r["amount_won"]) or 0) > 0]
    by_bank = {b: sum(1 for r in sel if r["lender_account"] == b) for b in BANKS}
    accounts = {r["account"] for r in sel}
    RUN["where"] = "data/processed/fin_mfg_lenders.csv"
    if len(sel) != 216 or by_bank != {"한국산업은행": 120, "하나은행": 64, "한국수출입은행": 32} or len(accounts) != 67:
        _stop(f"원래 차입처 줄 수 다름 — {len(sel)}줄 {by_bank} {len(accounts)}곳 (명세 216줄 · 120 · 64 · 32 · 67곳)")
    targets = []
    for no, borrower, code, listed, kind, rcept, sales, energy, notes in TARGETS:
        targets.append({"no": no, "borrower": borrower, "corp_code": code, "listed": listed, "report_kind": kind,
                        "rcept_no": rcept, "group_sales_mix": sales, "group_energy": energy, "group_notes": notes,
                        "corp_code_source": "표" if code else "", "stock_code": "", "items": {}, "fin_year": "",
                        "route": "", "report_nm": "", "latest_rcept_no": "", "doc_rcept_no": rcept, "api_rcepts": [],
                        "evidence": ""})
    names = {t["borrower"] for t in targets}
    if len(targets) != 68 or accounts - names:
        _stop(f"대상 표와 원래 차입처 줄의 회사가 다름 — {sorted(accounts - names)}")
    for t in targets:
        rc = {r["rcept_no"] for r in sel if r["account"] == t["borrower"]}
        if rc and rc != {t["rcept_no"]}:
            RUN["where"] = t["borrower"]
            _stop(f"표 접수번호와 원래 차입처 줄 rcept_no 다름 — 표 {t['rcept_no']} · 줄 {sorted(rc)}")
    RUN["where"] = ""
    return targets, lenders, sel


def find_corp_codes(targets):
    """고유번호 빈칸 7곳을 찾음 (4-5-4 다 1번)"""
    RUN["where"] = "1번 고유번호"
    df = call_api("corpCode")
    rows = df.to_dict("records")
    _MEMO["corp"] = {r["corp_code"]: r for r in rows}
    norm = lambda s: re.sub(r"주식회사|\(주\)|㈜|\s", "", s or "")  # noqa: E731
    by_name = {}
    for r in rows:
        by_name.setdefault(norm(r["corp_name"]), []).append(r)
    for t in targets:
        if t["corp_code"]:
            continue
        RUN["where"] = f"{t['borrower']} · 1번 고유번호"
        cands = by_name.get(norm(t["borrower"]), [])
        hit = [c for c in cands if any(e["rcept_no"] == t["rcept_no"] for e in list_disclosures(c["corp_code"]))]
        if len(hit) == 1:
            t["corp_code"], t["corp_code_source"] = hit[0]["corp_code"], "corpCode 찾음"
            t["evidence"] = t["rcept_no"]
        else:
            t["corp_code_source"] = "원문 확인"
            t["items"][1] = ("원문 확인", f"1번 원문 확인 — 후보 {len(cands)}곳 중 표 접수번호가 든 곳 {len(hit)}곳")
    for t in targets:
        if t["corp_code"] and t["corp_code"] in _MEMO["corp"]:
            t["stock_code"] = (_MEMO["corp"][t["corp_code"]].get("stock_code") or "").strip()
    RUN["where"] = ""


def list_disclosures(corp_code, **filters):
    """공시 목록을 모든 쪽 받아 돌려줌"""
    key = (corp_code, tuple(sorted(filters.items())))
    if key in _MEMO["list"]:
        return _MEMO["list"][key]
    out, page = [], 1
    while True:
        d = call_api("list", corp_code=corp_code, bgn_de="20250101", end_de=RUN["end_de"], **filters,
                     page_count="100", page_no=str(page))
        if d.get("status") == "013":
            break
        out += d.get("list", [])
        if page >= int(d.get("total_page") or 1):
            break
        page += 1
    _MEMO["list"][key] = out
    return out


def _base_name(nm):
    return re.sub(r"^(\s*\[[^\]]*\]\s*)+", "", nm or "").strip()


def check_reports(t):
    """공시 종류·정정본을 적음 (다 2번)"""
    RUN["where"] = f"{t['borrower']} · 2번 공시 종류"
    t["latest_rcept_no"] = t["rcept_no"]
    if not t["corp_code"]:
        t["items"][2] = ("원문 확인", "2번 원문 확인 — 고유번호 없음")
        return
    entries = list_disclosures(t["corp_code"])
    own = next((e for e in entries if e["rcept_no"] == t["rcept_no"]), None)
    if not own:
        t["items"][2] = ("원문 확인", "2번 원문 확인 — 공시 목록에 표 접수번호 없음")
        return
    t["report_nm"] = own["report_nm"]
    base = _base_name(own["report_nm"])
    later = [e for e in entries if e["report_nm"].strip().startswith("[")
             and _base_name(e["report_nm"]) == base and e["rcept_no"] > t["rcept_no"]]
    if later:
        t["latest_rcept_no"] = max(e["rcept_no"] for e in later)
    # 6·7번 원문용 접수번호 — '[첨부정정]'으로 시작하는 정정을 뺀 가장 늦은 것, 없으면 표 접수번호 (014 처리 가)
    body = [e["rcept_no"] for e in later if not e["report_nm"].strip().startswith("[첨부정정]")]
    t["doc_rcept_no"] = max(body) if body else t["rcept_no"]
    kind = t["report_kind"]
    if kind.startswith("사업보고서"):
        t["route"] = "사업보고서"
    elif kind.startswith("감사보고서"):
        t["route"] = "감사보고서"
    elif "사업보고서" in own["report_nm"]:
        t["route"] = "사업보고서"
    elif "감사보고서" in own["report_nm"]:
        t["route"] = "감사보고서"
    else:
        t["items"][2] = ("원문 확인", "2번 원문 확인 — 보고서명에 사업보고서·감사보고서 없음")


def _fin_rows_api(t, fs_div, d, year, note):
    label = "별도" if fs_div == "OFS" else "연결"
    for r in d.get("list", []):
        name = _nospace(r.get("account_nm"))
        for item, sjs, acc_id, rule in ITEM_RULES:
            if r.get("sj_div") not in sjs:
                continue
            if not ((acc_id and r.get("account_id") == acc_id) or rule(name)):
                continue
            raw = (r.get("thstrm_amount") or "").replace(",", "").strip()
            amt = raw if re.fullmatch(r"-?\d+", raw) else ""
            if amt:
                st, nt = "수집", note
            elif not raw:
                # H2 — API 당기 금액이 빈 값이면 0원
                amt, st, nt = "0", "수집", _add_note(note, "API 당기 금액 빈 값 → 0원")
            else:
                st, nt = "원문 확인", _add_note(note, f"당기 금액 글자 '{raw}'")
            _put("financials", borrower=t["borrower"], corp_code=t["corp_code"], fs_div=label, route="재무제표 API",
                 rcept_no=r.get("rcept_no", ""), bsns_year=year, sj_div=r.get("sj_div", ""), item=item,
                 account_id=r.get("account_id", ""), account_nm=r.get("account_nm", ""), amount_won=amt,
                 unit_raw=r.get("currency", ""), location="API fnlttSinglAcntAll", status=st, note=nt)
            if item == "제품·상품 매출":
                _MEMO["sales1"].setdefault(t["borrower"], []).append(dict(
                    fs=label, source="재무제표 API", rcept_no=r.get("rcept_no", ""), table_title=r.get("sj_nm", ""),
                    header_raw="", row_raw=_join([r.get("account_nm", ""), r.get("thstrm_amount", "")]),
                    row_label=r.get("account_nm", ""), amount_won=amt, unit_raw=r.get("currency", ""),
                    location="API fnlttSinglAcntAll", status=st, note=nt))


def collect_financials_api(t):
    """재무제표 API로 재무 줄을 받음 — 사업보고서 경로 (다 3번)"""
    RUN["where"] = f"{t['borrower']} · 3번 재무"
    ok = {t["rcept_no"], t["latest_rcept_no"]}
    for fs_div in ("OFS", "CFS"):
        d = call_api("fnlttSinglAcntAll", corp_code=t["corp_code"], bsns_year="2025", reprt_code="11011",
                     fs_div=fs_div)
        year, note = "2025", ""
        if d.get("status") == "000":
            got = d["list"][0].get("rcept_no", "") if d.get("list") else ""
            if got not in ok:
                d2 = call_api("fnlttSinglAcntAll", corp_code=t["corp_code"], bsns_year="2026", reprt_code="11011",
                              fs_div=fs_div)
                got2 = d2["list"][0].get("rcept_no", "") if d2.get("status") == "000" and d2.get("list") else ""
                if got2 in ok:
                    d, year, got = d2, "2026", got2
                else:
                    note = "응답 접수번호 다름"
            t["api_rcepts"].append(got)
            if fs_div == "OFS" or not t["fin_year"]:
                t["fin_year"] = year
            _fin_rows_api(t, fs_div, d, year, note)
        elif fs_div == "OFS":
            files = _doc(t["rcept_no"])
            _fin_rows_doc(t, "별도", t["rcept_no"], _sep_audit(files), "별도 감사보고서 없음")
            RUN["where"] = f"{t['borrower']} · 3번 재무"
        else:
            _put("financials", borrower=t["borrower"], corp_code=t["corp_code"], fs_div="연결", route="재무제표 API",
                 rcept_no="", bsns_year="2025", location="API fnlttSinglAcntAll", status="자료 없음")
    if not t["fin_year"]:
        t["fin_year"] = "2025"


def _fs_area_end(f):
    """주석 구역 시작 블록 번호 — 제목(공백 제거)이 '주석'이거나 '주석'으로 끝나는 첫 제목 (D7)"""
    return next((i for i, b in enumerate(f["blocks"]) if b["kind"] == "제목"
                 and _nospace(b["text"]).endswith("주석")), None)


def _find_table(f, names, end):
    """주석 구역 앞에서 줄 이름이 names 중 하나인 줄이 든 첫 표의 블록 번호 (D7)"""
    for i, b in enumerate(f["blocks"][:end]):
        if b["kind"] != "표":
            continue
        for r in b["rows"]:
            if r["cells"] and _item_name_doc(r["cells"][0][2]) in names:
                return i
    return None


def _fin_rows_doc(t, label, rcept_no, f, missing_note):
    """원문 문서 1개에서 재무상태표·손익계산서 줄을 읽어 financials에 적음"""
    base = dict(borrower=t["borrower"], corp_code=t["corp_code"], fs_div=label, route="감사보고서 원문",
                rcept_no=rcept_no, bsns_year="")
    if f is None:
        _put("financials", **base, status="원문 확인", note=missing_note)
        return
    end = _fs_area_end(f)
    if end is None:
        for item, sjs, _acc, _rule in ITEM_RULES:
            _put("financials", **base, sj_div="BS" if "BS" in sjs else "IS", item=item,
                 location=f["name"], status="원문 확인", note="주석 시작 못 찾음")
        return
    found, tables = set(), set()
    for sj, names in (("BS", ("자산총계",)), ("IS", REVENUE_NAMES)):
        i = _find_table(f, names, end)
        if i is None:
            continue
        tables.add(sj)
        b = f["blocks"][i]
        unit_raw = _table_unit(f["blocks"], i)
        mult = _unit(unit_raw) if unit_raw else None
        for r in b["rows"]:
            if not r["cells"]:
                continue
            label_raw = r["cells"][0][2]
            name = _item_name_doc(label_raw)
            for item, sjs, _acc, rule in ITEM_RULES:
                want = "BS" if "BS" in sjs else "IS"
                if want != sj or not rule(name):
                    continue
                found.add(item)
                txt, val, knote, problem, raw = _current_value(b["rows"], r)
                amt = _int_text(val * mult) if (val is not None and mult) else None
                if amt is None and val is None and not problem and raw == "-":
                    # H2 — 당기 칸 글자가 "-"이면 0원
                    amt, st, nt = "0", "수집", _add_note(knote, '당기 칸 글자 "-" → 0원')
                elif amt is None:
                    if val is None:
                        # F5 — 숫자가 아닌 당기 칸 글자를 적음
                        why = problem or (f'당기 칸 글자 "{raw}"' if raw else "당기 칸 숫자 없음")
                    else:
                        why = "단위 모름" if not mult else "원 단위 정수 아님"
                    st, nt = "원문 확인", _add_note(knote, why)
                else:
                    st, nt = "수집", knote
                _put("financials", **base, sj_div=sj, item=item, account_nm=label_raw, amount_won=amt or "",
                     unit_raw=unit_raw, location=_loc(f, b), status=st, note=nt)
                if item == "제품·상품 매출":
                    _MEMO["sales1"].setdefault(t["borrower"], []).append(dict(
                        fs=label, source="감사보고서 원문", rcept_no=rcept_no, table_title=_table_title(f["blocks"], i),
                        header_raw=_first_header_raw(b["rows"]), row_raw=_join([c[2] for c in r["cells"]]),
                        row_label=label_raw, amount_won=amt or "", unit_raw=unit_raw, location=_loc(f, b),
                        status=st, note=nt))
    for item, sjs, _acc, _rule in ITEM_RULES:
        if item in found:
            continue
        sj = "BS" if "BS" in sjs else "IS"
        # F4 — 별도의 비지배지분 · 손익계산서의 제품·상품 매출 줄이 없으면 자료 없음
        if item == "비지배지분" and label == "별도" and "BS" in tables:
            st, nt = "자료 없음", "별도 재무제표에는 비지배지분 줄 없음"
        elif item == "제품·상품 매출" and "IS" in tables:
            st, nt = "자료 없음", "손익계산서에 제품·상품 구분 줄 없음 (매출 구성은 sales_mix 후보로 판정)"
        else:
            st, nt = "원문 확인", "표에서 줄을 찾지 못함"
        _put("financials", **base, sj_div=sj, item=item, location=f["name"], status=st, note=nt)


def collect_financials_doc(t):
    """감사보고서 원문에서 재무 줄을 읽음 — 별도·연결 (다 4번)"""
    RUN["where"] = f"{t['borrower']} · 4번 재무"
    files = _doc(t["rcept_no"])
    _fin_rows_doc(t, "별도", t["rcept_no"], _body(files), "원문 파일 없음")
    period = re.search(r"\(\d{4}\.\d{2}\)", t["report_nm"] or t["report_kind"])
    period = period.group(0) if period else ""
    cands = [e for e in list_disclosures(t["corp_code"], pblntf_detail_ty="F002")
             if period and period in e["report_nm"]]
    if not cands:
        _put("financials", borrower=t["borrower"], corp_code=t["corp_code"], fs_div="연결", route="감사보고서 원문",
             status="자료 없음", note="연결감사보고서 없음")
        return
    rc = max(e["rcept_no"] for e in cands)
    _fin_rows_doc(t, "연결", rc, _body(_doc(rc)), "원문 파일 없음")


def _first_hit(f, terms):
    """파일 글·표에서 terms 중 처음 나온 말과 위치"""
    for term in terms:
        for b in f["blocks"]:
            if term in b["text"]:
                return term, _loc(f, b)
    return None, ""


_OPINION_WORDS = ("의견거절", "부적정의견", "한정의견", "적정의견")
_OPINION_PHRASES = ("적정하게 표시하고 있습니다", "공정하게 표시하고 있습니다")
_BASIS = re.compile(r"감사의견\s*근거")


def _opinion(f):
    """감사의견 — '감사의견' 제목 다음부터 '감사의견근거' 제목 앞까지의 문단에서 찾음 (D8)
    돌려줌: (의견, 찾은 블록, 근거 말, 범위 안 몇째 문단, 원문 확인 이유)"""
    bl = f["blocks"]
    hi = next((i for i, b in enumerate(bl) if b["kind"] != "표" and b["text"].startswith("감사의견")
               and not _BASIS.match(b["text"])), None)
    if hi is None:
        return None, None, "", 0, "감사의견 원문 확인 — 제목에 '감사의견'이 든 부분 없음"
    paras, closed = [], False
    first = bl[hi]["text"][len("감사의견"):].strip()
    for b, text in [(bl[hi], first)] + [(b, b["text"]) for b in bl[hi + 1:] if b["kind"] != "표"]:
        m = _BASIS.search(text)
        if m:
            text, closed = text[:m.start()].strip(), True
        if text:
            paras.append((b, text))
        if closed:
            break
    if not closed:
        return None, None, "", 0, "감사의견근거 제목 못 찾음"
    # F2 — 원문 글과 찾는 말 모두 공백을 지우고 비교함
    best = None
    for pi, (b, text) in enumerate(paras, 1):
        for w in _OPINION_WORDS:
            p = _nospace(text).find(_nospace(w))
            if p >= 0 and (best is None or (pi, p) < best[:2]):
                best = (pi, p, w, b)
    if best:
        return best[2], best[3], best[2], best[0], ""
    for pi, (b, text) in enumerate(paras, 1):
        for ph in _OPINION_PHRASES:
            if _nospace(ph) in _nospace(text):
                return "적정의견", b, ph, pi, ""
    return None, None, "", 0, "감사의견 원문 확인 — 감사의견 부분에서 의견 말·문구를 찾지 못함"


_KISU_YEAR = re.compile(r"제(\d+)기\((\d{4})\)")


def _audit_current_rows(lst, year):
    """감사의견 API의 당기 줄 — '당기' 글자가 든 줄, 없으면 H4 규칙 (제n기(연도)는 연도 = 사업연도, 제n기는 n이 가장 큰 줄)
    돌려줌: (당기 줄 목록, 정한 방법 note)"""
    cur = [r for r in lst if "당기" in (r.get("bsns_year") or "")]
    if cur:
        return cur, ""
    by_year = [(r, _KISU_YEAR.fullmatch(_nospace(r.get("bsns_year")))) for r in lst]
    if any(m for _r, m in by_year):
        sel = [r for r, m in by_year if m and m.group(2) == year]
    else:
        by_n = [(r, re.fullmatch(r"제(\d+)기", _nospace(r.get("bsns_year")))) for r in lst]
        ns = [int(m.group(1)) for _r, m in by_n if m]
        sel = [r for r, m in by_n if m and int(m.group(1)) == max(ns)] if ns else []
    if not sel:
        return [], ""
    names = " · ".join(dict.fromkeys(_nospace(r.get("bsns_year")) for r in sel))
    return sel, f"'당기' 글자 없음 → 당기 줄 = {names}"


def collect_audit(t):
    """감사의견·회계 기준을 적음 (다 5번)"""
    RUN["where"] = f"{t['borrower']} · 5번 감사의견"
    row = dict(borrower=t["borrower"], corp_code=t["corp_code"], route="", rcept_no=t["rcept_no"])
    states, locs = [], []
    if t["route"] == "사업보고서":
        row["route"] = "재무제표 API"
        d = call_api("accnutAdtorNmNdAdtOpinion", corp_code=t["corp_code"], bsns_year=t["fin_year"] or "2025",
                     reprt_code="11011")
        locs.append("API accnutAdtorNmNdAdtOpinion")
        if d.get("status") == "013":
            states.append(("자료 없음", "감사의견 자료 없음 — API 013"))
        else:
            lst = d.get("list", [])
            has_op = [r for r in lst if (r.get("adt_opinion") or "").strip() not in ("", "-")]
            if not has_op:
                # H3 — 의견 값이 있는 줄이 없으면 사업보고서 압축 파일 안 별도 감사보고서에서 읽음 (D8·F2 방법)
                row["route"] = "감사보고서 원문"
                locs.clear()
                fa = _sep_audit(_doc(t["rcept_no"]))
                op, blk, _ev, _pi, why = _opinion(fa) if fa else (None, None, "", 0, "별도 감사보고서 없음")
                if op:
                    row["opinion_raw"] = op
                    states.append(("수집", "감사의견 API에 의견 값 없음 → 별도 감사보고서에서 읽음"))
                else:
                    states.append(("원문 확인", "감사의견 API에 의견 값 없음 → " + why))
                locs.append(_loc(fa, blk) if blk else (fa["name"] if fa else ""))
            else:
                cur, how = _audit_current_rows(lst, t["fin_year"] or "2025")
                # E1 — 4개 칸이 모두 있고 adt_opinion이 빈 값·'-'가 아닌 당기 줄만 씀
                use = [r for r in cur if all(k in r for k in ("bsns_year", "adtor", "adt_opinion", "stlm_dt"))
                       and (r.get("adt_opinion") or "").strip() not in ("", "-")]
                skipped = len(cur) - len(use)
                ops = list(dict.fromkeys(r["adt_opinion"] for r in use))
                auds = list(dict.fromkeys(r["adtor"] for r in use))
                if not cur:
                    states.append(("원문 확인", "감사의견 원문 확인 — '당기' 줄 없음"))
                elif not use:
                    states.append(("원문 확인", "감사의견 원문 확인 — 쓸 수 있는 당기 줄 없음: " + str(cur[0])))
                elif len(ops) > 1:
                    states.append(("원문 확인", "감사의견 원문 확인 — 당기 줄 값이 다름: "
                                   + " / ".join(f"{r['adtor']} {r['adt_opinion']}" for r in use)))
                else:
                    row["opinion_raw"] = ops[0]
                    row["rcept_no"] = use[0].get("rcept_no", t["rcept_no"])
                    if len(auds) > 1:
                        # H4 — 감사의견 값이 모두 같고 감사인만 다르면 감사인은 빈 값
                        states.append(("수집", "감사인 값이 둘 — " + " · ".join(auds)))
                    else:
                        row["auditor"] = auds[0]
                        states.append(("수집", ""))
                if how:
                    states.append(("수집", how))
                if cur and skipped:
                    states.append(("수집", f"칸 빠진 당기 줄 {skipped}개"))
        f = _sep_audit(_doc(t["rcept_no"]))
    else:
        row["route"] = "감사보고서 원문"
        f = _body(_doc(t["rcept_no"]))
        op, blk, _ev, _pi, why = _opinion(f) if f else (None, None, "", 0, "원문 문서 없음")
        if op:
            row["opinion_raw"] = op
            states.append(("수집", ""))
        else:
            states.append(("원문 확인", why))
        locs.append(_loc(f, blk) if blk else (f["name"] if f else ""))
    if f is None and t["route"] == "사업보고서":
        # H5 — 별도 감사보고서 파일이 없으면 사업보고서 본문에서 같은 규칙으로 찾음
        f = _main_report(_doc(t["rcept_no"]))
        if f is not None:
            states.append(("수집", "별도 감사보고서 없음 → 사업보고서 본문에서 회계 기준을 찾음"))
    if f is None:
        states.append(("원문 확인", "회계 기준 원문 확인 — 원문 문서 없음"))
    else:
        term, loc = _first_hit(f, ("한국채택국제회계기준",))
        if not term:
            term, loc = _first_hit(f, ("일반기업회계기준",))
        if term:
            row["accounting_standard"] = term
            states.append(("수집", ""))
            locs.append(loc)
        else:
            states.append(("원문 확인", "회계 기준 원문 확인 — 두 말 모두 없음"))
            locs.append(f["name"])
    st = "원문 확인" if any(s == "원문 확인" for s, _ in states) else (
        "자료 없음" if any(s == "자료 없음" for s, _ in states) else "수집")
    _put("audit", **row, location=" · ".join(x for x in locs if x), status=st,
         note=" · ".join(n for _, n in states if n))


def _doc_note(t):
    """6·7번에서 latest_rcept_no와 다른 원문을 쓴 줄의 note (014 처리 가)"""
    if t["doc_rcept_no"] != t["latest_rcept_no"]:
        return f"첨부정정 {t['latest_rcept_no']} 원문 없음(014) — {t['doc_rcept_no']} 원문 사용"
    return ""


def _sales_doc_rows(t, f, s, e, source, rc):
    out = 0
    bl = f["blocks"]
    for i in range(s, e):
        b = bl[i]
        if b["kind"] != "표":
            continue
        title = _table_title(bl, i)
        header = _first_header_raw(b["rows"])
        if "매출" not in title and "매출" not in header:
            continue
        for r in b["rows"]:
            if not r["cells"]:
                continue
            first = r["cells"][0][2]
            if "제품" not in first and "상품" not in first:
                continue
            _put("sales_mix", borrower=t["borrower"], corp_code=t["corp_code"], group=t["group_sales_mix"],
                 source=source, rcept_no=rc, table_title=title, header_raw=header,
                 row_raw=_join([c[2] for c in r["cells"]]), row_label=first, amount_won="",
                 unit_raw=_table_unit(bl, i), location=_loc(f, b), status="수집", note=_doc_note(t))
            out += 1
    return out


def collect_sales_mix(t):
    """매출 구성 후보 줄을 모두 적음 (다 6번)"""
    RUN["where"] = f"{t['borrower']} · 6번 매출 구성"
    n = 0
    first = _MEMO["sales1"].get(t["borrower"], [])
    for fs in ("별도", "연결"):
        for r in first:
            if r["fs"] != fs:
                continue
            _put("sales_mix", borrower=t["borrower"], corp_code=t["corp_code"], group=t["group_sales_mix"],
                 **{k: v for k, v in r.items() if k != "fs"})
            n += 1
    rc = t["doc_rcept_no"]
    files = _doc(rc)
    if t["route"] == "사업보고서":
        mf = _main_report(files)
        if mf:
            bl = mf["blocks"]
            s = next((i for i, b in enumerate(bl) if b["kind"] == "제목"
                      and re.match(r"^(II|Ⅱ)\s*\.\s*사업의\s*내용", b["text"])), None)
            if s is not None:
                e = next((i for i in range(s + 1, len(bl)) if bl[i]["kind"] == "제목"
                          and re.match(r"^(III|Ⅲ|IV|Ⅳ|V|Ⅴ)\s*\.", bl[i]["text"])), len(bl))
                n += _sales_doc_rows(t, mf, s + 1, e, "사업보고서 사업의 내용", rc)
        af = _sep_audit(files)
    else:
        af = _body(files)
    if af:
        s, e = _notes_area(af)
        n += _sales_doc_rows(t, af, s, e, "감사보고서 주석", rc)
    if not n:
        _put("sales_mix", borrower=t["borrower"], corp_code=t["corp_code"], group=t["group_sales_mix"],
             rcept_no=rc, status="자료 없음", note=_doc_note(t))


def find_energy_terms(t):
    """사업보고서에서 에너지 찾는 말과 앞뒤 100자를 적음 (다 7번)"""
    RUN["where"] = f"{t['borrower']} · 7번 에너지"
    rc = t["doc_rcept_no"]
    hits = []
    for fi, f in enumerate(_doc(rc)):
        parts, offs, pos = [], [], 0
        for b in f["blocks"]:
            offs.append((pos, b))
            parts.append(b["text"])
            pos += len(b["text"]) + 1
        full = " ".join(parts)
        for ti, term in enumerate(ENERGY_TERMS):
            pat = re.escape(term)
            if re.fullmatch(r"[A-Za-z0-9]+", term):
                pat = rf"(?<![A-Za-z]){pat}(?![A-Za-z])"
            for m in re.finditer(pat, full):
                blk = next(b for o, b in reversed(offs) if o <= m.start())
                ctx = full[max(0, m.start() - 100):m.end() + 100]
                hits.append((fi, m.start(), ti, term, ctx, _loc(f, blk)))
    for _fi, _p, _ti, term, ctx, loc in sorted(hits):
        _put("energy_terms", borrower=t["borrower"], corp_code=t["corp_code"], rcept_no=rc, term=term, context=ctx,
             location=loc, status="수집", note=_doc_note(t))
    if not hits:
        _put("energy_terms", borrower=t["borrower"], corp_code=t["corp_code"], rcept_no=rc, status="자료 없음",
             note=_doc_note(t))


def _line_doc(files, doc_basis):
    if doc_basis.startswith("사업보고서 별도 주석"):
        return _main_report(files)
    return _sep_audit(files) or (_body(files) if len(files) == 1 else None)


def _basis_notes(doc_basis):
    """doc_basis의 '색인:'·'목차:' 뒤 주석 (번호, 제목) 목록"""
    m = re.search(r"(?:색인|목차):\s*(.*?)(?:\s·\s|$)", doc_basis)
    if not m:
        return []
    return [(int(n), t.strip()) for n, t in
            re.findall(r"(\d{1,2})\s*\.\s*(.*?)(?=,\s*\d{1,2}\s*\.|$)", m.group(1))]


def _basis_ranges(f, doc_basis):
    """doc_basis에 적힌 주석들의 블록 범위 — 다 9번 주석 정의 (D10). 정하지 못하면 빈 목록"""
    s, e = _notes_area(f)
    heads = _note_heads(f, s, e)
    out = []
    for num, title in _basis_notes(doc_basis):
        want = _nospace(f"{num}.{title}")
        for hi, (i, k, _t9) in enumerate(heads):
            have = _nospace(f["blocks"][i]["text"])
            if k == num and (have.startswith(want) or want.startswith(have)):
                out.append((i, heads[hi + 1][0] if hi + 1 < len(heads) else e))
                break
    return out


def _grid_text(row):
    return [g[2] for g in row["grid"]]


def _search_lines(f, ranges, key, mult, amt, by_amount_only):
    """범위(블록 번호) 안 표에서 차입처 글자(공백 무시)와 금액(단위 환산)이 같은 줄 — 합친 칸 포함 (D9)"""
    found = []
    for a, z in ranges:
        for i in range(a, z):
            b = f["blocks"][i]
            if b["kind"] != "표":
                continue
            for row in b["rows"]:
                texts = _grid_text(row)
                if not by_amount_only and not any(_nospace(x) == key for x in texts):
                    continue
                if any((_num(x) is not None and _num(x) * mult == amt) for x in texts):
                    found.append((i, b, row))
    return found


def collect_loan_lines(targets, lenders, sel):
    """대출 줄 220줄의 원문 줄을 찾아 적음 (다 8번)"""
    lines = [(f"A3-{r['_line']}", r, r["lender_account"], r["lender_raw"], "") for r in sel]
    for lid, rc, raw, amt, bank, note in S_LINES:
        cand = [r for r in lenders if r["rcept_no"] == rc and _dec(r["amount_won"]) == Decimal(amt)
                and r["lender_account"] not in BANKS and (not raw or r["lender_raw"] == raw)]
        if len(cand) != 1:
            RUN["where"] = f"{lid} · 8번 대출 줄"
            _stop(f"보정 줄의 원래 차입처 줄이 1줄이 아님 — {len(cand)}줄")
        lines.append((lid, cand[0], bank, cand[0]["lender_raw"], note))
    order = {t["borrower"]: t["no"] for t in targets}
    lines.sort(key=lambda x: (order[x[1]["account"]], x[1]["_line"]))
    if len(lines) != 220:
        _stop(f"대출 줄 수 다름 — {len(lines)}줄 (명세 220줄)")
    for lid, r, bank, raw, note in lines:
        RUN["where"] = f"{r['account']} · {lid} · 8번 대출 줄"
        amt = _dec(r["amount_won"])
        mult = UNIT_MULT.get(_nospace(r["unit"]))
        f = _line_doc(_doc(r["rcept_no"]), r["doc_basis"])
        by_amount_only = lid == "S1-2"
        found, outside, scope = [], False, ""
        if f is not None and mult:
            key = _nospace(raw)
            ranges = _basis_ranges(f, r["doc_basis"])
            if ranges:
                found = _search_lines(f, ranges, key, mult, amt, by_amount_only)
                scope = "주석 범위"
            if not ranges or not found:
                scope = ("주석 범위 0줄" if ranges else "주석 범위 못 정함") + " → 문서 전체"
                found = _search_lines(f, [(0, len(f["blocks"]))], key, mult, amt, by_amount_only)
                outside = True
        a3 = _int_text(amt) if amt is not None else ""
        base = dict(line_id=lid, borrower=r["account"], bank=bank, rcept_no=r["rcept_no"], lender_raw=raw,
                    amount_won_a3=a3 if a3 is not None else r["amount_won"], match_count=str(len(found)))
        if len(found) == 1:
            i, b, row = found[0]
            head = _header_cells(b["rows"])
            filled = any(g[3] for g in row["grid"]) or bool(head and any(g[3] for g in head[0]["grid"]))
            nt = note
            if filled:
                nt = _add_note(nt, "합친 칸 글자를 내려 적음")
            if outside:
                nt = _add_note(nt, "차입금 주석 밖에서 찾음")
            _put("loan_lines", **base, table_title=_table_title(f["blocks"], i),
                 header_raw=_join(_grid_text(head[0])) if head else "", row_raw=_join(_grid_text(row)),
                 location=_loc(f, b), status="수집", note=nt)
        else:
            why = ("원문 문서 없음" if f is None else "단위 모름" if not mult else
                   f"{scope} 찾은 줄 {len(found)}줄"
                   + ("" if not found else " — " + " · ".join(_loc(f, b) for _, b, _r in found)))
            _put("loan_lines", **base, location=f["name"] if f else "", status="원문 확인", note=_add_note(note, why))


def extract_notes(t):
    """주석 19곳의 문단·표 줄을 적음 (다 9번)"""
    RUN["where"] = f"{t['borrower']} · 9번 주석"
    words = NOTE_WORDS[t["group_notes"]]
    files = _doc(t["rcept_no"])
    f = _sep_audit(files) if t["route"] == "사업보고서" else _body(files)
    base = dict(borrower=t["borrower"], corp_code=t["corp_code"], rcept_no=t["rcept_no"], purpose=t["group_notes"])
    if f is None:
        _put("notes_text", **base, status="원문 확인", note="별도 감사보고서 없음")
        return
    s, e = _notes_area(f)
    heads = _note_heads(f, s, e)
    n = 0
    for hi, (i, k, title9) in enumerate(heads):
        if not any(w in title9 for w in words):
            continue
        end = heads[hi + 1][0] if hi + 1 < len(heads) else e
        heading = f["blocks"][i]["text"][:40]
        for b in f["blocks"][i:end]:
            if b["kind"] == "표":
                for row in b["rows"]:
                    texts = [c[2] for c in row["cells"]]
                    if not any(texts):
                        continue
                    txt = _join(texts)
                    _put("notes_text", **base, heading=heading, kind="표 줄", text_raw=txt,
                         bank_mentioned=_bank_mentioned(txt), location=_loc(f, b), status="수집")
                    n += 1
            else:
                _put("notes_text", **base, heading=heading, kind="문단", text_raw=b["text"],
                     bank_mentioned=_bank_mentioned(b["text"]), location=_loc(f, b), status="수집")
                n += 1
    if not n:
        _put("notes_text", **base, location=f["name"], status="원문 확인", note="찾는 주석 제목 없음")


def collect_legal(t):
    """법적 절차 관련 공시를 적음 (다 10번)"""
    RUN["where"] = f"{t['borrower']} · 10번 법적 절차"
    if not t["corp_code"]:
        _put("legal", borrower=t["borrower"], status="원문 확인", note="고유번호 없음")
        return
    n = 0
    for ty in ("B", "I"):
        for e in list_disclosures(t["corp_code"], pblntf_ty=ty):
            terms = [w for w in LEGAL_TERMS if w in e["report_nm"]]
            if terms:
                _put("legal", borrower=t["borrower"], corp_code=t["corp_code"], pblntf_ty=ty, rcept_no=e["rcept_no"],
                     rcept_dt=e.get("rcept_dt", ""), report_nm=e["report_nm"], matched_term=" · ".join(terms),
                     status="수집")
                n += 1
    if not n:
        _put("legal", borrower=t["borrower"], corp_code=t["corp_code"], status="자료 없음")


def collect_company(t):
    """기업개황을 적음 (다 11번)"""
    RUN["where"] = f"{t['borrower']} · 11번 기업개황"
    if not t["corp_code"]:
        t["items"][11] = ("원문 확인", "11번 원문 확인 — 고유번호 없음")
        return
    d = call_api("company", corp_code=t["corp_code"])
    if d.get("status") != "000":
        t["items"][11] = ("자료 없음", "11번 자료 없음 — 기업개황 응답 013")
        return
    for k, col in (("corp_name", "corp_name_official"), ("jurir_no", "jurir_no"), ("adres", "address"),
                   ("induty_code", "induty_code"), ("acc_mt", "acc_mt"), ("corp_cls", "corp_cls"),
                   ("est_dt", "est_dt")):
        t[col] = d.get(k, "")


def collect_employees(t):
    """직원 수를 적음 (다 12번)"""
    RUN["where"] = f"{t['borrower']} · 12번 직원 수"
    t["employees"] = ""
    if not t["route"]:
        t["items"][12] = ("원문 확인", "12번 원문 확인 — 공시 종류를 정하지 못함")
        return
    if t["route"] != "사업보고서":
        t["items"][12] = ("수집", "12번 감사보고서 경로 — 수집하지 않음")
        return
    d = call_api("empSttus", corp_code=t["corp_code"], bsns_year=t["fin_year"] or "2025", reprt_code="11011")
    if d.get("status") != "000":
        t["items"][12] = ("자료 없음", "12번 자료 없음 — 직원 현황 응답 013")
        return
    tot = ("합계", "계", "전체")
    lst = d.get("list", [])
    cur = [r for r in lst if _nospace(r.get("fo_bbm")) in tot and _nospace(r.get("sexdstn")) in tot]
    vals = {(r.get("sm") or "").strip() for r in cur}
    if cur:
        if len(vals) == 1 and "" not in vals:
            t["employees"] = vals.pop()
        else:
            t["items"][12] = ("원문 확인", "12번 원문 확인 — 합계 줄 여러 개: " + " / ".join(sorted(vals)))
        return
    # E2 — 합계 줄이 없으면 성별 줄의 sm을 모두 더함
    sub = tot + ("소계",)
    sms = [(r.get("sm") or "").replace(",", "").strip() for r in lst]
    divs = {_nospace(r.get("fo_bbm")) for r in lst}
    if not lst:
        t["items"][12] = ("원문 확인", "12번 원문 확인 — 직원 현황 줄 없음")
    elif any(_nospace(r.get("sexdstn")) in sub for r in lst):
        t["items"][12] = ("원문 확인", "12번 원문 확인 — 성별 칸에 합계·계·전체·소계 줄 있음")
    elif not all(re.fullmatch(r"\d+", s) for s in sms):
        t["items"][12] = ("원문 확인", "12번 원문 확인 — sm이 숫자가 아님: " + " / ".join(sms))
    elif divs & set(sub) and divs - set(sub):
        t["items"][12] = ("원문 확인", "12번 원문 확인 — 사업부문 합계·소계 줄과 다른 부문 줄이 함께 있음")
    else:
        t["employees"] = str(sum(int(s) for s in sms))
        t["items"][12] = ("수집", f"12번 남·여 줄 합 ({len(lst)}줄)")


def write_outputs(targets):
    """결과 파일 9개를 씀 (4-5-4 라)"""
    for t in targets:
        states = [t["items"][k] for k in sorted(t["items"])]
        st = "원문 확인" if any(s == "원문 확인" for s, _ in states) else (
            "자료 없음" if any(s == "자료 없음" for s, _ in states) else "수집")
        _put("targets", **{c: t.get(c, "") for c in COLS["targets"] if c not in ("status", "note", "collected_at",
                                                                              "version")},
             status=st, note=" · ".join(n for _, n in states if n))
        ROWS["targets"][-1]["no"] = str(t["no"])
    for name, cols in COLS.items():
        for r in ROWS[name]:
            if r.get("status") and r["status"] not in STATUSES:
                _stop(f"status 값이 세 가지 밖임 — {name} {r['status']}")
    OUT_PUB.mkdir(parents=True, exist_ok=True)
    OUT_RAW.mkdir(parents=True, exist_ok=True)
    for name, cols in COLS.items():
        with open(FILES[name], "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            for r in ROWS[name]:
                w.writerow([r.get(c, "") for c in cols])


def _pct(a, b):
    if not b:
        return None
    return ((Decimal(a) - Decimal(b)) / Decimal(b) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def run_checks(targets, lenders):
    """수집 검사 1~9를 실행하고 출력함 (4-5-4 마)"""
    fin = ROWS["financials"]
    kinds = {"PASS": 0, "FAIL": 0, "LIST": 0, "INFO": 0}

    def amounts(b, fs, item):
        return [Decimal(r["amount_won"]) for r in fin if r["borrower"] == b and r["fs_div"] == fs
                and r["item"] == item and r["amount_won"]]

    # 수집 #01
    out = []
    for t in targets:
        for fs in ("별도", "연결"):
            a, l_, e = (amounts(t["borrower"], fs, k) for k in ("자산총계", "부채총계", "자본총계"))
            if not (a or l_ or e):
                continue
            if len(set(a)) == 1 and len(set(l_)) == 1 and len(set(e)) == 1:
                diff = a[0] - (l_[0] + e[0])
                if diff:
                    out.append((t["borrower"], f"  {t['borrower']} {fs} — 차이 {diff}원"))
            else:
                out.append((t["borrower"], f"  {t['borrower']} {fs} — 차이 계산 불가 (자산 {len(set(a))}값 · "
                                           f"부채 {len(set(l_))}값 · 자본 {len(set(e))}값)"))
    print(f"[LIST] 수집 #01 자산 = 부채 + 자본 — {len({b for b, _ in out})}곳")
    for _, ln in out:
        print(ln)
    kinds["LIST"] += 1
    # 수집 #02
    for t in targets:
        fs_sum = sum((Decimal(r["amount_won"]) for r in fin if r["borrower"] == t["borrower"] and r["fs_div"] == "별도"
                      and r["item"] == "차입·사채·리스" and r["amount_won"]), Decimal(0))
        a3 = sum((_dec(r["amount_won"]) or Decimal(0) for r in lenders if r["account"] == t["borrower"]), Decimal(0))
        p = _pct(a3, fs_sum)
        a3s = _int_text(a3) if _int_text(a3) is not None else str(a3)
        print(f"[INFO] 수집 #02 차입금 대조 — {t['borrower']} 재무제표 {fs_sum}원 · 원래 차입처 줄 {a3s}원 · 차이율 "
              + (f"{p}%" if p is not None else "계산 불가 (재무제표 0원)"))
    kinds["INFO"] += 1
    # 수집 #03
    out = []
    for t in targets:
        vals = amounts(t["borrower"], "별도", "매출") + amounts(t["borrower"], "연결", "매출")
        if not vals:
            out.append(f"  {t['borrower']} — 매출 없음")
        elif any(v == 0 for v in vals):
            out.append(f"  {t['borrower']} — 매출 0")
        elif any(v < 0 for v in vals):
            out.append(f"  {t['borrower']} — 매출 음수")
    print(f"[LIST] 수집 #03 매출 — {len(out)}곳")
    for ln in out:
        print(ln)
    kinds["LIST"] += 1
    # 수집 #04
    out = []
    for t in targets:
        ok = {t["rcept_no"], t["latest_rcept_no"]}
        diff = [g for g in t["api_rcepts"] if g and g not in ok]
        if diff or t["latest_rcept_no"] != t["rcept_no"]:
            got = " · ".join(dict.fromkeys(t["api_rcepts"])) or t["rcept_no"]
            out.append(f"  {t['borrower']} — 응답 {got} · 표 {t['rcept_no']} · 정정본 {t['latest_rcept_no']}")
    print(f"[LIST] 수집 #04 접수번호 — {len(out)}곳")
    for ln in out:
        print(ln)
    kinds["LIST"] += 1
    # 수집 #05
    out = [t for t in targets if t["corp_code_source"] != "표"]
    print(f"[LIST] 수집 #05 고유번호 — {len(out)}곳")
    for t in out:
        code = t["corp_code"] if t["corp_code_source"] == "corpCode 찾음" else "원문 확인"
        print(f"  {t['borrower']} — {code} (근거 접수번호 {t['evidence'] or t['rcept_no']})")
    kinds["LIST"] += 1
    # 수집 #06
    out = [r for r in ROWS["loan_lines"] if r["match_count"] != "1"]
    print(f"[LIST] 수집 #06 대출 줄 찾기 — {len(out)}줄")
    for r in out:
        print(f"  {r['line_id']} {r['borrower']} — {r['match_count']}줄")
    kinds["LIST"] += 1
    # 수집 #07
    cnt = {k: sum(1 for r in ROWS[k] if r.get("status") == "원문 확인")
           for k in ("targets", "financials", "audit", "sales_mix", "loan_lines", "legal", "energy_terms",
                     "notes_text")}
    print("[INFO] 수집 #07 원문 확인 — " + " · ".join(f"{k} {v}" for k, v in cnt.items()))
    kinds["INFO"] += 1
    # 수집 #08
    bad = []
    for p in sorted(OUT_PUB.glob("*")):
        with open(p, encoding="utf-8-sig", newline="") as f:
            head = next(csv.reader(f), [])
        for c in head:
            if any(w in c for w in ("종가", "시가총액", "상장주식수", "market_cap")):
                bad.append(f"{p.name} {c}")
    if bad:
        for b in bad:
            print(f"[FAIL] 수집 #08 공개 폴더 거래소 숫자 — {b}")
        kinds["FAIL"] += 1
    else:
        print("[PASS] 수집 #08 공개 폴더 거래소 숫자")
        kinds["PASS"] += 1
    # 수집 #09
    if RUN["gitignore"]:
        print("[PASS] 수집 #09 .gitignore")
        kinds["PASS"] += 1
    else:
        print("[FAIL] 수집 #09 .gitignore — 두 줄 없음")
        kinds["FAIL"] += 1
    print(f"수집 검사 PASS {kinds['PASS']} · FAIL {kinds['FAIL']} · LIST {kinds['LIST']} · INFO {kinds['INFO']}")
    return 1 if kinds["FAIL"] else 0


def main():
    """수집 1~12번과 수집 검사를 차례로 실행함"""
    now = datetime.now()
    RUN["date"], RUN["end_de"] = now.strftime("%Y-%m-%d"), now.strftime("%Y%m%d")
    check_gitignore()
    targets, lenders, sel = load_targets()
    find_corp_codes(targets)
    for t in targets:
        check_reports(t)
    for t in targets:
        if t["route"] == "사업보고서":
            collect_financials_api(t)
        elif t["route"] == "감사보고서":
            collect_financials_doc(t)
    for t in targets:
        if t["route"]:
            collect_audit(t)
    for t in targets:
        if t["group_sales_mix"]:
            collect_sales_mix(t)
    for t in targets:
        if t["group_energy"]:
            find_energy_terms(t)
    collect_loan_lines(targets, lenders, sel)
    for t in targets:
        if t["group_notes"]:
            extract_notes(t)
    for t in targets:
        collect_legal(t)
    for t in targets:
        collect_company(t)
    for t in targets:
        collect_employees(t)
    RUN["where"] = ""
    write_outputs(targets)
    sys.exit(run_checks(targets, lenders))


if __name__ == "__main__":
    main()
