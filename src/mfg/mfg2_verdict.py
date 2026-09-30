"""제조2-7 가설 판정과 경계값 점검

- 입력: data/processed/mfg2_rank.csv
- 계획서 6-2 판정 기준을 그대로 적용함 (결과를 보고 바꾸지 않음)
  - H1 맞음: ⑤ 1점 이상이 과반 / 부분: 과반이나 합계 상위 1/3에서 ⑤ 0점이 과반 / 틀림: ⑤ 0점이 과반
  - H2 맞음: ② 2점 + ④ 1점 이상 + ⑤ 1점 이상을 모두 갖춘 계정이 1곳 이상 / 틀림: 0곳
- 중견·대기업으로 나눠서도 집계함 (계획서 6-2 단서)
- 시멘트·비료 계정은 ⑤ 2점이어도 CBAM 수요가 약하므로 H1 결과에 따로 표시함 (v1.4)
- 경계값: 기준 하나가 바뀌면 순위·판정이 흔들리는 계정을 표시함 (점수 아님)

출력: data/processed/mfg2_verdict.csv (계정별 판정 표시), 화면에 판정문 재료
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = PROC / "mfg2_verdict.csv"

WEAK_ITEM = ("시멘트", "비료")      # CBAM 수요가 약한 품목
BIG = ("대기업", "대기업 계열", "외국계 대기업 계열")


def half(n):
    """과반 기준값 (n의 절반 초과)"""
    return n / 2


def block(df, label):
    """집단 하나의 H1·H2 수치"""
    n = len(df)
    h1_n = int((df["s5"] >= 1).sum())
    top = df.nsmallest(max(1, round(n / 3)), "rank")
    top0 = int((top["s5"] == 0).sum())
    h2 = df[(df["s2"] == 2) & (df["s4"] >= 1) & (df["s5"] >= 1)]
    return dict(집단=label, 곳=n,
                H1_1점이상=h1_n, H1_비율=round(h1_n / n * 100, 1),
                상위3분의1=len(top), 상위_0점=top0,
                H2_충족=len(h2))


def main():
    df = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    for c in ("rank", "s2", "s3", "s4", "s5", "s6", "total"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    n = len(df)
    df["규모군"] = df["size"].map(lambda s: "대기업군" if s in BIG else "중견")
    df["수요약함"] = df["cbam_item"].map(
        lambda x: "수요 약함" if any(w in str(x) for w in WEAK_ITEM) else "")

    # H1
    h1_n = int((df["s5"] >= 1).sum())
    third = df.nsmallest(round(n / 3), "rank")
    third0 = int((third["s5"] == 0).sum())
    if h1_n <= half(n):
        h1 = "틀림"
    elif third0 > half(len(third)):
        h1 = "부분"
    else:
        h1 = "맞음"

    # H2
    h2 = df[(df["s2"] == 2) & (df["s4"] >= 1) & (df["s5"] >= 1)].copy()
    h2_verdict = "맞음" if len(h2) >= 1 else "틀림"

    # 경계값 표시 (점수 아님) — 기준 하나가 바뀌면 순위·판정이 흔들리는 계정만 좁혀서 표시함
    # 대상을 합계 상위 1/3로 한정함. 하위권은 한 칸 바뀌어도 선정에 영향이 없음
    top_n = round(len(df) / 3)
    df["경계"] = ""
    top_idx = df["rank"] <= top_n

    # (가) ⑤ 웹 개별검색을 하지 않은 2점 — 경쟁자가 나오면 2점→0점으로 두 칸 떨어짐
    no_web = [
        "알루코", "한주라이트메탈", "하이호경금속", "대호에이엘", "대호특수강", "환영철강공업",
        "넥스틸", "와이케이스틸", "진양특수강", "한국제강", "현대아이에프씨", "일진제강",
        "디케이동신", "한일제관", "하이스틸", "원일특강", "케이피에프", "성광벤드", "태광",
        "다스코", "에스와이", "제일테크노스", "동국에스엔씨", "삼목에스폼", "대창스틸"]
    hit = df["account"].map(lambda a: any(k in str(a) for k in no_web))
    df.loc[top_idx & hit & (df["s5"] == 2), "경계"] += "⑤ 웹 미조사 "

    # (나) ⑥ 불명 — 확인되면 1점→2점으로 오름
    df.loc[top_idx & (df["cbam_eu_exposure"] == "불명"), "경계"] += "⑥ 불명 "

    # (다) ③ 공장 2곳 — 공장 1곳만 더 찾으면 1점→2점
    df.loc[top_idx & (df["s3"] == 1), "경계"] += "③ 공장 2곳 "

    # (라) 선정 경계선 — 상위 1/3의 마지막 합계 구간에 걸친 계정
    cut = int(df.loc[df["rank"] == top_n, "total"].iloc[0])
    df.loc[df["total"] == cut, "경계"] += f"선정 경계선(합계 {cut}점) "
    df["경계"] = df["경계"].str.strip()

    df["H2충족"] = ((df["s2"] == 2) & (df["s4"] >= 1) & (df["s5"] >= 1)).map(
        {True: "Y", False: ""})
    cols = ["rank", "account", "size", "규모군", "cbam_item", "수요약함",
            "s2", "s3", "s4", "s5", "s6", "total",
            "cbam_eu_exposure", "competitor_layer", "evidence_source",
            "H2충족", "경계"]
    df[cols].to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print(f"{n}곳 → {OUT.relative_to(ROOT)}\n")

    print("[H1] 1차 업종 제조사 과반은 상용 탄소관리 솔루션 도입이 확인되지 않음 (⑤ 1점 이상)")
    print(f"  전체 {h1_n}/{n}곳 ({h1_n / n * 100:.1f}%) · 과반 기준 {half(n):.0f}곳 초과")
    print(f"  합계 상위 1/3 {len(third)}곳 중 ⑤ 0점 {third0}곳")
    print(f"  → 판정: {h1}")
    print(f"  ⑤ 분포: {df['s5'].value_counts().sort_index().to_dict()}")
    weak = df[(df["s5"] >= 1) & (df["수요약함"] != "")]
    print(f"  수요 약함(시멘트·비료) {len(weak)}곳 포함: {weak['account'].tolist()}")

    print("\n[H2] 필요성(②2)·예산(④≥1)·빈자리(⑤≥1)를 모두 갖춘 계정이 1곳 이상")
    print(f"  충족 {len(h2)}곳 → 판정: {h2_verdict}")
    print(h2[["rank", "account", "size", "s2", "s4", "s5", "s6", "total",
              "cbam_eu_exposure"]].to_string(index=False))

    print("\n[집단별]")
    rows = [block(df, "전체"), block(df[df["규모군"] == "중견"], "중견"),
            block(df[df["규모군"] == "대기업군"], "대기업군")]
    print(pd.DataFrame(rows).to_string(index=False))

    print(f"\n[경계값 표시 계정] 대상: 합계 상위 1/3 {top_n}곳 + 선정 경계선 구간")
    edge = df[df["경계"] != ""].sort_values("rank")
    print(f"  {len(edge)}곳")
    print(edge[["rank", "account", "total", "cbam_eu_exposure", "경계"]].to_string(index=False))
    print("\n  뜻: ⑤ 웹 미조사 = 경쟁자가 나오면 2점→0점(두 칸 하락) · "
          "⑥ 불명 = 확인되면 1점→2점 · ③ 공장 2곳 = 1곳 더 찾으면 1점→2점")


if __name__ == "__main__":
    main()