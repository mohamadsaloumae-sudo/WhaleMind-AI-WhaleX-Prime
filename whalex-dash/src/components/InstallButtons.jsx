import { useEffect, useState } from "react";

/**
 * 📱 زرّا تثبيت التطبيق — يكتشفان الجهاز ويتصرّفان.
 *
 * أندرويد: ضغطة واحدة تُثبّت عبر beforeinstallprompt.
 * آيفون في كروم: ننقله إلى سفاري (آبل تمنع التثبيت خارج سفاري).
 * آيفون في سفاري: إرشاد بصريّ — سهم متحرّك يُشير لزرّ المشاركة.
 */
export default function InstallButtons() {
  const [evt, setEvt] = useState(null);
  const [sheet, setSheet] = useState(null);   // "ios" | "android" | null
  const [done, setDone] = useState(false);

  useEffect(() => {
    const std = window.matchMedia?.("(display-mode: standalone)")?.matches
      || window.navigator.standalone === true;
    setDone(std);
    const onP = (e) => { e.preventDefault(); setEvt(e); };
    window.addEventListener("beforeinstallprompt", onP);
    return () => window.removeEventListener("beforeinstallprompt", onP);
  }, []);

  const ua = navigator.userAgent;
  const isIos = /iphone|ipad|ipod/i.test(ua);
  const isSaf = /safari/i.test(ua) && !/crios|fxios|edgios/i.test(ua);

  async function android() {
    if (evt) { evt.prompt(); await evt.userChoice; setEvt(null); return; }
    setSheet("android");
  }

  function ios() {
    if (isIos && !isSaf) {
      window.location.href = "x-safari-https://whalemindhybridai.online/";
      setTimeout(() => setSheet("ios"), 900);
      return;
    }
    setSheet("ios");
  }

  if (done) return null;

  const btn = {
    flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
    gap: 7, padding: "15px 10px", borderRadius: 16, cursor: "pointer",
    background: "rgba(15,163,146,.09)", border: "1px solid rgba(15,163,146,.28)",
    color: "#eaf6f4", fontSize: 13, fontWeight: 600,
  };

  return (
    <>
      <div style={{ marginTop: 22, direction: "rtl" }}>
        <div style={{ fontSize: 12.5, color: "#8fa9b4", marginBottom: 10,
                      textAlign: "center" }}>
          ثبّت التطبيق على جهازك
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={android} style={btn}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9.5" stroke="#0fa392" strokeWidth="1.6"/>
              <circle cx="12" cy="12" r="3.4" stroke="#0fa392" strokeWidth="1.6"/>
              <path d="M12 2.5v6M20.5 16.5l-5.2-3M3.5 16.5l5.2-3"
                    stroke="#0fa392" strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
            أندرويد
            <span style={{ fontSize: 10.5, color: "#7c98a4", fontWeight: 400 }}>
              تثبيت مباشر
            </span>
          </button>
          <button onClick={ios} style={btn}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <path d="M16.2 12.6c0-2.4 1.9-3.5 2-3.6-1.1-1.6-2.8-1.8-3.4-1.9-1.5-.15-2.9.85-3.6.85-.75 0-1.9-.83-3.1-.8-1.6.02-3.05.92-3.87 2.34-1.65 2.87-.42 7.1 1.18 9.42.78 1.13 1.72 2.4 2.94 2.36 1.18-.05 1.63-.77 3.06-.77 1.42 0 1.83.77 3.07.74 1.27-.02 2.07-1.16 2.85-2.3.9-1.32 1.27-2.6 1.29-2.66-.03-.01-2.47-.95-2.5-3.76z"
                    fill="#0fa392"/>
              <path d="M13.9 5.3c.65-.79 1.09-1.88.97-2.97-.94.04-2.07.62-2.74 1.4-.6.7-1.13 1.81-.99 2.88 1.05.08 2.12-.53 2.76-1.31z"
                    fill="#0fa392"/>
            </svg>
            آيفون
            <span style={{ fontSize: 10.5, color: "#7c98a4", fontWeight: 400 }}>
              عبر سفاري
            </span>
          </button>
        </div>
      </div>

      {sheet && <Guide kind={sheet} onClose={() => setSheet(null)} />}
    </>
  );
}

function Guide({ kind, onClose }) {
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
        animation: "wxUp .32s ease-out",
      }}>
        <style>{`
          @keyframes wxUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
          @keyframes wxBob{0%,100%{transform:translateY(0);opacity:.55}
                           50%{transform:translateY(9px);opacity:1}}
        `}</style>

        <div style={{ display: "flex", alignItems: "center", gap: 12,
                      marginBottom: 20 }}>
          <img src="/icon-192.png" alt="" width="44" height="44"
               style={{ borderRadius: 12 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 16.5, color: "#eaf6f4" }}>
              {ios ? "التثبيت على آيفون" : "التثبيت على أندرويد"}
            </div>
            <div style={{ fontSize: 12, color: "#8fa9b4", marginTop: 2 }}>
              {ios ? "من متصفّح سفاري" : "من متصفّح كروم"}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", color: "#6d8794",
            fontSize: 26, cursor: "pointer", lineHeight: 1,
          }}>×</button>
        </div>

        <Step n="١" text={ios
          ? <>اضغط زرّ المشاركة <Share/> في شريط سفاري الأسفل</>
          : <>اضغط زرّ القائمة <Dots/> أعلى المتصفّح</>} />
        <Step n="٢" text={ios
          ? <>اختر <b style={{color:"#eaf6f4"}}>إضافة إلى الشاشة الرئيسية</b></>
          : <>اختر <b style={{color:"#eaf6f4"}}>تثبيت التطبيق</b></>} />
        <Step n="٣" text={<>اضغط <b style={{color:"#eaf6f4"}}>إضافة</b> — وسيظهر التطبيق على شاشتك</>} />

        {ios && (
          <div style={{ textAlign: "center", marginTop: 18 }}>
            <div style={{ fontSize: 30, color: "#0fa392",
                          animation: "wxBob 1.5s ease-in-out infinite" }}>⬇︎</div>
            <div style={{ fontSize: 11.5, color: "#7c98a4", marginTop: 2 }}>
              زرّ المشاركة في الأسفل
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Step({ n, text }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start",
                  marginBottom: 15 }}>
      <div style={{
        width: 27, height: 27, borderRadius: 9, flexShrink: 0,
        background: "rgba(15,163,146,.16)", color: "#0fa392",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 13.5, fontWeight: 700,
      }}>{n}</div>
      <div style={{ fontSize: 14, color: "#c3d6dd", lineHeight: 1.75,
                    paddingTop: 3 }}>{text}</div>
    </div>
  );
}

const Share = () => (
  <span style={{ display: "inline-flex", alignItems: "center",
                 padding: "2px 8px", margin: "0 4px", borderRadius: 7,
                 background: "#123", verticalAlign: "middle" }}>
    <svg width="13" height="16" viewBox="0 0 14 18" fill="none">
      <path d="M7 1v11M7 1L3.6 4.4M7 1l3.4 3.4" stroke="#4da6ff"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M2 8v8h10V8" stroke="#4da6ff" strokeWidth="1.5"
            strokeLinecap="round"/>
    </svg>
  </span>
);

const Dots = () => (
  <span style={{ display: "inline-block", padding: "2px 9px", margin: "0 4px",
                 borderRadius: 7, background: "#123", color: "#eaf6f4",
                 letterSpacing: 1.5, verticalAlign: "middle" }}>⋮</span>
);
