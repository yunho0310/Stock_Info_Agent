"""
주가 모듈 (FinanceDataReader).

종목코드 → 현재가 / 전일 대비 등락률 / 거래량.
키가 필요 없습니다 (라이브러리만 설치).  pip install finance-datareader

설계 원칙: 주가 조회가 실패해도(네트워크/휴장 등) 예외로 전체를 죽이지 않고
ok=False 만 돌려줍니다. 공시 브리핑은 그대로 나가야 하니까요.
"""
from __future__ import annotations

import time
import datetime as dt

import config


def get_quote(stock_code: str, corp_name: str = "") -> dict:
    """종목코드 1개 → 시세 dict."""
    if config.MOCK_MODE or not stock_code:
        return _mock_quote(stock_code, corp_name)
    try:
        import FinanceDataReader as fdr
        end = dt.date.today()
        start = end - dt.timedelta(days=10)        # 직전 거래일 확보용 여유
        df = fdr.DataReader(stock_code, start, end)
        if df is None or df.empty:
            return {"ok": False, "stock_code": stock_code}
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        price = float(last["Close"])
        prev_close = float(prev["Close"])
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        return {
            "ok": True,
            "stock_code": stock_code,
            "price": price,
            "change_pct": change_pct,
            "volume": int(last.get("Volume", 0) or 0),
        }
    except Exception as e:
        print(f"  ⚠️  주가 조회 실패({corp_name or stock_code}): {e}")
        return {"ok": False, "stock_code": stock_code}


def get_quotes(holdings_meta: list[dict]) -> dict[str, dict]:
    """보유종목 전체 → {회사명: 시세}."""
    out = {}
    for m in holdings_meta:
        out[m["corp_name"]] = get_quote(m["stock_code"], m["corp_name"])
        if not config.MOCK_MODE:
            time.sleep(0.2)   # 데이터 소스 호출 간격
    return out


# ──────────────────────────────────────────────────────────────
# MOCK: 키/네트워크 없이 시험용 (종목코드 기반 고정 난수)
# ──────────────────────────────────────────────────────────────
def _mock_quote(stock_code: str, corp_name: str) -> dict:
    import random
    random.seed((stock_code or corp_name) + "v1")
    return {
        "ok": True,
        "stock_code": stock_code,
        "price": random.randint(200, 9000) * 100,
        "change_pct": round(random.uniform(-3.5, 3.5), 2),
        "volume": random.randint(100_000, 9_000_000),
        "mock": True,
    }
