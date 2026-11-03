"""
파이프라인 오케스트레이터.

흐름:  보유종목 메타 → 주가(시세) + 공시 수집 → 신규 공시만 필터
       → 요약(Claude) → 데일리 브리핑 렌더링 → 전송(메일/카톡) → 기록

강의의 '로그인→데이터수집→전략실행→주문' 구조에서
'전략실행→주문' 자리를 '요약→알림' 으로 바꾼 안전 버전.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from src import dart_client, store, summarizer, notifier, price_client, news_client


def run():
    print(f"▶ 종목 에이전트 실행 (MOCK={config.MOCK_MODE})")
    store.init_db()

    print("1) 보유종목 + 시세 조회…")
    holdings_meta = dart_client.get_holdings_meta()
    quotes = price_client.get_quotes(holdings_meta)
    print(f"   {len(holdings_meta)}종목 시세 확보")

    print("2) 종목 뉴스 조회…")
    news = news_client.get_news_all(holdings_meta)
    print(f"   뉴스 {sum(len(v) for v in news.values())}건" if news else "   뉴스 비활성")

    print("3) DART 공시 수집…")
    raw = dart_client.get_recent_disclosures()
    print(f"   총 {len(raw)}건 수집")

    print("4) 신규 공시 필터…")
    new_items = store.filter_new(raw)
    print(f"   신규 {len(new_items)}건")

    results = []
    if new_items:
        print("5) Claude 요약…")
        results = summarizer.summarize_all(new_items)
    else:
        print("5) 신규 공시 없음 — 요약 건너뜀")

    print("6) 브리핑 렌더링 & 전송…")
    subject, body = notifier.render(results, quotes=quotes,
                                    holdings_meta=holdings_meta, news=news)
    print("\n" + body + "\n")
    notifier.send_email(subject, body)
    notifier.send_kakao(body)

    if new_items:
        store.mark_sent(new_items)
    print("✔ 완료")


if __name__ == "__main__":
    run()
