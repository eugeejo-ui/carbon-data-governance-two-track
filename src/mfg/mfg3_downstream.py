"""제조-3 하류 후보 채점 — CBAM 하류 확대(집행위안 COM(2025) 989) 대상 중견·대기업 46곳

- 대상: data/external/cbam/mfg_final_reviewed.csv 중 wave_group_reviewed가 "2차(2028)"·"2차(2028, 제품명 확인)"이고
  규모가 중견·대기업인 곳 (1차 94곳과 겹침 없음). "2차 후보(확인 필요)" 220곳·"약" 88곳은 제품 확인 전이라 넣지 않음
- 하류 확대는 미확정 — 2026-09-15 유럽의회 입장 채택, 3자 협상 중(연내 합의 목표), 적용 목표 2028-01-01
  집행위안 약 180개 품목 기준이라 이사회(약 200개 추가)·의회(457개) 안보다 좁음 → 46곳은 하한
- ② 정부 검증 총량: CBAM(하류 후보) + 배출권 할당대상(cbam 파일 kets_member, 2026-01-01 명단) 또는
  목표관리업체·합병 승계(data/manual/mfg3_managed.csv) → 2점, 그 밖 1점
- ③ 공장 흩어짐: 등록공장(2024-12-31) — mfg2_factory.py와 같은 매칭·점수. 생산품 관련 판정은 하류 품목 공장 단어(넓게)와
  다른 회사 단어(화장품·도료·벽지 등)로 바꾸고, 사명 변경 계정은 옛 이름도 찾음
- ④ IT 예산: 정보보호 공시 — mfg2_it.py와 같은 값·3등분(46곳 안에서 중견/대기업 따로)
- ⑤ 2층 경쟁: data/manual/mfg3_competition.csv에 근거가 있으면 그 값, 없으면 2점(잠정 — 검색 전)
- ⑥ EU 노출: 채점하지 않음. 원문 "유럽" 언급 수(kw_유럽)만 참고 칸
- 합계 ②+③+④+⑤ (최대 8점). 동점: ② → ④ → ③ → 이름순. 모든 계정에 "하류 후보(미확정)" 표시
- 출력: data/processed/mfg_wave2_scores.csv · mfg3_factory_candidates.csv
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "mfg"))
from mfg2_factory import BRANCH, addr_key, hangul_reading, key, score, sido  # noqa: E402
from mfg2_it import kisa_names, load, tertile  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
EXT = ROOT / "data" / "external" / "cbam" / "mfg_final_reviewed.csv"
FACTORY = ROOT / "data" / "raw" / "한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv"
OUT = PROC / "mfg_wave2_scores.csv"
WAVE2 = ("2차(2028)", "2차(2028, 제품명 확인)")
BIG = {"대기업"}
# 하류 품목 공장으로 볼 생산품 단어 (넓게) · 다른 회사로 볼 생산품 단어 — 동명 회사 가려내기용
REL = (r"기계|기기|부품|모터|모타|전동기|변압기|발전기|전원|전기|전력|전선|케이블|와이어|기어|샤프트|베어링|클러치|"
       r"스풀|밸브|피니언|브라켓|동력|변속|자동차|차량|철도|중장비|굴삭|굴착|로더|지게차|크레인|콘베|컨베이어|호퍼|집진|"
       r"사이로|저장|용기|로봇|자동화|농기계|농업|트랙터|이앙|콤바인|냉장|세탁|제습|공기청정|에어컨|건조기|정수|온풍|"
       r"증발기|주조|주물|주강|단조|금속|메탈|도금|드릴|함마|비트|소방차|특장차|펌프|철판|가공|아이들러|로울러|롤러|"
       r"차단기|개폐기|통신장비|리액터|인버터|컨버터|연료전지|엔진|배터리|유압|실린더|브레이크|조향|제동|부스터|ABS|"
       r"승강기|엘리베이터|에스컬레이터|shaft|clutch|valve|spool|bracket|motor|cable")
NOT = r"화장품|도료|벽지|목재|케비넷|캐비닛|의약|식품|카라반|섬유|인쇄회로기판|가구|사료"
# 사명 변경·다른 표기 — 등록공장(2024-12-31)에는 옛 이름으로 있음
ALIASES = {"에이치디건설기계": ["에이치디현대건설기계", "에이치디현대인프라코어"], "수산세보틱스": ["수산중공업"],
           "에이치엘만도": ["만도"], "티와이엠": ["티와이엠(TYMCORPORATION)", "동양물산기업"]}


def is_relevant(product):
    return "Y" if re.search(REL, product, re.I) and not re.search(NOT, product) else "N"


def targets():
    m = pd.read_csv(EXT, dtype=str).fillna("")
    t = m[m["wave_group_reviewed"].isin(WAVE2) & m["size_class"].isin(["중견", "대기업"])].copy()
    t = t.rename(columns={"corp_name": "account", "size_class": "size", "ftc_group": "group",
                          "cbam_wave2_item": "item", "kw_유럽": "kw_europe"})
    t["listed"] = t["corp_cls"].map({"Y": "코스피", "K": "코스닥"}).fillna("")
    return t.reset_index(drop=True)


def s2(t):
    mg = pd.read_csv(MANUAL / "mfg3_managed.csv", dtype=str).fillna("")
    mg = mg[mg["managed"] == "Y"]
    kind = dict(zip(mg["account"].map(key), mg["kind"]))
    kets = t["kets_member"] == "True"
    man = t["account"].map(lambda a: kind.get(key(a), ""))
    t["s2"] = [2 if a or b else 1 for a, b in zip(kets, man)]
    t["s2_basis"] = ["CBAM 후보 + 배출권 할당대상" if a else f"CBAM 후보 + {b}" if b else "CBAM 후보만"
                     for a, b in zip(kets, man)]
    return t


def s3(t):
    f = pd.read_csv(FACTORY, encoding="cp949", dtype=str).fillna("")
    f["k"] = f["회사명"].map(key)
    f["k_read"] = f["k"].map(hangul_reading)
    f["addr_k"] = f["공장주소"].map(addr_key)
    f["sido"] = [sido(a, z) for a, z in zip(f["공장주소"], f["단지명"])]
    cands, rows = [], []
    for r in t.itertuples():
        k = key(r.account)
        names = {k, hangul_reading(k)} | set(ALIASES.get(k, []))
        exact = f[f["k"].isin(names) | f["k_read"].isin(names)].assign(match="정확")
        branch = f[f["k_read"].map(lambda x: any(x.startswith(n) and x != n and BRANCH.match(x[len(n):])
                                                 for n in names))].assign(match="지점")
        g = pd.concat([exact, branch])
        if g.empty and len(k) >= 3:
            g = f[f["k"].str.contains(k, regex=False)].assign(match="포함")
        g = g.drop_duplicates("addr_k").copy()
        g["relevant"] = g["생산품"].map(is_relevant)
        for x in g.itertuples():
            cands.append(dict(account=r.account, match=x.match, factory_name=x.회사명, zone=x.단지명,
                              product=x.생산품, address=x.공장주소, sido=x.sido, relevant=x.relevant))
        ex = g[g["match"] == "정확"]
        flags = []
        if g.empty:
            flags.append("매칭 0곳")
        elif (g["match"] == "포함").all():
            flags.append("포함 매칭만 — 확인 필요")
        same = (ex["relevant"] == "N").any() or len(ex) >= 6 or ex["sido"].nunique() >= 4
        kept = g[g["relevant"] == "Y"] if same else g
        if same:
            s_all = score(len(g), g.loc[g["sido"] != "?", "sido"].nunique())
            s_rel = score(len(kept), kept.loc[kept["sido"] != "?", "sido"].nunique())
            flags.append("동명 의심: 관련 공장만 셈" + (f" — 점수 갈림({s_all}↔{s_rel}), 확인 필요" if s_all != s_rel else ""))
        n, s = len(kept), kept.loc[kept["sido"] != "?", "sido"].nunique()
        rows.append(dict(factories=n, sido_n=s, s3=score(n, s), s3_flags=" / ".join(flags)))
    pd.DataFrame(cands).to_csv(PROC / "mfg3_factory_candidates.csv", index=False, encoding="utf-8-sig")
    return pd.concat([t, pd.DataFrame(rows)], axis=1)


def s4(t):
    years, kisa = [load(2026), load(2025)], kisa_names()
    vals, yrs = [], []
    for r in t.itertuples():
        names = {key(r.account)} | set(kisa.get(r.corp_code, []))
        names |= {hangul_reading(n) for n in names}
        hit = None
        for d in years:
            h = d[d["k"].isin(names) | d["k_read"].isin(names)]
            if len(h):
                hit = h.iloc[0]
                break
        vals.append(round(hit["it_won"] / 1e8, 1) if hit is not None else None)
        yrs.append(hit["year"] if hit is not None else "")
    t["it_eok"], t["it_year"] = vals, yrs
    t["size_group"] = t["size"].map(lambda s: "대기업" if s in BIG else "중견")
    t["s4"] = 0
    for g in ("중견", "대기업"):
        has = (t["size_group"] == g) & t["it_eok"].notna()
        if has.any():
            t.loc[has, "s4"] = tertile(t.loc[has, "it_eok"])
    t["s4_note"] = t["it_eok"].isna().map({True: "④ 자료 없음", False: ""})
    return t


def s5(t):
    p = MANUAL / "mfg3_competition.csv"
    ev = pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame(columns=["account", "s5", "basis"])
    m = {key(a): (int(s), b) for a, s, b in zip(ev["account"], ev["s5"], ev["basis"]) if str(s).isdigit()}
    t["s5"] = [m.get(key(a), (2, ""))[0] for a in t["account"]]
    t["s5_basis"] = [m.get(key(a), (2, "검색 전(잠정 2점)"))[1] for a in t["account"]]
    return t


def main():
    t = s5(s4(s3(s2(targets()))))
    t["total"] = t[["s2", "s3", "s4", "s5"]].sum(axis=1)
    t["flag"] = "하류 후보(미확정)"
    t = t.sort_values(["total", "s2", "s4", "s3", "account"], ascending=[False] * 4 + [True]).reset_index(drop=True)
    t["rank"] = t.index + 1
    cols = ["rank", "account", "size", "listed", "group", "item", "total", "s2", "s3", "s4", "s5",
            "s2_basis", "factories", "sido_n", "s3_flags", "it_year", "it_eok", "s4_note", "s5_basis",
            "kw_europe", "flag", "corp_code", "jurir_no"]
    t[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 34)
    print(f"→ {OUT.relative_to(ROOT)} ({len(t)}곳: " + " · ".join(f"{k} {v}" for k, v in t['size'].value_counts().items()) + ")")
    print("\n[1] 기준별 분포")
    print(pd.DataFrame({c: t[c].value_counts().reindex([2, 1, 0], fill_value=0) for c in ("s2", "s3", "s4", "s5")}).to_string())
    print("\n[2] 합계 분포 (최대 8점)")
    print(t["total"].value_counts().sort_index(ascending=False).rename("곳 수").to_string())
    print("\n[3] 순위")
    print(t[["rank", "account", "size", "item", "total", "s2", "s3", "s4", "s5", "factories", "it_eok", "kw_europe"]].to_string(index=False))
    chk = t[t["s3_flags"].str.contains("확인 필요|매칭 0곳")]
    print(f"\n[4] ③ 확인 필요 {len(chk)}곳")
    print(chk[["account", "factories", "s3", "s3_flags"]].to_string(index=False) if len(chk) else "없음")


if __name__ == "__main__":
    main()