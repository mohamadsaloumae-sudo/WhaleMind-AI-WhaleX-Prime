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
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
