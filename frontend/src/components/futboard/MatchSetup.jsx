import React, { useMemo, useState } from "react";
import { Button, EmptyState, Notice, Panel, ScreenHeader } from "./ui";

/**
 * Choose the two teams, who turned up, and the length of a half.
 *
 * Everyone in a squad is selected by default, because the common case is that
 * the whole squad plays and unticking two absentees is faster than ticking nine
 * people while they wait for you.
 *
 * There is no halftime setting: the first half ends, the whistle sounds, and the
 * second half starts when someone taps. Timing a break that people take at their
 * own pace was a setting with no job to do.
 */

const HALF_PRESETS = [15, 20, 25, 30];
const SUB_PRESETS = [3, 5, 7, 10];

function NumberChoice({ label, value, options, unit, onChange }) {
  return (
    <div>
      <p className="font-headline uppercase text-[0.78rem] tracking-widest text-[#00FF41]/75 mb-2">
        {label}
      </p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={`min-h-[44px] min-w-[64px] px-3 border rounded font-headline text-[0.9rem] tabular-nums active:scale-95 transition-colors ${
              option === value
                ? "border-[#00FF41]/60 bg-[#00FF41]/20 text-[#00FF41] font-bold"
                : "border-[#00FF41]/25 text-[#00FF41]/75 hover:bg-[#00FF41]/10"
            }`}
          >
            {option} {unit}
          </button>
        ))}
      </div>
    </div>
  );
}

function TeamPicker({ label, teams, value, disabledId, onChange }) {
  return (
    <div>
      <p className="font-headline uppercase text-[0.78rem] tracking-widest text-[#00FF41]/75 mb-2">
        {label}
      </p>
      <div className="flex flex-wrap gap-2">
        {teams.map((team) => {
          const blocked = team.id === disabledId;
          return (
            <button
              key={team.id}
              type="button"
              disabled={blocked}
              onClick={() => onChange(team.id === value ? null : team.id)}
              className={`min-h-[44px] px-3 border rounded font-headline text-[0.88rem] active:scale-95 transition-colors ${
                team.id === value
                  ? "border-[#00FF41]/60 bg-[#00FF41]/20 text-[#00FF41] font-bold"
                  : "border-[#00FF41]/25 text-[#00FF41]/75 hover:bg-[#00FF41]/10"
              } disabled:opacity-30 disabled:active:scale-100`}
            >
              {team.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function LineupPicker({ f, team, players, selected, onToggle, onAll, onNone }) {
  if (!team) return null;
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="font-headline uppercase text-[0.78rem] tracking-widest text-[#00FF41]/75 truncate">
          {f.setup.whoPlays(team.name)}
        </p>
        <div className="flex gap-1 shrink-0">
          <button
            type="button"
            onClick={onAll}
            className="min-h-[36px] px-2 font-headline uppercase text-[0.74rem] tracking-widest text-[#00FF41]/70 hover:text-[#00FF41]"
          >
            {f.setup.selectAll}
          </button>
          <button
            type="button"
            onClick={onNone}
            className="min-h-[36px] px-2 font-headline uppercase text-[0.74rem] tracking-widest text-[#00FF41]/70 hover:text-[#00FF41]"
          >
            {f.setup.selectNone}
          </button>
        </div>
      </div>
      {players.length === 0 ? (
        <Notice tone="warn">{f.setup.emptySquad}</Notice>
      ) : (
        <div className="flex flex-wrap gap-2">
          {players.map((player) => {
            const on = selected.has(player.id);
            return (
              <button
                key={player.id}
                type="button"
                onClick={() => onToggle(player.id)}
                className={`inline-flex items-center gap-1.5 min-h-[44px] px-3 border rounded font-headline text-[0.86rem] active:scale-95 transition-colors ${
                  on
                    ? "border-[#00FF41]/60 bg-[#00FF41]/15 text-[#00FF41]"
                    : "border-[#00FF41]/20 text-[#00FF41]/60 hover:bg-[#00FF41]/5"
                }`}
              >
                <span className="material-symbols-outlined text-[1rem]">
                  {on ? "check_circle" : "radio_button_unchecked"}
                </span>
                {player.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function MatchSetup({ f, teams, players, onBack, onStart }) {
  const [homeId, setHomeId] = useState(null);
  const [awayId, setAwayId] = useState(null);
  const [halfMinutes, setHalfMinutes] = useState(25);
  const [subMinutes, setSubMinutes] = useState(5);
  const [excluded, setExcluded] = useState(() => new Set());

  const squadOf = (teamId) =>
    teamId === null ? [] : players.filter((p) => p.team_ids.includes(teamId));

  const home = teams.find((t) => t.id === homeId) || null;
  const away = teams.find((t) => t.id === awayId) || null;
  const homeSquad = useMemo(() => squadOf(homeId), [homeId, players]);
  const awaySquad = useMemo(() => squadOf(awayId), [awayId, players]);

  // Everyone plays unless explicitly excluded, so switching teams does not lose
  // a selection the person was halfway through making.
  const playing = (squad) => new Set(squad.filter((p) => !excluded.has(p.id)).map((p) => p.id));
  const homePlaying = playing(homeSquad);
  const awayPlaying = playing(awaySquad);

  const toggle = (playerId) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (next.has(playerId)) next.delete(playerId);
      else next.add(playerId);
      return next;
    });

  const setAll = (squad, include) =>
    setExcluded((current) => {
      const next = new Set(current);
      squad.forEach((p) => (include ? next.delete(p.id) : next.add(p.id)));
      return next;
    });

  const ready = home && away && homePlaying.size > 0 && awayPlaying.size > 0;

  if (teams.length < 2) {
    return (
      <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
        <ScreenHeader title={f.setup.title} onBack={onBack} backLabel={f.back} />
        <EmptyState icon="groups">{f.setup.pickTwo}</EmptyState>
      </div>
    );
  }

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <ScreenHeader title={f.setup.title} onBack={onBack} backLabel={f.back} />

      <div className="space-y-4">
        <Panel title={f.setup.pickTwo} icon="sports_soccer">
          <div className="space-y-4">
            <TeamPicker label={f.setup.home} teams={teams} value={homeId} disabledId={awayId} onChange={setHomeId} />
            <TeamPicker label={f.setup.away} teams={teams} value={awayId} disabledId={homeId} onChange={setAwayId} />
          </div>
        </Panel>

        {(home || away) && (
          <Panel title={f.squads.players} icon="checklist">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <LineupPicker
                f={f}
                team={home}
                players={homeSquad}
                selected={homePlaying}
                onToggle={toggle}
                onAll={() => setAll(homeSquad, true)}
                onNone={() => setAll(homeSquad, false)}
              />
              <LineupPicker
                f={f}
                team={away}
                players={awaySquad}
                selected={awayPlaying}
                onToggle={toggle}
                onAll={() => setAll(awaySquad, true)}
                onNone={() => setAll(awaySquad, false)}
              />
            </div>
          </Panel>
        )}

        <Panel title={f.setup.title} icon="timer">
          <div className="space-y-4">
            <NumberChoice
              label={f.setup.halfMinutes}
              value={halfMinutes}
              options={HALF_PRESETS}
              unit={f.setup.minutes}
              onChange={setHalfMinutes}
            />
            <NumberChoice
              label={f.setup.subInterval}
              value={subMinutes}
              options={SUB_PRESETS}
              unit={f.setup.minutes}
              onChange={setSubMinutes}
            />
          </div>
        </Panel>

        {home && away && homePlaying.size === 0 && <Notice tone="warn">{f.setup.needPlayers}</Notice>}
        {home && away && awayPlaying.size === 0 && homePlaying.size > 0 && (
          <Notice tone="warn">{f.setup.needPlayers}</Notice>
        )}

        <Button
          variant="primary"
          icon="play_arrow"
          disabled={!ready}
          className="w-full min-h-[56px] text-[0.95rem]"
          onClick={() =>
            onStart({
              home,
              away,
              homePlayers: homeSquad.filter((p) => homePlaying.has(p.id)),
              awayPlayers: awaySquad.filter((p) => awayPlaying.has(p.id)),
              halfMinutes,
              subMinutes,
            })
          }
        >
          {f.setup.start}
        </Button>
      </div>

      <div className="h-8" />
    </div>
  );
}
