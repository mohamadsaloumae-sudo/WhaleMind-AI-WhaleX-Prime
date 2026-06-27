// بوّابة الاشتراك — تحمي المحتوى المدفوع (الإشارات، التداول)
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { subscription } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Lock, Crown } from "lucide-react";

export default function Paywall({ children }) {
  const { t } = useLang();
  const nav = useNavigate();
  const [state, setState] = useState("loading"); // loading | locked | open

  useEffect(() => {
    (async () => {
      try {
        const s = await subscription.status();
        setState(s?.is_active ? "open" : "locked");
      } catch {
        setState("locked");
      }
    })();
  }, []);

  if (state === "loading") return <div className="loading">{t("loading")}</div>;
  if (state === "open") return children;

  // مقفل — دعوة للاشتراك
  return (
    <div style={{ maxWidth: 480, margin: "40px auto", textAlign: "center" }}>
      <div className="card" style={{ padding: 32 }}>
        <div style={{
          width: 72, height: 72, borderRadius: "50%", margin: "0 auto 20px",
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "var(--brand-dim)",
        }}>
          <Lock size={34} color="var(--brand)" />
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 10 }}>{t("premiumOnly")}</h2>
        <p style={{ fontSize: 14, color: "var(--txt-2)", marginBottom: 24, lineHeight: 1.6 }}>
          {t("premiumDesc")}
        </p>
        <button className="btn btn-primary btn-block" onClick={() => nav("/subscription")}>
          <Crown size={18} /> {t("subscribeNow")}
        </button>
      </div>
    </div>
  );
}
