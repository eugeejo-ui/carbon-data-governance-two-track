"""금융1-4 제외 목록 확정 — 단계별 제외 파일을 하나로 합치고 사유를 묶음

- 입력 (모두 앞 단계 산출물)
  - fin_excluded.csv (1-1b) · fin_sub_excluded.csv (1-2) · fin_nonfin_excluded.csv (1-2b)
  - fin_unlisted_group_excluded.csv (1-3A) · fisis/fisis_big.csv의 "제외"·"자산 일치" 행 (1-3C)
  - fisis/companies.csv의 외은지점(권역 J, 영업 중) — 1-3C에서 목록만 받고 뺀 곳
- 사유는 원문 그대로 두고, 같은 성격끼리 "사유 묶음"을 붙임 (03 문서 3장 제외 규정과 같은 이름)
- "금융회사인데 뺀 곳"(설명·검토용)은 따로 저장함 — 해외 법인·펀드·제조업 자회사(금융업 아님)처럼
  애초에 금융사가 아닌 행은 빼고, 시장·규모·지점·지주·포트폴리오 없음·실질 지배 아님만 남김

출력
  - data/processed/fin_excluded_all.csv : 제외 전부 (단계·계정·지배회사/기업집단·업권·자산·사유 묶음·사유)
  - data/processed/fin_excluded_key.csv : 금융회사인데 뺀 곳
"""
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_ALL = PROC / "fin_excluded_all.csv"
OUT_KEY = PROC / "fin_excluded_key.csv"

# (묶음 이름, 사유 원문에서 찾을 말) — 앞에서부터 맞춤
GROUPS = [
    ("지주·기금 (금융지주 아님)", r"업권 미상|지주회사|지주·개인|기금 운영업|중간지주"),
    ("외국 금융회사 국내 지점", r"서울지점|외은지점"),
    ("시장 (코스피 아님)", r"상장 — 계획서 7-2 코스피 한정|코스닥|코넥스"),
    ("규모 (자산 2조 미만)", r"2조 미만"),
    ("명목회사·펀드·SPC·신탁 상품", r"명목회사|펀드|SPC|투자조합|신탁 상품"),
    ("해외 법인", r"해외 법인"),
    ("포트폴리오 없음 (GA·손해사정·IT·대부업·신용정보)", r"모집·대리|보험 관련 서비스|서비스 법인|대부업|포트폴리오 없음"),
    ("금융업 아님 (표준산업분류)", r"금융업 아님"),
    ("비금융 추정 (코드·키워드 없음)", r"코드 없음"),
    ("우선주", r"우선주"),
    ("중복 (이미 명단·다른 지배회사·옛 이름)", r"이미 명단|중복 제거|자산 일치"),
    ("실질 지배 아님 (지분 30~50%)", r"30~50% 검토 결과 제외"),
    ("자료 문제 (조회 실패·출자현황 없음·지분율 오류)", r"조회 실패|자료 없음|신고 오류"),
]
KEY_GROUPS = {"시장 (코스피 아님)", "규모 (자산 2조 미만)", "외국 금융회사 국내 지점", "지주·기금 (금융지주 아님)",
              "포트폴리오 없음 (GA·손해사정·IT·대부업·신용정보)", "실질 지배 아님 (지분 30~50%)"}
COLS = ["stage", "account", "parent_or_group", "sector", "assets_jo", "reason_group", "reason", "induty_code"]


def group_of(reason):
    for name, pat in GROUPS:
        if re.search(pat, str(reason)):
            return name
    return "기타"


def read(name):
    p = PROC / name
    return pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame()


def pick(df, stage, parent_col, assets_col=None):
    if not len(df):
        return pd.DataFrame(columns=COLS)
    g = lambda c: df[c] if c and c in df.columns else ""  # noqa: E731
    return pd.DataFrame({"stage": stage, "account": g("account"), "parent_or_group": g(parent_col),
                         "sector": g("sector"), "assets_jo": g(assets_col), "reason": g("reason"),
                         "induty_code": g("induty_code")})


def main():
    parts = [
        pick(read("fin_excluded.csv"), "1-1b 코스피 상장 금융사", None),
        pick(read("fin_sub_excluded.csv"), "1-2 금융 모회사의 종속", "parent"),
        pick(read("fin_nonfin_excluded.csv"), "1-2b 명단 밖 코스피 모회사의 종속", "parent"),
        pick(read("fin_unlisted_group_excluded.csv"), "1-3A 대기업집단 비상장", "group", "assets_jo"),
    ]
    big = read("fisis/fisis_big.csv")
    if len(big):
        b = big[big["where"].str.startswith(("제외", "이미 명단 — 자산"))]
        parts.append(pd.DataFrame({"stage": "1-3C 독립·외국계", "account": b["finance_nm"], "parent_or_group": "",
                                   "sector": b["part_nm"], "assets_jo": b["assets_jo"],
                                   "reason": b["where"], "induty_code": b.get("induty_code", "")}))
    comp = read("fisis/companies.csv")
    if len(comp):
        j = comp[(comp["part"] == "J") & (comp["closed"].str.lower() != "true")]
        parts.append(pd.DataFrame({"stage": "1-3C 독립·외국계", "account": j["finance_nm"], "parent_or_group": "",
                                   "sector": "외은지점", "assets_jo": "",
                                   "reason": "외은지점 — 한국 법인이 아닌 지점이라 결정은 본사 (목록만 받음)",
                                   "induty_code": ""}))
    a = pd.concat([p for p in parts if len(p)], ignore_index=True)
    a = a[a["reason"].astype(str).str.strip() != ""].copy()
    a["reason_group"] = a["reason"].map(group_of)
    a = a[COLS]
    PROC.mkdir(parents=True, exist_ok=True)
    a.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")
    key = a[(a["stage"].str.startswith("1-1b")) | (a["reason_group"].isin(KEY_GROUPS))]
    key.to_csv(OUT_KEY, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 100)
    print(f"제외 전부 {len(a)}행 → {OUT_ALL.relative_to(ROOT)}")
    print(f"금융회사인데 뺀 곳 {len(key)}행 → {OUT_KEY.relative_to(ROOT)}")
    print("\n[단계 × 사유 묶음]")
    t = pd.crosstab(a["reason_group"], a["stage"].str.split(" ").str[0], margins=True, margins_name="합계")
    print(t.to_string())
    other = a[a["reason_group"] == "기타"]
    if len(other):
        print(f"\n[사유 묶음 '기타' {len(other)}행 — 묶음 규칙 확인]")
        print(other["reason"].str.split(" — ").str[0].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
