import { useState } from "react";
import { useLang } from "../context/LangContext.jsx";

/**
 * 🧮 حاسبة خطّة التداول — تُعطي المشترك إعداداته حسب رأس ماله.
 * الأرقام من الخادم، محسوبة على أداء النظام الحقيقيّ خلال 30 يوماً.
 */
export default function PlanCalc() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [cap, setCap] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);

  async function calc() {
    const v = Number(cap);
    if (!Number.isFinite(v) || v <= 0) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/plan?capital=${v}`).then((x) => x.json());
      setRes(r);
    } catch { setRes(null); }
    finally { setBusy(false); }
  }

  const box = {
    background: "rgba(15,163,146,.06)", border: "1px solid rgba(15,163,146,.22)",
    borderRadius: 16, padding: 18, marginBottom: 20, direction: ar ? "rtl" : "ltr",
    textAlign: ar ? "right" : "left",
  };
  const row = {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "9px 0", borderBottom: "1px solid rgba(255,255,255,.05)",
    fontSize: 13.5,
  };

  return (
    <div style={box}>
      <div style={{ fontWeight: 700, fontSize: 16, color: "#eaf6f4",
                    marginBottom: 6 }}>
        🧮 {ar ? "احسب خطّتك" : "Plan calculator"}
      </div>
      <div style={{ fontSize: 12.5, color: "#8fa9b4", marginBottom: 14 }}>
        {ar ? "أدخل المبلغ الذي ستضعه في محفظة العقود، ونحسب لك إعداداتك."
            : "Enter your futures wallet capital and we compute your settings."}
      </div>

      <div style={{ display: "flex", gap: 9, marginBottom: 14 }}>
        <input type="number" inputMode="decimal" value={cap}
               onChange={(e) => setCap(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && calc()}
               placeholder={ar ? "مثال: 1000" : "e.g. 1000"}
               style={{
                 flex: 1, padding: "11px 13px", borderRadius: 11,
                 border: "1px solid #24404e", background: "#0b1a23",
                 color: "#eaf6f4", fontSize: 15, fontFamily: "inherit",
                 direction: "ltr", textAlign: ar ? "right" : "left",
               }} />
        <button onClick={calc} disabled={busy} style={{
          padding: "11px 20px", borderRadius: 11, border: "none",
          background: "#0fa392", color: "#03151a", fontWeight: 700,
          fontSize: 14, cursor: "pointer", fontFamily: "inherit",
        }}>{busy ? "…" : (ar ? "احسب" : "Calc")}</button>
      </div>

      {res && !res.ok && (
        <div style={{
          background: "rgba(255,90,90,.08)", border: "1px solid rgba(255,90,90,.25)",
          borderRadius: 11, padding: 14, fontSize: 13, color: "#ffb3b3",
          lineHeight: 1.9, whiteSpace: "pre-line",
        }}>{ar ? res.reason_ar : res.reason_en}</div>
      )}

      {res && res.ok && (
        <>
          <div style={{ fontSize: 12, color: "#0fa392", fontWeight: 700,
                        marginBottom: 4 }}>
            {ar ? "إعداداتك الموصى بها" : "Recommended settings"}
          </div>
          <div style={row}>
            <span style={{ color: "#8fa9b4" }}>{ar ? "مبلغ الصفقة" : "Trade size"}</span>
            <b style={{ color: "#eaf6f4" }} dir="ltr">${res.amount}</b>
          </div>
          <div style={row}>
            <span style={{ color: "#8fa9b4" }}>{ar ? "عدد الصفقات" : "Max positions"}</span>
            <b style={{ color: "#eaf6f4" }}>{res.slots}</b>
          </div>
          <div style={row}>
            <span style={{ color: "#8fa9b4" }}>{ar ? "الرافعة" : "Leverage"}</span>
            <b style={{ color: "#eaf6f4" }} dir="ltr">{res.leverage}x</b>
          </div>
          <div style={row}>
            <span style={{ color: "#8fa9b4" }}>{ar ? "درجات الإشارات" : "Grades"}</span>
            <b style={{ color: "#eaf6f4" }} dir="ltr">{res.grades}</b>
          </div>
          <div style={{ ...row, borderBottom: "none", marginTop: 6 }}>
            <span style={{ color: "#8fa9b4" }}>{ar ? "الربح المتوقّع" : "Expected"}</span>
            <b style={{ color: "#3ddc84" }} dir="ltr">
              +${res.monthly}/{ar ? "شهر" : "mo"}</b>
          </div>
          <div style={{ ...row, borderBottom: "none", paddingTop: 0 }}>
            <span style={{ color: "#8fa9b4" }}>
              {ar ? "بعد اشتراك البوت" : "After subscription"}</span>
            <b style={{ color: res.after_subscription > 0 ? "#3ddc84" : "#ffb3b3" }}
               dir="ltr">
              {res.after_subscription > 0 ? "+" : ""}${res.after_subscription}</b>
          </div>
          <div style={{
            marginTop: 12, padding: 11, borderRadius: 10,
            background: "rgba(240,180,41,.08)", fontSize: 11.5,
            color: "#f0b429", lineHeight: 1.8,
          }}>⚠️ {ar ? res.note_ar : res.note_en}</div>
        </>
      )}
    </div>
  );
}
