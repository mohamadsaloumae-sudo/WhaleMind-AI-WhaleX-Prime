/**
 * 📋 ترتيب أقسام المقدّمة
 * إضافة قسم: ملف + سطر هنا. إخفاؤه: enabled: false. ترتيبه: حرّك السطر.
 */
import Hero from "./Hero.jsx";
import LiveShowcase from "./LiveShowcase.jsx";
import LiveStats from "./LiveStats.jsx";
import WhyDifferent from "./WhyDifferent.jsx";
import HowItWorks from "./HowItWorks.jsx";
import Exchanges from "./Exchanges.jsx";
import Security from "./Security.jsx";
import Pricing from "./Pricing.jsx";
import ReferralBox from "./ReferralBox.jsx";
import FAQ from "./FAQ.jsx";
import Social from "./Social.jsx";
import Legal from "./Legal.jsx";

export const SECTIONS = [
  { id: "hero", Component: Hero, enabled: true },
  { id: "showcase", Component: LiveShowcase, enabled: true },
  { id: "stats", Component: LiveStats, enabled: true },
  { id: "why", Component: WhyDifferent, enabled: true },
  { id: "how", Component: HowItWorks, enabled: true },
  { id: "exchanges", Component: Exchanges, enabled: true },
  { id: "security", Component: Security, enabled: true },
  { id: "pricing", Component: Pricing, enabled: true },
  { id: "referral", Component: ReferralBox, enabled: true },
  { id: "faq", Component: FAQ, enabled: true },
  { id: "social", Component: Social, enabled: true },
  { id: "legal", Component: Legal, enabled: true },
];

/** 🎨 الهوية البصرية — تعديل هنا يُغيّر كل الأقسام */
// 🎨 نفس هوية التطبيق — القيم من tokens.css حرفياً
export const T = {
  bg: "#0a0e1a",        // --bg-0
  card: "#111726",      // --bg-1
  border: "#232d44",    // --bg-3
  brand: "#2dd4bf",     // --brand
  brand2: "#22c55e",    // --green
  gold: "#f59e0b",      // --amber
  red: "#ef4444",       // --red
  txt: "#e8edf7",       // --txt-1
  txt2: "#9aa6be",      // --txt-2
  txt3: "#5c6880",      // --txt-3
};
