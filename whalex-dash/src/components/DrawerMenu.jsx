// ☰ قائمة جانبية — انزلاق ناعم، صفوف مرتّبة، تتبع اتجاه اللغة
import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { PAGES } from "../lib/pages.js";
import { useLang } from "../context/LangContext.jsx";

// 🌐 روابط التواصل — عدّلها هنا فقط

/** صفّ إعداد: عنوان يمين وخيارات يسار */
function Row({ label, children }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "9px 4px",
    }}>
      <span style={{ fontSize: 12.5, color: "var(--txt-2, #b6bdcc)", flex: 1 }}>
        {label}
      </span>
      <div style={{ display: "flex", gap: 6 }}>{children}</div>
    </div>
  );
}

/** زرّ خيار صغير */
function Pill({ on, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      padding: "5px 12px", borderRadius: 8, cursor: "pointer",
      fontSize: 11.5, fontWeight: on ? 800 : 600,
      background: on ? "rgba(74,222,128,.14)" : "transparent",
      border: `1px solid ${on ? "rgba(74,222,128,.45)" : "rgba(255,255,255,.1)"}`,
      color: on ? "var(--brand, #4ade80)" : "var(--txt-3, #6b7688)",
      transition: "all .18s",
    }}>{children}</button>
  );
}

export default function DrawerMenu() {
  const { t, lang, setLang } = useLang();
  const [muted, setMuted] = useState(
    () => localStorage.getItem("wx_sound") === "off"
  );

  function setSound(on) {
    localStorage.setItem("wx_sound", on ? "on" : "off");
    setMuted(!on);
    window.dispatchEvent(new Event("wx-sound"));
  }
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);
  // 🏁 «عن المنصّة» أوّل القائمة — بصرياً فقط، فترتيب PAGES يحكم الشريط السفلي
  const _rest = PAGES.filter((p) => !p.adminOnly).slice(5);
  const _about = _rest.find((p) => p.path === "/landing");
  const pages = _about
    ? [_about, ..._rest.filter((p) => p.path !== "/landing")]
    : _rest;
  const rtl = lang === "ar";

  useEffect(() => {
    if (open) {
      const id = setTimeout(() => setShown(true), 10);
      document.body.style.overflow = "hidden";
      return () => { clearTimeout(id); document.body.style.overflow = ""; };
    }
    setShown(false);
  }, [open]);

  function close() {
    setShown(false);
    setTimeout(() => setOpen(false), 220);
  }

  return (
    <>
      <button className="lang-btn" onClick={() => setOpen(true)} title={t("more")} aria-label="menu">
        <Menu size={18} />
      </button>

      {open && (
        <div
          onClick={close}
          style={{
            position: "fixed", inset: 0, zIndex: 950,
            background: shown ? "rgba(4,6,12,0.6)" : "rgba(4,6,12,0)",
            backdropFilter: shown ? "blur(3px)" : "none",
            transition: "background .22s ease, backdrop-filter .22s ease",
          }}
        >
          <aside
            onClick={(e) => e.stopPropagation()}
            style={{
              position: "absolute", top: 0, bottom: 0, [rtl ? "right" : "left"]: 0,
              width: "min(76vw, 288px)", maxWidth: "100%",
              background: "var(--bg-2, #10141f)",
              [rtl ? "borderLeft" : "borderRight"]: "1px solid rgba(255,255,255,0.07)",
              boxShadow: "0 0 48px rgba(0,0,0,0.55)",
              transform: shown ? "translateX(0)" : `translateX(${rtl ? "100%" : "-100%"})`,
              transition: "transform .24s cubic-bezier(.22,.9,.3,1)",
              display: "flex", flexDirection: "column",
              padding: "calc(env(safe-area-inset-top, 0px) + 14px) 12px calc(env(safe-area-inset-bottom, 0px) + 14px)",
            }}
          >
            <header style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "2px 6px 14px", borderBottom: "1px solid rgba(255,255,255,0.07)", marginBottom: 10,
            }}>
              <span style={{ fontWeight: 700, fontSize: 14.5, letterSpacing: .2, opacity: .95 }}>
                {rtl ? "القائمة" : "Menu"}
              </span>
              <button onClick={close} aria-label="close" style={{
                background: "rgba(255,255,255,0.06)", border: "none", color: "inherit",
                width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", cursor: "pointer",
              }}><X size={17} /></button>
            </header>

            <nav style={{ display: "flex", flexDirection: "column", gap: 3, overflowY: "auto" }}>
              {pages.map((p) => {
                const Icon = p.icon;
                return (
                  <NavLink
                    key={p.path}
                    to={p.path}
                    onClick={close}
                    style={({ isActive }) => ({
                      display: "flex", alignItems: "center", gap: 11,
                      padding: "11px 10px", borderRadius: 11, textDecoration: "none",
                      fontSize: 14, fontWeight: isActive ? 700 : 500,
                      color: isActive ? "var(--brand, #4ade80)" : "var(--txt-2, #b6bdcc)",
                      background: isActive ? "rgba(74,222,128,0.10)" : "transparent",
                    })}
                  >
                    <span style={{
                      width: 32, height: 32, borderRadius: 9, display: "grid", placeItems: "center",
                      background: "rgba(255,255,255,0.05)", flexShrink: 0,
                    }}><Icon size={17} /></span>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t("nav." + p.path)}
                    </span>
                  </NavLink>
                );
              })}
            </nav>

            {/* ⚙️ إعدادات سريعة — اللغة والصوت (كانا في الرأس العلوي) */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid rgba(255,255,255,.07)" }}>
              <Row label={lang === "ar" ? "اللغة" : "Language"}>
                <Pill on={lang === "ar"} onClick={() => setLang("ar")}>عربي</Pill>
                <Pill on={lang === "en"} onClick={() => setLang("en")}>English</Pill>
              </Row>
              <Row label={lang === "ar" ? "صوت التنبيهات" : "Alert sound"}>
                <Pill on={!muted} onClick={() => setSound(true)}>
                  {lang === "ar" ? "تشغيل" : "On"}
                </Pill>
                <Pill on={muted} onClick={() => setSound(false)}>
                  {lang === "ar" ? "كتم" : "Mute"}
                </Pill>
              </Row>
            </div>


            <div style={{ marginTop: 14, paddingTop: 10, fontSize: 11, opacity: .4, textAlign: "center" }}>
              WhaleX Prime 🐋
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
