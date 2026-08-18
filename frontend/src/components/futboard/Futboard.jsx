import React, { useCallback, useEffect, useState } from "react";
import { useT } from "../../i18n";
import { futboardApi } from "../../lib/futboardApi";
import LiveMatch, { clearStoredMatch, createMatch, loadStoredMatch } from "./LiveMatch";
import MatchSetup from "./MatchSetup";
import SquadsScreen from "./SquadsScreen";
import StatsScreen from "./StatsScreen";
import { Button, ErrorState, ListRow, Loading, Notice, Panel } from "./ui";

/**
 * FUTBOARD: the hub, and the only component that talks to the API.
 *
 * Screens are local state rather than routes, because the site has no router and
 * adding one for four screens inside one section would be a dependency in
 * exchange for nothing. Every inner screen takes a `onBack`, which is the
 * navigation model: a home with three cards, and one step in and out.
 *
 * All data loading lives here so the screens stay pure functions of props. There
 * is exactly one fetch of the whole dataset, refreshed after any write — the
 * data is a few kilobytes and Neon charges by compute time, so one round trip
 * that wakes the database once beats four that each risk waking it again.
 */

const SCREENS = { HUB: "hub", SETUP: "setup", MATCH: "match", SQUADS: "squads", STATS: "stats" };

const HUB_CARDS = [
  { id: SCREENS.SETUP, icon: "play_arrow", key: "newMatch", hint: "newMatchHint" },
  { id: SCREENS.SQUADS, icon: "groups", key: "squads", hint: "squadsHint" },
  { id: SCREENS.STATS, icon: "bar_chart", key: "stats", hint: "statsHint" },
];

export default function Futboard() {
  // FUTBOARD used to carry its own language switch. Now the whole site is
  // bilingual it reads the global one: two independent switches on one page was
  // a worse answer than one, and this section is not special.
  const f = useT().futboard;

  const [screen, setScreen] = useState(SCREENS.HUB);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [slow, setSlow] = useState(false);
  const [match, setMatch] = useState(null);
  const [resumable, setResumable] = useState(() => loadStoredMatch());
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    setSlow(false);
    // Neon suspends after five minutes idle, so a first load can take a couple
    // of seconds. Say what the wait is rather than leaving a spinner running.
    const slowTimer = setTimeout(() => setSlow(true), 1200);
    try {
      const [teams, players, stats, matches] = await Promise.all([
        futboardApi.listTeams(),
        futboardApi.listPlayers(),
        futboardApi.stats(),
        futboardApi.listMatches(20),
      ]);
      setData({ teams, players, stats, matches });
    } catch (exc) {
      setError(exc.status === 503 ? f.common.unavailable : exc.message);
    } finally {
      clearTimeout(slowTimer);
      setSlow(false);
    }
  }, [f]);

  useEffect(() => {
    load();
  }, [load]);

  /** Run a write, then refresh. Errors propagate so the screen can show them. */
  const mutate = useCallback(
    async (action) => {
      const result = await action();
      await load();
      return result;
    },
    [load],
  );

  const startMatch = (settings) => {
    const created = createMatch(settings);
    setMatch(created);
    setResumable(null);
    setSaved(false);
    setScreen(SCREENS.MATCH);
  };

  const resumeMatch = () => {
    setMatch(resumable);
    setResumable(null);
    setScreen(SCREENS.MATCH);
  };

  const saveMatch = async (payload) => {
    await futboardApi.saveMatch(payload);
    await load();
    setSaved(true);
    setMatch(null);
    setScreen(SCREENS.HUB);
  };

  const leaveMatch = () => {
    setMatch(null);
    setResumable(loadStoredMatch());
    setScreen(SCREENS.HUB);
  };

  // ── screens ───────────────────────────────────────────────────────────────

  if (screen === SCREENS.MATCH && match) {
    return <LiveMatch f={f} match={match} onExit={leaveMatch} onSave={saveMatch} />;
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center p-6">
        <ErrorState message={error} onRetry={load} retryLabel={f.common.retry} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <Loading label={f.common.loading} slow={slow ? f.common.waking : null} />
      </div>
    );
  }

  if (screen === SCREENS.SQUADS) {
    return (
      <SquadsScreen
        f={f}
        teams={data.teams}
        players={data.players}
        onBack={() => setScreen(SCREENS.HUB)}
        onCreateTeam={(name) => mutate(() => futboardApi.createTeam(name))}
        onCreatePlayer={(name, teamId) => mutate(() => futboardApi.createPlayer(name, teamId))}
        onAddToTeam={(teamId, playerId) =>
          mutate(() => futboardApi.addPlayerToTeam(teamId, playerId))
        }
        onRemoveFromTeam={(teamId, playerId) =>
          mutate(() => futboardApi.removePlayerFromTeam(teamId, playerId))
        }
      />
    );
  }

  if (screen === SCREENS.SETUP) {
    return (
      <MatchSetup
        f={f}
        teams={data.teams}
        players={data.players}
        onBack={() => setScreen(SCREENS.HUB)}
        onStart={startMatch}
      />
    );
  }

  if (screen === SCREENS.STATS) {
    return (
      <StatsScreen
        f={f}
        stats={data.stats}
        matches={data.matches}
        onBack={() => setScreen(SCREENS.HUB)}
      />
    );
  }

  // ── hub ───────────────────────────────────────────────────────────────────

  const topScorer = data.stats.players.find((player) => player.goals > 0) || null;

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <div className="flex items-start justify-between gap-3 mb-5">
        <div className="min-w-0">
          <h2 className="text-xl sm:text-2xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_12px_rgba(0,255,65,0.45)]">
            {f.title}
          </h2>
          <p className="text-[0.84rem] text-[#00FF41]/70 font-headline mt-1 normal-case">
            {f.tagline}
          </p>
        </div>
      </div>

      {saved && (
        <div className="mb-4">
          <Notice>{f.live.saved}</Notice>
        </div>
      )}

      {resumable && (
        <div className="mb-4 border border-[#FFD700]/40 rounded p-3">
          <p className="font-headline text-[0.86rem] text-[#FFD700] normal-case">
            {f.live.resumeMatch}
          </p>
          <p className="font-headline text-[0.8rem] text-[#00FF41]/70 normal-case mt-0.5">
            {f.live.resumeHint}
          </p>
          <div className="flex gap-2 mt-3">
            <Button variant="primary" icon="play_arrow" onClick={resumeMatch}>
              {f.live.resume}
            </Button>
            <Button
              variant="danger"
              icon="delete"
              onClick={() => {
                clearStoredMatch();
                setResumable(null);
              }}
            >
              {f.live.discard}
            </Button>
          </div>
        </div>
      )}

      {/* The three cards. One column on a phone, three across from `sm`. */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        {HUB_CARDS.map((card) => (
          <button
            key={card.id}
            type="button"
            onClick={() => setScreen(card.id)}
            className="group flex sm:flex-col items-center sm:items-start gap-3 sm:gap-2 text-left p-4 sm:p-5 min-h-[88px] border border-[#00FF41]/25 rounded-lg bg-[#00FF41]/[0.03] hover:bg-[#00FF41]/10 hover:border-[#00FF41]/50 active:scale-[0.98] transition-colors"
          >
            <span className="material-symbols-outlined text-[1.9rem] sm:text-[2.2rem] text-[#00FF41] drop-shadow-[0_0_8px_rgba(0,255,65,0.5)] shrink-0">
              {card.icon}
            </span>
            <span className="min-w-0">
              <span className="block font-headline uppercase font-bold text-[0.95rem] tracking-wide text-[#00FF41]">
                {f.hub[card.key]}
              </span>
              <span className="block font-headline text-[0.78rem] text-[#00FF41]/70 normal-case mt-0.5 leading-snug">
                {f.hub[card.hint]}
              </span>
            </span>
          </button>
        ))}
      </div>

      {/* A little life on the home screen, so it is not three buttons on black. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-5">
        <Panel title={f.hub.recent} icon="history">
          {data.matches.length === 0 ? (
            <p className="font-headline text-[0.82rem] text-[#00FF41]/70 normal-case py-3 text-center">
              {f.hub.noMatchesYet}
            </p>
          ) : (
            <div className="space-y-1.5">
              {data.matches.slice(0, 5).map((entry) => (
                <ListRow key={entry.id}>
                  <span className="flex-1 font-headline text-[0.84rem] text-[#00FF41]/85 truncate text-right">
                    {entry.home_team_name}
                  </span>
                  <span className="shrink-0 font-headline font-bold tabular-nums text-[0.88rem] text-[#00FF41] px-1">
                    {entry.home_goals}—{entry.away_goals}
                  </span>
                  <span className="flex-1 font-headline text-[0.84rem] text-[#00FF41]/85 truncate">
                    {entry.away_team_name}
                  </span>
                </ListRow>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={f.hub.topScorer} icon="trophy">
          {!topScorer ? (
            <p className="font-headline text-[0.82rem] text-[#00FF41]/70 normal-case py-3 text-center">
              {f.hub.noMatchesYet}
            </p>
          ) : (
            <div className="flex items-center gap-3 py-2">
              <span className="material-symbols-outlined text-[2rem] text-[#FFD700]">trophy</span>
              <div className="min-w-0">
                <div className="font-headline text-[0.95rem] font-bold text-[#00FF41] truncate">
                  {topScorer.name}
                </div>
                <div className="font-headline text-[0.8rem] text-[#00FF41]/70 normal-case">
                  {f.hub.goalCount(topScorer.goals)} · {f.hub.matchCount(topScorer.matches)}
                </div>
              </div>
            </div>
          )}
        </Panel>
      </div>

      <div className="h-8" />
    </div>
  );
}
