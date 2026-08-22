import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles/tokens.css";
import "./styles/app.css";

// 🎁 رمز الإحالة من الرابط — يُحفظ ليُرسَل عند التسجيل
try {
  const _r = new URLSearchParams(window.location.search).get("ref");
  if (_r) localStorage.setItem("wx_ref", String(_r).trim().toUpperCase());
} catch { /* لا نُعطّل الإقلاع لأجل هذا */ }

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// تسجيل Service Worker — يجعل المنصّة تطبيقاً قابلاً للتثبيت (PWA)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").then((reg) => {
      // 🔄 تحديث ذاتيّ — العميل لا يمسح شيئاً بيده
      reg.update();
      setInterval(() => reg.update(), 60 * 60 * 1000);
      reg.addEventListener("updatefound", () => {
        const nw = reg.installing;
        if (!nw) return;
        nw.addEventListener("statechange", () => {
          if (nw.state === "installed" && navigator.serviceWorker.controller) {
            // نسخة جديدة جاهزة — نفعّلها ونُعيد التحميل مرّة واحدة
            nw.postMessage({ type: "SKIP_WAITING" });
          }
        });
      });
      let reloaded = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (reloaded) return;
        reloaded = true;
        window.location.reload();
      });
    }).catch(() => {});
  });
}
