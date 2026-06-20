/**
 * profile.js — WhaleX Prime
 * ══════════════════════════════════════
 * صفحة الحساب والإعدادات.
 * ══════════════════════════════════════
 */

const PROFILE = {

  load() {
    const p = STATE.profile;
    if(p.name) {
      document.getElementById('p-name').textContent = p.name;
      document.getElementById('p-av').textContent   = p.name[0].toUpperCase();
      if(p.email) document.getElementById('p-email').textContent = p.email;
    }
    this.loadStats();
    this.loadReferral();
  },

  async loadStats() {
    const d = await API.getTradeStats();
    if(!d) return;
    document.getElementById('st-pnl').textContent = UI.fmtUSD(d.total_pnl||0);
    document.getElementById('st-tr').textContent  = d.total_trades || 0;
    document.getElementById('st-wr').textContent  = (d.win_rate||0).toFixed(1)+'%';
    if(d.demo_balance) {
      document.getElementById('total-bal').textContent = d.demo_balance.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    }
  },

  async loadReferral() {
    const d = await API.getReferralStats();
    if(!d) return;
    document.getElementById('ref-cnt').textContent  = d.referrals   || 0;
    document.getElementById('ref-pts').textContent  = d.pro_points  || 0;
    document.getElementById('ref-days').textContent = d.free_days   || 0;
  },

  updateUI() {
    const isPro = STATE.isPro;
    const txt   = isPro ? '⭐ PRO Plan' : 'Free Plan';
    ['tier-tag','tier-badge'].forEach(id => {
      const el = document.getElementById(id);
      if(el) el.textContent = txt;
    });
  },

  async upgrade() {
    UI.toast('⏳ جاري معالجة الاشتراك...');
    const d = await API.upgrade({ tx_hash:'demo_'+Date.now(), amount_paid:50 });
    if(d?.status==='upgraded' || d?.status==='already_pro') {
      STATE.save('tier','pro');
      this.updateUI();
      UI.toast('🎉 PRO مفعّل! استمتع بكل الميزات');
      SIGNALS.load();
    } else {
      UI.toast('فشل الاشتراك — حاول مرة أخرى');
    }
  },

  copyRef() {
    UI.copy(document.getElementById('ref-link').textContent, '✓ تم نسخ رابط الإحالة');
  },

  shareRef() {
    const url = document.getElementById('ref-link').textContent;
    if(navigator.share) navigator.share({ title:'WhaleX Prime', url });
    else this.copyRef();
  },

  logout() {
    localStorage.clear();
    UI.toast('تم تسجيل الخروج');
    setTimeout(() => location.reload(), 1000);
  },

  // ── Settings ─────────────────────────

  openSettings() {
    this._buildSettingsPlatforms();
    this._syncSettingsUI();
    UI.openModal('mo-settings');
  },

  _buildSettingsPlatforms() {
    const list = document.getElementById('set-plat-list');
    if(!list) return;
    const all = [...CONFIG.PLATFORMS.dex, ...CONFIG.PLATFORMS.cex];
    list.innerHTML = all.map(p => `
      <div class="set-opt${STATE.setup.plat===p.v?' sel':''}" id="sp-${p.v}" onclick="PROFILE._selectPlatform('${p.v}')">
        <img src="${p.logo}" style="width:22px;height:22px;border-radius:5px;object-fit:contain" onerror="this.style.display='none'" alt="${p.n}">
        <div style="flex:1">
          <div style="font-weight:700;font-size:12px">${p.n}</div>
          <div style="font-size:10px;color:var(--text2)">${p.s}</div>
        </div>
        <div class="set-dot"></div>
      </div>`).join('');
  },

  _syncSettingsUI() {
    // نوع التداول
    ['futures','spot','meme'].forEach(t => {
      document.getElementById('set-t-'+t)?.classList.toggle('sel', STATE.setup.types?.includes(t));
    });
    // وضع التداول
    ['auto','manual'].forEach(m => {
      document.getElementById('set-m-'+m)?.classList.toggle('sel', STATE.setup.auto === m);
    });
  },

  _selectPlatform(v) {
    document.querySelectorAll('[id^="sp-"]').forEach(e => e.classList.remove('sel'));
    document.getElementById('sp-'+v)?.classList.add('sel');
    STATE.setup.plat = v;
  },

  toggleTradingType(t) {
    if(!STATE.setup.types) STATE.setup.types = [];
    const i = STATE.setup.types.indexOf(t);
    if(i === -1) STATE.setup.types.push(t);
    else STATE.setup.types.splice(i,1);
    document.getElementById('set-t-'+t)?.classList.toggle('sel', STATE.setup.types.includes(t));
  },

  setAutoMode(m) {
    STATE.setup.auto = m;
    ['auto','manual'].forEach(x => document.getElementById('set-m-'+x)?.classList.toggle('sel', x===m));
  },

  saveSettings() {
    STATE.save('setup', STATE.setup);
    UI.closeModal('mo-settings');
    UI.toast('✅ تم حفظ الإعدادات');
    if(STATE.currentScreen === 2) SIGNALS.load();
  },

  async saveApiKey() {
    const p = document.getElementById('api-plat').value;
    const k = document.getElementById('api-k').value;
    const s = document.getElementById('api-s').value;
    if(!k || !s) { UI.toast('أدخل API Key و Secret'); return; }
    if(k.length < 20 || s.length < 20) { UI.toast('المفاتيح قصيرة جداً'); return; }
    UI.toast('جاري اختبار المفاتيح...');
    if (p === 'binance') {
      try {
        const token = STATE.load('authToken');
        const isTestnet = confirm('استخدام Testnet (تجريبي)؟\n\nموافق = Testnet (آمن)\nإلغاء = Live (حقيقي)');
        const res = await fetch(`${CONFIG.API_BASE}/api/binance/connect`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : '',
          },
          body: JSON.stringify({
            api_key: k, api_secret: s,
            is_testnet: isTestnet, account_type: 'futures',
          }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
          UI.toast(`تم ربط Binance ${isTestnet ? 'Testnet' : 'Live'} بنجاح!`);
          UI.closeModal('mo-api');
          if (typeof BINANCE_WALLET !== 'undefined') {
            setTimeout(() => { ROUTER.go(3); BINANCE_WALLET.load(); }, 500);
          }
        } else {
          UI.toast((data.detail || 'فشل الربط'));
        }
      } catch (e) {
        UI.toast('خطأ: ' + e.message);
      }
      return;
    }
    UI.toast(`منصة ${p} ستكون متاحة قريباً — الآن Binance فقط`);
  },
};
