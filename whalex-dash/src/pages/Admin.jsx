// لوحة الإدارة
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Users, Activity, DollarSign } from "lucide-react";

export default function Admin() {
  const { t } = useLang();
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try { setStats(await api.get("/api/admin/stats")); }
      catch (e) { setErr(e.message); }
    })();
  }, []);

  return (
    <>
      {err && <div className="alert info">{t("adminFetchFail")}: {err}</div>}

      <div className="grid grid-3" style={{ marginBottom: 24 }}>
        <div className="card stat">
          <span className="label"><Users size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("users")}</span>
          <span className="value">{stats?.total_users ?? "—"}</span>
        </div>
        <div className="card stat">
          <span className="label"><DollarSign size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("proUsers")}</span>
          <span className="value">{stats?.pro_users ?? "—"}</span>
        </div>
        <div className="card stat">
          <span className="label"><Activity size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("todayTrades")}</span>
          <span className="value">{stats?.trades_today ?? "—"}</span>
        </div>
      </div>

      <div className="card">
        <div className="card-title">{t("manageUsers")}</div>
        <div className="empty">{t("adminHint")}</div>
      </div>
    </>
  );
}
