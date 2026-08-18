import React, { useState } from "react";
import { EmptyState, Panel, ScreenHeader } from "./ui";

/**
 * Scorers, teams and match history.
 *
 * Three tabs rather than three stacked tables: on a phone, stacking them means
 * scrolling past twenty players to reach the team table. Each table scrolls
 * horizontally inside its own container so a narrow screen never pushes the page
 * sideways.
 */

const TABS = [
  { id: "players", icon: "person" },
  { id: "teams", icon: "shield" },
  { id: "history", icon: "history" },
];

function Table({ head, children }) {
  return (
    <div className="overflow-x-auto scrollbar-hide">
      <table className="w-full text-[0.7rem] font-headline">
        <thead>
          <tr className="text-[#00FF41]/75 border-b border-[#00FF41]/15 uppercase text-[0.6rem]">
            {head}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export default function StatsScreen({ f, stats, matches, onBack }) {
  const [tab, setTab] = useState("players");

  const label = { players: f.stats.players, teams: f.stats.teams, history: f.stats.history };
  const hasAnything =
    stats.players.some((p) => p.matches > 0) || stats.teams.some((t) => t.played > 0);

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <ScreenHeader title={f.stats.title} onBack={onBack} backLabel={f.back} />

      <div className="flex gap-1 border-b border-[#00FF41]/20 mb-4">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => setTab(entry.id)}
            className={`flex items-center gap-1.5 min-h-[44px] px-3 sm:px-4 font-headline uppercase text-[0.68rem] tracking-widest border-b-2 -mb-px transition-colors ${
              tab === entry.id
                ? "border-[#00FF41] text-[#00FF41] bg-[#00FF41]/10"
                : "border-transparent text-[#00FF41]/60 hover:text-[#00FF41]"
            }`}
          >
            <span className="material-symbols-outlined text-[1rem]">{entry.icon}</span>
            {label[entry.id]}
          </button>
        ))}
      </div>

      {!hasAnything ? (
        <EmptyState icon="sports_soccer">{f.stats.empty}</EmptyState>
      ) : (
        <Panel>
          {tab === "players" && (
            <Table
              head={
                <>
                  <th className="py-2 px-2 text-left">{f.stats.name}</th>
                  <th className="py-2 px-2 text-right">{f.stats.matches}</th>
                  <th className="py-2 px-2 text-right">{f.stats.goals}</th>
                  <th className="py-2 px-2 text-right">{f.stats.perMatch}</th>
                  <th className="py-2 px-2 text-left">{f.stats.playsFor}</th>
                </>
              }
            >
              {stats.players.map((player) => (
                <tr key={player.player_id} className="border-b border-[#00FF41]/5">
                  <td className="py-1.5 px-2 text-[#00FF41]">{player.name}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">
                    {player.matches}
                  </td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41] font-bold">
                    {player.goals}
                  </td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">
                    {player.goals_per_match.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-2 text-[#00FF41]/70 normal-case">
                    {player.teams.join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </Table>
          )}

          {tab === "teams" && (
            <Table
              head={
                <>
                  <th className="py-2 px-2 text-left">{f.stats.name}</th>
                  <th className="py-2 px-2 text-right">{f.stats.played}</th>
                  <th className="py-2 px-2 text-right">{f.stats.won}</th>
                  <th className="py-2 px-2 text-right">{f.stats.drawn}</th>
                  <th className="py-2 px-2 text-right">{f.stats.lost}</th>
                  <th className="py-2 px-2 text-right">{f.stats.goalsFor}</th>
                  <th className="py-2 px-2 text-right">{f.stats.goalsAgainst}</th>
                  <th className="py-2 px-2 text-right">{f.stats.goalDifference}</th>
                </>
              }
            >
              {stats.teams.map((team) => (
                <tr key={team.team_id} className="border-b border-[#00FF41]/5">
                  <td className="py-1.5 px-2 text-[#00FF41]">{team.name}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">{team.played}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41] font-bold">{team.won}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">{team.drawn}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">{team.lost}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">{team.goals_for}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">{team.goals_against}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-[#00FF41]/75">
                    {team.goal_difference > 0 ? `+${team.goal_difference}` : team.goal_difference}
                  </td>
                </tr>
              ))}
            </Table>
          )}

          {tab === "history" &&
            (matches.length === 0 ? (
              <EmptyState icon="history">{f.hub.noMatchesYet}</EmptyState>
            ) : (
              <div className="space-y-2">
                {matches.map((match) => (
                  <div key={match.id} className="border border-[#00FF41]/15 rounded p-3 bg-black/20">
                    <div className="flex items-center gap-2 font-headline text-[0.78rem]">
                      <span className="flex-1 text-right text-[#00FF41] truncate">
                        {match.home_team_name}
                      </span>
                      <span className="shrink-0 tabular-nums font-bold text-[#00FF41] px-2">
                        {match.home_goals} — {match.away_goals}
                      </span>
                      <span className="flex-1 text-[#00FF41] truncate">{match.away_team_name}</span>
                    </div>
                    <div className="mt-1.5 font-headline text-[0.6rem] text-[#00FF41]/70 text-center normal-case">
                      {new Date(match.played_at).toLocaleDateString("en-GB", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                      {" · "}
                      {match.goals
                        .filter((goal) => goal.player_name)
                        .map((goal) => `${goal.player_name} ${goal.minute}'`)
                        .join(" · ") || "—"}
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </Panel>
      )}

      <div className="h-8" />
    </div>
  );
}
