import { createContext, useContext, useEffect, useState } from "react";
import { subscription } from "../lib/api.js";

/**
 * 🎁 حالة الاشتراك — مشترك · مجرّب · مجاني.
 *
 * لماذا نُخفي التفاصيل عن المجرّب:
 *   بلا ذلك يأخذ الأسبوع، ينسخ الإشارات وينفّذها يدوياً، ثم يمضي.
 *   فالمجرّب يرى النظام يعمل على حسابه — لا يرى ما يُنسَخ.
 */
const Ctx = createContext({ paid: false, trial: false, ready: false });

export function TierProvider({ children }) {
  const [s, setS] = useState({ paid: false, trial: false, ready: false });

  useEffect(() => {
    let dead = false;
    (async () => {
      try {
        const r = await subscription.status();
        if (dead) return;
        const plan = String(r?.plan || "").toLowerCase();
        setS({
          paid: !!r?.is_active && plan !== "trial",
          trial: !!r?.is_active && plan === "trial",
          ready: true,
        });
      } catch {
        if (!dead) setS({ paid: false, trial: false, ready: true });
      }
    })();
    return () => { dead = true; };
  }, []);

  return <Ctx.Provider value={s}>{children}</Ctx.Provider>;
}

export function useTier() {
  return useContext(Ctx);
}
