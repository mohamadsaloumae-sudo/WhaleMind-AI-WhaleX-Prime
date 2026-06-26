// ════════════════════════════════════════════════════════════
//  جذر التطبيق — يبني الـ routing تلقائياً من PAGES
// ════════════════════════════════════════════════════════════
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import { LangProvider } from "./context/LangContext.jsx";
import { PAGES } from "./lib/pages.js";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";

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
            element={<Layout titleKey={"nav." + p.path}><C /></Layout>}
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
      <Route
        path="/login"
        element={ready && user ? <Navigate to="/" replace /> : <Login />}
      />
      <Route path="/*" element={<Protected />} />
    </Routes>
  );
}

export default function App() {
  return (
    <LangProvider>
      <AuthProvider>
        <BrowserRouter>
          <Root />
        </BrowserRouter>
      </AuthProvider>
    </LangProvider>
  );
}
