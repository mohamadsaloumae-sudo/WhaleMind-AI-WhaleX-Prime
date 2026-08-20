import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";
import { useTier } from "../context/TierContext.jsx";
import { useLang } from "../context/LangContext.jsx";

/** شريط يشرح للمجرّب سبب الإخفاء — بلا لبس ولا إحباط. */
export default function TrialNote() {
  const { trial } = useTier();
  const { lang } = useLang();
  const nav = useNavigate();
  if (!trial) return null;
  const ar = lang !== "en";

  return (
    <div
      onClick={() => nav("/subscription")}
      style={{
        display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
        background: "rgba(45,212,191,.07)", border: "1px solid rgba(45,212,191,.3)",
        borderRadius: 13, padding: "12px 14px", marginBottom: 14,
      }}
    >
      <Lock size={16} style={{ color: "var(--brand)", flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--txt-1)" }}>
          {ar ? "تجربة مجانية — التفاصيل مخفيّة" : "Free trial — details hidden"}
        </div>
        <div style={{ fontSize: 11, color: "var(--txt-2)", marginTop: 2, lineHeight: 1.6 }}>
          {ar
            ? "النظام ينفّذ على حسابك وتراها في صفقاتك كاملةً. اشترك لترى كل إشارة قبل تنفيذها."
            : "The system executes on your account and you see them fully in your trades. Subscribe to see every signal before it fires."}
        </div>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 800, color: "var(--brand)", flexShrink: 0,
      }}>{ar ? "اشترك" : "Subscribe"}</span>
    </div>
  );
}
