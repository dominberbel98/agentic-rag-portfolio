import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import { useT } from "../i18n";
import {
  FORM_COLORS,
  LEGEND_ZONES,
  formatDateTime,
  formatGoalDifference,
  formatKickoff,
  zoneColor,
} from "../lib/laliga";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";
// `const L = tr.laliga` used to live here as a module-level alias. It froze the
// labels at import time, which is invisible with one language and wrong with two.

/* ────────── custom tooltip ────────── */
const CrtTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
      <p className="font-bold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || GREEN }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

/* ────────── empty state, shared by every panel ────────── */
const EmptyPanel = ({ title, icon, message }) => (
  <div className="viz-panel col-span-12">
    <h3 className="viz-title">
      <span className="material-symbols-outlined text-sm mr-2">{icon}</span>
      {title}
    </h3>
    <p className="text-[0.7rem] text-[#00FF41]/65 font-headline uppercase py-6 text-center">
      {message}
    </p>
  </div>
);

/* ═══════════ 1. STANDINGS TABLE ═══════════ */
function StandingsTable({ data }) {
  const tr = useT();
  const L = tr.laliga;
  const S = L.standings;
  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">leaderboard</span>
        {S.title}
      </h3>
      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-[0.7rem] sm:text-xs font-headline uppercase">
          <thead>
            <tr className="text-[#00FF41]/70 border-b border-[#00FF41]/10">
              <th className="py-2 px-1 text-left">{S.pos}</th>
              <th className="py-2 px-2 text-left">{S.team}</th>
              <th className="py-2 px-1 text-center">{S.played}</th>
              <th className="py-2 px-1 text-center">{S.won}</th>
              <th className="py-2 px-1 text-center">{S.drawn}</th>
              <th className="py-2 px-1 text-center">{S.lost}</th>
              <th className="py-2 px-1 text-center">{S.goalsFor}</th>
              <th className="py-2 px-1 text-center">{S.goalsAgainst}</th>
              <th className="py-2 px-1 text-center">{S.goalDifference}</th>
              <th className="py-2 px-1 text-center font-bold">{S.points}</th>
              <th className="py-2 px-2 text-center" title={S.formTooltip}>{S.form}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((team) => (
              <tr
                key={team.teamId}
                className="border-b border-[#00FF41]/5 hover:bg-[#00FF41]/5 transition-colors"
                style={{ borderLeftColor: zoneColor(team.zone), borderLeftWidth: 3 }}
              >
                <td className="py-1.5 px-1 text-center" style={{ color: zoneColor(team.zone) }}>
                  {team.position}
                </td>
                <td className="py-1.5 px-2 flex items-center gap-2">
                  <img src={team.teamCrest} alt="" className="w-5 h-5 object-contain" loading="lazy" />
                  <span className="truncate max-w-[120px] sm:max-w-none text-[#00FF41]/90">
                    {team.teamShortName || team.teamName}
                  </span>
                </td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/70">{team.playedGames}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/70">{team.won}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/70">{team.draw}</td>
                <td className="py-1.5 px-1 text-center text-[#FF4136]">{team.lost}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/60">{team.goalsFor}</td>
                <td className="py-1.5 px-1 text-center text-[#FF4136]">{team.goalsAgainst}</td>
                <td
                  className="py-1.5 px-1 text-center"
                  style={{ color: team.goalDifference >= 0 ? GREEN : "#FF4136" }}
                >
                  {formatGoalDifference(team.goalDifference)}
                </td>
                <td className="py-1.5 px-1 text-center font-bold text-[#00FF41]">{team.points}</td>
                <td className="py-1.5 px-2 text-center">
                  {team.form ? (
                    <span className="inline-flex gap-[3px]">
                      {team.form.split("").map((result, i) => (
                        <span
                          key={i}
                          title={result}
                          className="w-[14px] h-[14px] leading-[14px] text-[0.55rem] font-bold rounded-sm"
                          style={{
                            background: `${FORM_COLORS[result] ?? DIM}22`,
                            color: FORM_COLORS[result] ?? DIM,
                            border: `1px solid ${FORM_COLORS[result] ?? DIM}55`,
                          }}
                        >
                          {result}
                        </span>
                      ))}
                    </span>
                  ) : (
                    <span className="text-[#00FF41]/55">{S.formEmpty}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-3 sm:gap-4 mt-3 text-[0.6rem] text-[#00FF41]/65 font-headline uppercase">
        {LEGEND_ZONES.map((zone) => (
          <span key={zone} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: zoneColor(zone) }} />
            {tr.zones[zone]}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ═══════════ 2. POINTS BAR CHART ═══════════ */
function PointsDistribution({ data }) {
  const L = useT().laliga;
  const sorted = [...data].sort((a, b) => b.points - a.points);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">bar_chart</span>
        {L.points.title}
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis
            type="category"
            dataKey="teamShortName"
            tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }}
            width={55}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="points" name={L.points.label} radius={[0, 4, 4, 0]}>
            {sorted.map((team) => (
              <Cell key={team.teamId} fill={zoneColor(team.zone)} fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 3. ATTACK vs DEFENCE SCATTER ═══════════ */
function AttackVsDefence({ data }) {
  const L = useT().laliga;
  const A = L.attackDefence;
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">scatter_plot</span>
        {A.title}
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ left: 10, right: 20, top: 20, bottom: 20 }}>
          <XAxis
            type="number" dataKey="goalsFor" name={A.goalsFor}
            tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
            label={{ value: A.xLabel, position: "insideBottomRight", fill: DIM, fontSize: 10, offset: -5 }}
          />
          <YAxis
            type="number" dataKey="goalsAgainst" name={A.goalsAgainst}
            tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
            label={{ value: A.yLabel, position: "insideTopLeft", fill: DIM, fontSize: 10, offset: -5 }}
          />
          <ZAxis type="number" dataKey="points" range={[60, 400]} name={A.points} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
                  <p className="font-bold">{d.teamShortName}</p>
                  <p>{L.standings.goalsFor}: {d.goalsFor} | {L.standings.goalsAgainst}: {d.goalsAgainst}</p>
                  <p>{A.points}: {d.points}</p>
                </div>
              );
            }}
          />
          <Scatter data={data} shape="circle">
            {data.map((team) => (
              <Cell
                key={team.teamId}
                fill={zoneColor(team.zone)}
                fillOpacity={0.8}
                stroke={zoneColor(team.zone)}
                strokeWidth={1}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-1 uppercase">{A.caption}</p>
    </div>
  );
}

/* ═══════════ 4. GOAL DIFFERENCE DIVERGING BAR ═══════════ */
function GoalDiffSpectrum({ data }) {
  const L = useT().laliga;
  const sorted = [...data].sort((a, b) => b.goalDifference - a.goalDifference);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">swap_horiz</span>
        {L.goalDiff.title}
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis
            type="category" dataKey="teamShortName"
            tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }}
            width={55} axisLine={false} tickLine={false}
          />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="goalDifference" name={L.goalDiff.label} radius={[0, 4, 4, 0]}>
            {sorted.map((team) => (
              <Cell
                key={team.teamId}
                fill={team.goalDifference >= 0 ? GREEN : "#FF4136"}
                fillOpacity={0.65}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 5. RESULT RATE MATRIX ═══════════ */
function ResultRateMatrix({ data }) {
  const L = useT().laliga;
  const sorted = [...data].sort((a, b) => a.position - b.position);
  const W = L.winRate;
  const legend = [
    [W.win, GREEN, 0.7],
    [W.draw, "#FFD700", 0.5],
    [W.loss, "#FF4136", 0.5],
  ];
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">grid_on</span>
        {W.title}
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
          <XAxis
            type="number" domain={[0, 100]}
            tickFormatter={(v) => `${Math.round(v)}%`}
            tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
          />
          <YAxis
            type="category" dataKey="teamShortName"
            tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }}
            width={55} axisLine={false} tickLine={false}
          />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="winRate" name={W.win} stackId="rate" fill={GREEN} fillOpacity={0.7} />
          <Bar dataKey="drawRate" name={W.draw} stackId="rate" fill="#FFD700" fillOpacity={0.5} />
          <Bar dataKey="lossRate" name={W.loss} stackId="rate" fill="#FF4136" fillOpacity={0.5} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 text-[0.6rem] text-[#00FF41]/65 font-headline uppercase">
        {legend.map(([label, color, opacity]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ background: color, opacity }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ═══════════ 6. TOP-5 RADAR ═══════════ */
function Top5Radar({ data }) {
  const L = useT().laliga;
  const R = L.radar;
  const top5 = [...data].sort((a, b) => a.position - b.position).slice(0, 5);
  const metrics = ["won", "draw", "lost", "goalsFor", "goalsAgainst"];
  const colors = [GREEN, "#00BFFF", "#FFD700", "#FF6B6B", "#A78BFA"];

  // Normalise each axis across the top 5 only — which is what the caption now
  // says. It previously claimed the top 5 while normalising across all 20.
  const maxima = {};
  metrics.forEach((m) => {
    maxima[m] = Math.max(...top5.map((team) => team[m] || 0), 1);
  });

  const radarData = metrics.map((metric) => {
    const entry = { metric: R[metric] };
    top5.forEach((team) => {
      entry[team.teamShortName] = Math.round(((team[metric] || 0) / maxima[metric]) * 100);
      entry[`${team.teamShortName}_raw`] = team[metric] || 0;
    });
    return entry;
  });

  const RadarTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
        <p className="font-bold mb-1">{label}</p>
        {payload.map((p, i) => {
          const raw = p.payload[`${p.name}_raw`];
          return (
            <p key={i} style={{ color: p.color || GREEN }}>
              {p.name}: {raw != null ? raw : p.value}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">radar</span>
        {R.title}
      </h3>
      <ResponsiveContainer width="100%" height={380}>
        <RadarChart data={radarData} outerRadius="70%">
          <PolarGrid stroke="rgba(0,255,65,0.15)" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: GREEN, fontSize: 10, fontFamily: "Space Grotesk" }} />
          <PolarRadiusAxis tick={false} axisLine={false} />
          {top5.map((team, i) => (
            <Radar
              key={team.teamId}
              name={team.teamShortName}
              dataKey={team.teamShortName}
              stroke={colors[i]}
              fill={colors[i]}
              fillOpacity={0.1}
              strokeWidth={2}
            />
          ))}
          <Tooltip content={<RadarTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 mt-2 text-[0.6rem] font-headline uppercase">
        {top5.map((team, i) => (
          <span key={team.teamId} className="flex items-center gap-1" style={{ color: colors[i] }}>
            <span className="w-2 h-2 rounded-full" style={{ background: colors[i] }} />
            {team.teamShortName}
          </span>
        ))}
      </div>
      <p className="text-[0.6rem] text-[#00FF41]/55 font-headline mt-1 uppercase">{R.caption}</p>
    </div>
  );
}

/* ═══════════ 7. LATEST RESULTS ═══════════ */
function LatestResults({ results }) {
  const L = useT().laliga;
  const R = L.results;
  if (!results.length) {
    return <EmptyPanel title={R.title} icon="sports_soccer" message={R.empty} />;
  }
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">sports_soccer</span>
        {R.title}
      </h3>
      <div className="flex flex-col divide-y divide-[#00FF41]/5">
        {results.slice(0, 10).map((match) => (
          <div key={match.id} className="flex items-center gap-2 py-2 text-[0.7rem] font-headline uppercase">
            <span className="text-[#00FF41]/60 w-9 shrink-0">{R.matchdayShort(match.matchday)}</span>
            <span className="flex-1 text-right truncate text-[#00FF41]/80">{match.homeName}</span>
            <span className="px-2 font-bold text-[#00FF41] tabular-nums">
              {match.homeGoals}–{match.awayGoals}
            </span>
            <span className="flex-1 truncate text-[#00FF41]/80">{match.awayName}</span>
            {match.live && (
              <span className="text-[0.55rem] text-[#FF4136] flicker shrink-0">{R.live}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════ 8. UPCOMING FIXTURES ═══════════ */
function UpcomingFixtures({ fixtures }) {
  const L = useT().laliga;
  const F = L.fixtures;
  if (!fixtures.length) {
    return <EmptyPanel title={F.title} icon="event" message={F.empty} />;
  }
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">event</span>
        {F.title}
      </h3>
      <div className="flex flex-col divide-y divide-[#00FF41]/5">
        {fixtures.slice(0, 10).map((match) => (
          <div key={match.id} className="flex items-center gap-2 py-2 text-[0.7rem] font-headline uppercase">
            <span className="flex-1 text-right truncate text-[#00FF41]/80">{match.homeName}</span>
            <span className="px-2 text-[#00FF41]/60">vs</span>
            <span className="flex-1 truncate text-[#00FF41]/80">{match.awayName}</span>
            <span className="text-[0.55rem] text-[#00FF41]/60 shrink-0 w-[110px] text-right">
              {formatKickoff(match.kickoff)}
            </span>
          </div>
        ))}
      </div>
      <p className="text-[0.6rem] text-[#00FF41]/55 font-headline mt-2 uppercase">{F.caption}</p>
    </div>
  );
}

/* ═══════════ MAIN EXPORT ═══════════ */
export default function Visualizaciones() {
  const tr = useT();
  const L = tr.laliga;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/data/la_liga_data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-[#FF4136] font-headline text-sm uppercase">
        {L.error}: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          {L.loading}<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const standings = data.standings || [];
  const results = data.results || [];
  const fixtures = data.fixtures || [];
  // `state` is absent from data written before the pipeline emitted it, so the
  // component must not assume it — a stale deploy should still render.
  const state = data.state || {};
  const preseason = state.phase === "preseason";

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          {L.title}
        </h2>
        <p className="text-[0.65rem] text-[#00FF41]/65 font-headline uppercase mt-1">
          {tr.common.season} {data.season} · {tr.common.matchday} {data.matchday}
          {state.phase ? ` · ${tr.seasonPhase[state.phase]}` : ""} · {tr.common.updated}:{" "}
          {formatDateTime(data.updatedAt)}
        </p>
        <p className="text-[0.6rem] text-[#00FF41]/55 font-headline uppercase mt-0.5">
          {L.pipeline}
        </p>
      </div>

      {/* Season-state notices. The site showed a finished season's table as the
          current one for days, so an empty or barely-started season says so. */}
      {preseason && (
        <div className="mb-4 border border-[#FFD700]/30 bg-[#FFD700]/5 px-4 py-2 text-[0.7rem] text-[#FFD700]/80 font-headline uppercase">
          {L.preseasonNotice}
        </div>
      )}
      {!preseason && state.lowConfidence && (
        <div className="mb-4 border border-[#FFD700]/20 bg-[#FFD700]/5 px-4 py-2 text-[0.7rem] text-[#FFD700]/70 font-headline uppercase">
          {L.lowConfidenceNotice(state.maxGamesPlayed ?? 0)}
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-12 gap-4">
        <StandingsTable data={standings} />
        <LatestResults results={results} />
        <UpcomingFixtures fixtures={fixtures} />
        <PointsDistribution data={standings} />
        <AttackVsDefence data={standings} />
        <GoalDiffSpectrum data={standings} />
        <ResultRateMatrix data={standings} />
        <Top5Radar data={standings} />
      </div>

      {/* Bottom spacer for footer */}
      <div className="h-8" />
    </div>
  );
}
