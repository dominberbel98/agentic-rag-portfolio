import React, { useState } from "react";

const CERTS = [
  {
    id: "snowflake",
    title: "SnowPro Associate: Platform",
    issuer: "Snowflake",
    date: "Oct 2025",
    expires: "Oct 2027",
    image: "/certs/snowflake-snowpro.png",
    skills: ["Snowflake", "Data Warehousing", "Cloud", "SQL"],
  },
  {
    id: "databricks-fundamentals",
    title: "Databricks Fundamentals Accreditation",
    issuer: "Databricks Academy",
    date: "Nov 2025",
    image: "/certs/databricks-fundamentals.png",
    skills: ["Databricks", "Spark", "Lakehouse", "Delta Lake"],
  },
  {
    id: "databricks-genai",
    title: "Generative AI Fundamentals",
    issuer: "Databricks Academy",
    date: "May 2025",
    expires: "May 2027",
    image: "/certs/databricks-genai-fundamentals.png",
    skills: ["GenAI", "LLMs", "RAG", "Prompt Engineering"],
  },
  {
    id: "kaggle-sql",
    title: "Advanced SQL",
    issuer: "Kaggle",
    date: "Aug 2025",
    image: "/certs/kaggle-advanced-sql.png",
    skills: ["SQL", "Window Functions", "CTEs", "Analytics"],
  },
  {
    id: "ibm-python",
    title: "Data Analysis Using Python",
    issuer: "IBM Skills Network",
    date: "2025",
    image: "/certs/ibm-data-analysis-python.png",
    skills: ["Python", "Pandas", "NumPy", "scikit-learn"],
  },
  {
    id: "linkedin-powerbi",
    title: "Power BI Avanzado",
    issuer: "LinkedIn Learning",
    date: "May 2024",
    image: "/certs/linkedin-powerbi-avanzado.png",
    skills: ["Power BI", "DAX", "Data Modeling", "Dashboards"],
  },
];

export default function Certificaciones() {
  const [selected, setSelected] = useState(null);

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          CERTIFICACIONES_DS
        </h2>
        <p className="text-[0.65rem] text-[#00FF41]/40 font-headline uppercase mt-1">
          {CERTS.length} certificaciones verificadas · Data Engineering &amp; Analytics
        </p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {CERTS.map((cert) => (
          <div
            key={cert.id}
            onClick={() => setSelected(selected === cert.id ? null : cert.id)}
            className="viz-panel cursor-pointer hover:border-[#00FF41]/30 transition-all group"
          >
            {/* Image */}
            <div className="relative overflow-hidden rounded mb-3 bg-black/30">
              <img
                src={cert.image}
                alt={cert.title}
                className="w-full h-auto object-contain transition-transform duration-300 group-hover:scale-[1.02]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#0e0e0e]/60 to-transparent pointer-events-none" />
            </div>

            {/* Info */}
            <h3 className="text-[0.75rem] font-bold text-[#00FF41] font-headline uppercase leading-tight">
              {cert.title}
            </h3>
            <div className="flex items-center gap-2 mt-1.5 text-[0.6rem] text-[#00FF41]/50 font-headline uppercase">
              <span>{cert.issuer}</span>
              <span className="text-[#00FF41]/20">·</span>
              <span>{cert.date}</span>
              {cert.expires && (
                <>
                  <span className="text-[#00FF41]/20">·</span>
                  <span className="text-[#00FF41]/30">exp. {cert.expires}</span>
                </>
              )}
            </div>

            {/* Skills tags */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {cert.skills.map((s) => (
                <span
                  key={s}
                  className="text-[0.55rem] px-1.5 py-0.5 rounded border border-[#00FF41]/15 text-[#00FF41]/50 font-headline uppercase"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {selected && (
        <div
          className="fixed inset-0 z-[200] bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div className="relative max-w-3xl w-full max-h-[85vh]">
            <img
              src={CERTS.find((c) => c.id === selected)?.image}
              alt=""
              className="w-full h-auto object-contain rounded-lg border border-[#00FF41]/20 shadow-[0_0_30px_rgba(0,255,65,0.1)]"
            />
            <button
              className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-[#0e0e0e] border border-[#00FF41]/30 text-[#00FF41] flex items-center justify-center text-sm hover:bg-[#00FF41]/10"
              onClick={() => setSelected(null)}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="h-8" />
    </div>
  );
}
