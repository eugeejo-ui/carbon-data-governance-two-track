"""금융1-1 금융 트랙 모집단 추출과 업권 분류 (금융 트랙 공통 기준표·공통 함수 포함)

- DART 고유번호 목록에서 상장사를 뽑고, 회사개황 API(company)로 표준산업분류(induty_code)를 받아
  금융·보험업(KSIC 대분류 K: 64·65·66)만 남김
- 이름으로 추리지 않음. 사명에 업권이 드러나지 않는 곳(카카오뱅크·한국금융지주 등)을 놓치지 않기 위함
- 이 파일에는 금융 트랙 전체가 쓰는 기준표와 함수가 들어 있음. 기준을 바꿀 때는 여기만 고침
  - 기준표: SECTOR_BY_CODE·NAME_SECTOR·NAME_NOT_FIN·TRANSLIT·S3_BASIS·FIN_HOLDING·FIX_SECTOR·SHELL·
    SERVICE_ONLY·LENDER_ONLY·PREF·FUND·FOREIGN_FORM·
    지분 문턱(OWN_CONTROL·OWN_REVIEW·REVIEW_ASSET_MIN)·출자현황 대체 보고서(FALLBACK_REPORTS)
  - 함수: key·sector_by_code·sector_by_name·final_sector·service_reason·s3_basis·
    clean_name·is_foreign·to_f·to_won·name2(음역 대조)·extract_subsidiaries(종속회사 추출 전체)
  - 음역표 TRANSLIT: 공정위·FISIS·DART가 한글 음역(케이비·아이비케이)으로 적은 이름을 영문 표기와 맞춤.
    금융1-2·1-2b·1-3A·1-3C가 모두 이 표 하나를 씀 (2026-10-01 통합)
- 기준표를 고친 뒤에는 영향받는 파일을 순서대로 다시 실행함
  fin1_list.py → fin1_sector.py → fin1_subsidiary.py → fin1_nonfin_sub.py → fin1_unlisted.py
  → fin1_indep.py
- 출자현황을 API로 못 받는 모회사(기업은행처럼 양식에 "아래표 참조"만 적은 곳)는
  data/manual/fin_manual_subsidiaries.csv에 감사보고서 원문의 종속회사를 옮겨 적으면 같은 규칙으로 명단에 넣음

출력
  - data/processed/fin_candidates.csv : 금융업 코드로 걸린 상장사 전체
  - data/manual/fin_sector_review.csv : 업권이 "확인 필요"로 나온 계정
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUT = PROC / "fin_candidates.csv"
REVIEW = MANUAL / "fin_sector_review.csv"
CONTROL_DECISIONS = MANUAL / "fin_control_decisions.csv"
MANUAL_SUBS = MANUAL / "fin_manual_subsidiaries.csv"   # 원문에서 옮겨 적은 종속회사 (2026-10-01)

YEAR = "2025"
REPRT = "11011"
# 출자현황이 사업보고서에서 안 잡히면 차례로 봄 — 조용히 빠지는 모회사가 없게 (2026-10-01)
# (기업은행의 IBK캐피탈·IBK연금보험·IBK투자증권이 금융1-2에서 통째로 빠진 사례에서 추가)
FALLBACK_REPORTS = [("11014", "3분기보고서"), ("11012", "반기보고서")]   # 같은 해
PREV_YEAR_ANNUAL = True                                                 # 그래도 없으면 전년 사업보고서

# ───────────────────────── 업권 기준표 ─────────────────────────

# KSIC 10차 금융·보험업 대분류
FIN_PREFIX = ("64", "65", "66")

# 표준산업분류(KSIC 10차) 정식 세세분류 → 업권. 앞에서부터 맞추므로 긴 코드를 먼저 둠
# 출처: 통계청 한국표준산업분류
#   64911 금융리스업 / 64912 개발금융기관 / 64913 신용카드 및 할부금융업(캐피탈사 포함)
#   64919 그외 기타 여신금융업 / 64991 기금 운영업 / 64992 지주회사
#   6492·6493은 존재하지 않는 코드임
SECTOR_BY_CODE = [
    ("64992", "지주회사"),
    ("64991", "기금 운영업"),
    ("64121", "은행"), ("6411", "은행"), ("6412", "은행"),
    ("64132", "저축은행·신협"), ("6413", "저축은행·신협"), ("6419", "은행·기타 예금기관"),
    ("64201", "신탁·집합투자"), ("64209", "신탁·집합투자"), ("642", "신탁·집합투자"),
    ("64911", "금융리스"),
    ("64912", "개발금융기관"),
    ("64913", "카드·할부금융"),
    ("64919", "기타 여신금융"),
    ("6491", "여신금융"),
    ("64999", "그외 기타 금융"), ("6499", "그외 기타 금융"),
    ("65110", "생명보험"), ("6511", "생명보험"),
    ("65121", "손해보험"), ("65122", "보증보험"), ("6512", "손해보험"),
    ("652", "재보험"), ("653", "연금·공제"),
    ("66121", "증권"), ("66122", "선물"), ("6612", "증권"),
    ("66192", "금융지원 서비스"), ("661", "금융지원 서비스"),
    ("66202", "보험 모집·대리"), ("662", "보험 관련 서비스"),
    ("64", "기타 금융(확인 필요)"),
    ("65", "기타 보험(확인 필요)"),
    ("66", "기타 금융서비스(확인 필요)"),
]

# 고유번호가 안 잡혀 코드가 없을 때 쓰는 이름 키워드 — 업권 이름은 SECTOR_BY_CODE와 같은 말을 씀
# 앞에서부터 맞추므로 구체적인 것을 먼저 둠 (저축은행 → 은행, 캐피탈리스 → 캐피탈)
# 끝에 $가 붙은 키워드는 이름 끝에 올 때만 맞춤
NAME_SECTOR = [
    ("저축은행", "저축은행·신협"),
    ("재보험", "재보험"), ("보증보험", "보증보험"),
    ("손해보험", "손해보험"), ("화재", "손해보험"), ("손보", "손해보험"),
    # "생명"만으로는 생명누리(제약)·라이프케어(헬스케어)가 걸리므로 형태를 좁힘
    ("생명보험", "생명보험"), ("라이프생명", "생명보험"),
    ("생명$", "생명보험"), ("생명(주)", "생명보험"), ("생명㈜", "생명보험"),
    ("은행", "은행"), ("뱅크", "은행"),
    ("증권", "증권"), ("선물", "선물"),
    # "리스"만으로는 팰리스·폴라리스·쏠리스가 걸리므로 형태를 좁힘
    ("캐피탈리스", "금융리스"), ("금융리스", "금융리스"),
    ("카드", "카드·할부금융"), ("캐피탈", "카드·할부금융"),    # 64913에 캐피탈사가 들어감
    ("파이낸셜", "여신금융"),
    ("자산운용", "신탁·집합투자"), ("대체투자", "신탁·집합투자"), ("리츠운용", "신탁·집합투자"),
    ("부동산신탁", "신탁·집합투자"), ("자산신탁", "신탁·집합투자"), ("신탁", "신탁·집합투자"),
    ("프라이빗에쿼티", "신탁·집합투자"), ("프라이빗에퀴티", "신탁·집합투자"),
    ("벤처투자", "신탁·집합투자"), ("벤처스", "신탁·집합투자"), ("인베스트", "신탁·집합투자"),
    ("액셀러레이터", "신탁·집합투자"), ("파트너스", "신탁·집합투자"),
    ("에프앤아이", "그외 기타 금융"), ("F&I", "그외 기타 금융"),
    ("신용정보", "금융지원 서비스"),
    ("보험", "보험(확인 필요)"),
]

# 금융지주회사법상 금융지주 — 코드(64992)로는 일반 지주와 구분되지 않아 목록으로 확정함
FIN_HOLDING = ["KB금융지주", "신한금융지주회사", "하나금융지주", "우리금융지주",
               "BNK금융지주", "JB금융지주", "아이엠금융지주", "메리츠금융지주",
               "한국투자금융지주", "농협금융지주"]   # 농협금융지주는 비상장(금융1-3)

# DART 등록 코드가 실제 인가 업권과 다른 곳만 고침 (확인된 것만)
#   다올투자증권: 661(금융지원 서비스)로 등록돼 있으나 투자매매·중개업 인가를 받은 증권사
#   삼성카드 등 64913 계정은 DART가 맞음 — 64913이 "신용카드 및 할부금융업"
FIX_SECTOR = {"다올투자증권": "증권"}

# ───────────────────────── 제외 기준표 ─────────────────────────

# 명목회사 — 자산 운용을 AMC에 위탁함 (계획서 7-2 펀드·SPC)
# "리츠"는 메리츠에 걸리므로 앞에 한글이 붙지 않은 경우만 잡음
SHELL = re.compile(r"위탁관리부동산투자회사|부동산투자회사|투융자회사|부동산공모투자회사|"
                   r"(?<![가-힣])리츠")

# 펀드·SPC·투자조합·신탁 상품 — 회사가 아니라 돈을 담는 통 (계획서 7-2)
FUND = re.compile(r"펀드|투자조합|신기술조합|조합$|사모투자|PEF\b|집합투자기구|"
                  r"투자신탁|금전신탁|처분신탁|담보신탁|자사주신탁|"
                  r"유동화전문|특수목적|유한회사|합자회사|"
                  r"제[0-9일이삼사오육칠팔구십]+호|[0-9]+호|제[일이삼사오육칠팔구십]+차", re.I)

# 해외 법인 — 법인 형태 표기·지역명, 또는 한글이 하나도 없는 이름 (계획서 7-2)
FOREIGN_FORM = re.compile(
    r"Co\.|Ltd|Inc\b|LLC|L\.P|GmbH|S\.A|B\.V|Pte|Corp|PLC|AG$|GK$|"
    r"\bPT\b|PT\.|Sdn|Bhd|Kaisha|Limited|Holdings|"
    r"아메리카|유럽|홍콩|싱가포르|베트남|인도네시아|캄보디아|미얀마|"
    r"중국|일본|뉴욕|런던|미국|태국|필리핀|호주|카자흐|북경|상해|심천|유한공사", re.I)

# 우선주 등 — 의결권이 없거나 제한돼 지배력 판단에 쓰지 않음. 원래 이름(raw)에서 찾음
PREF = re.compile(r"우선주|우선$|전환우선|상환우선|신주인수권|RCPS|CPS", re.I)

# 금융업 코드를 달 수 있으나 인수·여신·투자 포트폴리오가 없는 법인
# (보험 모집·대리 = 법인보험대리점(GA), 손해사정, 고객센터·IT 자회사)
# 신용정보사(신용조사·채권추심)도 포트폴리오가 없어 뺌 (2026-10-01) — DART 코드 75993(사업지원서비스)으로
#   우리·BNK·IBK·SGI신용정보는 이미 빠졌고, 고유번호를 못 찾아 이름으로 판정되던 iM신용정보도 같게 처리
# GA 확인분(2026-09-30): 삼성생명금융서비스·한화생명금융서비스·한화라이프랩·
#   케이피보험서비스·마이금융파트너(현대해상). 한화피플라이프·IFC그룹은 한화생명금융서비스의
#   손자회사라 1단계 추출에서는 안 잡히나, "라이프"가 생명보험으로 오판되지 않게 미리 넣음
SERVICE_ONLY = re.compile(r"손해사정|보험대리|보험중개|손사|보험서비스|"
                          r"금융서비스|생명금융|라이프랩|금융파트너|피플라이프|"
                          r"Agency|에이전시|"
                          r"고객서비스|고객센터|서비스센터|아웃소싱|"
                          r"데이타시스템|데이터시스템|시스템즈|디에스|DS$|"
                          r"신용정보", re.I)
NO_PORTFOLIO_SECTORS = {"보험 모집·대리", "보험 관련 서비스"}

# 대부업체 — 금융업이나 계열사 자금 운용 목적이라 제조업 여신 포트폴리오가 없음
LENDER_ONLY = re.compile(r"대부$|대부㈜|대부\(주\)|신용투자대부|인베스트앤대부")

# 종속회사 안에서 빼는 업권 — 사업 자회사를 묶는 중간지주·기금
HOLDING_SECTORS = {"지주회사", "기금 운영업"}

# ───────────────────────── 지분 문턱 ─────────────────────────

OWN_CONTROL = 50.0                        # 보통주 지분율 50% 초과 → 종속
OWN_REVIEW = 30.0                         # 30% 초과 ~ 50% 이하 → 실질 지배 검토 구간
REVIEW_ASSET_MIN = 1_000_000_000_000      # 검토 구간은 자산 1조 이상만 기록
# 현대카드처럼 지분 36.96%여도 이사회 관여 등으로 모회사(현대자동차) 연결 종속기업인 곳이 있음
# 검토 구간 계정은 data/manual/fin_control_decisions.csv에 "포함"으로 적으면 명단에 들어감

# ───────────────────────── ③ 적용 방식 ─────────────────────────

# ③ 기준에서 업권별로 볼 대상 (PCAF 표준 Part A 금융배출량·B 촉진배출량·C 보험배출량)
# 채점 방식은 C안(여신 규모 × 업권 노출도) — 노출도 기준은 금융-2에서 조사로 정함
_LOAN = "제조업 여신 (금융배출량)"
S3_BASIS = {
    "은행": _LOAN, "은행·기타 예금기관": _LOAN, "저축은행·신협": _LOAN,
    "카드·할부금융": _LOAN, "금융리스": _LOAN, "기타 여신금융": _LOAN,
    "여신금융": _LOAN, "개발금융기관": _LOAN,
    "금융지주": "연결 기준 제조업 여신·인수·보험 (세 가지 합산)",
    "증권": "제조업 인수·주선 (촉진배출량)", "선물": "제조업 인수·주선 (촉진배출량)",
    "생명보험": "제조업 보험 인수 (보험배출량)", "손해보험": "제조업 보험 인수 (보험배출량)",
    "보증보험": "제조업 보증 인수 (보험배출량)", "재보험": "제조업 보험 인수 (보험배출량)",
    "보험(확인 필요)": "제조업 보험 인수 (보험배출량) — 업권 확인 필요",
    "신탁·집합투자": "제조업 투자·수탁 (금융배출량)",
    "연금·공제": "제조업 투자 (금융배출량)",
    "그외 기타 금융": "확인 필요 — 실제 영위 업무로 판단",
    "금융지원 서비스": "확인 필요 — 연결 자회사 기준 (카카오페이는 증권·손보 자회사 보유)",
}

# ───────────────────────── 공통 함수 ─────────────────────────


def key(name):
    """이름 비교용 — 법인 표기와 공백을 뗌"""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


# 한글 음역 → 영문 표기 (이름 대조용). 이름 앞머리만 바꾸며 긴 것부터 맞춤
# 출처별로 흩어져 있던 표(fin1_unlisted·fin1_indep)를 하나로 합침 (2026-10-01)
TRANSLIT = sorted([
    ("엔에이치엔", "NHN"), ("에스비아이", "SBI"), ("비엔케이", "BNK"), ("에이치디", "HD"),
    ("에스케이", "SK"), ("엔에이치", "NH"), ("케이비", "KB"), ("제이비", "JB"),
    ("아이엠", "IM"), ("엘에스", "LS"), ("케이티", "KT"), ("지에스", "GS"),
    ("씨제이", "CJ"), ("엘지", "LG"), ("오케이", "OK"), ("디비", "DB"),
    ("비씨", "BC"), ("와이지", "YG"),
    ("아이비케이", "IBK"), ("케이디비", "KDB"), ("에스씨", "SC"), ("비엔피", "BNP"),
    ("에이아이에이", "AIA"), ("엠지", "MG"), ("제이티", "JT"),
], key=lambda x: -len(x[0]))


def name2(name):
    """이름 대조 키 — 법인 표기·공백 제거 → 한글 음역을 영문으로 → 보험 접미어 통일 → 대문자"""
    s = key(name)
    for ko, en in TRANSLIT:
        if s.startswith(ko):
            s = en + s[len(ko):]
            break
    s = s.replace("생명보험", "생명").replace("화재해상보험", "화재").replace("손해보험", "손보")
    return s.upper()


_HOLD = {key(x) for x in FIN_HOLDING}
_FIX = {key(k): v for k, v in FIX_SECTOR.items()}


def to_f(x):
    """숫자로 바꿈 — 쉼표·%·공백을 떼고, 숫자가 아니면 0 ("-" 등)"""
    try:
        return float(re.sub(r"[,%\s]", "", str(x)) or 0)
    except ValueError:
        return 0.0


def to_won(x):
    x = str(x).replace(",", "").strip()
    if x in ("", "-"):
        return 0
    neg = x.startswith("(") and x.endswith(")")
    try:
        v = int(float(x.strip("()")))
    except ValueError:
        return 0
    return -v if neg else v


def sector_by_code(code):
    code = str(code or "")
    for prefix, name in SECTOR_BY_CODE:
        if code.startswith(prefix):
            return name
    return ""


# 이름에 금융 키워드가 있어도 비금융인 경우 — 코드가 없어 이름으로 판정할 때만 씀
# (HD현대오일뱅크가 "뱅크"에 걸려 은행으로 들어온 사례에서 추가, 2026-09-30)
NAME_NOT_FIN = re.compile(r"오일뱅크|정유|석유|케미칼|화학|제약|바이오|코스메틱|"
                          r"푸드|식품|건설|해운|물류")


def sector_by_name(name):
    """이름 키워드로 업권을 봄. 키워드가 $로 끝나면 이름 끝에 올 때만 맞춤
    비금융 단어(NAME_NOT_FIN)가 있으면 판정하지 않음"""
    s = str(name).strip()
    if NAME_NOT_FIN.search(s):
        return ""
    for kw, sec in NAME_SECTOR:
        if kw.endswith("$"):
            if s.endswith(kw[:-1]):
                return sec
        elif kw in s:
            return sec
    return ""


def final_sector(name, code):
    """업권 최종값 — 금융지주 목록 → 확인된 손보정 → 표준산업분류 순"""
    k = key(name)
    if k in _HOLD:
        return "금융지주"
    if k in _FIX:
        return _FIX[k]
    return sector_by_code(code) or "확인 필요"


def service_reason(name, sector):
    """포트폴리오가 없는 법인이면 사유를, 아니면 빈 문자열을 돌려줌"""
    if sector in NO_PORTFOLIO_SECTORS:
        return f"{sector} — 인수·여신 포트폴리오 없음"
    if SERVICE_ONLY.search(str(name)):
        return "손해사정·모집·고객센터·IT·신용정보 등 서비스 법인 — 포트폴리오 없음"
    if LENDER_ONLY.search(str(name)):
        return "대부업 — 계열사 자금 운용 목적, 제조업 여신 포트폴리오 없음"
    return ""


def s3_basis(sector):
    return S3_BASIS.get(sector, "확인 필요 — 업권별 적용 대상 미정")


def clean_name(name):
    """출자현황 표의 이름을 정리함 — 주석 표시(주5))·출자 종류 표기·닫히지 않은 괄호를 뗌"""
    s = str(name).replace("\\n", " ").replace("\n", " ")
    s = re.sub(r"주\s*\d+\)", "", s)
    s = re.sub(r"[(（][^)）]*(보통주|우선주|전환우선주|유상증자|신주인수권)[^)）]*[)）]", "", s)
    s = re.sub(r"_?(전환|상환)?우선주\d*$|_?보통주$", "", s.strip())
    # 주석·설명 표기 — (*4) / (비상장) / (코스닥 상장) / (구. 옛이름) / [사업자번호]
    s = re.sub(r"\(\s*\*\s*\d+\s*\)", "", s)
    s = re.sub(r"\(\s*(비상장|상장|코스닥\s*상장|코스피\s*상장|유가증권\s*상장|계열회사)\s*\)", "", s)
    s = re.sub(r"\(\s*구\s*\.?[^)]*\)", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"[(（][^)）]*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def is_foreign(nm):
    if FOREIGN_FORM.search(nm):
        return True
    return not re.search(r"[가-힣]", nm)


def load_control_decisions():
    """실질 지배 판단 파일 → {key: (결정, 사유)}. 파일이 없으면 빈 사전"""
    if not CONTROL_DECISIONS.exists():
        return {}
    d = pd.read_csv(CONTROL_DECISIONS, dtype=str).fillna("")
    return {key(r["account"]): (r["decision"].strip(), r.get("reason", ""))
            for r in d.to_dict("records") if r.get("account")}


def load_manual_subs():
    """원문 수동 입력 종속회사 → {지배회사 key: [출자현황 API와 같은 모양의 행]}. 파일이 없으면 빈 사전"""
    if not MANUAL_SUBS.exists():
        return {}
    d = pd.read_csv(MANUAL_SUBS, dtype=str).fillna("")
    out = {}
    for r in d.to_dict("records"):
        if not r.get("parent") or not r.get("account"):
            continue
        out.setdefault(key(r["parent"]), []).append({
            "inv_prm": r["account"], "trmend_blce_qota_rt": r.get("own_rate", ""),
            "recent_bsns_year_fnnr_sttus_tot_assets": r.get("assets_won", ""),
            "invstmnt_purps": "경영참여",
            "_period": f"원문 수동 입력({r.get('source', '')})"})
    return out


def _label(get_json, df, by_name, by_norm=None):
    """고유번호가 잡히면 표준산업분류, 안 잡히면 이름 키워드로 업권을 붙임
    고유번호는 법인 표기를 뗀 이름으로 찾고, 없으면 음역 대조(name2)로 찾음 — 후보가 하나일 때만 씀"""
    codes, sectors, how, found = [], [], [], []
    by_norm = by_norm or {}
    for r in df.to_dict("records"):
        code = ""
        cc_ = by_name.get(r["k"], "")
        if not cc_:
            hits = by_norm.get(name2(r["account"]), [])
            cc_ = hits[0] if len(hits) == 1 else ""
        found.append(cc_)
        if cc_:
            try:
                c = get_json("company", corp_code=cc_)
                if c.get("status") == "000":
                    code = str(c.get("induty_code") or "")
            except Exception:  # noqa: BLE001
                pass
        if code.startswith(FIN_PREFIX):
            sec, h = final_sector(r["account"], code), "코드"
        elif code:
            sec, h = "금융업 아님", "코드"
        else:
            nm_sec = sector_by_name(r["account"])
            sec, h = (nm_sec, "이름") if nm_sec else ("금융 키워드 없음", "없음")
        codes.append(code)
        sectors.append(sec)
        how.append(h)
    df = df.copy()
    df["corp_code"] = found
    df["induty_code"] = codes
    df["sector"] = sectors
    df["sector_by"] = how
    return df


def _drop_reason(r):
    """종속회사 행을 명단에서 뺄 사유 — 없으면 빈 문자열"""
    if r["sector"] == "금융업 아님":
        return f"표준산업분류 {r['induty_code']} — 금융업 아님"
    if r["sector"] == "금융 키워드 없음":
        return "코드 없음·금융 키워드 없음 — 비금융 추정 (검토 파일 확인)"
    if r["sector"] in HOLDING_SECTORS:
        return f"{r['sector']}({r['induty_code']}) — 사업 자회사를 묶는 중간지주·기금"
    if to_f(r["own_rate"]) > 100:
        return f"지분율 {r['own_rate']}% — DART 신고 오류로 보임, 확인 필요"
    return service_reason(r["account"], r["sector"])


def extract_subsidiaries(get_json, cc, parents, have_keys, listed_label,
                         year=YEAR, reprt=REPRT, progress=0):
    """지배회사 목록의 종속 금융회사를 뽑음 (금융1-2·1-2b 공통)

    parents: [{account, corp_code, induty_code}] / have_keys: 이미 명단에 있는 계정 key
    반환: (명단 DataFrame, 실질 지배 검토 DataFrame, 제외 DataFrame, 이름 판정 검토 DataFrame)
    """
    cc = cc.copy()
    cc["k"] = cc["corp_name"].map(key)
    by_name = dict(zip(cc["k"], cc["corp_code"]))
    by_norm = {}
    for code, nm in zip(cc["corp_code"], cc["corp_name"]):
        by_norm.setdefault(name2(nm), []).append(code)
    decisions = load_control_decisions()
    manual_subs = load_manual_subs()
    main, rev, excl = [], [], []
    periods = [(year, reprt, f"{year} 사업보고서")] + \
              [(year, rc, f"{year} {nm}") for rc, nm in FALLBACK_REPORTS] + \
              ([(str(int(year) - 1), "11011", f"{int(year) - 1} 사업보고서")] if PREV_YEAR_ANNUAL else [])

    def drop(r, reason):
        excl.append({**{c: r.get(c, "") for c in
                        ("account", "parent", "own_rate", "sector", "induty_code", "raw_name")},
                     "reason": reason})

    for i, p in enumerate(parents, 1):
        if progress and i % progress == 0:
            print(f"  {i}/{len(parents)} … (종속 {len(main)} · 검토 {len(rev)})")
        d, used, tried = {}, "", []
        for y, rc, label in periods:
            try:
                got = get_json("otrCprInvstmntSttus", corp_code=p["corp_code"],
                               bsns_year=y, reprt_code=rc)
            except Exception as e:  # noqa: BLE001
                tried.append(f"{label} 오류 {str(e)[:40]}")
                continue
            lst = got.get("list") or []
            # 줄이 있어도 숫자 지분율이 하나도 없으면 쓸 수 없는 자료로 봄 (기업은행 "아래표 참조" 사례)
            if got.get("status") == "000" and any(to_f(x.get("trmend_blce_qota_rt")) > 0 for x in lst):
                d, used = got, label
                break
            why = "표 형식 아님(숫자 지분율 없음)" if (got.get("status") == "000" and lst) else got.get("status", "")
            tried.append(f"{label} {why}")
        manual = manual_subs.get(key(p["account"]), [])
        if not used and not manual:
            drop(dict(account="", parent=p["account"]),
                 f"출자현황 자료 없음 — 원문 확인, 필요하면 수동 입력 파일에 적음 ({'; '.join(tried)})")
            continue
        for r in list(d.get("list") or []) + manual:
            raw = str(r.get("inv_prm") or "").strip()
            nm = clean_name(raw)
            if not nm or nm in ("-", "합계", "소계"):
                continue
            rate = to_f(r.get("trmend_blce_qota_rt"))
            if rate <= OWN_REVIEW:
                continue
            base = dict(account=nm, parent=p["account"], parent_induty=p.get("induty_code", ""),
                        own_rate=rate, raw_name=raw,
                        assets_won=to_won(r.get("recent_bsns_year_fnnr_sttus_tot_assets")),
                        purpose=str(r.get("invstmnt_purps") or "").strip(),
                        period=r.get("_period") or used)
            if PREF.search(raw):
                drop(base, "우선주 등 — 지배력 판단에 쓰지 않음")
                continue
            if FUND.search(nm) or SHELL.search(nm):
                drop(base, "펀드·SPC·투자조합·신탁 상품·명목회사 — 계획서 7-2")
                continue
            if is_foreign(nm):
                drop(base, "해외 법인 — 계획서 7-2")
                continue
            if key(nm) in have_keys:
                drop(base, "이미 명단에 있음 — 상장 또는 앞 단계 종속")
                continue
            if rate > OWN_CONTROL:
                main.append(base)
            elif base["assets_won"] >= REVIEW_ASSET_MIN:
                rev.append(base)

    base_cols = ["account", "parent", "parent_induty", "own_rate", "raw_name", "assets_won",
                 "purpose", "period"]
    df = pd.DataFrame(main, columns=base_cols)
    df["k"] = df["account"].map(key)
    df = df.sort_values("own_rate", ascending=False)
    for r in df[df.duplicated(subset=["k"], keep="first")].to_dict("records"):
        drop(r, "다른 지배회사 밑에 더 큰 지분으로 잡힘 — 중복 제거")
    df = df.drop_duplicates(subset=["k"], keep="first")
    df["control"] = "종속(지분 50% 초과)"
    df["note"] = ""

    # 실질 지배 검토 구간 — 50% 초과로 이미 잡힌 곳은 뺌, 판단 파일에 따라 편입·제외
    rv = pd.DataFrame(rev, columns=base_cols)
    rv["k"] = rv["account"].map(key)
    rv = rv[~rv["k"].isin(set(df["k"]))]
    rv = rv.sort_values("own_rate", ascending=False).drop_duplicates(subset=["k"], keep="first")
    take, left = [], []
    for r in rv.to_dict("records"):
        dec, why = decisions.get(r["k"], ("", ""))
        if dec == "포함":
            take.append({**r, "control": "실질 지배(지분 30~50%, 수동 확인)",
                         "note": f"실질 지배 판단 — {why}"})
        elif dec == "제외":
            drop(r, f"지분 30~50% 검토 결과 제외 — {why}")
        else:
            left.append(r)
    if take:
        df = pd.concat([df, pd.DataFrame(take)], ignore_index=True)

    df = _label(get_json, df, by_name, by_norm)
    keep = []
    for r in df.to_dict("records"):
        reason = _drop_reason(r)
        if reason:
            drop(r, reason)
        else:
            keep.append(r)
    fin = pd.DataFrame(keep, columns=list(df.columns))
    fin["listed"] = listed_label
    fin["assets_jo"] = (fin["assets_won"] / 1e12).round(2)
    fin["disclosure_basis"] = "지배회사 연결 공시"
    fin["s3_basis"] = fin["sector"].map(s3_basis)
    fin.loc[fin["sector_by"] == "이름", "note"] = (
        fin.loc[fin["sector_by"] == "이름", "note"].astype(str)
        + " 고유번호가 안 잡혀 이름으로 업권을 정함 — 확인 필요").str.strip()
    # 출자현황을 당해 사업보고서가 아닌 대체 보고서에서 받은 경우 표시
    alt = fin["period"].astype(str) != f"{year} 사업보고서"
    fin.loc[alt, "note"] = (fin.loc[alt, "note"].astype(str) + " 출자현황 기준: "
                            + fin.loc[alt, "period"].astype(str)).str.strip()
    # 원래 이름에 "코스닥"이 있으면 표시 — 코스닥 상장사는 자체 법정공시 대상이 아님(코스피 한정)
    kosdaq = fin["raw_name"].astype(str).str.contains("코스닥")
    fin.loc[kosdaq, "note"] = (fin.loc[kosdaq, "note"].astype(str)
                               + " 코스닥 상장사 — 자체 법정공시 대상 아님(코스피 한정)").str.strip()

    # 실질 지배 검토 파일 — 금융업인 곳만 남김
    ctrl = _label(get_json, pd.DataFrame(left, columns=rv.columns), by_name, by_norm) if left else \
        pd.DataFrame(columns=list(rv.columns) + ["corp_code", "induty_code", "sector", "sector_by"])
    ctrl = ctrl[~ctrl["sector"].isin(["금융업 아님", "금융 키워드 없음"])
                & ~ctrl["sector"].isin(HOLDING_SECTORS)]
    ctrl = ctrl[[service_reason(a, s) == "" for a, s in zip(ctrl["account"], ctrl["sector"])]] \
        if len(ctrl) else ctrl
    ctrl = ctrl.copy()
    ctrl["assets_jo"] = (ctrl["assets_won"].astype(float) / 1e12).round(2)
    ctrl["decision"] = ""

    ex = pd.DataFrame(excl, columns=["account", "parent", "own_rate", "sector",
                                     "induty_code", "raw_name", "reason"])
    need = pd.concat([
        fin[(fin["sector_by"] == "이름") | fin["sector"].str.contains("확인")][
            ["account", "parent", "sector", "sector_by", "own_rate", "assets_jo"]],
        ex[ex["reason"].str.startswith("코드 없음")][
            ["account", "parent", "sector", "own_rate"]].assign(sector_by="없음"),
    ], ignore_index=True)
    return fin, ctrl, ex, need


OUT_COLS = ["account", "sector", "listed", "control", "parent", "parent_induty", "own_rate",
            "assets_jo", "disclosure_basis", "s3_basis", "sector_by", "induty_code",
            "corp_code", "purpose", "period", "raw_name", "note"]
CTRL_COLS = ["account", "parent", "own_rate", "assets_jo", "sector", "sector_by",
             "induty_code", "decision"]


def report(tag, fin, ctrl, ex, need, out, ctrl_out, excl_out, review_out):
    """두 종속회사 단계가 같은 모양으로 저장·출력하게 함"""
    fin.sort_values("assets_jo", ascending=False)[OUT_COLS].to_csv(
        out, index=False, encoding="utf-8-sig")
    ctrl.sort_values("assets_jo", ascending=False)[CTRL_COLS].to_csv(
        ctrl_out, index=False, encoding="utf-8-sig")
    ex.to_csv(excl_out, index=False, encoding="utf-8-sig")
    need.to_csv(review_out, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 300)
    print(f"\n{tag} {len(fin)}곳 → {out.relative_to(ROOT)}")
    print("  지배 근거: " + " · ".join(f"{k} {v}" for k, v in fin["control"].value_counts().items()))
    print(f"  판정 근거: 코드 {(fin['sector_by'] == '코드').sum()} · 이름 {(fin['sector_by'] == '이름').sum()}")
    print(f"실질 지배 검토(지분 30~50%·자산 1조 이상) {len(ctrl)}곳 → {ctrl_out.relative_to(ROOT)}")
    print(f"이름 판정 검토 {len(need)}곳 → {review_out.relative_to(ROOT)}")
    print(f"뺀 행 {len(ex)}건 → {excl_out.relative_to(ROOT)}")
    print(ex["reason"].str.split(" — ").str[0].value_counts().head(12).to_string())
    nodata = ex[ex["reason"].str.startswith("출자현황")]
    if len(nodata):
        print(f"\n[출자현황을 못 받은 지배회사 {len(nodata)}곳 — 금융사면 원문 확인]")
        print(nodata[["parent", "reason"]].head(40).to_string(index=False))
    alt = fin[fin["period"].astype(str).str.len().gt(0) & ~fin["period"].astype(str).str.endswith("사업보고서")]
    if len(alt):
        print(f"\n[당해 사업보고서가 아닌 자료(대체 보고서·원문 수동 입력)로 받은 종속회사 {len(alt)}곳]")
        print(alt[["account", "parent", "period"]].to_string(index=False))
    print("\n[업권별]")
    print(fin["sector"].value_counts().to_string())
    print("\n[자산 상위 25]")
    print(fin.sort_values("assets_jo", ascending=False).head(25)[
        ["account", "sector", "parent", "own_rate", "control", "assets_jo"]].to_string(index=False))
    if len(ctrl):
        print("\n[실질 지배 검토 — fin_control_decisions.csv에 결정을 적으면 다음 실행에 반영]")
        print(ctrl.sort_values("assets_jo", ascending=False)[
            ["account", "parent", "own_rate", "sector", "assets_jo"]].to_string(index=False))


# ───────────────────────── 금융1-1 실행부 ─────────────────────────

def main():
    from dart_api import corp_codes, get_json  # noqa: E402

    cc = corp_codes()
    listed = cc[cc["stock_code"].astype(str).str.strip() != ""].copy()
    print(f"상장사(고유번호 기준) {len(listed)}곳 — 회사개황 조회 (캐시가 있으면 즉시 읽음)")

    rows, fails = [], []
    for i, r in enumerate(listed.to_dict("records"), 1):
        if i % 500 == 0:
            print(f"  {i}/{len(listed)} …")
        try:
            d = get_json("company", corp_code=r["corp_code"])
        except Exception as e:  # noqa: BLE001
            fails.append((r["corp_name"], str(e)[:80]))
            continue
        if d.get("status") != "000":
            continue
        code = str(d.get("induty_code") or "")
        if not code.startswith(FIN_PREFIX):
            continue
        name = d.get("corp_name", r["corp_name"])
        rows.append(dict(
            account=name,
            corp_code=r["corp_code"],
            stock_code=r["stock_code"],
            corp_cls=d.get("corp_cls", ""),      # Y 유가증권 / K 코스닥 / N 코넥스 / E 기타
            induty_code=code,
            code_sector=sector_by_code(code) or "확인 필요",
            sector=final_sector(name, code),
            jurir_no=d.get("jurir_no", ""),
            est_dt=d.get("est_dt", ""),
            acc_mt=d.get("acc_mt", ""),
        ))

    df = pd.DataFrame(rows)
    market = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "기타"}
    df["market"] = df["corp_cls"].map(market).fillna(df["corp_cls"])
    df = df.sort_values(["sector", "account"])
    PROC.mkdir(parents=True, exist_ok=True)
    MANUAL.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    need = df[df["sector"].str.contains("확인 필요")]
    need.to_csv(REVIEW, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print(f"\n금융·보험업 상장사 {len(df)}곳 → {OUT.relative_to(ROOT)}")
    print(f"확인 필요 {len(need)}곳 → {REVIEW.relative_to(ROOT)}")
    if fails:
        print(f"조회 실패 {len(fails)}곳: {fails[:5]}")
    print("\n[시장별]")
    print(df["market"].value_counts().to_string())
    kospi = df[df["market"] == "코스피"]
    print(f"\n[업권별 — 코스피 {len(kospi)}곳]")
    print(kospi["sector"].value_counts().to_string())
    changed = kospi[kospi["sector"] != kospi["code_sector"]]
    if len(changed):
        print("\n[코드 업권과 최종 업권이 다른 계정 — 금융지주 목록·손보정 적용분]")
        print(changed[["account", "induty_code", "code_sector", "sector"]].to_string(index=False))


if __name__ == "__main__":
    main()
