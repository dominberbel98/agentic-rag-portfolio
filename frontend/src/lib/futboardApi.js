/**
 * FUTBOARD API client.
 *
 * One place that knows the endpoints and the error shape, so components deal in
 * data and never in `fetch`.
 *
 * The timeout is generous on purpose. Neon suspends its compute after five
 * minutes without connections, so the first request after a quiet spell pays a
 * wake-up of roughly half a second — occasionally a few seconds if the region is
 * cold. A tight timeout would turn a normal wake into a spurious error, which is
 * why callers get an explicit "waking" state rather than a spinner that gives up.
 */

const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//api.${window.location.hostname.replace(/^www\./, "")}`;

const BASE = `${API_URL}/api/futboard`;
const TIMEOUT_MS = 30000;

export class FutboardApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "FutboardApiError";
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    throw new FutboardApiError(
      error.name === "AbortError" ? "The request timed out." : "Could not reach the server.",
      0,
    );
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    // FastAPI puts a string in `detail` for our own errors and a list of field
    // problems there for validation failures. Flatten both into one sentence.
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || "invalid value").join("; ")
      : detail || `Request failed (${response.status})`;
    throw new FutboardApiError(message, response.status);
  }
  return payload;
}

export const futboardApi = {
  health: () => request("/health"),

  listTeams: () => request("/teams"),
  createTeam: (name) => request("/teams", { method: "POST", body: { name } }),

  listPlayers: () => request("/players"),
  createPlayer: (name, teamId = null) =>
    request("/players", { method: "POST", body: { name, team_id: teamId } }),

  addPlayerToTeam: (teamId, playerId) =>
    request(`/teams/${teamId}/players`, { method: "POST", body: { player_id: playerId } }),
  removePlayerFromTeam: (teamId, playerId) =>
    request(`/teams/${teamId}/players/${playerId}`, { method: "DELETE" }),

  listMatches: (limit = 20) => request(`/matches?limit=${limit}`),
  saveMatch: (match) => request("/matches", { method: "POST", body: match }),

  stats: () => request("/stats"),
};

export default futboardApi;
