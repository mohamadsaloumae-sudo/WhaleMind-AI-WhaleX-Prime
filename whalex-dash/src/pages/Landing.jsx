import { useNavigate } from "react-router-dom";
import { useLang } from "../context/LangContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { SECTIONS, T } from "../landing/sections.js";
import TopBar from "../landing/TopBar.jsx";
import ScrollTop from "../components/ScrollTop.jsx";
import ChatWidget from "../components/ChatWidget.jsx";

/**
 * 🏁 المقدّمة — تُعرض عند كل فتح للتطبيق.
 * المشترك: الزرّ يأخذه للتداول مباشرةً.
 * غير المشترك: يأخذه للتجربة المجانية.
 */
export default function Landing() {
  const nav = useNavigate();
  const { lang, setLang } = useLang();
  const { user } = useAuth();

  // 🏁 الزائر بلا حساب → التسجيل · المسجَّل → حسب اشتراكه
  const guest = !user;
  const paid = ["pro", "vip", "admin", "trial"].includes(
    String(user?.tier || "").toLowerCase()
  );

  const props = {
    lang,
    onStart: () => {
      if (guest) { nav("/login"); return; }
      window.__wxIntroDone = true;
          window.dispatchEvent(new Event("wx-intro-done"));
          try { sessionStorage.setItem("wx_seen_intro", "1"); } catch {}
      nav(paid ? "/live" : "/subscription");
    },
    onPerf: () => {
      if (guest) { nav("/login"); return; }
      window.__wxIntroDone = true;
          window.dispatchEvent(new Event("wx-intro-done"));
          try { sessionStorage.setItem("wx_seen_intro", "1"); } catch {}
      nav("/positions");
    },
  };

  return (
    <div className="wx-landing" style={{ background: T.bg, minHeight: "100vh", marginInline: -16, position: "relative" }}>
      <TopBar
        lang={lang}
        guest={guest}
        onEnter={() => {
          if (guest) { nav("/login"); return; }
          window.__wxIntroDone = true;
          window.dispatchEvent(new Event("wx-intro-done"));
          try { sessionStorage.setItem("wx_seen_intro", "1"); } catch {}
          nav("/");
        }}
        onLang={() => setLang(lang === "en" ? "ar" : "en")}
      />
      <ScrollTop />
      <ChatWidget />
      {SECTIONS.filter((s) => s.enabled).map(({ id, Component }) => (
        <Component key={id} {...props} />
      ))}
    </div>
  );
}
