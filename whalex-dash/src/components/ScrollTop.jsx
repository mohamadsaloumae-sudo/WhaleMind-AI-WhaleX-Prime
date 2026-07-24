// ⬆️ العودة للأعلى — ظاهر دائماً، بضغطة واحدة
import { ArrowUp } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function ScrollTop() {
  const { lang } = useLang();

  function up() {
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
      document.documentElement.scrollTo?.({ top: 0, behavior: "smooth" });
      document.body.scrollTo?.({ top: 0, behavior: "smooth" });
      document.querySelectorAll(".page-body, .main-area, .app-shell").forEach((el) => {
        try { el.scrollTo({ top: 0, behavior: "smooth" }); } catch { el.scrollTop = 0; }
      });
    } catch { /* */ }
  }

  return (
    <button
      onClick={up}
      aria-label="scroll to top"
      title={lang === "ar" ? "أعلى الصفحة" : "Back to top"}
      style={{
        position: "fixed",
        bottom: "calc(env(safe-area-inset-bottom, 0px) + 84px)",
        [lang === "ar" ? "left" : "right"]: 14,
        width: 44, height: 44, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: "rgba(74,222,128,0.93)", color: "#06110a",
        border: "none", cursor: "pointer", zIndex: 890,
        boxShadow: "0 6px 22px rgba(0,0,0,0.45)",
        WebkitTapHighlightColor: "transparent",
      }}
    >
      <ArrowUp size={21} strokeWidth={2.7} />
    </button>
  );
}
