import React, { useEffect, useState } from "react";
import { useT } from "../i18n";

/**
 * Certifications, read from /data/profile.json.
 *
 * They used to be a hardcoded array here *and* a list in the RAG source
 * documents — two places to edit, already drifting apart. Both are now generated
 * from data/profile.yml by scripts/build_kb.py.
 */
export default function Certificaciones() {
  const tr = useT();
  const [certs, setCerts] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetch("/data/profile.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setCerts(data.certifications || []))
      .catch((e) => setError(e.message));
  }, []);

  const C = tr.certifications;

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-[#FF4136] font-headline text-sm uppercase">
        {C.error}: {error}
      </div>
    );
  }

  if (!certs) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#00FF41] font-headline text-sm uppercase flicker">
          {tr.common.loading}<span className="cursor-blink">_</span>
        </div>
      </div>
    );
  }

  const selectedCert = certs.find((c) => c.id === selected);

  return (
    <div className="w-full h-full overflow-y-auto scrollbar-hide p-3 sm:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl font-bold text-[#00FF41] font-headline uppercase tracking-tight drop-shadow-[0_0_10px_rgba(0,255,65,0.4)]">
          {C.title}
        </h2>
        <p className="text-[0.65rem] text-[#00FF41]/65 font-headline uppercase mt-1">
          {certs.length} verified certifications · Data Engineering &amp; Analytics
        </p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {certs.map((cert) => (
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
            <div className="flex items-center gap-2 mt-1.5 text-[0.6rem] text-[#00FF41]/70 font-headline uppercase">
              <span>{cert.issuer}</span>
              <span className="text-[#00FF41]/55">·</span>
              <span>{cert.date}</span>
              {cert.expires && (
                <>
                  <span className="text-[#00FF41]/55">·</span>
                  <span className="text-[#00FF41]/60">exp. {cert.expires}</span>
                </>
              )}
            </div>

            {/* Skills tags */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {(cert.skills || []).map((skill) => (
                <span
                  key={skill}
                  className="text-[0.55rem] px-1.5 py-0.5 rounded border border-[#00FF41]/15 text-[#00FF41]/70 font-headline uppercase"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {selectedCert && (
        <div
          className="fixed inset-0 z-[200] bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div className="relative max-w-3xl w-full max-h-[85vh]">
            <img
              src={selectedCert.image}
              alt={selectedCert.title}
              className="w-full h-auto object-contain rounded-lg border border-[#00FF41]/20 shadow-[0_0_30px_rgba(0,255,65,0.1)]"
            />
            <button
              aria-label={C.close}
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
