/**
 * FUTBOARD strings, in English and Spanish.
 *
 * Separate from `en.js` for two reasons. The rest of the site is English-only
 * and its dictionary is guarded by a test that fails on Spanish text; putting
 * translations in there would mean weakening that guard for the whole site.
 * And FUTBOARD is the one section with an audience that is not a recruiter —
 * it gets used on a pitch by people who would rather read Spanish — so it
 * carries its own switch.
 *
 * The two trees must stay key-for-key identical. A key present in `en` and
 * missing from `es` renders as `undefined` rather than failing the build, so
 * tests/test_futboard_i18n.py compares them.
 */

import { useCallback, useEffect, useState } from "react";

export const LANGUAGES = ["en", "es"];
const STORAGE_KEY = "futboard.language";

export const dictionary = {
  en: {
    title: "FUTBOARD",
    tagline: "Match clock, squads and statistics for our games",
    back: "Back",

    hub: {
      newMatch: "New match",
      newMatchHint: "Pick two teams and start the clock",
      squads: "Teams & players",
      squadsHint: "Create teams, register players",
      stats: "Statistics",
      statsHint: "Scorers, teams, match history",
      recent: "Recent matches",
      topScorer: "Top scorer",
      noMatchesYet: "No matches recorded yet",
      goalCount: (n) => `${n} ${n === 1 ? "goal" : "goals"}`,
      matchCount: (n) => `${n} ${n === 1 ? "match" : "matches"}`,
    },

    squads: {
      title: "Teams & players",
      teams: "Teams",
      players: "Players",
      newTeam: "New team",
      newPlayer: "New player",
      teamName: "Team name",
      playerName: "Player name",
      create: "Create",
      noTeam: "No team yet",
      playerCount: (n) => `${n} ${n === 1 ? "player" : "players"}`,
      squadOf: (name) => `Squad — ${name}`,
      addPlayer: "Add player to this team",
      remove: "Remove from team",
      emptyTeams: "No teams yet. Create the first one.",
      emptyPlayers: "No players yet.",
      emptySquad: "Nobody in this squad yet.",
      alreadyIn: "Already in this squad",
      selectTeamHint: "Select a team to manage its squad",
      playsFor: "Plays for",
      noTeams: "no team",
    },

    setup: {
      title: "New match",
      home: "Home team",
      away: "Away team",
      pickTwo: "Pick two different teams",
      whoPlays: (name) => `Who is playing for ${name}?`,
      selectAll: "All",
      selectNone: "None",
      halfMinutes: "Minutes per half",
      subInterval: "Substitution alert every",
      minutes: "min",
      start: "Start match",
      emptySquad: "This team has no players registered.",
      needPlayers: "Pick at least one player per team.",
    },

    live: {
      firstHalf: "1st half",
      secondHalf: "2nd half",
      halfTime: "Half time",
      fullTime: "Full time",
      of: (total) => `of ${total}:00`,
      goal: "Goal",
      whoScored: (name) => `Who scored for ${name}?`,
      notSpecified: "Not specified",
      undoLast: "Undo last goal",
      pause: "Pause",
      resume: "Resume",
      endHalf: "End half",
      startSecondHalf: "Start 2nd half",
      endMatch: "End match",
      nextSubs: "Next subs in",
      subsNow: "SUBSTITUTIONS",
      halfOver: "First half over",
      matchOver: "Match over",
      save: "Save match",
      saving: "Saving…",
      saved: "Match saved",
      discard: "Discard",
      discardConfirm: "Discard this match without saving?",
      resume_match: "A match is in progress",
      resumeHint: "Carry on where you left off, or discard it.",
      soundOn: "Sound on",
      soundOff: "Sound off",
      scorers: "Scorers",
      noScorers: "No goals yet",
    },

    stats: {
      title: "Statistics",
      players: "Players",
      teams: "Teams",
      history: "Match history",
      name: "Name",
      matches: "MP",
      goals: "Goals",
      perMatch: "G/M",
      playsFor: "Teams",
      played: "P",
      won: "W",
      drawn: "D",
      lost: "L",
      goalsFor: "GF",
      goalsAgainst: "GA",
      goalDifference: "GD",
      empty: "Nothing recorded yet. Play a match.",
    },

    common: {
      loading: "Loading",
      waking: "Waking the database…",
      error: "Something went wrong",
      retry: "Retry",
      unavailable: "FUTBOARD is not available right now.",
      cancel: "Cancel",
      close: "Close",
      required: "Enter a name first",
    },
  },

  es: {
    title: "FUTBOARD",
    tagline: "Cronómetro, equipos y estadísticas de nuestros partidos",
    back: "Volver",

    hub: {
      newMatch: "Nuevo partido",
      newMatchHint: "Elige dos equipos y arranca el reloj",
      squads: "Equipos y jugadores",
      squadsHint: "Crea equipos, registra jugadores",
      stats: "Estadísticas",
      statsHint: "Goleadores, equipos, historial",
      recent: "Últimos partidos",
      topScorer: "Máximo goleador",
      noMatchesYet: "Todavía no hay partidos",
      goalCount: (n) => `${n} ${n === 1 ? "gol" : "goles"}`,
      matchCount: (n) => `${n} ${n === 1 ? "partido" : "partidos"}`,
    },

    squads: {
      title: "Equipos y jugadores",
      teams: "Equipos",
      players: "Jugadores",
      newTeam: "Nuevo equipo",
      newPlayer: "Nuevo jugador",
      teamName: "Nombre del equipo",
      playerName: "Nombre del jugador",
      create: "Crear",
      noTeam: "Sin equipo",
      playerCount: (n) => `${n} ${n === 1 ? "jugador" : "jugadores"}`,
      squadOf: (name) => `Plantilla — ${name}`,
      addPlayer: "Añadir jugador a este equipo",
      remove: "Quitar del equipo",
      emptyTeams: "Aún no hay equipos. Crea el primero.",
      emptyPlayers: "Aún no hay jugadores.",
      emptySquad: "Todavía no hay nadie en esta plantilla.",
      alreadyIn: "Ya está en esta plantilla",
      selectTeamHint: "Selecciona un equipo para gestionar su plantilla",
      playsFor: "Juega en",
      noTeams: "sin equipo",
    },

    setup: {
      title: "Nuevo partido",
      home: "Equipo local",
      away: "Equipo visitante",
      pickTwo: "Elige dos equipos distintos",
      whoPlays: (name) => `¿Quién juega en ${name}?`,
      selectAll: "Todos",
      selectNone: "Ninguno",
      halfMinutes: "Minutos por parte",
      subInterval: "Aviso de cambios cada",
      minutes: "min",
      start: "Empezar partido",
      emptySquad: "Este equipo no tiene jugadores registrados.",
      needPlayers: "Elige al menos un jugador por equipo.",
    },

    live: {
      firstHalf: "1ª parte",
      secondHalf: "2ª parte",
      halfTime: "Descanso",
      fullTime: "Final",
      of: (total) => `de ${total}:00`,
      goal: "Gol",
      whoScored: (name) => `¿Quién ha marcado en ${name}?`,
      notSpecified: "Sin especificar",
      undoLast: "Deshacer último gol",
      pause: "Pausa",
      resume: "Seguir",
      endHalf: "Terminar parte",
      startSecondHalf: "Empezar 2ª parte",
      endMatch: "Terminar partido",
      nextSubs: "Próximos cambios en",
      subsNow: "CAMBIOS",
      halfOver: "Fin de la primera parte",
      matchOver: "Partido terminado",
      save: "Guardar partido",
      saving: "Guardando…",
      saved: "Partido guardado",
      discard: "Descartar",
      discardConfirm: "¿Descartar el partido sin guardarlo?",
      resume_match: "Hay un partido en curso",
      resumeHint: "Continúa donde lo dejaste, o descártalo.",
      soundOn: "Sonido activado",
      soundOff: "Sonido apagado",
      scorers: "Goleadores",
      noScorers: "Aún no hay goles",
    },

    stats: {
      title: "Estadísticas",
      players: "Jugadores",
      teams: "Equipos",
      history: "Historial",
      name: "Nombre",
      matches: "PJ",
      goals: "Goles",
      perMatch: "G/P",
      playsFor: "Equipos",
      played: "PJ",
      won: "G",
      drawn: "E",
      lost: "P",
      goalsFor: "GF",
      goalsAgainst: "GC",
      goalDifference: "DG",
      empty: "Todavía no hay nada. Juega un partido.",
    },

    common: {
      loading: "Cargando",
      waking: "Despertando la base de datos…",
      error: "Algo ha ido mal",
      retry: "Reintentar",
      unavailable: "FUTBOARD no está disponible ahora mismo.",
      cancel: "Cancelar",
      close: "Cerrar",
      required: "Escribe un nombre primero",
    },
  },
};

function initialLanguage() {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (LANGUAGES.includes(stored)) return stored;
  // A visitor whose browser is set to Spanish gets Spanish on the first visit;
  // everyone else gets English, like the rest of the site.
  const preferred = (window.navigator.language || "").slice(0, 2).toLowerCase();
  return preferred === "es" ? "es" : "en";
}

/** The active FUTBOARD language, its dictionary, and a toggle. */
export function useFutboardLanguage() {
  const [language, setLanguage] = useState(initialLanguage);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, language);
    } catch {
      /* private browsing; the choice just will not persist */
    }
  }, [language]);

  const toggle = useCallback(
    () => setLanguage((current) => (current === "en" ? "es" : "en")),
    [],
  );

  return { language, setLanguage, toggle, f: dictionary[language] };
}

export default dictionary;
