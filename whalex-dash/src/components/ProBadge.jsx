// 🏅 شارة الاشتراك والرتبة
import { useEffect, useState } from "react";
import { subscription } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

export default function ProBadge() {
  const { lang } = useLang();
  const [s, setS] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await subscription.status();
        if (alive) setS(r);
      } catch { /* */ }
    };
    load();
    const iv = setInterval(load, 60000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  if (!s) return null;
  const pro = s.is_active || s.tier === "admin";
  const ar = lang === "ar";

  return (
    <span
      title={pro && s.days_left != null ? `${s.days_left} ${ar ? "يوماً متبقية" : "days left"}` : ""}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5, flexShrink: 0,
        padding: "5px 10px", borderRadius: 8, fontSize: 11, fontWeight: 800, whiteSpace: "nowrap",
        background: pro ? "rgba(74,222,128,0.15)" : "rgba(255,255,255,0.06)",
        color: pro ? "var(--brand, #4ade80)" : "var(--txt-3)",
        border: `1px solid ${pro ? "rgba(74,222,128,0.3)" : "rgba(255,255,255,0.1)"}`,
      }}
    >
      {pro ? (
        <>
          <span>{s.icon || "🏅"}</span>
          <span>{s.tier === "admin" ? "ADMIN" : "PRO"}</span>
          {s.level_ar && s.tier !== "admin" && (
            <span style={{ opacity: .75, fontWeight: 600 }}>· {ar ? s.level_ar : s.level_en}</span>
          )}
        </>
      ) : (
        <span>{ar ? "مجاني" : "FREE"}</span>
      )}
    </span>
  );
}
