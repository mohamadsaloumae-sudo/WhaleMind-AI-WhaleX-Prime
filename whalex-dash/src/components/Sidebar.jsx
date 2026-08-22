// القائمة الجانبية — تُبنى تلقائياً من PAGES
import { NavLink } from "react-router-dom";
import { Waves, LogOut } from "lucide-react";
import { PAGES } from "../lib/pages.js";
import QuickSettings from "./QuickSettings.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { setWidth, applyUI, setCollapsed } from "../lib/uiState.js";
import { useEffect } from "react";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const isAdmin = user?.tier === "admin";

  // 🎛️ نُعيد ما حفظه المستخدم (الطيّ والعرض) عند الإقلاع
  useEffect(() => { applyUI(); }, []);

  // ↔️ سحب الحافّة لتغيير العرض
  function startDrag(e) {
    e.preventDefault();
    const move = (ev) => {
      const x = ev.touches ? ev.touches[0].clientX : ev.clientX;
      setWidth(window.innerWidth - x);
    };
    const stop = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", stop);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", stop);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", stop);
    window.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("touchend", stop);
  }

  return (
    <>
    <div className="wx-resize" onMouseDown={startDrag} onTouchStart={startDrag} />
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Waves size={24} />
        <span>WhaleX <span style={{ color: "var(--brand)" }}>Prime</span></span>
      </div>

      <nav className="nav-list">
        {PAGES.filter((p) => !p.adminOnly).map((p) => {
          const Icon = p.icon;
          return (
            <NavLink
              key={p.path}
              to={p.path}
              end={p.path === "/"}
              onClick={() => {
                // 📱 فتح صفحة يطوي القائمة — المحتوى يملأ الشاشة
                if (window.innerWidth > 980) setCollapsed(true);
              }}
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
    </>
  );
}
