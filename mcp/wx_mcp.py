"""🐋 خادم MCP لـWhaleX — تحكّم بالخادم من تطبيق Claude.

⚠️ يُنفّذ أوامر بصلاحيات مُشغّله. والخادم يحوي مفاتيح API لمشتركين
   بأموال حقيقية — فالمصادقة إلزامية ولا يعمل بلا رمز سرّيّ.

ويعمل في بيئة معزولة (venv) فلا يمسّ مكتبات النظام: تثبيته في
بيئة النظام رفع starlette إلى 1.6 وكسر fastapi وأوقف الخدمة.
"""
import asyncio
import hmac
import logging
import os
import pathlib
import subprocess
import time

from mcp.server.mcpserver import MCPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("/var/log/wx_mcp_audit.log"),
              logging.StreamHandler()])
log = logging.getLogger("wx_mcp")

TOKEN = os.environ.get("WX_MCP_TOKEN", "")
if not TOKEN or len(TOKEN) < 24:
    raise SystemExit("🔴 WX_MCP_TOKEN مفقود — ولّده: openssl rand -hex 32")

CMD_TIMEOUT = 120
MAX_OUT = 60_000
DENY = ("rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot",
        "> /dev/sd", "chmod -R 777 /")

# 🌐 نسمح بمضيف النفق — MCP 2.x يرفض أي Host غير محلّيّ حمايةً
#    من DNS rebinding، والنفق يُمرّر اسم trycloudflare فيُرفَض.
#    والمصادقة بالرمز تحمينا أصلاً.
import os as _os2
_HOSTS = _os2.environ.get("WX_MCP_HOSTS", "*")
# ملاحظة: allowed_hosts ليست بارامتراً لـMCPServer في هذه النسخة،
#   بل تُمرَّر عبر transport_security في sse_app أدناه.
mcp = MCPServer("whalex")


def _audit(kind, detail):
    log.info("🔑 %s | %s", kind, str(detail)[:400])


@mcp.tool(description="تنفيذ أمر shell على الخادم")
async def run_command(command: str, cwd: str = "/opt/whalex") -> str:
    low = command.lower()
    for d in DENY:
        if d in low:
            _audit("DENIED", command)
            return f"🔴 مرفوض — نمط خطر ({d})"
    _audit("RUN", f"{cwd}$ {command}")
    try:
        p = await asyncio.create_subprocess_shell(
            command, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        out, _ = await asyncio.wait_for(p.communicate(), CMD_TIMEOUT)
        t = out.decode("utf-8", "replace")
        if len(t) > MAX_OUT:
            t = t[:MAX_OUT] + f"\n… اقتُطع ({len(t)} حرفاً)"
        return f"[{p.returncode}]\n{t}" if t.strip() else f"[{p.returncode}] بلا مخرجات"
    except asyncio.TimeoutError:
        return f"🔴 تجاوز {CMD_TIMEOUT}s"
    except Exception as e:
        return f"🔴 {type(e).__name__}: {e}"


@mcp.tool(description="قراءة ملفّ نصّيّ مع أرقام الأسطر")
async def read_file(path: str, max_lines: int = 500) -> str:
    _audit("READ", path)
    try:
        p = pathlib.Path(path)
        if not p.is_file():
            return f"🔴 ليس ملفاً: {path}"
        lines = p.read_text("utf-8", "replace").splitlines()
        body = "\n".join(f"{i+1:5d}\t{l}" for i, l in enumerate(lines[:max_lines]))
        more = f"\n… ({len(lines)} سطراً)" if len(lines) > max_lines else ""
        return body + more
    except Exception as e:
        return f"🔴 {type(e).__name__}: {e}"


@mcp.tool(description="كتابة ملفّ مع نسخة احتياطية وفحص نحويّ")
async def write_file(path: str, content: str) -> str:
    _audit("WRITE", f"{path} ({len(content)}ح)")
    try:
        p = pathlib.Path(path)
        note = ""
        if p.exists():
            b = p.with_suffix(p.suffix + f".bak-{int(time.time())}")
            b.write_bytes(p.read_bytes())
            note = f" · نسخة {b.name}"
        if p.suffix == ".py":
            import ast
            ast.parse(content)
            note += " · نحوياً سليم ✅"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")
        return f"✅ {len(content)} حرفاً → {path}{note}"
    except SyntaxError as se:
        return f"🔴 خطأ نحويّ في السطر {se.lineno} — لم يُكتب"
    except Exception as e:
        return f"🔴 {type(e).__name__}: {e}"


@mcp.tool(description="استبدال نصّ فريد داخل ملفّ")
async def edit_file(path: str, old: str, new: str) -> str:
    _audit("EDIT", path)
    try:
        p = pathlib.Path(path)
        s = p.read_text("utf-8")
        n = s.count(old)
        if n != 1:
            return f"🔴 المرجع تكرّر {n} مرّة — يجب أن يكون فريداً"
        s2 = s.replace(old, new, 1)
        if p.suffix == ".py":
            import ast
            ast.parse(s2)
        b = p.with_suffix(p.suffix + f".bak-{int(time.time())}")
        b.write_bytes(p.read_bytes())
        p.write_text(s2, "utf-8")
        return f"✅ عُدّل · نسخة {b.name}"
    except SyntaxError as se:
        return f"🔴 الناتج معطوب نحوياً (السطر {se.lineno}) — لم يُكتب"
    except Exception as e:
        return f"🔴 {type(e).__name__}: {e}"


@mcp.tool(description="سجلّ خدمة systemd")
async def service_logs(service: str = "whalex", since: str = "10 min ago",
                       grep: str = "", lines: int = 60) -> str:
    q = f'journalctl -u {service} --since "{since}" --no-pager'
    if grep:
        q += f" | grep -iE {grep!r}"
    return await run_command(q + f" | tail -{int(lines)}", "/")


@mcp.tool(description="التحكّم بخدمة: status restart start stop is-active")
async def service_control(service: str = "whalex", action: str = "status") -> str:
    if action not in ("status", "restart", "start", "stop", "is-active"):
        return "🔴 فعل غير مسموح"
    _audit("SERVICE", f"{action} {service}")
    return await run_command(f"systemctl {action} {service} 2>&1 | head -25", "/")


@mcp.tool(description="فحص أمنيّ شامل للخادم")
async def security_check() -> str:
    out = []
    for t, c in (("الجلسات", "last -8 | head -8"),
                 ("محاولات فاشلة", "grep -c 'Failed password' /var/log/auth.log 2>/dev/null || echo 0"),
                 ("fail2ban", "fail2ban-client status sshd 2>/dev/null | tail -4 || echo 'غير مثبّت'"),
                 ("المنافذ", "ss -tlnp 2>/dev/null | grep LISTEN | head -10"),
                 ("الحمل", "uptime; free -m | head -2"),
                 ("القرص", "df -h / | tail -1")):
        out.append(f"═══ {t} ═══\n{await run_command(c, '/')}")
    return "\n\n".join(out)


@mcp.tool(description="استعلام SQL للقراءة فقط على SQLite")
async def query_db(db: str, sql: str, limit: int = 50) -> str:
    if not sql.strip().lower().startswith(("select", "pragma", "with")):
        return "🔴 القراءة فقط"
    _audit("SQL", f"{db}: {sql[:160]}")
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(x) for x in c.execute(sql).fetchmany(limit)]
        c.close()
        if not rows:
            return "(لا نتائج)"
        cols = list(rows[0])
        r = [" | ".join(cols), "-" * 60]
        r += [" | ".join(str(x.get(k))[:22] for k in cols) for x in rows]
        return "\n".join(r) + f"\n\n({len(rows)} صفّاً)"
    except Exception as e:
        return f"🔴 {type(e).__name__}: {e}"


def build_app():
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount

    class Auth(BaseHTTPMiddleware):
        """ثلاث طرق للرمز — بعض العملاء يحذف ?token= عند الحفظ،
        فنقبله أيضاً كجزء من المسار: /<TOKEN>/sse"""
        async def dispatch(self, request, call_next):
            h = request.headers.get("authorization", "")
            tok = ""
            if h.lower().startswith("bearer "):
                tok = h[7:]
            if not tok:
                tok = request.query_params.get("token", "")
            if not tok:
                parts = request.url.path.strip("/").split("/")
                if parts and len(parts[0]) >= 24:
                    tok = parts[0]
            if not hmac.compare_digest(tok, TOKEN):
                log.warning("🔴 رفض من %s · مسار %s",
                            request.client.host if request.client else "?",
                            request.url.path[:40])
                return JSONResponse({"error": "unauthorized"}, 401)
            return await call_next(request)

    # 🌐 نمرّر اعدادات النقل بأنفسنا — والا فعّلت المكتبة الحماية
    #    الافتراضية (127.0.0.1 فقط) فتُرفض طلبات النفق:
    #    ValueError: Request validation failed
    #    والامان محفوظ: الخدمة على 127.0.0.1 والمصادقة بالرمز مفعّلة.
    from mcp.server.transport_security import TransportSecuritySettings
    _sec = TransportSecuritySettings(
        enable_dns_rebinding_protection=False)
    inner = mcp.sse_app(transport_security=_sec)
    return Starlette(
        routes=[Mount(f"/{TOKEN}", app=inner), Mount("/", app=inner)],
        middleware=[Middleware(Auth)])


if __name__ == "__main__":
    import uvicorn
    log.info("🐋 WhaleX MCP · 127.0.0.1:8787 · المصادقة مفعّلة")
    uvicorn.run(build_app(), host="127.0.0.1", port=8787, log_level="warning")
