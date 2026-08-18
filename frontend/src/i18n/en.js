/**
 * User-facing strings, in one place.
 *
 * No i18n library: one target language does not justify the dependency. A flat
 * dictionary is here because the strings were previously scattered through the
 * JSX in a mix of Spanish and English, which is what made half of them easy to
 * miss.
 *
 * The CRT terminal aesthetic uses UPPER_SNAKE labels as a deliberate visual
 * device — those are kept, translated, not "cleaned up".
 */

export const t = {
  // ── Shell ────────────────────────────────────────────────────────────────
  app: {
    brand: "NEURAL_LINK_DS_V1.0",
    owner: "DOMINGO BERBEL",
    workspace: "DS_WORKSPACE",
    session: "SESSION: DATA_EXPLORER",
    menuLabel: "Menu",
    /*
      What the site is, for someone who just landed on it.
      Structured rather than one paragraph: the sidebar column is 256px wide, and
      a labelled list survives that width where prose does not. The point it has
      to land is that these are working models, not screenshots — a visitor who
      assumes the charts are static images never clicks them.
    */
    mascotTitle: "What is this?",
    mascotLead:
      "A CV you can interrogate. The assistant searches my real career documents and answers from them — actual dates, grades, employers and tech, with nothing invented.",
    mascotSections: [
      {
        label: "Visualisations",
        text: "The live La Liga table, rebuilt every 30 minutes by a PySpark job on a schedule.",
      },
      {
        label: "Models",
        text: "Three that run in your browser: a season forecast, a credit scorecard and a product recommender. Move the inputs and watch them respond.",
      },
      {
        label: "Certifications",
        text: "The verified ones, with what each covers.",
      },
      {
        // The one entry that names its stack. The others describe what a visitor
        // can do; this one is a working full-stack feature, so what it is built
        // on is the interesting part.
        label: "Futboard",
        text: "A scoreboard for our Sunday football, on serverless Postgres (Neon): relational schema, stats aggregated in SQL, clock driven by timestamps.",
      },
    ],
    mascotDismiss: "Dismiss",
    // On a phone there is no sidebar to dock the explainer in, so it opens as a
    // full-screen sheet from a button in the header instead.
    mascotOpen: "What is this?",
    mascotClose: "Close",
    languageLabel: "Language",
  },

  nav: {
    chat_cv: "chat_cv",
    visualizaciones: "visualisations",
    modelos: "models",
    prediccion_la_liga: "laliga_prediction",
    modelo_scoring: "credit_scoring",
    modelo_recomendation: "recommender",
    certificaciones: "certifications",
    futboard: "futboard",
  },

  // Real telemetry, not decoration. This used to read "TRAINING_SET: 100% ·
  // OPTIMIZER: ADAM · LEARNING_RATE: 0.001", none of which described anything
  // that existed.
  footer: {
    index: (documents) => `INDEX: ${documents} DOCS`,
    indexUnknown: "INDEX: —",
    model: (name) => `MODEL: ${name.toUpperCase()}`,
    embeddings: (name) => `EMBED: ${name.toUpperCase()}`,
    latency: (ms) => `LAST ANSWER: ${ms} MS`,
    firstToken: (ms) => `TTFT: ${ms} MS`,
    idle: "IDLE",
    running: "RUNNING_INFERENCE",
    domain: "domingoberbel.com",
  },

  // ── Chat ─────────────────────────────────────────────────────────────────
  chat: {
    windowTitle: "terminal — zsh — jupyter-kernel",
    kernelBusy: "KERNEL: BUSY (PYTHON 3.11)",
    kernelIdle: "KERNEL: IDLE (PYTHON 3.11)",
    assistant: "DS_ASSISTANT",
    userInput: "USER_INPUT",
    processing: "PROCESSING...",
    placeholder: "ASK ABOUT MODELS, TOOLS, OR EXPERIENCE...",
    send: "Send",
    connectionError: "Could not reach the backend.",

    // Drawn from the site's own logs: "a que se dedica" is by far the most asked
    // question, followed by education and achievements. The fourth is the one a
    // recruiter actually wants answered but nobody thought to type.
    suggestionsLabel: "TRY:",
    suggestions: [
      "What does Domingo do, and what is he best at?",
      "What did he study, and with what grades?",
      "What has he achieved in his roles so far?",
      "Would he fit a data science role on my team?",
    ],
    boot: [
      "[0.00104] IMPORTING PANDAS AS PD...",
      "[0.00255] LOADING PRETRAINED_MODELS/BERBEL_CV.PKL...",
      "[0.00389] INITIALIZING INFERENCE ENGINE...",
    ],
    contact: {
      heading: "— Direct contact",
      dismiss: "Close and keep chatting",
      viewLinkedin: "View LinkedIn profile",
      name: "Your name",
      email: "Your email",
      message: "Briefly describe the opportunity or what you need",
      submit: "Send message",
      subject: (name) => `Recruiter contact - ${name}`,
      body: (name, email, message) =>
        `Name: ${name}\nEmail: ${email}\n\nMessage:\n${message}`,
    },
  },

  // ── Shared ───────────────────────────────────────────────────────────────
  common: {
    loading: "LOADING_DATA",
    errorPrefix: "ERROR_LOADING_DATA",
    updated: "Updated",
    season: "Season",
    matchday: "Matchday",
    noData: "NO_DATA_AVAILABLE",
  },

  // Both model sections split into the same three views, so the labels are
  // shared rather than duplicated per section.
  tabs: {
    tryIt: "Try it",
    howItWorks: "How it works",
    evidence: "Evidence",
  },

  zones: {
    champions: "Champions League",
    europa: "Europa League",
    conference: "Conference League",
    mid: "Mid-table",
    relegation: "Relegation",
  },

  seasonPhase: {
    preseason: "Season has not started",
    in_progress: "Season in progress",
    finished: "Season finished",
  },

  // ── La Liga visualisations ───────────────────────────────────────────────
  laliga: {
    title: "LA_LIGA_DASHBOARD",
    pipeline: "Pipeline: PySpark → GitHub Actions (30 min) → SportsRC API",
    loading: "LOADING_LA_LIGA_DATA",
    error: "ERROR_LOADING_DATA",
    preseasonNotice:
      "The season has not started. Standings, form and rates populate once matches are played.",
    lowConfidenceNotice: (played) =>
      `Only ${played} matchday${played === 1 ? "" : "s"} played so far — per-team rates are still very noisy.`,

    standings: {
      title: "LIVE_STANDINGS",
      pos: "#",
      team: "Team",
      played: "P",
      won: "W",
      drawn: "D",
      lost: "L",
      goalsFor: "GF",
      goalsAgainst: "GA",
      goalDifference: "GD",
      points: "PTS",
      form: "FORM",
      formEmpty: "—",
      formTooltip: "Last 5, most recent first",
    },

    points: { title: "POINTS_DISTRIBUTION", label: "Points" },

    attackDefence: {
      title: "ATTACK_VS_DEFENCE",
      goalsFor: "Goals for",
      goalsAgainst: "Goals against",
      points: "Points",
      xLabel: "GF →",
      yLabel: "GA →",
      caption: "Bubble size = points · Ideal: top-right (many GF, few GA)",
    },

    goalDiff: { title: "GOAL_DIFFERENCE_SPECTRUM", label: "GD" },

    winRate: {
      title: "RESULT_RATE_MATRIX",
      win: "Win%",
      draw: "Draw%",
      loss: "Loss%",
    },

    radar: {
      title: "TOP_5_RADAR",
      won: "Wins",
      draw: "Draws",
      lost: "Losses",
      goalsFor: "GF",
      goalsAgainst: "GA",
      caption: "Axes normalised across the top 5 · Larger area = better · Fewer GA = tighter defence",
    },

    results: {
      title: "LATEST_RESULTS",
      empty: "No matches played yet this season.",
      live: "LIVE",
      matchdayShort: (n) => `MD${n}`,
    },

    fixtures: {
      title: "UPCOMING_FIXTURES",
      empty: "No upcoming fixtures announced.",
      caption: "Filtered from a global feed by matching both clubs against the table",
    },
  },

  // ── Predictive model ─────────────────────────────────────────────────────
  predictions: {
    title: "LA_LIGA_PREDICTIVE_MODELS",
    loading: "LOADING_PREDICTIONS",
    error: "ERROR_LOADING_PREDICTIONS",
    lowConfidence:
      "Too few matches played for a meaningful projection. Extrapolating one matchday across a 38-game season is not a forecast, so the numbers below are withheld until the sample supports them.",
    subtitle: (season, matchday, total, sims) =>
      `Season ${season} · Matchday ${matchday} · ${total} matchdays total · ${sims} simulations`,
    modelLine: (model, sims) =>
      `Model: ${model} · Poisson(λ=GF/game) + ${sims} Monte Carlo seasons`,
    shrinkageNote: (k) =>
      `Rates shrunk toward the league average with k=${k}, so a team looks average until it has earned otherwise`,
    championProb: { title: "CHAMPION_PROBABILITY", label: "P(Champion)" },
    projectedPoints: {
      title: "PROJECTED_POINTS (80% CI)",
      mean: "Pts (mean)",
      meanLabel: "Mean",
      range: "Range",
      interval: "80% interval",
    },
    goals: {
      title: "GOAL_PREDICTIONS",
      mostGoals: "Most goals scored",
      mostConceded: "Most goals conceded",
      leastConceded: "Fewest goals conceded",
    },
    importance: {
      title: "FEATURE_IMPORTANCE (XGBOOST)",
      ppg: "Points/game",
      winRate: "Win rate",
      drawRate: "Draw rate",
      lossRate: "Loss rate",
      gfPerGame: "GF/game",
      gaPerGame: "GA/game",
      gdPerGame: "GD/game",
      points: "Points",
      goalDifference: "Goal difference",
    },
    importanceCaption: "XGBoost multi:softprob · Features normalised per game",
    projectedTable: {
      title: "PROJECTED_TABLE (MD38)",
      team: "Team",
      current: "Now",
      projected: "Proj.",
      interval: "80% CI",
      goalsFor: "GF",
      goalsAgainst: "GA",
    },
    methodology: {
      title: "METHODOLOGY",
      steps: (simulations) => [
        "1. Feature engineering: per-match ratios (ppg, win%, GF/G, GA/G, GD/G), shrunk toward a prior early in the season",
        "2. Poisson simulation: for each remaining match, GF ~ Poisson(λ_gf), GA ~ Poisson(λ_ga) → result → points",
        `3. Monte Carlo: ${simulations} simulated seasons → distributions of points, goals and final position`,
        "4. XGBoost (multi:softprob): zone classifier (Champions / Europa / Conference / Mid / Relegation) over current features",
      ],
    },
  },

  // ── Credit scoring ───────────────────────────────────────────────────────
  scoring: {
    title: "CREDIT_SCORING_MODEL",
    loading: "LOADING_SCORING_MODEL",
    error: "ERROR_LOADING_SCORING_MODEL",
    metrics: { title: "MODEL_METRICS (test set)" },
    roc: { title: "ROC_CURVE" },
    importance: { title: "FEATURE_IMPORTANCE" },
    distribution: { title: "SCORE_DISTRIBUTION (300–850)" },
    simulator: { title: "INTERACTIVE_SIMULATOR" },
    bands: {
      poor: "Poor",
      fair: "Fair",
      good: "Good",
      veryGood: "Very Good",
      exceptional: "Exceptional",
    },
    features: {
      age: "Age",
      annual_income: "Annual income",
      employment_years: "Years employed",
      payment_history_pct: "% On-time payments",
      credit_utilization: "% Credit utilisation",
      credit_age_years: "Credit age",
      num_credit_accounts: "Credit accounts",
      recent_inquiries: "Recent enquiries",
      derogatory_marks: "Derogatory marks",
      loan_amount: "Loan amount",
      loan_to_income: "Loan / income",
      loan_purpose: "Loan purpose",
      home_ownership: "Home ownership",
      debt_to_income: "Debt / income",
    },
    units: { years: "yrs" },
    defaultProb: "Default probability",
    creditScore: "Credit score",
    score: "Score",
    rocCaption: "Red diagonal = random classifier · Green area = discriminative power",
    importanceCaption: "Mean AUC drop when the feature is permuted · Taller bar = more impact",
    sampleTable: {
      title: "SAMPLE_APPLICANTS (test set)",
      age: "Age",
      income: "Income",
      loan: "Loan",
      dti: "DTI",
      payments: "Payments",
      utilisation: "Util.",
      marks: "Marks",
      probLr: "P(LR)",
      probGbm: "P(GBM)",
      score: "Score",
      band: "Band",
    },
    loadingModel: "TRAINING_MODEL",
    generated: (when) => `Generated: ${when}`,
    datasetLine: (n, rate, train, test) =>
      `Dataset: ${n} applicants \u00b7 default rate ${rate}% \u00b7 ${train}/${test} stratified split`,
    applicants: (n) => `${n} applicants`,
    inferenceNote:
      "Client-side inference: sigmoid(\u03b2\u00b7x) with exported LR coefficients \u00b7 PDO=50, base=600, odds=50",
    // The number on its own says nothing. This is what turns it into something a
    // reader understands: which inputs are pushing it up, and which down.
    drivers: {
      title: "WHY THIS SCORE",
      caption:
        "Each bar is one input's contribution to this applicant's score, from the logistic regression coefficients",
      raises: "Raises the score",
      lowers: "Lowers the score",
    },
    explainer: {
      title: "WHAT DOES THIS MODEL DO?",
      problemLabel: "PROBLEM:",
      problem:
        "A bank receives 5,000 loan applications and has to decide which to approve without reviewing each one by hand. Who will pay, and who will default?",
      solutionLabel: "SOLUTION:",
      solution:
        "Two models learn the pattern of past defaulters — on-time payment history, credit utilisation, derogatory marks, income — and return a probability of default for each new applicant. That probability is converted into a FICO-style 300–850 score using the banking PDO formula: the higher the score, the more reliable the applicant.",
      tryItLabel: "HOW TO TRY IT:",
      tryIt:
        "In the interactive scorecard panel, move the sliders (income, on-time payments, utilisation) and watch the score and default probability change live. Inference runs in your browser, using logistic regression coefficients exported from scikit-learn.",
      detailsSummary: "▸ technical detail (ML pipeline)",
      pipelineTitle: "TECHNICAL_DETAIL (ML PIPELINE)",
      steps: [
        "1. Synthetic dataset calibrated to a ~17% default rate (12 numerical + 2 categorical features)",
        "2. Preprocessing: StandardScaler + OneHotEncoder · stratified 75/25 split",
        "3. Logistic Regression (interpretable) + Gradient Boosting calibrated via Platt sigmoid",
        "4. Validation: 5-fold StratifiedKFold (AUC, AvgPrecision, F1) + held-out test set",
        "5. PDO scorecard: factor = PDO / ln 2, offset = base − factor · ln(odds), clipped to 300–850",
        "6. Permutation importance, ROC, KS, Gini and Brier on the test set",
      ],
    },
  },

  // ── Recommender ──────────────────────────────────────────────────────────
  recommender: {
    title: "PRODUCT_RECOMMENDATION_ENGINE",
    loading: "LOADING_RECOMMENDATION_MODEL",
    error: "ERROR_LOADING_RECOMMENDATION_MODEL",
    personas: { title: "DEMO_PERSONAS" },
    similarity: { title: "SIMILARITY_RANKING", label: "Similarity" },
    similarityLabel: "similarity",
    catalog: (n) => `CATALOGUE (${n})`,
    recommendations: (n) => `RECOMMENDATIONS (top-${n})`,
    metrics: { title: "MODEL_METRICS" },
    reset: "Reset",
    load: "Load",
    clear: "Clear",
    loadingCatalog: "LOADING_CATALOGUE",
    subtitle: "Content-based · TF-IDF + category + price/rating · MMR re-ranking",
    stats: (products, categories, dim, coverage) =>
      `Catalogue: ${products} products · ${categories} categories · feature dim ${dim} · demo coverage ${coverage}%`,
    selectedCount: "Selected:",
    emptySelection: "select a product from the catalogue",
    explainCaption:
      "Click a recommendation to break down its similarity — which TF-IDF terms, plus the category and price/rating weights",
    personaItems: (n, diversity) => `${n} items · intra-list diversity ${diversity}`,
    explain: {
      title: "Why? (similarity breakdown)",
      tfidf: "TF-IDF",
      category: "Category",
      priceRating: "Price/Rating",
    },
    explainer: {
      title: "WHAT DOES THIS MODEL DO?",
      problemLabel: "PROBLEM:",
      problem:
        "An e-commerce catalogue of 32 products wants to suggest items similar to what each user already likes, without making them search.",
      solutionLabel: "SOLUTION:",
      solution:
        "Each product becomes a numeric vector — description via TF-IDF, category one-hot encoded, price and rating scaled. The user profile is the mean of the vectors of the products they picked. Recommendations are the products closest to that profile by cosine similarity, with an MMR re-rank that avoids returning six near-identical items.",
      tryItLabel: "HOW TO TRY IT:",
      tryIt:
        "Click products in the catalogue, or load one of the demo personas below. The list on the right recalculates instantly, in the browser. Toggle MMR diversity to see how varied the result becomes, move top_N, and click a recommendation to see why it was chosen — which TF-IDF terms, and how much weight came from category and price.",
      detailsSummary: "▸ technical detail (ML pipeline)",
      pipelineTitle: "TECHNICAL_DETAIL (ML PIPELINE)",
      steps: [
        "1. Per-item feature engineering: TF-IDF (1-2 grams, EN stop-words, max 120) + one-hot category · 0.6 + MinMax(price, rating) · 0.4",
        "2. User profile u = mean(v_i) over the selected items",
        "3. score(i) = cosine_similarity(u, v_i) for every unseen item",
        "4. MMR re-ranking (λ=0.7): argmax_i [λ·score(i) − (1−λ)·max sim(i, j) for j∈S]",
        "5. Client-side inference: the feature matrix is exported to JSON and all computation runs in JS",
      ],
    },
  },

  // ── FUTBOARD ─────────────────────────────────────────────────────────────
  // Moved in from a dictionary of its own once the whole site became bilingual.
  // Two independent language switches on one page was a worse answer than one.
  futboard: {
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
      resumeMatch: "A match is in progress",
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

  // ── Certifications ───────────────────────────────────────────────────────
  certifications: {
    title: "CERTIFICATIONS_DS",
    error: "ERROR_LOADING_CERTIFICATIONS",
    issued: "Issued",
    expires: "Expires",
    noExpiry: "No expiry",
    skills: "Skills",
    close: "Close",
  },
};

export default t;
