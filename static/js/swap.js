/**
 * swap.js — WhaleX Prime
 * ══════════════════════════════════════
 * Swap بين العملات داخل المحفظة.
 * ══════════════════════════════════════
 */

const SWAP = {

  _rates() {
    const P = STATE.prices;
    return {
      BTC:  P.BTCUSDT?.price || 0,
      ETH:  P.ETHUSDT?.price || 0,
      SOL:  P.SOLUSDT?.price || 0,
      BNB:  P.BNBUSDT?.price || 0,
      USDT: 1,
      USDC: 1,
    };
  },

  update() {
    const from = document.getElementById('sw-from').value;
    const to   = document.getElementById('sw-to').value;
    const amt  = parseFloat(document.getElementById('sw-amt')?.value) || 0;
    const r    = this._rates();

    if(!r[from] || !r[to] || amt <= 0) {
      document.getElementById('sw-out').textContent      = '0.00';
      document.getElementById('sw-rate').textContent     = '--';
      document.getElementById('sw-fee').textContent      = '--';
      document.getElementById('sw-receive').textContent  = '--';
      return;
    }

    const rate    = r[from] / r[to];
    const usdVal  = amt * r[from];
    const fee     = usdVal * CONFIG.GAS_FEE_PERCENT;
    const netUsd  = usdVal - fee;
    const receive = netUsd / r[to];

    document.getElementById('sw-out').textContent      = receive.toFixed(6);
    document.getElementById('sw-rate').textContent     = `1 ${from} = ${rate.toFixed(6)} ${to}`;
    document.getElementById('sw-fee').textContent      = '$' + fee.toFixed(2);
    document.getElementById('sw-receive').textContent  = `${receive.toFixed(6)} ${to}`;
  },

  flip() {
    const f = document.getElementById('sw-from');
    const t = document.getElementById('sw-to');
    const v = f.value;
    f.value = t.value;
    t.value = v;
    this.update();
  },

  async execute() {
    const amt = parseFloat(document.getElementById('sw-amt')?.value) || 0;
    if(amt <= 0) { UI.toast('أدخل المبلغ'); return; }

    const from = document.getElementById('sw-from').value;
    const to   = document.getElementById('sw-to').value;
    if(from === to) { UI.toast('اختر عملتين مختلفتين'); return; }

    UI.toast('جاري التنفيذ...');
    setTimeout(() => {
      UI.toast(`✓ تم تبديل ${amt} ${from} إلى ${to}`);
      UI.closeModal('mo-swap');
    }, 1500);
  },
};
