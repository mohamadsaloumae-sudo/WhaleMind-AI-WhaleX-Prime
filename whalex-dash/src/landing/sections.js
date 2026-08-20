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
  { id: "faq", Component: FAQ, enabled: true },
  { id: "social", Component: Social, enabled: true },
  { id: "legal", Component: Legal, enabled: true },
];

/** 🎨 الهوية البصرية — تعديل هنا يُغيّر كل الأقسام */
export const T = {
  bg: "#080c16",
  card: "rgba(255,255,255,.035)",
  border: "rgba(255,255,255,.08)",
  brand: "#2dd4bf",
  brand2: "#22c55e",
  gold: "#fbbf24",
  red: "#f87171",
  txt: "#ffffff",
  txt2: "#a8b3c4",
  txt3: "#6b7688",
};
