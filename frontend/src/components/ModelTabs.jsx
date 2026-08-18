import React from "react";

/**
 * Tab bar and headline-metric strip, shared by the scoring and recommender sections.
 *
 * Both sections used to render six panels at once, so a visitor landed on a wall
 * of charts with the interactive part fifth. They are now split into TRY IT /
 * HOW IT WORKS / EVIDENCE and only the active tab renders.
 *
 * The metric strip sits under the bar and is always visible, on purpose. Hiding
 * the evaluation behind a tab means a reader who never clicks it never learns
 * the model was validated at all — the strip keeps AUC, KS and Gini on screen
 * whichever tab is open, and the EVIDENCE tab holds the curves behind them.
 */

export function ModelTabs({ tabs, active, onChange }) {
  return (
    <div
      role="tablist"
      aria-label="Model views"
      className="flex gap-1 border-b border-[#00FF41]/20 overflow-x-auto scrollbar-hide"
    >
      {tabs.map((tab) => {
        const on = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(tab.id)}
            className={`flex flex-1 sm:flex-none items-center justify-center sm:justify-start gap-2 whitespace-nowrap px-2 sm:px-5 py-3.5 min-h-[52px] font-headline uppercase text-[0.78rem] sm:text-[0.9rem] tracking-wide sm:tracking-widest border-b-2 -mb-px transition-colors ${
              on
                ? "border-[#00FF41] text-[#00FF41] bg-[#00FF41]/10 drop-shadow-[0_0_6px_rgba(0,255,65,0.35)]"
                : "border-transparent text-[#00FF41]/55 hover:text-[#00FF41] hover:bg-[#00FF41]/5"
            }`}
          >
            <span className="material-symbols-outlined text-[1.15rem] hidden sm:inline">{tab.icon}</span>
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

/** Headline numbers that stay on screen whichever tab is open. */
export function MetricStrip({ items }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 px-1 py-3 border-b border-[#00FF41]/10">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="text-[0.68rem] font-headline uppercase tracking-widest text-[#00FF41]/65">
            {item.label}
          </span>
          <span
            className="text-[0.95rem] font-headline font-bold tabular-nums"
            style={{ color: item.color || "#00FF41" }}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export default ModelTabs;
