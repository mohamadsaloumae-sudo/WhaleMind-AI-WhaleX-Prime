import { useNavigate } from "react-router-dom";
import { useLang } from "../context/LangContext.jsx";
import { SECTIONS, T } from "../landing/sections.js";

/**
 * 🏁 صفحة المقدّمة — تُعرَض لكل مسجّل جديد.
 * الأقسام تأتي من sections.js: إضافة قسم = ملف + سطر.
 */
export default function Landing() {
  const nav = useNavigate();
  const { lang } = useLang();

  const props = {
    lang,
    onStart: () => nav("/subscription"),
    onPerf: () => nav("/positions"),
  };

  return (
    <div style={{ background: T.bg, minHeight: "100vh", marginInline: -16 }}>
      {SECTIONS.filter((s) => s.enabled).map(({ id, Component }) => (
        <Component key={id} {...props} />
      ))}
    </div>
  );
}
