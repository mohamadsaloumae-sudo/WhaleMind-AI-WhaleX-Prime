"""
Claude AI Approval V3 — مع Web Search
═════════════════════════════════════════════
Claude يضيف قيمة حقيقية:
1. يبحث في الإنترنت عن أخبار العملة الحالية
2. يفحص الأحداث القادمة (Token Unlock, Airdrop, FOMC...)
3. يفحص Sentiment السوق
4. يقارن مع بياناتنا ويُقرر
"""
import asyncio, httpx, logging, time

log = logging.getLogger("claude_approval")

_last_call = 0
_min_interval = 5

async def claude_approval(sig) -> tuple[bool, str]:
    """فلتر Claude — مع web search للسياق الخارجي"""
    global _last_call
    now = time.time()
    
    elapsed = now - _last_call
    if elapsed < _min_interval:
        await asyncio.sleep(_min_interval - elapsed)
    _last_call = time.time()
    
    try:
        from core.config import get_settings
        s = get_settings()
        
        if not s.anthropic_api_key:
            return True, "No API key"
        
        # ─ اسم العملة الأساسي ─
        base_symbol = sig.symbol.replace("USDT", "").replace("BUSD", "")
        
        # ─ البرومبت الذكي ─
        prompt = f"""أنت محلل كريبتو خبير. تقيّم إشارة تداول من نظام WhaleX Prime.

📊 الإشارة (من تحليلنا التقني):
{sig.symbol} {sig.direction} | Grade {sig.grade} | Score {sig.score}/10 | ثقة {sig.confidence}%
Entry: {sig.entry} | SL: {sig.sl} | TP1: {sig.tp1} | TP2: {sig.tp2} | TP3: {sig.tp3}
R:R 1:{sig.rr_tp1} | 1:{sig.rr_tp2} | 1:{sig.rr_tp3}
Strategies ({sig.strategy_count}/13): {sig.strategies[:300]}
MTF: 15m={sig.mtf_15m} | 1H={sig.mtf_1h} | 4H={sig.mtf_4h}
BTC: {sig.btc_trend} | Funding: {sig.funding_rate}% | OI: {sig.open_interest_change}%

🔍 مهمتك:
استخدم web_search للبحث عن:
1. آخر أخبار {base_symbol} (24 ساعة)
2. أحداث قادمة (Token Unlock, Airdrop, Mainnet)
3. السياق الماكرو (FOMC, CPI, خبر مؤثر على الكريبتو)

ثم قرّر هل هناك تناقض مع الإشارة.

⚠️ أجب فقط بـ 4-6 كلمات بالصيغة التالية (لا تكتب أي شيء آخر، لا مقدمة ولا تحليل):

APPROVED: <سبب من 3 كلمات>
أو
REJECT: <سبب من 3 كلمات>"""
        
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": s.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5",
                    "max_tokens": 300,
                    "tools": [{
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 2
                    }],
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            
            if r.status_code != 200:
                log.warning("Claude %s: %s", r.status_code, r.text[:150])
                return True, "API error — auto-approved"
            
            result = r.json()
            reply = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    reply += " " + block.get("text", "")
            reply_upper = reply.strip().upper()
            log.info("🤖 Claude: %s → %s", sig.symbol, reply[:120])
            
            if "REJECT" in reply_upper:
                idx = reply_upper.find("REJECT")
                # نحذف "REJECT" أو "REJECTED" مع علامات الترقيم
                after = reply[idx:].split(":", 1)
                reason = after[1].strip().strip("*_- .\n").strip()[:60] if len(after) > 1 else "REJECTED"
                return False, reason or "REJECTED"
            elif "APPROV" in reply_upper:
                idx = reply_upper.find("APPROV")
                after = reply[idx:].split(":", 1)
                reason = after[1].strip().strip("*_- .\n").strip()[:60] if len(after) > 1 else "APPROVED"
                return True, reason or "APPROVED"
            else:
                return True, "Unclear"
                
    except asyncio.TimeoutError:
        log.warning("Claude timeout")
        return True, "Timeout"
    except Exception as e:
        log.warning("Claude error: %s", e)
        return True, "Error"
