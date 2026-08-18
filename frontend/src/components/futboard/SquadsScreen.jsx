import React, { useState } from "react";
import { Button, EmptyState, ListRow, Notice, Panel, ScreenHeader, TextField } from "./ui";

/**
 * Teams and players.
 *
 * The data model this reflects: a team is created once and then chosen, players
 * live in one global registry, and a player can belong to several squads. So the
 * screen is two lists plus a squad editor, rather than players nested under a
 * team — nesting would imply an ownership that does not exist.
 *
 * One column on a phone, two from `lg`.
 */
export default function SquadsScreen({ f, teams, players, onBack, onCreateTeam, onCreatePlayer, onAddToTeam, onRemoveFromTeam }) {
  const [teamName, setTeamName] = useState("");
  const [playerName, setPlayerName] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const selectedTeam = teams.find((t) => t.id === selectedTeamId) || null;
  const squad = selectedTeam ? players.filter((p) => p.team_ids.includes(selectedTeam.id)) : [];
  const outsiders = selectedTeam
    ? players.filter((p) => !p.team_ids.includes(selectedTeam.id))
    : [];

  const run = async (action) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (exc) {
      setError(exc.message);
    } finally {
      setBusy(false);
    }
  };

  const teamNameOf = (player) =>
    player.team_ids
      .map((id) => teams.find((t) => t.id === id)?.name)
      .filter(Boolean)
      .join(", ") || f.squads.noTeams;

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <ScreenHeader title={f.squads.title} onBack={onBack} backLabel={f.back} />

      {error && (
        <div className="mb-3">
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Teams */}
        <Panel title={f.squads.teams} icon="groups">
          <div className="flex gap-2 mb-3">
            <TextField
              value={teamName}
              onChange={setTeamName}
              placeholder={f.squads.teamName}
              onSubmit={() =>
                teamName.trim() &&
                run(async () => {
                  await onCreateTeam(teamName.trim());
                  setTeamName("");
                })
              }
            />
            <Button
              variant="primary"
              icon="add"
              disabled={busy || !teamName.trim()}
              onClick={() =>
                run(async () => {
                  await onCreateTeam(teamName.trim());
                  setTeamName("");
                })
              }
            >
              {f.squads.create}
            </Button>
          </div>

          {teams.length === 0 ? (
            <EmptyState icon="groups">{f.squads.emptyTeams}</EmptyState>
          ) : (
            <div className="space-y-1.5">
              {teams.map((team) => (
                <ListRow
                  key={team.id}
                  active={team.id === selectedTeamId}
                  onClick={() => setSelectedTeamId(team.id === selectedTeamId ? null : team.id)}
                >
                  <span className="material-symbols-outlined text-[1.1rem] text-[#00FF41]/75">
                    shield
                  </span>
                  <span className="flex-1 font-headline text-[0.9rem] text-[#00FF41] truncate">
                    {team.name}
                  </span>
                  <span className="font-headline text-[0.75rem] text-[#00FF41]/70 shrink-0">
                    {f.squads.playerCount(team.player_count)}
                  </span>
                </ListRow>
              ))}
            </div>
          )}
        </Panel>

        {/* Players */}
        <Panel title={f.squads.players} icon="person">
          <div className="flex gap-2 mb-3">
            <TextField
              value={playerName}
              onChange={setPlayerName}
              placeholder={f.squads.playerName}
              onSubmit={() =>
                playerName.trim() &&
                run(async () => {
                  await onCreatePlayer(playerName.trim(), selectedTeamId);
                  setPlayerName("");
                })
              }
            />
            <Button
              variant="primary"
              icon="add"
              disabled={busy || !playerName.trim()}
              onClick={() =>
                run(async () => {
                  await onCreatePlayer(playerName.trim(), selectedTeamId);
                  setPlayerName("");
                })
              }
            >
              {f.squads.create}
            </Button>
          </div>

          {players.length === 0 ? (
            <EmptyState icon="person">{f.squads.emptyPlayers}</EmptyState>
          ) : (
            <div className="space-y-1.5 max-h-[340px] overflow-y-auto scrollbar-hide pr-1">
              {players.map((player) => (
                <ListRow key={player.id}>
                  <span className="material-symbols-outlined text-[1.1rem] text-[#00FF41]/75">
                    person
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block font-headline text-[0.9rem] text-[#00FF41] truncate">
                      {player.name}
                    </span>
                    <span className="block font-headline text-[0.74rem] text-[#00FF41]/70 truncate normal-case">
                      {f.squads.playsFor}: {teamNameOf(player)}
                    </span>
                  </span>
                </ListRow>
              ))}
            </div>
          )}
        </Panel>

        {/* Squad editor for the selected team */}
        <div className="lg:col-span-2">
          <Panel
            title={selectedTeam ? f.squads.squadOf(selectedTeam.name) : f.squads.teams}
            icon="checklist"
          >
            {!selectedTeam ? (
              <EmptyState icon="touch_app">{f.squads.selectTeamHint}</EmptyState>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <p className="font-headline uppercase text-[0.75rem] tracking-widest text-[#00FF41]/70 mb-2">
                    {f.squads.teams} · {f.squads.playerCount(squad.length)}
                  </p>
                  {squad.length === 0 ? (
                    <EmptyState icon="person_off">{f.squads.emptySquad}</EmptyState>
                  ) : (
                    <div className="space-y-1.5">
                      {squad.map((player) => (
                        <ListRow key={player.id}>
                          <span className="flex-1 font-headline text-[0.88rem] text-[#00FF41] truncate">
                            {player.name}
                          </span>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              run(() => onRemoveFromTeam(selectedTeam.id, player.id))
                            }
                            title={f.squads.remove}
                            aria-label={f.squads.remove}
                            className="shrink-0 w-9 h-9 flex items-center justify-center rounded text-[#FF4136] hover:bg-[#FF4136]/15 active:scale-95"
                          >
                            <span className="material-symbols-outlined text-[1.1rem]">close</span>
                          </button>
                        </ListRow>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="font-headline uppercase text-[0.75rem] tracking-widest text-[#00FF41]/70 mb-2">
                    {f.squads.addPlayer}
                  </p>
                  {outsiders.length === 0 ? (
                    <EmptyState icon="done_all">{f.squads.alreadyIn}</EmptyState>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {outsiders.map((player) => (
                        <button
                          key={player.id}
                          type="button"
                          disabled={busy}
                          onClick={() => run(() => onAddToTeam(selectedTeam.id, player.id))}
                          className="inline-flex items-center gap-1 min-h-[40px] px-3 border border-[#00FF41]/25 rounded font-headline text-[0.84rem] text-[#00FF41]/85 hover:bg-[#00FF41]/10 hover:text-[#00FF41] active:scale-95 disabled:opacity-40"
                        >
                          <span className="material-symbols-outlined text-[1rem]">add</span>
                          {player.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className="h-8" />
    </div>
  );
}
