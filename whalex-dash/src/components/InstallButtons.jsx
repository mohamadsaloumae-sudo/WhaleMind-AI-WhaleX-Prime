import { useEffect, useState } from "react";
import { useLang } from "../context/LangContext.jsx";

/**
 * 📱 زرّا تثبيت التطبيق — بحجم الأزرار المعتمدة عالمياً.
 * أندرويد: تثبيت مباشر بضغطة واحدة (بلا توجيهات).
 * آيفون: توجيه، لأن آبل تمنع التثبيت البرمجيّ.
 */
export default function InstallButtons() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [evt, setEvt] = useState(null);
  const [sheet, setSheet] = useState(null);

  useEffect(() => {
    const onP = (e) => { e.preventDefault(); setEvt(e); };
    window.addEventListener("beforeinstallprompt", onP);
    return () => window.removeEventListener("beforeinstallprompt", onP);
  }, []);

  const ua = navigator.userAgent;
  const isIos = /iphone|ipad|ipod/i.test(ua);
  const isSaf = /safari/i.test(ua) && !/crios|fxios|edgios/i.test(ua);

  // 🤖 كروم لا يُطلق beforeinstallprompt إلا بعد تفاعل وبشروطه.
  //    فإن لم يجهز الحدث نعرض إرشاد كروم بدل زرّ ميّت.
  async function android() {
    if (evt) {
      evt.prompt();
      await evt.userChoice;
      setEvt(null);
      return;
    }
    setSheet("android");
  }

  function ios() {
    if (isIos && !isSaf) {
      window.location.href = "x-safari-https://whalemindhybridai.online/";
      return;
    }
    setSheet("ios");
  }

  const btn = {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "9px 16px", borderRadius: 9, cursor: "pointer",
    background: "linear-gradient(180deg,#12b39f,#0d8b7c)",
    border: "1px solid rgba(255,255,255,.14)",
    color: "#03151a", fontSize: 12.5, fontWeight: 700,
    boxShadow: "0 2px 10px rgba(15,163,146,.25)",
    fontFamily: "inherit", whiteSpace: "nowrap",
  };

  return (
    <>
      <div style={{ marginTop: 18, display: "flex", gap: 9,
                    justifyContent: "center", flexWrap: "wrap" }}>
        <button onClick={android}
                style={btn}>
          <Android /> {ar ? "تثبيت" : "Install"}
        </button>
        <button onClick={ios} style={btn}>
          <Apple /> {ar ? "تثبيت" : "Install"}
        </button>
      </div>
      {sheet && <Guide kind={sheet} ar={ar} onClose={() => setSheet(null)} />}
    </>
  );
}

/* 🤖 شعار أندرويد الرسميّ — الروبوت كاملاً */
const Android = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="#3DDC84">
    <path d="M6.28 9.33a1.1 1.1 0 00-1.1 1.1v4.63a1.1 1.1 0 002.2 0v-4.63a1.1 1.1 0 00-1.1-1.1zm11.44 0a1.1 1.1 0 00-1.1 1.1v4.63a1.1 1.1 0 002.2 0v-4.63a1.1 1.1 0 00-1.1-1.1zM8.1 9.5v6.62c0 .5.4.9.9.9h.72v2.36a1.1 1.1 0 002.2 0V17h1.66v2.38a1.1 1.1 0 002.2 0V17h.72c.5 0 .9-.4.9-.9V9.5H8.1z"/>
    <path d="M15.02 5.03l.93-1.7a.23.23 0 00-.09-.31.23.23 0 00-.31.09l-.95 1.73a6.9 6.9 0 00-5.2 0l-.95-1.73a.23.23 0 00-.31-.09.23.23 0 00-.09.31l.93 1.7A6.2 6.2 0 005.9 8.6h12.2a6.2 6.2 0 00-3.08-3.57zM9.4 7.15a.6.6 0 110-1.2.6.6 0 010 1.2zm5.2 0a.6.6 0 110-1.2.6.6 0 010 1.2z"/>
  </svg>
);

/* شعار آبل الرسميّ */
const Apple = () => (
  <svg width="19" height="19" viewBox="0 0 24 24" fill="#03151a">
    <path d="M17.05 12.54c-.02-2.6 2.12-3.85 2.22-3.91-1.21-1.77-3.09-2.01-3.76-2.04-1.6-.16-3.12.94-3.93.94-.81 0-2.06-.92-3.39-.9-1.74.03-3.35.99-4.24 2.51-1.81 3.14-.46 7.79 1.3 10.34.86 1.25 1.88 2.65 3.22 2.6 1.29-.05 1.78-.83 3.34-.83 1.56 0 2 .83 3.37.81 1.39-.02 2.27-1.27 3.12-2.53.98-1.45 1.39-2.85 1.41-2.92-.03-.01-2.7-1.04-2.73-4.11M14.6 4.72c.71-.86 1.19-2.06 1.06-3.25-1.02.04-2.26.68-3 1.54-.66.76-1.24 1.98-1.08 3.15 1.14.09 2.31-.58 3.02-1.44"/>
  </svg>
);

function Guide({ kind, ar, onClose }) {
  const ios = kind === "ios";
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 9999, background: "rgba(0,0,0,.75)",
      display: "flex", alignItems: "flex-end",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: "100%", background: "#0b1e2a", borderRadius: "22px 22px 0 0",
        padding: "24px 20px",
        paddingBottom: "calc(28px + env(safe-area-inset-bottom, 0px))",
        direction: "rtl", textAlign: "right",
        animation: "wxUp .3s ease-out",
      }}>
        <style>{`
          @keyframes wxUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
          @keyframes wxBob{0%,100%{transform:translateY(0);opacity:.5}
                           50%{transform:translateY(8px);opacity:1}}
        `}</style>
        <div style={{ display: "flex", alignItems: "center", gap: 12,
                      marginBottom: 20 }}>
          <img src="/icon-192.png" alt="" width="42" height="42"
               style={{ borderRadius: 11 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 16, color: "#eaf6f4" }}>
              {ios ? (ar ? "التثبيت على آيفون" : "Install on iPhone")
                   : (ar ? "التثبيت على أندرويد" : "Install on Android")}
            </div>
            <div style={{ fontSize: 11.5, color: "#8fa9b4", marginTop: 2 }}>
              {ios ? (ar ? "من متصفّح سفاري" : "From Safari")
                   : (ar ? "من متصفّح كروم" : "From Chrome")}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", color: "#6d8794",
            fontSize: 26, cursor: "pointer", lineHeight: 1,
          }}>×</button>
        </div>
        <Step n="١" t={ios
          ? <>اضغط زرّ المشاركة <Share /> في شريط سفاري الأسفل</>
          : <>اضغط زرّ القائمة <Dots /> أعلى المتصفّح</>} />
        <Step n="٢" t={ios
          ? <>اختر <b style={{ color: "#eaf6f4" }}>إضافة إلى الشاشة الرئيسية</b></>
          : <>اختر <b style={{ color: "#eaf6f4" }}>تثبيت التطبيق</b></>} />
        <Step n="٣" t={<>اضغط <b style={{ color: "#eaf6f4" }}>{ios ? "إضافة" : "تثبيت"}</b> للتأكيد</>} />
        {ios && (
          <div style={{ textAlign: "center", marginTop: 14 }}>
            <div style={{ fontSize: 26, color: "#0fa392",
                          animation: "wxBob 1.5s ease-in-out infinite" }}>⬇︎</div>
          </div>
        )}
      </div>
    </div>
  );
}

const Step = ({ n, t }) => (
  <div style={{ display: "flex", gap: 11, marginBottom: 14 }}>
    <div style={{
      width: 25, height: 25, borderRadius: 8, flexShrink: 0,
      background: "rgba(15,163,146,.16)", color: "#0fa392",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 13, fontWeight: 700,
    }}>{n}</div>
    <div style={{ fontSize: 13.5, color: "#c3d6dd", lineHeight: 1.7,
                  paddingTop: 3 }}>{t}</div>
  </div>
);

const Share = () => (
  <span style={{ display: "inline-flex", padding: "2px 7px", margin: "0 3px",
                 borderRadius: 6, background: "#132a38",
                 verticalAlign: "middle" }}>
    <svg width="12" height="15" viewBox="0 0 14 18" fill="none">
      <path d="M7 1v11M7 1L3.6 4.4M7 1l3.4 3.4" stroke="#4da6ff"
            strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M2 8v8h10V8" stroke="#4da6ff" strokeWidth="1.6"
            strokeLinecap="round"/>
    </svg>
  </span>
);

const Dots = () => (
  <span style={{ display: "inline-block", padding: "1px 9px", margin: "0 3px",
                 borderRadius: 6, background: "#132a38", color: "#eaf6f4",
                 letterSpacing: 1.5, verticalAlign: "middle" }}>⋮</span>
);
