from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from routers.auth import require_pro, get_current_user
from core.config import get_settings
import logging

log = logging.getLogger("ai")

router = APIRouter(prefix="/api/ai", tags=["AI"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatBody(BaseModel):
    messages: List[ChatMessage]

class ContractBody(BaseModel):
    address: str
    chain: str = "sol"

@router.post("/chat")
async def ai_chat(body: ChatBody):
    s = get_settings()
    if not s.anthropic_api_key:
        return {"reply": "AI غير متاح حالياً. يرجى إضافة ANTHROPIC_API_KEY في الإعدادات."}
    try:
        import httpx
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 1000,
                    "system": """أنت WhaleX AI — المساعد الذكي الرسمي لمنصة WhaleMind Prime وWhaleX Prime.

هويتك:
- أنت جزء من منظومة WhaleMind Hybrid AI للتداول الذكي
- تعمل داخل Mini App على Telegram
- متخصص في تحليل أسواق الكريبتو وإدارة الصفقات

معلومات المنصة:
- WhaleX Prime: منظومة تداول ذكية مدعومة بالذكاء الاصطناعي
- WhaleMind AI: الرادار الذكي الذي يحلل 256 عملة في الوقت الفعلي
- الرادارات: Futures + Spot + Meme Coins
- Auto Trading: يدير الصفقات تلقائياً مع Pyramiding و Kill Switch
- Meme Scanner: يفحص العقود الذكية بـ 8 مراحل أمان
- المحافظ: تدعم Solana وEthereum وBSC وTron وBitcoin
- الاشتراك PRO: $50/شهر

للأسعار الحقيقية:
- BTC الآن تقريباً في منطقة $75,000-$80,000 (مايو 2026)
- إذا سألك المستخدم عن سعر محدد، اطلب منه السعر الحالي وحلل بناءً عليه
- يمكنك التحليل الفني الكامل: CVD، FVG، Order Block، Liquidation، RSI، MACD

قواعد:
- أجب دائماً بثقة ووضوح
- لا تقل أبداً أنك لا تعرف WhaleX أو WhaleMind
- إذا سألك عن كيفية عمل المنصة اشرح بالتفصيل
- تخصصك: الكريبتو والتداول فقط""",
                    "messages": messages[-10:],
                }
            )
            data = r.json()
            reply = data.get("content", [{}])[0].get("text", "خطأ في الاتصال")
            return {"reply": reply}
    except Exception as e:
        return {"reply": f"خطأ: {str(e)}"}

@router.post("/scan-contract")
async def scan_contract(body: ContractBody):
    from routers.scanner_engine import full_scan
    try:
        result = await full_scan(body.address, body.chain)
        return result
    except Exception as e:
        log.error("Scanner error: %s", e)
    # fallback
    s = get_settings()
    prompt = f"""افحص عقد العملة الرقمية بعنوان: {body.address} على شبكة {body.chain}

قم بفحص 8 مراحل:
1. Honeypot — هل يمكن البيع؟
2. Mint Authority — هل يمكن طباعة عملات جديدة؟
3. Freeze Authority — هل يمكن تجميد المحافظ؟
4. Liquidity Lock — هل السيولة محجوزة؟
5. Top Holders — هل شخص يملك 50%+؟
6. Contract Audit — هل العقد مدقق؟
7. Dev Wallet Activity — هل المطور باع؟
8. Social Verification — هل المشروع حقيقي؟

أعطني النتيجة بتنسيق JSON فقط مع هذه الحقول:
- score (0-100)
- risk (low/medium/high/critical)
- verdict (آمن/محفوف بالمخاطر/خطير)
- checks (array of 8 items with name, passed boolean, note)
- recommendation"""

    if not s.anthropic_api_key:
        return {
            "score": 0, "risk": "unknown", "verdict": "لا يمكن الفحص — API غير متاح",
            "checks": [], "recommendation": "يرجى إضافة ANTHROPIC_API_KEY"
        }
    try:
        import httpx, json
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 1000, "messages": [{"role": "user", "content": prompt}]}
            )
            data = r.json()
            text = data.get("content", [{}])[0].get("text", "{}")
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
    except Exception as e:
        return {"score": 0, "risk": "unknown", "verdict": f"خطأ: {str(e)}", "checks": [], "recommendation": ""}
