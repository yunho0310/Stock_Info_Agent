"""
설정 로더.

모든 비밀값(API 키, 메일 비밀번호 등)은 .env 파일에서 읽습니다.
.env 는 절대 git 에 올리지 마세요 (.gitignore 에 이미 포함).
"""
from __future__ import annotations
import os
from pathlib import Path

# .env 로드 (python-dotenv 가 있으면 사용, 없어도 OS 환경변수로 동작)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────
# 1) 내 보유종목  ← 여기만 네 실제 보유종목으로 바꾸면 됩니다.
#    종목명 또는 6자리 종목코드 둘 다 인식합니다.
# ──────────────────────────────────────────────────────────────
HOLDINGS = [
    h.strip()
    for h in os.getenv("HOLDINGS", "삼성전자,SK하이닉스,NAVER").split(",")
    if h.strip()
]  # 실제 보유종목은 .env 의 HOLDINGS=종목1,종목2,... 로 지정 (코드엔 예시만)

# ──────────────────────────────────────────────────────────────
# 2) API 키 / 비밀값  (.env 에서 읽음)
# ──────────────────────────────────────────────────────────────
DART_API_KEY = os.getenv("DART_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 요약에 쓸 모델. 매일 도는 작업이라 기본은 저렴한 Haiku.
# 더 정교한 해석을 원하면 "claude-sonnet-4-6" 으로 바꾸세요.
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "claude-haiku-4-5-20251001")

# ──────────────────────────────────────────────────────────────
# 3) 알림 채널  (.env 에서 읽음)
# ──────────────────────────────────────────────────────────────
# 이메일(SMTP). Gmail 이면 "앱 비밀번호"를 발급받아 SMTP_PASS 에 넣으세요.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")          # 보내는 사람 메일
SMTP_PASS = os.getenv("SMTP_PASS", "")          # 앱 비밀번호
MAIL_TO = os.getenv("MAIL_TO", "")              # 받는 사람 메일(보통 본인)

# 카카오톡 "나에게 보내기"(선택). 없으면 자동으로 건너뜀.
KAKAO_ACCESS_TOKEN = os.getenv("KAKAO_ACCESS_TOKEN", "")

# 네이버 검색 API (뉴스). 발급: https://developers.naver.com
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
# 뉴스 기능 on/off 및 종목당 뉴스 개수
NEWS_ENABLED = os.getenv("NEWS_ENABLED", "1") == "1"
NEWS_PER_STOCK = int(os.getenv("NEWS_PER_STOCK", "3"))

# ──────────────────────────────────────────────────────────────
# 4) 동작 옵션
# ──────────────────────────────────────────────────────────────
# 며칠 전 공시까지 조회할지 (기본: 어제~오늘. 주말/공휴일 보정용으로 3일 권장)
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "3"))

# 공시 원문까지 읽어 정밀 요약할지. 1=켜짐(권장), 0=제목만(크레딧 절약)
FETCH_DOCUMENT = os.getenv("FETCH_DOCUMENT", "1") == "1"

# dedup 용 SQLite 파일 경로
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "seen.db"))

# 키가 없을 때 가짜 데이터로 파이프라인을 시험하는 모드
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"
