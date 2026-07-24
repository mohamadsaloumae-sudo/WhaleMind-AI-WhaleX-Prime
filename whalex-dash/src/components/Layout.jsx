// الإطار العام للصفحات الداخلية
import Sidebar from "./Sidebar.jsx";
import BottomNav from "./BottomNav.jsx";
import { useLang } from "../context/LangContext.jsx";
import { Languages, Share2 } from "lucide-react";
import NotificationBell from "./NotificationBell.jsx";

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
      <Sidebar />
      <div className="main-area">
        <header className="topbar">
          <h1>{t(titleKey)}</h1>
          <div className="spacer" />
          <button className="lang-btn" onClick={toggle} title="Language">
            <Languages size={17} />
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <button className="lang-btn" onClick={shareApp} title={lang === "ar" ? "مشاركة" : "Share"}>
            <Share2 size={16} />
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
