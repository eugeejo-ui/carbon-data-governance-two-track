"""금융2-8 그림 — 순위·분포 3장 (seaborn)

- 입력: data/processed/fin2_verdict.csv (먼저 python src/fin/fin2_verdict.py 실행)
- 그림 (figures/) — 기존 fin2_figures.py의 fin_fig4~8과 번호가 이어짐
  1) fin_fig1_rank.png      선정 계정 순위 막대 — 합계 점수를 기준별로 쌓음
  2) fin_fig2_total.png     합계 점수 분포 — 선정 구간 강조
  3) fin_fig3_criteria.png  기준별 점수 분포 — 0·1·2점 곳 수
- 계획서 9장 F1~F3 원안의 "업권별 분포"는 빼고 순위 막대로 바꿈 (2026-10-01 사용자 결정 — 순위와 분포를 보는 용도, 박스플롯 미사용)
- 그림 문구에는 내부 기호(①②, ③-1 등)를 쓰지 않고 기준 이름을 씀
- 한글 글꼴은 맑은 고딕(윈도우) → 나눔고딕 → Noto 순으로 찾아 씀
"""
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
CUT = 5                                   # 선정 기준 (fin2_verdict.py와 같음)
WANT = ["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans KR", "Noto Sans CJK JP"]
CRIT = [("s1", "공시 의무 지위"), ("s2", "금융배출량 공시 빈칸"), ("s3", "제조업 대출·투자 노출"), ("s5", "IBM 거래 기록")]
CRIT_COLOR = ["#4C72B0", "#DD8452", "#55A868", "#8172B3"]
SCORE_COLOR = {"0점": "#BDBDBD", "1점": "#9ECAE1", "2점": "#3182BD"}
SEL, OTHER = "#3182BD", "#BDBDBD"


def set_font():
    have = {f.name for f in fm.fontManager.ttflist}
    for name in WANT:
        if name in have:
            plt.rcParams["font.family"] = name
            print(f"글꼴: {name}")
            break
    else:
        print("한글 글꼴을 찾지 못함 — 라벨이 깨질 수 있음")
    plt.rcParams["axes.unicode_minus"] = False
    fam = plt.rcParams["font.family"]
    sns.set_theme(style="whitegrid", font=fam[0] if isinstance(fam, list) else fam)


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장 {path.relative_to(ROOT)}")


def short(name):
    """그림용 짧은 이름 — (주)·㈜·주식회사 등을 뺌"""
    return re.sub(r"\(주\)|㈜|주식회사|\s+", "", str(name)) or str(name)


def fig1_rank(D):
    S = D[D["selected"] == "Y"].sort_values("rank").reset_index(drop=True)
    flag = S["ref_s2"].fillna("").str.startswith("② 공시 근거 못 찾음")
    labels = [f"{r}. {short(a)}" + (" †" if f else "") for r, a, f in zip(S["rank"], S["account"], flag)]
    fig, ax = plt.subplots(figsize=(9.5, 0.33 * len(S) + 2.2))
    y = np.arange(len(S))
    left = np.zeros(len(S))
    for (col, name), color in zip(CRIT, CRIT_COLOR):
        ax.barh(y, S[col], left=left, color=color, edgecolor="white", label=name)
        left += S[col].to_numpy()
    for i, t in enumerate(S["total"]):
        ax.text(t + 0.08, i, f"{t}점", va="center", fontsize=8, color="#333")
    ax.set_yticks(y, labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 8.6)
    ax.set_xticks(range(0, 9))
    ax.set_xlabel("합계 점수 (최대 8점)")
    ax.set_title(f"우선 계정 {len(S)}곳의 합계 점수와 기준별 구성 (합계 {CUT}점 이상)", fontsize=12)
    ax.legend(loc="lower right", frameon=True, fontsize=9, title="기준")
    fig.text(0.01, -0.02, "† 금융배출량 공시 근거를 찾지 못해 '공시 빈칸' 2점을 받은 곳 — 원문 대조에서 공시가 확인되면 합계가 1점 내려감\n"
             "점수가 높을수록 진입 우선순위가 높음. IBM 거래 기록 0점은 '거래 없음'이 아니라 '공개 자료로 확인 안 됨'",
             fontsize=8, color="#555", va="top")
    save(fig, "fin_fig1_rank.png")


def fig2_total(D):
    cnt = D["total"].value_counts().reindex(range(0, 9), fill_value=0)
    sel = D[D["total"] >= CUT]
    units = sel["report_unit"].nunique()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = [SEL if s >= CUT else OTHER for s in cnt.index]
    ax.bar(cnt.index, cnt.values, color=colors, width=0.7)
    for s, c in cnt.items():
        if c:
            ax.text(s, c + 1.5, f"{c}곳", ha="center", fontsize=9, color="#333")
    ax.axvline(CUT - 0.5, color="#444", ls="--", lw=1)
    ax.text(CUT - 0.42, cnt.max() * 0.92, f"선정 기준: {CUT}점 이상\n{len(sel)}곳 ({len(sel) / len(D):.1%}) · 보고 단위 {units}개",
            fontsize=9, color="#222", va="top")
    ax.set_xticks(range(0, 9))
    ax.set_xlabel("합계 점수 (최대 8점)")
    ax.set_ylabel("금융회사 수 (곳)")
    ax.set_ylim(0, cnt.max() * 1.15)
    ax.set_title(f"금융회사 {len(D)}곳의 합계 점수 분포", fontsize=12)
    fig.text(0.01, -0.02, "합계 = 공시 의무 지위 + 금융배출량 공시 빈칸 + 제조업 대출·투자 노출 + IBM 거래 기록 (각 0~2점)\n"
             "분포에 뚜렷한 끊김이 없어 점수 구간 경계에서 끊음 — 같은 점수 안에서 선정·비선정이 갈리지 않음",
             fontsize=8, color="#555", va="top")
    save(fig, "fin_fig2_total.png")


def fig3_criteria(D):
    rows = []
    for col, name in CRIT:
        vc = D[col].value_counts().reindex([0, 1, 2], fill_value=0)
        rows += [dict(기준=name, 점수=f"{s}점", 곳수=int(c)) for s, c in vc.items()]
    L = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    sns.barplot(data=L, x="기준", y="곳수", hue="점수", hue_order=["0점", "1점", "2점"],
                palette=SCORE_COLOR, ax=ax)
    for cont in ax.containers:
        ax.bar_label(cont, fmt="%d", fontsize=8, padding=2)
    ax.set_xlabel("")
    ax.set_ylabel("금융회사 수 (곳)")
    ax.set_ylim(0, L["곳수"].max() * 1.12)
    ax.set_title(f"기준별 점수 분포 (금융회사 {len(D)}곳)", fontsize=12)
    ax.legend(title="점수", frameon=False, fontsize=9)
    fig.text(0.01, -0.02, "공시 의무 지위: 상장 2점 · 비상장 종속과 공공 1점 · 그 밖 0점 / 금융배출량 공시 빈칸: 공시가 없을수록 2점\n"
             "제조업 대출·투자 노출: 세 갈래 측정 중 높은 쪽 / IBM 거래 기록: 최근 5년 공개 계약 2점 · 그 이전 사례 1점 · 확인 안 됨 0점",
             fontsize=8, color="#555", va="top")
    save(fig, "fin_fig3_criteria.png")


def main():
    set_font()
    D = pd.read_csv(PROC / "fin2_verdict.csv", dtype={"account": str})
    for c in ("rank", "total", "s1", "s2", "s3", "s5"):
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0).astype(int)
    D["selected"] = D["selected"].fillna("")
    print(f"입력 {len(D)}곳 · 선정 {int((D['selected'] == 'Y').sum())}곳")
    fig1_rank(D)
    fig2_total(D)
    fig3_criteria(D)


if __name__ == "__main__":
    main()
