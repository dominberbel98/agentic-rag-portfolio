import React, { useEffect, useState } from "react";
import Chat from "./components/Chat";
import { t as tr } from "./i18n/en";
import { getTelemetry, loadBackendMeta, subscribeTelemetry } from "./lib/telemetry";
import Visualizaciones from "./components/Visualizaciones";
import ModelosPredictivos from "./components/ModelosPredictivos";
import ModelosScoring from "./components/ModelosScoring";
import ModelosRecomendacion from "./components/ModelosRecomendacion";
import Certificaciones from "./components/Certificaciones";

const NAV_ITEMS = [
  { id: "chat_cv", icon: "chat", label: tr.nav.chat_cv },
  { id: "visualizaciones", icon: "monitoring", label: tr.nav.visualizaciones },
  {
    id: "modelos",
    icon: "functions",
    label: tr.nav.modelos,
    children: [
      { id: "prediccion_la_liga",  icon: "sports_soccer", label: tr.nav.prediccion_la_liga },
      { id: "modelo_scoring",      icon: "credit_score",  label: tr.nav.modelo_scoring },
      { id: "modelo_recomendation", icon: "recommend",    label: tr.nav.modelo_recomendation },
    ],
  },
  { id: "certificaciones", icon: "workspace_premium", label: tr.nav.certificaciones },
];

const MODEL_IDS = ["prediccion_la_liga", "modelo_scoring", "modelo_recomendation"];

function NavList({ activeSection, modelsOpen, onToggleModels, onSelect, hover }) {
  const baseRow = "flex items-center gap-3 px-6 py-4 cursor-pointer active:scale-95";
  const subRow  = "flex items-center gap-3 pl-12 pr-6 py-3 cursor-pointer active:scale-95 text-[0.7rem]";
  const transition = hover ? " transition-colors" : "";
  const activeCls   = "bg-[#00FF41]/10 text-[#00FF41] border-l-4 border-[#00FF41]";
  const inactiveCls = (sub) =>
    `${sub ? "text-[#00FF41]/60" : "text-[#00FF41]/65"} ${
      hover ? "hover:bg-[#00FF41]/5 hover:text-[#00FF41]" : ""
    } border-l-4 border-transparent`;

  return NAV_ITEMS.map((item) => {
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

const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//api.${window.location.hostname.replace(/^www\./, "")}`;

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("chat_cv");
  const [modelsOpen, setModelsOpen] = useState(false);
  const [telemetry, setTelemetryState] = useState(getTelemetry);
  const [mascotVisible, setMascotVisible] = useState(true);

  // The footer reports what the backend actually is, so ask it once and then
  // follow the store that Chat updates after every answer.
  useEffect(() => {
    loadBackendMeta(API_URL);
    return subscribeTelemetry(setTelemetryState);
  }, []);

  useEffect(() => {
    if (MODEL_IDS.includes(activeSection)) setModelsOpen(true);
  }, [activeSection]);

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
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-3 sm:px-6 h-14 sm:h-16 bg-[#0e0e0e]/80 backdrop-blur-xl border-b border-[#00FF41]/15 shadow-[0_0_15px_0_rgba(0,255,65,0.15)]">
        <div className="text-sm sm:text-xl font-bold text-[#00FF41] drop-shadow-[0_0_8px_rgba(0,255,65,0.4)] font-headline tracking-tighter">
          {tr.app.brand}
        </div>
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
          <div className="font-headline uppercase tracking-[0.25em] text-[0.85rem] text-[#00FF41] drop-shadow-[0_0_10px_rgba(0,255,65,0.6)] font-bold">
            {tr.app.owner}
          </div>
        </nav>
      </header>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="md:hidden fixed top-14 left-0 w-full z-[45] bg-[#0e0e0e]/95 backdrop-blur-xl border-b border-[#00FF41]/15 font-headline text-[0.75rem] uppercase max-h-[calc(100vh-56px)] overflow-y-auto scrollbar-hide">
          <div className="px-4 py-3 border-b border-[#00FF41]/10">
            <div className="text-[#00FF41] font-bold">{tr.app.workspace}</div>
            <div className="text-[#00FF41]/65 tracking-widest text-[0.65rem] mt-0.5">{tr.app.session}</div>
          </div>
          <NavList
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

      {/* Side Nav — desktop */}
      <aside className="fixed left-0 top-16 bottom-8 hidden md:flex flex-col z-40 bg-[#0e0e0e] w-64 border-r border-[#00FF41]/15 font-headline text-[0.75rem] uppercase">
        <div className="p-6 border-b border-[#00FF41]/10">
          <div className="text-[#00FF41] font-bold text-lg">{tr.app.workspace}</div>
          <div className="text-[#00FF41]/65 tracking-widest mt-1">{tr.app.session}</div>
        </div>
        <div className="flex-1 py-4 overflow-y-auto scrollbar-hide">
          <NavList
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
          is `left-0 w-64`, so it drew on top of the navigation — worst on a short
          laptop screen, where 72% landed on the menu items. Moving it into the
          content area only traded one overlap for another: it then covered the
          chat composer. The sidebar has ample unused vertical space below four
          nav items, and nothing else competes for it, so it cannot overlap
          anything here at any viewport width.
        */}
        {mascotVisible && (
          <div className="mascot-dock shrink-0 border-t border-[#00FF41]/10 px-4 py-3 overflow-y-auto scrollbar-hide">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[#00FF41] text-2xl mascot-bob drop-shadow-[0_0_8px_rgba(0,255,65,0.6)] shrink-0">
                smart_toy
              </span>
              <span className="mascot-antenna h-1.5 w-1.5 bg-[#00FF41] rounded-full shrink-0" />
              <span className="text-[#00FF41] text-[0.7rem] font-bold tracking-wide normal-case">
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

            <p className="mt-2 text-[#00FF41]/75 text-[0.63rem] leading-snug normal-case">
              {tr.app.mascotLead}
            </p>

            <dl className="mt-2.5 space-y-1.5">
              {tr.app.mascotSections.map((section) => (
                <div key={section.label}>
                  <dt className="text-[#00FF41]/90 text-[0.6rem] font-bold tracking-wide">
                    {section.label}
                  </dt>
                  <dd className="text-[#00FF41]/65 text-[0.6rem] leading-snug normal-case">
                    {section.text}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="fixed md:left-64 top-14 sm:top-16 right-0 bottom-8 overflow-hidden flex flex-col items-center justify-center p-2 sm:p-6 md:p-8 bg-surface">
        {activeSection === "chat_cv" && <Chat />}
        {activeSection === "visualizaciones" && <Visualizaciones />}
        {activeSection === "prediccion_la_liga" && <ModelosPredictivos />}
        {activeSection === "modelo_scoring" && <ModelosScoring />}
        {activeSection === "modelo_recomendation" && <ModelosRecomendacion />}
        {activeSection === "certificaciones" && <Certificaciones />}
        {/* Radial glow behind chat */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] z-[-2] pointer-events-none opacity-20">
          <div className="w-full h-full bg-[radial-gradient(circle_at_center,_#00FF4133_0%,_transparent_70%)]" />
        </div>
      </main>

      {/* Footer Stats */}
      <footer className="fixed bottom-0 left-0 w-full h-8 bg-surface-container border-t border-[#00FF41]/10 px-3 sm:px-6 flex items-center justify-between z-50 text-[0.55rem] sm:text-[0.6rem] font-headline uppercase text-[#00FF41]/65">
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
