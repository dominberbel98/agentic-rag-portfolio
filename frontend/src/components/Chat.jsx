import React from "react";
import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { setTelemetry } from "../lib/telemetry";

const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//api.${window.location.hostname.replace(/^www\./, "")}`;
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || "";

export default function Chat() {
  const tr = useT();
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

  const send = async (event, override) => {
    event?.preventDefault();
    const raw = override ?? question;
    if (!raw.trim() || loading) return;

    const currentQuestion = raw.trim();
    setQuestion("");
    setLoading(true);
    setShowContactForm(false);
    setMessages((prev) => [...prev, { role: "user", text: currentQuestion }]);

    const recentHistory = messages.slice(-20).map((m) => ({
      role: m.role,
      content: m.text,
    }));

    const assistantIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: "assistant", text: "", meta: "" }]);

    // Measured client-side, so it is the latency the visitor actually felt —
    // retrieval, generation and network included.
    const startedAt = performance.now();
    let firstTokenAt = null;

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: currentQuestion,
          top_k: 10,
          captcha_token: captchaToken || null,
          history: recentHistory,
        }),
      });

      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = JSON.parse(line.slice(6));

          if (payload.done) {
            setShowContactForm(Boolean(payload.needs_contact_form));
            setContactEmails(payload.contact_emails || []);
            setContactLinkedin(payload.contact_linkedin || "");
          } else if (payload.token !== undefined) {
            if (firstTokenAt === null) firstTokenAt = performance.now();
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = {
                ...updated[assistantIdx],
                text: updated[assistantIdx].text + payload.token,
              };
              return updated;
            });
          }
        }
      }
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[assistantIdx] = {
          role: "assistant",
          text: updated[assistantIdx]?.text || tr.chat.connectionError,
          meta: String(error),
        };
        return updated;
      });
    } finally {
      setLoading(false);
      setTelemetry({
        lastLatencyMs: Math.round(performance.now() - startedAt),
        firstTokenMs: firstTokenAt === null ? null : Math.round(firstTokenAt - startedAt),
      });
    }
  };

  const sendContact = (event) => {
    event.preventDefault();
    const to = contactEmails.join(",");
    const subject = encodeURIComponent(tr.chat.contact.subject(contactData.name));
    const body = encodeURIComponent(
      tr.chat.contact.body(contactData.name, contactData.email, contactData.message)
    );
    window.location.href = `mailto:${to}?subject=${subject}&body=${body}`;
  };

  const handleComposerKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      composerRef.current?.requestSubmit();
    }
  };

  return (
    <div className="w-full max-w-4xl h-full max-h-full md:max-h-[700px] flex flex-col bg-surface-container-low rounded-md md:rounded-lg shadow-[0_0_30px_rgba(0,255,65,0.1)] border border-[#00FF41]/10 relative overflow-hidden">

      {/* Window header — traffic lights */}
      <div className="h-9 sm:h-10 bg-surface-container-high border-b border-[#00FF41]/15 flex items-center justify-between px-3 sm:px-4 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-error-dim shadow-[0_0_5px_rgba(255,115,81,0.5)]" />
          <div className="w-2.5 h-2.5 rounded-full bg-secondary-dim shadow-[0_0_5px_rgba(252,175,0,0.5)]" />
          <div className="w-2.5 h-2.5 rounded-full bg-primary-dim shadow-[0_0_5px_rgba(0,252,64,0.5)]" />
          <span className="ml-2 sm:ml-4 font-headline text-[0.58rem] sm:text-[0.7rem] uppercase tracking-wider sm:tracking-widest text-on-surface-variant truncate max-w-[170px] sm:max-w-none">
            {tr.chat.windowTitle}
          </span>
        </div>
        <div className={`hidden sm:block text-primary-dim font-headline text-[0.7rem] tracking-tighter ${loading ? "flicker" : ""}`}>
          {loading ? tr.chat.kernelBusy : tr.chat.kernelIdle}
        </div>
      </div>

      {/* Chat history */}
      <div
        ref={messagesRef}
        className="flex-1 overflow-y-auto p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6 font-headline text-sm scrollbar-hide bg-surface-container-lowest/40"
      >
        {/* Boot log */}
        <div className="space-y-1 hidden sm:block">
          {tr.chat.boot.map((line) => (
            <div key={line} className="text-on-surface-variant opacity-80 text-[0.65rem] font-mono">{line}</div>
          ))}
        </div>

        {/* Initial greeting — visible when no messages yet */}
        {messages.length === 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-tertiary">
              <span className="material-symbols-outlined text-sm">psychology</span>
              <span className="text-[0.65rem] font-bold tracking-widest">{tr.chat.assistant}</span>
            </div>
            <div className="bg-surface-container px-4 sm:px-5 py-3 sm:py-4 rounded-lg border-l-2 border-primary/30 max-w-[95%] sm:max-w-[90%]">
              <p className="text-on-surface leading-relaxed crt-glow">
                Hello. I am the{" "}
                <span className="text-primary font-bold">Data Science Assistant</span> for{" "}
                <span className="text-primary font-bold">Domingo Berbel</span>. I have access to
                his entire dataset: professional experience in predictive modeling, statistical
                analysis, and machine learning architectures. What insights can I extract from the
                portfolio for you today?
              </p>
            </div>

            {/* Suggested openers. A visitor arriving cold does not know what this
                thing can answer, and the logs show the same few questions asked
                over and over — so offer those. Styled as terminal commands to
                match the composer prompt below. */}
            <div className="mt-2 flex flex-col gap-1.5 max-w-[95%] sm:max-w-[90%]">
              <span className="text-[0.6rem] font-bold tracking-widest text-[#00FF41]/60">
                {tr.chat.suggestionsLabel}
              </span>
              <div className="flex flex-col gap-1.5">
                {tr.chat.suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    disabled={loading}
                    onClick={() => send(null, suggestion)}
                    className="group flex items-start gap-2 text-left px-3 py-2 border border-[#00FF41]/20 bg-[#00FF41]/[0.03] text-[0.7rem] font-headline text-[#00FF41]/75 hover:bg-[#00FF41]/10 hover:border-[#00FF41]/40 hover:text-[#00FF41] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#00FF41] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <span className="text-[#00FF41]/60 group-hover:text-[#00FF41] shrink-0">&gt;</span>
                    <span>{suggestion}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Conversation messages */}
        {messages.map((msg, idx) =>
          msg.role === "assistant" ? (
            <div key={idx} className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-tertiary">
                <span className="material-symbols-outlined text-sm">psychology</span>
                <span className="text-[0.65rem] font-bold tracking-widest">{tr.chat.assistant}</span>
              </div>
              <div className="bg-surface-container px-4 sm:px-5 py-3 sm:py-4 rounded-lg border-l-2 border-primary/30 max-w-[95%] sm:max-w-[90%]">
                <p className="text-on-surface leading-relaxed crt-glow whitespace-pre-wrap">
                  {msg.text}
                  {loading && idx === messages.length - 1 && (
                    <span className="inline-block w-2 h-4 bg-primary ml-1 cursor-blink align-middle" />
                  )}
                </p>
                {msg.meta && (
                  <small className="block mt-2 text-error text-[0.65rem]">{msg.meta}</small>
                )}
              </div>
            </div>
          ) : (
            <div key={idx} className="flex flex-col gap-2 items-end">
              <div className="flex items-center gap-2 text-secondary">
                <span className="text-[0.65rem] font-bold tracking-widest">{tr.chat.userInput}</span>
                <span className="material-symbols-outlined text-sm">person</span>
              </div>
              <div className="bg-surface-container-high px-4 sm:px-5 py-3 sm:py-4 rounded-lg border-l-2 border-secondary/40 max-w-[95%] sm:max-w-[90%]">
                <p className="text-secondary leading-relaxed whitespace-pre-wrap">{msg.text}</p>
              </div>
            </div>
          )
        )}

        {/* Standalone loading indicator (before first token arrives) */}
        {loading && messages[messages.length - 1]?.role !== "assistant" && (
          <div className="flex items-center gap-2 text-primary/60">
            <span className="material-symbols-outlined text-sm flicker">pending</span>
            <span className="text-[0.65rem] font-bold tracking-widest flicker">{tr.chat.processing}</span>
          </div>
        )}
      </div>

      {/* Terminal input */}
      <form
        onSubmit={send}
        ref={composerRef}
        className="p-3 sm:p-5 md:p-6 bg-surface-container-low border-t border-[#00FF41]/10 shrink-0"
      >
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="text-primary font-bold text-base sm:text-lg flicker">&gt;</span>
          <input
            autoFocus
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            disabled={loading}
            className="flex-1 bg-transparent border-none focus:ring-0 text-primary-dim font-headline text-base sm:text-lg placeholder:text-primary-dim/20 outline-none disabled:opacity-50"
            placeholder={tr.chat.placeholder}
            type="text"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="px-3 py-2 text-[0.65rem] sm:text-xs font-headline uppercase tracking-widest border border-[#00FF41]/35 text-primary bg-[#00FF41]/5 hover:bg-[#00FF41]/10 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {tr.chat.send}
          </button>
        </div>
        {TURNSTILE_SITE_KEY ? <div ref={turnstileRef} className="captcha-slot mt-3" /> : null}
      </form>

      {/* Contact form — shown when backend signals needs_contact_form */}
      {showContactForm && (
        <form
          onSubmit={sendContact}
          className="p-3 sm:p-6 bg-surface-container border-t border-[#00FF41]/10 space-y-3 shrink-0"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-[0.65rem] font-bold tracking-widest text-tertiary uppercase">
              {tr.chat.contact.heading}
            </p>
            <button
              type="button"
              onClick={() => setShowContactForm(false)}
              title={tr.chat.contact.dismiss}
              aria-label={tr.chat.contact.dismiss}
              className="shrink-0 w-8 h-8 flex items-center justify-center rounded text-[#00FF41]/70 hover:text-[#00FF41] hover:bg-[#00FF41]/10 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#00FF41]"
            >
              <span className="material-symbols-outlined text-[1.1rem]">close</span>
            </button>
          </div>
          {contactLinkedin && (
            <a
              href={contactLinkedin}
              target="_blank"
              rel="noreferrer"
              className="block text-primary text-sm underline"
            >
              {tr.chat.contact.viewLinkedin}
            </a>
          )}
          <input
            value={contactData.name}
            onChange={(e) => setContactData((p) => ({ ...p, name: e.target.value }))}
            placeholder={tr.chat.contact.name}
            required
            className="w-full bg-surface-container-high border border-[#00FF41]/20 text-on-surface px-4 py-2 text-sm font-headline placeholder:text-on-surface-variant/40 outline-none focus:border-primary/50"
          />
          <input
            type="email"
            value={contactData.email}
            onChange={(e) => setContactData((p) => ({ ...p, email: e.target.value }))}
            placeholder={tr.chat.contact.email}
            required
            className="w-full bg-surface-container-high border border-[#00FF41]/20 text-on-surface px-4 py-2 text-sm font-headline placeholder:text-on-surface-variant/40 outline-none focus:border-primary/50"
          />
          <textarea
            value={contactData.message}
            onChange={(e) => setContactData((p) => ({ ...p, message: e.target.value }))}
            placeholder={tr.chat.contact.message}
            rows={3}
            required
            className="w-full bg-surface-container-high border border-[#00FF41]/20 text-on-surface px-4 py-2 text-sm font-headline placeholder:text-on-surface-variant/40 outline-none focus:border-primary/50 resize-none"
          />
          <button
            type="submit"
            className="w-full border border-[#00FF41]/40 bg-[#00FF41]/5 text-primary font-headline text-sm uppercase tracking-widest py-2 hover:bg-[#00FF41]/10 transition-colors"
          >
            {tr.chat.contact.submit}
          </button>
        </form>
      )}
    </div>
  );
}
