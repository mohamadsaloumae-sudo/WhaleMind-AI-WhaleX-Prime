// التداول — ربط Binance + اختيار آلي/يدوي + إعدادات التداول
import { useEffect, useState } from "react";
import { binance } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Bot, Hand, Link2, Unlink, Save } from "lucide-react";
import Paywall from "../components/Paywall.jsx";

export default function AutoTrade() {
  const { t } = useLang();
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [mode, setMode] = useState("auto");
  const [spotBusy, setSpotBusy] = useState(false);
  async function toggleSpot() {
    if (spotBusy) return; setSpotBusy(true);
    try {
      const r = await binance.autoTrade({ spot_enabled: !settings?.spot_auto_enabled });
      if (r?.success) setSettings((s) => ({ ...s, spot_auto_enabled: r.spot_auto_enabled }));
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setSpotBusy(false); }
  }
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [testnet, setTestnet] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [balance, setBalance] = useState(null);

  // حقول الإعدادات
  const [amount, setAmount] = useState(20);
  const [maxPos, setMaxPos] = useState(3);
  const [grades, setGrades] = useState("AS");
  const [leverage, setLeverage] = useState(20);

  async function loadStatus() {
    try {
      const st = await binance.status();
      setStatus(st);
      if (st?.connected) {
        const s = await binance.settings();
        setSettings(s);
        if (s.trade_amount_usdt) setAmount(s.trade_amount_usdt);
        if (s.max_open_positions) setMaxPos(s.max_open_positions);
        if (s.allowed_grades) setGrades(s.allowed_grades);
        if (s.leverage) setLeverage(s.leverage);
        try { setBalance(await binance.balance()); } catch { /* */ }
      }
    } catch { setStatus({ connected: false }); }
  }
  useEffect(() => { loadStatus(); }, []);

  // تحديث الرصيد تلقائياً كل 10 ثوانٍ
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const st = await binance.status();
        if (st?.connected) setBalance(await binance.balance());
      } catch { /* */ }
    }, 10000);
    return () => clearInterval(id);
  }, []);

  async function connect(e) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await binance.connect({ api_key: apiKey, api_secret: apiSecret, is_testnet: testnet, account_type: "futures" });
      setMsg({ type: "success", text: t("connectSuccess") });
      setApiKey(""); setApiSecret("");
      loadStatus();
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  async function disconnect() {
    setBusy(true);
    try { await binance.disconnect(); setMsg({ type: "info", text: t("disconnectDone") }); setSettings(null); loadStatus(); }
    catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  async function saveSettings(enabled) {
    setBusy(true); setMsg(null);
    try {
      const r = await binance.autoTrade({
        enabled: enabled !== undefined ? enabled : settings?.auto_trade_enabled,
        trade_amount_usdt: Number(amount),
        max_open_positions: Number(maxPos),
        allowed_grades: grades,
        leverage: Number(leverage),
      });
      setSettings(r);
      setMsg({ type: "success", text: t("save") + " ✓" });
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  const connected = status?.connected;
  const autoOn = settings?.auto_trade_enabled;

  return (
    <Paywall>
    <div style={{ maxWidth: 640 }}>
      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

      <div className="mode-switch">
        <button className={`mode-btn ${mode === "auto" ? "active" : ""}`} onClick={() => setMode("auto")}>
          <Bot size={22} /> {t("autoFutures")}
        </button>
        <button className={`mode-btn ${mode === "spot" ? "active" : ""}`} onClick={() => setMode("spot")}>
          🪙 {t("autoSpot")}
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

      {connected && balance?.futures && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">{t("balance")}</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 13, color: "var(--txt-2)" }}>{t("availableBalance")}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--brand)" }}>{Number(balance.futures?.available_balance || 0).toFixed(2)} USDT</div>
            </div>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 13, color: "var(--txt-2)" }}>{t("totalBalance")}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{Number(balance.futures?.total_wallet_balance || 0).toFixed(2)}</div>
            </div>
          </div>
        </div>
      )}

      {connected && mode === "auto" && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="toggle-row" style={{ margin: 0 }}>
              <div>
                <strong>{t("enableAutoTrade")}</strong>
                <p style={{ fontSize: 13, color: "var(--txt-2)", marginTop: 4 }}>{t("autoTradeDesc")}</p>
              </div>
              <label className="switch">
                <input type="checkbox" checked={!!autoOn} onChange={(e) => saveSettings(e.target.checked)} />
                <span className="slider" />
              </label>
            </div>
          </div>

          <div className="card">
            <div className="card-title">{t("tradeSettings")}</div>
            <div className="field">
              <label>{t("amountPerTrade")} (USDT)</label>
              <input type="number" min="10" max="10000" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("maxPositions")}</label>
              <input type="number" min="1" max="10" value={maxPos} onChange={(e) => setMaxPos(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("allowedGrades")}</label>
              <select value={grades} onChange={(e) => setGrades(e.target.value)}>
                <option value="S">S {t("only")}</option>
                <option value="AS">A + S</option>
                <option value="ASB">A + S + B</option>
              </select>
            </div>
            <div className="field">
              <label>{t("leverage") || "الرافعة المالية"}</label>
              <select value={leverage} onChange={(e) => setLeverage(e.target.value)}>
                <option value="3">3x</option>
                <option value="5">5x</option>
                <option value="10">10x</option>
                <option value="20">20x</option>
                <option value="50">50x</option>
                <option value="75">75x</option>
                <option value="100">100x</option>
              </select>
            </div>
            <button className="btn btn-primary btn-block" onClick={() => saveSettings()} disabled={busy}>
              <Save size={16} /> {busy ? t("processing") : t("save")}
            </button>
          </div>
        </>
      )}

      {mode === "spot" && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">🪙 {t("autoSpot")}</div>
          <div className="toggle-row" style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{settings?.spot_auto_enabled ? "✅ " : "⭕ "}{t("autoSpotState")}</span>
            <button className="btn" onClick={toggleSpot} disabled={spotBusy}
              style={{ padding: "8px 16px", borderRadius: 10, border: 0, fontWeight: 700,
                       background: settings?.spot_auto_enabled ? "var(--red)" : "var(--brand)",
                       color: settings?.spot_auto_enabled ? "#fff" : "#04211c" }}>
              {settings?.spot_auto_enabled ? t("disable") : t("enable")}
            </button>
          </div>
          <div style={{ color: "var(--txt-3)", fontSize: 12, marginTop: 10 }}>{t("autoSpotNote")}</div>
        </div>
      )}
    </div>
    </Paywall>
  );
}
