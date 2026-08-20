// القائمة الجانبية — تُبنى تلقائياً من PAGES
import { NavLink } from "react-router-dom";
import { Waves, LogOut } from "lucide-react";
import { PAGES } from "../lib/pages.js";
import QuickSettings from "./QuickSettings.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const isAdmin = user?.tier === "admin";

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Waves size={26} /> WhaleX
      </div>

      <nav className="nav-list">
        {(() => {
          // 🏁 «عن المنصّة» أوّل القائمة الجانبية
          const _a = PAGES.filter((p) => !p.adminOnly);
          const _ab = _a.find((p) => p.path === "/landing");
          return _ab ? [_ab, ..._a.filter((p) => p.path !== "/landing")] : _a;
        })().map((p) => {
          const Icon = p.icon;
          return (
            <NavLink
              key={p.path}
              to={p.path}
              end={p.path === "/"}
              className={({ isActive }) =>
                `nav-item ${p.adminOnly ? "admin" : ""} ${isActive ? "active" : ""}`
              }
            >
              <Icon size={19} /> {t("nav." + p.path)}
            </NavLink>
          );
        })}
      </nav>

      <div style={{ padding: "0 14px" }}>
        <QuickSettings />
      </div>

      <div className="sidebar-footer">
        <div className="user-chip">
          <span>{user?.uid?.slice(0, 8) || "مستخدم"}</span>
          <span className="tier">{user?.tier || "free"}</span>
        </div>
        <button className="logout-btn" onClick={logout}>
          <LogOut size={15} style={{ verticalAlign: "middle", marginLeft: 6 }} />
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}
