// الرئيسية — نظرة عامة
import { useEffect, useState } from "react";
import { Activity, Radio } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function Dashboard() {
  const { t } = useLang();
  const [live, setLive] = useState(false);

  useEffect(() => {
    let ws;
    try {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setLive(true);
      ws.onclose = () => setLive(false);
    } catch { /* تجاهل */ }
    return () => ws && ws.close();
  }, []);

  return (
    <>
      <div className="grid grid-4" style={{ marginBottom: 24 }}>
        <div className="card stat">
          <span className="label">{t("status")}</span>
          <span className="value green" style={{ fontSize: 20 }}>
            {live ? t("connectedLive") : t("notConnected")}
          </span>
        </div>
        <div className="card stat">
          <span className="label">{t("openTrades")}</span>
          <span className="value">—</span>
        </div>
        <div className="card stat">
          <span className="label">{t("todayProfit")}</span>
          <span className="value green">—</span>
        </div>
        <div className="card stat">
          <span className="label">{t("winRate")}</span>
          <span className="value">—</span>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title"><Radio size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("radarsStatus")}</div>
          <div className="toggle-row">
            <span>Peak Hunter — SHORT/LONG</span>
            <span className="badge grade">{t("working")}</span>
          </div>
          <div className="toggle-row">
            <span>Predator</span>
            <span className="badge grade">{t("working")}</span>
          </div>
        </div>
        <div className="card">
          <div className="card-title"><Activity size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("recentActivity")}</div>
          <div className="empty">{t("liveActivityHint")}</div>
        </div>
      </div>
    </>
  );
}
