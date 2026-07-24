// 📱 حارس الجهاز الواحد
import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";
import { api } from "../lib/api.js";

function deviceId() {
  let v = localStorage.getItem("wx_device");
  if (!v) {
    v = "d" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    localStorage.setItem("wx_device", v);
  }
  return v;
}



export default function DeviceGuard({ children }) {
  const { lang } = useLang();
  const ar = lang === "ar";
  const [locked, setLocked] = useState(false);

  async function register() {
    try {
      await api.post("/api/device/register", { user_id: "", device_id: deviceId(), ua: navigator.userAgent || "" });
      setLocked(false);
    } catch { /* */ }
  }

  useEffect(() => {
    register();
    const check = async () => {
      try {
        const d = await api.get(`/api/device/check?device_id=${deviceId()}`);
        setLocked(d && d.valid === false);
      } catch { /* */ }
    };
    const iv = setInterval(check, 30000);

    function onKick(e) {
      try {
        const d = JSON.parse(e.detail || "{}");
        if (d.event === "device_kick" && d.target_device === deviceId()) {
          setLocked(true);
        }
      } catch { /* */ }
    }
    window.addEventListener("wx-device", onKick);
    return () => { clearInterval(iv); window.removeEventListener("wx-device", onKick); };
  }, []);

  if (!locked) return children;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 3000, background: "var(--bg-1, #0b0e16)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: 26, textAlign: "center", gap: 14,
    }}>
      <span style={{
        width: 64, height: 64, borderRadius: 20, display: "grid", placeItems: "center",
        background: "rgba(239,68,68,0.14)", color: "#ef4444",
      }}><Smartphone size={30} /></span>
      <div style={{ fontSize: 17, fontWeight: 800 }}>
        {ar ? "الحساب مفتوح على جهاز آخر" : "Account open on another device"}
      </div>
      <div style={{ fontSize: 13.5, color: "var(--txt-3)", lineHeight: 1.9, maxWidth: 330 }}>
        {ar
          ? "يُسمح بجهاز واحد لكل اشتراك. أغلق التطبيق على الجهاز الآخر، أو اضغط الزر لنقل الجلسة إلى هذا الجهاز."
          : "One device per subscription. Close the app on the other device, or move the session here."}
      </div>
      <button onClick={register} style={{
        marginTop: 6, background: "var(--brand, #4ade80)", color: "#06110a", border: "none",
        borderRadius: 12, padding: "13px 26px", fontSize: 14, fontWeight: 700, cursor: "pointer",
      }}>
        {ar ? "استخدم هذا الجهاز" : "Use this device"}
      </button>
    </div>
  );
}
