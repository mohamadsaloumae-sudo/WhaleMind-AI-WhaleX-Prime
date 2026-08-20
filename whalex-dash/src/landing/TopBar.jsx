import { useEffect, useState } from "react";
import { LayoutDashboard, Languages } from "lucide-react";
import { T } from "./sections.js";

/**
 * شريط علوي ثابت — مخرج دائم من المقدّمة.
 * المشترك يدخل التطبيق مباشرةً · وغيره يبدأ التجربة.
 */
export default function TopBar({ lang = "ar", onEnter, onLang }) {
  const ar = lang !== "en";
  const [solid, setSolid] = useState(false);

  useEffect(() => {
    const on = () => setSolid(window.scrollY > 30);
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  return (
    <div style={{
      position: "sticky", top: 0, zIndex: 50,
      display: "flex", alignItems: "center", gap: 10,
      padding: "11px 16px",
      background: solid ? "rgba(8,12,22,.92)" : "transparent",
      backdropFilter: solid ? "blur(14px)" : "none",
      borderBottom: solid ? `1px solid ${T.border}` : "1px solid transparent",
      transition: "all .25s ease",
    }}>
      <span style={{
        fontSize: 16, fontWeight: 900, color: T.txt, letterSpacing: -.3,
      }}>
        WhaleX <span style={{ color: T.brand }}>Prime</span>
      </span>

      <button onClick={onLang} style={{
        marginInlineStart: "auto", display: "flex", alignItems: "center", gap: 5,
        padding: "7px 11px", borderRadius: 9, cursor: "pointer",
        background: "transparent", border: `1px solid ${T.border}`,
        color: T.txt2, fontSize: 11.5, fontWeight: 700,
      }}>
        <Languages size={14} />
        {ar ? "EN" : "ع"}
      </button>

      <button onClick={onEnter} style={{
        display: "flex", alignItems: "center", gap: 6,
        padding: "8px 14px", borderRadius: 9, cursor: "pointer",
        background: "rgba(45,212,191,.12)", border: `1px solid ${T.brand}55`,
        color: T.brand, fontSize: 12, fontWeight: 800,
      }}>
        <LayoutDashboard size={14} />
        {ar ? "تسجيل الدخول" : "Sign in"}
      </button>
    </div>
  );
}
