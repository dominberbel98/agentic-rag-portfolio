import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";
const BG = "#0e0e0e";
const ZONE_COLORS = {
  champions: "#00FF41",
  europa: "#00BFFF",
  relegation: "#FF4136",
  mid: "rgba(0,255,65,0.25)",
};

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

/* ═══════════ 1. CLASIFICACION TABLE ═══════════ */
function ClasificacionTable({ data }) {
  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">leaderboard</span>
        CLASIFICACIÓN_LIVE
      </h3>
      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-[0.7rem] sm:text-xs font-headline uppercase">
          <thead>
            <tr className="text-[#00FF41]/50 border-b border-[#00FF41]/10">
              <th className="py-2 px-1 text-left">#</th>
              <th className="py-2 px-2 text-left">Equipo</th>
              <th className="py-2 px-1 text-center">PJ</th>
              <th className="py-2 px-1 text-center">V</th>
              <th className="py-2 px-1 text-center">E</th>
              <th className="py-2 px-1 text-center">D</th>
              <th className="py-2 px-1 text-center">GF</th>
              <th className="py-2 px-1 text-center">GC</th>
              <th className="py-2 px-1 text-center">DG</th>
              <th className="py-2 px-1 text-center font-bold">PTS</th>
            </tr>
          </thead>
          <tbody>
            {data.map((t) => (
              <tr
                key={t.position}
                className="border-b border-[#00FF41]/5 hover:bg-[#00FF41]/5 transition-colors"
                style={{ borderLeftColor: ZONE_COLORS[t.zone], borderLeftWidth: 3 }}
              >
                <td className="py-1.5 px-1 text-center" style={{ color: ZONE_COLORS[t.zone] }}>{t.position}</td>
                <td className="py-1.5 px-2 flex items-center gap-2">
                  <img src={t.teamCrest} alt="" className="w-5 h-5 object-contain" loading="lazy" />
                  <span className="truncate max-w-[120px] sm:max-w-none text-[#00FF41]/90">{t.teamShortName || t.teamName}</span>
                </td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/50">{t.playedGames}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/70">{t.won}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/50">{t.draw}</td>
                <td className="py-1.5 px-1 text-center text-[#FF4136]/70">{t.lost}</td>
                <td className="py-1.5 px-1 text-center text-[#00FF41]/60">{t.goalsFor}</td>
                <td className="py-1.5 px-1 text-center text-[#FF4136]/50">{t.goalsAgainst}</td>
                <td className="py-1.5 px-1 text-center" style={{ color: t.goalDifference >= 0 ? GREEN : "#FF4136" }}>
                  {t.goalDifference > 0 ? "+" : ""}{t.goalDifference}
                </td>
                <td className="py-1.5 px-1 text-center font-bold text-[#00FF41]">{t.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex gap-4 mt-3 text-[0.6rem] text-[#00FF41]/40 font-headline uppercase">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: ZONE_COLORS.champions }} />Champions</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: ZONE_COLORS.europa }} />Europa</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: ZONE_COLORS.relegation }} />Descenso</span>
      </div>
    </div>
  );
}

/* ═══════════ 2. POINTS BAR CHART ═══════════ */
function PointsDistribution({ data }) {
  const sorted = [...data].sort((a, b) => b.points - a.points);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">bar_chart</span>
        DISTRIBUCIÓN_PUNTOS
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
          <Bar dataKey="points" name="Puntos" radius={[0, 4, 4, 0]}>
            {sorted.map((t, i) => (
              <Cell key={i} fill={ZONE_COLORS[t.zone]} fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 3. ATTACK vs DEFENSE SCATTER ═══════════ */
function AttackVsDefense({ data }) {
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">scatter_plot</span>
        ATAQUE_VS_DEFENSA
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ left: 10, right: 20, top: 20, bottom: 20 }}>
          <XAxis
            type="number" dataKey="goalsFor" name="Goles a favor"
            tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
            label={{ value: "GF →", position: "insideBottomRight", fill: DIM, fontSize: 10, offset: -5 }}
          />
          <YAxis
            type="number" dataKey="goalsAgainst" name="Goles en contra"
            tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
            label={{ value: "GC →", position: "insideTopLeft", fill: DIM, fontSize: 10, offset: -5 }}
          />
          <ZAxis type="number" dataKey="points" range={[60, 400]} name="Puntos" />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
                  <p className="font-bold">{d.teamShortName}</p>
                  <p>GF: {d.goalsFor} | GC: {d.goalsAgainst}</p>
                  <p>Puntos: {d.points}</p>
                </div>
              );
            }}
          />
          <Scatter data={data} shape="circle">
            {data.map((t, i) => (
              <Cell key={i} fill={ZONE_COLORS[t.zone]} fillOpacity={0.8} stroke={ZONE_COLORS[t.zone]} strokeWidth={1} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <p className="text-[0.6rem] text-[#00FF41]/30 font-headline mt-1 uppercase">
        Tamaño burbuja = puntos · Ideal: arriba-derecha (muchos GF, pocos GC)
      </p>
    </div>
  );
}

/* ═══════════ 4. GOAL DIFFERENCE DIVERGING BAR ═══════════ */
function GoalDiffSpectrum({ data }) {
  const sorted = [...data].sort((a, b) => b.goalDifference - a.goalDifference);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">swap_horiz</span>
        DIFERENCIA_GOLES_SPECTRUM
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
          <Bar dataKey="goalDifference" name="DG" radius={[0, 4, 4, 0]}>
            {sorted.map((t, i) => (
              <Cell key={i} fill={t.goalDifference >= 0 ? GREEN : "#FF4136"} fillOpacity={0.65} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 5. WIN RATE HEATMAP (stacked bar) ═══════════ */
function WinRateMatrix({ data }) {
  const sorted = [...data].sort((a, b) => a.position - b.position);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">grid_on</span>
        WIN_RATE_MATRIX
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} unit="%" />
          <YAxis
            type="category" dataKey="teamShortName"
            tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }}
            width={55} axisLine={false} tickLine={false}
          />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="winRate" name="Win%" stackId="rate" fill={GREEN} fillOpacity={0.7} />
          <Bar dataKey="drawRate" name="Draw%" stackId="rate" fill="#FFD700" fillOpacity={0.5} />
          <Bar dataKey="lossRate" name="Loss%" stackId="rate" fill="#FF4136" fillOpacity={0.5} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 text-[0.6rem] text-[#00FF41]/40 font-headline uppercase">
        <span className="flex items-center gap-1"><span className="w-2 h-2" style={{ background: GREEN, opacity: 0.7 }} />Win%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2" style={{ background: "#FFD700", opacity: 0.5 }} />Draw%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2" style={{ background: "#FF4136", opacity: 0.5 }} />Loss%</span>
      </div>
    </div>
  );
}

/* ═══════════ 6. TOP-5 RADAR ═══════════ */
function Top5Radar({ data }) {
  const top5 = [...data].sort((a, b) => a.position - b.position).slice(0, 5);
  const metrics = ["won", "draw", "lost", "goalsFor", "goalsAgainst"];
  const labels = { won: "Victorias", draw: "Empates", lost: "Derrotas", goalsFor: "GF", goalsAgainst: "GC" };
  const colors = [GREEN, "#00BFFF", "#FFD700", "#FF6B6B", "#A78BFA"];

  // Normalise each metric to 0-100 across all 20 teams, keep raw for tooltip
  const maxVals = {};
  metrics.forEach((m) => {
    maxVals[m] = Math.max(...data.map((t) => t[m] || 0), 1);
  });

  const radarData = metrics.map((m) => {
    const entry = { metric: labels[m] };
    top5.forEach((t) => {
      entry[t.teamShortName] = Math.round(((t[m] || 0) / maxVals[m]) * 100);
      entry[`${t.teamShortName}_raw`] = t[m] || 0;
    });
    return entry;
  });

  const RadarTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
        <p className="font-bold mb-1">{label}</p>
        {payload.map((p, i) => {
          const rawKey = `${p.name}_raw`;
          const raw = p.payload[rawKey];
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
        RADAR_TOP5
      </h3>
      <ResponsiveContainer width="100%" height={380}>
        <RadarChart data={radarData} outerRadius="70%">
          <PolarGrid stroke="rgba(0,255,65,0.15)" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: GREEN, fontSize: 10, fontFamily: "Space Grotesk" }} />
          <PolarRadiusAxis tick={false} axisLine={false} />
          {top5.map((t, i) => (
            <Radar
              key={t.teamShortName}
              name={t.teamShortName}
              dataKey={t.teamShortName}
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
        {top5.map((t, i) => (
          <span key={t.teamShortName} className="flex items-center gap-1" style={{ color: colors[i] }}>
            <span className="w-2 h-2 rounded-full" style={{ background: colors[i] }} />
            {t.teamShortName}
          </span>
        ))}
      </div>
      <p className="text-[0.6rem] text-[#00FF41]/25 font-headline mt-1 uppercase">
        Ejes normalizados dentro del Top 5 · Mayor área = mejor rendimiento · Solidez def. = menos GC
      </p>
    </div>
  );
}

/* ═══════════ MAIN EXPORT ═══════════ */
export default function Visualizaciones() {
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
        ERROR_LOADING_DATA: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          CARGANDO_DATOS_LA_LIGA<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const standings = data.standings || [];

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          LA_LIGA_DASHBOARD
        </h2>
        <p className="text-[0.65rem] text-[#00FF41]/40 font-headline uppercase mt-1">
          Temporada {data.season} · Jornada {data.matchday} · Actualizado:{" "}
          {new Date(data.updatedAt).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" })}
        </p>
        <p className="text-[0.6rem] text-[#00FF41]/25 font-headline uppercase mt-0.5">
          Pipeline: PySpark → GitHub Actions (30 min) → SportsRC API
        </p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-12 gap-4">
        <ClasificacionTable data={standings} />
        <PointsDistribution data={standings} />
        <AttackVsDefense data={standings} />
        <GoalDiffSpectrum data={standings} />
        <WinRateMatrix data={standings} />
        <Top5Radar data={standings} />
      </div>

      {/* Bottom spacer for footer */}
      <div className="h-8" />
    </div>
  );
}
