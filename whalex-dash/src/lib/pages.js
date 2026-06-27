// ════════════════════════════════════════════════════════════
//  سجلّ الصفحات المركزي (Page Registry)
//  ─────────────────────────────────────────────────────────────
//  لإضافة صفحة جديدة: 1) أنشئ ملفّها في src/pages/
//                     2) أضف سطراً واحداً هنا
//  لا شيء آخر. الـ routing والقائمة الجانبية يُبنيان تلقائياً.
// ════════════════════════════════════════════════════════════
import {
  LayoutDashboard, Radio, Bot, TrendingUp,
  CreditCard, Settings, Search, Shield, BarChart3,
} from "lucide-react";

import Dashboard from "../pages/Dashboard.jsx";
import Signals from "../pages/Signals.jsx";
import AutoTrade from "../pages/AutoTrade.jsx";
import Trades from "../pages/Trades.jsx";
import Subscription from "../pages/Subscription.jsx";
import SettingsPage from "../pages/Settings.jsx";
import Scanner from "../pages/Scanner.jsx";
import Positions from "../pages/Positions.jsx";
import Admin from "../pages/Admin.jsx";

// كل عنصر: { path, label, icon, component, adminOnly?, hideNav? }
export const PAGES = [
  { path: "/",             label: "الرئيسية",        icon: LayoutDashboard, component: Dashboard },
  { path: "/signals",      label: "الإشارات الحيّة",  icon: Radio,           component: Signals },
  { path: "/positions",    label: "الصفقات",         icon: BarChart3,       component: Positions },
  { path: "/auto-trade",   label: "التداول",         icon: Bot,             component: AutoTrade },
  { path: "/trades",       label: "صفقاتي",          icon: TrendingUp,      component: Trades },
  { path: "/scanner",      label: "فاحص العملات",     icon: Search,          component: Scanner },
  { path: "/subscription", label: "الاشتراك",        icon: CreditCard,      component: Subscription },
  { path: "/settings",     label: "الإعدادات",       icon: Settings,        component: SettingsPage },
  { path: "/admin",        label: "لوحة الإدارة",     icon: Shield,          component: Admin, adminOnly: true },
];
