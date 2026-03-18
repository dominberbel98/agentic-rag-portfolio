import React from "react";
import { useEffect, useRef, useState } from "react";

const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//api.${window.location.hostname.replace(/^www\./, "")}`;
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || "";

export default function Chat() {
  const [question, setQuestion] = useState("");

  // Warm-up: ping backend on mount so cold-start resolves while user reads
  useEffect(() => {
    fetch(`${API_URL}/health`).catch(() => {});
  }, []);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactEmails, setContactEmails] = useState([]);
  const [contactLinkedin, setContactLinkedin] = useState("");
  const [contactData, setContactData] = useState({ name: "", email: "", message: "" });
  const turnstileRef = useRef(null);
  const messagesRef = useRef(null);
  const composerRef = useRef(null);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !turnstileRef.current) return;

    const renderTurnstile = () => {
      if (!window.turnstile || !turnstileRef.current) return;
      window.turnstile.render(turnstileRef.current, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (token) => setCaptchaToken(token),
      });
    };

    if (window.turnstile) {
      renderTurnstile();
      return;
    }

    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    script.async = true;
    script.defer = true;
    script.onload = renderTurnstile;
    document.body.appendChild(script);

    return () => {
      script.onload = null;
    };
  }, []);

  useEffect(() => {
    if (!messagesRef.current) return;
    messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [messages, loading]);

  const send = async (event) => {
    event.preventDefault();
    if (!question.trim() || loading) return;

    const currentQuestion = question.trim();
    setQuestion("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: currentQuestion }]);

    // Build conversation history from last 20 messages (10 full turns) to give
    // the backend stronger context for follow-up questions.
    const recentHistory = messages.slice(-20).map((m) => ({
      role: m.role,
      content: m.text,
    }));

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: currentQuestion,
          top_k: 5,
          captcha_token: captchaToken || null,
          history: recentHistory,
        }),
      });

      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }

      const data = await response.json();
      setShowContactForm(Boolean(data.needs_contact_form));
      setContactEmails(data.contact_emails || []);
      setContactLinkedin(data.contact_linkedin || "");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer,
          meta: "",
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "No se pudo conectar con el backend.",
          meta: String(error),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendContact = (event) => {
    event.preventDefault();
    const to = contactEmails.join(",");
    const subject = encodeURIComponent(`Contacto recruiter - ${contactData.name}`);
    const body = encodeURIComponent(
      `Nombre: ${contactData.name}\nEmail: ${contactData.email}\n\nMensaje:\n${contactData.message}`
    );
    window.location.href = `mailto:${to}?subject=${subject}&body=${body}`;
  };

  const handleComposerKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      composerRef.current?.requestSubmit();
    }
  };

  return (
    <div className="chat-wrap">
      <div className="messages" ref={messagesRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <p className="empty-title">Explora el perfil de Domingo</p>
            <p className="empty">
              Prueba con preguntas como: "¿Qué experiencia tiene en Data Science?", "¿Qué puede aportar a una
              empresa?" o "¿Qué proyectos destacan más?"
            </p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <article key={idx} className={`msg ${msg.role}`}>
            <p>{msg.text}</p>
            {msg.meta && <small>{msg.meta}</small>}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={send} ref={composerRef}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleComposerKeyDown}
          placeholder="Escribe una pregunta sobre trayectoria, logros, proyectos o habilidades..."
          rows={3}
        />
        {TURNSTILE_SITE_KEY ? <div ref={turnstileRef} className="captcha-slot" /> : null}
        <button type="submit" disabled={loading}>
          {loading ? "Generando respuesta..." : "Enviar"}
        </button>
      </form>

      {showContactForm && (
        <form className="composer" onSubmit={sendContact}>
          <h3>Contacto</h3>
          {contactLinkedin && (
            <a href={contactLinkedin} target="_blank" rel="noreferrer">
              Ver perfil de LinkedIn
            </a>
          )}
          <input
            value={contactData.name}
            onChange={(e) => setContactData((p) => ({ ...p, name: e.target.value }))}
            placeholder="Tu nombre"
            required
          />
          <input
            type="email"
            value={contactData.email}
            onChange={(e) => setContactData((p) => ({ ...p, email: e.target.value }))}
            placeholder="Tu email"
            required
          />
          <textarea
            value={contactData.message}
            onChange={(e) => setContactData((p) => ({ ...p, message: e.target.value }))}
            placeholder="Cuéntame brevemente la oportunidad o necesidad"
            rows={4}
            required
          />
          <button type="submit">Enviar contacto</button>
        </form>
      )}
    </div>
  );
}
