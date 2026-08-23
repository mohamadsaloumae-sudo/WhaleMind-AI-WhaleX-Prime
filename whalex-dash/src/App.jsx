import React, { Suspense } from "react";
// ════════════════════════════════════════════════════════════
//  جذر التطبيق — يبني الـ routing تلقائياً من PAGES
// ════════════════════════════════════════════════════════════
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { LangProvider } from "./context/LangContext.jsx";
import { TierProvider } from "./context/TierContext.jsx";
import { PAGES } from "./lib/pages.js";
import Layout from "./components/Layout.jsx";
import DeviceGuard from "./components/DeviceGuard.jsx";
import Login from "./pages/Login.jsx";
// 📦 المقدّمة والقانونية كسولتان — المسجَّل لا يحمّلهما إطلاقاً
const Landing = React.lazy(() => import("./pages/Landing.jsx"));
const LegalPage = React.lazy(() => import("./pages/Legal.jsx"));

function Protected() {
  const { user, ready } = useAuth();
  if (!ready) return <div className="loading">جارٍ التحميل…</div>;
  if (!user) return <Navigate to="/login" replace />;

  const isAdmin = user.tier === "admin";

  return (
    <Suspense fallback={<div className="loading">جارٍ التحميل…</div>}>
    <Routes>
      {PAGES.filter((p) => !p.adminOnly || isAdmin).map((p) => {
        const C = p.component;
        return (
          <Route
            key={p.path}
            path={p.path}
            element={p.path === "/support" || p.path === "/landing"
              ? <C />
              : <Layout titleKey={"nav." + p.path}><C /></Layout>}
          />
        );
      })}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  );
}

// 🏁 بوّابة المقدّمة — مكوّن مستقلّ، فالتنقّل داخله لا يُعيد تقييم شرط خارجي
// 🏁 بوّابة المقدّمة — الحالة في sessionStorage لا في الذاكرة.
//    المتغيّر العاديّ يُمحى مع كل تحديث للصفحة، فكان الريفرش يُعيد المقدّمة.
//    sessionStorage يبقى ما دام التبويب مفتوحاً ويُمحى عند إغلاقه — وهو المطلوب.
function introSeen() {
  try { return sessionStorage.getItem("wx_intro_done") === "1"; }
  catch { return window.__wxIntroDone === true; }
}

function markIntroSeen() {
  try { sessionStorage.setItem("wx_intro_done", "1"); } catch { /* */ }
  window.__wxIntroDone = true;
}

function IntroGate({ children }) {
  const [done, setDone] = React.useState(introSeen);
  React.useEffect(() => {
    const on = () => setDone(true);
    window.addEventListener("wx-intro-done", on);
    return () => window.removeEventListener("wx-intro-done", on);
  }, []);
  if (done) return children;
  return <Navigate to="/landing" replace />;
}

function Root() {
  const { user, ready } = useAuth();
  return (
    <Routes>
      {/* 🏁 المقدّمة عامّة — الزائر يقرأها قبل أن يسجّل */}
      <Route path="/landing" element={<Landing />} />
      <Route path="/legal" element={<LegalPage />} />
      <Route
        path="/login"
        element={ready && user ? <Navigate to="/" replace /> : <Login />}
      />
      {/* 🏁 الزائر بلا حساب يرى المقدّمة أولاً لا شاشة الدخول */}
      <Route
        path="*"
        element={
          ready && !user
            ? <Navigate to="/landing" replace />

            : window.location.pathname === "/" && !introSeen()
              ? <IntroGate><DeviceGuard><Protected /></DeviceGuard></IntroGate>
              : <DeviceGuard><Protected /></DeviceGuard>
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <LangProvider>
      <AuthProvider>
        <TierProvider>
          <BrowserRouter>
      <Suspense fallback={<div className="loading">جارٍ التحميل…</div>}>
            <Root />
            </Suspense>
    </BrowserRouter>
        </TierProvider>
      </AuthProvider>
    </LangProvider>
  );
}
