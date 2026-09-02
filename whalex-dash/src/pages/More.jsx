import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";

/* المسارات والتسميات مأخوذة حرفياً من lib/pages.js */
const SHORTCUTS = [
  { p: "/auto-trade",   t: "التداول الآليّ", e: "Auto Trade", i: "🤖" },
  { p: "/positions",    t: "المراكز", e: "Positions", i: "📊" },
  { p: "/referral",     t: "الإحالة", e: "Referral", i: "🎁" },
  { p: "/support",      t: "خدمة العملاء", e: "Support", i: "💬" },
];

const SERVICES = [
  { p: "/",             t: "الرئيسية", e: "Home", i: "🏠" },
  { p: "/signals",      t: "الإشارات", e: "Signals", i: "📡" },
  { p: "/live",         t: "المفتوحة", e: "Live", i: "⚡" },
  { p: "/trades",       t: "صفقاتي", e: "My Trades", i: "📈" },
  { p: "/history",      t: "السجلّ الزمنيّ", e: "History", i: "🗓️" },
  { p: "/scanner",      t: "فاحص العملات", e: "Scanner", i: "🔍" },
  { p: "/subscription", t: "الاشتراك", e: "Subscription", i: "💳" },
  { p: "/api-guide",    t: "دليل الاستخدام", e: "API Guide", i: "🔗" },
  { p: "/settings",     t: "الإعدادات", e: "Settings", i: "⚙️" },
  { p: "/profile",      t: "حسابي", e: "Profile", i: "👤" },
  { p: "/landing",      t: "عن المنصّة", e: "About", i: "✨" },
];

const ADMIN_TILE = { p: "/admin", t: "لوحة الإدارة", e: "Admin", i: "🛡️" };

function Tile({ item, onGo, en }) {
  return (
    <button
      onClick={() => onGo(item.p)}
      style={{
        background: "none", border: "none", padding: 0, cursor: "pointer",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 7,
      }}
    >
      <div style={{
        width: 54, height: 54, borderRadius: 14,
        background: "rgba(255,255,255,.06)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 24,
      }}>{item.i}</div>
      <span style={{
        fontSize: 11.5, color: "var(--txt-2)", textAlign: "center",
        lineHeight: 1.25, maxWidth: 70,
      }}>{en && item.e ? item.e : item.t}</span>
    </button>
  );
}

function Grid({ items, onGo, en }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
      gap: "18px 8px", marginTop: 14,
    }}>
      {items.map((x) => <Tile key={x.p + x.t} item={x} onGo={onGo} en={en} />)}
    </div>
  );
}

export default function More() {
  const nav = useNavigate();
  const { user } = useAuth();
  const { lang } = useLang();
  const en = lang === "en";
  const [q, setQ] = useState("");

  const name = user?.username || user?.email || "مشترك";
  const uid = user?.display_id || (user?.uid || user?.id || "").slice(0, 8).toUpperCase();
  const tier = user?.tier === "admin" ? "أدمن"
    : user?.is_pro ? "Pro" : "عادي";

  const isAdmin = user?.tier === "admin";
  const services = useMemo(
    () => (isAdmin ? [...SERVICES, ADMIN_TILE] : SERVICES), [isAdmin]);
  const all = useMemo(() => [...SHORTCUTS, ...services], [services]);
  /* تطبيع عربيّ — "اشارات" تجد "الإشارات" */
  const norm = (t) => (t || "")
    .replace(/[أإآ]/g, "ا").replace(/ى/g, "ي")
    .replace(/ة/g, "ه").replace(/[ًٌٍَُِّْـ]/g, "");
  const found = useMemo(() => {
    const s = norm(q.trim());
    if (!s) return null;
    return all.filter((x) => norm(x.t).includes(s));
  }, [q, all]);

  const copyId = async () => {
    try { await navigator.clipboard.writeText(uid); }
    catch {
      const t = document.createElement("textarea");
      t.value = uid; document.body.appendChild(t);
      t.select(); document.execCommand("copy"); t.remove();
    }
    window.dispatchEvent(new CustomEvent("wx-toast",
      { detail: { message: "نُسخ المعرّف ✓" } }));
  };

  return (
    <div style={{ padding: "8px 14px 90px" }}>

      {/* بطاقة الحساب */}
      <div
        onClick={() => nav("/profile")}
        style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "16px 4px 20px", cursor: "pointer",
        }}
      >
        <div style={{
          width: 58, height: 58, borderRadius: "50%",
          background: "linear-gradient(135deg,#2a78d6,#4aa3ff)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 24, fontWeight: 800, color: "#fff", flexShrink: 0,
        }}>{(name[0] || "?").toUpperCase()}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 12, color: "var(--txt-3)",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <span>ID: {uid}</span>
            <span
              onClick={(e) => { e.stopPropagation(); copyId(); }}
              style={{ cursor: "pointer", opacity: .75 }}
            >📋</span>
          </div>
          <div style={{
            fontSize: 19, fontWeight: 800, marginTop: 2,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{name}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            <span style={{
              fontSize: 10.5, padding: "2px 9px", borderRadius: 5,
              background: "rgba(46,160,110,.18)", color: "#4bcf92",
            }}>{en ? "Verified" : "مُوثّق"}</span>
            <span style={{
              fontSize: 10.5, padding: "2px 9px", borderRadius: 5,
              background: "rgba(214,168,42,.18)", color: "#e0b73f",
            }}>{tier}</span>
          </div>
        </div>
        <span style={{ color: "var(--txt-3)", fontSize: 20 }}>›</span>
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={en ? "🔍 Search services..." : "🔍 ابحث عن خدمة..."}
        style={{
          width: "100%", padding: "11px 14px", borderRadius: 11,
          border: "1px solid rgba(255,255,255,.09)",
          background: "rgba(255,255,255,.05)", color: "var(--txt-1)",
          fontSize: 14, outline: "none", boxSizing: "border-box",
        }}
      />

      {found ? (
        <>
          <div style={{
            fontSize: 13, color: "var(--txt-3)", marginTop: 18,
          }}>{found.length} نتيجة</div>
          <Grid items={found} onGo={nav} en={en} />
        </>
      ) : (
        <>
          <div style={{
            fontSize: 15, fontWeight: 700, marginTop: 22,
          }}>{en ? "Shortcuts" : "الاختصار"}</div>
          <Grid items={SHORTCUTS} onGo={nav} en={en} />

          <div style={{
            fontSize: 15, fontWeight: 700, marginTop: 28,
          }}>{en ? "Services" : "الخدمات"}</div>
          <Grid items={services} onGo={nav} en={en} />
        </>
      )}
    </div>
  );
}
