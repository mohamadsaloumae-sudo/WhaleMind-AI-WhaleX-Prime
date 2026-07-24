// لوحة الإدارة — إحصائيات + إدارة المشتركين (ترقية يدوية)
import UserSheet from "../components/UserSheet.jsx";
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Users, Activity, DollarSign, Crown, Check } from "lucide-react";

export default function Admin() {
  const { t, lang } = useLang();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [sheetUser, setSheetUser] = useState(null);
  const [frozen, setFrozen] = useState(false);
  const [bcast, setBcast] = useState("");
  const [bcastMsg, setBcastMsg] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    try { setStats(await api.get("/api/admin/stats")); } catch (e) { setErr(e.message); }
    try { const u = await api.get("/api/admin/users"); setUsers(u?.users || []); } catch { /* */ }
    try { const f = await api.get("/api/admin/freeze"); setFrozen(!!f?.frozen); } catch { /* */ }
  }
  useEffect(() => { load(); }, []);

  async function grantPro(uid) {
    setBusy(uid); setMsg("");
    try {
      await api.post(`/api/admin/users/${uid}/grant-pro`, {});
      setMsg(t("grantedPro"));
      load();
    } catch (e) { setMsg(e.message); }
    finally { setBusy(""); }
  }

  return (
    <>
      {err && <div className="alert info">{t("adminFetchFail")}: {err}</div>}
      {msg && <div className="alert success">{msg}</div>}

      {/* الإحصائيات */}
      <div className="grid grid-3" style={{ marginBottom: 24 }}>
        <div className="card stat">
          <span className="label"><Users size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("users")}</span>
          <span className="value">{stats?.total_users ?? "—"}</span>
        </div>
        <div className="card stat">
          <span className="label"><DollarSign size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("proUsers")}</span>
          <span className="value" style={{ color: "var(--brand)" }}>{stats?.pro_users ?? "—"}</span>
        </div>
        <div className="card stat">
          <span className="label"><Activity size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("todayTrades")}</span>
          <span className="value">{stats?.trades_today ?? "—"}</span>
        </div>
      </div>

      {/* إدارة المستخدمين */}
      <div className="card">
        <div style={{
          padding: 14, borderRadius: 12, marginBottom: 16,
          background: frozen ? "rgba(59,130,246,0.10)" : "rgba(255,255,255,0.04)",
          border: `1px solid ${frozen ? "rgba(59,130,246,0.3)" : "rgba(255,255,255,0.08)"}`,
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700 }}>{frozen ? "🧊 التداول مجمّد" : "✅ التداول يعمل"}</div>
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 3, lineHeight: 1.6 }}>
              {frozen ? "لا تُفتح أي صفقة آلية حتى فك التجميد" : "جمّده أثناء الصيانة لمنع أي تنفيذ آلي"}
            </div>
          </div>
          <button
            onClick={async () => {
              try {
                const r = await api.post(`/api/admin/freeze?enable=${!frozen}`, {});
                setFrozen(!!r?.frozen);
              } catch { /* */ }
            }}
            style={{
              flexShrink: 0, border: "none", borderRadius: 10, padding: "11px 18px",
              fontSize: 13, fontWeight: 700, cursor: "pointer",
              background: frozen ? "var(--brand)" : "rgba(59,130,246,0.9)",
              color: frozen ? "#06110a" : "#fff",
            }}
          >{frozen ? "فك التجميد" : "تجميد الكل"}</button>
        </div>

        <div style={{ padding: 14, borderRadius: 12, marginBottom: 16, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 4 }}>📢 إرسال جماعي</div>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 10, lineHeight: 1.6 }}>
            تصل كل المشتركين الفعّالين فقط — إشعار منبثق داخل التطبيق وتيليجرام
          </div>
          <textarea
            value={bcast}
            onChange={(e) => setBcast(e.target.value)}
            placeholder="اكتب رسالتك للمشتركين..."
            rows={3}
            style={{
              width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 10, padding: "10px 12px", color: "inherit", fontSize: 13, outline: "none",
              resize: "vertical", marginBottom: 8, fontFamily: "inherit",
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              onClick={async () => {
                const t = bcast.trim();
                if (!t) return;
                if (!confirm("إرسال هذه الرسالة لكل المشتركين الفعّالين؟")) return;
                try {
                  const r = await api.post("/api/admin/broadcast", { message: t });
                  setBcastMsg(`✅ وصلت ${r?.recipients ?? 0} مشترك`);
                  setBcast("");
                } catch { setBcastMsg("⚠️ فشل الإرسال"); }
              }}
              style={{
                background: "var(--brand)", color: "#06110a", border: "none", borderRadius: 10,
                padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer",
              }}
            >إرسال للجميع</button>
            {bcastMsg && <span style={{ fontSize: 12, color: "var(--brand)" }}>{bcastMsg}</span>}
          </div>
        </div>

        <div className="card-title">{t("manageUsers")} ({users.length})</div>
        {sheetUser && (
          <UserSheet userId={sheetUser} onClose={() => setSheetUser(null)} onChanged={load} />
        )}
        {users.length === 0 ? (
          <div className="empty">{t("adminHint")}</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {users.map((u) => (
              <div key={u.id} onClick={() => setSheetUser(u.id)} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 14px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)",
                cursor: "pointer",
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{u.username}</div>
                  <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai" }) : ""}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="badge" style={{
                    background: u.tier === "pro" ? "rgba(45,212,191,0.15)" : u.tier === "admin" ? "rgba(168,85,247,0.15)" : "var(--bg-1)",
                    color: u.tier === "pro" ? "var(--brand)" : u.tier === "admin" ? "var(--accent)" : "var(--txt-3)",
                  }}>{u.tier}</span>
                  {u.tier === "free" && (
                    <button
                      className="btn btn-primary"
                      style={{ padding: "6px 12px", fontSize: 12 }}
                      onClick={() => grantPro(u.id)}
                      disabled={busy === u.id}
                    >
                      {busy === u.id ? "..." : <><Crown size={13} /> {t("grantPro")}</>}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
