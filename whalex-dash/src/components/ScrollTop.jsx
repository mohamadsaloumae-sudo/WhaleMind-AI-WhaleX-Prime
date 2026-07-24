// ⬆️ العودة للأعلى
import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function ScrollTop() {
  const { lang } = useLang();
  const [show, setShow] = useState(false);

  useEffect(() => {
    const scrollers = [window, document.querySelector(".page-body"), document.querySelector(".main-area")].filter(Boolean);
    const read = () => Math.max(
      window.scrollY || 0,
      document.documentElement.scrollTop || 0,
      document.body.scrollTop || 0,
      document.querySelector(".page-body")?.scrollTop || 0,
      document.querySelector(".main-area")?.scrollTop || 0
    );
    const onScroll = () => setShow(read() > 250);
    scrollers.forEach((s) => s.addEventListener("scroll", onScroll, { passive: true }));
    const iv = setInterval(onScroll, 400);
    onScroll();
    return () => {
      scrollers.forEach((s) => s.removeEventListener("scroll", onScroll));
      clearInterval(iv);
    };
  }, []);

  function up() {
    [document.querySelector(".page-body"), document.querySelector(".main-area")].forEach((el) => {
      if (el && el.scrollTop > 0) el.scrollTo({ top: 0, behavior: "smooth" });
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.documentElement.scrollTo?.({ top: 0, behavior: "smooth" });
  }

  return (
    <button
      onClick={up}
      aria-label="top"
      style={{
        position: "fixed",
        bottom: "calc(env(safe-area-inset-bottom, 0px) + 80px)",
        [lang === "ar" ? "left" : "right"]: 16,
        width: 44, height: 44, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: "rgba(74,222,128,0.95)", color: "#06110a",
        border: "none", cursor: "pointer", zIndex: 880,
        boxShadow: "0 6px 22px rgba(0,0,0,0.4)",
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0) scale(1)" : "translateY(14px) scale(.8)",
        pointerEvents: show ? "auto" : "none",
        transition: "opacity .2s ease, transform .2s cubic-bezier(.22,.9,.3,1)",
      }}
    >
      <ArrowUp size={21} strokeWidth={2.7} />
    </button>
  );
}
