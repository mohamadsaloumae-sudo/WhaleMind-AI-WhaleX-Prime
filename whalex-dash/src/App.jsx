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
import Landing from "./pages/Landing.jsx";

function Protected() {
  const { user, ready } = useAuth();
  if (!ready) return <div className="loading">جارٍ التحميل…</div>;
  if (!user) return <Navigate to="/login" replace />;

  const isAdmin = user.tier === "admin";

  return (
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
  );
}

function Root() {
  const { user, ready } = useAuth();
  return (
    <Routes>
      {/* 🏁 المقدّمة عامّة — الزائر يقرأها قبل أن يسجّل */}
      <Route path="/landing" element={<Landing />} />
      <Route
        path="/login"
        element={ready && user ? <Navigate to="/" replace /> : <Login />}
      />
      {/* 🏁 الزائر بلا حساب يرى المقدّمة أولاً لا شاشة الدخول */}
      <Route
        path="/*"
        element={
          ready && !user
            ? <Navigate to="/landing" replace />
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
            <Root />
          </BrowserRouter>
        </TierProvider>
      </AuthProvider>
    </LangProvider>
  );
}
