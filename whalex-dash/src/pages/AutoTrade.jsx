// التداول — ربط Binance + اختيار آلي/يدوي
import { useEffect, useState } from "react";
import { binance } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Bot, Hand, Link2, Unlink } from "lucide-react";

export default function AutoTrade() {
  const { t } = useLang();
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("auto");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [testnet, setTestnet] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function loadStatus() {
    try { setStatus(await binance.status()); } catch { setStatus({ connected: false }); }
  }
  useEffect(() => { loadStatus(); }, []);

  async function connect(e) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await binance.connect({ api_key: apiKey, api_secret: apiSecret, is_testnet: testnet, account_type: testnet ? "demo" : "real" });
      setMsg({ type: "success", text: t("connectSuccess") });
      setApiKey(""); setApiSecret("");
      loadStatus();
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally { setBusy(false); }
  }

  async function disconnect() {
    setBusy(true);
    try { await binance.disconnect(); setMsg({ type: "info", text: t("disconnectDone") }); loadStatus(); }
    catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  async function toggleAuto(enabled) {
    try { await binance.autoTrade({ enabled }); loadStatus(); }
    catch (e) { setMsg({ type: "error", text: e.message }); }
  }

  const connected = status?.connected;

  return (
    <div style={{ maxWidth: 640 }}>
      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

      <div className="mode-switch">
        <button className={`mode-btn ${mode === "auto" ? "active" : ""}`} onClick={() => setMode("auto")}>
          <Bot size={22} /> {t("autoTrade")}
        </button>
        <button className={`mode-btn ${mode === "manual" ? "active" : ""}`} onClick={() => setMode("manual")}>
          <Hand size={22} /> {t("manualTrade")}
        </button>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">{t("binanceStatus")}</div>
        {connected ? (
          <div className="toggle-row">
            <span style={{ color: "var(--green)", fontWeight: 700 }}>● {t("connected")} {status.is_testnet ? `(${t("testnetMode")})` : `(${t("realMode")})`}</span>
            <button className="btn btn-danger" onClick={disconnect} disabled={busy}>
              <Unlink size={16} /> {t("disconnect")}
            </button>
          </div>
        ) : (
          <form onSubmit={connect}>
            <div className="field">
              <label>{t("apiKey")}</label>
              <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} required placeholder={t("binanceKeyPlaceholder")} />
            </div>
            <div className="field">
              <label>{t("apiSecret")}</label>
              <input type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} required placeholder={t("secretPlaceholder")} />
            </div>
            <div className="toggle-row">
              <span>{t("testnetToggle")}</span>
              <label className="switch">
                <input type="checkbox" checked={testnet} onChange={(e) => setTestnet(e.target.checked)} />
                <span className="slider" />
              </label>
            </div>
            <button className="btn btn-primary btn-block" disabled={busy}>
              <Link2 size={16} /> {busy ? t("processing") : t("connectAccount")}
            </button>
          </form>
        )}
      </div>

      {connected && mode === "auto" && (
        <div className="card">
          <div className="toggle-row" style={{ margin: 0 }}>
            <div>
              <strong>{t("enableAutoTrade")}</strong>
              <p style={{ fontSize: 13, color: "var(--txt-2)", marginTop: 4 }}>{t("autoTradeDesc")}</p>
            </div>
            <label className="switch">
              <input type="checkbox" defaultChecked={status?.auto_trade_enabled}
                     onChange={(e) => toggleAuto(e.target.checked)} />
              <span className="slider" />
            </label>
          </div>
        </div>
      )}

      {connected && mode === "manual" && (
        <div className="card"><div className="empty">{t("manualHint")}</div></div>
      )}
    </div>
  );
}
