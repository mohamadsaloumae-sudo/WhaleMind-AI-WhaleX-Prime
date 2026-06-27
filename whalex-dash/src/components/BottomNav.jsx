// القائمة السفلية (موبايل) — أول 4 صفحات + "المزيد" (الأدمن مستبعد دائماً — رابط سرّي فقط)
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { PAGES } from "../lib/pages.js";
import { useLang } from "../context/LangContext.jsx";
import { Menu, X } from "lucide-react";

export default function BottomNav() {
  const { t } = useLang();
  const [moreOpen, setMoreOpen] = useState(false);

  // الأدمن مستبعد من كل القوائم — يُفتح برابط /admin المباشر فقط
  const visible = PAGES.filter((p) => !p.adminOnly);
  const mainPages = visible.slice(0, 4);
  const morePages = visible.slice(4);

  return (
    <>
      {moreOpen && (
        <div className="more-overlay" onClick={() => setMoreOpen(false)}>
          <div className="more-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="more-header">
              <span>{t("more")}</span>
              <button className="more-close" onClick={() => setMoreOpen(false)}><X size={20} /></button>
            </div>
            <div className="more-grid">
              {morePages.map((p) => {
                const Icon = p.icon;
                return (
                  <NavLink
                    key={p.path}
                    to={p.path}
                    onClick={() => setMoreOpen(false)}
                    className={({ isActive }) => `more-item ${isActive ? "active" : ""}`}
                  >
                    <Icon size={24} />
                    <span>{t("nav." + p.path)}</span>
                  </NavLink>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <nav className="bottom-nav">
        {mainPages.map((p) => {
          const Icon = p.icon;
          return (
            <NavLink
              key={p.path}
              to={p.path}
              end={p.path === "/"}
              className={({ isActive }) => `bottom-nav-item ${isActive ? "active" : ""}`}
            >
              <Icon size={22} />
              <span>{t("nav." + p.path)}</span>
            </NavLink>
          );
        })}
        {morePages.length > 0 && (
          <button className={`bottom-nav-item ${moreOpen ? "active" : ""}`} onClick={() => setMoreOpen(true)}>
            <Menu size={22} />
            <span>{t("more")}</span>
          </button>
        )}
      </nav>
    </>
  );
}
