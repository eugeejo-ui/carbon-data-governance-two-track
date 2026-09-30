"""제조2-2 ③ 데이터 흩어짐: 등록공장(2024-12-31)으로 계정별 공장 수·시도 수

- 매칭: 이름 정리 후 정확 일치 + "계정 이름 + 공장·지점·사업소 등"(예: 고려제강(주)언양공장)
  이름은 영문 약자의 한글 읽기(KG→케이지 등)와 알려진 옛 이름도 함께 씀
  그래도 없으면 공장 회사명에 계정 이름이 들어간 경우를 후보로만 잡음(포함)
- 같은 주소는 한 공장으로 셈. 시도는 주소 첫머리(없으면 시·군 이름)로 정함
- 생산품이 계정의 CBAM 부문과 무관해 보이는 공장(동명 회사 가능성)은 relevant=N으로 표시
- 동명 회사 의심: 정확 일치 공장에 무관 생산품이 섞였거나, 정확 일치만 6곳 이상 또는 4개 시도 이상
- 판단이 필요한 계정: 매칭 0곳, 포함 매칭만 있음, 동명 의심이면서 "전부 셀 때"와 "관련 공장만 셀 때" 점수가 다른 경우
  (점수가 같으면 어느 쪽이든 결과가 같아 자동 처리하고 표시만 함)
  → 사람 판단 기록(data/manual/factory_match_review.csv)이 있으면 그 결과로 셈
- 점수: 공장 3곳 이상 또는 2개 이상 시도 2점, 공장 2곳 1점, 1곳 0점, 확인 불가 0점(③ 자료 없음)

출력: data/processed/mfg2_factory_candidates.csv (계정별 후보 공장), data/processed/mfg2_factory_score.csv
"""
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
FACTORY = ROOT / "data" / "raw" / "한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv"
REVIEW = MANUAL / "factory_match_review.csv"

LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   ["에이", "비", "씨", "디", "이", "에프", "지", "에이치", "아이", "제이", "케이", "엘", "엠",
                    "엔", "오", "피", "큐", "알", "에스", "티", "유", "브이", "더블유", "엑스", "와이", "지"]))
# 알려진 옛 이름·다른 표기 (계정 이름 → 등록공장에 있을 수 있는 이름)
ALIASES = {
    "SIMPAC": ["심팩"], "포스코스틸리온": ["포스코강판"], "삼표시멘트": ["동양시멘트"],
    "한주라이트메탈": ["한주금속"], "케이비아이동양철관": ["동양철관"],
    "포스코에스피": ["포스코모빌리티솔루션"],
}
SIDO = {"서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천", "광주": "광주", "대전": "대전",
        "울산": "울산", "세종": "세종", "경기": "경기", "강원": "강원", "충청북": "충북", "충북": "충북",
        "충청남": "충남", "충남": "충남", "전라북": "전북", "전북": "전북", "전라남": "전남", "전남": "전남",
        "경상북": "경북", "경북": "경북", "경상남": "경남", "경남": "경남", "제주": "제주"}
CITY = {"포항": "경북", "경주": "경북", "구미": "경북", "영천": "경북", "광양": "전남", "여수": "전남",
        "순천": "전남", "목포": "전남", "창원": "경남", "김해": "경남", "양산": "경남", "거제": "경남",
        "당진": "충남", "서산": "충남", "천안": "충남", "아산": "충남", "군산": "전북", "익산": "전북",
        "완주": "전북", "안산": "경기", "시흥": "경기", "평택": "경기", "화성": "경기", "청주": "충북",
        "충주": "충북", "단양": "충북", "제천": "충북", "삼척": "강원", "동해": "강원", "강릉": "강원"}
# 계정 이름 뒤에 붙으면 같은 회사의 사업장으로 보는 말
BRANCH = re.compile(r"^(제?\d*(단지)?공장|[가-힣A-Za-z0-9]{0,8}(공장|지점|센터|사업소|사업장|사업부문?|출하공장|영업소))$")
METAL = (r"강|철|스틸|STEEL|금속|선재|봉|관|볼트|너트|단조|주강|주물|와이어|WIRE|BAR|CHQ|로프|캔|용기|형강|판|"
         r"코일|구조|데크|타워|TOWER|빔|환원|페로|합금|도금|파이프|피팅|이음|플랜지|병마개|블록|선체|잔골재|"
         r"알루미|알미|알류|AL|빌렛|빌레트|잉고트|괴|압연|압출|폼|샷시|새시|창호")
RELEVANT = {
    "철강": METAL,
    "알루미늄": METAL,
    "시멘트": r"시멘트|클링커|슬래그|슬라그|레미콘|몰탈|석회",
    "비료": r"비료|암모니아|질산|황산|인산|요소|복비",
}


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def hangul_reading(k):
    """영문 약자를 한글 읽기로 (KG스틸→케이지스틸, 동국S&C→동국에스엔씨). '앤'은 '엔'으로 맞춤"""
    s = re.sub(r"[A-Z]+", lambda m: "".join(LETTERS[c] for c in m.group(0)), str(k).upper().replace("&", "엔"))
    return s.replace("앤", "엔")


def addr_key(a):
    a = re.sub(r"\(.*?\)", "", str(a))
    a = re.sub(r"외\s*\d+\s*필지", "", a)
    return re.sub(r"[\s,]", "", a)


def sido(addr, zone):
    a = str(addr).strip()
    for p, v in SIDO.items():
        if a.startswith(p):
            return v
    text = f"{a} {zone}"
    for c, v in CITY.items():
        if c in text:
            return v
    return "?"


def score(n, s):
    if n == 0:
        return 0
    if n >= 3 or s >= 2:
        return 2
    return 1 if n == 2 else 0


def main():
    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    f = pd.read_csv(FACTORY, encoding="cp949", dtype=str).fillna("")
    f["k"] = f["회사명"].map(key)
    f["k_read"] = f["k"].map(hangul_reading)
    f["addr_k"] = f["공장주소"].map(addr_key)
    f["sido"] = [sido(a, z) for a, z in zip(f["공장주소"], f["단지명"])]

    cands = []
    for r in base.itertuples():
        k = key(r.account)
        names = {k, hangul_reading(k)} | set(ALIASES.get(k, []))
        names |= {hangul_reading(n) for n in names}
        exact = f[f["k"].isin(names) | f["k_read"].isin(names)].assign(match="정확")
        branch = f[f["k_read"].map(lambda x: any(x.startswith(n) and x != n and BRANCH.match(x[len(n):])
                                                 for n in names))].assign(match="지점")
        m = pd.concat([exact, branch])
        if m.empty and len(k) >= 3:
            m = f[f["k"].str.contains(k, regex=False)].assign(match="포함")
        m = m.drop_duplicates("addr_k")
        rel = RELEVANT.get(r.cbam_sector, ".")
        for x in m.itertuples():
            cands.append(dict(account=r.account, sector=r.cbam_sector, match=x.match, factory_name=x.회사명,
                              zone=x.단지명, product=x.생산품, address=x.공장주소, addr_k=x.addr_k, sido=x.sido,
                              relevant="Y" if re.search(rel, x.생산품, re.I) else "N"))
    c = pd.DataFrame(cands, columns=["account", "sector", "match", "factory_name", "zone", "product",
                                     "address", "addr_k", "sido", "relevant"])

    review = pd.read_csv(REVIEW, dtype=str).fillna("") if REVIEW.exists() else pd.DataFrame(
        columns=["account", "addr_k", "keep", "note"])
    rows = []
    for r in base.itertuples():
        g = c[c["account"] == r.account]
        ex = g[g["match"] == "정확"]
        flags, need = [], False
        if g.empty:
            flags.append("매칭 0곳")
            need = True
        elif (g["match"] == "포함").all():
            flags.append("포함 매칭만")
            need = True
        if (ex["relevant"] == "N").any() or len(ex) >= 6 or ex["sido"].nunique() >= 4:
            flags.append("동명 의심")
            rel = g[g["relevant"] == "Y"]
            s_all = score(len(g), g.loc[g["sido"] != "?", "sido"].nunique())
            s_rel = score(len(rel), rel.loc[rel["sido"] != "?", "sido"].nunique())
            if s_all != s_rel:
                need = True
                flags.append(f"점수 갈림({s_all}↔{s_rel})")
        if (g["sido"] == "?").any():
            flags.append("시도 불명")
        rv = review[review["account"] == r.account]
        if len(rv):
            kept = g[g["addr_k"].isin(rv.loc[rv["keep"] == "Y", "addr_k"])]
            status, note = "사람 판단", " / ".join(n for n in rv["note"] if n)
        elif need:
            kept, status, note = g[g["relevant"] == "Y"], "확인 필요", ""
        elif "동명 의심" in flags:
            kept, status, note = g[g["relevant"] == "Y"], "자동", "동명 의심: 관련 공장만 셈(전부 세도 점수 같음)"
        else:
            kept, status, note = g, "자동", ""
        n, s = len(kept), kept.loc[kept["sido"] != "?", "sido"].nunique()
        rows.append(dict(account=r.account, size=r.size, sector=r.cbam_sector, candidates=len(g),
                         factories=n, sido_n=s, sidos="/".join(sorted(kept["sido"].unique())),
                         s3=score(n, s), s3_note="③ 자료 없음" if n == 0 else "", status=status,
                         flags=" / ".join(flags), review_note=note))
    sc = pd.DataFrame(rows)
    c.to_csv(PROC / "mfg2_factory_candidates.csv", index=False, encoding="utf-8-sig")
    sc.to_csv(PROC / "mfg2_factory_score.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 50)
    print(f"계정 {len(sc)}곳, 후보 공장 {len(c)}곳")
    print(pd.crosstab(sc["status"], sc["s3"], margins=True, margins_name="합계"))
    need = sc[sc["status"] == "확인 필요"]
    print(f"\n[확인 필요 {len(need)}곳] (점수는 생산품이 관련 있는 공장만 센 잠정값)")
    print(need[["account", "candidates", "factories", "sido_n", "s3", "flags"]].to_string(index=False)
          if len(need) else "없음")
    auto_flag = sc[(sc["status"] == "자동") & (sc["flags"] != "")]
    print(f"\n[자동 처리했지만 표시가 있는 {len(auto_flag)}곳] (동명이 섞여도 점수가 같음)")
    print(auto_flag[["account", "candidates", "factories", "sido_n", "s3", "flags"]].to_string(index=False)
          if len(auto_flag) else "없음")
    done = sc[sc["status"] == "사람 판단"]
    print(f"\n[사람 판단 {len(done)}곳]")
    print(done[["account", "factories", "sido_n", "s3", "s3_note"]].to_string(index=False) if len(done) else "없음")


if __name__ == "__main__":
    main()