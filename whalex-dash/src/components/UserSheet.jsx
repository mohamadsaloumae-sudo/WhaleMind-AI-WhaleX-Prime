// 👤 ملف المشترك — تفعيل، إلغاء، ونتائج التداول
import { useEffect, useState } from "react";
import UserLedger from "./UserLedger.jsx";
import { X, Check, Ban, Send } from "lucide-react";
import { api } from "../lib/api.js";

const DURATIONS = [7, 30, 90, 180, 365];

export default function UserSheet({ userId, onClose, onChanged }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [days, setDays] = useState(30);
  const [msg, setMsg] = useState("");
  const [dm, setDm] = useState("");
  const [sentLog, setSentLog] = useState([]);

  async function sendDm() {
    const t = dm.trim();
    if (!t) return;
    setBusy(true);
    try {
      await api.post(`/api/admin/users/${userId}/message`, { message: t });
      setDm(""); setMsg("✉️ أُرسلت الرسالة");
      const h = await api.get(`/api/admin/users/${userId}/messages`);
      setSentLog(h?.messages || []);
    } catch { setMsg("⚠️ فشل الإرسال"); }
    setBusy(false);
  }

  async function load() {
    try {
      const r = await api.get(`/api/admin/users/${userId}/detail`);
      setD(r);
    } catch { setD({ error: true }); }
  }
  useEffect(() => { load(); }, [userId]);

  async function grant() {
    setBusy(true); setMsg("");
    try {
      const r = await api.post(`/api/admin/users/${userId}/grant-custom`, { days });
      setMsg(`✅ فُعّل ${days} يوماً`);
      await load(); onChanged && onChanged();
    } catch { setMsg("⚠️ فشل التفعيل"); }
    setBusy(false);
  }

  async function cancel() {
    if (!confirm("إلغاء اشتراك هذا المستخدم وسحب وصوله للقنوات؟")) return;
    setBusy(true); setMsg("");
    try {
      await api.post(`/api/admin/users/${userId}/cancel-sub`, {});
      setMsg("🔒 أُلغي الاشتراك");
      await load(); onChanged && onChanged();
    } catch { setMsg("⚠️ فشل الإلغاء"); }
    setBusy(false);
  }

  const M = ({ name, icon, m }) => (
    <div style={{ padding: "10px 12px", background: "rgba(255,255,255,0.04)", borderRadius: 10, marginBottom: 7 }}>
      <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 6 }}>{icon} {name}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 6, fontSize: 11.5 }}>
        <span style={{ color: "var(--txt-3)" }}>صفقات <b style={{ color: "var(--txt-1)" }}>{m?.trades ?? 0}</b></span>
        <span style={{ color: "#22c55e" }}>رابحة <b>{m?.wins ?? 0}</b></span>
        <span style={{ color: "#ef4444" }}>خاسرة <b>{m?.losses ?? 0}</b></span>
        <span style={{ color: "var(--txt-3)" }}>نجاح <b style={{ color: "var(--txt-1)" }}>{m?.win_rate ?? 0}%</b></span>
        <span style={{ color: "#22c55e" }}>+{m?.profit ?? 0}%</span>
        <span style={{ color: (m?.net ?? 0) >= 0 ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
          صافي {(m?.net ?? 0) >= 0 ? "+" : ""}{m?.net ?? 0}%
        </span>
      </div>
    </div>
  );

  const sub = d?.subscription;

  const [_pt, _setPt] = useState("futures");
  const [_det, _setDet] = useState(null);
  const [_rep, _setRep] = useState("");
  const [_msg, _setMsg] = useState("");
  const [_frm, _setFrm] = useState("");
  const [_to, _setTo] = useState("");
  const [_prev, _setPrev] = useState(null);
  const _n = (v, d) => (v == null || isNaN(v)) ? "—"
    : (Number(v) < 0.01 && Number(v) > 0
       ? Number(v).toFixed(8).replace(/0+$/, "")
       : Number(v).toFixed(d || 4));
  const _ts = (t) => { if (!t) return "—";
    const x = new Date(Number(t) * 1000), p = (n) => String(n).padStart(2, "0");
    return `${p(x.getDate())}/${p(x.getMonth() + 1)} ${p(x.getHours())}:${p(x.getMinutes())}`; };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 1400, background: "rgba(4,6,12,0.66)", backdropFilter: "blur(3px)", display: "flex", alignItems: "flex-end" }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: "100%", maxHeight: "88vh", overflowY: "auto",
        background: "var(--bg-1, #0b0e16)", borderRadius: "18px 18px 0 0",
        padding: "16px 16px calc(env(safe-area-inset-bottom,0px) + 20px)",
        borderTop: "1px solid rgba(255,255,255,0.09)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 800 }}>{d?.username || d?.email || "مشترك"}</div>
            {d?.email && d?.username && (
              <div style={{ fontSize: 11.5, color: "var(--txt-2)" }}>{d.email}</div>
            )}
            <div style={{ fontSize: 10.5, color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis" }}>{userId}</div>
          </div>
          <button onClick={onClose} style={{ background: "rgba(255,255,255,0.06)", border: "none", color: "inherit", width: 32, height: 32, borderRadius: 9, cursor: "pointer" }}><X size={17} /></button>
        </div>

        <div style={{
          padding: 12, borderRadius: 12, marginBottom: 14,
          background: sub?.active ? "rgba(34,197,94,0.10)" : "rgba(239,68,68,0.10)",
          border: `1px solid ${sub?.active ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: sub?.active ? "#22c55e" : "#ef4444" }}>
            {sub?.active ? `✅ اشتراك فعّال — ${sub.days_left} يوماً متبقية` : "🔒 لا اشتراك فعّال"}
          </div>
          {sub?.expires_at && <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 3 }}>ينتهي: {String(sub.expires_at).slice(0, 16)}</div>}
        </div>

        {d?.profile && (d.profile.ip || d.profile.phone || d.profile.country) && (
          <div style={{ padding: 12, borderRadius: 12, marginBottom: 14, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>🌐 بيانات الاتصال</div>
            <div style={{ display: "grid", gap: 5, fontSize: 11.5, color: "var(--txt-3)" }}>
              {d.profile.country && <div>الدولة: <b style={{ color: "var(--txt-1)" }}>{d.profile.flag} {d.profile.country}{d.profile.city ? " · " + d.profile.city : ""}</b></div>}
              {d.profile.phone && <div>الهاتف: <b style={{ color: "#25D366" }} dir="ltr">{d.profile.phone}</b></div>}
              {d.profile.ip && <div>العنوان الحالي: <b style={{ color: "var(--txt-1)" }} dir="ltr">{d.profile.ip}</b></div>}
              {d.profile.prev_ip && d.profile.prev_ip !== d.profile.ip && <div>السابق: <span dir="ltr">{d.profile.prev_ip}</span></div>}
              {d.profile.isp && <div>المزوّد: <b style={{ color: "var(--txt-1)" }}>{d.profile.isp}</b></div>}
              {d.profile.last_seen && <div>آخر دخول: <b style={{ color: "var(--txt-1)" }}>{new Date(d.profile.last_seen * 1000).toLocaleString("ar-AE", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</b></div>}
            </div>
          </div>
        )}

        <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>🎁 تفعيل مجاني</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
          {DURATIONS.map((n) => (
            <button key={n} onClick={() => setDays(n)} style={{
              padding: "7px 13px", borderRadius: 9, fontSize: 12, cursor: "pointer",
              border: days === n ? "1px solid var(--brand)" : "1px solid rgba(255,255,255,0.12)",
              background: days === n ? "rgba(74,222,128,0.15)" : "transparent",
              color: days === n ? "var(--brand)" : "var(--txt-2)", fontWeight: days === n ? 700 : 500,
            }}>{n} يوم</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <button onClick={grant} disabled={busy} style={{
            flex: 1, background: "var(--brand)", color: "#06110a", border: "none", borderRadius: 10,
            padding: "11px", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: busy ? .5 : 1,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}><Check size={16} /> تفعيل {days} يوم</button>
          <button onClick={cancel} disabled={busy} style={{
            background: "rgba(239,68,68,0.14)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 10, padding: "11px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6,
          }}><Ban size={16} /> إلغاء</button>
        </div>
        {msg && <div style={{ fontSize: 12.5, marginBottom: 12, color: "var(--brand)" }}>{msg}</div>}

        <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>✉️ رسالة خاصة</div>
        <div style={{ display: "flex", gap: 7, marginBottom: 8 }}>
          <input
            value={dm}
            onChange={(e) => setDm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendDm()}
            placeholder="اكتب رسالة تصله وحده..."
            style={{
              flex: 1, minWidth: 0, background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10,
              padding: "10px 12px", color: "inherit", fontSize: 13, outline: "none",
            }}
          />
          <button onClick={sendDm} disabled={busy} style={{
            background: "var(--accent, #38bdf8)", border: "none", borderRadius: 10, width: 44,
            display: "grid", placeItems: "center", cursor: "pointer", color: "#04121a", opacity: busy ? .5 : 1,
          }}><Send size={16} /></button>
        </div>
        {/* 💬 المحادثة كاملةً — كانت سطراً واحداً بلا وقت ولا سجلّ،
            فلا نرى ما أرسلناه ولا متى. والقائمة مقلوبة (الأحدث أوّلاً)
            من الواجهة، فنعكسها لتقرأ كأي دردشة. */}
        {sentLog.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>
              💬 المحادثة ({sentLog.length})
            </div>
            <div style={{
              maxHeight: 300, overflowY: "auto", padding: "8px 4px",
              background: "rgba(255,255,255,0.02)", borderRadius: 10,
            }}>
              {[...sentLog].reverse().map((m, i, arr) => {
                const dmStamp = (ts) => {
                  if (!ts) return "";
                  const d = new Date(Number(ts) * 1000);
                  return d.toLocaleTimeString("ar-AE", {
                    timeZone: "Asia/Dubai", hour: "2-digit", minute: "2-digit" });
                };
                const dmDay = (ts) => {
                  if (!ts) return "";
                  return new Date(Number(ts) * 1000)
                    .toLocaleDateString("ar-AE", { timeZone: "Asia/Dubai" });
                };
                const dmLabel = (ts) => {
                  const k = dmDay(ts);
                  const now = new Date();
                  const today = now.toLocaleDateString("ar-AE", { timeZone: "Asia/Dubai" });
                  const y = new Date(now.getTime() - 86400000)
                    .toLocaleDateString("ar-AE", { timeZone: "Asia/Dubai" });
                  if (k === today) return "اليوم";
                  if (k === y) return "أمس";
                  return k;
                };
                const newDay = i === 0 || dmDay(m.created_at) !== dmDay(arr[i - 1]?.created_at);
                return (
                  <div key={i}>
                    {newDay && (
                      <div style={{ textAlign: "center", margin: "8px 0 10px" }}>
                        <span style={{
                          fontSize: 10, color: "var(--txt-3)",
                          background: "rgba(255,255,255,0.06)",
                          padding: "3px 11px", borderRadius: 10,
                        }}>{dmLabel(m.created_at)}</span>
                      </div>
                    )}
                    <div style={{
                      marginInlineStart: "auto", maxWidth: "88%", width: "fit-content",
                      background: "rgba(45,212,191,0.13)",
                      borderRadius: "12px 12px 4px 12px",
                      padding: "8px 11px", marginBottom: 7,
                      fontSize: 12, lineHeight: 1.75, whiteSpace: "pre-wrap",
                    }}>
                      {m.message}
                      <div dir="ltr" style={{ fontSize: 9.5, opacity: .55, marginTop: 3 }}>
                        {dmStamp(m.created_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {d?.link_check && (
          <div style={{
            padding: 12, borderRadius: 12, marginBottom: 14,
            background: d.link_check.ok ? "rgba(34,197,94,0.07)" : "rgba(234,179,8,0.07)",
            border: "1px solid " + (d.link_check.ok ? "rgba(34,197,94,0.25)" : "rgba(234,179,8,0.3)"),
          }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 9 }}>
              🔑 حالة الربط بباينانس
              {d.link_check.ok ? (
                <span style={{ color: "#22c55e", marginInlineStart: 8 }}>✓ سليم</span>
              ) : (
                <span style={{ color: "#eab308", marginInlineStart: 8 }}>
                  {(d.link_check.problems || []).length} مشكلة
                </span>
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 6, marginBottom: 9 }}>
              {[
                ["المفتاح", d.link_check.key_valid],
                ["تداول فيوتشر", d.link_check.futures_enabled],
                ["تداول سبوت", d.link_check.spot_enabled],
                ["قائمة العناوين", d.link_check.ip_restricted],
                ["التداول الآليّ", d.link_check.auto_trade_on],
                ["السحب مغلق", d.link_check.withdraw_enabled === false],
              ].map(([k, v], i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between",
                  padding: "7px 9px", background: "rgba(255,255,255,0.04)",
                  borderRadius: 8, fontSize: 11.5,
                }}>
                  <span style={{ color: "var(--txt-3)" }}>{k}</span>
                  <span style={{ color: v === true ? "#22c55e" : v === false ? "#ef4444" : "var(--txt-3)", fontWeight: 700 }}>
                    {v === true ? "✓" : v === false ? "✗" : "—"}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 7, marginBottom: 9 }}>
              <div style={{ flex: 1, padding: "8px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 8 }}>
                <div style={{ fontSize: 10, color: "var(--txt-3)" }}>رصيد الفيوتشر</div>
                <div style={{ fontSize: 13.5, fontWeight: 800 }} dir="ltr">
                  {d.link_check.futures_balance == null ? "—" : d.link_check.futures_balance.toFixed(2) + "$"}
                </div>
              </div>
              <div style={{ flex: 1, padding: "8px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 8 }}>
                <div style={{ fontSize: 10, color: "var(--txt-3)" }}>رصيد السبوت</div>
                <div style={{ fontSize: 13.5, fontWeight: 800 }} dir="ltr">
                  {d.link_check.spot_balance == null ? "—" : d.link_check.spot_balance.toFixed(2) + "$"}
                </div>
              </div>
            </div>
            {/* 📤 كشف الحساب — معاينة ثم ارسال */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: "var(--txt-3)",
                            marginBottom: 6 }}>كشف الحساب</div>
              <div style={{ display: "flex", gap: 5, alignItems: "center",
                            marginBottom: 6 }}>
                <input type="date" value={_frm}
                  onChange={(e) => { _setFrm(e.target.value); _setPrev(null); }}
                  style={{ flex: 1, padding: "6px 7px", borderRadius: 6,
                    border: "1px solid rgba(255,255,255,.1)", fontSize: 11,
                    background: "rgba(255,255,255,.04)", color: "var(--txt-2)",
                    fontFamily: "inherit" }} />
                <span style={{ fontSize: 10, color: "var(--txt-3)" }}>إلى</span>
                <input type="date" value={_to}
                  onChange={(e) => { _setTo(e.target.value); _setPrev(null); }}
                  style={{ flex: 1, padding: "6px 7px", borderRadius: 6,
                    border: "1px solid rgba(255,255,255,.1)", fontSize: 11,
                    background: "rgba(255,255,255,.04)", color: "var(--txt-2)",
                    fontFamily: "inherit" }} />
              </div>
              <button disabled={_rep === "p"}
                onClick={async () => {
                  _setRep("p"); _setMsg(""); _setPrev(null);
                  try {
                    const q = new URLSearchParams({ period: "full" });
                    if (_frm) q.set("frm", _frm);
                    if (_to) q.set("to", _to);
                    q.delete("period");
                    const r = await api.get(
                      `/api/admin/users/${userId}/report/rows?${q}`);
                    if (r?.ok) _setPrev(r);
                    else _setMsg("⚠️ " + (r?.error || "فشل"));
                  } catch (e) { _setMsg("⚠️ " + (e?.message || "فشل")); }
                  _setRep("");
                }}
                style={{ width: "100%", padding: "9px", borderRadius: 8,
                  border: "1px solid var(--brand)", background:
                  "rgba(45,212,191,.12)", color: "var(--brand)",
                  fontSize: 12.5, fontWeight: 700, cursor: "pointer",
                  fontFamily: "inherit" }}>
                {_rep === "p" ? "جارٍ…" : "👁️ عرض الكشف"}
              </button>
              {_prev && _prev.rows && (
                <>
                  <div style={{ marginTop: 8, maxHeight: 360,
                    overflow: "auto", borderRadius: 8,
                    border: "1px solid rgba(255,255,255,.08)" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse",
                      fontSize: 10.5, direction: "rtl" }}>
                      <thead><tr style={{ background: "rgba(0,0,0,.35)",
                        position: "sticky", top: 0 }}>
                        {["العملة", "الاتجاه", "الدخول", "الخروج",
                          "الكمّية", "الرافعة", "النتيجة", "الرسوم",
                          "الصافي", "التراكميّ", "السبب", "فُتحت",
                          "أُغلقت"].map((h) => (
                          <th key={h} style={{ padding: "6px 5px",
                            color: "var(--txt-3)", fontWeight: 700,
                            whiteSpace: "nowrap", textAlign: "center",
                            borderBottom: "1px solid rgba(255,255,255,.1)"
                          }}>{h}</th>))}
                      </tr></thead>
                      <tbody>
                        {(_prev.rows || []).map((r, i) => {
                          const g = (r.pnl_pct || 0) >= 0;
                          const td = { padding: "5px 5px", textAlign: "center",
                            whiteSpace: "nowrap",
                            borderBottom: "1px solid rgba(255,255,255,.05)" };
                          return (
                          <tr key={i} style={{ background: r.open
                            ? "rgba(234,179,8,.07)" : "transparent" }}>
                            <td style={{ ...td, fontWeight: 700 }} dir="ltr">
                              {r.market === "spot" ? "🪙" : "⚡"} {r.symbol}</td>
                            <td style={td}>{r.direction || "—"}</td>
                            <td style={td} dir="ltr">{_n(r.entry)}</td>
                            <td style={td} dir="ltr">{r.open ? "—" : _n(r.exit)}</td>
                            <td style={td} dir="ltr">{_n(r.qty, 2)}</td>
                            <td style={td} dir="ltr">
                              {r.leverage > 1 ? r.leverage + "x" : "—"}</td>
                            <td style={{ ...td, fontWeight: 800,
                              color: r.open ? "var(--txt-3)"
                                : (g ? "#22c55e" : "#ef4444") }} dir="ltr">
                              {r.open ? "مفتوحة"
                                : (g ? "+" : "") + (r.pnl_pct || 0).toFixed(2) + "%"}</td>
                            <td style={{ ...td, color: "#eab308" }} dir="ltr">
                              {r.fee ? "-" + Number(r.fee).toFixed(3) : "—"}</td>
                            <td style={{ ...td, fontWeight: 700,
                              color: (r.net || 0) >= 0 ? "#22c55e" : "#ef4444"
                            }} dir="ltr">
                              {r.net == null ? "—"
                                : ((r.net >= 0 ? "+" : "") + r.net.toFixed(2) + "$")}</td>
                            <td style={{ ...td, color: "var(--txt-3)" }} dir="ltr">
                              {r.running == null ? "—"
                                : ((r.running >= 0 ? "+" : "") + r.running.toFixed(2))}</td>
                            <td style={{ ...td, fontSize: 10 }}>{r.reason || "—"}</td>
                            <td style={{ ...td, color: "var(--txt-3)",
                              fontSize: 10 }} dir="ltr">{_ts(r.opened_at)}</td>
                            <td style={{ ...td, color: "var(--txt-3)",
                              fontSize: 10 }} dir="ltr">{_ts(r.closed_at)}</td>
                          </tr>);
                        })}
                      </tbody>
                    </table>
                  </div>
                  {_prev.summary && (
                    <div style={{ marginTop: 6, padding: "8px 10px",
                      borderRadius: 8, background: "rgba(0,0,0,.25)",
                      fontSize: 11.5, display: "grid",
                      gridTemplateColumns: "repeat(auto-fit,minmax(105px,1fr))",
                      gap: 6 }}>
                      {[["المغلقة", _prev.summary.n],
                        ["رابحة", _prev.summary.wins],
                        ["خاسرة", _prev.summary.losses],
                        ["النجاح", _prev.summary.win_rate + "%"],
                        ["الخام", _prev.summary.gross + "$"],
                        ["الرسوم", "-" + _prev.summary.fees + "$"],
                        ["الصافي", (_prev.summary.net >= 0 ? "+" : "")
                          + _prev.summary.net + "$"],
                        ["مفتوحة", _prev.summary.open]].map(([k, v], j) => (
                        <div key={j}>
                          <div style={{ fontSize: 9.5, color: "var(--txt-3)"
                          }}>{k}</div>
                          <div dir="ltr" style={{ fontWeight: 800,
                            color: k === "الصافي"
                              ? (_prev.summary.net >= 0 ? "#22c55e" : "#ef4444")
                              : "var(--txt-1)" }}>{v}</div>
                        </div>))}
                    </div>
                  )}
                  <button disabled={_rep === "s"}
                    onClick={async () => {
                      _setRep("s"); _setMsg("");
                      try {
                        const q = new URLSearchParams({ period: "full" });
                        if (_frm) q.set("frm", _frm);
                        if (_to) q.set("to", _to);
                        const r = await api.post(
                          `/api/admin/users/${userId}/report?${q}`, {});
                        _setMsg(r?.ok ? "✅ أُرسل للمشترك"
                                      : "⚠️ " + (r?.error || "فشل"));
                      } catch (e) { _setMsg("⚠️ " + (e?.message || "فشل")); }
                      _setRep("");
                    }}
                    style={{ width: "100%", marginTop: 6, padding: "9px",
                      borderRadius: 8, border: "none",
                      background: "var(--brand)", color: "#03151a",
                      fontSize: 12.5, fontWeight: 800, cursor: "pointer",
                      fontFamily: "inherit" }}>
                    {_rep === "s" ? "جارٍ الإرسال…" : "📤 إرسال للمشترك"}
                  </button>
                </>
              )}
              {_msg && <div style={{ fontSize: 11.5, marginTop: 6,
                textAlign: "center",
                color: _msg[0] === "✅" ? "#22c55e" : "#eab308" }}>{_msg}</div>}
            </div>

            {/* 📊 مراكزه المفتوحة — فيوتشر وسبوت بتبويبين منفصلين.
                كان الادمن لا يرى شيئاً فلا يعرف ما يجري في حسابه. */}
            {(() => {
              const _f = d.positions?.futures || [];
              const _s = d.positions?.spot || [];
              if (!_f.length && !_s.length) return null;
              const _cur = _pt === "spot" ? _s : _f;
              return (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, color: "var(--txt-3)",
                                marginBottom: 6 }}>المراكز المفتوحة</div>
                  <div style={{ display: "flex", gap: 6, marginBottom: 7 }}>
                    {[["futures", "⚡ فيوتشر", _f.length],
                      ["spot", "🪙 سبوت", _s.length]].map(([k, lbl, n]) => (
                      <button key={k} onClick={() => _setPt(k)} style={{
                        flex: 1, padding: "6px 4px", borderRadius: 7,
                        border: _pt === k ? "1px solid var(--brand)"
                                          : "1px solid rgba(255,255,255,.1)",
                        background: _pt === k ? "rgba(45,212,191,.12)"
                                              : "transparent",
                        color: _pt === k ? "var(--brand)" : "var(--txt-3)",
                        fontSize: 11.5, fontWeight: 700, cursor: "pointer",
                        fontFamily: "inherit",
                      }}>{lbl} ({n})</button>
                    ))}
                  </div>
                  {_cur.length === 0 ? (
                    <div style={{ fontSize: 11, color: "var(--txt-3)",
                                  padding: "6px 2px" }}>لا مراكز</div>
                  ) : _cur.map((x, i) => {
                    const _k = _pt + i;
                    const _op = _det === _k;
                    const _fn = (v, dd) => (v == null || isNaN(v)) ? "—"
                      : Number(v) < 0.01 ? Number(v).toFixed(dd || 8)
                      : Number(v).toFixed(4);
                    const _age = (ts) => {
                      if (!ts) return "—";
                      const m = Math.round((Date.now() / 1000 - Number(ts)) / 60);
                      if (m < 1) return "الآن";
                      if (m < 60) return m + " دقيقة";
                      return Math.floor(m / 60) + " ساعة " + (m % 60) + " د";
                    };
                    const _rows = [];
                    if (x.entry != null) _rows.push(["الدخول", _fn(x.entry)]);
                    if (x.current != null) _rows.push(["الحالي", _fn(x.current)]);
                    if (x.size != null) _rows.push(["الحجم", _fn(x.size, 2)]);
                    if (x.qty != null) _rows.push(["الكمية", _fn(x.qty, 2)]);
                    if (x.spend != null) _rows.push(["المبلغ", x.spend.toFixed(2) + "$"]);
                    if (x.leverage) _rows.push(["الرافعة", x.leverage + "x"]);
                    if (x.exchange) _rows.push(["المنصّة", x.exchange]);
                    if (x.opened_at) _rows.push(["العمر", _age(x.opened_at)]);
                    return (
                    <div key={i} onClick={() => _setDet(_op ? null : _k)}
                      style={{
                      padding: "7px 9px", marginBottom: 4, borderRadius: 7,
                      background: "rgba(255,255,255,.04)", fontSize: 12,
                      cursor: "pointer",
                    }}>
                      <div style={{ display: "flex",
                                    justifyContent: "space-between" }}>
                        <span dir="ltr"><b>{x.symbol}</b>
                          {x.direction ? " · " + x.direction : ""}
                          {x.exchange ? " · " + x.exchange : ""}</span>
                        <span dir="ltr" style={{ fontWeight: 800,
                          color: x.pnl_pct == null ? "var(--txt-2)"
                               : x.pnl_pct >= 0 ? "#22c55e" : "#ef4444" }}>
                          {x.pnl_pct == null
                            ? (x.spend ? x.spend.toFixed(0) + "$" : "—")
                            : (x.pnl_pct >= 0 ? "+" : "") + x.pnl_pct + "%"}
                        </span>
                      </div>
                      {_op && (
                        <div style={{ marginTop: 7, paddingTop: 7,
                          borderTop: "1px solid rgba(255,255,255,.08)",
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit,minmax(88px,1fr))",
                          gap: 6 }}>
                          {_rows.map(([k, v], j) => (
                            <div key={j}>
                              <div style={{ fontSize: 9.5,
                                            color: "var(--txt-3)" }}>{k}</div>
                              <div dir="ltr" style={{ fontSize: 11.5,
                                    fontWeight: 700 }}>{v}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
              );
            })()}
            {(d.link_check.problems || []).length > 0 && (
              <div style={{ marginBottom: 8 }}>
                {d.link_check.problems.map((p, i) => (
                  <div key={i} style={{ fontSize: 11.5, color: "#ef4444", marginBottom: 3 }}>• {p}</div>
                ))}
              </div>
            )}
            {(d.link_check.advice || []).length > 0 && (
              <div style={{ padding: "9px 11px", background: "rgba(45,212,191,0.08)", borderRadius: 9 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--brand, #2dd4bf)", marginBottom: 5 }}>
                  💡 التوجيه — انسخه وأرسله له
                </div>
                {d.link_check.advice.map((a, i) => (
                  <div key={i} style={{ fontSize: 11.5, lineHeight: 1.8 }}>{i + 1}. {a}</div>
                ))}
              </div>
            )}
            {d.link_check.error && (
              <div style={{ fontSize: 11, color: "#eab308", marginTop: 7 }} dir="ltr">
                {d.link_check.error}
              </div>
            )}
          </div>
        )}

        {/* 📒 دفتر الحساب — user_trades وحده (التنفيذ الحقيقي)، مجمّع بالايام */}
        <div style={{ fontSize: 12.5, fontWeight: 700, margin: "18px 0 8px" }}>📒 دفتر الحساب</div>
        {(d?.markets_enabled?.length ? d.markets_enabled : ["futures"]).map((mk) => (
          <UserLedger key={mk} userId={userId} days={30} market={mk} />
        ))}

      </div>
    </div>
  );
}
