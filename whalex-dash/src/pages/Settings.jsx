// الإعدادات
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { User, Shield, LogOut } from "lucide-react";

export default function Settings() {
  const { user, logout } = useAuth();
  const { t } = useLang();

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title"><User size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("account")}</div>
        <div style={{ display: "grid", gap: 12, fontSize: 14 }}>
          <div className="toggle-row" style={{ margin: 0 }}>
            <span style={{ color: "var(--txt-2)" }}>{t("userId")}</span>
            <span style={{ fontFamily: "monospace" }}>{user?.uid}</span>
          </div>
          <div className="toggle-row" style={{ margin: 0 }}>
            <span style={{ color: "var(--txt-2)" }}>{t("plan")}</span>
            <span className="badge grade">{user?.tier}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title"><Shield size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("security")}</div>
        <p style={{ fontSize: 13.5, color: "var(--txt-2)", marginBottom: 16 }}>{t("securityDesc")}</p>
        <button className="btn btn-danger" onClick={logout}>
          <LogOut size={16} /> {t("logout")}
        </button>
      </div>
    </div>
  );
}
