/**
 * Shared La Liga presentation constants.
 *
 * The zone boundaries and their colours were previously duplicated across
 * Visualizaciones.jsx and ModelosPredictivos.jsx, and again in two Python
 * scripts. They disagreed, which is how the Conference League zone went missing
 * without anyone noticing: seventh place was painted as mid-table and the legend
 * only listed three tiers.
 *
 * These must stay in step with scripts/laliga_transform.py.
 */

export const ZONE_COLORS = {
  champions: "#00FF41", // phosphor green — the site's primary
  europa: "#00BFFF", // cyan
  conference: "#B24BF3", // violet: distinct from green/cyan/red at CRT brightness
  mid: "rgba(0,255,65,0.25)",
  relegation: "#FF4136",
};

/** Zones shown in the legend, in table order. `mid` is deliberately absent —
 * it is the absence of a zone, not a zone. */
export const LEGEND_ZONES = ["champions", "europa", "conference", "relegation"];

export const CHAMPIONS_LEAGUE_SLOTS = 4;
export const EUROPA_LEAGUE_SLOTS = 6;
export const CONFERENCE_LEAGUE_SLOTS = 7;
export const RELEGATION_FROM = 18;

/** Mirrors zone_for_position in scripts/laliga_transform.py. */
export function zoneForPosition(position) {
  if (position <= CHAMPIONS_LEAGUE_SLOTS) return "champions";
  if (position <= EUROPA_LEAGUE_SLOTS) return "europa";
  if (position <= CONFERENCE_LEAGUE_SLOTS) return "conference";
  if (position >= RELEGATION_FROM) return "relegation";
  return "mid";
}

export function zoneColor(zone) {
  return ZONE_COLORS[zone] ?? ZONE_COLORS.mid;
}

/** Colour a single form character: W green, D amber, L red. */
export const FORM_COLORS = {
  W: "#00FF41",
  D: "#FFD700",
  L: "#FF4136",
};

/**
 * Format an ISO timestamp for the CRT header.
 * en-GB rather than es-ES, and 24-hour, which the terminal look wants anyway.
 */
export function formatDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" });
}

/** Kickoff times arrive as epoch milliseconds in the upcoming-fixtures feed. */
export function formatKickoff(value) {
  if (value == null) return "—";
  const date = new Date(typeof value === "number" ? value : Date.parse(value));
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Signed goal difference, so +3 reads as a gain rather than as 3. */
export function formatGoalDifference(value) {
  const n = Number(value) || 0;
  return n > 0 ? `+${n}` : String(n);
}
