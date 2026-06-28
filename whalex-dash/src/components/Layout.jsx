// الإطار العام للصفحات الداخلية
import Sidebar from "./Sidebar.jsx";
import BottomNav from "./BottomNav.jsx";
import { useLang } from "../context/LangContext.jsx";
import { Languages } from "lucide-react";
import NotificationBell from "./NotificationBell.jsx";

export default function Layout({ titleKey, children }) {
  const { t, lang, toggle } = useLang();
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <header className="topbar">
          <h1>{t(titleKey)}</h1>
          <div className="spacer" />
          <button className="lang-btn" onClick={toggle} title="Language">
            <Languages size={17} />
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <NotificationBell />
          <span className="status-dot">{t("systemRunning")}</span>
        </header>
        <div className="page-body">{children}</div>
      </div>
      <BottomNav />
    </div>
  );
}
