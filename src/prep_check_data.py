"""준비-2c 자료 점검표

data/raw, data/external 아래 CSV·엑셀 파일의 인코딩, 머리글 위치, 행·열 수, 앞쪽 열 이름,
파일 해시를 확인해 data/README.md의 '자료 점검표' 부분에 기록함
"""
from pathlib import Path
import datetime as dt
import hashlib

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
README = DATA / "README.md"
SCAN_DIRS = [DATA / "raw", DATA / "external"]
SUFFIXES = {".csv", ".xlsx", ".xls"}

# 이미 알고 있는 행 수 (다르면 '다름'으로 표시)
EXPECTED_ROWS = {
    "target_firms.csv": 73,
    "step1_unlisted_final.csv": 32,
    "step1_firm_types_final.csv": 73,
    "mfg_final_reviewed.csv": 1610,
    "it_spend_matched.csv": 1610,
    "steel_15min_clean.csv": 35040,
    "한국산업단지공단_전국등록공장현황_등록공장현황자료_20241231.csv": 217048,
}


def sha12(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def clean(text):
    return str(text).replace("|", "/").replace("\n", " ").strip()


def check_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"인코딩 판별 실패: {path.name}")
    if enc == "cp949":
        label = "CP949"
    else:
        with open(path, "rb") as f:
            label = "UTF-8 (BOM)" if f.read(3) == b"\xef\xbb\xbf" else "UTF-8"
    return [{
        "시트": "-",
        "인코딩": label,
        "머리글 행": 1,
        "행 수": len(df),
        "열 수": df.shape[1],
        "앞쪽 열": [clean(c) for c in df.columns[:6]],
    }]


def check_excel(path):
    results = []
    for sheet in pd.ExcelFile(path).sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
        filled = raw.notna().sum(axis=1)
        if raw.empty or filled.max() == 0:
            results.append({"시트": sheet, "인코딩": "엑셀", "머리글 행": "-", "행 수": 0, "열 수": 0, "앞쪽 열": []})
            continue
        # 값이 가장 많이 찬 줄의 절반 이상 찬 첫 줄을 머리글로 봄 (자동 판별)
        header_pos = int((filled >= filled.max() * 0.5).to_numpy().argmax())
        header = [clean(v) for v in raw.iloc[header_pos].dropna().tolist()]
        body = raw.iloc[header_pos + 1:].dropna(how="all")
        results.append({
            "시트": sheet,
            "인코딩": "엑셀",
            "머리글 행": header_pos + 1,
            "행 수": len(body),
            "열 수": len(header),
            "앞쪽 열": header[:6],
        })
    return results


def main():
    today = dt.date.today().isoformat()
    rows = []
    for base in SCAN_DIRS:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            checks = check_csv(path) if path.suffix.lower() == ".csv" else check_excel(path)
            for c in checks:
                expected = EXPECTED_ROWS.get(path.name)
                if expected is None:
                    verdict = "-"
                elif expected == c["행 수"]:
                    verdict = "일치"
                else:
                    verdict = f"다름 (예상 {expected})"
                rows.append([
                    path.relative_to(DATA).as_posix(), clean(c["시트"]), c["인코딩"], str(c["머리글 행"]),
                    f'{c["행 수"]:,}', str(c["열 수"]), verdict, ", ".join(c["앞쪽 열"]), sha12(path),
                ])

    lines = [
        f"## 자료 점검표 ({today})",
        "",
        "- 엑셀의 머리글 행은 자동 판별값임 (값이 가장 많이 찬 줄의 절반 이상 찬 첫 줄)",
        "- 해시는 SHA-256 앞 12자리이며, 파일이 바뀌었는지 확인할 때 씀",
        "",
        "| 파일 | 시트 | 인코딩 | 머리글 행 | 행 수 | 열 수 | 행 수 확인 | 앞쪽 열 이름 | 해시 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines += ["| " + " | ".join(r) + " |" for r in rows]

    text = README.read_text(encoding="utf-8")
    marker = "## 자료 점검표"
    if marker in text:
        text = text[: text.index(marker)]
    text = text.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print("\n".join(lines))
    print(f"\n[완료] data/README.md에 자료 점검표 기록 ({len(rows)}행)")


if __name__ == "__main__":
    main()