# 📈 보유종목 공시 요약 에이전트

> 개발 기간: 2026.06 · 공개: 2026.11 · AI 개발 도구(Claude Code)로 구현

매일 아침, 내가 보유한 종목의 **새 DART 공시**를 자동으로 찾아
**호재/악재 태깅 + 3줄 요약 + 예상 영향**으로 정리해서 메일·카카오톡으로 보내주는 에이전트.

> 강의 〈AI 주식 자동매매 with Claude Code〉의 구조
> (`로그인 → 데이터 수집 → 전략 실행 → 주문`) 에서
> 위험한 **주문(매수/매도)** 자리를 **요약·알림**으로 바꾼 **안전 버전**입니다.
> 돈이 직접 움직이지 않으므로 입문/검증 단계에 적합합니다.

---

## 🧩 구조

```
disclosure-agent/
├─ run.py                 # 진입점:  python run.py
├─ config.py              # ★ 보유종목·키·옵션 (여기만 보면 됨)
├─ .env.example           # → .env 로 복사 후 본인 키 입력
├─ requirements.txt
├─ crontab.example        # 스케줄 등록 예시
└─ src/
   ├─ dart_client.py      # DART 공시 수집 (+ 종목명→corp_code 매핑)
   ├─ store.py            # SQLite 중복 제거 (이미 보낸 공시 기록)
   ├─ summarizer.py       # Claude API 요약·태깅
   ├─ notifier.py         # 메일(SMTP) + 카카오톡 발송
   └─ pipeline.py         # 전체 흐름 오케스트레이션
```

흐름: **수집(DART) → 신규만 필터(SQLite) → 요약(Claude) → 전송(메일/카톡) → 기록**

---

## 🚀 시작하기 (돌아와서 5분)

### 0. 키 없이 먼저 돌려보기 (이미 검증됨)
```bash
pip install -r requirements.txt
MOCK_MODE=1 python run.py     # 가짜 공시로 전체 흐름 확인
```

### 1. 키 발급 (전부 무료/저가)
| 키 | 발급처 | 비고 |
|----|--------|------|
| DART | https://opendart.fss.or.kr | 인증키 신청, 무료 |
| Anthropic | https://console.anthropic.com | API Keys, 요약당 수원 미만 |
| Gmail 앱비번 | Google 계정 → 보안 → 앱 비밀번호 | 2단계 인증 필요 |

### 2. .env 작성
```bash
cp .env.example .env
# .env 를 열어 위에서 받은 키들을 채우기
```
> ⚠️ `.env` 는 **절대 git 에 올리지 마세요** (`.gitignore` 에 이미 포함).
> 키는 본인만 다뤄야 합니다.

### 3. 보유종목 수정
`config.py` 의 `HOLDINGS` 리스트를 **실제 보유종목**으로 교체.
종목명("삼성전자") 또는 6자리 코드("005930") 둘 다 인식.

### 4. 실행
```bash
python run.py
```

---

## ⏰ 매일 자동 실행

```bash
crontab -e
# crontab.example 의 한 줄을 본인 경로로 수정해 붙여넣기
# (평일 오전 8시 실행)
```
- 노트북은 그 시각에 **켜져 있어야** 실행됩니다.
- **24시간** 돌리려면 EC2 에 올려 같은 cron 등록 → 너의 자산관리 API 서버 AWS 배포 계획과 합쳐집니다.

---

## 💬 카카오톡 "나에게 보내기" (선택)

1. https://developers.kakao.com → 애플리케이션 생성
2. 카카오 로그인 활성화 + 동의항목에 `talk_message` 추가
3. OAuth 로 access token 발급 → `.env` 의 `KAKAO_ACCESS_TOKEN` 에 입력
   (토큰 만료 시 refresh 필요 — 자동 갱신은 추후 확장)
- 비워두면 메일만 발송하고 카톡은 자동 생략됩니다.

---

## 🔧 확장 포인트 (다음 단계)

1. **공시 원문 전체 분석** — `summarizer.fetch_document_text()` 구현.
   DART `document.xml`(zip) 을 받아 본문을 프롬프트에 주입하면
   제목 기반 → 원문 기반 정밀 요약으로 업그레이드.
2. **RAG 확장** — 요약 결과를 벡터DB(Chroma 등)에 적재하면
   "내 보유종목 최근 공시 자연어 질의"가 가능. (네가 탐색하던 방향)
3. **저장소 교체** — `store.py` 의 `filter_new/mark_sent` 인터페이스를 유지한 채
   SQLite → 자산관리 API 서버의 **MySQL** 로 바꾸면 프로젝트와 통합.
4. **포트폴리오 연동** — 보유종목을 하드코딩 대신 자산관리 API 에서 가져오기.

---

## ⚠️ 안전 메모

- 이 에이전트는 **분석·알림 전용**입니다. 자동 매수/매도 기능은 **의도적으로 넣지 않았습니다.**
- 출력은 투자 참고용이며, 투자 판단과 책임은 본인에게 있습니다.
- 공시 해석은 제목·원문 기반 자동 분석이므로, 중요한 건은 반드시 원문 링크로 직접 확인하세요.
