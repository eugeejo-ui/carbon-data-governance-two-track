"""OpenDART 호출 도우미

- API 키는 .env의 DART_API_KEY에서 읽음
- 응답은 data/raw/dart/cache/에, 공시 원문 파일은 data/raw/dart/docs/에 저장하고
  다음부터는 저장본을 씀 (둘 다 GitHub 제외 폴더)
- status 000(정상)·013(자료 없음)만 저장하고, 그 밖의 오류는 멈춤
"""
from pathlib import Path
import json
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "dart" / "cache"
DOCS = ROOT / "data" / "raw" / "dart" / "docs"
BASE = "https://opendart.fss.or.kr/api"

load_dotenv(ROOT / ".env")
KEY = os.environ.get("DART_API_KEY", "")


def get_json(endpoint, **params):
    """endpoint 예: 'company', 'hyslrSttus', 'fnlttSinglAcnt', 'list'"""
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    path = CACHE / f"{endpoint}_{tag}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if not KEY:
        raise RuntimeError(".env에 DART_API_KEY가 없음")
    r = requests.get(f"{BASE}/{endpoint}.json", params={"crtfc_key": KEY, **params}, timeout=30)
    r.raise_for_status()
    data = r.json()
    status = data.get("status")
    if status not in ("000", "013"):
        raise RuntimeError(f"DART 오류 {status}: {data.get('message')} ({endpoint} {params})")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.2)
    return data


def corp_codes():
    """DART 고유번호 전체 목록 (corp_code, corp_name, stock_code, modify_date)"""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "corpCode.zip"
    if not path.exists():
        if not KEY:
            raise RuntimeError(".env에 DART_API_KEY가 없음")
        r = requests.get(f"{BASE}/corpCode.xml", params={"crtfc_key": KEY}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    rows = [{c.tag: (c.text or "").strip() for c in item} for item in root.iter("list")]
    return pd.DataFrame(rows)


def document_zip(rcept_no):
    """공시 원문 파일(zip) 경로. 없으면 받아서 저장함"""
    DOCS.mkdir(parents=True, exist_ok=True)
    path = DOCS / f"{rcept_no}.zip"
    if path.exists():
        return path
    if not KEY:
        raise RuntimeError(".env에 DART_API_KEY가 없음")
    r = requests.get(f"{BASE}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"PK"):
        msg = r.content[:300].decode("utf-8", errors="ignore")
        status = re.search(r"<status>(.*?)</status>", msg)
        raise RuntimeError(f"DART 원문 오류 {status.group(1) if status else ''}: {rcept_no} {msg}")
    path.write_bytes(r.content)
    time.sleep(0.5)
    return path