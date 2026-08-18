import { t as tr } from "../i18n/en";
import React, { useEffect, useMemo, useState } from "react";
import { MetricStrip, ModelTabs } from "./ModelTabs";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const GREEN = "#00FF41";
const DIM = "rgba(0,255,65,0.4)";

const CATEGORY_COLOR = {
  electronics: "#00BFFF",
  books: "#FFD700",
  sports: "#00FF41",
  home: "#FF8C00",
};

/* ────────── linear-algebra helpers (browser-side) ────────── */
function dot(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
}
function norm(a) { return Math.sqrt(dot(a, a)); }
function cosine(a, b) {
  const na = norm(a), nb = norm(b);
  if (na === 0 || nb === 0) return 0;
  return dot(a, b) / (na * nb);
}
function meanVec(matrix, indices) {
  const dim = matrix[0].length;
  const out = new Float32Array(dim);
  for (const i of indices) {
    const row = matrix[i];
    for (let j = 0; j < dim; j++) out[j] += row[j];
  }
  for (let j = 0; j < dim; j++) out[j] /= indices.length;
  return out;
}

/* MMR re-rank for diversity */
function mmr(candidates, matrix, k, lambda) {
  if (!candidates.length) return [];
  const sorted = [...candidates].sort((a, b) => b.score - a.score);
  const selected = [sorted.shift()];
  while (selected.length < k && sorted.length) {
    let bestIdx = -1, bestVal = -Infinity;
    for (let j = 0; j < sorted.length; j++) {
      const c = sorted[j];
      let maxSim = -Infinity;
      for (const s of selected) {
        const sim = cosine(matrix[c.idx], matrix[s.idx]);
        if (sim > maxSim) maxSim = sim;
      }
      const score = lambda * c.score - (1 - lambda) * maxSim;
      if (score > bestVal) { bestVal = score; bestIdx = j; }
    }
    selected.push(sorted.splice(bestIdx, 1)[0]);
  }
  return selected;
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

/* ════════ Product card ════════ */
function ProductCard({ product, selected, onToggle, similarity }) {
  const color = CATEGORY_COLOR[product.category] || GREEN;
  return (
    <button
      onClick={() => onToggle?.(product.id)}
      className={`relative text-left w-full border rounded p-3 bg-black/30 transition-all group ${
        selected
          ? "border-[#00FF41]/60 shadow-[0_0_12px_rgba(0,255,65,0.25)]"
          : "border-[#00FF41]/15 hover:border-[#00FF41]/35"
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className="flex-shrink-0 w-10 h-10 rounded flex items-center justify-center"
          style={{ background: `${color}22`, border: `1px solid ${color}44` }}
        >
          <span className="material-symbols-outlined text-[1.2rem]" style={{ color }}>
            {product.icon || "inventory_2"}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[0.82rem] font-bold font-headline uppercase text-[#00FF41] truncate">
            {product.name}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[0.68rem] font-headline uppercase">
            <span style={{ color }}>{product.category}</span>
            <span className="text-[#00FF41]/60">·</span>
            <span className="text-[#00FF41]/70">€{product.price}</span>
            <span className="text-[#00FF41]/60">·</span>
            <span className="text-[#FFD700]/70">★ {product.rating}</span>
          </div>
          {similarity !== undefined && (
            <div className="mt-1.5 h-1 bg-[#00FF41]/10 rounded overflow-hidden">
              <div className="h-full" style={{ width: `${Math.max(0, Math.min(1, similarity)) * 100}%`, background: GREEN, opacity: 0.75 }} />
            </div>
          )}
          {similarity !== undefined && (
            <div className="text-[0.68rem] font-headline uppercase text-[#00FF41]/70 mt-1">
              similarity {similarity.toFixed(3)}
            </div>
          )}
        </div>
      </div>
      {selected && (
        <span className="absolute top-2 right-2 material-symbols-outlined text-[1rem] text-[#00FF41]">check_circle</span>
      )}
    </button>
  );
}

/* ════════ Personas summary ════════ */
function PersonaSummary({ personas, onApply }) {
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">groups</span>
        {tr.recommender.personas.title}
      </h3>
      <div className="space-y-2">
        {personas.map((p) => (
          <div key={p.persona} className="flex items-center justify-between border border-[#00FF41]/15 rounded px-3 py-2 bg-black/20">
            <div>
              <div className="text-[0.82rem] font-headline uppercase text-[#00FF41] font-bold">{p.persona}</div>
              <div className="text-[0.68rem] font-headline uppercase text-[#00FF41]/65">
                {tr.recommender.personaItems(p.history.length, p.diversity.toFixed(2))}
              </div>
            </div>
            <button
              onClick={() => onApply(p.history)}
              className="text-[0.6rem] font-headline uppercase text-[#00FF41] border border-[#00FF41]/30 rounded px-2 py-1 hover:bg-[#00FF41]/10"
            >
              {tr.recommender.load}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ════════ Top-N similarity bar chart ════════ */
function SimilarityBars({ recs }) {
  const data = recs.map((r) => ({ name: r.name, sim: r.similarity, cat: r.category }));
  return (
    <div className="viz-panel col-span-12 lg:col-span-6">
      <h3 className="viz-title">
        <span className="material-symbols-outlined text-sm mr-2">leaderboard</span>
        {tr.recommender.similarity.title}
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 38)}>
        <BarChart data={data} layout="vertical" margin={{ left: 80, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" domain={[0, 1]} tick={{ fill: DIM, fontSize: 10 }} axisLine={{ stroke: DIM }} />
          <YAxis type="category" dataKey="name" tick={{ fill: GREEN, fontSize: 9, fontFamily: "Space Grotesk" }} width={75} axisLine={false} tickLine={false} />
          <Tooltip content={<CrtTooltip />} cursor={{ fill: "rgba(0,255,65,0.05)" }} />
          <Bar dataKey="sim" name={tr.recommender.similarity.label} radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={CATEGORY_COLOR[d.cat] || GREEN} fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ════════ Why this rec — feature breakdown ════════ */
function ExplainPanel({ profile, item, vocab, breakdown }) {
  if (!profile || !item) return null;
  const tfidfDim = breakdown.tfidf_dims;

  // contributions per dimension
  const contribs = profile.map((p, i) => p * item[i]);
  const tfidfContrib = contribs.slice(0, tfidfDim);
  const catContrib = contribs.slice(tfidfDim, tfidfDim + breakdown.category_dims).reduce((a, b) => a + b, 0);
  const numContrib = contribs.slice(tfidfDim + breakdown.category_dims).reduce((a, b) => a + b, 0);

  // top tf-idf terms
  const topTerms = tfidfContrib
    .map((v, i) => ({ term: vocab[i], v }))
    .filter((t) => t.v > 0)
    .sort((a, b) => b.v - a.v)
    .slice(0, 5);

  const total = tfidfContrib.reduce((a, b) => a + b, 0) + catContrib + numContrib;

  return (
    <div className="border border-[#00FF41]/15 rounded p-3 bg-black/20 mt-3">
      <div className="text-[0.72rem] font-headline uppercase text-[#00FF41]/70 mb-2">
        {tr.recommender.explain.title}
      </div>
      <div className="flex gap-1 mb-2 h-2 rounded overflow-hidden bg-[#00FF41]/5">
        <div style={{ width: `${(tfidfContrib.reduce((a, b) => a + b, 0) / total) * 100}%`, background: GREEN, opacity: 0.65 }} />
        <div style={{ width: `${(catContrib / total) * 100}%`, background: "#00BFFF", opacity: 0.65 }} />
        <div style={{ width: `${(numContrib / total) * 100}%`, background: "#FFD700", opacity: 0.65 }} />
      </div>
      <div className="flex flex-wrap gap-3 text-[0.68rem] font-headline uppercase">
        <span className="text-[#00FF41]">■ {tr.recommender.explain.tfidf}</span>
        <span className="text-[#00BFFF]">■ {tr.recommender.explain.category}</span>
        <span className="text-[#FFD700]">■ {tr.recommender.explain.priceRating}</span>
      </div>
      {topTerms.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {topTerms.map((t) => (
            <span key={t.term} className="text-[0.68rem] font-headline uppercase text-[#00FF41] border border-[#00FF41]/25 rounded px-2 py-0.5">
              {t.term}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ════════ MAIN EXPORT ════════ */

const TABS = [
  { id: "try", icon: "tune", label: tr.tabs.tryIt },
  { id: "how", icon: "help", label: tr.tabs.howItWorks },
  { id: "evidence", icon: "query_stats", label: tr.tabs.evidence },
];
export default function ModelosRecomendacion() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [useMmr, setUseMmr] = useState(true);
  const [topN, setTopN] = useState(6);
  const [explainId, setExplainId] = useState(null);
  const [tab, setTab] = useState("try");

  useEffect(() => {
    fetch("/data/product_recommendations.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setData(d);
        const init = d.personas?.[0]?.history || [];
        setSelected(new Set(init));
      })
      .catch((e) => setError(e.message));
  }, []);

  const profileVec = useMemo(() => {
    if (!data || selected.size === 0) return null;
    const idByPos = new Map(data.catalog.map((p, i) => [p.id, i]));
    const seenIdx = [...selected].map((id) => idByPos.get(id)).filter((i) => i !== undefined);
    if (!seenIdx.length) return null;
    return meanVec(data.featureMatrix, seenIdx);
  }, [data, selected]);

  const recommendations = useMemo(() => {
    if (!data) return null;
    if (!profileVec) return [];
    const matrix = data.featureMatrix;
    const candidates = data.catalog
      .map((p, i) => ({ idx: i, product: p, score: cosine(profileVec, matrix[i]) }))
      .filter((c) => !selected.has(c.product.id));

    const picks = useMmr
      ? mmr(candidates, matrix, topN, 0.7)
      : [...candidates].sort((a, b) => b.score - a.score).slice(0, topN);

    return picks.map((c, i) => ({ ...c.product, similarity: c.score, rank: i + 1 }));
  }, [data, profileVec, selected, useMmr, topN]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-[#FF4136] font-headline text-sm uppercase">
        {tr.recommender.error}: {error}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          {tr.recommender.loadingCatalog}<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const toggle = (id) => setSelected((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const clearAll = () => setSelected(new Set());

  const headline = [
    { label: "PRODUCTS", value: data.catalog.length },
    { label: "CATEGORIES", value: data.categories.length },
    { label: "FEATURE DIM", value: data.featureMatrix[0].length },
    { label: "DIVERSITY", value: data.metrics.avgDiversity.toFixed(2) },
    { label: "COVERAGE", value: `${(data.metrics.catalogCoverage * 100).toFixed(0)}%` },
  ];

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      <div className="mb-3">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          {tr.recommender.title}
        </h2>
        <p className="text-[0.7rem] text-[#00FF41]/70 font-headline mt-1 leading-relaxed max-w-3xl normal-case">
          {tr.recommender.explainer.problem}
        </p>
      </div>

      <ModelTabs tabs={TABS} active={tab} onChange={setTab} />
      <MetricStrip items={headline} />

      {tab === "try" && (
        <>
          {/* Controls */}
          <div className="viz-panel col-span-12 mt-4 mb-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-[0.78rem] font-headline uppercase text-[#00FF41]/70">
                {tr.recommender.selectedCount} <span className="text-[#00FF41] font-bold">{selected.size}</span>
              </div>
              <button
                onClick={clearAll}
                className="min-h-[38px] text-[0.72rem] font-headline uppercase text-[#FF4136] border border-[#FF4136]/30 rounded px-3 hover:bg-[#FF4136]/10"
              >
                {tr.recommender.clear}
              </button>
              <label className="flex items-center gap-2 text-[0.72rem] font-headline uppercase text-[#00FF41]/70">
                <input type="checkbox" checked={useMmr} onChange={(e) => setUseMmr(e.target.checked)} className="accent-[#00FF41]" />
                MMR diversity
              </label>
              <div className="flex items-center gap-2 text-[0.72rem] font-headline uppercase text-[#00FF41]/70">
                top_N
                <input
                  type="range" min={3} max={10} step={1} value={topN}
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="w-24 h-1 appearance-none bg-[#00FF41]/20 rounded outline-none accent-[#00FF41]"
                />
                <span className="text-[#00FF41] font-bold tabular-nums">{topN}</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-12 gap-4">
            {/* Catalogue */}
            <div className="viz-panel col-span-12 lg:col-span-7">
              <h3 className="viz-title">
                <span className="material-symbols-outlined text-sm mr-2">grid_view</span>
                {tr.recommender.catalog(data.catalog.length)}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[520px] overflow-y-auto scrollbar-hide pr-1">
                {data.catalog.map((p) => (
                  <ProductCard key={p.id} product={p} selected={selected.has(p.id)} onToggle={toggle} />
                ))}
              </div>
            </div>

            {/* Recommendations */}
            <div className="viz-panel col-span-12 lg:col-span-5">
              <h3 className="viz-title">
                <span className="material-symbols-outlined text-sm mr-2">recommend</span>
                {tr.recommender.recommendations(topN)}
              </h3>
              {selected.size === 0 && (
                <div className="text-[0.7rem] font-headline uppercase text-[#00FF41]/65 py-8 text-center">
                  {tr.recommender.emptySelection}
                </div>
              )}
              {recommendations && recommendations.length > 0 && (
                <div className="space-y-2 max-h-[520px] overflow-y-auto scrollbar-hide pr-1">
                  {recommendations.map((r) => (
                    <div key={r.id}>
                      <div onClick={() => setExplainId((id) => (id === r.id ? null : r.id))} className="cursor-pointer">
                        <ProductCard product={r} similarity={r.similarity} />
                      </div>
                      {explainId === r.id && profileVec && (
                        <ExplainPanel
                          profile={profileVec}
                          item={data.featureMatrix[data.catalog.findIndex((p) => p.id === r.id)]}
                          vocab={data.tfidfVocab}
                          breakdown={data.featureBreakdown}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[0.7rem] text-[#00FF41]/65 font-headline mt-3 normal-case leading-relaxed">
                {tr.recommender.explainCaption}
              </p>
            </div>
          </div>
        </>
      )}

      {tab === "how" && (
        <div className="grid grid-cols-12 gap-4 mt-4">
          <div className="viz-panel col-span-12 lg:col-span-7">
            <h3 className="viz-title">
              <span className="material-symbols-outlined text-sm mr-2">help</span>
              {tr.recommender.explainer.title}
            </h3>
            <div className="text-[0.72rem] text-[#00FF41]/75 font-headline leading-relaxed space-y-3 normal-case">
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.recommender.explainer.problemLabel}</span>{" "}
                {tr.recommender.explainer.problem}
              </p>
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.recommender.explainer.solutionLabel}</span>{" "}
                {tr.recommender.explainer.solution}
              </p>
              <p>
                <span className="text-[#00FF41] font-bold uppercase">{tr.recommender.explainer.tryItLabel}</span>{" "}
                {tr.recommender.explainer.tryIt}
              </p>
            </div>
          </div>

          <div className="viz-panel col-span-12 lg:col-span-5">
            <h3 className="viz-title">
              <span className="material-symbols-outlined text-sm mr-2">account_tree</span>
              {tr.recommender.explainer.pipelineTitle}
            </h3>
            <div className="text-[0.66rem] text-[#00FF41]/70 font-headline leading-relaxed space-y-2 normal-case">
              {tr.recommender.explainer.steps.map((step) => (
                <p key={step} className="pl-3 border-l border-[#00FF41]/20">{step}</p>
              ))}
            </div>
            <p className="text-[0.6rem] text-[#00FF41]/60 font-headline mt-3 uppercase">
              {tr.recommender.subtitle}
            </p>
          </div>
        </div>
      )}

      {tab === "evidence" && (
        <div className="grid grid-cols-12 gap-4 mt-4">
          <PersonaSummary personas={data.personas} onApply={(history) => { setSelected(new Set(history)); setTab("try"); }} />
          {recommendations && recommendations.length > 0 && <SimilarityBars recs={recommendations} />}
        </div>
      )}

      <div className="h-8" />
    </div>
  );
}
