// القائمة السفلية — خمس صفحات أساسية فقط (الباقي في قائمة ☰ أعلى الشاشة)
import { NavLink } from "react-router-dom";
import { PAGES } from "../lib/pages.js";
import { useLang } from "../context/LangContext.jsx";

export default function BottomNav() {
  const { t } = useLang();
  const mainPages = PAGES.filter((p) => !p.adminOnly).slice(0, 5);

  return (
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
    </nav>
  );
}
