import React, { useState } from "react";
import Chat from "./components/Chat";

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);

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
          NEURAL_LINK_DS_V1.0
        </div>
        {/* Hamburger — solo móvil */}
        <button
          className="md:hidden flex flex-col gap-[5px] p-2 pointer-events-auto"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Menú"
        >
          <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "rotate-45 translate-y-[7px]" : ""}`} />
          <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "opacity-0" : ""}`} />
          <span className={`block w-5 h-[2px] bg-[#00FF41] transition-all duration-200 ${menuOpen ? "-rotate-45 -translate-y-[7px]" : ""}`} />
        </button>
        <nav className="hidden md:flex items-center">
          <div className="font-headline uppercase tracking-[0.25em] text-[0.85rem] text-[#00FF41] drop-shadow-[0_0_10px_rgba(0,255,65,0.6)] font-bold">
            DOMINGO BERBEL
          </div>
        </nav>
      </header>

      {/* Menú móvil desplegable */}
      {menuOpen && (
        <div className="md:hidden fixed top-14 left-0 w-full z-[45] bg-[#0e0e0e]/95 backdrop-blur-xl border-b border-[#00FF41]/15 font-headline text-[0.75rem] uppercase">
          <div className="px-4 py-3 border-b border-[#00FF41]/10">
            <div className="text-[#00FF41] font-bold">DS_WORKSPACE</div>
            <div className="text-[#00FF41]/40 tracking-widest text-[0.65rem] mt-0.5">SESSION: DATA_EXPLORER</div>
          </div>
          {[
            { icon: "chat", label: "chat_cv", active: true },
            { icon: "monitoring", label: "visualizaciones" },
            { icon: "functions", label: "modelos_predictivos" },
            { icon: "workspace_premium", label: "certificaciones" },
          ].map(({ icon, label, active }) => (
            <div
              key={label}
              onClick={() => setMenuOpen(false)}
              className={`flex items-center gap-3 px-6 py-4 cursor-pointer active:scale-95 ${
                active
                  ? "bg-[#00FF41]/10 text-[#00FF41] border-l-4 border-[#00FF41]"
                  : "text-[#00FF41]/40 border-l-4 border-transparent"
              }`}
            >
              <span className="material-symbols-outlined text-[1.2rem]">{icon}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Overlay para cerrar menú tocando fuera */}
      {menuOpen && (
        <div
          className="md:hidden fixed inset-0 z-[44]"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Side Nav — desktop */}
      <aside className="fixed left-0 top-16 h-[calc(100vh-64px)] hidden md:flex flex-col z-40 bg-[#0e0e0e] w-64 border-r border-[#00FF41]/15 font-headline text-[0.75rem] uppercase">
        <div className="p-6 border-b border-[#00FF41]/10">
          <div className="text-[#00FF41] font-bold text-lg">DS_WORKSPACE</div>
          <div className="text-[#00FF41]/40 tracking-widest mt-1">SESSION: DATA_EXPLORER</div>
        </div>
        <div className="flex-1 py-4">
          <div className="flex items-center gap-3 px-6 py-4 bg-[#00FF41]/10 text-[#00FF41] border-l-4 border-[#00FF41] cursor-pointer active:scale-95">
            <span className="material-symbols-outlined text-[1.2rem]">chat</span>
            <span>chat_cv</span>
          </div>
          <div className="flex items-center gap-3 px-6 py-4 text-[#00FF41]/40 hover:bg-[#00FF41]/5 hover:text-[#00FF41] cursor-pointer active:scale-95">
            <span className="material-symbols-outlined text-[1.2rem]">monitoring</span>
            <span>visualizaciones</span>
          </div>
          <div className="flex items-center gap-3 px-6 py-4 text-[#00FF41]/40 hover:bg-[#00FF41]/5 hover:text-[#00FF41] cursor-pointer active:scale-95">
            <span className="material-symbols-outlined text-[1.2rem]">functions</span>
            <span>modelos_predictivos</span>
          </div>
          <div className="flex items-center gap-3 px-6 py-4 text-[#00FF41]/40 hover:bg-[#00FF41]/5 hover:text-[#00FF41] cursor-pointer active:scale-95">
            <span className="material-symbols-outlined text-[1.2rem]">workspace_premium</span>
            <span>certificaciones</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="fixed md:left-64 top-14 sm:top-16 right-0 bottom-8 overflow-hidden flex flex-col items-center justify-center p-2 sm:p-6 md:p-8 bg-surface">
        <Chat />
        {/* Radial glow behind chat */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] z-[-2] pointer-events-none opacity-20">
          <div className="w-full h-full bg-[radial-gradient(circle_at_center,_#00FF4133_0%,_transparent_70%)]" />
        </div>
      </main>

      {/* Footer Stats */}
      <footer className="fixed bottom-0 left-0 w-full h-8 bg-surface-container border-t border-[#00FF41]/10 px-3 sm:px-6 flex items-center justify-between z-50 text-[0.55rem] sm:text-[0.6rem] font-headline uppercase text-[#00FF41]/40">
        <div className="flex gap-2 sm:gap-4">
          <span>TRAINING_SET: 100%</span>
          <span className="hidden md:inline">OPTIMIZER: ADAM</span>
          <span className="hidden sm:inline">LEARNING_RATE: 0.001</span>
        </div>
        <div className="flex gap-2 sm:gap-4 items-center">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary flicker" />
            RUNNING_INFERENCE
          </span>
          <span className="hidden sm:inline">domingoberbel.com</span>
        </div>
      </footer>

      {/* Mascota — desktop: lateral izquierdo | móvil: esquina inferior izquierda */}
      {/* Desktop */}
      <div className="fixed top-[72%] left-[20px] z-[60] hidden md:flex items-end gap-4 pointer-events-none -translate-y-1/2">
        <div className="flex flex-col items-start gap-2">
          <div className="bg-[#00FF41]/10 border border-[#00FF41]/30 p-3 rounded-lg backdrop-blur-md max-w-[220px] shadow-[0_0_15px_rgba(0,255,65,0.1)]">
            <p className="text-[#00FF41] text-[0.7rem] font-headline uppercase leading-tight">
              Hola! Prueba a hacerle una pregunta al asistente de IA. Las opciones de visualizaciones, modelos_predictivos y certificados aún están en construcción
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#00FF41] text-4xl flicker drop-shadow-[0_0_8px_rgba(0,255,65,0.6)]">smart_toy</span>
            <div className="h-2 w-2 bg-[#00FF41] rounded-full animate-pulse" />
          </div>
        </div>
      </div>

    </>
  );
}
