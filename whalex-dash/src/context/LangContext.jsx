// ════════════════════════════════════════════════════════════
//  سياق اللغة (Language Context)
//  يدير اللغة الحالية (ar/en) والاتّجاه (rtl/ltr).
// ════════════════════════════════════════════════════════════
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { TRANSLATIONS } from "../lib/i18n.js";

const LangCtx = createContext(null);
const LANG_KEY = "whalex_lang";

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem(LANG_KEY) || "ar");

  // نطبّق اللغة والاتّجاه على <html>
  useEffect(() => {
    const dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    localStorage.setItem(LANG_KEY, lang);
  }, [lang]);

  const t = useCallback(
    (key) => TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.ar[key] ?? key,
    [lang]
  );

  const toggle = useCallback(() => {
    setLang((l) => (l === "ar" ? "en" : "ar"));
  }, []);

  return (
    <LangCtx.Provider value={{ lang, dir: lang === "ar" ? "rtl" : "ltr", t, toggle, setLang }}>
      {children}
    </LangCtx.Provider>
  );
}

export function useLang() {
  return useContext(LangCtx);
}
