import React, { useState } from "react";

const SERVER_IP = "178.105.49.200";

const EX = [
  {
    id: "binance", name: "Binance", ar: "باينانس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png",
    color: "#F0B90B", passphrase: false,
    path: "الملف الشخصي ← إدارة الـAPI",
    steps: [
      "افتح موقع باينانس وسجّل الدخول، ثم اضغط أيقونة حسابك أعلى اليمين.",
      "اختر API Management من القائمة.",
      "اضغط Create API ثم اختر System generated.",
      "اكتب اسماً للمفتاح — مثلاً WhaleX — واضغط Next.",
      "أكمل التحقّق برمز البريد وتطبيق المصادقة.",
      "ستظهر API Key و Secret Key — انسخهما فوراً، فالسرّي لا يظهر ثانيةً.",
      "اضغط Edit restrictions وفعّل: Enable Reading و Enable Spot Trading و Enable Futures.",
      "في IP access restriction اختر Restrict access to trusted IPs only وأضف عنوان سيرفرنا.",
      "احفظ، ثم الصق المفتاحين في صفحة التداول الآلي داخل التطبيق.",
    ],
    warn: "باينانس تطلب تفعيل الفيوتشر من حسابك أولاً قبل ظهور الخيار.",
  },
  {
    id: "bybit", name: "Bybit", ar: "باي بيت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png",
    color: "#F7A600", passphrase: false,
    path: "الحساب ← API",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك أعلى اليمين، ثم API.",
      "اضغط Create New Key واختر System-generated API Keys.",
      "اختر نوع الاستخدام: API Transaction.",
      "اكتب اسماً للمفتاح.",
      "في الصلاحيات فعّل Orders و Positions تحت Unified Trading.",
      "فعّل أيضاً Spot Trading إن أردت تشغيل رادار السبوت.",
      "اختر Only IPs with these addresses وأضف عنوان سيرفرنا.",
      "أكمل التحقّق، وانسخ المفتاحين فوراً.",
    ],
    warn: "باي بيت تُلزم بتحديد الـIP لمفاتيح التداول — بدونه لن يعمل المفتاح.",
  },
  {
    id: "okx", name: "OKX", ar: "أوكي إكس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png",
    color: "#8ab4ff", passphrase: true,
    path: "الحساب ← API",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم API.",
      "اضغط Create V5 API Key.",
      "اكتب اسماً للمفتاح.",
      "اكتب Passphrase — كلمة سرّ إضافية. احفظها، فأوكي إكس تطلبها معك.",
      "في الصلاحيات فعّل Trade — ويشمل القراءة تلقائياً.",
      "أضف عنوان سيرفرنا في خانة IP address.",
      "أكمل التحقّق، ثم انسخ: API Key و Secret Key و Passphrase.",
      "الصق الثلاثة في التطبيق — أوكي إكس تحتاج الحقول الثلاثة.",
    ],
    warn: "أوكي إكس تطلب Passphrase — بدونها لن يعمل المفتاح إطلاقاً.",
  },
  {
    id: "bitget", name: "Bitget", ar: "بيتجت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png",
    color: "#00F0FF", passphrase: true,
    path: "الحساب ← إدارة الـAPI",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم API Management.",
      "اضغط Create API واختر System-generated API key.",
      "اكتب اسماً، ثم اكتب Passphrase واحفظها.",
      "في الصلاحيات اختر Read-write.",
      "فعّل: Spot Trade و Futures Trade.",
      "أضف عنوان سيرفرنا في IP address binding.",
      "أكمل التحقّق وانسخ: API Key و Secret Key و Passphrase.",
    ],
    warn: "بيتجت تطلب Passphrase أيضاً — ثلاثة حقول لا اثنان.",
  },
  {
    id: "gate", name: "Gate.io", ar: "جيت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png",
    color: "#17E6A1", passphrase: false,
    path: "الحساب ← مفاتيح الـAPI",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم API Keys.",
      "اضغط Create API Key واختر APIv4 Key.",
      "اكتب اسماً للمفتاح.",
      "فعّل: Spot Trade و Perpetual Futures — واختر Read and Write.",
      "أضف عنوان سيرفرنا في IP Whitelist.",
      "أكمل التحقّق وانسخ المفتاحين فوراً.",
    ],
    warn: "جيت تُظهر المفتاح السرّي مرّة واحدة فقط عند الإنشاء.",
  },
  {
    id: "mexc", name: "MEXC", ar: "مكسي",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png",
    color: "#2AC18A", passphrase: false,
    path: "الحساب ← إدارة الـAPI",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم API Management.",
      "اضغط Create API.",
      "اكتب ملاحظة أو اسماً للمفتاح.",
      "فعّل الصلاحيات: Read و Trade للسبوت والفيوتشر.",
      "أضف عنوان سيرفرنا في خانة الـIP.",
      "أكمل التحقّق وانسخ المفتاحين.",
    ],
    warn: "مكسي تُلزم بتحديد الـIP لمفاتيح الفيوتشر.",
  },
  {
    id: "bingx", name: "BingX", ar: "بينج إكس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png",
    color: "#2954FF", passphrase: false,
    path: "الحساب ← إدارة الـAPI",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم API Management.",
      "اضغط Create API.",
      "اكتب اسماً للمفتاح.",
      "فعّل: Read و Spot Trading و Perpetual Futures Trading.",
      "أضف عنوان سيرفرنا في IP Restriction.",
      "أكمل التحقّق وانسخ المفتاحين.",
    ],
    warn: "بينج إكس تسمّي الفيوتشر Perpetual Futures في قائمة الصلاحيات.",
  },
];

/* رسم توضيحيّ مبسّط لواجهة المنصّة — دوائر مرقّمة على مواضع الأزرار.
   ليس لقطة حقيقية بل خريطة تُريك أين تضغط. */
function Mock({ color }) {
  const c = color;
  return (
    <svg viewBox="0 0 340 210" style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x="0" y="0" width="340" height="210" rx="10" fill="#0d1420" stroke="#223" />
      <rect x="0" y="0" width="340" height="26" rx="10" fill="#141d2c" />
      <rect x="0" y="18" width="340" height="8" fill="#141d2c" />
      <circle cx="14" cy="13" r="3.5" fill="#ef4444" />
      <circle cx="26" cy="13" r="3.5" fill="#eab308" />
      <circle cx="38" cy="13" r="3.5" fill="#22c55e" />
      <circle cx="312" cy="13" r="7.5" fill={c} opacity="0.9" />
      <circle cx="312" cy="13" r="12" fill="none" stroke={c} strokeWidth="1.6" opacity="0.7">
        <animate attributeName="r" values="12;15;12" dur="2s" repeatCount="indefinite" />
      </circle>
      <text x="312" y="17" fontSize="9" fill="#0d1420" textAnchor="middle" fontWeight="700">1</text>
      <rect x="16" y="40" width="120" height="11" rx="3" fill="#2a3a52" />
      <rect x="240" y="36" width="84" height="22" rx="6" fill={c} opacity="0.92" />
      <text x="282" y="51" fontSize="10" fill="#0d1420" textAnchor="middle" fontWeight="700">Create API</text>
      <circle cx="230" cy="47" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="230" y="51" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">2</text>
      <rect x="16" y="70" width="308" height="60" rx="7" fill="#111a28" stroke="#243247" />
      <text x="26" y="86" fontSize="9.5" fill="#7d8fa8">Permissions</text>
      <rect x="26" y="94" width="13" height="13" rx="3" fill="#22c55e" />
      <path d="M29 100.5l2.4 2.6 4.6-5" stroke="#0d1420" strokeWidth="1.8" fill="none" />
      <text x="46" y="104" fontSize="9.5" fill="#c9d6e6">Read</text>
      <rect x="100" y="94" width="13" height="13" rx="3" fill="#22c55e" />
      <path d="M103 100.5l2.4 2.6 4.6-5" stroke="#0d1420" strokeWidth="1.8" fill="none" />
      <text x="120" y="104" fontSize="9.5" fill="#c9d6e6">Spot Trade</text>
      <rect x="196" y="94" width="13" height="13" rx="3" fill="#22c55e" />
      <path d="M199 100.5l2.4 2.6 4.6-5" stroke="#0d1420" strokeWidth="1.8" fill="none" />
      <text x="216" y="104" fontSize="9.5" fill="#c9d6e6">Futures</text>
      <rect x="26" y="112" width="13" height="13" rx="3" fill="none" stroke="#ef4444" strokeWidth="1.6" />
      <path d="M28.5 114.5l8 8M36.5 114.5l-8 8" stroke="#ef4444" strokeWidth="1.4" />
      <text x="46" y="122" fontSize="9.5" fill="#ef4444">Withdraw</text>
      <circle cx="316" cy="100" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="316" y="104" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">3</text>
      <rect x="16" y="140" width="308" height="52" rx="7" fill="#111a28" stroke={c} strokeWidth="1.4" />
      <text x="26" y="157" fontSize="9.5" fill="#7d8fa8">IP Restriction</text>
      <rect x="26" y="164" width="210" height="18" rx="4" fill="#0a1018" stroke="#243247" />
      <text x="34" y="177" fontSize="10" fill={c} fontFamily="monospace">{SERVER_IP}</text>
      <rect x="244" y="164" width="52" height="18" rx="4" fill={c} opacity="0.9" />
      <text x="270" y="177" fontSize="9" fill="#0d1420" textAnchor="middle" fontWeight="700">Add</text>
      <circle cx="312" cy="150" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="312" y="154" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">4</text>
    </svg>
  );
}

function Copy({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={() => {
        try {
          navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        } catch (e) { /* */ }
      }}
      style={{
        background: done ? "#22c55e" : "var(--brand, #2dd4bf)",
        border: "none", borderRadius: 7, padding: "7px 14px", cursor: "pointer",
        color: "#08121c", fontWeight: 800, fontSize: 12.5, whiteSpace: "nowrap",
      }}>
      {done ? "تم النسخ" : "نسخ"}
    </button>
  );
}

export default function ApiGuide() {
  const [open, setOpen] = useState("binance");

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "4px 2px 40px" }}>
      <h2 style={{ fontSize: 20, margin: "6px 0 4px" }}>🔑 ربط مفاتيح المنصّات</h2>
      <p style={{ color: "var(--txt-3, #8fa3ba)", fontSize: 13.5, lineHeight: 1.85, margin: "0 0 16px" }}>
        دليل خطوة بخطوة لإنشاء مفتاح على كل منصّة وربطه بالتطبيق.
        المفتاح يُشفَّر عندنا، ولا نطلب صلاحية سحب إطلاقاً.
      </p>

      <div className="card" style={{ padding: 16, marginBottom: 14, borderInlineStart: "3px solid var(--brand, #2dd4bf)" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>🌐 عنوان سيرفرنا</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <code style={{
            background: "var(--bg-2, #0d1420)", padding: "9px 14px", borderRadius: 7,
            fontSize: 15, fontWeight: 700, letterSpacing: 0.4, direction: "ltr",
            color: "var(--brand, #2dd4bf)", border: "1px solid var(--border, #223)",
          }}>{SERVER_IP}</code>
          <Copy text={SERVER_IP} />
        </div>
        <div style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)", lineHeight: 1.9, marginTop: 10 }}>
          أضف هذا العنوان في خانة IP Restriction على المنصّة.
          فيصير المفتاح صالحاً من سيرفرنا وحده — ولو وصل إلى غيرنا لا يعمل.
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginBottom: 14, borderInlineStart: "3px solid #22c55e" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>📵 هاتفك ليس مطلوباً بعد الربط</div>
        <div style={{ fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2 }}>
          بعد إتمام الربط يجري التنفيذ من سيرفرنا لا من جهازك.
          فلو أُغلق هاتفك أو انقطع الإنترنت عنه أو أغلقت التطبيق —
          يواصل النظام فتح الصفقات وإدارتها وإغلاقها على مدار الساعة.
          هاتفك يعرض لك ما يجري فقط، ولا يشارك في التنفيذ.
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginBottom: 18, borderInlineStart: "3px solid #ef4444" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>🛡️ قواعد الأمان</div>
        <ul style={{ margin: 0, paddingInlineStart: 20, fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2.1 }}>
          <li><b>لا تُفعّل صلاحية السحب أبداً</b> — النظام لا يحتاجها.</li>
          <li>فعّل القراءة وتداول السبوت وتداول الفيوتشر فقط.</li>
          <li>قيّد المفتاح بعنوان سيرفرنا — هذه أقوى حماية لك.</li>
          <li>المفتاح السرّي يظهر مرّة واحدة عند الإنشاء — انسخه فوراً.</li>
          <li>لا تُرسل مفاتيحك لأحد — أدخلها في التطبيق مباشرةً.</li>
        </ul>
      </div>

      {EX.map((e) => {
        const isOpen = open === e.id;
        return (
          <div key={e.id} className="card" style={{ padding: 0, marginBottom: 10, overflow: "hidden" }}>
            <button
              onClick={() => setOpen(isOpen ? "" : e.id)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 11,
                padding: "14px 16px", background: "transparent", border: "none",
                cursor: "pointer", color: "inherit", textAlign: "start",
              }}>
              <img src={e.logo} alt={e.name} width="26" height="26"
                   style={{ borderRadius: 6, flexShrink: 0 }}
                   onError={(ev) => { ev.target.style.display = "none"; }} />
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 14.5, fontWeight: 800, display: "block" }}>
                  {e.ar} <span style={{ color: "var(--txt-3, #8fa3ba)", fontWeight: 500 }}>· {e.name}</span>
                </span>
                <span style={{ fontSize: 11.5, color: "var(--txt-3, #8fa3ba)" }}>{e.path}</span>
              </span>
              {e.passphrase ? (
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: "3px 7px", borderRadius: 5,
                  background: "rgba(234,179,8,0.14)", color: "#eab308", whiteSpace: "nowrap",
                }}>Passphrase</span>
              ) : null}
              <span style={{ fontSize: 15, color: "var(--txt-3, #8fa3ba)", flexShrink: 0 }}>
                {isOpen ? "−" : "+"}
              </span>
            </button>

            {isOpen ? (
              <div style={{ padding: "0 16px 16px" }}>
                <div style={{ border: "1px solid var(--border, #223)", borderRadius: 9, overflow: "hidden", marginBottom: 12 }}>
                  <Mock color={e.color} />
                </div>
                <div style={{ fontSize: 11.5, color: "var(--txt-3, #8fa3ba)", marginBottom: 12, textAlign: "center", lineHeight: 1.7 }}>
                  رسم توضيحيّ للمواضع — قد تختلف الألوان والترتيب قليلاً حسب تحديث المنصّة
                </div>

                <ol style={{ margin: 0, paddingInlineStart: 0, listStyle: "none", display: "grid", gap: 9 }}>
                  {e.steps.map((st, i) => (
                    <li key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <span style={{
                        width: 21, height: 21, borderRadius: "50%", flexShrink: 0,
                        background: "var(--brand, #2dd4bf)", color: "#08121c",
                        fontSize: 11, fontWeight: 800, display: "flex",
                        alignItems: "center", justifyContent: "center", marginTop: 1,
                      }}>{i + 1}</span>
                      <span style={{ fontSize: 13, lineHeight: 1.85 }}>{st}</span>
                    </li>
                  ))}
                </ol>

                <div style={{
                  marginTop: 13, padding: "10px 13px", borderRadius: 8,
                  background: "rgba(234,179,8,0.09)", border: "1px solid rgba(234,179,8,0.22)",
                  fontSize: 12.5, lineHeight: 1.8, color: "#eab308",
                }}>⚠️ {e.warn}</div>

                <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)" }}>عنوان الـIP المطلوب:</span>
                  <code style={{
                    background: "var(--bg-2, #0d1420)", padding: "5px 10px", borderRadius: 6,
                    fontSize: 13, direction: "ltr", color: "var(--brand, #2dd4bf)",
                  }}>{SERVER_IP}</code>
                  <Copy text={SERVER_IP} />
                </div>
              </div>
            ) : null}
          </div>
        );
      })}

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>❓ بعد الربط</div>
        <div style={{ fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2 }}>
          افتح صفحة التداول الآلي داخل التطبيق، الصق المفتاحين
          وكلمة الـPassphrase إن طلبتها منصّتك، ثم اضغط اختبار الاتصال.
          إن نجح الاختبار فالربط تمّ، ويبدأ النظام العمل على حسابك فوراً.
        </div>
      </div>
    </div>
  );
}
