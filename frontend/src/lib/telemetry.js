/**
 * A one-value store for live assistant telemetry.
 *
 * The footer used to display decorative numbers — "TRAINING_SET: 100%",
 * "OPTIMIZER: ADAM", "LEARNING_RATE: 0.001" — that described nothing. It now
 * shows the real index size, the real model, and the measured latency of the
 * last answer, which is both more honest and more interesting.
 *
 * This is a 20-line publish/subscribe rather than context or a state library:
 * Chat is the only publisher, the footer the only subscriber, and threading a
 * setter through App into Chat would touch more code than the feature is worth.
 */

const listeners = new Set();

let state = {
  documents: null,      // documents in the retrieval index
  embeddingModel: null,
  chatModel: null,
  lastLatencyMs: null,  // wall time of the most recent answer
  firstTokenMs: null,   // time to first streamed token
};

export function getTelemetry() {
  return state;
}

export function setTelemetry(patch) {
  state = { ...state, ...patch };
  for (const listener of listeners) listener(state);
}

export function subscribeTelemetry(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Fetch the backend's self-description. Failure is silent: the footer falls
 *  back to showing nothing rather than an error, since this is decoration. */
export async function loadBackendMeta(apiUrl) {
  try {
    const response = await fetch(`${apiUrl}/api/meta`);
    if (!response.ok) return;
    const data = await response.json();
    setTelemetry({
      documents: data.documents ?? null,
      embeddingModel: data.embeddingModel ?? null,
      chatModel: data.chatModel ?? null,
    });
  } catch {
    /* offline or cold-starting; leave the fields empty */
  }
}
