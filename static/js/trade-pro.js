/**
 * trade-pro.js — WhaleX Prime v2
 * ══════════════════════════════════════
 * صفحة التداول الاحترافية + نظام الطبقات.
 * مع Manual + Auto Trading + Notifications.
 * ══════════════════════════════════════
 */

const TRADEPRO = {

  _sym:       'BTCUSDT',
  _side:      'buy',
  _orderType: 'limit',
  _leverage:  10,
  _margin:    'cross',
  _mode:      'manual',  // manual | auto
  _obInterval: null,
  _priceInterval: null,
  _activePos: null,
  _allSymbols: [],
  _notifications: [],  // قائمة التنبيهات
  _autoActive: false,

  // ── الدخول للصفحة ────────────────────
  onEnter() {
    this._sym = STATE.tradeSymbol || 'BTCUSDT';
    document.getElementById('tp-sym').textContent = this._sym;
    this._startStreams();
    this._loadPositions();
    this._updateBellBadge();

    // الاستماع للتنبيهات من مدير الصفقات
    BUS.on('ws:alert', (msg) => this._addNotification(msg));
  },

  onLeave() {
    this._stopStreams();
  },

  // ── البيانات الحية ───────────────────
  _startStreams() {
    this._fetchPrice();
    this._fetchOrderBook();
    this._priceInterval = setInterval(() => this._fetchPrice(), 2000);
    this._obInterval    = setInterval(() => this._fetchOrderBook(), 3000);
  },

  _stopStreams() {
    if(this._priceInterval) clearInterval(this._priceInterval);
    if(this._obInterval) clearInterval(this._obInterval);
  },

  async _fetchPrice() {
    try {
      const r = await fetch(`https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=${this._sym}`);
      const d = await r.json();
      const px = parseFloat(d.lastPrice);
      const ch = parseFloat(d.priceChangePercent);
      const up = ch >= 0;

      const pEl = document.getElementById('tp-price');
      const cEl = document.getElementById('tp-change');
      const curEl = document.getElementById('tp-ob-current');

      if(pEl) {
        pEl.textContent = this._fmtPrice(px);
        pEl.className = 'tp-price ' + (up ? 'up' : 'dn');
      }
      if(cEl) {
        cEl.textContent = (up ? '+' : '') + ch.toFixed(2) + '%';
        cEl.className = 'tp-change ' + (up ? 'up' : 'dn');
      }
      if(curEl) {
        curEl.textContent = this._fmtPrice(px);
        curEl.className = 'tp-ob-current ' + (up ? 'up' : 'dn');
      }

      const pInp = document.getElementById('tp-price-inp');
      if(pInp && !pInp.value) pInp.value = px.toFixed(this._decimals(px));
    } catch(e) {}
  },

  async _fetchOrderBook() {
    try {
      const r = await fetch(`https://fapi.binance.com/fapi/v1/depth?symbol=${this._sym}&limit=10`);
      const d = await r.json();
      const bids = d.bids.slice(0, 5);
      const asks = d.asks.slice(0, 5).reverse();

      const maxQty = Math.max(
        ...bids.map(b => parseFloat(b[1])),
        ...asks.map(a => parseFloat(a[1]))
      );

      const renderRow = (row) => {
        const px = parseFloat(row[0]);
        const qty = parseFloat(row[1]);
        const pct = (qty / maxQty * 100).toFixed(1);
        return `<div class="tp-ob-row" onclick="TRADEPRO.setPrice(${px})">
          <div class="tp-ob-bg" style="width:${pct}%"></div>
          <span class="tp-ob-px">${this._fmtPrice(px)}</span>
          <span class="tp-ob-qty">${this._fmtQty(qty)}</span>
        </div>`;
      };

      const sellsEl = document.getElementById('tp-ob-sells');
      const buysEl  = document.getElementById('tp-ob-buys');
      if(sellsEl) sellsEl.innerHTML = asks.map(renderRow).join('');
      if(buysEl) buysEl.innerHTML = bids.map(renderRow).join('');

      const totalBids = bids.reduce((s, b) => s + parseFloat(b[1]), 0);
      const totalAsks = asks.reduce((s, a) => s + parseFloat(a[1]), 0);
      const total = totalBids + totalAsks;
      if(total > 0) {
        const buyPct  = (totalBids / total * 100);
        const sellPct = 100 - buyPct;
        document.getElementById('tp-buy-pct').textContent = buyPct.toFixed(1) + '%';
        document.getElementById('tp-sell-pct').textContent = sellPct.toFixed(1) + '%';
        document.getElementById('tp-bar-buy').style.width = buyPct + '%';
        document.getElementById('tp-bar-sell').style.width = sellPct + '%';
      }
    } catch(e) {}
  },

  setPrice(px) {
    const inp = document.getElementById('tp-price-inp');
    if(inp) inp.value = px.toFixed(this._decimals(px));
  },

  // ── Mode Switch (Manual / Auto) ──────
  setMode(mode, el) {
    this._mode = mode;
    document.querySelectorAll('.tp-mode-tab').forEach(t => t.classList.remove('on'));
    el.classList.add('on');
    document.getElementById('tp-manual-mode').style.display = mode === 'manual' ? 'flex' : 'none';
    document.getElementById('tp-auto-mode').style.display   = mode === 'auto' ? 'block' : 'none';
  },

  // ── الطبقات (Layers) ─────────────────
  openLayer(name) {
    const layer = document.getElementById('layer-' + name);
    if(!layer) return;
    layer.classList.add('on');
    if(name === 'sym')         this._loadSymbols();
    if(name === 'signals')     this._loadSignalsLayer();
    if(name === 'positions')   this._loadPositionsLayer();
    if(name === 'chart')       this._loadChart();
    if(name === 'notifications') this._loadNotificationsLayer();
  },

  closeLayer(name) {
    document.getElementById('layer-' + name)?.classList.remove('on');
  },

  // ── اختيار العملة ─────────────────────
  async _loadSymbols() {
    const list = document.getElementById('sym-list');
    if(!list) return;
    list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text3)">جاري التحميل...</div>';

    try {
      const r = await fetch('https://fapi.binance.com/fapi/v1/ticker/24hr');
      const data = await r.json();
      // جلب كل العملات المتاحة على Binance Futures (USDT pairs)
      const top = data
        .filter(x => x.symbol.endsWith('USDT') && parseFloat(x.quoteVolume) > 0)
        .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume));

      this._allSymbols = top;
      this._renderSymbols(top);
    } catch(e) {
      list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--red)">فشل التحميل</div>';
    }
  },

  _renderSymbols(symbols) {
    const list = document.getElementById('sym-list');
    if(!list) return;
    list.innerHTML = symbols.map(s => {
      const up = parseFloat(s.priceChangePercent) >= 0;
      return `<div class="tp-sym-row" onclick="TRADEPRO.selectSymbol('${s.symbol}')">
        <div class="tp-sym-info">
          <div class="tp-sym-name-row">${s.symbol}</div>
          <div class="tp-sym-vol">Vol: $${this._fmtCompact(parseFloat(s.quoteVolume))}</div>
        </div>
        <div style="text-align:left;flex-shrink:0">
          <div class="tp-sym-price">${this._fmtPrice(parseFloat(s.lastPrice))}</div>
          <div class="tp-sym-chg ${up ? 'up' : 'dn'}">${up?'+':''}${parseFloat(s.priceChangePercent).toFixed(2)}%</div>
        </div>
      </div>`;
    }).join('');
  },

  filterSymbols(q) {
    if(!this._allSymbols) return;
    const filtered = this._allSymbols.filter(s =>
      s.symbol.toLowerCase().includes(q.toLowerCase())
    );
    this._renderSymbols(filtered);
  },

  selectSymbol(sym) {
    this._sym = sym;
    STATE.save('tradeSymbol', sym);
    document.getElementById('tp-sym').textContent = sym;
    document.getElementById('tp-price-inp').value = '';
    this.closeLayer('sym');
    this._fetchPrice();
    this._fetchOrderBook();
  },

  // ── اتجاه الصفقة ─────────────────────
  setSide(side, el) {
    this._side = side;
    document.querySelectorAll('.tp-side-tab').forEach(t => t.classList.remove('on'));
    el.classList.add('on');
    const btn = document.getElementById('tp-submit');
    btn.textContent = side === 'buy' ? 'صفقة شراء / Long' : 'صفقة بيع / Short';
    btn.className = 'tp-submit ' + side;
  },

  // ── نوع الأمر ────────────────────────
  setOrderType(type) {
    this._orderType = type;
    const labels = {
      limit:  'طلب حدي',
      market: 'طلب سوقي',
      stop:   'إيقاف الخسارة',
    };
    document.getElementById('tp-order-type-lbl').textContent = labels[type];
    document.querySelectorAll('[id^="ot-"]').forEach(e => e.textContent = '');
    const chk = document.getElementById('ot-' + type);
    if(chk) chk.textContent = '✓';
    this.closeLayer('ordertype');
  },

  // ── الرافعة ──────────────────────────
  setLev(v) {
    this._leverage = parseInt(v);
    const _t = document.getElementById('tp-leverage'); if(_t) _t.textContent = v + 'x';
    const _lc = document.getElementById('lev-current'); if(_lc) _lc.textContent = v + 'x';
    const _ls = document.getElementById('lev-slider'); if(_ls) _ls.value = v;
    const _sl = document.getElementById('set-leverage'); if(_sl) _sl.value = v;
    const _slv = document.getElementById('set-lev-val'); if(_slv) _slv.textContent = v + 'x';
  },

  setMargin(m, el) {
    this._margin = m;
    document.querySelectorAll('.tp-set-tab').forEach(t => t.classList.remove('on'));
    el.classList.add('on');
  },

  saveSettings() {
    UI.toast('✓ تم حفظ الإعدادات');
    this.closeLayer('settings');
  },

  // ── الإدخالات ────────────────────────
  adjustPrice(dir) {
    const inp = document.getElementById('tp-price-inp');
    const v = parseFloat(inp.value) || 0;
    const step = v > 1000 ? 1 : v > 10 ? 0.1 : 0.001;
    inp.value = Math.max(0, v + (dir * step)).toFixed(this._decimals(v));
  },

  adjustAmount(dir) {
    const inp = document.getElementById('tp-amount-inp');
    const v = parseFloat(inp.value) || 0;
    inp.value = Math.max(0, v + (dir * 10)).toFixed(2);
    this.calcTotal();
  },

  onSlider(el) {
    const pct = el.value / 100;
    const available = 1000;
    const usdt = available * pct;
    document.getElementById('tp-amount-inp').value = usdt.toFixed(2);
    this.calcTotal();
  },

  setBBO() {
    const cur = document.getElementById('tp-ob-current').textContent;
    document.getElementById('tp-price-inp').value = cur;
  },

  calcTotal() {
    const amt = parseFloat(document.getElementById('tp-amount-inp').value) || 0;
    const cost = amt / this._leverage;
    document.getElementById('tp-cost').textContent = cost.toFixed(2) + ' USDT';
  },

  toggleTPSL(chk) {},

  // ── تنفيذ الصفقة اليدوية ─────────────
  async execute() {
    const price = parseFloat(document.getElementById('tp-price-inp').value);
    const amt   = parseFloat(document.getElementById('tp-amount-inp').value);

    if(!price || !amt) { UI.toast('أدخل السعر والمبلغ'); return; }

    UI.toast('جاري التنفيذ...');
    const dir = this._side === 'buy' ? 'LONG' : 'SHORT';

    const d = await API.executeTrade({
      symbol:       this._sym,
      direction:    dir,
      amount:       amt,
      leverage:     this._leverage,
      price:        price,
      order_type:   this._orderType,
      margin_type:  this._margin,
      account_type: STATE.mode,
    });

    if(d?.status === 'executed' || d?.status === 'pending') {
      UI.toast(`✓ ${dir} ${this._sym} @ ${price}`);
      this._showStopBar(this._sym, dir);
      this._loadPositions();
    } else {
      UI.toast('فشل التنفيذ — حاول مرة أخرى');
    }
  },

  // ── Auto Trading ─────────────────────
  async toggleAuto() {
    if(this._autoActive) {
      // إيقاف
      if(!confirm('إيقاف Auto Trading؟ ستبقى الصفقات المفتوحة تحت إدارة مدير الصفقات.')) return;
      this._autoActive = false;
      this._updateAutoUI();
      UI.toast('⏹ Auto Trading أُوقف');
      BUS.emit('trade:auto:stop', null);
    } else {
      // تفعيل
      if(!STATE.isPro) {
        UI.toast('⚠️ يتطلب اشتراك PRO');
        return;
      }
      const amt = parseFloat(document.getElementById('auto-amount').value) || 0;
      if(amt < 50) { UI.toast('الحد الأدنى $50'); return; }

      this._autoActive = true;
      this._updateAutoUI();
      UI.toast('🤖 Auto Trading مفعّل');
      BUS.emit('trade:auto:start', {
        amount: amt,
        risk: document.getElementById('auto-risk').value,
      });
    }
  },

  _updateAutoUI() {
    const dot = document.getElementById('auto-status-dot');
    const txt = document.getElementById('auto-status-txt');
    const btn = document.getElementById('auto-toggle-btn');
    if(this._autoActive) {
      dot.classList.add('active');
      txt.textContent = 'نشط — يستقبل الإشارات';
      btn.textContent = '⏹ إيقاف Auto Trading';
      btn.className = 'tp-submit sell';
    } else {
      dot.classList.remove('active');
      txt.textContent = 'متوقف';
      btn.textContent = '🤖 تشغيل Auto Trading';
      btn.className = 'tp-submit buy';
    }
  },

  // ── الصفقات المفتوحة ─────────────────
  async _loadPositions() {
    const d = await API.getTradeStats();
    const count = d?.open_positions || 0;
    const badge = document.getElementById('tp-pos-count');
    if(badge) {
      if(count > 0) { badge.style.display = 'flex'; badge.textContent = count; }
      else badge.style.display = 'none';
    }
  },

  async _loadPositionsLayer() {
    const list = document.getElementById('tp-positions-list');
    if(!list) return;
    list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text3)">جاري التحميل...</div>';
    const positions = [];
    if(positions.length === 0) {
      list.innerHTML = `<div class="empty"><div class="empty-ico">📭</div><div class="empty-t">لا توجد صفقات مفتوحة</div></div>`;
      return;
    }
  },

  _showStopBar(sym, dir) {
    const bar = document.getElementById('tp-stop-bar');
    bar.style.display = 'flex';
    document.getElementById('tp-stop-title').textContent = `${sym} ${dir}`;
    document.getElementById('tp-stop-sub').textContent = `رافعة ${this._leverage}x`;
    this._activePos = { sym, dir };
  },

  async stopActive() {
    if(!this._activePos) return;
    if(!confirm(`إغلاق صفقة ${this._activePos.sym}؟`)) return;
    const d = await API.forceStop(this._activePos.sym);
    UI.toast(d?.status === 'force_closed' ? '✓ تم الإغلاق' : 'فشل الإغلاق');
    document.getElementById('tp-stop-bar').style.display = 'none';
    this._activePos = null;
  },

  // ── الإشارات — مع TP1 + TP2 + TP3 ─────
  async _loadSignalsLayer() {
    const list = document.getElementById('tp-signals-list');
    if(!list) return;
    list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text3)">جاري التحميل...</div>';

    const d = await API.getFuturesSignals();
    const signals = d?.signals || [];

    if(signals.length === 0) {
      list.innerHTML = `<div class="empty"><div class="empty-ico">📡</div><div class="empty-t">لا توجد إشارات الآن</div></div>`;
      return;
    }

    list.innerHTML = signals.slice(0, 15).map(s => {
      const isL = s.direction === 'LONG';
      // التاريخ بـ UTC+4 (الإمارات)
      // التوقيت — تحويل لـ UTC+4 (الإمارات)
      let dt;
      if(typeof s.created_at === 'number') {
        dt = new Date(s.created_at * (s.created_at < 1e12 ? 1000 : 1));
      } else {
        const str = String(s.created_at);
        dt = new Date(str.includes('Z') || str.includes('+') ? str : str + 'Z');
      }
      const dxb = new Date(dt.getTime() + 4*3600000);
      const pad = n => String(n).padStart(2,'0');
      const tm = `${dxb.getUTCFullYear()}-${pad(dxb.getUTCMonth()+1)}-${pad(dxb.getUTCDate())} ${pad(dxb.getUTCHours())}:${pad(dxb.getUTCMinutes())}`;

      return `<div class="tp-signal-row" onclick='TRADEPRO.applySignal(${JSON.stringify({sym:s.symbol,dir:s.direction,entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,tp3:s.tp3,lev:s.leverage||10,grade:s.grade,conf:s.confidence}).replace(/'/g,"&apos;")})'>
        <div class="tp-signal-hd">
          <span style="font-size:14px;font-weight:800">${s.symbol}</span>
          <span class="pill ${isL?'pill-g':'pill-r'}">${s.direction}</span>
          <span class="grd ${UI.gradeClass(s.grade)}">${s.grade}</span>
          <span class="tp-signal-time">${tm} +4</span>
          <span class="tp-signal-conf">${s.confidence||0}%</span>
        </div>
        <div class="tp-signal-lvls">
          <div class="tp-signal-lv en"><div class="tp-signal-lv-l">دخول</div><div class="tp-signal-lv-v">${UI.fmtPrice(s.entry)}</div></div>
          <div class="tp-signal-lv sl"><div class="tp-signal-lv-l">SL</div><div class="tp-signal-lv-v">${UI.fmtPrice(s.sl)}</div></div>
          <div class="tp-signal-lv t1"><div class="tp-signal-lv-l">TP1</div><div class="tp-signal-lv-v">${UI.fmtPrice(s.tp1)}</div></div>
          <div class="tp-signal-lv t2"><div class="tp-signal-lv-l">TP2</div><div class="tp-signal-lv-v">${UI.fmtPrice(s.tp2)}</div></div>
          <div class="tp-signal-lv t3"><div class="tp-signal-lv-l">TP3</div><div class="tp-signal-lv-v">${UI.fmtPrice(s.tp3)}</div></div>
        </div>
      </div>`;
    }).join('');
  },

  applySignal(data) {
    if(typeof data === 'string') {
      try { data = JSON.parse(data.replace(/&apos;/g,"'")); } catch { return; }
    }
    this.selectSymbol(data.sym);
    setTimeout(() => {
      this._side = data.dir === 'LONG' ? 'buy' : 'sell';
      document.querySelectorAll('.tp-side-tab').forEach(t => t.classList.remove('on'));
      document.querySelector(`.tp-side-tab.${this._side}`)?.classList.add('on');
      this.setSide(this._side, document.querySelector(`.tp-side-tab.${this._side}`));
      document.getElementById('tp-price-inp').value = data.entry;
      this.setLev(data.lev);
      this.closeLayer('signals');
      UI.toast(`✓ تم تطبيق إشارة ${data.sym} ${data.dir} ${data.grade}`);
    }, 150);
  },

  // ── الرسم البياني ────────────────────
  _loadChart() {
    const frame = document.getElementById('tp-chart-frame');
    if(!frame) return;
    document.getElementById('chart-title').textContent = this._sym + ' — الرسم';
    frame.src = `https://s.tradingview.com/widgetembed/?symbol=BINANCE%3A${this._sym}.P&interval=15&theme=dark&style=1&locale=ar&toolbar_bg=%23020408&hide_side_toolbar=0&allow_symbol_change=0`;
  },

  // ── التنبيهات / Notifications ─────────
  _addNotification(msg) {
    const cleanMsg = (msg.message || '').replace(/<[^>]*>/g, '');
    this._notifications.unshift({
      msg:  cleanMsg,
      icon: this._getNotifIcon(cleanMsg),
      time: Date.now(),
      read: false,
    });
    if(this._notifications.length > 30) this._notifications.pop();
    this._updateBellBadge();
  },

  _getNotifIcon(msg) {
    if(msg.includes('TP3')) return '🏆';
    if(msg.includes('TP2')) return '🚀';
    if(msg.includes('TP1')) return '🎯';
    if(msg.includes('SL')) return '🔴';
    if(msg.includes('هروب')) return '🏃';
    if(msg.includes('Pyramid')) return '📈';
    if(msg.includes('Claude') || msg.includes('AI')) return '🤖';
    if(msg.includes('انفجار') || msg.includes('Explosion')) return '💥';
    return '📡';
  },

  _updateBellBadge() {
    const badge = document.getElementById('tp-bell-badge');
    if(!badge) return;
    const unread = this._notifications.filter(n => !n.read).length;
    if(unread > 0) {
      badge.style.display = 'flex';
      badge.textContent = unread > 99 ? '99+' : unread;
    } else {
      badge.style.display = 'none';
    }
  },

  _loadNotificationsLayer() {
    const list = document.getElementById('tp-notif-list');
    if(!list) return;

    // علّم كل التنبيهات كمقروءة
    this._notifications.forEach(n => n.read = true);
    this._updateBellBadge();

    if(this._notifications.length === 0) {
      list.innerHTML = `<div class="empty"><div class="empty-ico">🔕</div><div class="empty-t">لا توجد تنبيهات</div></div>`;
      return;
    }

    list.innerHTML = this._notifications.map(n => {
      const dt = new Date(n.time);
      const utcMs = dt.getTime() + dt.getTimezoneOffset()*60000;
      const dxb = new Date(utcMs + 4*3600000);
      const tm = dxb.toISOString().replace('T',' ').slice(0,16);
      return `<div class="tp-notif-row">
        <div class="tp-notif-icon">${n.icon}</div>
        <div class="tp-notif-content">
          <div class="tp-notif-msg">${n.msg}</div>
          <div class="tp-notif-time">${tm} +4</div>
        </div>
      </div>`;
    }).join('');
  },

  clearNotifications() {
    this._notifications = [];
    this._updateBellBadge();
    this._loadNotificationsLayer();
  },

  // ── Utils ────────────────────────────
  _fmtPrice(v) {
    if(v >= 1000) return v.toFixed(2);
    if(v >= 1) return v.toFixed(3);
    return v.toFixed(6);
  },

  _fmtQty(v) {
    if(v >= 1000) return (v/1000).toFixed(2) + 'K';
    return v.toFixed(2);
  },

  _fmtCompact(n) {
    if(n >= 1e9) return (n/1e9).toFixed(1) + 'B';
    if(n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if(n >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toFixed(0);
  },

  _decimals(v) {
    if(v >= 1000) return 2;
    if(v >= 1) return 3;
    return 6;
  },
};
