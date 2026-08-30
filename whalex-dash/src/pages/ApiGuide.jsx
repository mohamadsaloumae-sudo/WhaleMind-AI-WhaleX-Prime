import React, { useState } from "react";
import PlanCalc from "../components/PlanCalc.jsx";
import { useLang } from "../context/LangContext.jsx";

const SERVER_IP = "178.105.49.200";

const EX = [
  {
    id: "binance", name: "Binance", ar: "باينانس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png",
    color: "#F0B90B", passphrase: false,
    path: "الحساب [Account] ← إدارة المفاتيح [API Management]",
    path_en: "[Account] - [API Management]",
    pre: "قبل الإنشاء يلزم ثلاثة أمور: تفعيل المصادقة الثنائية، وإيداع أي مبلغ في محفظة السبوت لتنشيط الحساب، وإتمام توثيق الهوية.",
    pre_en: "Three things are required first: two-factor authentication enabled, any deposit into your Spot Wallet to activate the account, and completed identity verification.",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك أعلى اليمين، ثم اختر الحساب [Account].",
      "افتح إدارة المفاتيح [API Management] واضغط إنشاء مفتاح [Create API].",
      "اختر نوع المفتاح: مولّد النظام [System-generated] — وهو الذي يُعطيك مفتاحاً وسرّاً.",
      "اكتب اسماً للمفتاح [Label] مثل WhaleX.",
      "أكمل التحقّق بجهاز المصادقة أو مفتاح المرور [2FA / Passkey].",
      "انسخ المفتاحين فوراً: [API Key] و[Secret Key] — والسرّي لا يظهر ثانيةً.",
      "اضغط تعديل الصلاحيات [Edit restrictions].",
      "في تقييد الوصول [IP access restriction] اختر السماح لعناوين موثوقة فقط [Restrict access to trusted IPs only]، وأضف عنوان سيرفرنا واحفظ.",
      "بعد حفظ العنوان فعّل: القراءة [Enable Reading] وتداول السبوت [Enable Spot and Margin Trading] والفيوتشر [Enable Futures].",
      "انتظر خمس إلى عشر دقائق حتى ينشط المفتاح، ثم أدخله في صفحة التداول الآلي.",
    ],
    steps_en: [
      "Log in, click your profile icon at the top right, then choose [Account].",
      "Open [API Management] and click [Create API].",
      "Choose the key type: [System-generated] — this gives you a key and a secret.",
      "Enter a [Label] for the key, such as WhaleX.",
      "Complete verification with your 2FA device or passkey.",
      "Copy both immediately: [API Key] and [Secret Key] — the secret is never shown again.",
      "Click [Edit restrictions].",
      "Under [IP access restriction] choose [Restrict access to trusted IPs only], add our server IP and save.",
      "Once the IP is saved, enable: [Enable Reading], [Enable Spot and Margin Trading] and [Enable Futures].",
      "Wait five to ten minutes for activation, then enter it in the Auto Trading page.",
    ],
    warn: "قاعدة باينانس منذ 2023: المفتاح بلا تقييد عنوان لا يُمنَح إلا صلاحية القراءة [Enable Reading] — فالعنوان أولاً ثم الصلاحيات. وإن أنشأتَ المفتاح قبل تفعيل حساب الفيوتشر، أو فعّلتَ هامش المحفظة [Portfolio Margin]، فلن تعمل صلاحية الفيوتشر إطلاقاً.",
    warn_en: "Binance rule since 2023: a key with an unrestricted IP can only be set to [Enable Reading] — so set the IP first, then the permissions. And if the key was created before your Futures account was enabled, or you activated [Portfolio Margin], the Futures permission will not work at all.",
  },
  {
    id: "bybit", name: "Bybit", ar: "باي بيت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png",
    color: "#F7A600", passphrase: false,
    path: "الحساب والأمان [Account & Security] ← إدارة المفاتيح [API Management]",
    path_en: "[Account & Security] - [API Management]",
    pre: "الحسابات الجديدة تنتظر 48 ساعة قبل إتاحة إنشاء المفاتيح. والعملية من متصفّح الحاسوب لا من التطبيق.",
    pre_en: "New accounts wait 48 hours before key creation becomes available. Use a desktop browser, not the app.",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك أعلى اليمين، ثم المفاتيح [API].",
      "افتح إدارة المفاتيح [API Management] واضغط إنشاء مفتاح جديد [Create New Key].",
      "اختر مفاتيح مولّدة من النظام [System-generated API Keys].",
      "في استخدام المفتاح [API Key Usage] اختر معاملات برمجية [API Transaction].",
      "اكتب اسماً للمفتاح، واختر [HMAC] إن سُئلت عن نوع التوقيع.",
      "في الصلاحيات [API Key Permissions] اختر قراءة وكتابة [Read-Write].",
      "تحت الحساب الموحّد [Unified Trading] فعّل: الأوامر [Orders] والمراكز [Positions].",
      "فعّل تداول السبوت [Spot Trading] إن أردت تشغيل رادار السبوت.",
      "ألغِ التحديد عن: السحب [Withdrawal] والتحويل [Account Transfer] وتحويل الحسابات الفرعية [Subaccount Transfer].",
      "اختر السماح لعناوين محدّدة [Only IPs with granted permissions] وأضف عنوان سيرفرنا.",
      "اضغط إرسال [Submit]، أكمل التحقّق، ثم انسخ المفتاحين فوراً.",
    ],
    steps_en: [
      "Log in, click your account icon at the top right, then [API].",
      "Open [API Management] and click [Create New Key].",
      "Choose [System-generated API Keys].",
      "Under [API Key Usage] select [API Transaction].",
      "Name the key, and choose [HMAC] if asked about the signature type.",
      "Under [API Key Permissions] choose [Read-Write].",
      "Under [Unified Trading] enable: [Orders] and [Positions].",
      "Enable [Spot Trading] if you want the spot radar running.",
      "Uncheck: [Withdrawal], [Account Transfer] and [Subaccount Transfer].",
      "Choose [Only IPs with granted permissions] and add our server IP.",
      "Click [Submit], complete verification, then copy both keys immediately.",
    ],
    warn: "أموالك يجب أن تكون في الحساب الموحّد [Unified Trading Account] لا في حساب التمويل [Funding] — وإلّا لن يراها النظام. والمفتاح بلا تقييد عنوان ينتهي بعد ثلاثة أشهر.",
    warn_en: "Your funds must sit in the [Unified Trading Account], not [Funding] — otherwise the system cannot see them. A key without an IP restriction expires after three months.",
  },
  {
    id: "okx", name: "OKX", ar: "أوكي إكس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png",
    color: "#8ab4ff", passphrase: true,
    path: "الحساب ← المفاتيح [API] ← إنشاء مفتاح [Create V5 API Key]",
    path_en: "[Account] - [API] - [Create V5 API Key]",
    pre: "من متصفّح الحاسوب فقط — لا تعمل من التطبيق. ويلزم توثيق الهوية وتفعيل المصادقة الثنائية.",
    pre_en: "Desktop browser only — this does not work in the app. Identity verification and two-factor authentication are required.",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك أعلى اليمين، ثم المفاتيح [API].",
      "اضغط إنشاء مفتاح [Create V5 API Key].",
      "اكتب اسماً للمفتاح [API Name].",
      "اكتب كلمة السرّ الإضافية [Passphrase] — تختارها أنت، واحفظها فأوكي إكس لا تستعيدها.",
      "في الصلاحيات [Permissions] فعّل التداول [Trade] — وتُدرَج القراءة معه تلقائياً.",
      "في قائمة العناوين المسموحة [IP address allowlist] أضف عنوان سيرفرنا.",
      "اضغط تأكيد [Confirm] وأكمل التحقّق.",
      "انسخ الثلاثة: [API Key] و[Secret Key] و[Passphrase] — وأدخلها كلّها في التطبيق.",
    ],
    steps_en: [
      "Log in, click your account icon at the top right, then [API].",
      "Click [Create V5 API Key].",
      "Enter an [API Name] for the key.",
      "Set a [Passphrase] — you choose it, and save it since OKX cannot recover it.",
      "Under [Permissions] enable [Trade] — reading is included automatically.",
      "Add our server IP under [IP address allowlist].",
      "Click [Confirm] and complete verification.",
      "Copy all three: [API Key], [Secret Key] and [Passphrase] — enter all of them in the app.",
    ],
    warn: "اضبط وضع الحساب [Account mode] على الفيوتشر [Futures] أو المتقدّم [Advanced] من إعدادات التداول، وإلّا لن يعمل الفيوتشر. والمفتاح بلا عنوان يُحذف تلقائياً بعد خمول قصير — أمّا المقيَّد بعنوان فلا ينتهي أبداً.",
    warn_en: "Set [Account mode] to [Futures] or [Advanced] in your trading settings, otherwise futures will not work. A key without an IP is deleted automatically after a short period of inactivity — one bound to an IP never expires.",
  },
  {
    id: "bitget", name: "Bitget", ar: "بيتجت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png",
    color: "#00F0FF", passphrase: true,
    path: "الحساب ← إدارة المفاتيح [API Management]",
    path_en: "[Account] - [API Management]",
    pre: "بيتجت تطلب كلمة سرّ إضافية [Passphrase] تختارها أنت — فالحقول ثلاثة لا اثنان.",
    pre_en: "Bitget requires a [Passphrase] that you choose — three fields, not two.",
    steps: [
      "سجّل الدخول واضغط أيقونة حسابك، ثم إدارة المفاتيح [API Management].",
      "اضغط إنشاء مفتاح [Create API] واختر مولّد النظام [System-generated API key].",
      "اكتب اسماً للمفتاح، ثم اكتب كلمة السرّ الإضافية [Passphrase] واحفظها.",
      "في الصلاحيات اختر قراءة وكتابة [Read-write].",
      "فعّل: تداول السبوت [Spot Trade] وتداول الفيوتشر [Futures Trade].",
      "اترك السحب [Withdraw] مغلقاً — النظام لا يحتاجه.",
      "في ربط العنوان [IP address binding] أضف عنوان سيرفرنا.",
      "أكمل التحقّق وانسخ: [API Key] و[Secret Key] و[Passphrase].",
    ],
    steps_en: [
      "Log in, click your account icon, then [API Management].",
      "Click [Create API] and choose [System-generated API key].",
      "Name the key, then set a [Passphrase] and save it.",
      "Under permissions choose [Read-write].",
      "Enable: [Spot Trade] and [Futures Trade].",
      "Leave [Withdraw] off — the system does not need it.",
      "Add our server IP under [IP address binding].",
      "Complete verification and copy: [API Key], [Secret Key] and [Passphrase].",
    ],
    warn: "رسالة الخطأ [Apikey does not exist] أو [Passphrase is error] تعني أن كلمة السرّ التي أدخلتَها لا تطابق ما كتبتَه عند الإنشاء.",
    warn_en: "An error saying [Apikey does not exist] or [Passphrase is error] means the passphrase you entered does not match the one set at creation.",
  },
  {
    id: "gate", name: "Gate.io", ar: "جيت",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png",
    color: "#17E6A1", passphrase: false,
    path: "الملف الشخصي ← إدارة المفاتيح [API Management]",
    path_en: "[Profile] - [API Management]",
    pre: "المفتاح بلا قائمة عناوين يبقى صالحاً 90 يوماً فقط ثم يتوقّف.",
    pre_en: "A key without an IP list stays valid for only 90 days, then stops working.",
    steps: [
      "سجّل الدخول ومرّر المؤشّر على أيقونة حسابك، ثم إدارة المفاتيح [API Management].",
      "اضغط إنشاء مفتاح [Create API Key].",
      "اكتب اسماً للمفتاح.",
      "في نوع المفتاح [API Key Type] اختر [APIv4 Key].",
      "في نوع الحساب اختر حساب التداول [Trading Account].",
      "في الصلاحيات [Permissions] فعّل: تداول السبوت [Spot Trade] والعقود الدائمة [Perpetual Futures] والمحفظة [Wallet].",
      "في قائمة العناوين [IP Permissions] أضف عنوان سيرفرنا — فيصير المفتاح دائماً بلا انتهاء.",
      "أكمل التحقّق وانسخ المفتاحين فوراً.",
    ],
    steps_en: [
      "Log in, hover over your account icon, then [API Management].",
      "Click [Create API Key].",
      "Name the key.",
      "Under [API Key Type] choose [APIv4 Key].",
      "For account type choose [Trading Account].",
      "Under [Permissions] enable: [Spot Trade], [Perpetual Futures] and [Wallet].",
      "Add our server IP under [IP Permissions] — the key then never expires.",
      "Complete verification and copy both keys immediately.",
    ],
    warn: "بلا إضافة العنوان سيتوقّف مفتاحك بعد 90 يوماً وتحتاج إنشاء غيره.",
    warn_en: "Without adding the IP your key stops after 90 days and you will need to create another.",
  },
  {
    id: "mexc", name: "MEXC", ar: "مكسي",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png",
    color: "#2AC18A", passphrase: false,
    path: "الملف الشخصي ← إدارة المفاتيح [API Management]",
    path_en: "[Profile] - [API Management]",
    pre: "من موقع الويب فقط — تطبيق مكسي لا يدعم إنشاء المفاتيح.",
    pre_en: "Web only — the MEXC app does not support key creation.",
    steps: [
      "سجّل الدخول من متصفّح واضغط أيقونة حسابك أعلى اليمين، ثم إدارة المفاتيح [API Management].",
      "اضغط إنشاء مفتاح [Create API].",
      "اكتب ملاحظة في خانة [Notes] — وهي إلزامية.",
      "تحت حساب الفيوتشر [Futures Account] فعّل: عرض تفاصيل الحساب [View Account Details].",
      "تحت التداول [Trade] فعّل: عرض تفاصيل الأوامر [View Order Details] وإرسال الأوامر [Order Placing].",
      "فعّل صلاحيات السبوت [Spot] إن أردت تشغيل رادار السبوت.",
      "في ربط العنوان [Link IP Address] أضف عنوان سيرفرنا.",
      "ضع علامة على إقرار المخاطر [Risk Reminders] ثم اضغط إنشاء [Create].",
      "أكمل التحقّق وانسخ المفتاحين فوراً.",
    ],
    steps_en: [
      "Log in from a browser, click your account icon at the top right, then [API Management].",
      "Click [Create API].",
      "Write a note in the [Notes] field — it is mandatory.",
      "Under [Futures Account] enable: [View Account Details].",
      "Under [Trade] enable: [View Order Details] and [Order Placing].",
      "Enable the [Spot] permissions too if you want the spot radar running.",
      "Add our server IP under [Link IP Address].",
      "Tick the [Risk Reminders] acknowledgement then click [Create].",
      "Complete verification and copy both keys immediately.",
    ],
    warn: "مكسي تُنبّه: المفتاح غير المرتبط بعنوان صالح 90 يوماً فقط. وإضافة العنوان تُلغي هذا الانتهاء.",
    warn_en: "MEXC warns that a key not linked to an IP is valid for 90 days only. Adding the IP removes that expiry.",
  },
  {
    id: "bingx", name: "BingX", ar: "بينج إكس",
    logo: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png",
    color: "#2954FF", passphrase: false,
    path: "الصورة الشخصية ← إدارة المفاتيح [API Management]",
    path_en: "[Avatar] - [API Management]",
    pre: "بينج إكس تفصل صلاحية السبوت عن الفيوتشر — فعّل ما تحتاجه.",
    pre_en: "BingX separates spot and futures permissions — enable what you need.",
    steps: [
      "سجّل الدخول واضغط صورتك الشخصية أعلى اليمين، ثم إدارة المفاتيح [API Management].",
      "اضغط إنشاء مفتاح [Create API].",
      "اكتب اسماً للمفتاح.",
      "فعّل تداول السبوت [Spot Trading] إن أردت السبوت.",
      "فعّل تداول العقود الدائمة [Perpetual Futures Trading] للفيوتشر.",
      "أضف عنوان سيرفرنا في خانة العناوين المسموحة [IP Restriction].",
      "اضغط إنشاء [Create] وأكمل التحقّق، ثم انسخ المفتاحين.",
    ],
    steps_en: [
      "Log in, click your profile picture at the top right, then [API Management].",
      "Click [Create API].",
      "Name the key.",
      "Enable [Spot Trading] if you want spot.",
      "Enable [Perpetual Futures Trading] for futures.",
      "Add our server IP under [IP Restriction].",
      "Click [Create], complete verification, then copy both keys.",
    ],
    warn: "إن تداولتَ على السوقين بكثافة، أنشئ مفتاحين منفصلين لتفادي حدود الطلبات.",
    warn_en: "If you trade heavily on both markets, create two separate keys to avoid rate limit errors.",
  },
];



/* رسم توضيحيّ مبسّط لواجهة المنصّة — دوائر مرقّمة على مواضع الأزرار.
   ليس لقطة حقيقية بل خريطة تُريك أين تضغط. */
function Mock({ color }) {
  const c = color;
  return (
    <svg viewBox="0 0 340 218" direction="ltr"
         style={{ width: "100%", height: "auto", display: "block",
                  direction: "ltr", unicodeBidi: "isolate" }}>
      <rect x="0" y="0" width="340" height="218" rx="10" fill="#0d1420" stroke="#223" />
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
      <rect x="16" y="38" width="118" height="10" rx="3" fill="#2a3a52" />
      <rect x="238" y="34" width="86" height="22" rx="6" fill={c} opacity="0.92" />
      <text x="281" y="49" fontSize="10" fill="#0d1420" textAnchor="middle" fontWeight="700">Create API</text>
      <circle cx="228" cy="45" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="228" y="49" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">2</text>
      <rect x="16" y="68" width="308" height="76" rx="7" fill="#111a28" stroke="#243247" />
      <text x="26" y="82" fontSize="9" fill="#7d8fa8">Permissions</text>
      <rect x="26" y="86" width="13" height="13" rx="3" fill="#22c55e" />
      <path d="M29 92.5l2.4 2.6 4.6 -5" stroke="#0d1420" strokeWidth="1.9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <text x="46" y="96" fontSize="9.5" fill="#c9d6e6">Read</text>
      <rect x="26" y="103" width="13" height="13" rx="3" fill="#22c55e" />
      <path d="M29 109.5l2.4 2.6 4.6 -5" stroke="#0d1420" strokeWidth="1.9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <text x="46" y="113" fontSize="9.5" fill="#c9d6e6">Spot + Futures Trade</text>
      <rect x="26" y="120" width="13" height="13" rx="3" fill="none" stroke="#ef4444" strokeWidth="1.6" />
      <path d="M28.5 122.5l8 8M36.5 122.5l-8 8" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
      <text x="46" y="130" fontSize="9.5" fill="#ef4444">Withdraw</text>
      <circle cx="310" cy="84" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="310" y="88" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">3</text>
      <rect x="16" y="152" width="308" height="52" rx="7" fill="#111a28" stroke={c} strokeWidth="1.4" />
      <text x="26" y="168" fontSize="9" fill="#7d8fa8">IP Restriction</text>
      <rect x="26" y="175" width="206" height="19" rx="4" fill="#0a1018" stroke="#243247" />
      <text x="34" y="188" fontSize="10" fill={c} fontFamily="monospace">{SERVER_IP}</text>
      <rect x="242" y="175" width="56" height="19" rx="4" fill={c} opacity="0.9" />
      <text x="270" y="188" fontSize="9" fill="#0d1420" textAnchor="middle" fontWeight="700">Add</text>
      <circle cx="310" cy="164" r="9" fill="#0d1420" stroke={c} strokeWidth="1.5" />
      <text x="310" y="168" fontSize="9.5" fill={c} textAnchor="middle" fontWeight="700">4</text>
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
      {done ? "\u2713" : "Copy"}
    </button>
  );
}

export default function ApiGuide() {
  const [open, setOpen] = useState("binance");
  // 🌐 اللغة من السياق — القراءة المباشرة من التخزين لا تُعيد الرسم
  //    عند التبديل، والمفتاح whalex_lang لا wx_lang.
  const { lang } = useLang();
  const ar = lang !== "en";
  const L = (a, e) => (ar ? a : e);

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "4px 2px 40px" }}>
      <h2 style={{ fontSize: 20, margin: "6px 0 4px" }}>{L("📚 دليل الاستخدام", "📚 User Guide")}</h2>

      {/* 🧮 حاسبة الخطّة — أوّل ما يحتاجه المشترك قبل أن يربط حسابه:
          كم يضع، وبأي إعدادات، وكم يتوقّع. والأرقام من أداء النظام
          الحقيقيّ خلال ثلاثين يوماً لا من تقدير. */}
      <PlanCalc />
      <div style={{
        fontSize: 13.5, fontWeight: 800, margin: "14px 0 6px",
        display: "flex", alignItems: "center", gap: 7,
      }}>
        <span style={{
          width: 3, height: 15, borderRadius: 2,
          background: "var(--brand, #2dd4bf)", display: "inline-block",
        }} />
        {L("🔑 ربط مفاتيح المنصّات", "🔑 Connecting exchange API keys")}
      </div>
      <p style={{ color: "var(--txt-3, #8fa3ba)", fontSize: 13.5, lineHeight: 1.85, margin: "0 0 16px" }}>
{L("دليل خطوة بخطوة لإنشاء مفتاح على كل منصّة وربطه بالتطبيق. المفتاح يُشفَّر عندنا، ولا نطلب صلاحية سحب إطلاقاً.",
            "A step-by-step guide to creating an API key on each exchange and linking it to the app. Your key is encrypted on our side, and we never request withdrawal permission.")}
      </p>

      <div className="card" style={{ padding: 16, marginBottom: 14, borderInlineStart: "3px solid var(--brand, #2dd4bf)" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>{L("🌐 عنوان سيرفرنا", "🌐 Our server IP")}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <code style={{
            background: "var(--bg-2, #0d1420)", padding: "9px 14px", borderRadius: 7,
            fontSize: 15, fontWeight: 700, letterSpacing: 0.4, direction: "ltr",
            color: "var(--brand, #2dd4bf)", border: "1px solid var(--border, #223)",
          }}>{SERVER_IP}</code>
          <Copy text={SERVER_IP} />
        </div>
        <div style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)", lineHeight: 1.9, marginTop: 10 }}>
{L("أضف هذا العنوان في خانة IP Restriction على المنصّة. فيصير المفتاح صالحاً من سيرفرنا وحده — ولو وصل إلى غيرنا لا يعمل.",
              "Add this address in the IP Restriction field on the exchange. The key then works only from our server — if it ever leaks elsewhere it is useless.")}
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginBottom: 14, borderInlineStart: "3px solid #22c55e" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>{L("📵 هاتفك ليس مطلوباً بعد الربط", "📵 Your phone is not needed after linking")}</div>
        <div style={{ fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2 }}>
{L("بعد إتمام الربط يجري التنفيذ من سيرفرنا لا من جهازك. فلو أُغلق هاتفك أو انقطع الإنترنت عنه أو أغلقت التطبيق — يواصل النظام فتح الصفقات وإدارتها وإغلاقها على مدار الساعة. هاتفك يعرض لك ما يجري فقط، ولا يشارك في التنفيذ.",
              "Once linked, execution runs on our server, not on your device. If your phone is off, loses internet, or you close the app, the system keeps opening, managing and closing trades around the clock. Your phone only shows you what is happening.")}
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginBottom: 18, borderInlineStart: "3px solid #ef4444" }}>
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>{L("🛡️ قواعد الأمان", "🛡️ Security rules")}</div>
        <ul style={{ margin: 0, paddingInlineStart: 20, fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2.1 }}>
          <li>{L("لا تُفعّل صلاحية السحب أبداً — النظام لا يحتاجها.", "Never enable withdrawal permission — the system does not need it.")}</li>
          <li>{L("فعّل القراءة وتداول السبوت وتداول الفيوتشر فقط.", "Enable reading, spot trading and futures trading only.")}</li>
          <li>{L("قيّد المفتاح بعنوان سيرفرنا — هذه أقوى حماية لك.", "Restrict the key to our server IP — this is your strongest protection.")}</li>
          <li>{L("المفتاح السرّي يظهر مرّة واحدة عند الإنشاء — انسخه فوراً.", "The secret key is shown once at creation — copy it immediately.")}</li>
          <li>{L("لا تُرسل مفاتيحك لأحد — أدخلها في التطبيق مباشرةً.", "Never send your keys to anyone — enter them directly in the app.")}</li>
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
                  {ar ? e.ar : e.name} <span style={{ color: "var(--txt-3, #8fa3ba)", fontWeight: 500 }}>· {e.name}</span>
                </span>
                <span style={{ fontSize: 11.5, color: "var(--txt-3, #8fa3ba)" }}>{ar ? e.path : (e.path_en || e.path)}</span>
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
{L("رسم توضيحيّ للمواضع — قد تختلف الألوان والترتيب قليلاً حسب تحديث المنصّة",
                      "Illustration of where to click — colours and layout may differ slightly after exchange updates")}
                </div>

                {e.pre ? (
                  <div style={{
                    marginBottom: 12, padding: "10px 13px", borderRadius: 8,
                    background: "rgba(45,212,191,0.08)",
                    border: "1px solid rgba(45,212,191,0.2)",
                    fontSize: 12.5, lineHeight: 1.85, color: "var(--brand, #2dd4bf)",
                  }}>{L("📌 قبل البدء: ", "📌 Before you start: ")}{ar ? e.pre : (e.pre_en || e.pre)}</div>
                ) : null}

                <ol style={{ margin: 0, paddingInlineStart: 0, listStyle: "none", display: "grid", gap: 9 }}>
                  {(ar ? e.steps : (e.steps_en || e.steps)).map((st, i) => (
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
                }}>⚠️ {ar ? e.warn : (e.warn_en || e.warn)}</div>

                <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)" }}>{L("عنوان الـIP المطلوب:", "Required IP address:")}</span>
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
        <div style={{ fontSize: 13.5, fontWeight: 800, marginBottom: 8 }}>{L("❓ بعد الربط", "❓ After linking")}</div>
        <div style={{ fontSize: 13, color: "var(--txt-3, #8fa3ba)", lineHeight: 2 }}>
{L("افتح صفحة التداول الآلي داخل التطبيق، الصق المفتاحين وكلمة الـPassphrase إن طلبتها منصّتك، ثم اضغط اختبار الاتصال. إن نجح الاختبار فالربط تمّ، ويبدأ النظام العمل على حسابك فوراً.",
              "Open the Auto Trading page in the app, paste both keys and the passphrase if your exchange requires one, then press test connection. If the test passes, linking is complete and the system starts working on your account right away.")}
        </div>
      </div>
    </div>
  );
}
