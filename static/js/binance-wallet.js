/**
 * binance-wallet.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة ربط Binance + الرصيد + Auto-Trade
 * ══════════════════════════════════════
 */

const BINANCE_WALLET = {
  _status: null,
  _balance: null,
  _positions: [],
  _settings: null,
  _refreshTimer: null,

  // ═══════════════════════════════════════════
  // ─── API LAYER ─────────────────────────────
  // ═══════════════════════════════════════════
  async _api(path, opts = {}) {
    const token = STATE.load('authToken');
    const url = `${CONFIG.API_BASE}${path}`;
    const res = await fetch(url, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...opts.headers,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'خطأ' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async fetchStatus() {
    try {
      this._status = await this._api('/api/binance/status');
      return this._status;
    } catch (e) {
      console.error('fetchStatus error:', e);
      this._status = { connected: false };
      return this._status;
    }
  },

  async fetchBalance() {
    if (!this._status?.connected) return null;
    try {
      this._balance = await this._api('/api/binance/balance');
      return this._balance;
    } catch (e) {
      console.error('fetchBalance error:', e);
      return null;
    }
  },

  async fetchPositions() {
    if (!this._status?.connected) return [];
    try {
      const r = await this._api('/api/binance/positions');
      this._positions = r.positions || [];
      return this._positions;
    } catch (e) {
      console.error('fetchPositions error:', e);
      return [];
    }
  },

  async testKeys(apiKey, apiSecret, isTestnet = true) {
    return this._api('/api/binance/test', {
      method: 'POST',
      body: JSON.stringify({
        api_key: apiKey,
        api_secret: apiSecret,
        is_testnet: isTestnet,
      }),
    });
  },

  async connect(apiKey, apiSecret, isTestnet = true) {
    return this._api('/api/binance/connect', {
      method: 'POST',
      body: JSON.stringify({
        api_key: apiKey,
        api_secret: apiSecret,
        is_testnet: isTestnet,
        account_type: 'futures',
      }),
    });
  },

  async disconnect() {
    return this._api('/api/binance/disconnect', { method: 'DELETE' });
  },

  async updateAutoTrade(settings) {
    return this._api('/api/binance/auto-trade', {
      method: 'POST',
      body: JSON.stringify(settings),
    });
  },

  // ═══════════════════════════════════════════
  // ─── MAIN ENTRY ────────────────────────────
  // ═══════════════════════════════════════════
  async load() {
    const container = document.getElementById('bn-container');
    if (!container) return;

    container.innerHTML = `<div class="bn-loading">⏳ جاري التحميل...</div>`;
    await this.fetchStatus();

    if (this._status?.connected) {
      await this.fetchBalance();
      await this.fetchPositions();
      this.renderConnected();
      this._startRefresh();
    } else {
      this.renderDisconnected();
      this._stopRefresh();
    }
  },

  unload() {
    this._stopRefresh();
  },

  _startRefresh() {
    this._stopRefresh();
    this._refreshTimer = setInterval(async () => {
      await this.fetchBalance();
      await this.fetchPositions();
      this._updateLiveData();
    }, 15000); // كل 15 ثانية
  },

  _stopRefresh() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  },

  // ═══════════════════════════════════════════
  // ─── CONNECT PAGE (غير مربوط) ──────────────
  // ═══════════════════════════════════════════
  renderDisconnected() {
    const container = document.getElementById('bn-container');
    container.innerHTML = `
      <div class="bn-connect">
        <div class="bn-hero">
          <div class="bn-logo">🟡</div>
          <h2>ربط Binance</h2>
          <p>اربط حسابك للتداول التلقائي والمتابعة الحية</p>
        </div>

        <div class="bn-steps">
          <h3>📋 خطوات إنشاء API Key:</h3>
          <ol>
            <li>افتح <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" rel="noopener">Binance API Management</a></li>
            <li>اضغط <b>"Create API"</b> ثم اختر <b>System Generated</b></li>
            <li>أدخل اسم: <b>WhaleMind</b></li>
            <li>⚠️ <b style="color:#ff6b6b">مهم:</b> فعّل فقط:
              <ul>
                <li>✅ Enable Reading</li>
                <li>✅ Enable Futures</li>
                <li>❌ <b>لا تفعّل</b> Enable Withdrawals</li>
              </ul>
            </li>
            <li>انسخ <b>API Key</b> و <b>Secret Key</b></li>
          </ol>
        </div>

        <div class="bn-form">
          <div class="bn-field">
            <label>API Key</label>
            <input type="text" id="bn-api-key" placeholder="أدخل API Key" autocomplete="off">
          </div>
          <div class="bn-field">
            <label>Secret Key</label>
            <input type="password" id="bn-api-secret" placeholder="أدخل Secret Key" autocomplete="off">
          </div>
          <div class="bn-field bn-toggle-row">
            <label class="bn-switch">
              <input type="checkbox" id="bn-testnet" checked>
              <span class="bn-slider"></span>
            </label>
            <span>استخدم Testnet (تجريبي — مُوصى به للبداية)</span>
          </div>

          <button class="btn btn-neon" onclick="BINANCE_WALLET.handleConnect()">
            🔗 ربط الحساب
          </button>
          <div id="bn-connect-status" class="bn-status"></div>
        </div>

        <div class="bn-security">
          <b>🛡️ الأمان:</b><br>
          • مفاتيحك مشفّرة بـ AES-256<br>
          • لا نطلب صلاحية السحب أبداً<br>
          • تستطيع قطع الاتصال في أي لحظة<br>
          • أموالك تبقى على Binance، نحن ننفّذ فقط
        </div>
      </div>
    `;
  },

  async handleConnect() {
    const apiKey = document.getElementById('bn-api-key').value.trim();
    const apiSecret = document.getElementById('bn-api-secret').value.trim();
    const isTestnet = document.getElementById('bn-testnet').checked;
    const statusEl = document.getElementById('bn-connect-status');

    if (!apiKey || !apiSecret) {
      statusEl.innerHTML = `<div class="bn-err">⚠️ أدخل API Key و Secret Key</div>`;
      return;
    }
    if (apiKey.length < 20 || apiSecret.length < 20) {
      statusEl.innerHTML = `<div class="bn-err">⚠️ المفاتيح قصيرة جداً</div>`;
      return;
    }

    statusEl.innerHTML = `<div class="bn-info">⏳ جاري اختبار المفاتيح...</div>`;
    try {
      const result = await this.connect(apiKey, apiSecret, isTestnet);
      if (result.success) {
        statusEl.innerHTML = `<div class="bn-ok">✅ تم الربط بنجاح!</div>`;
        setTimeout(() => this.load(), 1000);
      }
    } catch (e) {
      statusEl.innerHTML = `<div class="bn-err">❌ ${e.message}</div>`;
    }
  },

  // ═══════════════════════════════════════════
  // ─── CONNECTED VIEW (مربوط) ────────────────
  // ═══════════════════════════════════════════
  renderConnected() {
    const container = document.getElementById('bn-container');
    const b = this._balance?.futures || {};
    const totalWallet = (b.total_wallet_balance || 0).toFixed(2);
    const available = (b.available_balance || 0).toFixed(2);
    const pnl = (b.total_unrealized_pnl || 0).toFixed(2);
    const pnlColor = parseFloat(pnl) >= 0 ? '#00ff88' : '#ff4d6d';

    const network = this._status.is_testnet ? '🧪 Testnet' : '🟢 Live';
    const autoState = this._status.auto_trade_enabled ? 'مفعّل' : 'معطّل';
    const autoColor = this._status.auto_trade_enabled ? '#00ff88' : '#999';

    container.innerHTML = `
      <!-- Header -->
      <div class="bn-header">
        <div class="bn-hdr-left">
          <div class="bn-logo-sm">🟡</div>
          <div>
            <div class="bn-hdr-title">Binance</div>
            <div class="bn-hdr-net">${network}</div>
          </div>
        </div>
        <button class="bn-disconnect" onclick="BINANCE_WALLET.handleDisconnect()">قطع الربط</button>
      </div>

      <!-- Balance Card -->
      <div class="bn-balance-card">
        <div class="bn-bal-label">إجمالي الرصيد (Futures)</div>
        <div class="bn-bal-value">$${totalWallet}</div>
        <div class="bn-bal-row">
          <div>
            <span class="bn-bal-sub-label">متاح</span>
            <span class="bn-bal-sub-value">$${available}</span>
          </div>
          <div>
            <span class="bn-bal-sub-label">PnL غير محقق</span>
            <span class="bn-bal-sub-value" style="color:${pnlColor}">${parseFloat(pnl) >= 0 ? '+' : ''}$${pnl}</span>
          </div>
        </div>
      </div>

      <!-- Auto-Trade Settings -->
      <div class="bn-section">
        <div class="bn-section-title">⚡ Auto-Trade</div>
        <div class="bn-auto-card">
          <div class="bn-auto-row">
            <div>
              <div class="bn-auto-state" style="color:${autoColor}">${autoState}</div>
              <div class="bn-auto-desc">ينفّذ إشارات WhaleMind تلقائياً</div>
            </div>
            <label class="bn-switch">
              <input type="checkbox" id="bn-auto-toggle" ${this._status.auto_trade_enabled ? 'checked' : ''}
                onchange="BINANCE_WALLET.toggleAutoTrade(this.checked)">
              <span class="bn-slider"></span>
            </label>
          </div>

          <div class="bn-settings-grid" ${!this._status.auto_trade_enabled ? 'style="opacity:0.5;pointer-events:none"' : ''}>
            <div class="bn-set">
              <label>المبلغ لكل صفقة ($)</label>
              <input type="number" id="bn-trade-amount" value="${this._status.trade_amount_usdt || 100}" min="10" max="10000">
            </div>
            <div class="bn-set">
              <label>أقصى صفقات مفتوحة</label>
              <input type="number" id="bn-max-positions" value="${this._status.max_open_positions || 3}" min="1" max="10">
            </div>
            <div class="bn-set bn-set-full">
              <label>درجات الإشارات المسموحة</label>
              <div class="bn-grades">
                <label class="bn-grade-chk">
                  <input type="checkbox" id="bn-grade-s" ${(this._status.allowed_grades || []).includes('S') ? 'checked' : ''}>
                  <span class="bn-chip s">⭐ S</span>
                </label>
                <label class="bn-grade-chk">
                  <input type="checkbox" id="bn-grade-a" ${(this._status.allowed_grades || []).includes('A') ? 'checked' : ''}>
                  <span class="bn-chip a">A</span>
                </label>
                <label class="bn-grade-chk">
                  <input type="checkbox" id="bn-grade-b" ${(this._status.allowed_grades || []).includes('B') ? 'checked' : ''}>
                  <span class="bn-chip b">B</span>
                </label>
              </div>
            </div>
          </div>

          <button class="btn btn-neon" onclick="BINANCE_WALLET.saveSettings()" style="margin-top:8px"
            ${!this._status.auto_trade_enabled ? 'disabled' : ''}>
            💾 حفظ الإعدادات
          </button>
        </div>
      </div>

      <!-- Open Positions -->
      <div class="bn-section">
        <div class="bn-section-title">📊 الصفقات المفتوحة (${this._positions.length})</div>
        <div id="bn-positions-list">
          ${this._renderPositions()}
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="bn-section">
        <div class="bn-section-title">⚡ إجراءات سريعة</div>
        <div class="bn-actions">
          <button class="btn btn-outline" onclick="ROUTER.go(1)">📈 تداول يدوي</button>
          <button class="btn btn-outline" onclick="BINANCE_WALLET.load()">🔄 تحديث</button>
        </div>
      </div>
    `;
  },

  _renderPositions() {
    if (this._positions.length === 0) {
      return `<div class="bn-empty">لا توجد صفقات مفتوحة</div>`;
    }
    return this._positions.map(p => {
      const pnlColor = p.unrealized_pnl >= 0 ? '#00ff88' : '#ff4d6d';
      const sideIcon = p.direction === 'LONG' ? '🟢' : '🔴';
      const pnlPct = ((p.mark_price - p.entry_price) / p.entry_price * 100 * (p.direction === 'LONG' ? 1 : -1)).toFixed(2);
      return `
        <div class="bn-position">
          <div class="bn-pos-top">
            <div>
              <span class="bn-pos-symbol">${sideIcon} ${p.symbol}</span>
              <span class="bn-pos-side">${p.direction} ${p.leverage}x</span>
            </div>
            <div style="color:${pnlColor};font-weight:800">
              ${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}
              <span style="font-size:11px">(${pnlPct}%)</span>
            </div>
          </div>
          <div class="bn-pos-bot">
            <span>دخول: $${p.entry_price.toFixed(4)}</span>
            <span>الحالي: $${p.mark_price.toFixed(4)}</span>
            <span>الحجم: ${p.size}</span>
          </div>
          <button class="bn-pos-close" onclick="BINANCE_WALLET.closePosition('${p.symbol}')">إغلاق</button>
        </div>
      `;
    }).join('');
  },

  _updateLiveData() {
    // تحديث live بدون re-render كامل
    if (!this._status?.connected) return;
    const b = this._balance?.futures || {};
    const totalWallet = (b.total_wallet_balance || 0).toFixed(2);
    const pnl = (b.total_unrealized_pnl || 0).toFixed(2);
    
    const balEl = document.querySelector('.bn-bal-value');
    if (balEl) balEl.textContent = `$${totalWallet}`;
    
    const posListEl = document.getElementById('bn-positions-list');
    if (posListEl) posListEl.innerHTML = this._renderPositions();
  },

  // ═══════════════════════════════════════════
  // ─── ACTIONS ────────────────────────────────
  // ═══════════════════════════════════════════
  async toggleAutoTrade(enabled) {
    try {
      await this.updateAutoTrade({ enabled });
      await this.load();
    } catch (e) {
      alert('خطأ: ' + e.message);
    }
  },

  async saveSettings() {
    const amount = parseFloat(document.getElementById('bn-trade-amount').value);
    const maxPos = parseInt(document.getElementById('bn-max-positions').value);
    const grades = [];
    if (document.getElementById('bn-grade-s').checked) grades.push('S');
    if (document.getElementById('bn-grade-a').checked) grades.push('A');
    if (document.getElementById('bn-grade-b').checked) grades.push('B');

    if (grades.length === 0) {
      alert('اختر درجة واحدة على الأقل');
      return;
    }

    try {
      await this.updateAutoTrade({
        trade_amount_usdt: amount,
        max_open_positions: maxPos,
        allowed_grades: grades.join(','),
      });
      alert('✅ تم الحفظ');
    } catch (e) {
      alert('خطأ: ' + e.message);
    }
  },

  async handleDisconnect() {
    if (!confirm('هل أنت متأكد من قطع ربط Binance؟')) return;
    try {
      await this.disconnect();
      await this.load();
    } catch (e) {
      alert('خطأ: ' + e.message);
    }
  },

  async closePosition(symbol) {
    if (!confirm(`إغلاق صفقة ${symbol}؟`)) return;
    try {
      const token = STATE.load('authToken');
      await fetch(`${CONFIG.API_BASE}/api/binance/manual/close`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ symbol, market_type: 'futures', percentage: 100 }),
      });
      setTimeout(() => this.load(), 1500);
    } catch (e) {
      alert('خطأ: ' + e.message);
    }
  },
};

// ═══════════════════════════════════════════
// ─── Wallet Tabs Switcher ──────────────────
// ═══════════════════════════════════════════
const WalletTabs = {
  show(which, el) {
    document.querySelectorAll('#sc3 .tab').forEach(t => t.classList.remove('on'));
    el?.classList.add('on');
    const web3View = document.getElementById('wal-web3-view');
    const bnView = document.getElementById('bn-container');
    if (which === 'web3') {
      web3View.style.display = '';
      bnView.style.display = 'none';
      BINANCE_WALLET.unload();
    } else {
      web3View.style.display = 'none';
      bnView.style.display = '';
      BINANCE_WALLET.load();
    }
  }
};
