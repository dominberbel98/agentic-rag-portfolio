import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis,
  ErrorBar,
} from "recharts";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";
const ZONE_COLORS = {
  champions: "#00FF41",
  europa: "#00BFFF",
  relegation: "#FF4136",
  mid: "rgba(0,255,65,0.25)",
};

function zoneFromPos(pos) {
  if (pos <= 4) return "champions";
  if (pos <= 6) return "europa";
  if (pos >= 18) return "relegation";
  return "mid";
}

/* ────────── CRT tooltip ────────── */
const CrtTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
      <p className="font-bold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || GREEN }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
        </p>
      ))}
    </div>
  );
};

/* ═══════════ 1. CHAMPION PROBABILITY BAR ═══════════ */
function ChampionProb({ data }) {
  const filtered = data.filter((t) => t.championProb > 0);
  // If only one team has prob, show top 5 anyway for context
  const show = filtered.length > 1 ? filtered : data.slice(0, 5);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">emoji_events</span>
        PROBABILIDAD_CAMPEÓN
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(200, show.length * 45)}>
        <BarChart data={show} layout="vertical" margin={{ left: 70, right: 30, top: 5, bottom: 5 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: DIM, fontSize: 10 }} unit="%" axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="teamShortName" tick={{ fill: GREEN, fontSize: 10, fontFamily: "Space Grotesk" }} width={65} axisLine={false} tickLine={false} />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="championProb" name="P(Campeón)" radius={[0, 4, 4, 0]}>
            {show.map((t, i) => (
              <Cell key={i} fill={GREEN} fillOpacity={Math.max(0.2, t.championProb / 100)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 2. PROJECTED POINTS with confidence ═══════════ */
function ProjectedPoints({ data }) {
  const chartData = data.map((t) => ({
    ...t,
    errorLow: t.mc.pointsMean - t.mc.pointsP10,
    errorHigh: t.mc.pointsP90 - t.mc.pointsMean,
    zone: zoneFromPos(t.currentPosition),
  }));

  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">trending_up</span>
        PUNTOS_PROYECTADOS (IC 80%)
      </h3>
      <ResponsiveContainer width="100%" height={420}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 70, right: 30, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="teamShortName" tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }} width={65} axisLine={false} tickLine={false} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
                  <p className="font-bold">{d.teamShortName}</p>
                  <p>Media: {d.mc.pointsMean} pts</p>
                  <p>IC 80%: [{d.mc.pointsP10} – {d.mc.pointsP90}]</p>
                  <p>Rango: [{d.mc.pointsMin} – {d.mc.pointsMax}]</p>
                </div>
              );
            }}
            cursor={{ fill: "rgba(0,255,65,0.05)" }}
          />
          <Bar dataKey="mc.pointsMean" name="Pts (media)" radius={[0, 4, 4, 0]}>
            {chartData.map((t, i) => (
              <Cell key={i} fill={ZONE_COLORS[t.zone]} fillOpacity={0.65} />
            ))}
            <ErrorBar dataKey="errorHigh" direction="right" width={4} stroke={GREEN} strokeOpacity={0.5} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════ 3. MOST GOALS / LEAST CONCEDED ═══════════ */
function GoalProbabilities({ data }) {
  const topGF = [...data].sort((a, b) => b.mostGoalsProb - a.mostGoalsProb).slice(0, 5);
  const topGA = [...data].sort((a, b) => b.mostConcededProb - a.mostConcededProb).slice(0, 5);
  const topLeastGA = [...data].sort((a, b) => b.leastConcededProb - a.leastConcededProb).slice(0, 5);

  const MiniBar = ({ items, dataKey, title, icon, color }) => (
    <div className="flex-1 min-w-[250px]">
      <h4 className="text-[0.65rem] font-headline uppercase text-[#00FF41]/60 mb-2 flex items-center gap-1">
        <span className="material-symbols-outlined text-xs">{icon}</span>
        {title}
      </h4>
      {items.map((t) => (
        <div key={t.teamShortName} className="flex items-center gap-2 mb-1.5">
          <img src={t.teamCrest} alt="" className="w-4 h-4" loading="lazy" />
          <span className="text-[0.6rem] text-[#00FF41]/70 font-headline w-16 truncate">{t.teamShortName}</span>
          <div className="flex-1 h-3 bg-[#00FF41]/5 rounded overflow-hidden">
            <div
              className="h-full rounded transition-all"
              style={{ width: `${t[dataKey]}%`, background: color, opacity: 0.7 }}
            />
          </div>
          <span className="text-[0.6rem] font-headline text-[#00FF41]/50 w-10 text-right">{t[dataKey]}%</span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">sports_soccer</span>
        PREDICCIONES_GOLES
      </h3>
      <div className="flex flex-wrap gap-0">
        <MiniBar items={topGF} dataKey="mostGoalsProb" title="Más goleador" icon="arrow_upward" color={GREEN} />
        <div className="w-px bg-[#00FF41]/15 mx-3 self-stretch hidden sm:block" />
        <MiniBar items={topGA} dataKey="mostConcededProb" title="Más goleado" icon="arrow_downward" color="#FF4136" />
        <div className="w-px bg-[#00FF41]/15 mx-3 self-stretch hidden sm:block" />
        <MiniBar items={topLeastGA} dataKey="leastConcededProb" title="Menos goleado" icon="shield" color="#00BFFF" />
      </div>
    </div>
  );
}

/* ═══════════ 4. XGBoost Feature Importance ═══════════ */
function FeatureImportance({ importance }) {
  if (!importance || Object.keys(importance).length === 0) return null;

  const labels = {
    ppg: "Puntos/partido",
    winRate: "% Victorias",
    drawRate: "% Empates",
    lossRate: "% Derrotas",
    gfPerGame: "GF/partido",
    gaPerGame: "GC/partido",
    gdPerGame: "DG/partido",
    points: "Puntos",
    goalDifference: "Dif. goles",
  };

  const data = Object.entries(importance)
    .map(([k, v]) => ({ feature: labels[k] || k, importance: v }))
    .sort((a, b) => b.importance - a.importance);

  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">model_training</span>
        XGBOOST_FEATURE_IMPORTANCE
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} layout="vertical" margin={{ left: 90, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="feature" tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }} width={85} axisLine={false} tickLine={false} />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="importance" name="Importancia" fill={GREEN} fillOpacity={0.6} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[0.55rem] text-[#00FF41]/25 font-headline mt-1 uppercase">
        XGBoost multi:softprob · Features normalizadas por partido
      </p>
    </div>
  );
}

/* ═══════════ 5. PROJECTED TABLE ═══════════ */
function ProjectedTable({ data }) {
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">table_chart</span>
        CLASIFICACIÓN_PROYECTADA (J38)
      </h3>
      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-[0.65rem] sm:text-xs font-headline uppercase">
          <thead>
            <tr className="text-[#00FF41]/50 border-b border-[#00FF41]/10">
              <th className="py-1.5 px-1 text-left">#</th>
              <th className="py-1.5 px-2 text-left">Equipo</th>
              <th className="py-1.5 px-1 text-center">Actual</th>
              <th className="py-1.5 px-1 text-center">Proy.</th>
              <th className="py-1.5 px-1 text-center">IC 80%</th>
              <th className="py-1.5 px-1 text-center">GF</th>
              <th className="py-1.5 px-1 text-center">GC</th>
            </tr>
          </thead>
          <tbody>
            {data.map((t, i) => {
              const zone = zoneFromPos(i + 1);
              return (
                <tr key={t.teamShortName} className="border-b border-[#00FF41]/5 hover:bg-[#00FF41]/5"
                  style={{ borderLeftColor: ZONE_COLORS[zone], borderLeftWidth: 3 }}>
                  <td className="py-1 px-1 text-center" style={{ color: ZONE_COLORS[zone] }}>{i + 1}</td>
                  <td className="py-1 px-2 flex items-center gap-1.5">
                    <img src={t.teamCrest} alt="" className="w-4 h-4" loading="lazy" />
                    <span className="text-[#00FF41]/80 truncate max-w-[90px]">{t.teamShortName}</span>
                  </td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/40">{t.currentPoints}</td>
                  <td className="py-1 px-1 text-center font-bold text-[#00FF41]">{t.mc.pointsMean}</td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/40">[{t.mc.pointsP10}–{t.mc.pointsP90}]</td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/50">{t.mc.gfMean}</td>
                  <td className="py-1 px-1 text-center text-[#FF4136]/50">{t.mc.gaMean}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ═══════════ MAIN EXPORT ═══════════ */
export default function ModelosPredictivos() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/data/la_liga_predictions.json")
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
        ERROR_LOADING_PREDICTIONS: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          EJECUTANDO_MODELO<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const predictions = data.predictions || [];

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          MODELOS_PREDICTIVOS_LA_LIGA
        </h2>
        <p className="text-[0.65rem] text-[#00FF41]/40 font-headline uppercase mt-1">
          Temporada {data.season} · Jornada {data.matchday} · {data.totalMatches} jornadas totales · {data.nSimulations.toLocaleString()} simulaciones
        </p>
        <p className="text-[0.6rem] text-[#00FF41]/25 font-headline uppercase mt-0.5">
          Modelo: {data.model} · Poisson(λ=GF/partido) + {data.nSimulations.toLocaleString()} Monte Carlo seasons
        </p>
      </div>

      {/* Method explanation */}
      <div className="viz-panel col-span-12 mb-4">
        <h3 className="viz-title">
          <span className="material-symbols-outlined text-sm mr-2">psychology</span>
          METODOLOGÍA
        </h3>
        <div className="text-[0.65rem] text-[#00FF41]/60 font-headline leading-relaxed space-y-1">
          <p><span className="text-[#00FF41]">1.</span> Feature engineering: ratios por partido (ppg, win%, GF/G, GA/G, GD/G)</p>
          <p><span className="text-[#00FF41]">2.</span> Simulación Poisson: para cada partido restante, GF ~ Poisson(λ_gf), GA ~ Poisson(λ_ga) → resultado → puntos</p>
          <p><span className="text-[#00FF41]">3.</span> Monte Carlo: {data.nSimulations.toLocaleString()} temporadas simuladas → distribución de puntos, goles, clasificación</p>
          <p><span className="text-[#00FF41]">4.</span> XGBoost (multi:softprob): clasificador de zona (Champions/Europa/Mid/Descenso) sobre features actuales</p>

        </div>
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-12 gap-4">
        <ChampionProb data={predictions} />
        <ProjectedPoints data={predictions} />
        <GoalProbabilities data={predictions} />
        <FeatureImportance importance={data.xgbFeatureImportance} />
        <ProjectedTable data={predictions} />
      </div>

      <div className="h-8" />
    </div>
  );
}
