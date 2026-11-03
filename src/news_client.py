"""
뉴스 모듈 (네이버 검색 API).

종목명으로 최근 뉴스를 검색해 제목·링크·날짜를 가져옵니다.
키 발급(무료): https://developers.naver.com → 애플리케이션 등록 → 검색 API
  → .env 에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 입력

설계 원칙(주가 모듈과 동일): 실패해도 예외로 전체를 죽이지 않고 빈 리스트 반환.
뉴스가 없거나 키가 없으면 브리핑에서 뉴스 줄만 빠질 뿐, 시세·공시는 그대로 나갑니다.
"""
from __future__ import annotations

import re
import html
import time

import requests

import config

_NAVER_URL = "https://openapi.naver.com/v1/search/news.json"


def _strip(text: str) -> str:
    """네이버가 주는 <b>태그·엔티티 제거."""
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return html.unescape(text).strip()


def get_news(corp_name: str, count: int | None = None) -> list[dict]:
    """종목 1개 → [{title, link, date}] (최신순, 최대 count건)."""
    count = count or config.NEWS_PER_STOCK
    if config.MOCK_MODE or not (config.NAVER_CLIENT_ID and config.NAVER_CLIENT_SECRET):
        return _mock_news(corp_name, count)
    try:
        resp = requests.get(
            _NAVER_URL,
            headers={
                "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
            },
            params={"query": corp_name, "display": count, "sort": "date"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        out = []
        for it in items[:count]:
            out.append({
                "title": _strip(it.get("title", "")),
                "link": it.get("originallink") or it.get("link", ""),
                "date": (it.get("pubDate", "")[:16]),   # 'Mon, 30 Jun 2026'
            })
        return out
    except Exception as e:
        print(f"  ⚠️  뉴스 조회 실패({corp_name}): {e}")
        return []


def get_news_all(holdings_meta: list[dict]) -> dict[str, list[dict]]:
    """보유종목 전체 → {회사명: [뉴스…]}."""
    if not config.NEWS_ENABLED:
        return {}
    out = {}
    for m in holdings_meta:
        out[m["corp_name"]] = get_news(m["corp_name"])
        if not config.MOCK_MODE:
            time.sleep(0.2)
    return out


# ──────────────────────────────────────────────────────────────
# MOCK: 키 없이 시험용
# ──────────────────────────────────────────────────────────────
def _mock_news(corp_name: str, count: int) -> list[dict]:
    base = [
        {"title": f"{corp_name}, 2분기 실적 시장 기대치 상회", "link": "https://example.com/1", "date": "Mon, 30 Jun 2026"},
        {"title": f"{corp_name} 신규 수주 소식에 주가 강세", "link": "https://example.com/2", "date": "Mon, 30 Jun 2026"},
        {"title": f"증권가 '{corp_name}' 목표주가 상향", "link": "https://example.com/3", "date": "Sun, 29 Jun 2026"},
    ]
    return base[:count]
