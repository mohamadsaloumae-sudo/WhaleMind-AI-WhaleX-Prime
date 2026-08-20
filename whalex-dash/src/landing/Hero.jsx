import { Zap, Activity } from "lucide-react";
import { T } from "./sections.js";

/** ① البطل — أوّل ما يراه الزائر */
export default function Hero({ lang = "ar", onStart, onPerf }) {
  const ar = lang !== "en";
  return (
    <section style={{
      padding: "40px 20px 26px",
      background: `radial-gradient(120% 80% at 50% 0%, rgba(45,212,191,.13) 0%, transparent 60%), ${T.bg}`,
      textAlign: "center",
    }}>
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 7,
        padding: "6px 14px", borderRadius: 20, marginBottom: 22,
        background: "rgba(45,212,191,.1)", border: `1px solid ${T.brand}44`,
        fontSize: 11.5, fontWeight: 700, color: T.brand,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: 6, background: T.brand2,
          boxShadow: `0 0 8px ${T.brand2}`,
        }} />
        {ar ? "يعمل بينما أنت نائم" : "Works while you sleep"}
      </div>

      <h1 style={{
        fontSize: "clamp(30px, 8.5vw, 44px)", lineHeight: 1.22,
        fontWeight: 900, margin: "0 0 18px", color: T.txt,
      }}>
        {ar ? "تداول آلي كامل" : "Fully automated"}
        <br />
        <span style={{
          background: `linear-gradient(95deg, ${T.brand}, ${T.brand2})`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}>
          {ar ? "من الإشارة إلى الإغلاق" : "from signal to close"}
        </span>
      </h1>

      <p style={{
        fontSize: 14.5, lineHeight: 1.85, color: T.txt2,
        maxWidth: 460, margin: "0 auto 26px",
      }}>
        {ar
          ? "نظام يراقب السوق على مدار الساعة، يصطاد الفرصة، ينفّذها على حسابك في منصّتك، ويحرسها حتى الخروج. لا توصية تنتظر تنفيذك — بل صفقة تُدار بالكامل."
          : "A system that watches the market around the clock, catches the setup, executes it on your own exchange account, and guards it until exit. Not a signal waiting on you — a fully managed trade."}
      </p>

      <div style={{
        display: "flex", flexDirection: "column", gap: 11,
        maxWidth: 340, margin: "0 auto",
      }}>
        <button onClick={onStart} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          padding: "15px 20px", borderRadius: 13, border: "none", cursor: "pointer",
          background: `linear-gradient(95deg, ${T.brand}, ${T.brand2})`,
          color: "#04121a", fontSize: 15.5, fontWeight: 800,
          boxShadow: `0 8px 26px ${T.brand}33`,
        }}>
          <Zap size={18} />
          {ar ? "ابدأ أسبوعك المجاني" : "Start your free week"}
        </button>

        <button onClick={onPerf} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          padding: "13px 20px", borderRadius: 13, cursor: "pointer",
          background: "transparent", border: `1px solid ${T.border}`,
          color: T.txt, fontSize: 13.5, fontWeight: 600,
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: 7, background: T.brand2,
            boxShadow: `0 0 8px ${T.brand2}`,
          }} />
          <Activity size={16} />
          {ar ? "شاهد الأداء المباشر" : "See live performance"}
        </button>
      </div>

      <div style={{ fontSize: 11, color: T.txt3, marginTop: 14 }}>
        {ar ? "بلا بطاقة ائتمان · ألغِ متى شئت" : "No credit card · Cancel anytime"}
      </div>
    </section>
  );
}
