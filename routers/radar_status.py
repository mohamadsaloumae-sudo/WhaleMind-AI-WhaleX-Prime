"""🩺 حالة الرادارات — مقروءة من الواقع.

الشارة في الواجهة كانت نصا ثابتا يقول "يعمل" دائما، فلو توقف
رادار لبقيت تطمئن المشترك كذبا. هذا المسار يقرأ نبض كل رادار
من سجل الخدمة نفسه: قراءة فقط، بلا لمس رادار او قاعدة بيانات.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/radars", tags=["Radars"])


@router.get("/status")
def radars_status():
    try:
        from services.radar_pulse import status
        return status()
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "radars": []}
