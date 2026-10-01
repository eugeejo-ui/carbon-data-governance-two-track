"""정리-1·로드맵 — 트랙별 최종 순위표 + 연도별 진입 로드맵 + 타임라인 그림 (새 조사 없음)

- 입력 (data/processed/): mfg2_rank.csv (제조 1차 94곳) · mfg_wave2_scores.csv (제조 하류 46곳) ·
  fin2_verdict.csv + fin_scores.csv (금융 278곳, 공시 연도)
- 우선 계정: 제조 1차 합계 8점 이상(17곳, v1.5) · 금융 합계 5점 이상(37곳, v1.11) · 하류는 미확정이라 전부 후보
- 연락 연도 규칙 (계획서 7-1을 연도로 나눔)
  - 제조 1차: EU 노출 확인·신규 → 2026 하반기 (2027-02 인증서 판매·2027-09-30 첫 연례 신고 전에 EU 수입자 데이터 요청이 옴)
              그 밖(축소·불명·미확인) → 2027
  - 제조 하류: 합계 7점 이상 → 2028 (적용 목표 2028-01-01, 3자 협상 결과 확인 뒤), 그 밖 → 확정 뒤 재평가
               2027은 합의 확인 뒤 ⑤ 경쟁·EU 노출을 재조사하는 해
  - 금융: 금융배출량(Scope 3)은 ESG 공시 시작 3년 뒤 — 공시 연도 2028(자산 10조 이상) → 2031 공시 → 2029 연락(준비 마감 2029년 말)
          2029 → 2032 → 2030 / 2030(검토) → 2033 검토 → 2030 / 알리오(공공) → 2029 (단계 확대, 일정 미정) / 대상 아님 → 2030
- 출력: data/processed/final_ranking.csv · roadmap.csv · roadmap_summary.csv, figures/roadmap_timeline.png
"""
from pathlib import Path
import re
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
MFG_CUT, FIN_CUT, WAVE2_CUT = 8, 5, 7
YEARS = ["2026 하반기", "2027", "2028", "2029", "2030", "2031"]
EVENTS = [  # (연도 칸, 사건) — 계획서 1·5·7장 확인 사실
    ("2026 하반기", "전환금융 실무 모범규준 확정(10월 말 예정) · CBAM 하류 3자 협상(연내 합의 목표)"),
    ("2027", "CBAM 인증서 판매 시작(2-1) · 첫 연례 신고·반납(9-30)"),
    ("2028", "CBAM 하류 적용 목표(1-1, 미확정) · ESG 공시 자산 10조 이상 시작"),
    ("2029", "ESG 공시 5조 이상 · 금융배출량 준비 마감(연말)"),
    ("2030", "제3자 인증 시작(범위 미정) · ESG 공시 2조 이상 검토"),
    ("2031", "금융배출량(Scope 3) 법정 공시 — 자산 10조 이상"),
]
TOUCH = {
    "제조 1차": "설비·제품별 배출량 산정 근거와 출처 증빙 묶음 — CBAM 신고·EU 수입자 요청 대응, 같은 데이터로 ESG 공시·은행 전환금융 심사",
    "제조 하류": "하류 확대 확정 시 제품 내 철강·알루미늄 함량별 내재 배출량 산정 — 공급사 데이터 수집·출처 관리 체계",
    "금융": "금융배출량 데이터의 출처 구분(신정원 플랫폼 추정치 vs 차주 실측)·변경 이력·인증 대비 증빙",
}
FIN_YEAR = {"2028": ("2029", "2031 금융배출량 공시(10조 이상) — 준비 마감 2029년 말"),
            "2029": ("2030", "2032 금융배출량 공시(5조 이상, 3년 유예 적용 시)"),
            "2030(검토)": ("2030", "2033 금융배출량 공시 검토(2조 이상)"),
            "알리오": ("2029", "알리오 통합공시 Scope 3 단계 확대(일정 미정)")}


def key(name):
    return re.sub(r"\s|\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))


def set_font():
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans KR"]:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    fam = plt.rcParams["font.family"]
    sns.set_theme(style="whitegrid", font=fam[0] if isinstance(fam, list) else fam)


def mfg1():
    d = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    for c in ("rank", "total", "s2", "s3", "s4", "s5", "s6"):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int)
    eu = d.get("cbam_eu_exposure", pd.Series([""] * len(d)))
    d["priority"] = (d["total"] >= MFG_CUT).map({True: "Y", False: ""})
    d["contact_year"] = [("2026 하반기" if e in ("확인", "신규") else "2027") if p == "Y" else "" for p, e in zip(d["priority"], eu)]
    d["trigger"] = ["2027-09-30 첫 연례 신고 — EU 수입자 데이터 요청" if y == "2026 하반기" else
                    "CBAM 신고 2년차·ESG 공시 대비" if y else "" for y in d["contact_year"]]
    d["basis"] = [f"합계 {t}점(②{a}③{b}④{c}⑤{e}⑥{f}) · EU 노출 {x or '없음'}"
                  for t, a, b, c, e, f, x in zip(d["total"], d["s2"], d["s3"], d["s4"], d["s5"], d["s6"], eu)]
    return pd.DataFrame(dict(track="제조 1차", rank=d["rank"], account=d["account"], segment=d["size"],
                             total=d["total"], max_score=10, priority=d["priority"], contact_year=d["contact_year"],
                             trigger=d["trigger"], basis=d["basis"], unit=""))


def mfg_wave2():
    d = pd.read_csv(PROC / "mfg_wave2_scores.csv", dtype=str).fillna("")
    for c in ("rank", "total"):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int)
    y = d["total"].map(lambda t: "2028" if t >= WAVE2_CUT else "확정 뒤 재평가")
    return pd.DataFrame(dict(track="제조 하류", rank=d["rank"], account=d["account"], segment=d["size"],
                             total=d["total"], max_score=8, priority="후보(미확정)", contact_year=y,
                             trigger=y.map({"2028": "CBAM 하류 적용 목표 2028-01-01 (3자 협상 결과 확인 뒤)",
                                            "확정 뒤 재평가": "확정 뒤 재평가"}),
                             basis=[f"합계 {t}점 · {b} · ⑤ {s}" for t, b, s in zip(d["total"], d["s2_basis"], d["s5_basis"])],
                             unit=""))


def fin():
    v = pd.read_csv(PROC / "fin2_verdict.csv", dtype=str).fillna("")
    s = pd.read_csv(PROC / "fin_scores.csv", dtype=str).fillna("")
    v = v.merge(s[["account", "disclosure_year"]], on="account", how="left").fillna("")
    for c in ("rank", "total"):
        v[c] = pd.to_numeric(v[c], errors="coerce").fillna(0).astype(int)
    yr = [FIN_YEAR.get(y, ("2030", "자율 공시 단계 — 그룹 공시 편입 시 앞당김")) if sel == "Y" else ("", "")
          for y, sel in zip(v["disclosure_year"], v["selected"])]
    return pd.DataFrame(dict(track="금융", rank=v["rank"], account=v["account"], segment=v["group"],
                             total=v["total"], max_score=8, priority=v["selected"],
                             contact_year=[a for a, _ in yr], trigger=[b for _, b in yr],
                             basis=[f"합계 {t}점 · 공시 연도 {y or '없음'} · {r}" for t, y, r in
                                    zip(v["total"], v["disclosure_year"], v["ref_s2"].str.slice(0, 24))],
                             unit=v["report_unit"]))


def timeline(R):
    S = R[R["contact_year"] != ""]
    tracks = ["제조 1차", "제조 하류", "금융"]
    x = {y: i for i, y in enumerate(YEARS + ["확정 뒤 재평가"])}
    fig, ax = plt.subplots(figsize=(12, 5.2))
    colors = {"제조 1차": "#DD8452", "제조 하류": "#F2C49B", "금융": "#4C72B0"}
    for j, t in enumerate(tracks):
        g = S[S["track"] == t].groupby("contact_year").size()
        for y, n in g.items():
            xi = x.get(y, len(YEARS))
            ax.barh(j, 0.9, left=xi - 0.45, height=0.55, color=colors[t], edgecolor="white")
            units = S[(S["track"] == t) & (S["contact_year"] == y)]["unit"].replace("", pd.NA).dropna().nunique()
            ax.text(xi, j, f"{n}곳" + (f"\n(보고 단위 {units}개)" if units else ""), ha="center", va="center", fontsize=9)
    for y, e in EVENTS:
        lines = "\n".join(textwrap.fill(part, 13) for part in e.split(" · "))
        ax.text(x[y], len(tracks) - 0.3, lines, ha="center", va="top", fontsize=7, color="#444")
    ax.set_yticks(range(len(tracks)), ["제조 — CBAM 1차 업종 우선 계정", "제조 — CBAM 하류 후보(미확정)", "금융 — 우선 계정"])
    ax.set_xticks(range(len(x)), list(x.keys()))
    ax.set_xlim(-0.6, len(x) - 0.4)
    ax.set_ylim(-0.6, len(tracks) + 1.2)
    ax.invert_yaxis()
    ax.set_title("트랙별 연도별 진입 경로 (연락 연도별 계정 수와 그해 규제 계기)", fontsize=12)
    fig.text(0.01, -0.04, "연락 연도는 계획서 7-1 규칙을 연도로 나눈 것임. 제조 하류는 CBAM 확대가 확정되기 전의 후보임\n"
             "금융은 ESG 공시 시작 3년 뒤의 금융배출량 법정 공시(자산 10조 이상 2031년)를 기준으로 함. 아래 문구는 그해 규제 계기",
             fontsize=8, color="#555", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "roadmap_timeline.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    R = pd.concat([mfg1(), mfg_wave2(), fin()], ignore_index=True)
    R["first_touch"] = [TOUCH[t] if y else "" for t, y in zip(R["track"], R["contact_year"])]
    R.to_csv(PROC / "final_ranking.csv", index=False, encoding="utf-8-sig")
    M = R[R["contact_year"] != ""].copy()
    M["year_order"] = M["contact_year"].map({y: i for i, y in enumerate(YEARS + ["확정 뒤 재평가"])})
    M = M.sort_values(["year_order", "track", "rank"]).drop(columns="year_order")
    M.to_csv(PROC / "roadmap.csv", index=False, encoding="utf-8-sig")
    ev = dict(EVENTS)
    Sm = (M.groupby(["contact_year", "track"]).agg(accounts=("account", "size"),
                                                   units=("unit", lambda s: s.replace("", pd.NA).dropna().nunique()),
                                                   names=("account", lambda s: " · ".join(map(key, s.head(8)))))
          .reset_index())
    Sm["event"] = Sm["contact_year"].map(ev).fillna("")
    Sm["first_touch"] = Sm["track"].map(TOUCH)
    Sm.to_csv(PROC / "roadmap_summary.csv", index=False, encoding="utf-8-sig")
    set_font()
    timeline(M)

    pd.set_option("display.width", 230)
    pd.set_option("display.max_colwidth", 70)
    print(f"→ final_ranking.csv ({len(R)}행) · roadmap.csv ({len(M)}행) · roadmap_summary.csv · figures/roadmap_timeline.png")
    print("\n[1] 트랙별 행 수 · 우선/후보 수")
    print(R.groupby("track").agg(rows=("account", "size"), contact=("contact_year", lambda s: int((s != '').sum()))).to_string())
    print("\n[2] 연도별 로드맵 요약")
    print(Sm[["contact_year", "track", "accounts", "units", "names"]].to_string(index=False))


if __name__ == "__main__":
    main()