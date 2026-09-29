"""제조1-2 명단 합치기

중견 73곳, 상장 CBAM 1차 대기업·중소, 비상장 판정 32곳, 지주회사 확인에서 추가한 회사를
한 표로 합치고 01_mfg1_list.md 3-2 기준(지주회사, 소멸·생산 중단, 신원 확인, 규모 재확인)에
따라 처리 상태를 붙임. 지주회사는 같은 기업집단의 CBAM 1차 업종 회사를 후보로 뽑음

입력(사람 판단)
- data/manual/mfg1_holding_decisions.csv의 added 열 (제조1-2)
- data/manual/mfg1_size_checks.csv (제조1-3 사람 판정, 있으면 반영)
- data/processed/mfg1_size_screen.csv의 '해당 없음' (제조1-3 자동 선별, 있으면 반영)

출력
- data/processed/mfg1_merged.csv: 후보 전체와 처리 상태
  status·size는 제조1-2 기준(제조1-3 코드가 대상 선별에 씀), status_final·size_final은 제조1-3 반영 후
- data/processed/mfg1_holding_candidates.csv: 지주회사별 사업회사 후보
"""
from pathlib import Path
import re
import warnings

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

ROOT = Path(__file__).resolve().parents[2]
EXT = ROOT / "data" / "external"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

TARGET = EXT / "energy_ladder" / "target_firms.csv"
UNLISTED = EXT / "energy_ladder" / "step1_unlisted_final.csv"
CBAM = EXT / "cbam" / "mfg_final_reviewed.csv"
FTC = RAW / "소속회사 개요.xlsx"
KETS = RAW / "배출권거래제 할당대상업체 현황_260101기준.xlsx"
DECISIONS = ROOT / "data" / "manual" / "mfg1_holding_decisions.csv"
SIZE_CHECKS = ROOT / "data" / "manual" / "mfg1_size_checks.csv"
SIZE_SCREEN = OUT / "mfg1_size_screen.csv"

# cbam 판정에서 1차로 나온 업종코드 앞 4자리 (두산에너빌리티의 2911은 회사별 판정이라 뺌)
CBAM1_KSIC4 = ("2411", "2412", "2413", "2419", "2421", "2422", "2331",
               "2031", "2012", "2511", "2591", "2599")

# 3-2 소멸·생산 중단 (이전 레포 01_target_accounts.md 4장 기록)
EVENTS = {
    "한일현대시멘트": "합병 소멸: 2025-11-01 한일시멘트에 흡수합병 (존속법인 한일시멘트는 중견 명단에 있음)",
    "디비메탈": "생산 중단: DB월드와 합병 보도, 2026-06 합금철 생산 전면 중단 보도",
}

# 3-2 신원 확인 대상 (동명 회사)
IDENTITY = {
    "피엔알": "동명 회사 있음. 공정위 포스코 집단의 (주)피엔알과 배출권 명단 업체가 같은 법인인지 확인",
    "동남": "동명 회사 8곳. 배출권 명단 업체의 법인 특정 필요",
}

# 이전 레포에서 제외한 상장 중견 지주회사 (cbam 1차·중견인데 73곳에 없음)
MID_HOLDINGS = {"한일홀딩스", "KISCO홀딩스"}


def key(name):
    """법인 표기·공백을 지운 이름 (매칭용)"""
    if pd.isna(name):
        return ""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def load_ftc():
    ftc = pd.read_excel(FTC, dtype=str)
    ftc["k"] = ftc["소속회사명"].map(key)
    ftc["ksic4"] = ftc["업종코드"].str[1:5]
    return ftc


def load_kets():
    k = pd.read_excel(KETS, header=None, skiprows=3, dtype=str).iloc[:, 1:5]
    k.columns = ["no", "kets_code", "kets_name", "kets_ksic"]
    k = k.dropna(subset=["kets_code"])
    k["k"] = k["kets_name"].map(key)
    return k


def ftc_lookup(ftc, k, jurir=""):
    """법인등록번호(있으면)로, 없으면 이름으로 공정위 소속회사를 찾아
    (기업집단, 법인등록번호, 업종코드, 건수, 찾은 방법)을 돌려줌"""
    how = "법인등록번호"
    r = ftc[ftc["법인등록번호"] == jurir] if jurir else ftc.iloc[0:0]
    if r.empty:
        how = "이름"
        r = ftc[ftc["k"] == k]
    if r.empty:
        return "", "", "", 0, ""
    return ("/".join(sorted(r["기업집단명"].unique())),
            "/".join(sorted(r["법인등록번호"].unique())),
            "/".join(sorted(r["업종코드"].unique())),
            r["법인등록번호"].nunique(), how)


def build():
    t = pd.read_csv(TARGET, dtype={"corp_code": str, "ksic": str})
    u = pd.read_csv(UNLISTED, dtype={"corp_code": str, "kets_ksic": str, "kets_code": str})
    m = pd.read_csv(CBAM, dtype={"corp_code": str, "stock_code": str,
                                 "jurir_no": str, "induty_code": str})
    w1 = m[m["wave_group_reviewed"] == "1차(2027)"]

    rows = []

    # 1) 중견 73곳 (상장 58 + 비상장 15)
    kets_by_corp = u.set_index("corp_code")["kets_code"].dropna().to_dict()
    jurir_by_corp = m.set_index("corp_code")["jurir_no"].dropna().to_dict()
    for r in t.itertuples():
        listed = r.source.startswith("상장")
        rows.append(dict(
            name=r.name, source="중견 73 (이전 레포)", listed="상장" if listed else "비상장",
            size="중견", corp_code=r.corp_code, kets_code=kets_by_corp.get(r.corp_code, ""),
            ksic=r.ksic, kets_member=r.kets_member, is_holding=False,
            jurir_no=jurir_by_corp.get(r.corp_code, "") if listed else "",
            group_prev=r.ftc_group if pd.notna(r.ftc_group) else "", note_prev=r.note if pd.notna(r.note) else "",
        ))

    # 2) 상장 CBAM 1차 대기업 12곳 + 이전에 뺀 중견 지주회사 2곳
    big = w1[w1["size_class"] == "대기업"]
    midh = w1[(w1["size_class"] == "중견") & (w1["corp_name"].map(key).isin(MID_HOLDINGS))]
    for r in pd.concat([big, midh]).itertuples():
        rows.append(dict(
            name=r.corp_name, source="상장 cbam 1차", listed="상장", size=r.size_class,
            corp_code=r.corp_code, kets_code="", ksic=r.induty_code, kets_member=r.kets_member,
            is_holding=str(r.is_holding) == "True", jurir_no=r.jurir_no,
            group_prev=r.ftc_group if pd.notna(r.ftc_group) else "", note_prev="",
        ))

    # 3) 비상장 판정 32곳 중 중견(73곳에 이미 있음)을 뺀 17곳
    for r in u[u["verdict"] != "중견"].itertuples():
        rows.append(dict(
            name=r.kets_name, source="비상장 판정 32 (이전 레포)", listed="비상장",
            size=r.verdict, corp_code=r.corp_code if pd.notna(r.corp_code) else "",
            kets_code=r.kets_code, ksic=r.kets_ksic, kets_member=True, is_holding=False,
            jurir_no="", group_prev="", note_prev=r.note if pd.notna(r.note) else "",
        ))

    # 4) 상장 CBAM 1차 중소 27곳: cbam 판정이 규칙 2·4를 쓰지 않아 제조1-3에서 다시 봄
    for r in w1[w1["size_class"] == "중소"].itertuples():
        rows.append(dict(
            name=r.corp_name, source="상장 cbam 1차", listed="상장", size="중소",
            corp_code=r.corp_code, kets_code="", ksic=r.induty_code, kets_member=r.kets_member,
            is_holding=False, jurir_no=r.jurir_no,
            group_prev=r.ftc_group if pd.notna(r.ftc_group) else "", note_prev=r.size_reason,
        ))

    # 5) 지주회사 확인에서 추가하기로 한 회사 (배출권 명단에서 코드·업종을 가져옴)
    kets = load_kets()
    dec = pd.read_csv(DECISIONS, dtype=str).fillna("")
    for d in dec[dec["added"] != ""].itertuples():
        for name in d.added.split("/"):
            hit = kets[kets["k"] == key(name)]
            rows.append(dict(
                name=hit["kets_name"].iloc[0] if len(hit) else name,
                source="지주회사 확인에서 추가", listed="비상장", size="대기업 계열",
                corp_code="", kets_code=hit["kets_code"].iloc[0] if len(hit) else "",
                ksic=hit["kets_ksic"].iloc[0] if len(hit) else "", kets_member=len(hit) > 0,
                is_holding=False, jurir_no="", group_prev="",
                note_prev=f"{d.holding} 확인에서 추가 ({d.decided_on})",
            ))

    df = pd.DataFrame(rows)
    df["k"] = df["name"].map(key)
    df["jurir_no"] = df["jurir_no"].fillna("")

    # 공정위 소속회사(2026-05)와 이름 대조
    ftc = load_ftc()
    look = pd.Series([ftc_lookup(ftc, k, j) for k, j in zip(df["k"], df["jurir_no"])], index=df.index)
    df["group_2605"] = look.str[0]
    df["ftc_jurir_no"] = look.str[1]
    df["ftc_ksic"] = look.str[2]
    df["ftc_n"] = look.str[3]
    df["ftc_match"] = look.str[4]

    # 처리 상태 (3-2 기준)
    status, reason, step = [], [], []
    for r in df.itertuples():
        if r.is_holding:
            s, why, nxt = "제외", "지주회사", "사업회사 후보 확인 (mfg1_holding_candidates.csv)"
        elif r.k in EVENTS:
            s, why, nxt = "제외", EVENTS[r.k], ""
        elif r.k in IDENTITY:
            s, why, nxt = "확인 대기", IDENTITY[r.k], "제조1-3 신원 확인"
        elif r.size == "중소" and r.listed == "상장":
            s, why, nxt = "확인 대기", "상장 중소: cbam 판정에 규칙 2·4가 없었음", "제조1-3 DART 최대주주 선별"
        elif r.size == "중소":
            s, why, nxt = "확인 대기", "규모 기준(5·6)으로 중소 판정", "제조1-3 감사보고서 열람"
        else:
            s, why, nxt = "포함", "", ""
        status.append(s); reason.append(why); step.append(nxt)
    df["status"], df["reason"], df["next_step"] = status, reason, step

    # 기업집단 소속 재확인: 이전 기록과 2026-05 공정위 자료가 다르면 표시
    def group_check(r):
        prev, now = r.group_prev, r.group_2605
        if r.size in ("대기업", "대기업 계열") and not now:
            return "공정위 2026-05 명단에서 못 찾음"
        if prev and now and prev not in now.split("/"):
            return f"집단 다름: 이전 {prev} / 2026-05 {now}"
        if prev and not now:
            return f"2026-05 명단에서 못 찾음 (이전 {prev})"
        return ""
    df["group_check"] = df.apply(group_check, axis=1)

    # 제조1-3 결과 반영: 사람 판정이 먼저, 그다음 자동 선별 '해당 없음'
    df["status_final"], df["size_final"], df["final_note"] = df["status"], df["size"], ""
    if SIZE_CHECKS.exists():
        c = pd.read_csv(SIZE_CHECKS, dtype=str).fillna("")
        for r in c.itertuples():
            hit = df["k"] == key(r.name)
            df.loc[hit, ["status_final", "size_final", "final_note"]] = [
                r.verdict, r.size_after, f"제조1-3 확인({r.checked_on}): {r.note}"]
    if SIZE_SCREEN.exists():
        s = pd.read_csv(SIZE_SCREEN, dtype=str).fillna("")
        for r in s[s["result"] == "해당 없음"].itertuples():
            hit = (df["k"] == key(r.name)) & (df["status_final"] == "확인 대기")
            df.loc[hit, ["status_final", "size_final", "final_note"]] = [
                "제외", "중소", f"제조1-3 자동 선별: {r.why}"]

    cols = ["name", "status_final", "size_final", "final_note",
            "status", "reason", "next_step", "source", "listed", "size",
            "group_prev", "group_2605", "group_check", "corp_code", "kets_code", "jurir_no",
            "ftc_jurir_no", "ftc_ksic", "ftc_n", "ftc_match", "ksic", "kets_member", "is_holding", "note_prev"]
    return df[cols + ["k"]], ftc


def holding_candidates(df, ftc, kets):
    """지주회사별로 같은 기업집단의 CBAM 1차 업종 회사를 뽑고
    명단 포함 여부와 배출권 할당대상 여부를 표시함.
    기업집단 기준이라 한 집단에 지주회사가 여럿이면 다른 지주회사 아래 회사도 섞임.
    지분 30% 이상 여부는 사업보고서로 따로 확인해야 함"""
    in_list = set(df.loc[df["status"] != "제외", "k"])
    kets_map = kets.drop_duplicates("k").set_index("k")[["kets_code", "kets_ksic"]]
    out = []
    for h in df[df["is_holding"]].itertuples():
        groups = [g for g in (h.group_2605 or h.group_prev).split("/") if g]
        if not groups:
            out.append(dict(holding=h.name, group="", candidate="", ftc_ksic="",
                            assets_mil="", jurir_no="", in_list="", kets="",
                            note="공정위 기업집단 아님 → 지주회사 사업보고서 종속회사 목록으로 확인"))
            continue
        c = ftc[ftc["기업집단명"].isin(groups) & ftc["ksic4"].isin(CBAM1_KSIC4)]
        c = c[c["k"] != h.k]
        for r in c.itertuples():
            if r.k in kets_map.index:
                kc = kets_map.loc[r.k]
                kets_txt = f"대상 ({kc.kets_code}, {kc.kets_ksic})"
            else:
                kets_txt = "아님"
            out.append(dict(holding=h.name, group=r.기업집단명, candidate=r.소속회사명,
                            ftc_ksic=r.업종코드, assets_mil=r.자산총액, jurir_no=r.법인등록번호,
                            in_list="있음" if r.k in in_list else "없음", kets=kets_txt, note=""))
    return pd.DataFrame(out)


def main():
    df, ftc = build()
    hc = holding_candidates(df, ftc, load_kets())
    OUT.mkdir(parents=True, exist_ok=True)
    df.drop(columns="k").to_csv(OUT / "mfg1_merged.csv", index=False, encoding="utf-8-sig")
    hc.to_csv(OUT / "mfg1_holding_candidates.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 60)
    print(f"후보 전체 {len(df)}곳")
    print("\n[제조1-2 기준 상태]")
    print(pd.crosstab([df["source"], df["size"]], df["status"], margins=True, margins_name="합계"))
    print("\n[제조1-3 반영 후 최종 상태]")
    print(pd.crosstab(df["size_final"], df["status_final"], margins=True, margins_name="합계"))
    changed = df[(df["status"] == "확인 대기") & (df["status_final"] != "확인 대기")]
    print("\n[확인 대기 → 판정]")
    print(changed.groupby(["status_final", "size_final"]).size().to_string())
    print("\n포함으로 바뀐 곳: " + ", ".join(changed.loc[changed["status_final"] == "포함", "name"]))
    left = df[df["status_final"] == "확인 대기"]
    print("아직 확인 대기: " + (", ".join(left["name"]) if len(left) else "없음"))
    print("\n[제외·확인 대기]")
    print(df[df["status"] != "포함"][["name", "status", "reason"]].to_string(index=False))
    print("\n[기업집단 소속 재확인 필요]")
    g = df[df["group_check"] != ""][["name", "size", "group_check"]]
    print(g.to_string(index=False) if len(g) else "없음")
    print("\n[지주회사 사업회사 후보]")
    print(hc[["holding", "candidate", "ftc_ksic", "assets_mil", "in_list", "kets", "note"]].to_string(index=False))
    print("\n[명단에 없는데 배출권 할당대상인 지주회사 계열 후보]")
    x = hc[(hc["in_list"] == "없음") & hc["kets"].str.startswith("대상")].drop_duplicates("candidate")
    print(x[["holding", "candidate", "ftc_ksic", "kets"]].to_string(index=False) if len(x) else "없음")


if __name__ == "__main__":
    main()