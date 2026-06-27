// لوحة الإدارة — إحصائيات + إدارة المشتركين (ترقية يدوية)
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Users, Activity, DollarSign, Crown, Check } from "lucide-react";

export default function Admin() {
  const { t, lang } = useLang();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    try { setStats(await api.get("/api/admin/stats")); } catch (e) { setErr(e.message); }
    try { const u = await api.get("/api/admin/users"); setUsers(u?.users || []); } catch { /* */ }
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
        <div className="card-title">{t("manageUsers")} ({users.length})</div>
        {users.length === 0 ? (
          <div className="empty">{t("adminHint")}</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {users.map((u) => (
              <div key={u.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 14px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)",
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
