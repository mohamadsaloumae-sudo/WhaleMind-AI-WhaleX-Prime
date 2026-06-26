// القائمة السفلية (موبايل) — تُبنى تلقائياً من PAGES
import { NavLink } from "react-router-dom";
import { PAGES } from "../lib/pages.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";

export default function BottomNav() {
  const { user } = useAuth();
  const { t } = useLang();
  const isAdmin = user?.tier === "admin";

  const navPages = PAGES
    .filter((p) => !p.adminOnly || isAdmin)
    .slice(0, 5);

  return (
    <nav className="bottom-nav">
      {navPages.map((p) => {
        const Icon = p.icon;
        return (
          <NavLink
            key={p.path}
            to={p.path}
            end={p.path === "/"}
            className={({ isActive }) =>
              `bottom-nav-item ${p.adminOnly ? "admin" : ""} ${isActive ? "active" : ""}`
            }
          >
            <Icon size={22} />
            <span>{t("nav." + p.path)}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
