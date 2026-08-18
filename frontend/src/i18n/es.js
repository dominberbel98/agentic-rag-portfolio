/**
 * Spanish strings. Mirrors `en.js` key for key.
 *
 * English stays the source of truth: it is what a recruiter sees first and what
 * the assistant's corpus is written in. This file is a translation of it, and
 * tests/test_i18n.py fails if a key exists in one tree and not the other, or if
 * a key is a function in one and a plain string in the other — both render as
 * `undefined` or throw at runtime rather than failing the build.
 *
 * Two categories are deliberately NOT translated:
 *
 * The UPPER_SNAKE terminal labels stay largely as they are. They are a visual
 * device borrowed from a console, not prose, and `CREDIT_SCORING_MODEL` reads
 * the same to a Spanish speaker. Where a word genuinely differs it is
 * translated (`LIVE_STANDINGS` → `CLASIFICACION_EN_VIVO`).
 *
 * Technical vocabulary keeps its English form, because that is what it is called
 * in Spanish too: TF-IDF, Monte Carlo, Gradient Boosting, AUC, PySpark. A
 * translated "Impulso de gradiente" would be less clear, not more.
 */

export const t = {
  // ── Shell ────────────────────────────────────────────────────────────────
  app: {
    brand: "NEURAL_LINK_DS_V1.0",
    owner: "DOMINGO BERBEL",
    workspace: "DS_WORKSPACE",
    session: "SESIÓN: DATA_EXPLORER",
    menuLabel: "Menú",
    mascotTitle: "¿Qué es esto?",
    mascotLead:
      "Un CV al que puedes preguntar. El asistente busca en mis documentos reales de carrera y responde a partir de ellos: fechas, notas, empresas y tecnologías de verdad, sin inventar nada.",
    mascotSections: [
      {
        label: "Visualizaciones",
        text: "La tabla de La Liga en vivo, reconstruida cada 30 minutos por un trabajo de PySpark programado.",
      },
      {
        label: "Modelos",
        text: "Tres que se ejecutan en tu navegador: una previsión de temporada, un scorecard de crédito y un recomendador de productos. Mueve las entradas y mira cómo responden.",
      },
      {
        label: "Certificaciones",
        text: "Las verificadas, con lo que cubre cada una.",
      },
      {
        label: "Futboard",
        text: "Un marcador para nuestros partidos de los domingos, sobre Postgres serverless (Neon): esquema relacional, estadísticas agregadas en SQL y reloj gobernado por marcas de tiempo.",
      },
    ],
    mascotDismiss: "Ocultar",
    mascotOpen: "¿Qué es esto?",
    mascotClose: "Cerrar",
    languageLabel: "Idioma",
  },

  nav: {
    chat_cv: "chat_cv",
    visualizaciones: "visualizaciones",
    modelos: "modelos",
    prediccion_la_liga: "prediccion_laliga",
    modelo_scoring: "scoring_credito",
    modelo_recomendation: "recomendador",
    certificaciones: "certificaciones",
    futboard: "futboard",
  },

  footer: {
    index: (documents) => `ÍNDICE: ${documents} DOCS`,
    indexUnknown: "ÍNDICE: —",
    model: (name) => `MODELO: ${name.toUpperCase()}`,
    embeddings: (name) => `EMBED: ${name.toUpperCase()}`,
    latency: (ms) => `ÚLTIMA RESPUESTA: ${ms} MS`,
    firstToken: (ms) => `TTFT: ${ms} MS`,
    idle: "EN ESPERA",
    running: "EJECUTANDO_INFERENCIA",
    domain: "domingoberbel.com",
  },

  // ── Chat ─────────────────────────────────────────────────────────────────
  chat: {
    windowTitle: "terminal — zsh — jupyter-kernel",
    kernelBusy: "KERNEL: OCUPADO (PYTHON 3.11)",
    kernelIdle: "KERNEL: LIBRE (PYTHON 3.11)",
    assistant: "DS_ASISTENTE",
    userInput: "ENTRADA_USUARIO",
    processing: "PROCESANDO...",
    placeholder: "PREGUNTA POR MODELOS, HERRAMIENTAS O EXPERIENCIA...",
    send: "Enviar",
    connectionError: "No se ha podido contactar con el servidor.",

    suggestionsLabel: "PRUEBA:",
    suggestions: [
      "¿A qué se dedica Domingo y en qué es mejor?",
      "¿Qué estudió y con qué notas?",
      "¿Qué ha conseguido en sus puestos hasta ahora?",
      "¿Encajaría en un puesto de data science en mi equipo?",
    ],
    boot: [
      "[0.00104] IMPORTANDO PANDAS AS PD...",
      "[0.00255] CARGANDO PRETRAINED_MODELS/BERBEL_CV.PKL...",
      "[0.00389] INICIALIZANDO MOTOR DE INFERENCIA...",
    ],
    contact: {
      heading: "— Contacto directo",
      dismiss: "Cerrar y seguir hablando",
      viewLinkedin: "Ver perfil de LinkedIn",
      name: "Tu nombre",
      email: "Tu email",
      message: "Describe brevemente la oportunidad o lo que necesitas",
      submit: "Enviar mensaje",
      subject: (name) => `Contacto de reclutador - ${name}`,
      body: (name, email, message) =>
        `Nombre: ${name}\nEmail: ${email}\n\nMensaje:\n${message}`,
    },
  },

  // ── Shared ───────────────────────────────────────────────────────────────
  common: {
    loading: "CARGANDO_DATOS",
    errorPrefix: "ERROR_AL_CARGAR_DATOS",
    updated: "Actualizado",
    season: "Temporada",
    matchday: "Jornada",
    noData: "SIN_DATOS_DISPONIBLES",
  },

  tabs: {
    tryIt: "Pruébalo",
    howItWorks: "Cómo funciona",
    evidence: "Evidencia",
  },

  zones: {
    champions: "Champions League",
    europa: "Europa League",
    conference: "Conference League",
    mid: "Zona media",
    relegation: "Descenso",
  },

  seasonPhase: {
    preseason: "La temporada no ha empezado",
    in_progress: "Temporada en curso",
    finished: "Temporada terminada",
  },

  // ── La Liga ──────────────────────────────────────────────────────────────
  laliga: {
    title: "PANEL_LA_LIGA",
    pipeline: "Pipeline: PySpark → GitHub Actions (30 min) → SportsRC API",
    loading: "CARGANDO_DATOS_DE_LA_LIGA",
    error: "ERROR_AL_CARGAR_DATOS",
    preseasonNotice:
      "La temporada no ha empezado. La clasificación, la forma y los ratios se rellenan cuando se juegan partidos.",
    lowConfidenceNotice: (played) =>
      `Solo ${played} jornada${played === 1 ? "" : "s"} jugada${played === 1 ? "" : "s"} — los ratios por equipo son todavía muy inestables.`,

    standings: {
      title: "CLASIFICACION_EN_VIVO",
      pos: "#",
      team: "Equipo",
      played: "PJ",
      won: "G",
      drawn: "E",
      lost: "P",
      goalsFor: "GF",
      goalsAgainst: "GC",
      goalDifference: "DG",
      points: "PTS",
      form: "FORMA",
      formEmpty: "—",
      formTooltip: "Últimos 5, el más reciente primero",
    },

    points: { title: "DISTRIBUCION_DE_PUNTOS", label: "Puntos" },

    attackDefence: {
      title: "ATAQUE_VS_DEFENSA",
      goalsFor: "Goles a favor",
      goalsAgainst: "Goles en contra",
      points: "Puntos",
      xLabel: "GF →",
      yLabel: "GC →",
      caption: "Tamaño de burbuja = puntos · Ideal: arriba a la derecha (muchos GF, pocos GC)",
    },

    goalDiff: { title: "ESPECTRO_DE_DIFERENCIA_DE_GOLES", label: "DG" },

    winRate: {
      title: "MATRIZ_DE_RESULTADOS",
      win: "% Victoria",
      draw: "% Empate",
      loss: "% Derrota",
    },

    radar: {
      title: "RADAR_TOP_5",
      won: "Victorias",
      draw: "Empates",
      lost: "Derrotas",
      goalsFor: "GF",
      goalsAgainst: "GC",
      caption: "Ejes normalizados entre los 5 primeros · Más área = mejor · Menos GC = defensa más sólida",
    },

    results: {
      title: "ULTIMOS_RESULTADOS",
      empty: "Todavía no se ha jugado ningún partido esta temporada.",
      live: "EN VIVO",
      matchdayShort: (n) => `J${n}`,
    },

    fixtures: {
      title: "PROXIMOS_PARTIDOS",
      empty: "No hay próximos partidos anunciados.",
      caption: "Filtrados de un feed global cruzando ambos clubes con la tabla",
    },
  },

  // ── Predictive model ─────────────────────────────────────────────────────
  predictions: {
    title: "MODELOS_PREDICTIVOS_LA_LIGA",
    loading: "CARGANDO_PREDICCIONES",
    error: "ERROR_AL_CARGAR_PREDICCIONES",
    lowConfidence:
      "Se han jugado muy pocos partidos para una proyección con sentido. Extrapolar una jornada a una temporada de 38 no es un pronóstico, así que los números se retienen hasta que la muestra los sostenga.",
    subtitle: (season, matchday, total, sims) =>
      `Temporada ${season} · Jornada ${matchday} · ${total} jornadas en total · ${sims} simulaciones`,
    modelLine: (model, sims) =>
      `Modelo: ${model} · Poisson(λ=GF/partido) + ${sims} temporadas Monte Carlo`,
    shrinkageNote: (k) =>
      `Ratios contraídos hacia la media de la liga con k=${k}, así que un equipo parece medio hasta que demuestre lo contrario`,
    championProb: { title: "PROBABILIDAD_DE_TITULO", label: "P(Campeón)" },
    projectedPoints: {
      title: "PUNTOS_PROYECTADOS (IC 80%)",
      mean: "Pts (media)",
      meanLabel: "Media",
      range: "Rango",
      interval: "Intervalo 80%",
    },
    goals: {
      title: "PREDICCION_DE_GOLES",
      mostGoals: "Más goles marcados",
      mostConceded: "Más goles recibidos",
      leastConceded: "Menos goles recibidos",
    },
    importance: {
      title: "IMPORTANCIA_DE_VARIABLES (XGBOOST)",
      ppg: "Puntos/partido",
      winRate: "Ratio de victoria",
      drawRate: "Ratio de empate",
      lossRate: "Ratio de derrota",
      gfPerGame: "GF/partido",
      gaPerGame: "GC/partido",
      gdPerGame: "DG/partido",
      points: "Puntos",
      goalDifference: "Diferencia de goles",
    },
    importanceCaption: "XGBoost multi:softprob · Variables normalizadas por partido",
    projectedTable: {
      title: "TABLA_PROYECTADA (J38)",
      team: "Equipo",
      current: "Ahora",
      projected: "Proy.",
      interval: "IC 80%",
      goalsFor: "GF",
      goalsAgainst: "GC",
    },
    methodology: {
      title: "METODOLOGIA",
      steps: (simulations) => [
        "1. Ingeniería de variables: ratios por partido (pts/partido, % victoria, GF/P, GC/P, DG/P), contraídos hacia un prior al principio de la temporada",
        "2. Simulación de Poisson: para cada partido restante, GF ~ Poisson(λ_gf), GC ~ Poisson(λ_gc) → resultado → puntos",
        `3. Monte Carlo: ${simulations} temporadas simuladas → distribuciones de puntos, goles y posición final`,
        "4. XGBoost (multi:softprob): clasificador de zona (Champions / Europa / Conference / Media / Descenso) sobre las variables actuales",
      ],
    },
  },

  // ── Credit scoring ───────────────────────────────────────────────────────
  scoring: {
    title: "MODELO_DE_SCORING_DE_CREDITO",
    loading: "CARGANDO_MODELO_DE_SCORING",
    error: "ERROR_AL_CARGAR_EL_MODELO_DE_SCORING",
    metrics: { title: "METRICAS_DEL_MODELO (conjunto de test)" },
    roc: { title: "CURVA_ROC" },
    importance: { title: "IMPORTANCIA_DE_VARIABLES" },
    distribution: { title: "DISTRIBUCION_DE_SCORE (300–850)" },
    simulator: { title: "SIMULADOR_INTERACTIVO" },
    bands: {
      poor: "Malo",
      fair: "Regular",
      good: "Bueno",
      veryGood: "Muy bueno",
      exceptional: "Excepcional",
    },
    features: {
      age: "Edad",
      annual_income: "Ingresos anuales",
      employment_years: "Años empleado",
      payment_history_pct: "% Pagos puntuales",
      credit_utilization: "% Uso del crédito",
      credit_age_years: "Antigüedad del crédito",
      num_credit_accounts: "Cuentas de crédito",
      recent_inquiries: "Consultas recientes",
      derogatory_marks: "Marcas negativas",
      loan_amount: "Importe del préstamo",
      loan_to_income: "Préstamo / ingresos",
      loan_purpose: "Finalidad del préstamo",
      home_ownership: "Régimen de vivienda",
      debt_to_income: "Deuda / ingresos",
    },
    units: { years: "años" },
    defaultProb: "Probabilidad de impago",
    creditScore: "Score de crédito",
    score: "Score",
    rocCaption: "Diagonal roja = clasificador aleatorio · Área verde = poder discriminante",
    importanceCaption: "Caída media de AUC al permutar la variable · Barra más larga = más impacto",
    sampleTable: {
      title: "SOLICITANTES_DE_EJEMPLO (conjunto de test)",
      age: "Edad",
      income: "Ingresos",
      loan: "Préstamo",
      dti: "DTI",
      payments: "Pagos",
      utilisation: "Uso",
      marks: "Marcas",
      probLr: "P(LR)",
      probGbm: "P(GBM)",
      score: "Score",
      band: "Banda",
    },
    loadingModel: "ENTRENANDO_MODELO",
    generated: (when) => `Generado: ${when}`,
    datasetLine: (n, rate, train, test) =>
      `Dataset: ${n} solicitantes · tasa de impago ${rate}% · división estratificada ${train}/${test}`,
    applicants: (n) => `${n} solicitantes`,
    inferenceNote:
      "Inferencia en el navegador: sigmoid(β·x) con coeficientes de LR exportados · PDO=50, base=600, odds=50",
    drivers: {
      title: "POR QUÉ ESTE SCORE",
      caption:
        "Cada barra es la contribución de una entrada al score de este solicitante, según los coeficientes de la regresión logística",
      raises: "Sube el score",
      lowers: "Baja el score",
    },
    explainer: {
      title: "¿QUÉ HACE ESTE MODELO?",
      problemLabel: "PROBLEMA:",
      problem:
        "Un banco recibe 5.000 solicitudes de préstamo y tiene que decidir cuáles aprobar sin revisarlas una a una a mano. ¿Quién pagará y quién dejará de pagar?",
      solutionLabel: "SOLUCIÓN:",
      solution:
        "Dos modelos aprenden el patrón de quienes han impagado antes — historial de pagos puntuales, uso del crédito, marcas negativas, ingresos — y devuelven una probabilidad de impago para cada nuevo solicitante. Esa probabilidad se convierte en un score de 300 a 850 al estilo FICO con la fórmula bancaria PDO: cuanto más alto el score, más fiable el solicitante.",
      tryItLabel: "CÓMO PROBARLO:",
      tryIt:
        "En el panel del scorecard interactivo, mueve los deslizadores (ingresos, pagos puntuales, uso del crédito) y observa cómo cambian el score y la probabilidad de impago en vivo. La inferencia corre en tu navegador, con coeficientes de regresión logística exportados desde scikit-learn.",
      detailsSummary: "▸ detalle técnico (pipeline de ML)",
      pipelineTitle: "DETALLE_TECNICO (PIPELINE DE ML)",
      steps: [
        "1. Dataset sintético calibrado a una tasa de impago del ~17% (12 variables numéricas + 2 categóricas)",
        "2. Preprocesado: StandardScaler + OneHotEncoder · división estratificada 75/25",
        "3. Regresión logística (interpretable) + Gradient Boosting calibrado con sigmoide de Platt",
        "4. Validación: StratifiedKFold de 5 particiones (AUC, AvgPrecision, F1) + conjunto de test reservado",
        "5. Scorecard PDO: factor = PDO / ln 2, offset = base − factor · ln(odds), recortado a 300–850",
        "6. Importancia por permutación, ROC, KS, Gini y Brier sobre el conjunto de test",
      ],
    },
  },

  // ── Recommender ──────────────────────────────────────────────────────────
  recommender: {
    title: "MOTOR_DE_RECOMENDACION_DE_PRODUCTOS",
    loading: "CARGANDO_MODELO_DE_RECOMENDACION",
    error: "ERROR_AL_CARGAR_EL_MODELO_DE_RECOMENDACION",
    personas: { title: "PERFILES_DE_DEMO" },
    similarity: { title: "RANKING_DE_SIMILITUD", label: "Similitud" },
    similarityLabel: "similitud",
    catalog: (n) => `CATALOGO (${n})`,
    recommendations: (n) => `RECOMENDACIONES (top-${n})`,
    metrics: { title: "METRICAS_DEL_MODELO" },
    reset: "Reiniciar",
    load: "Cargar",
    clear: "Limpiar",
    loadingCatalog: "CARGANDO_CATALOGO",
    subtitle: "Basado en contenido · TF-IDF + categoría + precio/valoración · reordenado con MMR",
    stats: (products, categories, dim, coverage) =>
      `Catálogo: ${products} productos · ${categories} categorías · dimensión ${dim} · cobertura de demo ${coverage}%`,
    selectedCount: "Seleccionados:",
    emptySelection: "elige un producto del catálogo",
    explainCaption:
      "Pulsa una recomendación para desglosar su similitud: qué términos TF-IDF, más el peso de la categoría y del precio/valoración",
    personaItems: (n, diversity) => `${n} artículos · diversidad intra-lista ${diversity}`,
    explain: {
      title: "¿Por qué? (desglose de similitud)",
      tfidf: "TF-IDF",
      category: "Categoría",
      priceRating: "Precio/Valoración",
    },
    explainer: {
      title: "¿QUÉ HACE ESTE MODELO?",
      problemLabel: "PROBLEMA:",
      problem:
        "Un catálogo de comercio electrónico con 32 productos quiere sugerir artículos parecidos a lo que ya le gusta a cada usuario, sin obligarle a buscar.",
      solutionLabel: "SOLUCIÓN:",
      solution:
        "Cada producto se convierte en un vector numérico: la descripción con TF-IDF, la categoría en one-hot, y el precio y la valoración escalados. El perfil del usuario es la media de los vectores de los productos que ha elegido. Las recomendaciones son los productos más cercanos a ese perfil por similitud del coseno, con un reordenado MMR que evita devolver seis artículos casi idénticos.",
      tryItLabel: "CÓMO PROBARLO:",
      tryIt:
        "Pulsa productos del catálogo, o carga uno de los perfiles de demo de abajo. La lista de la derecha se recalcula al instante, en el navegador. Activa la diversidad MMR para ver cuánto varía el resultado, mueve top_N, y pulsa una recomendación para ver por qué se eligió: qué términos TF-IDF, y cuánto peso vino de la categoría y del precio.",
      detailsSummary: "▸ detalle técnico (pipeline de ML)",
      pipelineTitle: "DETALLE_TECNICO (PIPELINE DE ML)",
      steps: [
        "1. Ingeniería de variables por artículo: TF-IDF (1-2 gramas, stop-words EN, máx. 120) + categoría one-hot · 0,6 + MinMax(precio, valoración) · 0,4",
        "2. Perfil de usuario u = media(v_i) sobre los artículos seleccionados",
        "3. score(i) = similitud_coseno(u, v_i) para cada artículo no visto",
        "4. Reordenado MMR (λ=0,7): argmax_i [λ·score(i) − (1−λ)·máx sim(i, j) para j∈S]",
        "5. Inferencia en el navegador: la matriz de variables se exporta a JSON y todo el cálculo corre en JS",
      ],
    },
  },

  // ── FUTBOARD ─────────────────────────────────────────────────────────────
  futboard: {
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
      resumeMatch: "Hay un partido en curso",
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

  // ── Certifications ───────────────────────────────────────────────────────
  certifications: {
    title: "CERTIFICACIONES_DS",
    error: "ERROR_AL_CARGAR_CERTIFICACIONES",
    issued: "Emitida",
    expires: "Caduca",
    noExpiry: "Sin caducidad",
    skills: "Competencias",
    close: "Cerrar",
  },
};

export default t;
