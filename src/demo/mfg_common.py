"""09 제조 시연 공통 함수 (클로드 코드 1회차)

0.001 반올림(r3)·소수 반올림(rq)·정수 반올림(r0)·최대 나머지 배분(lr)·CSV 읽기(read_csv)·쓰기(write_csv)·실행 날짜(today_str)
규칙은 docs/progress/09_demo_mfg.md 4-8-3·4-8-4
"""
import csv
import datetime
import math
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "demo" / "mfg" / "db"
EXT = ROOT / "data" / "demo" / "mfg" / "ext"

# 목록 순서 (09 4-8-4) — lr 동점 순서와 행 순서를 고정함
PLANTS = ["KG_DJ", "KG_IC", "TW_HJ", "TW_NS", "HBG_CW", "HBG_GJ", "HBG_SA",
          "SA_PS", "HI_CEM", "HI_SEC"]
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
VERSION = "v1 (09 C-014)"
UNIT = Fraction(1, 1000)


def r3(x):
    """0.001 단위 반올림 (0.0005는 0에서 먼 쪽)"""
    return rq(x, 3)


def rq(x, n):
    """소수 n자리 반올림 (5는 0에서 먼 쪽)"""
    x = Fraction(x)
    scale = Fraction(10) ** n
    q = Fraction(math.floor(abs(x) * scale + Fraction(1, 2))) / scale
    return -q if x < 0 else q


def r0(x):
    """정수 반올림 (0.5는 올림)"""
    return rq(x, 0)


def lr(total, weights, unit=UNIT):
    """최대 나머지 배분 — 나눈 값의 합 = 총량"""
    unit = Fraction(unit)
    n = Fraction(total) / unit
    if n.denominator != 1:
        raise ValueError(f"lr: 총량 {total}이 단위 {unit}의 정수배가 아님 — 멈춤 (09 4-8-4)")
    n = int(n)
    w = [Fraction(v) for v in weights]
    sw = sum(w)
    exact = [n * v / sw for v in w]
    base = [math.floor(e) for e in exact]
    # 남은 몫을 소수 부분이 큰 순서로 1씩 줌, 같으면 목록 앞쪽 먼저
    order = sorted(range(len(w)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:n - sum(base)]:
        base[i] += 1
    return [Fraction(b) * unit for b in base]


def read_csv(path):
    """UTF-8 BOM CSV를 읽어 행 목록으로 돌려줌"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, columns, rows, decimals=None):
    r"""칸 순서대로 UTF-8 BOM CSV를 씀 (줄 끝 \n)

    - 값: None = 빈 값, str·int = 그대로, Fraction = decimals[칸](기본 3)자리 고정 소수
    - 숫자 쓰기 규칙은 09 4-8-3
    """
    decimals = decimals or {}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for row in rows:
            out = []
            for c in columns:
                v = row[c]
                if v is None:
                    out.append("")
                elif isinstance(v, Fraction):
                    n = decimals.get(c, 3)
                    i = int(rq(v, n) * 10 ** n)
                    s = str(abs(i)).rjust(n + 1, "0")
                    s = s[:-n] + "." + s[-n:] if n else s
                    out.append(("-" if i < 0 else "") + s)
                else:
                    out.append(str(v))
            w.writerow(out)


def today_str():
    """실행 날짜 YYYY-MM-DD"""
    return datetime.date.today().isoformat()
