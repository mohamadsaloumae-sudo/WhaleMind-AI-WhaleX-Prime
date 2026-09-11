import { useEffect, useState } from "react";
import { ChevronDown, ChevronLeft, TrendingUp, TrendingDown } from "lucide-react";

/* 📒 دفتر حساب المشترك — مصدر واحد: user_trades (التنفيذ الحقيقي).
   ما لم يُفتح على المنصّة لا يُعرض. الترتيب زمنيّ دائماً، مجمّع بالأيام. */

const f = (n, d = 2) => (n === null || n === undefined ? "—" : Number(n).toFixed(d));
const usd = (n) => (n > 0 ? "+" : "") + f(n) + "$";
const pct = (n) => (n > 0 ? "+" : "") + f(n, 2) + "%";
const cls = (n) => (n > 0 ? "pos" : n < 0 ? "neg" : "");

const dayName = (iso) => {
  const d = new Date(iso + "T00:00:00");
  const today = new Date();
  const diff = Math.round((today.setHours(0, 0, 0, 0) - d) / 86400000);
  if (diff === 0) return "اليوم";
  if (diff === 1) return "أمس";
  return d.toLocaleDateString("ar-EG-u-nu-latn", { weekday: "long", day: "numeric", month: "long" });
};

const hm = (ts) =>
  new Date(ts * 1000).toLocaleTimeString("ar-EG-u-nu-latn", {
    hour: "2-digit", minute: "2-digit", hour12: false,
  });

const MKT = { futures: "⚡ الفيوتشر", spot: "🪙 السبوت", meme: "🐸 الميم" };

export default function UserLedger({ userId, days = 30, market = "futures" }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [openDays, setOpenDays] = useState({});

  useEffect(() => {
    if (!userId) return;
    let alive = true;
    const load = (first) => {
      if (first) { setData(null); setErr(""); }
      fetch(`/api/admin/user/${userId}/ledger?days=${days}&market=${market}`)
        .then((r) => r.json())
        .then((d) => { if (alive) d.error ? setErr(d.error) : setData(d); })
        .catch((e) => alive && first && setErr(String(e)));
    };
    load(true);
    const t = setInterval(() => load(false), 5000);   // 📡 المفتوحة حيّة
    return () => { alive = false; clearInterval(t); };
  }, [userId, days, market]);

  if (err) return <div className="alert info">تعذّر جلب الدفتر: {err}</div>;
  if (!data) return <div className="card" style={{ padding: 20, opacity: .6 }}>جارٍ التحميل…</div>;

  const m = data.overall || {};
  const pf = m.profit_factor;

  return (
    <div className="ledger">
      <div style={{ fontSize: 12, fontWeight: 700, opacity: .7, marginBottom: 8 }}>
        {MKT[market] || market}
      </div>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="card stat">
          <span className="label">الصافي بعد الرسوم</span>
          <span className={"value " + cls(m.net)}>{usd(m.net)}</span>
          <span className="sub">{m.n} صفقة</span>
        </div>
        <div className="card stat">
          <span className="label">معامل الربح</span>
          <span className={"value " + (pf >= 1.5 ? "pos" : pf >= 1 ? "" : "neg")}>{f(pf)}</span>
          <span className="sub">{pf >= 1.5 ? "جيّد" : pf >= 1 ? "حدّيّ" : "خاسر"}</span>
        </div>
        <div className="card stat">
          <span className="label">نسبة الفوز</span>
          <span className="value">{f(m.win_rate, 1)}%</span>
          <span className="sub">متوسّط {usd(m.expectancy)} / صفقة</span>
        </div>
        <div className="card stat">
          <span className="label">أقصى تراجع</span>
          <span className="value neg">{usd(m.max_dd)}</span>
          <span className="sub">رسوم {f(m.fees)}$</span>
        </div>
      </div>

      <div className="card" style={{ padding: "10px 14px", marginBottom: 16, display: "flex",
           gap: 24, flexWrap: "wrap", fontSize: 13 }}>
        <span>قبل الرسوم <b className={cls(m.gross)}>{usd(m.gross)}</b></span>
        <span>الرسوم <b className="neg">−{f(m.fees)}$</b></span>
        <span>متوسّط الرابحة <b className="pos">{usd(m.avg_win)}</b></span>
        <span>متوسّط الخاسرة <b className="neg">{usd(m.avg_loss)}</b></span>
        <span>الأفضل <b className="pos">{usd(m.best)}</b></span>
        <span>الأسوأ <b className="neg">{usd(m.worst)}</b></span>
      </div>

      {data.open?.length > 0 && (
        <div className="card" style={{ marginBottom: 16, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line,#1e2a3a)",
               fontWeight: 600, fontSize: 14 }}>
            <span className="pulse" /> مفتوحة الآن ({data.open.length})
          </div>
          <table className="ltable">
            <thead>
              <tr><th>العملة</th><th>الاتّجاه</th><th>دخول</th><th>السعر الآن</th>
                  <th>الربح</th><th>بالدولار</th><th>رافعة</th><th>فُتحت</th></tr>
            </thead>
            <tbody>
              {data.open.map((t) => (
                <tr key={t.id}>
                  <td className="sym">{t.symbol}</td>
                  <td><span className={"dir " + t.direction.toLowerCase()}>{t.direction}</span></td>
                  <td className="num dim">{t.entry}</td>
                  <td className="num live">{t.live_price ?? "—"}</td>
                  <td className={"num b " + cls(t.live_pnl_pct)}>
                    {t.live_pnl_pct != null ? pct(t.live_pnl_pct) : "—"}
                  </td>
                  <td className={"num " + cls(t.live_pnl_usdt)}>
                    {t.live_pnl_usdt != null ? usd(t.live_pnl_usdt) : "—"}
                  </td>
                  <td className="num dim">{t.leverage}x</td>
                  <td className="num dim">{hm(t.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.days?.length === 0 && (
        <div className="card" style={{ padding: 20, textAlign: "center", opacity: .6 }}>
          لا صفقات منفَّذة في هذه المدّة
        </div>
      )}

      {data.days?.map((d) => {
        const dm = d.metrics;
        const open = !!openDays[d.date];
        return (
          <div className="card" key={d.date} style={{ marginBottom: 10, padding: 0, overflow: "hidden" }}>
            <button
              className="dayhead"
              onClick={() => setOpenDays((s) => ({ ...s, [d.date]: !s[d.date] }))}
            >
              <span className="chev">{open ? <ChevronDown size={16} /> : <ChevronLeft size={16} />}</span>
              <span className="dname">{dayName(d.date)}</span>
              <span className="dcount">{dm.n} صفقة</span>
              <span className="dwin">فوز {f(dm.win_rate, 0)}%</span>
              <span className={"dnet " + cls(dm.net)}>
                {dm.net > 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />} {usd(dm.net)}
              </span>
            </button>

            {open && (
              <table className="ltable">
                <thead>
                  <tr>
                    <th>العملة</th><th>الاتّجاه</th><th>دخول</th><th>خروج</th>
                    <th>المدّة</th><th>%</th><th>رسوم</th><th>الصافي</th><th>السبب</th>
                  </tr>
                </thead>
                <tbody>
                  {d.trades.map((t) => (
                    <tr key={t.id}>
                      <td className="sym">{t.symbol}</td>
                      <td><span className={"dir " + t.direction.toLowerCase()}>{t.direction}</span></td>
                      <td className="num dim">{t.entry}</td>
                      <td className="num dim">{t.exit_price}</td>
                      <td className="num dim">{t.duration_min ? f(t.duration_min, 0) + "د" : "—"}</td>
                      <td className={"num " + cls(t.pnl_pct)}>{pct(t.pnl_pct)}</td>
                      <td className="num dim">{f(t.commission)}$</td>
                      <td className={"num b " + cls(t.net_usdt)}>{usd(t.net_usdt)}</td>
                      <td className="reason">{t.close_reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}

      <style>{`
        .ledger .sub { display:block; font-size:11px; opacity:.55; margin-top:2px; }
        .ledger .pos { color:#22c55e; }
        .ledger .neg { color:#ef4444; }
        .ledger .dayhead {
          width:100%; display:flex; align-items:center; gap:14px;
          padding:12px 14px; background:none; border:0; cursor:pointer;
          color:inherit; font-size:14px; text-align:start;
        }
        .ledger .dayhead:hover { background:rgba(255,255,255,.03); }
        .ledger .chev { opacity:.5; display:flex; }
        .ledger .dname { font-weight:600; min-width:120px; }
        .ledger .dcount, .ledger .dwin { opacity:.6; font-size:12.5px; }
        .ledger .dnet { margin-inline-start:auto; font-weight:700;
                        display:flex; align-items:center; gap:5px; }
        .ledger .ltable { width:100%; border-collapse:collapse; font-size:12.5px; }
        .ledger .ltable th {
          text-align:start; padding:7px 10px; font-weight:500; font-size:11px;
          opacity:.45; border-bottom:1px solid var(--line,#1e2a3a);
          text-transform:uppercase; letter-spacing:.4px;
        }
        .ledger .ltable td { padding:8px 10px; border-bottom:1px solid rgba(255,255,255,.035); }
        .ledger .ltable tr:last-child td { border-bottom:0; }
        .ledger .ltable tbody tr:hover { background:rgba(255,255,255,.025); }
        .ledger .sym { font-weight:600; font-family:ui-monospace,monospace; }
        .ledger .num { font-family:ui-monospace,monospace; text-align:end; }
        .ledger .num.b { font-weight:700; }
        .ledger .dim { opacity:.55; }
        .ledger .reason { font-size:11px; opacity:.5; }
        .ledger .dir {
          font-size:10.5px; font-weight:700; padding:2px 7px; border-radius:4px;
          letter-spacing:.3px;
        }
        .ledger .live { color:#38bdf8; font-weight:600; }
        .ledger .pulse {
          display:inline-block; width:7px; height:7px; border-radius:50%;
          background:#22c55e; margin-inline-end:7px; vertical-align:middle;
          animation:lpulse 1.8s ease-in-out infinite;
        }
        @keyframes lpulse { 0%,100%{opacity:1;transform:scale(1)}
                            50%{opacity:.35;transform:scale(.8)} }
        .ledger .dir.long  { background:rgba(34,197,94,.13); color:#22c55e; }
        .ledger .dir.short { background:rgba(239,68,68,.13); color:#ef4444; }
        @media (max-width:640px){
          .ledger .ltable th:nth-child(3), .ledger .ltable td:nth-child(3),
          .ledger .ltable th:nth-child(4), .ledger .ltable td:nth-child(4),
          .ledger .ltable th:nth-child(9), .ledger .ltable td:nth-child(9) { display:none; }
          .ledger .dcount, .ledger .dwin { display:none; }
        }
      `}</style>
    </div>
  );
}
