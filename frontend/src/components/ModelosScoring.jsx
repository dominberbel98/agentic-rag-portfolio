import React, { useEffect, useMemo, useState } from "react";
import { t as tr } from "../i18n/en";
import { MetricStrip, ModelTabs } from "./ModelTabs";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, ReferenceLine, AreaChart, Area,
} from "recharts";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";
const RED = "#FF4136";

const BAND_COLOR = {
  Poor: "#FF4136",
  Fair: "#FF8C00",
  Good: "#FFD700",
  "Very Good": "#00BFFF",
  Exceptional: "#00FF41",
};

/* ────────── helpers ────────── */
const sigmoid = (z) => 1 / (1 + Math.exp(-z));

/**
 * Map a default probability onto the 300-850 scale.
 *
 * The anchor comes from `data.scorecard`, which the Python pipeline derives from
 * the portfolio's actual default rate. Hardcoding it here as well is how the two
 * ends drifted apart: the browser scored against 50:1 odds — a 1.96% chance of
 * default — while the population defaults at 17%, so the interactive score sat
 * roughly 168 points below the distribution charted beside it.
 */
function probToScore(prob, scorecard) {
  const { pdo, baseScore, baseOdds, minScore, maxScore } = scorecard;
  const factor = pdo / Math.log(2);
  const offset = baseScore - factor * Math.log(baseOdds);
  const odds = (1 - prob) / Math.max(prob, 1e-9);
  const raw = offset + factor * Math.log(odds);
  return Math.max(minScore, Math.min(maxScore, Math.round(raw)));
}

function bandFromScore(s) {
  if (s < 580) return "Poor";
  if (s < 670) return "Fair";
  if (s < 740) return "Good";
  if (s < 800) return "Very Good";
  return "Exceptional";
}

function predictWithLR(weights, applicant) {
  let z = weights.intercept;
  for (const f of weights.numerical) {
    const v = Number(applicant[f.feature] ?? 0);
    z += ((v - f.mean) / (f.std || 1)) * f.coef;
  }
  for (const c of weights.categorical) {
    if (String(applicant[c.feature]) === String(c.level)) z += c.coef;
  }
  return sigmoid(z);
}

/* ────────── tooltip ────────── */
const CrtTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
      {label !== undefined && <p className="font-bold mb-1">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || GREEN }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(4) : p.value}
        </p>
      ))}
    </div>
  );
};

/* ═══════════ 1. METRIC CARDS ═══════════ */
function MetricCards({ data }) {
  const lr = data.models.logistic;
  const gbm = data.models.gbm;
  const cards = [
    { label: "AUC-ROC (GBM)", v: gbm.test.auc, fmt: (x) => x.toFixed(3), good: gbm.test.auc > 0.7 },
    { label: "KS Statistic",  v: gbm.test.ks,  fmt: (x) => x.toFixed(3), good: gbm.test.ks > 0.3 },
    { label: "Gini",          v: gbm.test.gini, fmt: (x) => x.toFixed(3), good: gbm.test.gini > 0.4 },
    { label: "Avg Precision", v: gbm.test.average_precision, fmt: (x) => x.toFixed(3) },
    { label: "Brier Score",   v: gbm.test.brier, fmt: (x) => x.toFixed(3), good: gbm.test.brier < 0.2 },
    { label: "AUC LR (CV)",   v: lr.cv.auc_mean, fmt: (x) => x.toFixed(3), good: lr.cv.auc_mean > 0.7 },
  ];
  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">dashboard</span>
        {tr.scoring.metrics.title}
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map((c) => (
          <div key={c.label} className="border border-[#00FF41]/15 rounded p-3 bg-black/20">
            <div className="text-[0.55rem] font-headline uppercase text-[#00FF41]/70 tracking-widest mb-1">
              {c.label}
            </div>
            <div
              className="text-xl sm:text-2xl font-bold font-headline"
              style={{ color: c.good === false ? RED : GREEN, textShadow: `0 0 8px ${c.good === false ? RED : GREEN}55` }}
            >
              {c.fmt(c.v)}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-3 uppercase">
        {tr.scoring.datasetLine(
          data.dataset.n.toLocaleString(),
          (data.dataset.defaultRate * 100).toFixed(1),
          data.dataset.trainSize,
          data.dataset.testSize,
        )}
      </p>
    </div>
  );
}

/* ═══════════ 2. ROC CURVE ═══════════ */
function RocPanel({ roc, auc }) {
  const data = roc.map((p) => ({ fpr: p.fpr, tpr: p.tpr }));
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">stacked_line_chart</span>
        ROC_CURVE — AUC {auc.toFixed(3)}
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ left: 10, right: 20, top: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="rocFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={GREEN} stopOpacity={0.4} />
              <stop offset="100%" stopColor={GREEN} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis type="number" dataKey="fpr" domain={[0, 1]} tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
                 label={{ value: "FPR →", position: "insideBottomRight", fill: DIM, fontSize: 10, offset: -2 }} />
          <YAxis type="number" dataKey="tpr" domain={[0, 1]} tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }}
                 label={{ value: "TPR ↑", position: "insideTopLeft", fill: DIM, fontSize: 10, offset: 5 }} />
          <Tooltip content={<CrtTooltip />} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="rgba(255,65,54,0.4)" strokeDasharray="3 3" ifOverflow="extendDomain" />
          <Area type="monotone" dataKey="tpr" stroke={GREEN} strokeWidth={2} fill="url(#rocFill)" name="TPR" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
      <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-1 uppercase">
        {tr.scoring.rocCaption}
      </p>
    </div>
  );
}

/* ═══════════ 3. FEATURE IMPORTANCE ═══════════ */
function ImportancePanel({ rows }) {
  const labels = {
    age: tr.scoring.features.age,
    annual_income: tr.scoring.features.annual_income,
    employment_years: tr.scoring.features.employment_years,
    loan_amount: tr.scoring.features.loan_amount,
    payment_history_pct: tr.scoring.features.payment_history_pct,
    credit_utilization: tr.scoring.features.credit_utilization,
    credit_age_years: tr.scoring.features.credit_age_years,
    num_credit_accounts: tr.scoring.features.num_credit_accounts,
    recent_inquiries: tr.scoring.features.recent_inquiries,
    derogatory_marks: tr.scoring.features.derogatory_marks,
    debt_to_income: tr.scoring.features.debt_to_income,
    loan_to_income: tr.scoring.features.loan_to_income,
    loan_purpose: tr.scoring.features.loan_purpose,
    home_ownership: tr.scoring.features.home_ownership,
  };
  const data = rows.slice(0, 10).map((r) => ({ ...r, label: labels[r.feature] || r.feature }));
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">model_training</span>
        FEATURE_IMPORTANCE (permutation)
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ left: 90, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="label" tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }} width={85} axisLine={false} tickLine={false} />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="importance" name="Δ AUC" fill={GREEN} fillOpacity={0.65} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-1 uppercase">
        {tr.scoring.importanceCaption}
      </p>
    </div>
  );
}

/* ═══════════ 4. SCORE DISTRIBUTION ═══════════ */
function ScoreDistribution({ histogram, bands }) {
  const data = histogram.map((b) => ({
    bin: b.bin,
    range: `${b.from}–${b.to}`,
    count: b.count,
    band: bandFromScore(b.bin),
  }));
  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">bar_chart</span>
        {tr.scoring.distribution.title}
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ left: 0, right: 10, top: 10, bottom: 10 }}>
          <XAxis dataKey="bin" tick={{ fill: DIM, fontSize: 9 }} axisLine={{ stroke: DIM }} />
          <YAxis tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-[#0e0e0e]/95 border border-[#00FF41]/30 px-3 py-2 text-xs font-headline uppercase text-[#00FF41] shadow-[0_0_12px_rgba(0,255,65,0.2)]">
                  <p className="font-bold">Score {d.range}</p>
                  <p style={{ color: BAND_COLOR[d.band] }}>{d.band}</p>
                  <p>{tr.scoring.applicants(d.count)}</p>
                </div>
              );
            }}
            cursor={{ fill: "rgba(0,255,65,0.05)" }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (<Cell key={i} fill={BAND_COLOR[d.band]} fillOpacity={0.65} />))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 mt-2 text-[0.6rem] font-headline uppercase">
        {bands.map((b) => (
          <span key={b.band} className="flex items-center gap-1" style={{ color: BAND_COLOR[b.band] }}>
            <span className="w-2 h-2 rounded-full" style={{ background: BAND_COLOR[b.band] }} />
            {b.band} · {b.count}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ═══════════ 5. INTERACTIVE SCORECARD ═══════════ */
const SLIDER_FIELDS = [
  { key: "age", label: tr.scoring.features.age, min: 21, max: 70, step: 1, unit: tr.scoring.units.years },
  { key: "annual_income", label: tr.scoring.features.annual_income, min: 15000, max: 300000, step: 1000, unit: "€" },
  { key: "employment_years", label: tr.scoring.features.employment_years, min: 0, max: 40, step: 1, unit: tr.scoring.units.years },
  { key: "loan_amount", label: tr.scoring.features.loan_amount, min: 1000, max: 100000, step: 500, unit: "€" },
  { key: "payment_history_pct", label: tr.scoring.features.payment_history_pct, min: 0, max: 100, step: 1, unit: "%" },
  { key: "credit_utilization", label: tr.scoring.features.credit_utilization, min: 0, max: 100, step: 1, unit: "%" },
  { key: "credit_age_years", label: tr.scoring.features.credit_age_years, min: 0, max: 35, step: 0.5, unit: tr.scoring.units.years },
  { key: "num_credit_accounts", label: tr.scoring.features.num_credit_accounts, min: 1, max: 15, step: 1, unit: "" },
  { key: "recent_inquiries", label: tr.scoring.features.recent_inquiries, min: 0, max: 10, step: 1, unit: "" },
  { key: "derogatory_marks", label: tr.scoring.features.derogatory_marks, min: 0, max: 5, step: 1, unit: "" },
];

// A typical applicant, not a flattering one: this lands at roughly 644, in Fair,
// which is the band 57% of the portfolio occupies. It also sits just under the
// Good boundary, so moving a single slider changes the band — which is the point
// of an interactive scorecard, and something the previous default could not do
// from the bottom of the scale.
const DEFAULT_APPLICANT = {
  age: 35, annual_income: 55000, employment_years: 8, loan_amount: 15000,
  payment_history_pct: 96, credit_utilization: 18, credit_age_years: 12,
  num_credit_accounts: 4, recent_inquiries: 1, derogatory_marks: 0,
  loan_purpose: "personal", home_ownership: "rent",
};

function deriveExtras(a) {
  const monthlyPay = a.loan_amount * 0.05;
  const monthlyIncome = a.annual_income / 12;
  return {
    debt_to_income: monthlyPay / Math.max(monthlyIncome, 1),
    loan_to_income: a.loan_amount / Math.max(a.annual_income, 1),
  };
}

function InteractiveScorecard({ weights, levels, scorecard, applicant, setApplicant }) {
  const result = useMemo(() => {
    const full = { ...applicant, ...deriveExtras(applicant) };
    const prob = predictWithLR(weights, full);
    const score = probToScore(prob, scorecard);
    return { prob, score, band: bandFromScore(score) };
  }, [applicant, weights, scorecard]);

  const bandColor = BAND_COLOR[result.band];

  return (
    <div className="viz-panel col-span-12 lg:col-span-5">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">tune</span>
        {tr.scoring.simulator.title}
      </h3>

      {/* Score gauge */}
      <div className="flex flex-col items-center mb-4 p-4 border border-[#00FF41]/15 rounded bg-black/30">
        <div className="text-[0.6rem] font-headline uppercase text-[#00FF41]/70 tracking-widest mb-1">Credit Score</div>
        <div
          className="text-5xl sm:text-6xl font-bold font-headline tabular-nums"
          style={{ color: bandColor, textShadow: `0 0 18px ${bandColor}80` }}
        >
          {result.score}
        </div>
        <div className="text-xs font-headline uppercase mt-1" style={{ color: bandColor }}>{result.band}</div>
        <div className="text-[0.65rem] font-headline uppercase text-[#00FF41]/60 mt-2">
          P(default) = <span className="text-[#00FF41]">{(result.prob * 100).toFixed(2)}%</span>
        </div>

        {/* horizontal score bar */}
        <div className="w-full mt-3 h-2 rounded bg-[#00FF41]/10 relative overflow-hidden">
          <div
            className="absolute top-0 bottom-0 w-1 rounded"
            style={{
              left: `${((result.score - 300) / 550) * 100}%`,
              background: bandColor,
              boxShadow: `0 0 8px ${bandColor}`,
            }}
          />
          <div className="absolute inset-0 flex">
            {[300, 580, 670, 740, 800, 850].slice(0, 5).map((from, i) => {
              const to = [580, 670, 740, 800, 850][i];
              const w = ((to - from) / 550) * 100;
              const band = bandFromScore(from + 1);
              return <div key={i} style={{ width: `${w}%`, background: BAND_COLOR[band], opacity: 0.18 }} />;
            })}
          </div>
        </div>
      </div>

      {/* Sliders */}
      <div className="space-y-2.5 max-h-[420px] overflow-y-auto scrollbar-hide pr-1">
        {SLIDER_FIELDS.map((f) => (
          <div key={f.key}>
            <div className="flex justify-between text-[0.6rem] font-headline uppercase">
              <span className="text-[#00FF41]/70">{f.label}</span>
              <span className="text-[#00FF41] tabular-nums">
                {applicant[f.key]}{f.unit ? ` ${f.unit}` : ""}
              </span>
            </div>
            <input
              type="range" min={f.min} max={f.max} step={f.step} value={applicant[f.key]}
              onChange={(e) => setApplicant((s) => ({ ...s, [f.key]: Number(e.target.value) }))}
              className="w-full h-1 appearance-none bg-[#00FF41]/20 rounded outline-none accent-[#00FF41]"
            />
          </div>
        ))}

        {/* Categorical selects */}
        {["loan_purpose", "home_ownership"].map((feat) => (
          <div key={feat} className="flex justify-between items-center gap-2">
            <span className="text-[0.6rem] font-headline uppercase text-[#00FF41]/70">
              {feat === "loan_purpose" ? tr.scoring.features.loan_purpose : tr.scoring.features.home_ownership}
            </span>
            <select
              value={applicant[feat]}
              onChange={(e) => setApplicant((s) => ({ ...s, [feat]: e.target.value }))}
              className="bg-black/40 border border-[#00FF41]/20 text-[#00FF41] text-[0.65rem] font-headline uppercase px-2 py-1 rounded outline-none focus:border-[#00FF41]/50"
            >
              {(levels[feat] || []).map((lvl) => (
                <option key={lvl} value={lvl}>{lvl}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <p className="text-[0.55rem] text-[#00FF41]/55 font-headline mt-3 uppercase">
        {tr.scoring.inferenceNote}
      </p>
    </div>
  );
}

/* ═══════════ 6. WHY THIS SCORE ═══════════ */

/**
 * Per-input contribution to the score shown next to it.
 *
 * The gauge alone gives a number with no reason attached, which is exactly the
 * complaint a scorecard is supposed to answer. These are the logistic
 * regression's own terms — the standardised value times its coefficient — so the
 * explanation is the model, not a story told about it.
 *
 * Sign convention: z rises with default risk and the score falls as z rises, so
 * a positive z contribution is drawn as a negative effect on the score.
 */
function scoreDrivers(weights, applicant) {
  const rows = [];
  for (const f of weights.numerical) {
    const value = Number(applicant[f.feature] ?? 0);
    rows.push({ feature: f.feature, z: ((value - f.mean) / (f.std || 1)) * f.coef });
  }
  for (const c of weights.categorical) {
    if (String(applicant[c.feature]) === String(c.level)) {
      rows.push({ feature: c.feature, z: c.coef });
    }
  }
  return rows
    .map((r) => ({ ...r, effect: -r.z }))
    .filter((r) => Math.abs(r.effect) > 0.005)
    .sort((a, b) => Math.abs(b.effect) - Math.abs(a.effect))
    .slice(0, 7);
}

function ScoreDrivers({ weights, applicant }) {
  const drivers = useMemo(() => scoreDrivers(weights, applicant), [weights, applicant]);
  const widest = Math.max(...drivers.map((d) => Math.abs(d.effect)), 0.001);

  return (
    <div className="viz-panel col-span-12 lg:col-span-7">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">insights</span>
        {tr.scoring.drivers.title}
      </h3>

      <div className="flex gap-5 mb-4 text-[0.75rem] font-headline uppercase">
        <span className="text-[#00FF41]">▲ {tr.scoring.drivers.raises}</span>
        <span className="text-[#FF4136]">▼ {tr.scoring.drivers.lowers}</span>
      </div>

      <div className="space-y-3">
        {drivers.map((d) => {
          const up = d.effect > 0;
          const width = (Math.abs(d.effect) / widest) * 50;
          return (
            <div key={`${d.feature}-${d.z}`} className="flex items-center gap-2">
              <span className="w-[38%] shrink-0 text-right text-[0.78rem] font-headline uppercase text-[#00FF41]/80 truncate">
                {tr.scoring.features[d.feature] || d.feature}
              </span>
              {/* Diverging bar: the centre line is "no effect", so length and
                  side are both readable at a glance. */}
              <div className="flex-1 h-4 relative">
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#00FF41]/25" />
                <div
                  className="absolute top-0 bottom-0 rounded-sm"
                  style={{
                    width: `${width}%`,
                    [up ? "left" : "right"]: "50%",
                    background: up ? GREEN : RED,
                    opacity: 0.7,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[0.72rem] text-[#00FF41]/65 font-headline mt-4 normal-case leading-relaxed">
        {tr.scoring.drivers.caption}
      </p>
    </div>
  );
}

/* ═══════════ 7. SAMPLE APPLICANTS ═══════════ */
function SampleApplicants({ rows }) {
  return (
    <div className="viz-panel col-span-12">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">groups</span>
        {tr.scoring.sampleTable.title}
      </h3>
      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-[0.65rem] font-headline uppercase">
          <thead>
            <tr className="text-[#00FF41]/70 border-b border-[#00FF41]/10">
              <th className="py-1.5 px-2 text-center">#</th>
              <th className="py-1.5 px-2 text-left">{tr.scoring.sampleTable.age}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.income}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.loan}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.dti}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.payments}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.utilisation}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.marks}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.probLr}</th>
              <th className="py-1.5 px-2 text-right">{tr.scoring.sampleTable.probGbm}</th>
              <th className="py-1.5 px-2 text-center">{tr.scoring.sampleTable.score}</th>
              <th className="py-1.5 px-2 text-left">{tr.scoring.sampleTable.band}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-[#00FF41]/5 hover:bg-[#00FF41]/5"
                  style={{ borderLeftColor: BAND_COLOR[r.band], borderLeftWidth: 3 }}>
                <td className="py-1 px-2 text-center text-[#00FF41]/65">{i + 1}</td>
                <td className="py-1 px-2 text-[#00FF41]/70">{r.age}</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{r.annual_income.toLocaleString()}€</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{r.loan_amount.toLocaleString()}€</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{r.debt_to_income.toFixed(2)}</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{r.payment_history_pct}%</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{r.credit_utilization}%</td>
                <td className="py-1 px-2 text-right text-[#FF4136]">{r.derogatory_marks}</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{(r.prob_default_lr * 100).toFixed(1)}%</td>
                <td className="py-1 px-2 text-right text-[#00FF41]/70">{(r.prob_default_gbm * 100).toFixed(1)}%</td>
                <td className="py-1 px-2 text-center font-bold" style={{ color: BAND_COLOR[r.band] }}>{r.score}</td>
                <td className="py-1 px-2 text-[#00FF41]/70">{r.band}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════ MAIN EXPORT ═══════════ */

const TABS = [
  { id: "try", icon: "tune", label: tr.tabs.tryIt },
  { id: "how", icon: "help", label: tr.tabs.howItWorks },
  { id: "evidence", icon: "query_stats", label: tr.tabs.evidence },
];

export default function ModelosScoring() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("try");
  // Lifted out of InteractiveScorecard so the drivers panel scores the same
  // applicant the sliders are describing.
  const [applicant, setApplicant] = useState(DEFAULT_APPLICANT);

  useEffect(() => {
    fetch("/data/credit_scoring.json")
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
        {tr.scoring.error}: {error}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          {tr.scoring.loadingModel}<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const gbm = data.models.gbm.test;
  const headline = [
    { label: "AUC", value: gbm.auc.toFixed(3) },
    { label: "KS", value: gbm.ks.toFixed(3) },
    { label: "GINI", value: gbm.gini.toFixed(3) },
    { label: "BRIER", value: gbm.brier.toFixed(3) },
  ];

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <div className="mb-3">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          {tr.scoring.title}
        </h2>
        <p className="text-[0.7rem] text-[#00FF41]/70 font-headline mt-1 leading-relaxed max-w-3xl normal-case">
          {tr.scoring.explainer.problem}
        </p>
      </div>

      <ModelTabs tabs={TABS} active={tab} onChange={setTab} />
      <MetricStrip items={headline} />

      {tab === "try" && (
        <div className="grid grid-cols-12 gap-4 mt-4">
          <InteractiveScorecard
            weights={data.models.logistic.weights}
            levels={data.models.logistic.weights.categorical_levels}
            scorecard={data.scorecard}
            applicant={applicant}
            setApplicant={setApplicant}
          />
          <ScoreDrivers weights={data.models.logistic.weights} applicant={applicant} />
        </div>
      )}

      {tab === "how" && (
        <div className="grid grid-cols-12 gap-4 mt-4">
          <div className="viz-panel col-span-12 lg:col-span-7">
            <h3 className="viz-title">
              <span className="material-symbols-outlined text-sm mr-2">help</span>
              {tr.scoring.explainer.title}
            </h3>
            <div className="text-[0.72rem] text-[#00FF41]/75 font-headline leading-relaxed space-y-3 normal-case">
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.scoring.explainer.problemLabel}</span>{" "}
                {tr.scoring.explainer.problem}
              </p>
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.scoring.explainer.solutionLabel}</span>{" "}
                {tr.scoring.explainer.solution}
              </p>
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.scoring.explainer.tryItLabel}</span>{" "}
                {tr.scoring.explainer.tryIt}
              </p>
            </div>
          </div>

          <div className="viz-panel col-span-12 lg:col-span-5">
            <h3 className="viz-title">
              <span className="material-symbols-outlined text-sm mr-2">account_tree</span>
              {tr.scoring.explainer.pipelineTitle}
            </h3>
            <div className="text-[0.66rem] text-[#00FF41]/70 font-headline leading-relaxed space-y-2 normal-case">
              {tr.scoring.explainer.steps.map((step) => (
                <p key={step} className="pl-3 border-l border-[#00FF41]/20">{step}</p>
              ))}
            </div>
            <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-3 uppercase">
              {tr.scoring.generated(
                new Date(data.generatedAt).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }),
              )}
            </p>
          </div>
        </div>
      )}

      {tab === "evidence" && (
        <div className="grid grid-cols-12 gap-4 mt-4">
          <MetricCards data={data} />
          <RocPanel roc={data.rocCurve} auc={data.models.gbm.test.auc} />
          <ImportancePanel rows={data.featureImportance} />
          <ScoreDistribution histogram={data.scoreHistogram} bands={data.bandDistribution} />
          <SampleApplicants rows={data.sampleApplicants} />
        </div>
      )}

      <div className="h-8" />
    </div>
  );
}
