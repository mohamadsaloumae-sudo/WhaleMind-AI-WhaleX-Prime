// لوحة الإدارة — إحصائيات + إدارة المشتركين (ترقية يدوية)
import UserSheet from "../components/UserSheet.jsx";
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Users, Activity, DollarSign, Crown, Check } from "lucide-react";
import AdminChat from "../components/AdminChat.jsx";

export default function Admin() {
  const { t, lang } = useLang();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [uq, setUq] = useState("");
  // 🔍 بحث المستخدمين — لا يمسّ users الأصلية
  const _nz = (t) => String(t || "")
    .replace(/[أإآ]/g, "ا").replace(/ى/g, "ي")
    .replace(/ة/g, "ه").replace(/[ًٌٍَُِّْـ]/g, "").toLowerCase().trim();
  const _uq = _nz(uq);
  const fUsers = !_uq ? users : users.filter((u) =>
    _nz(u.username).includes(_uq) || _nz(u.email).includes(_uq) ||
    String(u.display_id || "").includes(_uq) ||
    String(u.id || "").toLowerCase().includes(_uq));
  // 👤 لوحة المشترك في العنوان أيضاً — فلا تُغلق عند التحديث.
  const [sheetUser, _setSheetRaw] = useState(() => {
    try {
      return new URLSearchParams(window.location.hash.replace(/^#/, "")).get("u") || null;
    } catch (e) { return null; }
  });
  const setSheetUser = (uid) => {
    _setSheetRaw(uid);
    try {
      const p = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      if (uid) p.set("u", uid); else p.delete("u");
      window.location.hash = p.toString();
    } catch (e) { /* */ }
  };
  const [frozen, setFrozen] = useState(false);
  const [bcast, setBcast] = useState("");
  const [refs, setRefs] = useState(null);      // 🎁 الإحالات
  const [wds, setWds] = useState([]);          // طلبات السحب
  const [openRef, setOpenRef] = useState(null);
  const [rq, setRq] = useState("");
  // 🔍 بحث الإحالات — لا يمسّ refs الأصلية
  const _rq = _nz(rq);
  const _fRefs = !refs?.referrers ? []
    : !_rq ? refs.referrers
    : refs.referrers.filter((r) =>
        _nz(r.code).includes(_rq) || _nz(r.name).includes(_rq)); // 👤 الحساب المفتوح
  // 📑 التبويب في العنوان — فالتحديث يُبقيك مكانك بدل الرجوع للرئيسية.
  const _readTab = () => {
    try {
      const h = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("t");
      return h || localStorage.getItem("wx_admin_tab") || "overview";
    } catch (e) { return "overview"; }
  };
  const [tab, _setTabRaw] = useState(_readTab);
  const setTab = (k) => {
    _setTabRaw(k);
    try {
      localStorage.setItem("wx_admin_tab", k);
      window.location.hash = "t=" + k;
    } catch (e) { /* */ }
  };
  useEffect(() => {
    const onHash = () => _setTabRaw(_readTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // 📱 بيان منفصل — فتُثبَّت لوحة الإدارة كأيقونة مستقلّة
  useEffect(() => {
    const el = document.querySelector('link[rel="manifest"]');
    const old = el?.getAttribute("href");
    if (el) el.setAttribute("href", "/static/admin-manifest.json");
    return () => { if (el && old) el.setAttribute("href", old); };
  }, []);
  const [bcastMsg, setBcastMsg] = useState("");
  const [pending, setPending] = useState([]);
  const [replies, setReplies] = useState({});

  useEffect(() => {
    const onQ = () => {
      api.get("/api/admin/support/pending")
        .then((s) => setPending(s?.pending || []))
        .catch(() => {});
    };
    window.addEventListener("wx-support", onQ);
    const iv = setInterval(onQ, 30000);
    return () => { window.removeEventListener("wx-support", onQ); clearInterval(iv); };
  }, []);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    try { setStats(await api.get("/api/admin/stats")); } catch (e) { setErr(e.message); }
    try { const u = await api.get("/api/admin/users"); setUsers(u?.users || []); } catch { /* */ }
    try { const f = await api.get("/api/admin/freeze"); setFrozen(!!f?.frozen); } catch { /* */ }
    try { setRefs(await api.get("/api/admin/referrals")); }
    catch (e) { setRefs({ error: e?.message || "تعذر الجلب" }); }
    try { const w = await api.get("/api/admin/withdrawals"); setWds(w?.withdrawals || []); } catch { /* */ }
    try {
      const s = await api.get("/api/admin/support/pending");
      setPending(s?.pending || []);
      localStorage.setItem("wx_is_admin", "1");
    } catch { /* */ }
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

      {/* 📑 تبويبات — كل قسم على حدة */}
      <div style={{ display: "flex", gap: 7, margin: "14px 0", flexWrap: "wrap" }}>
        {[["overview","📊 نظرة عامّة"],["users","👥 المستخدمون"],["referrals","🎁 الإحالات"],["support","💬 الدعم" + (pending.length ? " (" + pending.length + ")" : "")]].map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)} style={{
            padding: "8px 15px", borderRadius: 10, cursor: "pointer", fontSize: 12.5,
            fontWeight: tab===k?800:600,
            background: tab===k?"rgba(45,212,191,.14)":"transparent",
            border: "1px solid "+(tab===k?"rgba(45,212,191,.45)":"rgba(255,255,255,.1)"),
            color: tab===k?"var(--brand)":"var(--txt-3)",
          }}>{l}</button>
        ))}
      </div>

      {tab==="users" && (
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

        <div className="card-title">
          {t("manageUsers")} ({fUsers.length}{uq ? ` / ${users.length}` : ""})
        </div>
        <input
          value={uq}
          onChange={(e) => setUq(e.target.value)}
          placeholder="🔍 اسم · بريد · ID"
          style={{
            width: "100%", padding: "9px 12px", borderRadius: 9, marginBottom: 10,
            border: "1px solid rgba(255,255,255,.10)",
            background: "rgba(255,255,255,.05)", color: "var(--txt-1)",
            fontSize: 13.5, outline: "none", boxSizing: "border-box",
          }}
        />
        {sheetUser && (
          <UserSheet userId={sheetUser} onClose={() => setSheetUser(null)} onChanged={load} />
        )}
        {fUsers.length === 0 ? (
          <div className="empty">{t("adminHint")}</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {fUsers.map((u) => (
              <div key={u.id} onClick={() => setSheetUser(u.id)} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 14px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)",
                cursor: "pointer",
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{u.username}</div>
                  {u.display_id && (
                    <div style={{ fontSize: 10.5, color: "var(--txt-3)",
                                  fontFamily: "monospace" }}>ID {u.display_id}</div>
                  )}
                  <div style={{ fontSize: 11, color: "var(--txt-3)", display: "flex", gap: 7, alignItems: "center" }}>
                    <span>{u.created_at ? new Date(u.created_at).toLocaleDateString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai" }) : ""}</span>
                    {u.has_binance ? (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 5,
                        background: u.auto_trade_on ? "rgba(34,197,94,0.16)" : "rgba(234,179,8,0.16)",
                        color: u.auto_trade_on ? "#22c55e" : "#eab308",
                      }}>
                        🔗 {u.auto_trade_on ? "مربوط" : "مربوط · آليّ مُطفأ"}
                      </span>
                    ) : (
                      <span style={{
                        fontSize: 10, padding: "1px 6px", borderRadius: 5,
                        background: "rgba(255,255,255,0.05)", color: "var(--txt-3)",
                      }}>لا ربط</span>
                    )}
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

      )}

      {tab === "support" && <AdminChat />}

      {/* 🎁 الإحالات وطلبات السحب */}
      {tab==="referrals" && (refs?.error) && (
        <div className="card" style={{ marginTop: 16, padding: 14, border: "1px solid rgba(248,113,113,.3)" }}>
          <div style={{ fontSize: 12.5, color: "#f87171" }}>⚠️ الإحالات: {refs.error}</div>
        </div>
      )}
      {tab==="referrals" && refs && !refs.error && (
        <div className="card" style={{ marginTop: 16, padding: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>
            🎁 الإحالات ({_fRefs.length}{rq ? ` / ${refs.referrers.length}` : ""})
          </div>
          <input
            value={rq}
            onChange={(e) => setRq(e.target.value)}
            placeholder="🔍 كود أو اسم المُحيل"
            style={{
              width: "100%", padding: "9px 12px", borderRadius: 9, marginBottom: 10,
              border: "1px solid rgba(255,255,255,.10)",
              background: "rgba(255,255,255,.05)", color: "var(--txt-1)",
              fontSize: 13.5, outline: "none", boxSizing: "border-box",
            }}
          />

          <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
            {[["مُحيل", refs.referrers.length],
              ["سجّلوا", refs.total_invited],
              ["💳 دفعوا", refs.referrers.reduce((a, r) => a + r.converted, 0)],
              ["مستحقّ", "$" + refs.total_owed]]
              .map(([l, v], i) => (
              <div key={i} style={{
                flex: 1, textAlign: "center", padding: "10px 4px",
                background: "rgba(255,255,255,.03)", borderRadius: 10,
                border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: 17, fontWeight: 800, color: i === 3 ? "#fbbf24" : i === 2 ? "#22c55e" : "var(--txt-1)" }}>{v}</div>
                <div style={{ fontSize: 10, color: "var(--txt-3)", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>

          {wds.filter((w) => w.status === "pending").length > 0 && (
            <>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "#fbbf24", marginBottom: 9 }}>
                ⏳ طلبات سحب معلّقة
              </div>
              {wds.filter((w) => w.status === "pending").map((w) => (
                <div key={w.id} style={{
                  background: "rgba(251,191,36,.06)", border: "1px solid rgba(251,191,36,.3)",
                  borderRadius: 12, padding: 13, marginBottom: 9,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <b style={{ fontSize: 13.5 }}>{w.name}</b>
                    <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{w.country}</span>
                    <span style={{ marginInlineStart: "auto", fontSize: 17, fontWeight: 900, color: "#22c55e" }}>
                      ${w.amount}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--txt-2)", marginBottom: 4, direction: "ltr" }}>
                    {w.phone} · {w.network} · دعا {w.invited}
                  </div>
                  <div style={{
                    fontSize: 10.5, color: "var(--txt-3)", wordBreak: "break-all",
                    direction: "ltr", marginBottom: 10, userSelect: "all",
                  }}>{w.wallet}</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-primary" style={{ flex: 1, fontSize: 12 }}
                      onClick={async () => {
                        if (!window.confirm(`أرسلتَ $${w.amount} فعلاً؟`)) return;
                        try { await api.post(`/api/admin/withdrawals/${w.id}`, { action: "paid" }); load(); }
                        catch (e) { alert(e.message); }
                      }}>✓ دُفعت</button>
                    <button className="btn btn-danger" style={{ flex: 1, fontSize: 12 }}
                      onClick={async () => {
                        if (!window.confirm("رفض الطلب؟")) return;
                        try { await api.post(`/api/admin/withdrawals/${w.id}`, { action: "rejected" }); load(); }
                        catch (e) { alert(e.message); }
                      }}>✕ رفض</button>
                  </div>
                </div>
              ))}
            </>
          )}

          {_fRefs.map((r) => {
            const open = openRef === r.code;
            const ST = {
              subscribed: ["✅", "مشترك", "#22c55e"],
              trial: ["🎁", "تجربة", "var(--brand)"],
              trial_ended: ["⌛", "انتهت — لم يشترك", "#fbbf24"],
              signed_up: ["⏳", "سجّل فقط", "var(--txt-3)"],
            };
            return (
              <div key={r.code} style={{ borderTop: "1px solid rgba(255,255,255,.05)" }}>
                <div onClick={() => setOpenRef(open ? null : r.code)}
                  style={{
                    display: "flex", alignItems: "center", gap: 9,
                    padding: "10px 0", fontSize: 12.5, cursor: "pointer",
                  }}>
                  <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{open ? "▾" : "▸"}</span>
                  <span style={{ fontWeight: 700, color: "var(--brand)", direction: "ltr" }}>{r.code}</span>
                  <span style={{ flex: 1, color: "var(--txt-1)", fontWeight: 600 }}>{r.name}</span>
                  <span style={{ fontSize: 11, color: "var(--txt-3)" }}>
                    {r.invited} سجّل
                  </span>
                  <span style={{
                    fontSize: 11, fontWeight: 800, padding: "2px 8px", borderRadius: 6,
                    background: r.converted ? "rgba(34,197,94,.14)" : "rgba(255,255,255,.05)",
                    color: r.converted ? "#22c55e" : "var(--txt-3)",
                  }}>
                    💳 {r.converted} دفع
                  </span>
                  <span style={{ fontWeight: 800, color: "#22c55e", direction: "ltr" }}>${r.earned}</span>
                </div>

                {open && (
                  <div style={{
                    padding: "4px 0 12px", marginInlineStart: 18,
                    borderInlineStart: "2px solid rgba(45,212,191,.25)",
                    paddingInlineStart: 12,
                  }}>
                    <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 7 }}>
                      {r.email} · مدفوع ${r.paid_out} · مستحقّ ${r.owed}
                    </div>
                    {(r.people || []).length === 0 ? (
                      <div style={{ fontSize: 11.5, color: "var(--txt-3)" }}>
                        أنشأ رابطاً ولم يدعُ أحداً بعد
                      </div>
                    ) : r.people.map((p, j) => {
                      const [ic, lbl, col] = ST[p.state] || ST.signed_up;
                      return (
                        <div key={j} style={{
                          display: "flex", alignItems: "center", gap: 8,
                          padding: "6px 0", fontSize: 12,
                        }}>
                          <span>{ic}</span>
                          <span style={{ flex: 1, color: "var(--txt-2)" }}>{p.name}</span>
                          <span style={{ fontSize: 10.5, color: col }}>{lbl}</span>
                          {p.earned > 0 && (
                            <span style={{ fontSize: 11.5, fontWeight: 700, color: "#22c55e", direction: "ltr" }}>
                              +${p.earned}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
