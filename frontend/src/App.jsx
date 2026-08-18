import React, { useEffect, useMemo, useState } from "react";
import Chat from "./components/Chat";
import { useLanguage, useT } from "./i18n";
import { getTelemetry, loadBackendMeta, subscribeTelemetry } from "./lib/telemetry";
import Visualizaciones from "./components/Visualizaciones";
import ModelosPredictivos from "./components/ModelosPredictivos";
import ModelosScoring from "./components/ModelosScoring";
import ModelosRecomendacion from "./components/ModelosRecomendacion";
import Certificaciones from "./components/Certificaciones";
import Futboard from "./components/futboard/Futboard";

const MODEL_IDS = ["prediccion_la_liga", "modelo_scoring", "modelo_recomendation"];

/**
 * The navigation, built during render.
 *
 * This was a module-level `NAV_ITEMS` constant, which froze every label at
 * import time. Harmless with one language; a silent bug with two — switching to
 * Spanish would have translated the whole site except the menu.
 */
function useNavItems(tr) {
  return useMemo(
    () => [
      { id: "chat_cv", icon: "chat", label: tr.nav.chat_cv },
      { id: "visualizaciones", icon: "monitoring", label: tr.nav.visualizaciones },
      {
        id: "modelos",
        icon: "functions",
        label: tr.nav.modelos,
        children: [
          { id: "prediccion_la_liga", icon: "sports_soccer", label: tr.nav.prediccion_la_liga },
          { id: "modelo_scoring", icon: "credit_score", label: tr.nav.modelo_scoring },
          { id: "modelo_recomendation", icon: "recommend", label: tr.nav.modelo_recomendation },
        ],
      },
      { id: "certificaciones", icon: "workspace_premium", label: tr.nav.certificaciones },
      { id: "futboard", icon: "sports_soccer", label: tr.nav.futboard },
    ],
    [tr],
  );
}

function NavList({ items, activeSection, modelsOpen, onToggleModels, onSelect, hover }) {
  const baseRow = "flex items-center gap-3 px-6 py-4 cursor-pointer active:scale-95";
  const subRow  = "flex items-center gap-3 pl-12 pr-6 py-3 cursor-pointer active:scale-95 text-[0.86rem]";
  const transition = hover ? " transition-colors" : "";
  const activeCls   = "bg-[#00FF41]/10 text-[#00FF41] border-l-4 border-[#00FF41]";
  const inactiveCls = (sub) =>
    `${sub ? "text-[#00FF41]/60" : "text-[#00FF41]/65"} ${
      hover ? "hover:bg-[#00FF41]/5 hover:text-[#00FF41]" : ""
    } border-l-4 border-transparent`;

  return items.map((item) => {
    if (item.children) {
      const isActive = MODEL_IDS.includes(activeSection);
      return (
        <div key={item.id}>
          <div
            onClick={onToggleModels}
            className={`${baseRow}${transition} ${isActive ? activeCls : inactiveCls(false)}`}
          >
            <span className="material-symbols-outlined text-[1.2rem]">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            <span className={`material-symbols-outlined text-[1rem] transition-transform ${modelsOpen ? "rotate-180" : ""}`}>
              expand_more
            </span>
          </div>
          {modelsOpen && item.children.map((c) => (
            <div
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`${subRow}${transition} ${activeSection === c.id ? activeCls : inactiveCls(true)}`}
            >
              <span className="material-symbols-outlined text-[1rem]">{c.icon}</span>
              <span>{c.label}</span>
            </div>
          ))}
        </div>
      );
    }
    return (
      <div
        key={item.id}
        onClick={() => onSelect(item.id)}
        className={`${baseRow}${transition} ${activeSection === item.id ? activeCls : inactiveCls(false)}`}
      >
        <span className="material-symbols-outlined text-[1.2rem]">{item.icon}</span>
        <span>{item.label}</span>
      </div>
    );
  });
}

/**
 * The site-wide language switch.
 *
 * Both codes are always shown rather than a single "switch to X" button, so it
 * reads as a state you can see rather than an action whose result you have to
 * guess. Sized for a thumb, because on a phone it sits in the header next to the
 * hamburger.
 */
function LanguageSwitch({ language, onChange, label, compact = false }) {
  return (
    <div
      role="group"
      aria-label={label}
      className="shrink-0 flex border border-[#00FF41]/40 rounded overflow-hidden"
    >
      {["en", "es"].map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => onChange(code)}
          aria-pressed={language === code}
          className={`font-headline uppercase tracking-widest transition-colors ${
            compact ? "min-h-[36px] px-2.5 text-[0.82rem]" : "min-h-[38px] px-3 text-[0.88rem]"
          } ${
            language === code
              ? "bg-[#00FF41]/20 text-[#00FF41] font-bold drop-shadow-[0_0_6px_rgba(0,255,65,0.4)]"
              : "text-[#00FF41]/60 hover:text-[#00FF41] hover:bg-[#00FF41]/5"
          }`}
        >
          {code}
        </button>
      ))}
    </div>
  );
}

/** The explainer body, shared by the sidebar dock and the mobile sheet. */
function MascotBody({ tr, large = false }) {
  return (
    <>
      <p className={`text-[#00FF41]/75 leading-relaxed normal-case ${large ? "text-[0.92rem]" : "text-[0.84rem]"}`}>
        {tr.app.mascotLead}
      </p>
      <dl className={large ? "mt-4 space-y-3" : "mt-2.5 space-y-1.5"}>
        {tr.app.mascotSections.map((section) => (
          <div key={section.label}>
            <dt className={`text-[#00FF41]/90 font-bold tracking-wide ${large ? "text-[0.95rem]" : "text-[0.8rem]"}`}>
              {section.label}
            </dt>
            <dd className={`text-[#00FF41]/65 leading-relaxed normal-case ${large ? "text-[0.95rem]" : "text-[0.8rem]"}`}>
              {section.text}
            </dd>
          </div>
        ))}
      </dl>
    </>
  );
}

const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//api.${window.location.hostname.replace(/^www\./, "")}`;

const MASCOT_SEEN_KEY = "site.mascotSeen";

export default function App() {
  const tr = useT();
  const { language, setLanguage } = useLanguage();
  const navItems = useNavItems(tr);

  const [menuOpen, setMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("chat_cv");
  const [modelsOpen, setModelsOpen] = useState(false);
  const [telemetry, setTelemetryState] = useState(getTelemetry);
  const [mascotVisible, setMascotVisible] = useState(true);

  // On a phone there is no sidebar, so the explainer opens over the page on a
  // first visit — the one moment a visitor has no idea what they are looking at.
  // After that it is behind a header button, because being shown it twice is an
  // obstacle rather than an introduction.
  const [mascotSheetOpen, setMascotSheetOpen] = useState(() => {
    try {
      return !window.localStorage.getItem(MASCOT_SEEN_KEY);
    } catch {
      return true;
    }
  });

  const closeMascotSheet = () => {
    setMascotSheetOpen(false);
    try {
      window.localStorage.setItem(MASCOT_SEEN_KEY, "1");
    } catch {
      /* private browsing */
    }
  };

  // The footer reports what the backend actually is, so ask it once and then
  // follow the store that Chat updates after every answer.
  useEffect(() => {
    loadBackendMeta(API_URL);
    return subscribeTelemetry(setTelemetryState);
  }, []);

  useEffect(() => {
    if (MODEL_IDS.includes(activeSection)) setModelsOpen(true);
  }, [activeSection]);

  // A sheet that covers the page must not leave the page scrolling behind it.
  useEffect(() => {
    if (!mascotSheetOpen) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mascotSheetOpen]);

  return (
    <>
      {/* Scanline CRT overlay */}
      <div className="scanline-overlay" />

      {/* Matrix background */}
      <div className="matrix-bg">
        <div className="matrix-dots" />
        <div className="math-overlay">
{`∑(x-μ)²/N  y=mx+b  ∇f(x)=0  P(A|B)=P(B|A)P(A)/P(B)  ∂f/∂x  ∫e^x dx
λ=f(x,y)  σ=√Var(X)  β=(X'X)⁻¹X'y  z=(x-μ)/σ  R²=1-SSR/SST  log(p/1-p)
H₀: μ₁=μ₂  α=0.05  tanh(x)  ReLU(x)  softmax(zᵢ)=e^ᶻⁱ/∑e^ᶻʲ  E=mc²
∑(x-μ)²/N  y=mx+b  ∇f(x)=0  P(A|B)=P(B|A)P(A)/P(B)  ∂f/∂x  ∫e^x dx
λ=f(x,y)  σ=√Var(X)  β=(X'X)⁻¹X'y  z=(x-μ)/σ  R²=1-SSR/SST  log(p/1-p)`}
        </div>
      </div>

      {/* Top App Bar */}
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center gap-2 px-3 sm:px-6 h-14 sm:h-16 bg-[#0e0e0e]/80 backdrop-blur-xl border-b border-[#00FF41]/15 shadow-[0_0_15px_0_rgba(0,255,65,0.15)]">
        <div className="min-w-0 truncate text-sm sm:text-xl font-bold text-[#00FF41] drop-shadow-[0_0_8px_rgba(0,255,65,0.4)] font-headline tracking-tighter">
          {tr.app.brand}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Explainer, mobile only — the desktop sidebar has it docked. */}
          <button
            type="button"
            onClick={() => setMascotSheetOpen(true)}
            aria-label={tr.app.mascotOpen}
            title={tr.app.mascotOpen}
            className="md:hidden w-10 h-10 flex items-center justify-center rounded border border-[#00FF41]/30 text-[#00FF41] hover:bg-[#00FF41]/10 active:scale-95"
          >
            <span className="material-symbols-outlined text-[1.3rem]">smart_toy</span>
          </button>

          <LanguageSwitch
            language={language}
            onChange={setLanguage}
            label={tr.app.languageLabel}
            compact
          />

          {/* Hamburger — mobile only */}
          <button
            className="md:hidden flex flex-col gap-[5px] p-2 pointer-events-auto"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={tr.app.menuLabel}
          >
            <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "rotate-45 translate-y-[7px]" : ""}`} />
            <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "opacity-0" : ""}`} />
            <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "-rotate-45 -translate-y-[7px]" : ""}`} />
          </button>

          <nav className="hidden md:flex items-center">
            <div className="font-headline uppercase tracking-[0.25em] text-[0.95rem] text-[#00FF41] drop-shadow-[0_0_10px_rgba(0,255,65,0.6)] font-bold">
              {tr.app.owner}
            </div>
          </nav>
        </div>
      </header>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="md:hidden fixed top-14 left-0 w-full z-[45] bg-[#0e0e0e]/95 backdrop-blur-xl border-b border-[#00FF41]/15 font-headline text-[0.86rem] uppercase max-h-[calc(100vh-56px)] overflow-y-auto scrollbar-hide">
          <div className="px-4 py-3 border-b border-[#00FF41]/10">
            <div className="text-[#00FF41] font-bold">{tr.app.workspace}</div>
            <div className="text-[#00FF41]/65 tracking-widest text-[0.78rem] mt-0.5">{tr.app.session}</div>
          </div>
          <NavList
            items={navItems}
            activeSection={activeSection}
            modelsOpen={modelsOpen}
            onToggleModels={() => setModelsOpen((o) => !o)}
            onSelect={(id) => { setActiveSection(id); setMenuOpen(false); }}
            hover={false}
          />
        </div>
      )}

      {/* Tap-outside overlay to close the menu */}
      {menuOpen && (
        <div
          className="md:hidden fixed inset-0 z-[44]"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Explainer sheet — mobile only, covers the page */}
      {mascotSheetOpen && (
        <div className="md:hidden fixed inset-0 z-[70] bg-[#050505]/95 backdrop-blur-sm flex flex-col">
          <div className="flex items-center gap-3 px-4 h-14 border-b border-[#00FF41]/20 shrink-0">
            <span className="material-symbols-outlined text-[#00FF41] text-2xl mascot-bob drop-shadow-[0_0_8px_rgba(0,255,65,0.6)] shrink-0">
              smart_toy
            </span>
            <span className="mascot-antenna h-1.5 w-1.5 bg-[#00FF41] rounded-full shrink-0" />
            <h2 className="flex-1 min-w-0 truncate text-[#00FF41] font-headline font-bold text-[1rem]">
              {tr.app.mascotTitle}
            </h2>
            {/* The same switch as the header, so the explanation can be read in
                either language without leaving the sheet. It sets the site
                language, so the change survives closing it. */}
            <LanguageSwitch
              language={language}
              onChange={setLanguage}
              label={tr.app.languageLabel}
              compact
            />
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-hide px-4 py-5">
            <MascotBody tr={tr} large />
          </div>

          <div className="p-4 border-t border-[#00FF41]/20 shrink-0">
            <button
              type="button"
              onClick={closeMascotSheet}
              className="w-full min-h-[52px] border border-[#00FF41]/60 rounded bg-[#00FF41]/15 hover:bg-[#00FF41]/25 active:scale-[0.98] font-headline font-bold uppercase tracking-widest text-[0.95rem] text-[#00FF41]"
            >
              {tr.app.mascotClose}
            </button>
          </div>
        </div>
      )}

      {/* Side Nav — desktop */}
      <aside className="fixed left-0 top-16 bottom-8 hidden md:flex flex-col z-40 bg-[#0e0e0e] w-72 border-r border-[#00FF41]/15 font-headline text-[0.9rem] uppercase overflow-y-auto scrollbar-hide">
        <div className="p-6 border-b border-[#00FF41]/10">
          <div className="text-[#00FF41] font-bold text-lg">{tr.app.workspace}</div>
          <div className="text-[#00FF41]/65 tracking-widest mt-1">{tr.app.session}</div>
        </div>
        <div className="py-4 shrink-0">
          <NavList
            items={navItems}
            activeSection={activeSection}
            modelsOpen={modelsOpen}
            onToggleModels={() => setModelsOpen((o) => !o)}
            onSelect={setActiveSection}
            hover
          />
        </div>

        {/*
          Mascot, docked in the sidebar's own empty space.

          It was `fixed top-[72%] left-[20px] z-[60]` over a `z-40` sidebar that
          is `left-0 w-72`, so it drew on top of the navigation — worst on a short
          laptop screen, where 72% landed on the menu items. Moving it into the
          content area only traded one overlap for another: it then covered the
          chat composer. The sidebar has ample unused vertical space below four
          nav items, and nothing else competes for it, so it cannot overlap
          anything here at any viewport width.

          `mt-auto` parks it at the bottom when there is spare room, and the
          sidebar itself scrolls when there is not. Giving the nav its own
          scroll area instead made the two compete for a fixed height: with
          `models` expanded, the last menu entry was clipped behind the dock
          with no visible scrollbar to explain where it had gone.
        */}
        {mascotVisible && (
          <div className="mascot-dock mt-auto shrink-0 border-t border-[#00FF41]/10 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[#00FF41] text-2xl mascot-bob drop-shadow-[0_0_8px_rgba(0,255,65,0.6)] shrink-0">
                smart_toy
              </span>
              <span className="mascot-antenna h-1.5 w-1.5 bg-[#00FF41] rounded-full shrink-0" />
              <span className="text-[#00FF41] text-[0.88rem] font-bold tracking-wide normal-case">
                {tr.app.mascotTitle}
              </span>
              <button
                type="button"
                onClick={() => setMascotVisible(false)}
                aria-label={tr.app.mascotDismiss}
                title={tr.app.mascotDismiss}
                className="ml-auto w-5 h-5 flex items-center justify-center text-[#00FF41]/70 hover:text-[#00FF41] hover:bg-[#00FF41]/10 rounded shrink-0 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#00FF41]"
              >
                ✕
              </button>
            </div>

            <div className="mt-2">
              <MascotBody tr={tr} />
            </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="fixed left-0 md:left-72 top-14 sm:top-16 right-0 bottom-8 overflow-hidden flex flex-col items-center justify-center p-2 sm:p-6 md:p-8 bg-surface">
        {activeSection === "chat_cv" && <Chat />}
        {activeSection === "visualizaciones" && <Visualizaciones />}
        {activeSection === "prediccion_la_liga" && <ModelosPredictivos />}
        {activeSection === "modelo_scoring" && <ModelosScoring />}
        {activeSection === "modelo_recomendation" && <ModelosRecomendacion />}
        {activeSection === "certificaciones" && <Certificaciones />}
        {activeSection === "futboard" && <Futboard />}
        {/* Radial glow behind chat */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] z-[-2] pointer-events-none opacity-20">
          <div className="w-full h-full bg-[radial-gradient(circle_at_center,_#00FF4133_0%,_transparent_70%)]" />
        </div>
      </main>

      {/* Footer Stats */}
      <footer className="fixed bottom-0 left-0 w-full h-8 bg-surface-container border-t border-[#00FF41]/10 px-3 sm:px-6 flex items-center justify-between z-50 text-[0.72rem] sm:text-[0.74rem] font-headline uppercase text-[#00FF41]/65">
        <div className="flex gap-2 sm:gap-4">
          <span>
            {telemetry.documents == null
              ? tr.footer.indexUnknown
              : tr.footer.index(telemetry.documents)}
          </span>
          {telemetry.chatModel && (
            <span className="hidden md:inline">{tr.footer.model(telemetry.chatModel)}</span>
          )}
          {telemetry.embeddingModel && (
            <span className="hidden lg:inline">
              {tr.footer.embeddings(telemetry.embeddingModel)}
            </span>
          )}
        </div>
        <div className="flex gap-2 sm:gap-4 items-center">
          {telemetry.firstTokenMs != null && (
            <span className="hidden lg:inline">{tr.footer.firstToken(telemetry.firstTokenMs)}</span>
          )}
          {telemetry.lastLatencyMs != null && (
            <span className="hidden sm:inline">{tr.footer.latency(telemetry.lastLatencyMs)}</span>
          )}
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary flicker" />
            {tr.footer.running}
          </span>
          <span className="hidden sm:inline">{tr.footer.domain}</span>
        </div>
      </footer>
    </>
  );
}
