/**
 * The three match cues, synthesised with the Web Audio API.
 *
 * No audio files, deliberately. Three short beeps as assets would mean three
 * network requests on a pitch with poor signal, a `media-src` entry in the CSP,
 * and files to keep in sync with the build. Oscillators cost nothing, work
 * offline, and are exactly as loud as they need to be.
 *
 * Mobile browsers refuse to start audio without a user gesture, so `unlock()`
 * has to be called from the tap that starts the match. Calling it later — from a
 * timer, when the substitution cue is due — produces silence with no error.
 *
 * The phone may also be on silent, which no amount of correct audio code can
 * defeat. Every cue is therefore paired with a visual flash in the UI, and the
 * sounds are treated as the secondary channel rather than the only one.
 */

let context = null;
let enabled = true;

function ensureContext() {
  if (typeof window === "undefined") return null;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return null;
  if (context === null) {
    try {
      context = new AudioContextClass();
    } catch {
      return null;
    }
  }
  return context;
}

/** Call from a user gesture (the start button) before any cue is due. */
export function unlock() {
  const ctx = ensureContext();
  if (!ctx) return false;
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return true;
}

export function setSoundEnabled(value) {
  enabled = Boolean(value);
}

export function isSoundEnabled() {
  return enabled;
}

/**
 * One tone.
 *
 * The gain ramp matters more than it looks: starting or stopping a square wave
 * at full amplitude produces an audible click, which on three beeps in a row
 * sounds like a fault rather than a signal.
 */
function tone(ctx, { frequency, start, duration, volume = 0.25, type = "square" }) {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, ctx.currentTime + start);

  gain.gain.setValueAtTime(0.0001, ctx.currentTime + start);
  gain.gain.exponentialRampToValueAtTime(volume, ctx.currentTime + start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + duration);

  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(ctx.currentTime + start);
  oscillator.stop(ctx.currentTime + start + duration + 0.02);
}

function play(notes) {
  if (!enabled) return;
  const ctx = ensureContext();
  if (!ctx) return;
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  notes.forEach((note) => tone(ctx, note));
}

/** Substitutions are due: two short mid beeps, the least alarming of the three. */
export function playSubstitution() {
  play([
    { frequency: 880, start: 0, duration: 0.16 },
    { frequency: 880, start: 0.24, duration: 0.16 },
  ]);
}

/** End of a half: three longer, higher beeps. Meant to carry across a pitch. */
export function playHalfEnd() {
  play([
    { frequency: 1046, start: 0, duration: 0.3, volume: 0.3 },
    { frequency: 1046, start: 0.4, duration: 0.3, volume: 0.3 },
    { frequency: 1046, start: 0.8, duration: 0.45, volume: 0.3 },
  ]);
}

/** End of the match: a descending figure, so it cannot be mistaken for a half. */
export function playFullTime() {
  play([
    { frequency: 1046, start: 0, duration: 0.28, volume: 0.3 },
    { frequency: 784, start: 0.32, duration: 0.28, volume: 0.3 },
    { frequency: 523, start: 0.64, duration: 0.7, volume: 0.32 },
  ]);
}
