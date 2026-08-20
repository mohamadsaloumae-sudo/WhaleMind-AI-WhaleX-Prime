import { useNavigate } from "react-router-dom";
import { useLang } from "../context/LangContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { SECTIONS, T } from "../landing/sections.js";
import TopBar from "../landing/TopBar.jsx";

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
    onStart: () => nav(guest ? "/login" : paid ? "/live" : "/subscription"),
    onPerf: () => nav(guest ? "/login" : "/positions"),
  };

  return (
    <div style={{ background: T.bg, minHeight: "100vh", marginInline: -16 }}>
      <TopBar
        lang={lang}
        onEnter={() => nav(guest ? "/login" : "/")}
        onLang={() => setLang(lang === "en" ? "ar" : "en")}
      />
      {SECTIONS.filter((s) => s.enabled).map(({ id, Component }) => (
        <Component key={id} {...props} />
      ))}
    </div>
  );
}
