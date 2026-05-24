/**
 * trade-pro.js — WhaleX Prime
 * ══════════════════════════════════════
 * صفحة التداول الاحترافية + نظام الطبقات.
 * مستقل تماماً — يستخدم BUS للتواصل.
 * ══════════════════════════════════════
 */

const TRADEPRO = {

  _sym:       'BTCUSDT',
  _side:      'buy',
  _orderType: 'limit',
  _leverage:  10,
  _margin:    'cross',
  _obInterval: null,
  _priceInterval: null,
  _activePos: null,

  // ── الدخول للصفحة ────────────────────
  onEnter() {
    this._sym = STATE.tradeSymbol || 'BTCUSDT';
    document.getElementById('tp-sym').textContent = this._sym;
    this._startStreams();
    this._loadPositions();
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

      // تعبئة السعر الافتراضي في حقل الأمر
      const pInp = document.getElementById('tp-price-inp');
      if(pInp && !pInp.value) pInp.value = px.toFixed(this._decimals(px));
    } catch(e) {}
  },

  async _fetchOrderBook() {
    try {
      const r = await fetch(`https://fapi.binance.com/fapi/v1/depth?symbol=${this._sym}&limit=10`);
      const d = await r.json();
      const bids = d.bids.slice(0, 5); // 5 أوامر شراء
      const asks = d.asks.slice(0, 5).reverse(); // 5 أوامر بيع (مرتبة من الأعلى)

      // أكبر كمية لحساب نسبة الـ background
      const maxQty = Math.max(
        ...bids.map(b => parseFloat(b[1])),
        ...asks.map(a => parseFloat(a[1]))
      );

      const renderRow = (row) => {
        const px = parseFloat(row[0]);
        const qty = parseFloat(row[1]);
        const pct = (qty / maxQty * 100).toFixed(1);
        return `<div class="tp-ob-row">
          <div class="tp-ob-bg" style="width:${pct}%"></div>
          <span class="tp-ob-px">${this._fmtPrice(px)}</span>
          <span class="tp-ob-qty">${this._fmtQty(qty)}</span>
        </div>`;
      };

      const sellsEl = document.getElementById('tp-ob-sells');
      const buysEl  = document.getElementById('tp-ob-buys');
      if(sellsEl) sellsEl.innerHTML = asks.map(renderRow).join('');
      if(buysEl) buysEl.innerHTML = bids.map(renderRow).join('');

      // نسبة الشراء/البيع
      const totalBids = bids.reduce((s, b) => s + parseFloat(b[1]), 0);
      const totalAsks = asks.reduce((s, a) => s + parseFloat(a[1]), 0);
      const total = totalBids + totalAsks;
      if(total > 0) {
        const buyPct  = (totalBids / total * 100);
        const sellPct = 100 - buyPct;
        document.getElementById('tp-buy-pct').textContent = buyPct.toFixed(2) + '%';
        document.getElementById('tp-sell-pct').textContent = sellPct.toFixed(2) + '%';
        document.getElementById('tp-bar-buy').style.width = buyPct + '%';
        document.getElementById('tp-bar-sell').style.width = sellPct + '%';
      }
    } catch(e) {}
  },

  // ── الطبقات (Layers) ─────────────────
  openLayer(name) {
    const layer = document.getElementById('layer-' + name);
    if(!layer) return;
    layer.classList.add('on');
    // تحميل المحتوى عند الفتح
    if(name === 'sym')      this._loadSymbols();
    if(name === 'signals')  this._loadSignalsLayer();
    if(name === 'positions') this._loadPositionsLayer();
    if(name === 'chart')    this._loadChart();
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
      // العملات الأكثر تداولاً (USDT)
      const top = data
        .filter(x => x.symbol.endsWith('USDT'))
        .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume))
        .slice(0, 50);

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
        <div style="text-align:left">
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
    btn.textContent = side === 'buy' ? 'صفقة شراء' : 'صفقة بيع';
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
    document.getElementById('ot-' + type).textContent = '✓';
    this.closeLayer('ordertype');
  },

  // ── الرافعة ──────────────────────────
  setLev(v) {
    this._leverage = parseInt(v);
    document.getElementById('tp-leverage').textContent = v + 'x';
    document.getElementById('lev-current')?.textContent = v + 'x';
    document.getElementById('lev-slider')?.value = v;
    document.getElementById('set-leverage')?.value = v;
    document.getElementById('set-lev-val')?.textContent = v + 'x';
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
    const available = 1000; // TODO: من المحفظة الحقيقية
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

  toggleTPSL(chk) {
    // TODO: عرض حقول TP/SL إضافية
  },

  // ── تنفيذ الصفقة ─────────────────────
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

  // ── الصفقات المفتوحة ─────────────────
  async _loadPositions() {
    const d = await API.getTradeStats();
    const count = d?.open_positions || 0;
    const badge = document.getElementById('tp-pos-count');
    if(count > 0) {
      badge.style.display = 'flex';
      badge.textContent = count;
    } else {
      badge.style.display = 'none';
    }
  },

  async _loadPositionsLayer() {
    const list = document.getElementById('tp-positions-list');
    if(!list) return;
    list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text3)">جاري التحميل...</div>';

    // TODO: API call لجلب الصفقات الحقيقية
    const positions = []; // مؤقت

    if(positions.length === 0) {
      list.innerHTML = `<div class="empty">
        <div class="empty-ico">📭</div>
        <div class="empty-t">لا توجد صفقات مفتوحة</div>
      </div>`;
      return;
    }

    list.innerHTML = positions.map(p => `
      <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px">
          <div>
            <div style="font-weight:800">${p.symbol}</div>
            <div style="font-size:11px;color:${p.direction==='LONG'?'var(--green)':'var(--red)'};font-weight:700">${p.direction} ${p.leverage}x</div>
          </div>
          <div style="text-align:left">
            <div style="font-family:var(--mono);font-weight:700;color:${p.pnl>0?'var(--green)':'var(--red)'}">${p.pnl>0?'+':''}${p.pnl.toFixed(2)}%</div>
            <div style="font-size:11px;color:var(--text3)">${p.entry}</div>
          </div>
        </div>
        <button class="tp-stop-btn" style="width:100%" onclick="TRADEPRO.closePosition('${p.id}')">⏹ إغلاق الصفقة</button>
      </div>
    `).join('');
  },

  _showStopBar(sym, dir) {
    const bar = document.getElementById('tp-stop-bar');
    bar.style.display = 'flex';
    document.getElementById('tp-stop-title').textContent = `${sym} ${dir}`;
    document.getElementById('tp-stop-sub').textContent = `رافعة ${this._leverage}x — ${this._orderType}`;
    this._activePos = { sym, dir };
  },

  async stopActive() {
    if(!this._activePos) return;
    if(!confirm(`إغلاق صفقة ${this._activePos.sym}؟`)) return;
    const d = await API.forceStop(this._activePos.sym);
    UI.toast(d?.status === 'force_closed' ? '✓ تم الإغلاق' : 'فشل الإغلاق');
    document.getElementById('tp-stop-bar').style.display = 'none';
    this._activePos = null;
    this._loadPositions();
  },

  async closePosition(id) {
    if(!confirm('إغلاق الصفقة؟')) return;
    UI.toast('جاري الإغلاق...');
    // TODO: API call
    this._loadPositionsLayer();
  },

  // ── الإشارات ─────────────────────────
  async _loadSignalsLayer() {
    const list = document.getElementById('tp-signals-list');
    if(!list) return;
    list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text3)">جاري التحميل...</div>';

    const d = await API.getFuturesSignals();
    const signals = d?.signals || [];

    if(signals.length === 0) {
      list.innerHTML = `<div class="empty">
        <div class="empty-ico">📡</div>
        <div class="empty-t">لا توجد إشارات الآن</div>
      </div>`;
      return;
    }

    list.innerHTML = signals.slice(0, 10).map(s => {
      const isL = s.direction === 'LONG';
      return `<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px;cursor:pointer"
        onclick="TRADEPRO.applySignal('${s.symbol}','${s.direction}',${s.entry},${s.sl},${s.tp1},${s.leverage||10})">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-weight:800">${s.symbol}</span>
          <span class="pill ${isL?'pill-g':'pill-r'}">${s.direction}</span>
          <span class="grd ${UI.gradeClass(s.grade)}">${s.grade}</span>
          <span style="margin-right:auto;font-size:11px;color:var(--neon);font-weight:700">${s.confidence||0}%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;font-size:11px">
          <div><span style="color:var(--text3)">دخول:</span> <b>${UI.fmtPrice(s.entry)}</b></div>
          <div><span style="color:var(--text3)">SL:</span> <b style="color:var(--red)">${UI.fmtPrice(s.sl)}</b></div>
          <div><span style="color:var(--text3)">TP1:</span> <b style="color:var(--green)">${UI.fmtPrice(s.tp1)}</b></div>
        </div>
      </div>`;
    }).join('');
  },

  applySignal(sym, dir, entry, sl, tp1, lev) {
    this.selectSymbol(sym);
    setTimeout(() => {
      this._side = dir === 'LONG' ? 'buy' : 'sell';
      document.querySelectorAll('.tp-side-tab').forEach(t => t.classList.remove('on'));
      document.querySelector(`.tp-side-tab.${this._side}`)?.classList.add('on');
      document.getElementById('tp-price-inp').value = entry;
      this.setLev(lev);
      this.closeLayer('signals');
      UI.toast(`✓ تم تطبيق إشارة ${sym}`);
    }, 100);
  },

  // ── الرسم البياني ────────────────────
  _loadChart() {
    const frame = document.getElementById('tp-chart-frame');
    if(!frame) return;
    document.getElementById('chart-title').textContent = this._sym + ' — الرسم';
    frame.src = `https://s.tradingview.com/widgetembed/?symbol=BINANCE%3A${this._sym}.P&interval=15&theme=dark&style=1&locale=ar&toolbar_bg=%23020408&hide_side_toolbar=0&allow_symbol_change=0`;
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
