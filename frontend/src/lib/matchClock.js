/**
 * The match clock.
 *
 * Elapsed time is derived from wall-clock timestamps, never accumulated from
 * ticks. This is the one thing in FUTBOARD that has to be right: a phone locks
 * its screen and throttles or suspends timers in a backgrounded tab, so a clock
 * built by adding a second per `setInterval` callback comes back minutes short
 * after a pocket. Because the running total is `Date.now() - startedAt - paused`,
 * the interval only decides how often the display refreshes; it has no bearing
 * on what the display says.
 *
 * The state is a plain serialisable object so the whole match survives a reload
 * through localStorage — including a clock that kept running while the tab was
 * closed, which is the correct behaviour for a game that did not stop.
 */

export const RUNNING = "running";
export const PAUSED = "paused";
export const HALF_OVER = "half_over";
export const MATCH_OVER = "match_over";

/** A fresh clock for the first half, not yet started. */
export function createClock(halfMinutes, subIntervalMinutes) {
  return {
    halfMinutes,
    subIntervalMinutes,
    half: 1,
    status: PAUSED,
    startedAt: null,
    pausedTotalMs: 0,
    pausedAt: null,
    // Substitution cues already fired this half, so a re-render cannot repeat one.
    subCuesFired: 0,
  };
}

export function halfDurationMs(clock) {
  return clock.halfMinutes * 60_000;
}

/** Milliseconds played in the current half, clamped to the half's length. */
export function elapsedMs(clock, now = Date.now()) {
  if (clock.startedAt === null) return 0;
  const frozenAt = clock.pausedAt ?? now;
  const reference = clock.status === PAUSED ? frozenAt : now;
  const raw = reference - clock.startedAt - clock.pausedTotalMs;
  return Math.max(0, Math.min(raw, halfDurationMs(clock)));
}

export function remainingMs(clock, now = Date.now()) {
  return Math.max(0, halfDurationMs(clock) - elapsedMs(clock, now));
}

/** Whole minutes played in the current half — what a goal is stamped with. */
export function elapsedMinutes(clock, now = Date.now()) {
  const base = clock.half === 2 ? clock.halfMinutes : 0;
  return base + Math.floor(elapsedMs(clock, now) / 60_000);
}

export function formatClock(ms) {
  const total = Math.floor(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/**
 * How many substitution cues should have fired by now.
 *
 * Cues land at each whole multiple of the interval, but never at the very end of
 * the half: the whistle is about to go anyway, and two alerts a second apart
 * read as a malfunction. With a 25-minute half and a 5-minute interval that is
 * four cues, at 5, 10, 15 and 20 — not five.
 */
export function dueSubCues(clock, now = Date.now()) {
  const intervalMs = clock.subIntervalMinutes * 60_000;
  if (intervalMs <= 0) return 0;
  const elapsed = elapsedMs(clock, now);
  const maxCues = Math.max(0, Math.ceil(halfDurationMs(clock) / intervalMs) - 1);
  return Math.min(Math.floor(elapsed / intervalMs), maxCues);
}

/** Milliseconds until the next substitution cue, or null if none is left. */
export function msToNextSubCue(clock, now = Date.now()) {
  const intervalMs = clock.subIntervalMinutes * 60_000;
  if (intervalMs <= 0) return null;
  const elapsed = elapsedMs(clock, now);
  const nextIndex = Math.floor(elapsed / intervalMs) + 1;
  const maxCues = Math.max(0, Math.ceil(halfDurationMs(clock) / intervalMs) - 1);
  if (nextIndex > maxCues) return null;
  return nextIndex * intervalMs - elapsed;
}

// ── transitions: each returns a new clock, none mutates ─────────────────────

export function start(clock, now = Date.now()) {
  if (clock.status === RUNNING) return clock;
  if (clock.startedAt === null) {
    return { ...clock, status: RUNNING, startedAt: now, pausedAt: null };
  }
  // Resuming: fold the time spent paused into the offset so it is not played.
  const pausedFor = clock.pausedAt === null ? 0 : now - clock.pausedAt;
  return {
    ...clock,
    status: RUNNING,
    pausedAt: null,
    pausedTotalMs: clock.pausedTotalMs + pausedFor,
  };
}

export function pause(clock, now = Date.now()) {
  if (clock.status !== RUNNING) return clock;
  return { ...clock, status: PAUSED, pausedAt: now };
}

export function endHalf(clock) {
  return {
    ...clock,
    status: clock.half === 1 ? HALF_OVER : MATCH_OVER,
    pausedAt: clock.pausedAt ?? Date.now(),
  };
}

/** Second half: a fresh clock at zero, keeping the settings. */
export function startSecondHalf(clock, now = Date.now()) {
  return {
    ...clock,
    half: 2,
    status: RUNNING,
    startedAt: now,
    pausedTotalMs: 0,
    pausedAt: null,
    subCuesFired: 0,
  };
}

export function isOver(clock) {
  return clock.status === MATCH_OVER;
}
