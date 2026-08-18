import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  HALF_OVER,
  MATCH_OVER,
  PAUSED,
  RUNNING,
  createClock,
  dueSubCues,
  elapsedMinutes,
  elapsedMs,
  endHalf,
  formatClock,
  halfDurationMs,
  msToNextSubCue,
  pause,
  start,
  startSecondHalf,
} from "../../lib/matchClock";
import {
  isSoundEnabled,
  playFullTime,
  playHalfEnd,
  playSubstitution,
  setSoundEnabled,
  unlock,
} from "../../lib/matchSounds";
import { AMBER, Button, GREEN, Notice, RED, ScreenHeader } from "./ui";

/**
 * The match in progress: one column per team, each with its score, its goal
 * button and its scorers.
 *
 * Three things drive the shape of this file.
 *
 * The clock is read from timestamps (see lib/matchClock.js), so the 250ms
 * interval here only decides how smoothly the display updates. If the phone
 * sleeps for ten minutes, the next tick shows the correct time rather than a
 * clock that lost ten minutes.
 *
 * Cues fire from a ref, not from state. Deriving "should the substitution beep
 * play" from a render would replay it on every re-render inside the same second;
 * the ref records what has already sounded and is the single gate.
 *
 * The whole match is mirrored into localStorage on every change, so closing the
 * tab or locking the phone does not lose a game that is already being played.
 */

const STORAGE_KEY = "futboard.match";

export function loadStoredMatch() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearStoredMatch() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private browsing */
  }
}

function storeMatch(match) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(match));
  } catch {
    /* private browsing: the match still works, it just will not survive a reload */
  }
}

/** A match ready to be played. Serialisable on purpose — this is what is stored. */
export function createMatch({ home, away, homePlayers, awayPlayers, halfMinutes, subMinutes }) {
  return {
    home: { id: home.id, name: home.name, players: homePlayers },
    away: { id: away.id, name: away.name, players: awayPlayers },
    halfMinutes,
    subMinutes,
    clock: createClock(halfMinutes, subMinutes),
    goals: [],
  };
}

export default function LiveMatch({ f, match: initialMatch, onExit, onSave }) {
  const [match, setMatch] = useState(initialMatch);
  const [now, setNow] = useState(() => Date.now());
  const [picker, setPicker] = useState(null); // which side is choosing a scorer
  const [flash, setFlash] = useState(null); // visual twin of each sound cue
  const [sound, setSound] = useState(isSoundEnabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const firedCues = useRef({ half: match.clock.half, count: 0 });
  const clock = match.clock;

  useEffect(() => storeMatch(match), [match]);

  // Display refresh only; the values themselves come from timestamps.
  useEffect(() => {
    if (clock.status !== RUNNING) return undefined;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [clock.status]);

  const showFlash = useCallback((kind) => {
    setFlash(kind);
    setTimeout(() => setFlash(null), 2600);
  }, []);

  // Keep the screen awake while the clock runs. Best effort: not every browser
  // grants it, and a refused lock is not an error worth showing anyone.
  useEffect(() => {
    if (clock.status !== RUNNING || !navigator.wakeLock) return undefined;
    let sentinel = null;
    let cancelled = false;
    navigator.wakeLock
      .request("screen")
      .then((lock) => {
        if (cancelled) lock.release().catch(() => {});
        else sentinel = lock;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (sentinel) sentinel.release().catch(() => {});
    };
  }, [clock.status]);

  // ── cues ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (clock.status !== RUNNING) return;

    if (firedCues.current.half !== clock.half) {
      firedCues.current = { half: clock.half, count: 0 };
    }

    const due = dueSubCues(clock, now);
    if (due > firedCues.current.count) {
      firedCues.current.count = due;
      playSubstitution();
      showFlash("subs");
    }

    if (elapsedMs(clock, now) >= halfDurationMs(clock)) {
      const finishing = clock.half === 2;
      if (finishing) playFullTime();
      else playHalfEnd();
      showFlash(finishing ? "full" : "half");
      setMatch((current) => ({ ...current, clock: endHalf(current.clock) }));
    }
  }, [clock, now, showFlash]);

  // ── actions ───────────────────────────────────────────────────────────────

  const handleStart = () => {
    unlock(); // must happen inside the tap, or mobile audio stays silent
    setMatch((current) => ({ ...current, clock: start(current.clock) }));
    setNow(Date.now());
  };

  const handlePause = () =>
    setMatch((current) => ({ ...current, clock: pause(current.clock) }));

  const handleEndHalf = () => {
    const finishing = clock.half === 2;
    if (finishing) playFullTime();
    else playHalfEnd();
    showFlash(finishing ? "full" : "half");
    setMatch((current) => ({ ...current, clock: endHalf(current.clock) }));
  };

  const handleSecondHalf = () => {
    unlock();
    firedCues.current = { half: 2, count: 0 };
    setMatch((current) => ({ ...current, clock: startSecondHalf(current.clock) }));
    setNow(Date.now());
  };

  const recordGoal = (side, playerId) => {
    setMatch((current) => ({
      ...current,
      goals: [
        ...current.goals,
        {
          side,
          team_id: current[side].id,
          player_id: playerId,
          half: current.clock.half,
          minute: elapsedMinutes(current.clock),
        },
      ],
    }));
    setPicker(null);
  };

  const undoLastGoal = () =>
    setMatch((current) => ({ ...current, goals: current.goals.slice(0, -1) }));

  const toggleSound = () => {
    const next = !sound;
    setSound(next);
    setSoundEnabled(next);
    if (next) unlock();
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({
        home_team_id: match.home.id,
        away_team_id: match.away.id,
        half_minutes: match.halfMinutes,
        sub_interval_minutes: match.subMinutes,
        home_player_ids: match.home.players.map((p) => p.id),
        away_player_ids: match.away.players.map((p) => p.id),
        goals: match.goals.map(({ team_id, player_id, half, minute }) => ({
          team_id,
          player_id,
          half,
          minute,
        })),
      });
      clearStoredMatch();
    } catch (exc) {
      setError(exc.message);
    } finally {
      setSaving(false);
    }
  };

  // ── derived ───────────────────────────────────────────────────────────────

  const score = (side) => match.goals.filter((g) => g.side === side).length;
  const elapsed = elapsedMs(clock, now);
  const progress = Math.min(100, (elapsed / halfDurationMs(clock)) * 100);
  const toNextCue = msToNextSubCue(clock, now);
  const cueMarker =
    toNextCue === null ? null : ((elapsed + toNextCue) / halfDurationMs(clock)) * 100;

  const halfLabel =
    clock.status === MATCH_OVER
      ? f.live.fullTime
      : clock.status === HALF_OVER
        ? f.live.halfTime
        : clock.half === 1
          ? f.live.firstHalf
          : f.live.secondHalf;

  const flashText =
    flash === "subs" ? f.live.subsNow : flash === "half" ? f.live.halfOver : f.live.matchOver;

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6 flex flex-col">
      <ScreenHeader
        title={`${match.home.name} ${score("home")} — ${score("away")} ${match.away.name}`}
        onBack={onExit}
        backLabel={f.back}
        right={
          <button
            type="button"
            onClick={toggleSound}
            title={sound ? f.live.soundOn : f.live.soundOff}
            aria-label={sound ? f.live.soundOn : f.live.soundOff}
            className="shrink-0 min-h-[44px] px-3 text-[#00FF41]/75 hover:text-[#00FF41]"
          >
            <span className="material-symbols-outlined">{sound ? "volume_up" : "volume_off"}</span>
          </button>
        }
      />

      {/* Clock */}
      <div className="text-center">
        <div
          className="font-headline font-bold tabular-nums text-[2.6rem] sm:text-[3.4rem] leading-none"
          style={{ color: GREEN, textShadow: "0 0 18px rgba(0,255,65,0.5)" }}
        >
          {formatClock(elapsed)}
        </div>
        <div className="font-headline uppercase text-[0.78rem] tracking-[0.2em] text-[#00FF41]/70 mt-1">
          {halfLabel} · {f.live.of(match.halfMinutes)}
        </div>
      </div>

      {/* Progress, with the next substitution cue marked */}
      <div className="relative h-1.5 my-3 rounded bg-[#00FF41]/15">
        <div
          className="absolute inset-y-0 left-0 rounded"
          style={{ width: `${progress}%`, background: GREEN, opacity: 0.75 }}
        />
        {cueMarker !== null && (
          <div
            className="absolute -top-1 -bottom-1 w-[2px]"
            style={{ left: `${cueMarker}%`, background: AMBER }}
          />
        )}
      </div>

      {flash ? (
        <div
          className="text-center font-headline font-bold uppercase tracking-[0.25em] text-[0.9rem] py-2 rounded flicker"
          style={{ color: flash === "subs" ? AMBER : GREEN, background: "rgba(0,255,65,0.08)" }}
        >
          {flashText}
        </div>
      ) : (
        toNextCue !== null &&
        clock.status === RUNNING && (
          <div
            className="text-center font-headline uppercase text-[0.78rem] tracking-widest"
            style={{ color: AMBER }}
          >
            {f.live.nextSubs} {formatClock(toNextCue)}
          </div>
        )
      )}

      {/* One column per team */}
      <div className="grid grid-cols-2 gap-2 sm:gap-4 mt-3 flex-1 min-h-0">
        {["home", "away"].map((side) => (
          <div
            key={side}
            className="flex flex-col border border-[#00FF41]/20 rounded p-2 sm:p-3 bg-black/20 min-h-0"
          >
            <h3 className="font-headline uppercase text-[0.82rem] sm:text-[0.9rem] text-center text-[#00FF41]/85 tracking-wide truncate">
              {match[side].name}
            </h3>
            <div
              className="font-headline font-bold tabular-nums text-center text-[2rem] sm:text-[2.6rem] leading-tight"
              style={{ color: GREEN, textShadow: "0 0 14px rgba(0,255,65,0.45)" }}
            >
              {score(side)}
            </div>

            <button
              type="button"
              onClick={() => setPicker(side)}
              disabled={clock.status === MATCH_OVER}
              className="w-full min-h-[56px] my-2 border border-[#00FF41]/55 rounded bg-[#00FF41]/15 hover:bg-[#00FF41]/25 active:scale-95 font-headline font-bold uppercase text-[0.95rem] tracking-widest text-[#00FF41] disabled:opacity-40 disabled:active:scale-100"
            >
              + {f.live.goal}
            </button>

            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-hide space-y-1">
              {match.goals.filter((g) => g.side === side).length === 0 ? (
                <p className="font-headline text-[0.74rem] text-[#00FF41]/65 text-center normal-case pt-1">
                  {f.live.noScorers}
                </p>
              ) : (
                match.goals
                  .filter((g) => g.side === side)
                  .map((goal, index) => {
                    const scorer = match[side].players.find((p) => p.id === goal.player_id);
                    return (
                      <div
                        key={`${goal.minute}-${index}`}
                        className="flex justify-between gap-2 font-headline text-[0.75rem] text-[#00FF41]/75 normal-case"
                      >
                        <span className="truncate">{scorer ? scorer.name : "—"}</span>
                        <span className="tabular-nums shrink-0">{goal.minute}'</span>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 mt-3">
        {clock.status === HALF_OVER ? (
          <Button variant="primary" icon="play_arrow" onClick={handleSecondHalf} className="flex-1">
            {f.live.startSecondHalf}
          </Button>
        ) : clock.status === MATCH_OVER ? null : (
          <>
            <Button
              variant="primary"
              icon={clock.status === RUNNING ? "pause" : "play_arrow"}
              onClick={clock.status === RUNNING ? handlePause : handleStart}
              className="flex-1"
            >
              {clock.status === RUNNING ? f.live.pause : f.live.resume}
            </Button>
            <Button variant="danger" icon="stop" onClick={handleEndHalf} className="flex-1">
              {clock.half === 2 ? f.live.endMatch : f.live.endHalf}
            </Button>
          </>
        )}
        {match.goals.length > 0 && clock.status !== MATCH_OVER && (
          <Button icon="undo" onClick={undoLastGoal}>
            {f.live.undoLast}
          </Button>
        )}
      </div>

      {clock.status === MATCH_OVER && (
        <div className="mt-3 space-y-2">
          {error && <Notice tone="error">{error}</Notice>}
          <div className="flex gap-2">
            <Button variant="primary" icon="save" onClick={save} disabled={saving} className="flex-1">
              {saving ? f.live.saving : f.live.save}
            </Button>
            <Button
              variant="danger"
              icon="delete"
              onClick={() => {
                if (window.confirm(f.live.discardConfirm)) {
                  clearStoredMatch();
                  onExit();
                }
              }}
            >
              {f.live.discard}
            </Button>
          </div>
        </div>
      )}

      {/* Scorer picker */}
      {picker && (
        <div
          className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/70 p-3"
          onClick={() => setPicker(null)}
        >
          <div
            className="w-full max-w-md border-2 border-[#00FF41]/50 rounded-lg bg-[#0a0a0a] p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <h4 className="font-headline uppercase text-[0.86rem] tracking-widest text-[#00FF41] text-center mb-3">
              {f.live.whoScored(match[picker].name)}
            </h4>
            <div className="flex flex-wrap gap-2 max-h-[45vh] overflow-y-auto scrollbar-hide">
              {match[picker].players.map((player) => (
                <button
                  key={player.id}
                  type="button"
                  onClick={() => recordGoal(picker, player.id)}
                  className="min-h-[44px] px-3 border border-[#00FF41]/30 rounded font-headline text-[0.86rem] text-[#00FF41]/85 hover:bg-[#00FF41]/10 hover:text-[#00FF41] active:scale-95"
                >
                  {player.name}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => recordGoal(picker, null)}
              className="w-full min-h-[52px] mt-3 border border-[#00FF41]/60 rounded bg-[#00FF41]/15 hover:bg-[#00FF41]/25 font-headline font-bold uppercase text-[0.86rem] tracking-widest text-[#00FF41] active:scale-95"
            >
              {f.live.notSpecified}
            </button>
            <button
              type="button"
              onClick={() => setPicker(null)}
              className="w-full min-h-[44px] mt-2 font-headline uppercase text-[0.8rem] tracking-widest text-[#00FF41]/65 hover:text-[#00FF41]"
            >
              {f.common.cancel}
            </button>
          </div>
        </div>
      )}

      <div className="h-4" />
    </div>
  );
}
