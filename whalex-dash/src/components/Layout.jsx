// الإطار العام للصفحات الداخلية
import Sidebar from "./Sidebar.jsx";
import BottomNav from "./BottomNav.jsx";
import { useLang } from "../context/LangContext.jsx";
import { Languages, Share2 } from "lucide-react";
import NotificationBell from "./NotificationBell.jsx";
import DrawerMenu from "./DrawerMenu.jsx";
import { PanelRight } from "lucide-react";
import { toggleSidebar } from "../lib/uiState.js";
import ProBadge from "./ProBadge.jsx";
import ScrollTop from "./ScrollTop.jsx";
import Toast from "./Toast.jsx";

export default function Layout({ titleKey, children }) {
  const { t, lang, toggle } = useLang();

  async function shareApp() {
    const APP_URL = "https://whalemindhybridai.online";
    const TEXT = lang === "ar"
      ? "🐋 WhaleX Prime\n\nمنصّة إشارات تداول مدعومة بالذكاء الاصطناعي.\n\n⚡ رادارات للعقود الآجلة والسبوت والميم كوينز\n🎯 فحص صارم متعدّد الطبقات قبل كل إشارة\n📊 إدارة لحظية للصفقات وجني أرباح تلقائي\n🔔 إشعارات فورية عبر تيليجرام\n\nجرّبها الآن:"
      : "🐋 WhaleX Prime\n\nAI-powered trading signals platform.\n\n⚡ Futures, Spot & Meme-coin radars\n🎯 Multi-layer screening before every signal\n📊 Live position management with auto profit-locking\n🔔 Instant Telegram alerts\n\nTry it now:";
    // داخل تيليجرام: نافذة المشاركة الأصلية برابط التطبيق (لا رابط الصفحة)
    try {
      const tg = window.Telegram && window.Telegram.WebApp;
      if (tg && tg.openTelegramLink) {
        tg.openTelegramLink(
          "https://t.me/share/url?url=" + encodeURIComponent(APP_URL) +
          "&text=" + encodeURIComponent(TEXT)
        );
        return;
      }
    } catch { /* تابع للبديل */ }
    try {
      if (navigator.share) {
        await navigator.share({ text: TEXT, url: APP_URL });
        return;
      }
      await navigator.clipboard.writeText(TEXT + "\n" + APP_URL);
      alert(lang === "ar" ? "✅ نُسخ رابط التطبيق" : "✅ App link copied");
    } catch { /* المستخدم ألغى */ }
  }

  return (
    <div className="app-shell">
      <Toast />
      <Sidebar />
      <div className="main-area">
        <header className="topbar">
          {/* ☰ طيّ القائمة الجانبية — سطح المكتب فقط */}
          <button
            className="wx-sb-toggle"
            onClick={toggleSidebar}
            title="القائمة"
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              color: "var(--txt-2)", display: "flex", alignItems: "center",
              padding: 6, borderRadius: 8, marginInlineEnd: 4,
            }}
          >
            <PanelRight size={18} strokeWidth={1.8} />
          </button>

          {/* 🏷️ العنوان والفئة معاً — النقطة الخضراء تعني أن النظام يعمل */}
          <h1 style={{
            minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
            whiteSpace: "nowrap", flexShrink: 1,
          }}>{t(titleKey)}</h1>
          <span style={{
            width: 7, height: 7, borderRadius: 7, flexShrink: 0,
            background: "var(--green, #22c55e)",
            boxShadow: "0 0 8px var(--green, #22c55e)",
            animation: "wxLive 2.2s ease-in-out infinite",
          }} title={t("systemRunning")} />
          <ProBadge />
          <div style={{ flex: "1 1 auto" }} />
          <button
            onClick={shareApp}
            title={lang === "ar" ? "مشاركة" : "Share"}
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              color: "var(--txt-2)", display: "flex", alignItems: "center",
              padding: 6, borderRadius: 8, transition: "color .2s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--brand)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--txt-2)"; }}
          >
            <Share2 size={18} strokeWidth={1.8} />
          </button>
          <NotificationBell />
          <DrawerMenu />
        </header>
        <style>{"@keyframes wxLive{0%,100%{opacity:1}50%{opacity:.35}}"}</style>
        <div className="page-body" style={{ position: "relative" }}><ScrollTop />{children}</div>
      </div>
      <BottomNav />
    </div>
  );
}
