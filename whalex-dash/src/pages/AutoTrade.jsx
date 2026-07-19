// التداول — ربط Binance + اختيار آلي/يدوي + إعدادات التداول
import { useEffect, useState } from "react";
import { binance } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Bot, Hand, Link2, Unlink, Save } from "lucide-react";
import Paywall from "../components/Paywall.jsx";

export default function AutoTrade() {
  const { t, lang } = useLang();
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [mode, setMode] = useState(localStorage.getItem("wx_auto_mode") || "auto");
  useEffect(() => { localStorage.setItem("wx_auto_mode", mode); }, [mode]);
  const [spotBusy, setSpotBusy] = useState(false);
  async function toggleSpot() {
    if (spotBusy) return; setSpotBusy(true);
    try {
      const r = await binance.autoTrade({ spot_enabled: !settings?.spot_auto_enabled });
      if (r?.success) setSettings((s) => ({ ...s, spot_auto_enabled: r.spot_auto_enabled }));
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setSpotBusy(false); }
  }
  const [spotSaved, setSpotSaved] = useState(false);
  const [spotErr, setSpotErr] = useState("");
  const [spotTot, setSpotTot] = useState(0);
  useEffect(() => { const t = balance?.usdt_total_spot ?? balance?.usdt_free; if (t && t > 0) setSpotTot(t); }, [balance]);
  async function saveSpot(patch) {
    try {
      const r = await binance.autoTrade(patch);
      if (r?.success) { setSettings((s) => ({ ...s, ...patch })); setSpotSaved(true); setTimeout(() => setSpotSaved(false), 1800); }
    } catch { /* */ }
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
          <Bot size={22} /> {t("autoSpot")}
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

      {connected && (balance?.futures || balance?.spot) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">{t("balance")}</div>
          {mode === "spot" ? (
            <div>
              <div style={{ fontSize: 13, color: "var(--txt-2)" }}>{lang === "ar" ? "رصيد السبوت الكلي" : "Total spot balance"}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--brand)" }}>{(spotTot ?? 0).toFixed(2)} USDT</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>{lang === "ar" ? "المتاح للشراء" : "Available"}: {(balance?.usdt_free ?? 0).toFixed(2)} USDT</div>
            </div>
          ) : (
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
          )}
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="card-title">🪙 {t("autoSpot")}</div>
            {spotSaved && <span style={{ fontSize: 12, fontWeight: 700, color: "var(--brand)" }}>✓ {lang === "ar" ? "حُفظ" : "Saved"}</span>}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <span>{settings?.spot_auto_enabled ? "✅ " : "⭕ "}{t("autoSpotState")}</span>
            <div onClick={() => !spotBusy && toggleSpot()}
              style={{ width: 52, height: 28, borderRadius: 14, cursor: "pointer", flexShrink: 0,
                       background: settings?.spot_auto_enabled ? "var(--brand)" : "#3a3a3a",
                       position: "relative", transition: "background .2s", opacity: spotBusy ? 0.5 : 1 }}>
              <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#fff",
                            position: "absolute", top: 3, left: settings?.spot_auto_enabled ? 27 : 3,
                            transition: "left .2s" }} />
            </div>
          </div>
          <div style={{ fontSize: 13, color: "var(--txt-2)", margin: "14px 0 6px" }}>{lang === "ar" ? "مبلغ كل صفقة (USDT)" : "Amount per trade (USDT)"}</div>
          <input type="number" min="5" defaultValue={settings?.spot_trade_amount || 5}
            onBlur={(e) => {
              const bal = spotTot ?? 0;
              const amt = parseFloat(e.target.value) || 5;
              if (amt > bal) { setSpotErr(lang === "ar" ? `رصيدك ${bal.toFixed(2)}$ لا يكفي — أعد الشحن` : `Balance ${bal.toFixed(2)}$ insufficient — top up`); e.target.value = settings?.spot_trade_amount || 5; return; }
              setSpotErr("");
              const maxT = Math.max(1, Math.floor(bal / amt));
              const patch = { spot_trade_amount: amt };
              if ((settings?.spot_max_positions ?? 0) !== 0) patch.spot_max_positions = Math.min(settings?.spot_max_positions || maxT, maxT);
              saveSpot(patch);
            }}
            style={{ width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid var(--bg-2)", background: "var(--bg-1)", color: "var(--txt-0)", boxSizing: "border-box" }} />
          {spotErr ? (
            <div style={{ fontSize: 12, color: "var(--red)", marginTop: 6 }}>⚠️ {spotErr}</div>
          ) : (
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>
              {lang === "ar" ? `رصيدك يكفي ` : `Balance covers `}<b>{Math.max(0, Math.floor((spotTot ?? 0) / (settings?.spot_trade_amount || 5)))}</b>{lang === "ar" ? ` صفقة` : ` trades`}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "14px 0 6px" }}>
            <span style={{ fontSize: 13, color: "var(--txt-2)" }}>{lang === "ar" ? "أوتو (كل الصفقات)" : "Auto (all signals)"}</span>
            <div onClick={() => saveSpot({ spot_max_positions: (settings?.spot_max_positions ?? 0) === 0 ? Math.max(1, Math.floor((spotTot ?? 0) / (settings?.spot_trade_amount || 5))) : 0 })}
              style={{ width: 52, height: 28, borderRadius: 14, cursor: "pointer", flexShrink: 0,
                       background: (settings?.spot_max_positions ?? 0) === 0 ? "var(--brand)" : "#3a3a3a",
                       position: "relative", transition: "background .2s" }}>
              <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#fff",
                            position: "absolute", top: 3, left: (settings?.spot_max_positions ?? 0) === 0 ? 27 : 3, transition: "left .2s" }} />
            </div>
          </div>
          {(settings?.spot_max_positions ?? 0) !== 0 && (
            <>
              <div style={{ fontSize: 13, color: "var(--txt-2)", margin: "8px 0 6px" }}>{lang === "ar" ? "عدد الصفقات" : "Number of trades"}</div>
              <input type="number" min="1" value={settings?.spot_max_positions || 1}
                onChange={(e) => {
                  const bal = spotTot ?? 0;
                  const maxT = Math.max(1, Math.floor(bal / (settings?.spot_trade_amount || 5)));
                  const v = Math.min(Math.max(1, parseInt(e.target.value) || 1), maxT);
                  saveSpot({ spot_max_positions: v });
                }}
                style={{ width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid var(--bg-2)", background: "var(--bg-1)", color: "var(--txt-0)", boxSizing: "border-box" }} />
              <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 4 }}>
                {lang === "ar" ? `الحد الأقصى بحسب رصيدك: ` : `Max by your balance: `}<b>{Math.max(1, Math.floor((spotTot ?? 0) / (settings?.spot_trade_amount || 5)))}</b>
              </div>
            </>
          )}
        </div>
      )}
    </div>
    </Paywall>
  );
}
