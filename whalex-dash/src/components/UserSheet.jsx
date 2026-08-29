// 👤 ملف المشترك — تفعيل، إلغاء، ونتائج التداول
import { useEffect, useState } from "react";
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
            <div style={{ fontSize: 15, fontWeight: 800 }}>{d?.email || "مشترك"}</div>
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
        {sentLog.length > 0 && (
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 14, lineHeight: 1.8 }}>
            آخر رسالة: {String(sentLog[0]?.message || "").slice(0, 60)}
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

        {d?.ledger && d.ledger.closed > 0 && (
          <div style={{ padding: 12, borderRadius: 12, marginBottom: 14, background: "rgba(74,222,128,0.07)", border: "1px solid rgba(74,222,128,0.2)" }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 9 }}>💰 أرباحه الحقيقية على باينانس</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 7, marginBottom: 9 }}>
              <div style={{ padding: "9px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 9 }}>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>صفقات مغلقة</div>
                <div style={{ fontSize: 15, fontWeight: 800 }}>{d.ledger.closed} <span style={{ fontSize: 11, color: "var(--txt-3)" }}>({d.ledger.open} مفتوحة)</span></div>
              </div>
              <div style={{ padding: "9px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 9 }}>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>نسبة النجاح</div>
                <div style={{ fontSize: 15, fontWeight: 800 }}>{d.ledger.win_rate}%</div>
              </div>
              <div style={{ padding: "9px 10px", background: "rgba(34,197,94,0.10)", borderRadius: 9 }}>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>رابحة</div>
                <div style={{ fontSize: 15, fontWeight: 800, color: "#22c55e" }}>{d.ledger.wins}</div>
              </div>
              <div style={{ padding: "9px 10px", background: "rgba(239,68,68,0.10)", borderRadius: 9 }}>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>خاسرة</div>
                <div style={{ fontSize: 15, fontWeight: 800, color: "#ef4444" }}>{d.ledger.losses}</div>
              </div>
            </div>
            <div style={{
              padding: "10px 12px", borderRadius: 9, textAlign: "center",
              background: (d.ledger.net_usdt || 0) >= 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            }}>
              <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>صافي الربح الفعلي</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: (d.ledger.net_usdt || 0) >= 0 ? "#22c55e" : "#ef4444" }} dir="ltr">
                {(d.ledger.net_usdt || 0) >= 0 ? "+" : ""}{d.ledger.net_usdt} USDT
              </div>
              <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }} dir="ltr">
                ({(d.ledger.net_pct || 0) >= 0 ? "+" : ""}{d.ledger.net_pct}%)
              </div>
            </div>
            {(d.ledger.recent || []).length > 0 && (
              <div style={{ display: "grid", gap: 4, marginTop: 9 }}>
                {d.ledger.recent.slice(0, 5).map((t, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, padding: "6px 9px", background: "rgba(255,255,255,0.03)", borderRadius: 7 }}>
                    <span><b>{t.symbol}</b> · {t.direction}</span>
                    <span style={{ color: t.pnl_pct >= 0 ? "#22c55e" : "#ef4444", fontWeight: 700 }} dir="ltr">
                      {t.pnl_pct >= 0 ? "+" : ""}{Number(t.pnl_pct).toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>📊 تداوله الفعلي</div>
        {d?.auto_trades && d.auto_trades.total > 0 ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 7, marginBottom: 10 }}>
              <div style={{ padding: "10px 8px", background: "rgba(255,255,255,0.04)", borderRadius: 10, textAlign: "center" }}>
                <div style={{ fontSize: 17, fontWeight: 800 }}>{d.auto_trades.total}</div>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>إشارة وصلته</div>
              </div>
              <div style={{ padding: "10px 8px", background: "rgba(34,197,94,0.10)", borderRadius: 10, textAlign: "center" }}>
                <div style={{ fontSize: 17, fontWeight: 800, color: "#22c55e" }}>{d.auto_trades.executed}</div>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>نُفّذت فعلياً</div>
              </div>
              <div style={{ padding: "10px 8px", background: "rgba(239,68,68,0.10)", borderRadius: 10, textAlign: "center" }}>
                <div style={{ fontSize: 17, fontWeight: 800, color: "#ef4444" }}>{d.auto_trades.failed}</div>
                <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>فشلت</div>
              </div>
            </div>
            {(d.auto_trades.last || []).length > 0 && (
              <div style={{ display: "grid", gap: 5, marginBottom: 6 }}>
                {d.auto_trades.last.map((t, i) => (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px 10px", background: "rgba(255,255,255,0.03)", borderRadius: 8, fontSize: 11.5,
                  }}>
                    <span><b>{t.signal_symbol}</b> · {t.signal_direction}</span>
                    <span style={{ color: t.executed ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                      {t.executed ? "نُفّذت" : "فشلت"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div style={{
            padding: 12, borderRadius: 10, background: "rgba(255,255,255,0.03)",
            fontSize: 12, color: "var(--txt-3)", lineHeight: 1.7,
          }}>
            لا توجد صفقات منفَّذة لهذا المشترك — لم يربط باينانس أو لم يفعّل التداول الآلي بعد.
          </div>
        )}

        <div style={{ fontSize: 12.5, fontWeight: 700, margin: "14px 0 8px" }}>📈 أداء إشارات المنصة</div>
        <M name="الفيوتشر" icon="⚡" m={d?.markets?.futures} />
        <M name="السبوت" icon="🪙" m={d?.markets?.spot} />
        <M name="الميم" icon="🐸" m={d?.markets?.meme} />
      </div>
    </div>
  );
}
