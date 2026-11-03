"""
요약 실패 원인 진단기.

실행:  python3 diagnose.py

Anthropic API 호출만 따로 떼어 1회 시험해서,
'요약 실패'의 진짜 원인(키/모델/크레딧/네트워크)을 콕 집어줍니다.
"""
from __future__ import annotations

import config


def main():
    print("=== 요약(Anthropic) 진단 ===\n")

    # 1) 키 존재/형식 점검
    key = config.ANTHROPIC_API_KEY
    if not key:
        print("❌ ANTHROPIC_API_KEY 가 비어 있습니다.")
        print("   → .env 에 ANTHROPIC_API_KEY=sk-ant-... 를 넣었는지 확인하세요.")
        return
    if key != key.strip() or " " in key:
        print("⚠️  키 앞뒤/중간에 공백이 있습니다. 따옴표·공백 없이 붙여넣으세요.")
    if not key.startswith("sk-ant-"):
        print("⚠️  키가 보통 'sk-ant-' 로 시작합니다. 값이 올바른지 확인하세요.")
    print(f"• 키 길이: {len(key)}자 (앞 10자: {key[:10]}…)")
    print(f"• 모델: {config.SUMMARY_MODEL}\n")

    # 2) 실제 호출 1회
    try:
        import anthropic
    except ImportError:
        print("❌ anthropic 패키지가 없습니다 → python3 -m pip install anthropic")
        return

    client = anthropic.Anthropic(api_key=key)
    try:
        msg = client.messages.create(
            model=config.SUMMARY_MODEL,
            max_tokens=20,
            messages=[{"role": "user", "content": "한국어로 '정상'이라고만 답해."}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        print(f"✅ 호출 성공! 응답: {text!r}")
        print("   → 키·모델 모두 정상입니다. run.py 의 요약도 작동해야 합니다.")
    except Exception as e:
        name = type(e).__name__
        print(f"❌ 호출 실패: {name}: {e}\n")
        _hint(name, str(e))


def _hint(name: str, msg: str):
    m = (name + " " + msg).lower()
    print("── 원인 추정 ──")
    if "authentication" in m or "401" in m or "invalid x-api-key" in m:
        print("🔑 키가 틀렸습니다. console.anthropic.com 에서 키를 다시 발급해")
        print("   .env 의 ANTHROPIC_API_KEY 에 공백 없이 넣으세요.")
    elif "not_found" in m or "404" in m or "model" in m:
        print("🤖 모델 이름 문제일 수 있습니다.")
        print("   .env 에 SUMMARY_MODEL=claude-haiku-4-5-20251001 로 지정하거나,")
        print("   claude-sonnet-4-6 등 계정에서 쓸 수 있는 모델로 바꿔보세요.")
    elif "credit" in m or "billing" in m or "quota" in m or "402" in m or "insufficient" in m:
        print("💳 크레딧/결제 문제입니다. console.anthropic.com → Billing 에서")
        print("   결제수단을 등록하거나 크레딧을 충전하세요. (요약은 건당 몇 원 수준)")
    elif "rate" in m or "429" in m:
        print("⏳ 요청이 너무 잦습니다(rate limit). 잠시 후 다시 시도하세요.")
    elif "connection" in m or "timeout" in m or "network" in m:
        print("🌐 네트워크 문제입니다. 인터넷 연결을 확인하고 다시 시도하세요.")
    else:
        print("❓ 위 메시지를 그대로 복사해서 물어보면 정확히 짚어드릴게요.")


if __name__ == "__main__":
    main()
