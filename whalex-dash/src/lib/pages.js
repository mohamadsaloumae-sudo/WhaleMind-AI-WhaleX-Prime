// ════════════════════════════════════════════════════════════
//  سجلّ الصفحات المركزي (Page Registry)
//  ─────────────────────────────────────────────────────────────
//  لإضافة صفحة جديدة: 1) أنشئ ملفّها في src/pages/
//                     2) أضف سطراً واحداً هنا
//  لا شيء آخر. الـ routing والقائمة الجانبية يُبنيان تلقائياً.
// ════════════════════════════════════════════════════════════
// 📦 تحميل كسول — كل صفحة ملف يُجلَب عند فتحها فقط.
//    كانت الأربع عشرة تُحمَّل كلّها في الفتح الأول.
import { lazy } from "react";
import {
  LayoutDashboard, Radio, Bot, TrendingUp,
  CreditCard, Settings, Search, Shield, BarChart3, Activity, MessageCircle, Sparkles, Gift, UserCircle,
} from "lucide-react";


const Dashboard = lazy(() => import("../pages/Dashboard.jsx"));
const Signals = lazy(() => import("../pages/Signals.jsx"));
const AutoTrade = lazy(() => import("../pages/AutoTrade.jsx"));
const Trades = lazy(() => import("../pages/Trades.jsx"));
const Subscription = lazy(() => import("../pages/Subscription.jsx"));
const SettingsPage = lazy(() => import("../pages/Settings.jsx"));
const Scanner = lazy(() => import("../pages/Scanner.jsx"));
const Positions = lazy(() => import("../pages/Positions.jsx"));
const LivePositions = lazy(() => import("../pages/LivePositions.jsx"));
const Admin = lazy(() => import("../pages/Admin.jsx"));
const Support = lazy(() => import("../pages/Support.jsx"));
const Landing = lazy(() => import("../pages/Landing.jsx"));
const Referral = lazy(() => import("../pages/Referral.jsx"));
const Profile = lazy(() => import("../pages/Profile.jsx"));

// كل عنصر: { path, label, icon, component, adminOnly?, hideNav? }
export const PAGES = [
  { path: "/",             label: "الرئيسية",        icon: LayoutDashboard, component: Dashboard },
  { path: "/signals",      label: "الإشارات الحيّة",  icon: Radio,           component: Signals },
  { path: "/live",         label: "الصفقات المفتوحة", icon: Activity,        component: LivePositions },
  { path: "/positions",    label: "الصفقات",         icon: BarChart3,       component: Positions },
  { path: "/auto-trade",   label: "التداول",         icon: Bot,             component: AutoTrade },
  { path: "/trades",       label: "صفقاتي",          icon: TrendingUp,      component: Trades },
  { path: "/scanner",      label: "فاحص العملات",     icon: Search,          component: Scanner },
  { path: "/subscription", label: "الاشتراك",        icon: CreditCard,      component: Subscription },
  { path: "/settings",     label: "الإعدادات",       icon: Settings,        component: SettingsPage },
  { path: "/landing",      label: "عن المنصّة",       icon: Sparkles,        component: Landing },
  { path: "/profile",      label: "حسابي",           icon: UserCircle,      component: Profile },
  { path: "/referral",     label: "برنامج الإحالة",   icon: Gift,            component: Referral },
  { path: "/support",      label: "خدمة العملاء",    icon: MessageCircle,   component: Support },
  { path: "/admin",        label: "لوحة الإدارة",     icon: Shield,          component: Admin, adminOnly: true },
];
