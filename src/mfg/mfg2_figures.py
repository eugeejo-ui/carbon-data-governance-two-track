"""제조2-7 점수 분포 그래프 (seaborn)

- 입력: data/processed/mfg2_verdict.csv (먼저 python src/mfg/mfg2_verdict.py 실행)
- 그림 4장을 따로 저장함
  1) fig1_total_dist.png    합계 분포
  2) fig2_criteria.png      기준별(②③④⑤⑥) 점수 분포
  3) fig3_size_box.png      규모별 합계 상자그림
  4) fig4_eu_exposure.png   EU 노출별 합계 분포 (H2 충족 계정 표시)
- 한글 글꼴은 맑은 고딕(윈도우) → 나눔고딕 → Noto 순으로 찾아 씀
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "processed" / "mfg2_verdict.csv"
FIG = ROOT / "figures"

WANT = ["Malgun Gothic", "NanumGothic", "AppleGothic",
        "Noto Sans CJK KR", "Noto Sans KR", "Noto Sans CJK JP"]


def set_font():
    have = {f.name for f in fm.fontManager.ttflist}
    for name in WANT:
        if name in have:
            plt.rcParams["font.family"] = name
            print(f"글꼴: {name}")
            return
    print("한글 글꼴을 찾지 못함 — 라벨이 깨질 수 있음")


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장 {path.relative_to(ROOT)}")


def main():
    set_font()
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font=plt.rcParams["font.family"][0]
                  if isinstance(plt.rcParams["font.family"], list)
                  else plt.rcParams["font.family"])

    df = pd.read_csv(SRC, dtype=str).fillna("")
    for c in ("rank", "s2", "s3", "s4", "s5", "s6", "total"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # 1) 합계 분포
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.countplot(data=df, x="total", hue="규모군", ax=ax,
                  palette={"중견": "#4C72B0", "대기업군": "#DD8452"})
    ax.set_title("합계 점수 분포 (94곳, 만점 10점)", fontsize=13, pad=12)
    ax.set_xlabel("합계 점수")
    ax.set_ylabel("계정 수")
    ax.legend(title="")
    for c in ax.containers:
        ax.bar_label(c, fmt="%d", fontsize=8, padding=1)
    save(fig, "fig1_total_dist.png")

    # 2) 기준별 점수 분포
    names = {"s2": "② 정부 검증 총량", "s3": "③ 공장 흩어짐", "s4": "④ IT 예산",
             "s5": "⑤ 2층 경쟁", "s6": "⑥ EU 노출"}
    long = df.melt(id_vars=["account"], value_vars=list(names),
                   var_name="기준", value_name="점수")
    long["기준"] = long["기준"].map(names)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.countplot(data=long, x="기준", hue="점수", ax=ax,
                  palette={0: "#B0B7BF", 1: "#5B8FC9", 2: "#1F3A63"})
    ax.set_title("기준별 점수 분포", fontsize=13, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("계정 수")
    ax.legend(title="점수", loc="upper left")
    for c in ax.containers:
        ax.bar_label(c, fmt="%d", fontsize=8, padding=1)
    save(fig, "fig2_criteria.png")

    # 3) 규모별 합계 상자그림
    fig, ax = plt.subplots(figsize=(7, 5))
    order = ["중견", "대기업", "대기업 계열", "외국계 대기업 계열"]
    order = [o for o in order if o in set(df["size"])]
    sns.boxplot(data=df, x="size", y="total", order=order, ax=ax,
                color="#C6DBEF", width=0.5, showfliers=False)
    sns.stripplot(data=df, x="size", y="total", order=order, ax=ax,
                  color="#2B4C7E", size=4, alpha=0.7, jitter=0.2)
    ax.set_title("규모별 합계 점수", fontsize=13, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("합계 점수")
    for i, o in enumerate(order):
        sub = df[df["size"] == o]
        ax.text(i, 10.6, f"n={len(sub)}\n평균 {sub['total'].mean():.1f}",
                ha="center", fontsize=9, color="#444")
    ax.set_ylim(2, 11.4)
    save(fig, "fig3_size_box.png")

    # 4) EU 노출별 합계 분포 (H2 충족 표시)
    fig, ax = plt.subplots(figsize=(9, 5))
    order6 = ["확인", "신규", "축소", "불명", "미확인"]
    order6 = [o for o in order6 if o in set(df["cbam_eu_exposure"])]
    sns.boxplot(data=df, x="cbam_eu_exposure", y="total", order=order6, ax=ax,
                color="#E8E8E8", width=0.55, showfliers=False)
    sns.stripplot(data=df, x="cbam_eu_exposure", y="total", order=order6, ax=ax,
                  hue="H2충족", palette={"Y": "#C44E52", "": "#8C8C8C"},
                  size=6, alpha=0.85, jitter=0.22, dodge=False)
    ax.set_title("EU 노출별 합계 점수 — 붉은 점은 H2 세 조건 충족 계정",
                 fontsize=13, pad=12)
    ax.set_xlabel("⑥ EU 노출 판정")
    ax.set_ylabel("합계 점수")
    h, lab = ax.get_legend_handles_labels()
    keep = [(a, b) for a, b in zip(h, lab) if b == "Y"]
    ax.legend([a for a, _ in keep], ["H2 충족"], loc="lower left")
    for i, o in enumerate(order6):
        sub = df[df["cbam_eu_exposure"] == o]
        ax.text(i, 10.6, f"n={len(sub)}\nH2 {int((sub['H2충족'] == 'Y').sum())}곳",
                ha="center", fontsize=9, color="#444")
    ax.set_ylim(2, 11.4)
    save(fig, "fig4_eu_exposure.png")

    print(f"\n그림 4장 → {FIG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()