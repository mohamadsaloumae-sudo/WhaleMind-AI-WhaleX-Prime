/**
 * router.js — WhaleX Prime
 * ══════════════════════════════════════
 * إدارة التنقل بين الشاشات.
 * ══════════════════════════════════════
 */

const ROUTER = {

  SCREENS: {
    0: { id:'sc0', navId:'n0',  label:'الرئيسية', onEnter: ()=> SIGNALS.loadHome() },
    1: { id:'sc1', navId:null,  label:'تداول',    onEnter: ()=> TRADEPRO.onEnter(), onLeave: ()=> TRADEPRO.onLeave() },
    2: { id:'sc2', navId:'n2',  label:'إشارات',   onEnter: ()=> SIGNALS.load() },
    3: { id:'sc3', navId:'n3',  label:'المحفظة',  onEnter: ()=> WALLET.load() },
    4: { id:'sc4', navId:null,  label:'حسابي',    onEnter: ()=> PROFILE.load() },
    5: { id:'sc5', navId:'n5',  label:'AI Chat',  onEnter: ()=> CHAT.init() },
    6: { id:'sc6', navId:null,  label:'Scanner',  onEnter: ()=> {} },
  },

  current: 0,

  go(i) {
    const prev = this.SCREENS[this.current];
    try { prev?.onLeave?.(); } catch(e) {}
    document.getElementById(prev?.id)?.classList.remove('show');

    const next = this.SCREENS[i];
    if(!next) return;
    document.getElementById(next.id)?.classList.add('show');
    this.current = i;
    STATE.save('currentScreen', i);

    const back = document.getElementById('btn-back');
    if(back) back.classList.toggle('hidden', i === 0);

    document.querySelectorAll('.ni').forEach(n => n.classList.remove('on'));
    if(next.navId) document.getElementById(next.navId)?.classList.add('on');

    try { next.onEnter?.(); } catch(e) { console.error('Router onEnter error:', e); }
    BUS.emit('router:change', { from: this.current, to: i, screen: next });
  },

  back() { this.go(0); },

  init() {
    let startX = 0;
    document.addEventListener('touchstart', e => {
      startX = e.changedTouches[0].screenX;
    }, {passive:true});

    document.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].screenX - startX;
      // لا swipe إذا كان في طبقة مفتوحة
      if(document.querySelector('.tp-layer.on')) return;
      const isScrollable = e.target.closest('.scr-body, .chat-body, .mo-sheet, .ob-body, .tp-layer, .tp-orderbook, .tp-form');
      if(Math.abs(dx) > 70 && !isScrollable) {
        if(dx < 0 && this.current < 5) this.go(this.current + 1);
        else if(dx > 0 && this.current > 0) this.go(this.current - 1);
      }
    }, {passive:true});

    document.addEventListener('visibilitychange', () => {
      if(document.visibilityState === 'hidden') this.go(0);
    });
  },
};
