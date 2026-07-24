// ⬆️ العودة للأعلى — يظهر عند بدء النزول، يختفي في الأعلى
import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function ScrollTop() {
  const { lang } = useLang();
  const [show, setShow] = useState(false);
  const elRef = useRef(null);

  useEffect(() => {
    // اكتشاف الحاوية التي تتمرّر فعلاً
    function findScroller() {
      const cands = [
        document.querySelector(".page-body"),
        document.querySelector(".main-area"),
        document.querySelector(".app-shell"),
        document.scrollingElement,
        document.documentElement,
        document.body,
      ].filter(Boolean);
      for (const el of cands) {
        if (el.scrollHeight - el.clientHeight > 40) return el;
      }
      return document.scrollingElement || document.documentElement;
    }

    function pos() {
      const el = elRef.current;
      const a = el ? el.scrollTop : 0;
      return Math.max(a, window.scrollY || 0, document.documentElement.scrollTop || 0, document.body.scrollTop || 0);
    }

    function check() {
      if (!elRef.current) elRef.current = findScroller();
      setShow(pos() > 60);
    }

    elRef.current = findScroller();
    const targets = [window, document, elRef.current].filter(Boolean);
    targets.forEach((t) => t.addEventListener("scroll", check, { passive: true, capture: true }));
    const iv = setInterval(check, 300);
    check();
    return () => {
      targets.forEach((t) => t.removeEventListener("scroll", check, { capture: true }));
      clearInterval(iv);
    };
  }, []);

  function up() {
    const el = elRef.current;
    try { el && el.scrollTo({ top: 0, behavior: "smooth" }); } catch { if (el) el.scrollTop = 0; }
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.querySelectorAll(".page-body, .main-area, .app-shell").forEach((n) => {
      try { n.scrollTo({ top: 0, behavior: "smooth" }); } catch { n.scrollTop = 0; }
    });
    setTimeout(() => setShow(false), 300);
  }

  return (
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
        background: "rgba(74,222,128,0.55)",
        backdropFilter: "blur(6px)",
        color: "#04140a", border: "1px solid rgba(255,255,255,0.18)",
        cursor: "pointer", zIndex: 890,
        boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        opacity: show ? 0.75 : 0,
        pointerEvents: show ? "auto" : "none",
        transition: "opacity .25s ease, transform .25s cubic-bezier(.22,.9,.3,1)",
        WebkitTapHighlightColor: "transparent",
      }}
    >
      <ArrowUp size={19} strokeWidth={2.8} />
    </button>
  );
}
