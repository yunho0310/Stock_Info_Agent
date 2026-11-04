"""
공시 요약기 (Claude API).

각 신규 공시에 대해:
  - 호재 / 악재 / 중립 태그
  - 3줄 요약
  - 예상 주가 영향 한 줄
을 생성합니다.

v1 은 '공시 제목 + 회사명' 기반으로 해석합니다. (DART list.json 이 주는 정보)
공시 원문 전체를 읽고 싶으면 아래 fetch_document_text() 를 구현해
프롬프트에 본문을 끼워 넣으면 됩니다. (확장 포인트 표시해 둠)
"""
from __future__ import annotations
import io
import re
import html
import json
import zipfile

import requests

import config

SYSTEM_PROMPT = """너는 한국 주식 투자자를 돕는 공시 분석 어시스턴트다.
주어진 DART 공시 제목·회사명과 (제공되면) 공시 원문 발췌를 바탕으로,
투자자가 5초 안에 파악할 수 있도록 간결히 분석하라.
원문이 있으면 반드시 원문 내용을 근거로 삼고, 제목만 있으면 그 한계를 드러내라.
추측을 사실처럼 단정하지 마라.
반드시 아래 JSON 형식 '하나만' 출력하라. 다른 말, 마크다운, 코드펜스 금지.

{"tag": "호재|악재|중립", "summary": ["문장1", "문장2", "문장3"], "impact": "예상 주가 영향 한 줄"}"""

VALID_TAGS = ("호재", "악재", "중립")


def _build_user_prompt(item: dict, body: str | None) -> str:
    base = (
        f"회사명: {item['corp_name']}\n"
        f"공시 제목: {item['report_nm']}\n"
        f"접수일: {item['rcept_dt']}\n"
        f"제출인: {item.get('flr_nm', '')}"
    )
    if body:
        base += f"\n\n[공시 원문 발췌]\n{body[:4000]}"
    return base


def _clean_dart_xml(raw: bytes) -> str:
    """DART 원문(XML/HTML 바이트) → 태그 걷어낸 평문."""
    text = None
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)  # 스크립트 제거
    text = re.sub(r"(?s)<[^>]+>", " ", text)                         # 모든 태그 제거
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_document_text(rcept_no: str) -> str | None:
    """
    DART document API 로 공시 원문을 가져와 평문으로 반환.
    응답은 zip(내부 XML)이라 압축 해제 후 태그를 제거한다.
    실패해도(권한/형식 등) None 반환 → 제목 기반으로 자동 폴백.
    """
    if config.MOCK_MODE or not config.DART_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://opendart.fss.or.kr/api/document.xml",
            params={"crtfc_key": config.DART_API_KEY, "rcept_no": rcept_no},
            timeout=30,
        )
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith((".xml", ".html"))]
            if not xml_names:
                return None
            raw = zf.read(xml_names[0])     # 본 문서(첫 파일)
        text = _clean_dart_xml(raw)
        return text or None
    except zipfile.BadZipFile:
        return None                        # zip 이 아니면(에러응답 등) 폴백
    except Exception as e:
        print(f"  ⚠️  원문 조회 실패({rcept_no}): {e}")
        return None


def summarize_one(item: dict) -> dict:
    """공시 1건 → 분석 결과 dict (item 에 tag/summary/impact 추가)."""
    if config.MOCK_MODE or not config.ANTHROPIC_API_KEY:
        return {**item, **_mock_summary(item)}

    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    body = fetch_document_text(item["rcept_no"]) if config.FETCH_DOCUMENT else None
    msg = client.messages.create(
        model=config.SUMMARY_MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(item, body)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"summary": [text[:200]], "impact": "분석 형식 오류"}
    if parsed.get("tag") not in VALID_TAGS:
        print(f"  ⚠️  태그 형식 오류({item['corp_name']}): {parsed.get('tag')!r}")
        parsed["tag"] = "분석실패"
        parsed["summary_failed"] = True
    return {**item, **parsed}


def summarize_all(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        try:
            out.append(summarize_one(it))
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            print(f"  ⚠️  요약 실패({it['corp_name']}) → {reason}")
            out.append({
                **it,
                "tag": "분석실패",
                "summary": [f"요약 실패 ({type(e).__name__})",
                            "python3 diagnose.py 로 원인 확인하세요."],
                "impact": reason[:160],
                "summary_failed": True,
            })
    return out


# ──────────────────────────────────────────────────────────────
# MOCK: 키 없이 시험용 (제목 키워드 기반 단순 규칙)
# ──────────────────────────────────────────────────────────────
def _mock_summary(item: dict) -> dict:
    title = item["report_nm"]
    if "공급계약" in title or "자기주식취득" in title or "자기주식 취득" in title:
        tag = "호재"
    elif "유상증자" in title or "전환사채" in title:
        tag = "악재"
    else:
        tag = "중립"
    return {
        "tag": tag,
        "summary": [
            f"{item['corp_name']}가 '{title}' 공시를 제출했습니다.",
            "제목 기반 자동 분류 결과입니다 (MOCK).",
            "실제 키 연결 시 Claude 가 원문 맥락까지 해석합니다.",
        ],
        "impact": f"[MOCK] {tag} 신호로 추정",
    }
