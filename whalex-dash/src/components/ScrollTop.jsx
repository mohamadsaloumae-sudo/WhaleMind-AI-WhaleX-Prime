// ⬆️ العودة للأعلى — يظهر عند النزول، بضغطة واحدة
import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function ScrollTop() {
  const { lang } = useLang();
  const [show, setShow] = useState(false);

  useEffect(() => {
    const target = document.querySelector(".page-body") || window;
    const read = () => (target === window ? window.scrollY : target.scrollTop);
    const onScroll = () => setShow(read() > 300);
    target.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      target.removeEventListener("scroll", onScroll);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  function up() {
    const target = document.querySelector(".page-body");
    if (target && target.scrollTop > 0) target.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <button
      onClick={up}
      aria-label="top"
      style={{
        position: "fixed",
        bottom: "calc(env(safe-area-inset-bottom, 0px) + 78px)",
        [lang === "ar" ? "left" : "right"]: 16,
        width: 42, height: 42, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: "rgba(74,222,128,0.92)", color: "#06110a",
        border: "none", cursor: "pointer", zIndex: 800,
        boxShadow: "0 6px 20px rgba(0,0,0,0.35)",
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0) scale(1)" : "translateY(14px) scale(.85)",
        pointerEvents: show ? "auto" : "none",
        transition: "opacity .22s ease, transform .22s cubic-bezier(.22,.9,.3,1)",
      }}
    >
      <ArrowUp size={20} strokeWidth={2.6} />
    </button>
  );
}
