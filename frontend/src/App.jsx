import React from "react";
import Chat from "./components/Chat";

export default function App() {
  return (
    <main className="page">
      <section className="crt-shell">
        <aside className="profile-pane">
          <div className="profile-head">
            <p className="eyebrow">Domingo Berbel</p>
            <h1>Data Scientist: de datos a acciones.</h1>
            <p className="subtitle">
              Perfil técnico con visión de negocio, y capacidad para convertir datos en decisiones, automatización
              y resultados.
            </p>
          </div>

          <div className="portrait-frame">
            <img src="/foto.png" alt="Domingo Berbel" className="portrait" />
            <div className="portrait-glow" aria-hidden="true" />
          </div>

          <div className="signal-card">
            <p className="signal-title">Por qué destaca</p>
            <ul className="signal-list">
              <li>Combina Data Science, automatización y delivery en producción.</li>
              <li>Traduce problemas de negocio en soluciones técnicas útiles.</li>
              <li>Se comunica con perfiles técnicos y no técnicos.</li>
            </ul>
          </div>
        </aside>

        <section className="chat-pane">
          <header className="chat-header">
            <div>
              <p className="eyebrow">www.domingoberbel.com</p>
              <h2>Pregúntame por experiencia, proyectos, skills o encaje profesional</h2>
            </div>
            <div className="status-pill">Disponible ES / EN</div>
          </header>
          <Chat />
        </section>
      </section>
    </main>
  );
}
