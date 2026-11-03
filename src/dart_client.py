"""
DART OpenAPI 클라이언트.

하는 일:
  1) 보유종목(종목명/종목코드) → DART corp_code 로 변환
     (DART 가 주는 corpCode.xml 매핑을 하루 캐싱)
  2) 각 종목의 최근 공시 목록(list.json) 조회

키가 없으면 MOCK_MODE 로 가짜 공시를 돌려줘서 파이프라인을 시험할 수 있습니다.
"""
from __future__ import annotations
import io
import time
import zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

import config

DART_BASE = "https://opendart.fss.or.kr/api"
CORP_CACHE = Path(__file__).parent.parent / "corpcode_cache.xml"
CORP_CACHE_TTL = 60 * 60 * 24  # 1일


# ──────────────────────────────────────────────────────────────
# corp_code 매핑
# ──────────────────────────────────────────────────────────────
def _download_corp_map() -> str:
    """DART 에서 corpCode.xml(zip) 을 받아 캐시에 저장."""
    url = f"{DART_BASE}/corpCode.xml"
    resp = requests.get(url, params={"crtfc_key": config.DART_API_KEY}, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    CORP_CACHE.write_bytes(xml_bytes)
    return xml_bytes.decode("utf-8")


def _load_corp_map() -> str:
    if CORP_CACHE.exists() and (time.time() - CORP_CACHE.stat().st_mtime) < CORP_CACHE_TTL:
        return CORP_CACHE.read_text(encoding="utf-8")
    return _download_corp_map()


def build_holding_corpcodes(holdings: list[str]) -> dict[str, str]:
    """
    보유종목 리스트 → {corp_code: 표시이름} dict.
    종목명 또는 6자리 종목코드 둘 다 매칭.
    """
    xml = _load_corp_map()
    root = ET.fromstring(xml)

    by_name, by_stock = {}, {}
    for item in root.iter("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        if not stock_code:  # 상장사만 (비상장은 stock_code 비어있음)
            continue
        by_name[corp_name.replace(" ", "").lower()] = (corp_code, corp_name)
        by_stock[stock_code] = (corp_code, corp_name)

    result = {}
    for h in holdings:
        key = h.strip()
        hit = by_stock.get(key) or by_name.get(key.replace(" ", "").lower())
        if hit:
            result[hit[0]] = hit[1]
        else:
            print(f"  ⚠️  매칭 실패: '{h}' — 종목명/코드를 확인하세요.")
    return result


def build_holding_meta(holdings: list[str]) -> list[dict]:
    """
    보유종목 → [{corp_code, corp_name, stock_code}] 리스트.
    공시(corp_code)와 주가(stock_code) 둘 다에 쓰려고 종목코드까지 포함.
    """
    xml = _load_corp_map()
    root = ET.fromstring(xml)

    by_name, by_stock = {}, {}
    for item in root.iter("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        if not stock_code:
            continue
        rec = {"corp_code": corp_code, "corp_name": corp_name, "stock_code": stock_code}
        by_name[corp_name.replace(" ", "").lower()] = rec
        by_stock[stock_code] = rec

    out = []
    for h in holdings:
        key = h.strip()
        hit = by_stock.get(key) or by_name.get(key.replace(" ", "").lower())
        if hit:
            out.append(hit)
        else:
            print(f"  ⚠️  매칭 실패: '{h}' — 종목명/코드를 확인하세요.")
    return out


def get_holdings_meta() -> list[dict]:
    """보유종목 메타(코드 포함). MOCK 이면 가짜 데이터."""
    if config.MOCK_MODE or not config.DART_API_KEY:
        return _mock_holdings_meta()
    return build_holding_meta(config.HOLDINGS)


# ──────────────────────────────────────────────────────────────
# 공시 목록 조회
# ──────────────────────────────────────────────────────────────
def fetch_disclosures(corp_code: str, corp_name: str, bgn_de: str, end_de: str) -> list[dict]:
    """한 종목의 [bgn_de, end_de] 기간 공시 목록."""
    params = {
        "crtfc_key": config.DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": 100,
    }
    resp = requests.get(f"{DART_BASE}/list.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":          # 013 = 데이터 없음 (정상)
        return []
    out = []
    for it in data.get("list", []):
        out.append({
            "rcept_no": it["rcept_no"],
            "corp_name": it.get("corp_name", corp_name),
            "report_nm": it.get("report_nm", ""),
            "rcept_dt": it.get("rcept_dt", ""),
            "flr_nm": it.get("flr_nm", ""),
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it['rcept_no']}",
        })
    return out


def get_recent_disclosures() -> list[dict]:
    """보유종목 전체의 최근 공시 목록(중복 제거 전)."""
    if config.MOCK_MODE or not config.DART_API_KEY:
        return _mock_disclosures()

    today = dt.date.today()
    bgn = (today - dt.timedelta(days=config.LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    meta = build_holding_meta(config.HOLDINGS)
    all_items = []
    for m in meta:
        corp_code, corp_name = m["corp_code"], m["corp_name"]
        try:
            items = fetch_disclosures(corp_code, corp_name, bgn, end)
            all_items.extend(items)
            print(f"  • {corp_name}: 공시 {len(items)}건")
        except Exception as e:
            print(f"  ⚠️  {corp_name} 조회 실패: {e}")
        time.sleep(0.3)  # DART 호출 간격 예의
    return all_items


# ──────────────────────────────────────────────────────────────
# MOCK: 키 없이 파이프라인 시험용 가짜 데이터
# ──────────────────────────────────────────────────────────────
def _mock_holdings_meta() -> list[dict]:
    return [
        {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930"},
        {"corp_code": "00164779", "corp_name": "SK하이닉스", "stock_code": "000660"},
        {"corp_code": "00266961", "corp_name": "NAVER", "stock_code": "035420"},
    ]


def _mock_disclosures() -> list[dict]:
    today = dt.date.today().strftime("%Y%m%d")
    return [
        {
            "rcept_no": "20260629000001",
            "corp_name": "삼성전자",
            "report_nm": "단일판매ㆍ공급계약체결",
            "rcept_dt": today,
            "flr_nm": "삼성전자",
            "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260629000001",
        },
        {
            "rcept_no": "20260629000002",
            "corp_name": "SK하이닉스",
            "report_nm": "유상증자결정",
            "rcept_dt": today,
            "flr_nm": "SK하이닉스",
            "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260629000002",
        },
        {
            "rcept_no": "20260629000003",
            "corp_name": "NAVER",
            "report_nm": "주요사항보고서(자기주식취득결정)",
            "rcept_dt": today,
            "flr_nm": "NAVER",
            "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260629000003",
        },
    ]
