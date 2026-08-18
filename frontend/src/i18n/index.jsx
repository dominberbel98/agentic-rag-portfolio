import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import en from "./en";
import es from "./es";

/**
 * One language for the whole site.
 *
 * Still no i18n library. Two languages and a flat dictionary do not justify one,
 * and the tests that keep the trees honest live in Python next to the rest of
 * the frontend guards.
 *
 * The important consequence of doing it this way: **the dictionary must be read
 * during render, not at import time.** Several components used to capture it in
 * a module-level constant — `NAV_ITEMS`, `SLIDER_FIELDS`, the tab arrays,
 * `const L = tr.laliga` — which was harmless while there was one language and
 * silently unfixable once there were two, because the labels would freeze at
 * whatever was loaded first. Those all moved inside their components.
 *
 * English is the default on a first visit regardless of browser locale: it is
 * what a recruiter sees, and the corpus the assistant answers from is English.
 * The choice is one tap and is remembered.
 */

const DICTIONARIES = { en, es };
export const LANGUAGES = Object.keys(DICTIONARIES);
const STORAGE_KEY = "site.language";

const LanguageContext = createContext(null);

function initialLanguage() {
  if (typeof window === "undefined") return "en";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (LANGUAGES.includes(stored)) return stored;
  } catch {
    /* private browsing */
  }
  return "en";
}

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(initialLanguage);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, language);
    } catch {
      /* private browsing: the choice just will not persist */
    }
    // Assistive technology and the browser both care; the page is one document
    // whose language genuinely changes.
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      toggle: () => setLanguage((current) => (current === "en" ? "es" : "en")),
      t: DICTIONARIES[language],
    }),
    [language],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

function useLanguageContext() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useT must be used inside <LanguageProvider>");
  }
  return context;
}

/** The active dictionary. Call inside a component, never at module scope. */
export function useT() {
  return useLanguageContext().t;
}

/** The active language code plus the setters, for the toggle itself. */
export function useLanguage() {
  const { language, setLanguage, toggle } = useLanguageContext();
  const select = useCallback((code) => setLanguage(code), [setLanguage]);
  return { language, setLanguage: select, toggle };
}

export { en, es };
