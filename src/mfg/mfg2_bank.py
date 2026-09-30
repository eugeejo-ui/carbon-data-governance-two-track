"""제조2-6 은행 차입 표시 (점수 아님)

- 입력: data/processed/mfg2_rank.csv (합계 상위), data/manual/eu_check_rcept.csv (보고서 번호 보완)
- 합계 상위 계정의 공시 원문에서 차입금 주석을 찾아 차입처와 차입금 규모를 뽑음
- 판정은 하지 않음. 뽑힌 문장을 보고 사용자가 정리함
- 출력
  - data/processed/bank_scan/<계정>.txt : 계정별 차입 관련 문장
  - data/manual/mfg_bank_borrowing.csv : 손으로 채울 표 (계정·주요 차입처·차입금·기준일·출처)
"""
from html import unescape
from pathlib import Path
import re
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dart_api import document_zip, get_json  # noqa: E402

PROC = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
OUTDIR = PROC / "bank_scan"
OUT_CSV = MANUAL / "mfg_bank_borrowing.csv"

MIN_TOTAL = 7             # 합계 7점 이상을 대상으로 함 (점수 구간에서 끊음)
BEFORE, AFTER = 60, 900   # 키워드 앞뒤 글자 수 (차입금 표가 길어 넉넉히 잡음)

BANKS = ("산업은행|기업은행|수출입은행|국민은행|KB국민|신한은행|우리은행|하나은행|KEB하나|농협은행|"
         "NH농협|씨티은행|SC제일|부산은행|대구은행|경남은행|광주은행|전북은행|제주은행|iM뱅크|"
         "수협은행|새마을금고|신협|저축은행|캐피탈|산은|중소기업은행")
KEYWORDS = re.compile(r"단기차입금|장기차입금|차입금의 내역|차입처|사채|"
                      r"담보로 제공|지급보증|" + BANKS)
STOP = re.compile(r"차입처|차입금|은행|이자율|담보|보증|사채|만기|액면")


def key(name):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", str(name))
    return re.sub(r"\s", "", s)


def clean(raw):
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def snippets(zip_path):
    out, seen = [], set()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            b = z.read(member)
            for enc in ("utf-8", "cp949"):
                try:
                    raw = b.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raw = b.decode("utf-8", errors="ignore")
            text = clean(raw)
            covered = -1
            for m in KEYWORDS.finditer(text):
                if m.start() <= covered:
                    continue
                s = text[max(0, m.start() - BEFORE): m.end() + AFTER]
                covered = m.end() + AFTER
                k = re.sub(r"\s", "", s)[:40]
                if k in seen:
                    continue
                seen.add(k)
                # 은행 이름이나 차입 관련 단어가 2개 이상 들어간 조각만 남김
                if len(STOP.findall(s)) >= 2:
                    out.append(s)
    return out


def alt_rcepts(corp_code):
    """같은 해의 사업·감사보고서 접수번호 목록 (정정본 포함). 원문이 없을 때 차례로 씀"""
    if not corp_code:
        return []
    out = []
    for ty in ("A", "F"):
        hit = get_json("list", corp_code=corp_code, bgn_de="20260101",
                       end_de="20261231", pblntf_ty=ty, page_count="100")
        for row in hit.get("list", []) or []:
            if "사업보고서" in row.get("report_nm", "") or "감사보고서" in row.get("report_nm", ""):
                out.append(row["rcept_no"])
    return out


def main():
    rank = pd.read_csv(PROC / "mfg2_rank.csv", dtype=str).fillna("")
    rank["total_n"] = pd.to_numeric(rank["total"], errors="coerce").fillna(0)
    top = rank[rank["total_n"] >= MIN_TOTAL]
    rc = pd.read_csv(MANUAL / "eu_check_rcept.csv", dtype=str).fillna("") \
        if (MANUAL / "eu_check_rcept.csv").exists() else pd.DataFrame(columns=["account", "rcept_no"])
    rcept_map = {key(a): n for a, n in zip(rc["account"], rc["rcept_no"]) if n}
    base = pd.read_csv(PROC / "mfg2_base.csv", dtype=str).fillna("")
    code_map = {key(a): c for a, c in zip(base["account"], base["corp_code"]) if c}

    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows, fails = [], []
    for i, r in enumerate(top.to_dict("records"), 1):
        acc = r["account"]
        print(f"[{i}/{len(top)}] {acc}")
        k = key(acc)
        no = rcept_map.get(k, "")
        if not no and code_map.get(k):
            # A는 정기공시(사업보고서), F는 외부감사 관련(감사보고서)
            for ty in ("A", "F"):
                hit = get_json("list", corp_code=code_map[k], bgn_de="20260101",
                               end_de="20261231", pblntf_ty=ty, page_count="100")
                for row in hit.get("list", []) or []:
                    if "사업보고서" in row.get("report_nm", "") or "감사보고서" in row.get("report_nm", ""):
                        no = row["rcept_no"]
                        break
                if no:
                    break
        if not no:
            fails.append((acc, "보고서 번호 없음"))
            print("    건너뜀: 보고서 번호 없음")
            continue
        snips, used, last = None, no, ""
        for cand in [no] + [x for x in alt_rcepts(code_map.get(k, "")) if x != no]:
            try:
                snips = snippets(document_zip(cand))
                used = cand
                break
            except Exception as e:  # noqa: BLE001
                last = str(e)[:120]
        if snips is None:
            fails.append((acc, last))
            print(f"    실패: {last}")
            continue
        no = used
        name = re.sub(r"[\\/:*?\"<>|()]", "", acc)
        (OUTDIR / f"{name}.txt").write_text(
            f"# {acc} rcept_no={no}\nhttps://dart.fss.or.kr/dsaf001/main.do?rcpNo={no}\n\n"
            + "\n\n- ".join([""] + snips), encoding="utf-8")
        rows.append(dict(account=acc, rank=r["rank"], total=r["total"], rcept_no=no,
                         main_banks="", borrowing_eok="", basis_date="", note="",
                         source=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={no}"))
        print(f"    저장: {name}.txt ({len(snips)}조각)")

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"\n완료 {len(rows)} · 실패 {len(fails)}")
    print(f"조각: {OUTDIR.relative_to(ROOT)} · 빈 표: {OUT_CSV.relative_to(ROOT)}")
    for a, m in fails:
        print(f"  실패 {a}: {m}")


if __name__ == "__main__":
    main()