import React, { useEffect, useState } from "react";
import { useT } from "../i18n";
import { ZONE_COLORS, zoneForPosition } from "../lib/laliga";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis,
  ErrorBar,
} from "recharts";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";

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
  const tr = useT();
  const filtered = data.filter((t) => t.championProb > 0);
  // If only one team has prob, show top 5 anyway for context
  const show = filtered.length > 1 ? filtered : data.slice(0, 5);
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">emoji_events</span>
        {tr.predictions.championProb.title}
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(200, show.length * 45)}>
        <BarChart data={show} layout="vertical" margin={{ left: 70, right: 30, top: 5, bottom: 5 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: DIM, fontSize: 10 }} unit="%" axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="teamShortName" tick={{ fill: GREEN, fontSize: 10, fontFamily: "Space Grotesk" }} width={65} axisLine={false} tickLine={false} />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="championProb" name={tr.predictions.championProb.label} radius={[0, 4, 4, 0]}>
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
  const tr = useT();
  const chartData = data.map((t) => ({
    ...t,
    errorLow: t.mc.pointsMean - t.mc.pointsP10,
    errorHigh: t.mc.pointsP90 - t.mc.pointsMean,
    zone: zoneForPosition(t.currentPosition),
  }));

  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">trending_up</span>
        {tr.predictions.projectedPoints.title}
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
                  <p>{tr.predictions.projectedPoints.meanLabel}: {d.mc.pointsMean} pts</p>
                  <p>IC 80%: [{d.mc.pointsP10} – {d.mc.pointsP90}]</p>
                  <p>{tr.predictions.projectedPoints.range}: [{d.mc.pointsMin} – {d.mc.pointsMax}]</p>
                </div>
              );
            }}
            cursor={{ fill: "rgba(0,255,65,0.05)" }}
          />
          <Bar dataKey="mc.pointsMean" name={tr.predictions.projectedPoints.mean} radius={[0, 4, 4, 0]}>
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
  const tr = useT();
  const topGF = [...data].sort((a, b) => b.mostGoalsProb - a.mostGoalsProb).slice(0, 5);
  const topGA = [...data].sort((a, b) => b.mostConcededProb - a.mostConcededProb).slice(0, 5);
  const topLeastGA = [...data].sort((a, b) => b.leastConcededProb - a.leastConcededProb).slice(0, 5);

  const MiniBar = ({ items, dataKey, title, icon, color }) => (
    <div className="flex-1 min-w-[250px]">
      <h4 className="text-[0.78rem] font-headline uppercase text-[#00FF41]/60 mb-2 flex items-center gap-1">
        <span className="material-symbols-outlined text-xs">{icon}</span>
        {title}
      </h4>
      {items.map((t) => (
        <div key={t.teamShortName} className="flex items-center gap-2 mb-1.5">
          <img src={t.teamCrest} alt="" className="w-4 h-4" loading="lazy" />
          <span className="text-[0.74rem] text-[#00FF41]/70 font-headline w-16 truncate">{t.teamShortName}</span>
          <div className="flex-1 h-3 bg-[#00FF41]/5 rounded overflow-hidden">
            <div
              className="h-full rounded transition-all"
              style={{ width: `${t[dataKey]}%`, background: color, opacity: 0.7 }}
            />
          </div>
          <span className="text-[0.74rem] font-headline text-[#00FF41]/70 w-10 text-right">{t[dataKey]}%</span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">sports_soccer</span>
        {tr.predictions.goals.title}
      </h3>
      <div className="flex flex-wrap gap-0">
        <MiniBar items={topGF} dataKey="mostGoalsProb" title={tr.predictions.goals.mostGoals} icon="arrow_upward" color={GREEN} />
        <div className="w-px bg-[#00FF41]/15 mx-3 self-stretch hidden sm:block" />
        <MiniBar items={topGA} dataKey="mostConcededProb" title={tr.predictions.goals.mostConceded} icon="arrow_downward" color="#FF4136" />
        <div className="w-px bg-[#00FF41]/15 mx-3 self-stretch hidden sm:block" />
        <MiniBar items={topLeastGA} dataKey="leastConcededProb" title={tr.predictions.goals.leastConceded} icon="shield" color="#00BFFF" />
      </div>
    </div>
  );
}

/* ═══════════ 4. XGBoost Feature Importance ═══════════ */
function FeatureImportance({ importance }) {
  const tr = useT();
  if (!importance || Object.keys(importance).length === 0) return null;

  const labels = {
    ppg: tr.predictions.importance.ppg,
    winRate: tr.predictions.importance.winRate,
    drawRate: tr.predictions.importance.drawRate,
    lossRate: tr.predictions.importance.lossRate,
    gfPerGame: tr.predictions.importance.gfPerGame,
    gaPerGame: tr.predictions.importance.gaPerGame,
    gdPerGame: tr.predictions.importance.gdPerGame,
    points: tr.predictions.importance.points,
    goalDifference: tr.predictions.importance.goalDifference,
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
      <p className="text-[0.72rem] text-[#00FF41]/55 font-headline mt-1 uppercase">
        {tr.predictions.importanceCaption}
      </p>
    </div>
  );
}

/* ═══════════ 5. PROJECTED TABLE ═══════════ */
function ProjectedTable({ data }) {
  const tr = useT();
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">table_chart</span>
        {tr.predictions.projectedTable.title}
      </h3>
      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-[0.78rem] sm:text-xs font-headline uppercase">
          <thead>
            <tr className="text-[#00FF41]/70 border-b border-[#00FF41]/10">
              <th className="py-1.5 px-1 text-left">#</th>
              <th className="py-1.5 px-2 text-left">{tr.predictions.projectedTable.team}</th>
              <th className="py-1.5 px-1 text-center">{tr.predictions.projectedTable.current}</th>
              <th className="py-1.5 px-1 text-center">{tr.predictions.projectedTable.projected}</th>
              <th className="py-1.5 px-1 text-center">{tr.predictions.projectedTable.interval}</th>
              <th className="py-1.5 px-1 text-center">{tr.predictions.projectedTable.goalsFor}</th>
              <th className="py-1.5 px-1 text-center">{tr.predictions.projectedTable.goalsAgainst}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((t, i) => {
              const zone = zoneForPosition(i + 1);
              return (
                <tr key={t.teamShortName} className="border-b border-[#00FF41]/5 hover:bg-[#00FF41]/5"
                  style={{ borderLeftColor: ZONE_COLORS[zone], borderLeftWidth: 3 }}>
                  <td className="py-1 px-1 text-center" style={{ color: ZONE_COLORS[zone] }}>{i + 1}</td>
                  <td className="py-1 px-2 flex items-center gap-1.5">
                    <img src={t.teamCrest} alt="" className="w-4 h-4" loading="lazy" />
                    <span className="text-[#00FF41]/80 truncate max-w-[90px]">{t.teamShortName}</span>
                  </td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/65">{t.currentPoints}</td>
                  <td className="py-1 px-1 text-center font-bold text-[#00FF41]">{t.mc.pointsMean}</td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/65">[{t.mc.pointsP10}–{t.mc.pointsP90}]</td>
                  <td className="py-1 px-1 text-center text-[#00FF41]/70">{t.mc.gfMean}</td>
                  <td className="py-1 px-1 text-center text-[#FF4136]">{t.mc.gaMean}</td>
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
  const tr = useT();
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
        {tr.predictions.error}: {error}
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
          {tr.predictions.title}
        </h2>
        <p className="text-[0.78rem] text-[#00FF41]/65 font-headline uppercase mt-1">
          {tr.predictions.subtitle(data.season, data.matchday, data.totalMatches, data.nSimulations.toLocaleString())}
        </p>
        <p className="text-[0.74rem] text-[#00FF41]/55 font-headline uppercase mt-0.5">
          {tr.predictions.modelLine(data.model, data.nSimulations.toLocaleString())}
        </p>
        {data.shrinkageK != null && (
          <p className="text-[0.74rem] text-[#00FF41]/55 font-headline uppercase mt-0.5">
            {tr.predictions.shrinkageNote(data.shrinkageK)}
          </p>
        )}
      </div>

      {/* Too few matches for the projection to mean anything. Shown rather than
          hidden, because the point is that the model knows its own limits. */}
      {data.lowConfidence && (
        <div className="mb-4 border border-[#FFD700]/30 bg-[#FFD700]/5 px-4 py-3 text-[0.82rem] text-[#FFD700]/80 font-headline uppercase leading-relaxed">
          {tr.predictions.lowConfidence}
        </div>
      )}

      {/* Method explanation */}
      <div className="viz-panel col-span-12 mb-4">
        <h3 className="viz-title">
          <span className="material-symbols-outlined text-sm mr-2">psychology</span>
          {tr.predictions.methodology.title}
        </h3>
        <div className="text-[0.78rem] text-[#00FF41]/60 font-headline leading-relaxed space-y-1">
          {tr.predictions.methodology.steps(data.nSimulations.toLocaleString()).map((step) => (
            <p key={step}>{step}</p>
          ))}
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
