// ⬆️ العودة للأعلى — يعتمد على علامة مراقبة، لا على تخمين الحاوية
import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function ScrollTop() {
  const { lang } = useLang();
  const [show, setShow] = useState(false);
  const markRef = useRef(null);

  useEffect(() => {
    const mark = markRef.current;
    if (!mark) return;
    const io = new IntersectionObserver(
      ([e]) => setShow(!e.isIntersecting),
      { threshold: 0, rootMargin: "0px" }
    );
    io.observe(mark);
    return () => io.disconnect();
  }, []);

  function up() {
    try {
      markRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch {
      markRef.current?.scrollIntoView();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.querySelectorAll(".page-body, .main-area, .app-shell").forEach((n) => {
      try { n.scrollTo({ top: 0, behavior: "smooth" }); } catch { n.scrollTop = 0; }
    });
  }

  return (
    <>
      <span ref={markRef} style={{ position: "absolute", top: 0, height: 1, width: 1, opacity: 0, pointerEvents: "none" }} />
      <button
        onClick={up}
        aria-label="top"
        title={lang === "ar" ? "أعلى الصفحة" : "Back to top"}
        style={{
          position: "fixed",
          top: "50%",
          [lang === "ar" ? "left" : "right"]: 12,
          transform: show ? "translateY(-50%) scale(1)" : "translateY(-50%) scale(.7)",
          width: 40, height: 40, borderRadius: "50%",
          display: "grid", placeItems: "center",
          background: "rgba(74,222,128,0.5)",
          backdropFilter: "blur(6px)",
          color: "#04140a", border: "1px solid rgba(255,255,255,0.2)",
          cursor: "pointer", zIndex: 890,
          boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
          opacity: show ? 0.8 : 0,
          pointerEvents: show ? "auto" : "none",
          transition: "opacity .25s ease, transform .25s cubic-bezier(.22,.9,.3,1)",
          WebkitTapHighlightColor: "transparent",
        }}
      >
        <ArrowUp size={19} strokeWidth={2.8} />
      </button>
    </>
  );
}
