"""금융2-8 그림 (1차) — ③-2·③-3 집계로 그릴 수 있는 4장 (seaborn)

- 입력: data/processed/fin_exposure.csv · fin_borrower_edges.csv (먼저 python src/fin/fin2_exposure.py 실행)
- 그림 (figures/)
  4) fin_fig4_eu_share.png        금융회사별 CBAM 제조사 거래 수 및 EU 수출 확인 제조사 비중 (제조 fig4와 짝)
  5) fin_fig5_sector_heatmap.png  금융회사 × 차주 업종별 거래 차주 수 (③-2·③-3 전체)
  6) fin_fig6_mfg_network.png     업종별 거래 연결망 ① 제조 94곳 – 금융회사 (원 크기: 연결 수, 색상: 업종, 빨간 테두리: EU 수출 확인)
  6b) fin_fig6b_all_network.png   업종별 거래 연결망 ② 고탄소 차주 전체(③-2·③-3) – 금융회사
  7) fin_fig7_layers.png          금융회사별 ③-3 대비 ③-2 거래 차주 수 비교 (③-2로 추가 식별된 금융회사 표시)
  8) fin_fig8_coverage.png        결론 — 금융회사 수에 따른 CBAM 제조사·EU 수출 제조사 누적 포괄률
- F1~F3(합계·기준별·업권별 분포)은 ①②③-1⑤ 점수가 나온 뒤 같은 파일에 더함 (04 문서 9장)
- 곳 수만 씀 — 금액은 점수에 안 쓰는 원칙대로 선 굵기에도 쓰지 않음 (04 문서 3-7-3)
- 한글 글꼴은 맑은 고딕(윈도우) → 나눔고딕 → Noto 순으로 찾아 씀
"""
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"

T33_HIGH, T32_HIGH = 16, 30                     # fin2_exposure.py 문턱과 같음
WANT = ["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans KR", "Noto Sans CJK JP"]
TYPE_COLOR = {"은행": "#4C72B0", "보험": "#55A868", "카드·캐피탈": "#DD8452", "증권·운용": "#8172B3", "기타": "#8C8C8C"}
EU_RED = "#C44E52"
OTHER = "기타 업종"


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


NICK = {"한국산업은행": "산업은행", "한국수출입은행": "수출입은행", "중소기업은행": "기업은행",
        "한국스탠다드차타드은행": "SC제일은행", "한국씨티은행": "씨티은행"}


def short(name):
    """그림용 짧은 이름 — (주)·㈜·주식회사 등을 빼고 긴 은행 이름은 줄임"""
    t = re.sub(r"\(주\)|㈜|주식회사|\s+", "", str(name)) or str(name)
    return NICK.get(t, t)


def sector(s):
    """제조 CBAM 품목과 배출권 업종 구분을 한 표기로"""
    s = str(s or "")
    if re.search(r"알루미늄", s):
        return "알루미늄"
    if re.search(r"시멘트", s):
        return "시멘트·비금속"
    if re.search(r"비료|수소", s):
        return "화학"
    if re.search(r"철|강|금속|합금|선재", s):
        return "철강·금속"
    return s or "기타"


def load():
    A = pd.read_csv(PROC / "fin_exposure.csv", dtype={"account": str}).fillna(0)
    E = pd.read_csv(PROC / "fin_borrower_edges.csv", dtype=str).fillna("")
    E["sector"] = E["borrower_sector"].map(sector)
    A = A.sort_values("exposure_order")
    A["name"] = A["account"].map(short)
    return A, E


def fig4_eu_share(A):
    d = A[A["n33"] > 0].copy()
    if d["n33_eu"].sum() == 0:
        print("  (EU 확인 차주가 0 — mfg2_verdict.csv가 없거나 비어 있어 4번 그림을 건너뜀)")
        return
    d["그 밖"] = d["n33"] - d["n33_eu"]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(d) + 1.6))
    y = np.arange(len(d))
    ax.barh(y, d["n33_eu"], color=EU_RED, label="EU 수출 확인 제조사")
    ax.barh(y, d["그 밖"], left=d["n33_eu"], color="#C6DBEF", label="기타 제조사")
    for i, (eu, n) in enumerate(zip(d["n33_eu"], d["n33"])):
        ax.text(n + 0.6, i, f"{n}곳 (EU {eu})", va="center", fontsize=8, color="#444")
    ax.axvline(T33_HIGH, color="#444", ls="--", lw=1)
    ax.text(T33_HIGH + 0.4, -0.9, f"점수 2점 기준선 ({T33_HIGH}곳)", fontsize=8, color="#444")
    ax.set_yticks(y, d["name"])
    ax.invert_yaxis()
    ax.set_xlabel("거래 제조사 수 (CBAM 대상 제조사 94곳 중)")
    ax.set_title("금융회사별 CBAM 대상 제조사 거래 수 및 EU 수출 확인 제조사 비중", fontsize=13, pad=12)
    ax.legend(loc="lower right")
    save(fig, "fin_fig4_eu_share.png")


def fig5_heatmap(A, E):
    lenders = A[(A["n33"] + A["n32"]) > 0]["account"].tolist()
    g = E[E["lender"].isin(lenders)].groupby(["lender", "sector"])["borrower"].nunique().unstack(fill_value=0)
    order = g.sum().sort_values(ascending=False)
    keep = order.index[:10].tolist()
    if len(order) > 10:
        g[OTHER] = g[[c for c in g.columns if c not in keep]].sum(axis=1)
        keep += [OTHER]
    g = g.reindex(index=lenders, columns=keep, fill_value=0)
    g.index = [short(x) for x in g.index]
    annot = g.astype(int).astype(str).replace("0", "")
    fig, ax = plt.subplots(figsize=(0.75 * len(keep) + 3, 0.34 * len(g) + 1.8))
    sns.heatmap(g, cmap="Blues", annot=annot, fmt="", linewidths=0.4, linecolor="#EEE",
                cbar_kws={"label": "거래 기업 수", "shrink": 0.6}, ax=ax, annot_kws={"fontsize": 8})
    types = A.set_index("account").loc[lenders, "lender_type"].tolist()
    for lab, t in zip(ax.get_yticklabels(), types):
        lab.set_color(TYPE_COLOR.get(t, "#444"))
    ax.set_xlabel("거래 기업 업종 (CBAM 대상 제조사: CBAM 품목 · 그 밖 고탄소 기업: 배출권 업종 구분)")
    ax.set_ylabel("")
    ax.set_title("금융회사 × 고탄소 기업 업종별 거래 기업 수\n"
                 "(고탄소 기업: 배출권 할당대상 기업 + CBAM 대상 제조사 · 금융회사명 색상: 업권 구분)", fontsize=13, pad=12)
    handles = [Line2D([], [], marker="s", ls="", color=c, label=t) for t, c in TYPE_COLOR.items() if t in types]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.18, 1), title="업권", frameon=False)
    save(fig, "fin_fig5_sector_heatmap.png")


def sector_palette(E):
    """업종 색 — ①·②에서 같은 업종은 같은 색"""
    order = E.groupby("sector")["borrower"].nunique().sort_values(ascending=False).index.tolist()
    pal = dict(zip(order, sns.color_palette("tab20", len(order))))
    pal[OTHER] = (0.62, 0.62, 0.62)
    return pal


def layout(borrowers, sec_of, deg, sec_order, R=1.0, ring_gap=0.11, spacing=0.07):
    """둘레를 업종 크기만큼 나눠 구역을 만들고, 회사가 많은 구역은 여러 겹으로 둠"""
    n = len(borrowers)
    gap = 0.10
    total = 2 * np.pi - gap * len(sec_order)
    pos, wedge, a0 = {}, {}, np.pi / 2
    for sct in sec_order:
        m = sorted([b for b in borrowers if sec_of[b] == sct], key=lambda b: (-deg[b], b))
        if not m:
            continue
        span = total * len(m) / n
        cap = max(1, int(span * R / spacing))
        k = int(np.ceil(len(m) / cap))
        per = int(np.ceil(len(m) / k))
        for i, b_ in enumerate(m):
            r, j = i % k, i // k
            ang = a0 - (j + 0.5 + (0.5 if r % 2 else 0)) * span / per
            rad = R + ring_gap * r
            pos[b_] = np.array([rad * np.cos(ang), rad * np.sin(ang)])
        wedge[sct] = (a0, a0 - span, len(m), R + ring_gap * (k - 1))
        a0 -= span + gap
    return pos, wedge


def place_lenders(lenders, nbrs, pos, size_r, pull=0.55, rmax=0.80, iters=600):
    """금융회사는 거래처 평균 위치 쪽으로 끌려간 뒤, 원끼리 밀어내 겹치지 않게 함"""
    P = {a: pull * np.mean([pos[b] for b in nbrs[a]], axis=0) for a in lenders}
    for _ in range(iters):
        moved = False
        for i, a in enumerate(lenders):
            for c in lenders[i + 1:]:
                d = P[a] - P[c]
                dist = np.linalg.norm(d) + 1e-9
                need = (size_r[a] + size_r[c]) * 1.08 + 0.02
                if dist < need:
                    push = (need - dist) / 2 * d / dist
                    P[a] = P[a] + push
                    P[c] = P[c] - push
                    moved = True
            nr = np.linalg.norm(P[a])
            if nr > rmax:
                P[a] = P[a] * rmax / nr
        if not moved:
            break
    return P


def fig6_network(A, E, scope, fname, pal, label_deg, min_sector=1, size=13):
    if scope == "제조94":
        e = E[E["borrower_scope"].isin(["제조94", "둘 다"])].copy()
        head = "CBAM 대상 제조사"
    else:
        e = E.copy()
        head = "고탄소 기업(배출권 할당대상 기업 + CBAM 대상 제조사)"
    if e.empty:
        print(f"  ({head} 연결이 없어 {fname}을 건너뜀)")
        return
    e = e.drop_duplicates(["lender", "borrower"])
    deg_b = e.groupby("borrower")["lender"].nunique()
    deg_l = e.groupby("lender")["borrower"].nunique()
    sec_of = e.groupby("borrower")["sector"].first()
    small = sec_of.value_counts()[lambda v: v < min_sector].index        # 작은 업종은 "기타 업종"으로 합침
    sec_of = sec_of.where(~sec_of.isin(small), OTHER)
    eu = e.groupby("borrower")["eu_confirmed"].max()
    sec_order = [x for x in sec_of.value_counts().index if x != OTHER] + ([OTHER] if OTHER in set(sec_of) else [])
    borrowers = deg_b.index.tolist()
    lenders = [a for a in A.sort_values("exposure_order")["account"] if a in deg_l.index]
    pos, wedge = layout(borrowers, sec_of, deg_b, sec_order)

    fig, ax = plt.subplots(figsize=(size, size))
    lim = 1.75
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")
    pt = (fig.get_size_inches()[0] * 72 * 0.80) / (2 * lim)          # 1 단위 ≈ pt
    smax = deg_l.max()
    s_l = {a: 90 + 1900 * deg_l[a] / smax for a in lenders}
    r_l = {a: np.sqrt(s_l[a] / np.pi) / pt for a in lenders}
    nbrs = {a: e.loc[e["lender"] == a, "borrower"].tolist() for a in lenders}
    inside = {a for a in lenders if deg_l[a] >= 17}                     # 큰 원은 이름을 안에
    fs = 8
    eff = {a: r_l[a] if a in inside else max(r_l[a], (len(short(a)) + 3) * fs * 0.55 / pt / 2) + 0.03
           for a in lenders}                                            # 밀어낼 때 이름 길이까지 포함
    P = place_lenders(lenders, nbrs, pos, eff)

    for _, r in e.iterrows():                                          # 선 — 차주 업종 색, 옅게
        p, q = P[r["lender"]], pos[r["borrower"]]
        ax.plot([p[0], q[0]], [p[1], q[1]], color=pal[sec_of[r["borrower"]]], alpha=0.22, lw=0.6, zorder=1)
    for b_ in borrowers:                                               # 차주 원 — 크기 = 거래 금융회사 수
        is_eu = eu[b_] == "Y"
        ax.scatter(*pos[b_], s=18 + 38 * deg_b[b_], color=pal[sec_of[b_]], zorder=3,
                   edgecolor=EU_RED if is_eu else "white", linewidth=1.8 if is_eu else 0.5)
        if is_eu or deg_b[b_] >= label_deg:
            ang = np.degrees(np.arctan2(pos[b_][1], pos[b_][0]))
            out = pos[b_] / np.linalg.norm(pos[b_]) * (wedge[sec_of[b_]][3] + 0.06)   # 구역 맨 바깥 겹 밖에서 시작
            right = -90 <= ang <= 90
            ax.text(out[0], out[1], f"{short(b_)} {deg_b[b_]}", fontsize=7, rotation=ang if right else ang - 180,
                    rotation_mode="anchor", ha="left" if right else "right", va="center",
                    color=EU_RED if is_eu else "#333", fontweight="bold" if is_eu else "normal", zorder=5)
    for sct, (a1, a2, n, rr) in wedge.items():                         # 업종 이름 — 구역 바깥
        mid = (a1 + a2) / 2
        rad = rr + 0.50
        ax.text(rad * np.cos(mid), rad * np.sin(mid), f"{sct}\n{n}곳", ha="center", va="center", fontsize=10,
                color=pal[sct], fontweight="bold", zorder=6)
    for a in lenders[::-1]:                                            # 금융회사 원 — 큰 것이 위
        t = A.loc[A["account"] == a, "lender_type"].iloc[0]
        ax.scatter(*P[a], s=s_l[a], color="#3A3A3A" if t == "은행" else TYPE_COLOR.get(t, "#777"),
                   edgecolor="white", linewidth=1.2, zorder=7)
        if a in inside:
            ax.text(P[a][0], P[a][1], f"{short(a)}\n{deg_l[a]}", ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold", zorder=8, linespacing=1.1)
        else:
            ax.text(P[a][0], P[a][1] + r_l[a] + 0.02, f"{short(a)} {deg_l[a]}", ha="center", va="bottom", fontsize=fs,
                    zorder=8, path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
    hs = [Line2D([], [], marker="o", ls="", color=pal[sct], markersize=8, label=f"{sct} ({int((sec_of == sct).sum())})")
          for sct in sec_order]
    hs += [Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=EU_RED, markeredgewidth=2,
                  markersize=8, label="EU 수출 확인")]
    types = sorted({A.loc[A["account"] == a, "lender_type"].iloc[0] for a in lenders})
    hs += [Line2D([], [], marker="o", ls="", color="#3A3A3A" if t == "은행" else TYPE_COLOR.get(t, "#777"),
                  markersize=10, label=f"금융회사({t})") for t in types]
    ax.legend(handles=hs, loc="upper left", bbox_to_anchor=(1.0, 0.95), fontsize=9, frameon=False, title="범례")
    ax.set_title(f"{head} {len(borrowers)}곳 – 금융회사 {len(lenders)}곳 거래 연결망 (원 크기: 연결 수, 색상: 업종)\n"
                 f"(직접 대출 거래 기준 · 기업명 표시: EU 수출 확인 또는 거래 금융회사 {label_deg}곳 이상)", fontsize=13, pad=10)
    save(fig, fname)


def fig8_coverage(E):
    """결론 — 신규 포괄 제조사가 많은 금융회사부터 누적할 때의 포괄률"""
    e = E[E["borrower_scope"].isin(["제조94", "둘 다"])]
    if e.empty:
        return
    total, eu_all = 94, set(e.loc[e["eu_confirmed"] == "Y", "borrower"])
    v = PROC / "mfg2_verdict.csv"
    if v.exists():
        m = pd.read_csv(v, dtype=str).fillna("")
        total = len(m)
        eu_n = int((m.get("cbam_eu_exposure", "") == "확인").sum())
    else:
        eu_n = len(eu_all)
    sets = {a: set(g["borrower"]) for a, g in e.groupby("lender")}
    got, rows = set(), []
    while sets:
        a = max(sets, key=lambda k: (len(sets[k] - got), len(sets[k])))
        if not sets[a] - got:
            break
        got |= sets.pop(a)
        rows.append((short(a), len(got) / total * 100, len(got & eu_all) / max(eu_n, 1) * 100, len(got)))
    d = pd.DataFrame(rows, columns=["금융회사", "제조", "EU", "곳"])
    x = np.arange(1, len(d) + 1)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(x, d["제조"], marker="o", color="#2B4C7E", label=f"CBAM 대상 제조사 {total}곳 대비 누적 포괄률")
    ax.plot(x, d["EU"], marker="o", color=EU_RED, label=f"EU 수출 확인 제조사 {eu_n}곳 대비 누적 포괄률")
    for i in range(min(5, len(d))):                                    # 위에 있는 선의 숫자는 위, 아래 선은 아래
        up_eu = d["EU"][i] >= d["제조"][i]
        ax.text(x[i], d["EU"][i] + (3 if up_eu else -6), f"{d['EU'][i]:.0f}%", ha="center", fontsize=8.5, color=EU_RED)
        ax.text(x[i], d["제조"][i] + (-6 if up_eu else 3), f"{d['제조'][i]:.0f}%", ha="center", fontsize=8.5,
                color="#2B4C7E")
    allc = len(set(e["borrower"])) / total * 100
    ax.axhline(allc, color="#999", ls=":", lw=1)
    ax.text(len(d), allc + 1.5, f"조사 대상 금융회사에서 직접 차입한 제조사 전체 {len(set(e['borrower']))}곳 ({allc:.0f}%)",
            ha="right", fontsize=8.5, color="#666")
    ax.set_xticks(x, [f"+{n}" for n in d["금융회사"]], rotation=45, ha="right", fontsize=8.5)
    ax.set_ylim(0, 108)
    ax.set_ylabel("누적 포괄률 (%)")
    ax.set_xlabel("추가 금융회사 (신규 포괄 제조사 수 순 · 점수 순위와 무관)")
    ax.set_title("금융회사 수에 따른 CBAM 대상 제조사 거래 포괄률\n"
                 "(누적 포괄률: 선택한 금융회사 중 한 곳 이상과 직접 대출 거래가 있는 제조사 비율)", fontsize=12, pad=10)
    ax.legend(loc="lower right")
    save(fig, "fin_fig8_coverage.png")


def fig7_layers(A):
    d = A[(A["n33"] + A["n32"]) > 0].copy()
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9, 0.36 * len(d) + 1.8))
    for i, (a, b) in enumerate(zip(d["n33"], d["n32"])):
        ax.plot([a, b], [i, i], color="#CCC", lw=2, zorder=1)
    ax.scatter(d["n33"], y, color="#4C72B0", s=40, zorder=2, label="CBAM 대상 제조사(94곳) 중 거래 기업 수")
    ax.scatter(d["n32"], y, color="#DD8452", s=40, zorder=2, label="고탄소 기업 중 거래 기업 수")
    ax.axvline(T33_HIGH, color="#4C72B0", ls=":", lw=1)
    ax.axvline(T32_HIGH, color="#DD8452", ls=":", lw=1)
    ax.text(T33_HIGH + 0.5, -1.45, f"CBAM 대상 제조사 점수 2점 기준선 ({T33_HIGH}곳)", fontsize=8, color="#4C72B0",
            va="center")                                               # 기준선 설명은 맨 위 — 범례와 겹치지 않게
    ax.text(T32_HIGH + 0.5, -0.75, f"고탄소 기업 점수 2점 기준선 ({T32_HIGH}곳)", fontsize=8, color="#DD8452", va="center")
    ax.set_yticks(y, d["name"])
    for lab, t, a in zip(ax.get_yticklabels(), d["lender_type"], d["n33"]):
        lab.set_color(TYPE_COLOR.get(t, "#444"))
        if a == 0:
            lab.set_fontweight("bold")
    ax.set_ylim(len(d) - 0.3, -2.0)                                   # 위쪽 여백에 기준선 설명 (아래로 갈수록 순위가 낮음)
    ax.set_xlabel("거래 기업 수")
    only32 = int(((d["n33"] == 0) & (d["n32"] > 0)).sum())
    ax.set_title(f"금융회사별 거래 기업 수 비교 — CBAM 대상 제조사 vs 고탄소 기업\n"
                 f"(고탄소 기업: 배출권 할당대상 기업 + CBAM 대상 제조사 · 굵은 글씨: 고탄소 기업에서만 거래가 확인된 금융회사 {only32}곳)",
                 fontsize=12, pad=12)
    ax.legend(loc="lower right")
    save(fig, "fin_fig7_layers.png")


def main():
    set_font()
    A, E = load()
    print(f"금융회사 {len(A)}곳 · 연결 {len(E)}쌍")
    fig4_eu_share(A)
    fig5_heatmap(A, E)
    pal = sector_palette(E)
    fig6_network(A, E, "제조94", "fin_fig6_mfg_network.png", pal, label_deg=4)
    fig6_network(A, E, "전체", "fin_fig6b_all_network.png", pal, label_deg=6, min_sector=3, size=15)
    fig7_layers(A)
    fig8_coverage(E)
    print(f"\n그림 → {FIG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
