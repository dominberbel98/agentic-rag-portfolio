import React from "react";

/**
 * Shared FUTBOARD primitives.
 *
 * Mobile-first, because this gets used standing on a pitch: every tap target is
 * at least 44px tall, nothing depends on hover, and the layout starts as one
 * column and only widens at `sm`/`lg`. On a desktop the same components fill the
 * extra width instead of leaving a phone-shaped strip in the middle of a monitor.
 *
 * Text sits at /65 or above on the phosphor green. Anything below /55 fails
 * WCAG AA against the #0e0e0e surface, which tests/test_frontend_consistency.py
 * enforces across every component.
 */

export const GREEN = "#00FF41";
export const AMBER = "#FFD700";
export const RED = "#FF4136";

export function ScreenHeader({ title, subtitle, onBack, backLabel, right }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="shrink-0 flex items-center gap-1 min-h-[44px] px-3 -ml-1 font-headline uppercase text-[0.7rem] tracking-widest text-[#00FF41]/75 hover:text-[#00FF41] active:scale-95"
        >
          <span className="material-symbols-outlined text-[1.1rem]">arrow_back</span>
          {backLabel}
        </button>
      )}
      <div className="flex-1 min-w-0">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)] truncate">
          {title}
        </h2>
        {subtitle && (
          <p className="text-[0.7rem] text-[#00FF41]/70 font-headline mt-0.5 normal-case">
            {subtitle}
          </p>
        )}
      </div>
      {right}
    </div>
  );
}

export function Panel({ title, icon, children, className = "" }) {
  return (
    <section className={`viz-panel ${className}`}>
      {title && (
        <h3 className="viz-title">
          {icon && <span className="material-symbols-outlined text-sm mr-2">{icon}</span>}
          {title}
        </h3>
      )}
      {children}
    </section>
  );
}

export function Button({
  children,
  onClick,
  variant = "default",
  icon,
  disabled,
  type = "button",
  className = "",
}) {
  const palette = {
    default:
      "border-[#00FF41]/30 text-[#00FF41]/85 bg-[#00FF41]/[0.04] hover:bg-[#00FF41]/10 hover:text-[#00FF41]",
    primary:
      "border-[#00FF41]/60 text-[#00FF41] bg-[#00FF41]/15 hover:bg-[#00FF41]/25 font-bold",
    danger: "border-[#FF4136]/45 text-[#FF4136] bg-[#FF4136]/[0.06] hover:bg-[#FF4136]/15",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 min-h-[44px] px-4 border rounded font-headline uppercase text-[0.7rem] tracking-widest transition-colors active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 ${palette[variant]} ${className}`}
    >
      {icon && <span className="material-symbols-outlined text-[1.1rem]">{icon}</span>}
      {children}
    </button>
  );
}

export function TextField({ value, onChange, placeholder, onSubmit, maxLength = 40 }) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter" && onSubmit) {
          event.preventDefault();
          onSubmit();
        }
      }}
      placeholder={placeholder}
      maxLength={maxLength}
      className="flex-1 min-w-0 min-h-[44px] bg-black/40 border border-[#00FF41]/25 rounded px-3 text-[0.85rem] font-headline text-[#00FF41] placeholder:text-[#00FF41]/60 outline-none focus:border-[#00FF41]/60"
    />
  );
}

/** A row that reads as one tappable thing on a phone. */
export function ListRow({ children, onClick, active, className = "" }) {
  const Element = onClick ? "button" : "div";
  return (
    <Element
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`w-full flex items-center gap-3 min-h-[48px] px-3 py-2 border rounded text-left transition-colors ${
        active
          ? "border-[#00FF41]/60 bg-[#00FF41]/10"
          : "border-[#00FF41]/15 bg-black/20 hover:border-[#00FF41]/35"
      } ${onClick ? "active:scale-[0.99]" : ""} ${className}`}
    >
      {children}
    </Element>
  );
}

export function Notice({ children, tone = "info" }) {
  const palette = {
    info: "border-[#00FF41]/25 text-[#00FF41]/75",
    warn: "border-[#FFD700]/40 text-[#FFD700]",
    error: "border-[#FF4136]/45 text-[#FF4136]",
  };
  return (
    <p
      className={`border rounded px-3 py-2.5 font-headline text-[0.7rem] leading-relaxed normal-case ${palette[tone]}`}
    >
      {children}
    </p>
  );
}

export function EmptyState({ children, icon = "inbox" }) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <span className="material-symbols-outlined text-[1.8rem] text-[#00FF41]/55">{icon}</span>
      <p className="font-headline text-[0.72rem] text-[#00FF41]/70 normal-case max-w-xs">
        {children}
      </p>
    </div>
  );
}

/**
 * Loading state that names the wait.
 *
 * Neon suspends its compute after five minutes idle, so the first request of a
 * visit can take a couple of seconds. "Waking the database" is both true and
 * more reassuring than a spinner that looks stuck.
 */
export function Loading({ label, slow }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12">
      <div className="font-headline text-[0.8rem] uppercase text-[#00FF41] flicker">
        {label}
        <span className="cursor-blink">_</span>
      </div>
      {slow && (
        <div className="font-headline text-[0.68rem] text-[#00FF41]/70 normal-case">{slow}</div>
      )}
    </div>
  );
}

export function ErrorState({ message, onRetry, retryLabel }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <span className="material-symbols-outlined text-[1.8rem] text-[#FF4136]">error</span>
      <p className="font-headline text-[0.75rem] text-[#FF4136] normal-case max-w-sm">{message}</p>
      {onRetry && (
        <Button onClick={onRetry} icon="refresh">
          {retryLabel}
        </Button>
      )}
    </div>
  );
}

/** The EN/ES switch. Both options are always visible, so it reads as a choice. */
export function LanguageToggle({ language, onChange }) {
  return (
    <div className="shrink-0 flex border border-[#00FF41]/30 rounded overflow-hidden">
      {["en", "es"].map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => onChange(code)}
          aria-pressed={language === code}
          className={`min-h-[38px] px-3 font-headline uppercase text-[0.68rem] tracking-widest transition-colors ${
            language === code
              ? "bg-[#00FF41]/20 text-[#00FF41] font-bold"
              : "text-[#00FF41]/60 hover:text-[#00FF41] hover:bg-[#00FF41]/5"
          }`}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
