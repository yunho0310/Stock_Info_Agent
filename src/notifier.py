"""
리포트 렌더링 + 알림 전송.

- render(): 분석 결과 → 사람이 읽기 좋은 텍스트 브리핑
- send_email(): SMTP 로 메일 발송
- send_kakao(): 카카오톡 '나에게 보내기' (토큰 있을 때만)
"""
from __future__ import annotations
import datetime as dt
import smtplib
from email.mime.text import MIMEText

import requests

import config

TAG_EMOJI = {"호재": "🔵", "악재": "🔴", "중립": "⚪", "분석실패": "⚠️"}


def _fmt_quote(corp: str, q: dict | None) -> str:
    """한 종목의 시세 한 줄."""
    if not q or not q.get("ok"):
        return f"  • {corp}: 시세 조회 불가"
    chg = q.get("change_pct", 0.0)
    arrow = "📈" if chg > 0 else ("📉" if chg < 0 else "➖")
    sign = "+" if chg >= 0 else ""
    price = f"{int(q['price']):,}원"
    return f"  {arrow} {corp}: {price} ({sign}{chg:.2f}%)"


def render(results: list[dict],
           quotes: dict[str, dict] | None = None,
           holdings_meta: list[dict] | None = None,
           news: dict[str, list[dict]] | None = None) -> tuple[str, str]:
    """(제목, 본문) 반환.  results=신규 공시, quotes={회사명:시세}, news={회사명:[뉴스]}."""
    today = dt.date.today().strftime("%Y-%m-%d")
    subject = f"[{today}] 보유종목 데일리 브리핑"

    order = [m["corp_name"] for m in holdings_meta] if holdings_meta else None
    lines = [f"=== {subject} ==="]

    # ── 1) 주가 스냅샷 (모든 보유종목, 매일) ──
    if quotes:
        names = order or list(quotes)
        lines.append("▶ 시세 (전일 대비)")
        for corp in names:
            lines.append(_fmt_quote(corp, quotes.get(corp)))
        lines.append("")

    # ── 2) 공시 섹션 (신규만) ──
    if results:
        highlights = [r for r in results if r.get("tag") in ("호재", "악재")]
        head = (f"주목할 공시 {len(highlights)}건"
                if highlights else "중립성 공시 위주")
        failed = sum(1 for r in results if r.get("tag") == "분석실패")
        if failed:
            head += f" (분석실패 {failed}건)"
        lines.append(f"▶ 신규 공시: {head}")
        lines.append("")

        by_corp: dict[str, list[dict]] = {}
        for r in results:
            by_corp.setdefault(r["corp_name"], []).append(r)
        for corp, items in by_corp.items():
            lines.append(f"【{corp}】")
            for it in items:
                emoji = TAG_EMOJI.get(it.get("tag", "중립"), "⚪")
                lines.append(f"  {emoji} {it['report_nm']}  [{it.get('tag','중립')}]")
                summary = it.get("summary", [])
                if isinstance(summary, str):   # LLM 이 목록 대신 문장 하나로 준 경우
                    summary = [summary]
                for s in summary:
                    lines.append(f"     - {s}")
                lines.append(f"     · 예상 영향: {it.get('impact','-')}")
                lines.append(f"     · 원문: {it['url']}")
            lines.append("")
    else:
        lines.append("▶ 신규 공시: 없음 ✅")
        lines.append("")

    # ── 3) 종목 뉴스 섹션 ──
    if news and any(news.values()):
        lines.append("▶ 종목 뉴스")
        names = order or list(news)
        for corp in names:
            items = news.get(corp) or []
            if not items:
                continue
            lines.append(f"【{corp}】")
            for n in items:
                date = f" ({n['date']})" if n.get("date") else ""
                lines.append(f"  · {n['title']}{date}")
                if n.get("link"):
                    lines.append(f"    {n['link']}")
        lines.append("")

    return subject, "\n".join(lines)


def send_email(subject: str, body: str) -> bool:
    if not (config.SMTP_USER and config.SMTP_PASS and config.MAIL_TO):
        print("  ℹ️  메일 설정이 없어 발송을 건너뜁니다 (.env 의 SMTP_* / MAIL_TO 확인).")
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER
    msg["To"] = config.MAIL_TO
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        print("  ✉️  메일 발송 완료")
        return True
    except Exception as e:
        print(f"  ⚠️  메일 발송 실패: {e}")
        return False


def send_kakao(text: str) -> bool:
    """카카오톡 '나에게 보내기'(메모). KAKAO_ACCESS_TOKEN 있을 때만."""
    if not config.KAKAO_ACCESS_TOKEN:
        return False
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    template = {
        "object_type": "text",
        "text": text[:1900],  # 카카오 길이 제한 대비
        "link": {"web_url": "https://dart.fss.or.kr"},
    }
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.KAKAO_ACCESS_TOKEN}"},
            data={"template_object": __import__("json").dumps(template)},
            timeout=15,
        )
        if resp.status_code == 200:
            print("  💬 카카오톡 발송 완료")
            return True
        print(f"  ⚠️  카카오톡 실패({resp.status_code}): {resp.text[:120]}")
        return False
    except Exception as e:
        print(f"  ⚠️  카카오톡 실패: {e}")
        return False
