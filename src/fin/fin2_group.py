"""금융2-0 보고 단위 — 278곳 각각의 금융배출량을 실제로 공시하는 "대표 회사"를 정함

- 금융배출량은 금융지주가 그룹 연결로 공시하므로 ②(현재 빈칸)·③-2(고탄소 노출)는 대표 회사 값으로 잼
  (계획서 9-5 "종속회사는 그룹 값 적용", 2026-10-01 결정: 소유 관계로 묶음 — 거래 관계와 무관)
- 묶는 근거는 금융-1에서 이미 정한 지배 관계(fin_list.csv의 parent)를 씀
  - 비상장 종속 → 지배회사(1-1) / 손자회사 → 지배회사를 따라 맨 위 / 공공기관 종속 → 산업은행
  - 명단 밖 코스피 모회사의 종속 → 자기 자신 (모회사가 제조사·일반 지주라 금융배출량을 내지 않음)
  - 상장·공공금융기관 → 자기 자신 / 독립·외국계 → 최대주주가 명단 안에 있으면 그 회사(애큐온저축은행)
- 대기업집단 비상장(1-3A) 21곳은 공정위 자료에 기업집단만 있고 지배회사가 없어 여기서 확인함
  - DART 고유번호: 이름으로 찾고 법인등록번호로 같은 회사인지 확인
  - 최대주주: DART 최대주주 현황(사업보고서) → 없으면 감사보고서 원문 (fin1_owner·fin1_audit와 같은 방식, 1등급)
  - 최대주주가 명단 안의 회사이고 지분 50% 초과면 그 회사를 지배회사로 봄
- 점검: 1-3A인데 최대주주가 코스피 상장사이고 50% 초과면 "1-2b로 옮길지 확인"으로 표시
  (금융1-2b는 코스피 지배회사의 출자현황으로 찾았으므로 원래 거기서 잡혔어야 함)
- 대표 회사 보고서에 해당 회사가 실제로 포함되는지는 ② 조사 때 보고 범위로 다시 확인함

출력
  - data/processed/fin_groups.csv : 278곳의 대표 회사·지배회사·근거
  - data/processed/fin_unlisted_owners.csv : 1-3A 21곳 최대주주 확인 결과
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from dart_api import corp_codes, get_json  # noqa: E402
from fin.fin1_list import key, name2, to_f  # noqa: E402
from fin.fin1_owner import owners_api  # noqa: E402
from fin.fin1_audit import audit_owner  # noqa: E402

PROC = ROOT / "data" / "processed"
LIST = PROC / "fin_list.csv"
OUT = PROC / "fin_groups.csv"
OUT_OWN = PROC / "fin_unlisted_owners.csv"
CONTROL = 50.0


def name_index(cc):
    """DART 고유번호 목록을 한 번만 변환해 둠 — (법인 표기 뗀 이름 → 번호들), (음역 이름 → 번호들)"""
    by_key, by_n2 = {}, {}
    for c, n in zip(cc["corp_code"], cc["corp_name"]):
        by_key.setdefault(key(n), []).append(c)
        by_n2.setdefault(name2(n), []).append(c)
    return {key: by_key, name2: by_n2}


def corp_for(name, jurir, idx):
    """1-3A 계정의 DART 고유번호 — 이름(법인 표기 제거 → 음역 변환)으로 후보를 찾고 법인등록번호로 확인"""
    j = str(jurir).replace("-", "")
    for f in (key, name2):
        cands = idx[f].get(f(name), [])
        for c in cands:
            try:
                d = get_json("company", corp_code=c)
            except Exception:  # noqa: BLE001
                continue
            if d.get("status") == "000" and (not j or str(d.get("jurir_no", "")).replace("-", "") == j):
                return c, "이름+법인등록번호 일치" if j else "이름 일치"
        if len(cands) == 1 and not j:
            return cands[0], "이름 일치"
    # 앞에 "NH"처럼 다른 말이 붙은 DART 이름 (농협손해보험 ↔ NH농협손해보험) — 법인등록번호로만 확정
    k = key(name)
    near = [c for kk, cs in idx[key].items() if len(k) >= 4 and kk != k and kk.endswith(k) for c in cs][:10]
    for c in near:
        try:
            d = get_json("company", corp_code=c)
        except Exception:  # noqa: BLE001
            continue
        if j and d.get("status") == "000" and str(d.get("jurir_no", "")).replace("-", "") == j:
            return c, "이름 끝부분+법인등록번호 일치"
    return "", "DART에서 못 찾음"


def unlisted_owners(f, cc):
    """1-3A 21곳의 최대주주 — 최대주주 현황 → 감사보고서 원문 (처음 조회하는 회사라 DART 호출로 몇 분 걸릴 수 있음)"""
    rows = []
    idx = name_index(cc)
    targets = f[f["layer"] == "비상장 비종속(대기업집단)"].to_dict("records")
    for i, r in enumerate(targets, 1):
        print(f"  [{i}/{len(targets)}] {r['account']} — 고유번호·최대주주 조회", flush=True)
        code, how = corp_for(r["account"], r["jurir_no"], idx)
        owner, rate, basis, status = "", None, "", how
        if code:
            o, rt, top3, per, st = owners_api(code)
            if st == "ok":
                owner, rate, basis, status = o, rt, f"DART 최대주주 현황({per}) — {top3}", "ok"
            else:
                print("      사업보고서 없음 → 감사보고서 원문 조회", flush=True)
                au = audit_owner(code)
                if au["owner"]:
                    owner, rate = au["owner"], au["rate"]
                    basis = f"감사보고서 원문({au['report']}, {au['rcept_no']})"
                    status = au["status"]
                else:
                    status = f"최대주주 못 찾음 — {au['status']}"
        rows.append(dict(account=r["account"], group=r["group"], corp_code=code, owner=owner,
                         owner_rate="" if rate is None else f"{rate:.2f}", basis=basis, status=status))
    return pd.DataFrame(rows, columns=["account", "group", "corp_code", "owner", "owner_rate", "basis", "status"])


def main():
    f = pd.read_csv(LIST, dtype=str).fillna("")
    cc = corp_codes()
    acc_by = {}
    for a in f["account"]:
        acc_by.setdefault(key(a), a)
        acc_by.setdefault(name2(a), a)
    find = lambda n: acc_by.get(key(n)) or acc_by.get(name2(n))  # noqa: E731

    print(f"대기업집단 비상장 {int((f['layer'] == '비상장 비종속(대기업집단)').sum())}곳 — 지배 관계 확인", flush=True)
    own = unlisted_owners(f, cc)
    # 감사보고서 문장에서 잡힌 이름이 길게 섞인 경우 — "지배기업/지배회사 ○○" 뒤 이름만 씀 (농협은행·NH저축은행)
    own["owner"] = own["owner"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    for i, r in own.iterrows():
        m = re.search(r"지배(?:기업|회사)\s*:?\s*([^\s,]+)", r["owner"])
        if m and (r["owner_rate"] == "" or len(r["owner"]) > 40):
            own.at[i, "owner"] = m.group(1)
            own.at[i, "basis"] = (r["basis"] + " — 원문의 '지배기업/지배회사' 표기").strip(" —")
            own.at[i, "status"] = "지배회사 확인(지분율 표기 없음)"
    own.to_csv(OUT_OWN, index=False, encoding="utf-8-sig")
    listed_keys = {key(n) for n, s in zip(cc["corp_name"], cc["stock_code"]) if str(s).strip()}

    # 지배회사 연결 (명단 안의 회사만)
    up, why = {}, {}
    for r in f.to_dict("records"):
        a, layer = r["account"], r["layer"]
        if layer in ("비상장 종속", "비상장 종속(손자회사)", "공공기관 종속") and find(r["parent"]):
            up[a], why[a] = find(r["parent"]), f"금융-1 지배회사({layer})"
        elif layer == "비상장 비종속(독립·외국계)" and r["owner"] and find(r["owner"]) and to_f(r["owner_rate"]) > CONTROL:
            up[a], why[a] = find(r["owner"]), "최대주주가 명단 안의 회사(1-3C 소유 구조)"
    flags = []
    for r in own.to_dict("records"):
        if r["owner"] and r["status"].startswith("지배회사 확인") and find(r["owner"]):
            up[r["account"]], why[r["account"]] = find(r["owner"]), "원문의 지배기업 표기(1-3A 확인)"
        elif r["owner"] and to_f(r["owner_rate"]) > CONTROL:
            if find(r["owner"]):
                up[r["account"]], why[r["account"]] = find(r["owner"]), "최대주주가 명단 안의 회사(1-3A 확인)"
            elif key(r["owner"]) in listed_keys:
                flags.append((r["account"], r["owner"], r["owner_rate"]))

    def top(a):
        seen = [a]
        while a in up and up[a] not in seen:
            a = up[a]
            seen.append(a)
        return a, len(seen) - 1

    layer_of = dict(zip(f["account"], f["layer"]))
    out = []
    for r in f.to_dict("records"):
        t, depth = top(r["account"])
        out.append(dict(account=r["account"], layer=r["layer"], report_unit=t, report_unit_layer=layer_of.get(t, ""),
                        depth=depth, link_basis=why.get(r["account"], "자기 자신"), direct_parent=up.get(r["account"], "")))
    g = pd.DataFrame(out)
    g.to_csv(OUT, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 120)
    units = g.groupby("report_unit").size().sort_values(ascending=False)
    print(f"{len(g)}곳 → 보고 단위 {len(units)}곳 → {OUT.relative_to(ROOT)}")
    print("\n[보고 단위의 층]")
    print(g.drop_duplicates("report_unit")["report_unit_layer"].value_counts().to_string())
    print("\n[묶인 곳이 2곳 이상인 보고 단위]")
    print(units[units > 1].to_string())
    print(f"\n[1-3A {len(own)}곳 최대주주] → {OUT_OWN.relative_to(ROOT)}")
    print(own[["account", "owner", "owner_rate", "status"]].to_string(index=False))
    if flags:
        print("\n[점검 — 1-3A인데 최대주주가 코스피 상장사이고 50% 초과: 1-2b로 옮길지 확인]")
        for a, o, rt in flags:
            print(f"  · {a} — {o} {rt}%")
    miss = own[~own["status"].isin(["ok"]) & (own["owner"] == "")]
    if len(miss):
        print("\n[최대주주를 못 찾은 곳 — 원문 확인 필요]")
        print(miss[["account", "corp_code", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()
