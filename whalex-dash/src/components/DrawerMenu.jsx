// ☰ قائمة جانبية علوية — كل الصفحات خارج الشريط السفلي
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { PAGES } from "../lib/pages.js";
import { useLang } from "../context/LangContext.jsx";

export default function DrawerMenu() {
  const { t, lang } = useLang();
  const [open, setOpen] = useState(false);
  const pages = PAGES.filter((p) => !p.adminOnly).slice(5);
  const side = lang === "ar" ? "right" : "left";

  return (
    <>
      <button className="lang-btn" onClick={() => setOpen(true)} title={t("more")}>
        <Menu size={18} />
      </button>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
            zIndex: 900, backdropFilter: "blur(2px)",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              position: "absolute", top: 0, bottom: 0, [side]: 0, width: "min(78vw, 300px)",
              background: "var(--bg-2, #131722)", borderInlineStart: "1px solid var(--line, #222)",
              padding: "18px 14px", display: "flex", flexDirection: "column", gap: 6,
              boxShadow: "0 0 40px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>{t("more")}</span>
              <button className="more-close" onClick={() => setOpen(false)}><X size={20} /></button>
            </div>
            {pages.map((p) => {
              const Icon = p.icon;
              return (
                <NavLink
                  key={p.path}
                  to={p.path}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) => `more-item ${isActive ? "active" : ""}`}
                  style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "13px 12px",
                    borderRadius: 10, fontSize: 14.5, textDecoration: "none",
                  }}
                >
                  <Icon size={21} />
                  <span>{t("nav." + p.path)}</span>
                </NavLink>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
