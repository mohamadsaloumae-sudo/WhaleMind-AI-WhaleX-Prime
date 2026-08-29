import { useEffect, useState } from "react";

export default function InstallPrompt() {
  const [evt, setEvt] = useState(null);
  const [show, setShow] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    const done = window.matchMedia?.("(display-mode: standalone)")?.matches
      || window.navigator.standalone === true;
    if (done) return;
    if (localStorage.getItem("wx_install_no")) return;

    const ua = navigator.userAgent;
    const isIos = /iphone|ipad|ipod/i.test(ua) && !window.MSStream;
    const isSaf = /safari/i.test(ua) && !/crios|fxios|edgios/i.test(ua);

    const onP = (e) => {
      e.preventDefault();
      setEvt(e);
      setTimeout(() => setShow(true), 2500);
    };
    window.addEventListener("beforeinstallprompt", onP);
    if (isIos && isSaf) {
      setIos(true);
      setTimeout(() => setShow(true), 2500);
    }
    return () => window.removeEventListener("beforeinstallprompt", onP);
  }, []);

  async function go() {
    if (!evt) return;
    evt.prompt();
    const r = await evt.userChoice;
    if (r?.outcome === "accepted") localStorage.setItem("wx_install_no", "1");
    setShow(false); setEvt(null);
  }

  function no() {
    localStorage.setItem("wx_install_no", "1");
    setShow(false);
  }

  if (!show) return null;

  const box = {
    position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 9999,
    background: "#0b1e2a", borderTop: "1px solid #17394a",
    borderRadius: "20px 20px 0 0", padding: "20px 18px",
    paddingBottom: "calc(20px + env(safe-area-inset-bottom, 0px))",
    boxShadow: "0 -8px 32px rgba(0,0,0,.5)",
    animation: "wxUp .35s ease-out", direction: "rtl", textAlign: "right",
  };

  return (
    <div style={box}>
      <style>{"@keyframes wxUp{from{transform:translateY(100%)}to{transform:translateY(0)}}"}</style>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <img src="/icon-192.png" alt="" width="46" height="46"
             style={{ borderRadius: 12, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "#eaf6f4" }}>
            ثبّت تطبيق WhaleX
          </div>
          <div style={{ fontSize: 12.5, color: "#8fa9b4", marginTop: 3 }}>
            وصول أسرع وإشعارات فورية بالإشارات
          </div>
        </div>
        <button onClick={no} style={{
          background: "none", border: "none", color: "#6d8794",
          fontSize: 24, cursor: "pointer", padding: "0 4px", lineHeight: 1,
        }}>×</button>
      </div>
      {ios ? (
        <div style={{ fontSize: 13.5, color: "#c3d6dd", lineHeight: 2 }}>
          <div style={{ marginBottom: 6 }}>خطوتان في سفاري:</div>
          <div>١. اضغط زرّ المشاركة <b>⬆︎</b> في الشريط الأسفل</div>
          <div>٢. اختر <b style={{ color: "#eaf6f4" }}>إضافة إلى الشاشة الرئيسية</b></div>
        </div>
      ) : (
        <button onClick={go} disabled={!evt} style={{
          width: "100%", padding: "13px 0", border: "none", borderRadius: 13,
          fontSize: 15.5, fontWeight: 700, color: "#04121a",
          cursor: evt ? "pointer" : "default",
          background: evt ? "#0fa392" : "#2a3f49",
        }}>{evt ? "تثبيت التطبيق" : "جارٍ التحضير…"}</button>
      )}
    </div>
  );
}
