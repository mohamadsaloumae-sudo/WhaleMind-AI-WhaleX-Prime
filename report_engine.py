# -*- coding: utf-8 -*-
import asyncio, sqlite3, time, logging
log = logging.getLogger("report_engine")
ML_DB = "/opt/whalex/ml_training.db"
REPORT_INTERVAL = 28800
MARGIN_USD = 100.0

def _fetch_closed(since_ts: int) -> list:
    conn = sqlite3.connect(ML_DB)
    rows = conn.execute(
        "SELECT symbol, direction, grade, tier, pnl_pct, closed_at "
        "FROM training_signals "
        "WHERE pnl_pct IS NOT NULL AND closed_at IS NOT NULL AND closed_at >= ? "
        "AND (result IS NULL OR result NOT LIKE 'shadow%') "
        "ORDER BY closed_at",
        (since_ts,)
    ).fetchall()
    conn.close()
    return rows

def _radar_block(title, rows):
    if not rows:
        return f"<b>{title}</b>\nلا صفقات\n"
    w = [r for r in rows if r[4] > 0]
    l = [r for r in rows if r[4] <= 0]
    def _names(items):
        return "، ".join(f"{r[0]} ({r[4]:+.1f}%)" for r in items) if items else "—"
    out = f"<b>{title}</b> — {len(rows)} صفقة\n"
    out += f"✅ رابحة {len(w)}: {_names(w)}\n"
    out += f"❌ خاسرة {len(l)}: {_names(l)}\n"
    return out

def build_report(hours: int = 8) -> str:
    now = int(time.time())
    since = now - hours * 3600
    rows = _fetch_closed(since)
    if not rows:
        return (
            f"📊 <b>WhaleX Report</b> — آخر {hours}h\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"لا صفقات مغلقة في هذه الفترة.\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    pnls = [r[4] for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total = len(pnls)
    win_rate = len(wins) / total * 100 if total else 0
    best = max(wins) if wins else 0.0
    worst = min(losses) if losses else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    net_usd = sum(MARGIN_USD * (p / 100) for p in pnls)
    win_usd = sum(MARGIN_USD * (p / 100) for p in wins)
    loss_usd = sum(MARGIN_USD * (p / 100) for p in losses)
    ph_short = [r for r in rows if r[3] == "PH" and r[1] == "SHORT"]
    ph_long  = [r for r in rows if r[3] == "PH" and r[1] == "LONG"]
    predator = [r for r in rows if r[3] != "PH"]
    emoji = "🟢" if net_usd > 0 else "🔴"
    return (
        f"📊 <b>WhaleX Report</b> — آخر {hours}h\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"الصفقات: <b>{total}</b> · رابحة <b>{len(wins)}</b> ({win_rate:.0f}%) · خاسرة {len(losses)}\n"
        f"أكبر ربح: +{best:.2f}% · أكبر خسارة: {worst:.2f}%\n"
        f"متوسط الرابحة: +{avg_win:.2f}% · متوسط الخاسرة: {avg_loss:.2f}%\n"
        f"{emoji} <b>الصافي: ${net_usd:+.2f}</b> (أرباح +${win_usd:.2f} / خسائر -${abs(loss_usd):.2f})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔻 {_radar_block('Peak Hunter SHORT', ph_short)}"
        f"─────────────\n"
        f"📈 {_radar_block('Peak Hunter LONG', ph_long)}"
        f"─────────────\n"
        f"🎯 {_radar_block('Predator', predator)}"
        f"━━━━━━━━━━━━━━━━━━"
    )

REPORT_HOURS_UTC = {4, 12, 20}

async def report_loop(notify_fn=None):
    import time as _t
    log.info("📊 Report Engine بدأ — تقارير 08:00/16:00/00:00 (توقيت الإمارات)")
    last_sent_hour = -1
    while True:
        try:
            utc_hour = _t.gmtime().tm_hour
            utc_min = _t.gmtime().tm_min
            if utc_hour in REPORT_HOURS_UTC and utc_hour != last_sent_hour and utc_min < 5:
                uae_hour = (utc_hour + 4) % 24
                report = build_report(hours=8)
                report = report.replace("WhaleX Report", f"WhaleX Report — {uae_hour:02d}:00 🇦🇪")
                log.info("📊 إرسال التقرير الدوري (UAE %02d:00)", uae_hour)
                if notify_fn:
                    await notify_fn("system", report, event_type="report", to_channel=True)
                last_sent_hour = utc_hour
        except Exception as e:
            log.error("report_loop error: %s", e)
        await asyncio.sleep(60)
