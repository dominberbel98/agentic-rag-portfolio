# EXPLICACIÓN COMPLETA DEL PROYECTO — Para principiantes

## ¿QUÉ ES ESTE PROYECTO?

Es una **web personal / portfolio** de Domingo Berbel (Data Scientist) que tiene:

1. **Un chatbot con IA** — Le preguntas sobre Domingo y te responde usando RAG (busca en sus documentos reales y genera respuestas con un LLM).
2. **Visualizaciones de La Liga** — 6 gráficos interactivos con datos en tiempo real de la liga española de fútbol.
3. **Modelo predictivo** — Usa Machine Learning (XGBoost) y simulaciones Monte Carlo para predecir cómo acabará la liga.
4. **Galería de certificaciones** — Muestra los 6 certificados profesionales de Domingo.

La web está desplegada en **Azure** (nube de Microsoft) y se actualiza sola cada 30 minutos.

---

## ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────────┐
│                    USUARIO (navegador)                   │
│                  domingoberbel.com                       │
└─────────────────┬───────────────────┬───────────────────┘
                  │                   │
         Archivos estáticos      Preguntas al chat
         (HTML, JS, CSS,         (API REST)
          datos JSON)
                  │                   │
                  ▼                   ▼
┌─────────────────────┐  ┌───────────────────────────────┐
│  Azure Static Web   │  │  Azure Container Apps         │
│  Apps (FRONTEND)    │  │  (BACKEND)                    │
│                     │  │                               │
│  React + Vite       │  │  FastAPI (Python)             │
│  Tailwind CSS       │  │  ├─ RAG Service               │
│  Recharts           │  │  ├─ Embeddings cache          │
│  Nginx              │  │  ├─ OpenAI / Azure OpenAI     │
│                     │  │  ├─ Rate limiting              │
│  Puerto: 80/443     │  │  └─ Analytics (SQLite)        │
└─────────────────────┘  └───────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             OpenAI API      Google Gemini    SportsRC API
             (generar        (embeddings)     (datos fútbol)
              respuestas)
```

**¿Qué significa cada cosa?**

- **Frontend**: Lo que ve el usuario (la web). Se ejecuta en el navegador.
- **Backend**: El servidor que procesa las preguntas del chat. Se ejecuta en la nube.
- **API**: Una "puerta" por la que el frontend habla con el backend. El frontend manda una pregunta, el backend devuelve una respuesta.
- **Azure**: La nube de Microsoft donde está alojado todo.

---

## ESTRUCTURA DE CARPETAS

```
portfolio-chatbot/
│
├── backend/                  ← Servidor Python (FastAPI)
│   ├── Dockerfile            ← Receta para crear el contenedor
│   ├── requirements.txt      ← Librerías Python necesarias
│   ├── .env.example          ← Plantilla de variables secretas
│   └── app/
│       ├── config.py         ← Configuración (lee variables de entorno)
│       ├── main.py           ← Punto de entrada del servidor
│       ├── models.py         ← Modelos de datos (qué forma tiene una pregunta/respuesta)
│       ├── api/
│       │   └── chat.py       ← Endpoints: /chat, /chat/stream, /admin
│       └── services/
│           ├── rag_service.py        ← Cerebro del chatbot (RAG + LLM)
│           ├── embedding_service.py  ← Genera vectores con Google Gemini
│           ├── analytics_store.py    ← Guarda logs de preguntas
│           ├── captcha_service.py    ← Verifica que no eres un bot
│           └── guards.py            ← Límites de uso (rate limiting)
│
├── frontend/                 ← Web React (lo que ve el usuario)
│   ├── Dockerfile            ← Receta para crear el contenedor
│   ├── index.html            ← Página HTML base
│   ├── nginx.conf            ← Configuración del servidor web
│   ├── package.json          ← Librerías JavaScript necesarias
│   ├── vite.config.js        ← Configuración de Vite (empaquetador)
│   ├── tailwind.config.js    ← Configuración de colores/diseño
│   ├── postcss.config.js     ← Procesado de CSS
│   ├── .env.example          ← Plantilla de variables
│   ├── public/
│   │   ├── staticwebapp.config.json  ← Config de Azure Static Web Apps
│   │   ├── certs/            ← Imágenes de certificaciones (6 PNGs)
│   │   └── data/
│   │       ├── la_liga_data.json         ← Datos actuales de La Liga
│   │       └── la_liga_predictions.json  ← Predicciones del modelo ML
│   └── src/
│       ├── main.jsx          ← Punto de entrada de React
│       ├── App.jsx           ← Componente principal (layout + navegación)
│       ├── styles.css        ← Estilos globales (efectos CRT retro)
│       └── components/
│           ├── Chat.jsx              ← Interfaz del chatbot
│           ├── Visualizaciones.jsx   ← 6 gráficos de La Liga
│           ├── ModelosPredictivos.jsx ← 5 paneles de predicciones ML
│           └── Certificaciones.jsx   ← Galería de certificados
│
├── scripts/                  ← Scripts de automatización
│   ├── pipeline_laliga.py    ← ETL: descarga datos de La Liga con PySpark
│   ├── predict_laliga.py     ← Modelo predictivo: XGBoost + Monte Carlo
│   ├── index_documents.py    ← Indexa documentos del CV para el chatbot
│   ├── deploy_azure.sh       ← Despliega todo en Azure
│   ├── deployment_checklist.sh ← Checklist de despliegue
│   ├── setup_budget.sh       ← Configura límite de gasto en Azure
│   └── sync_preguntas.py     ← Descarga logs de preguntas del backend
│
├── infra/aca/                ← Configuración de infraestructura Azure
│   ├── azure.env.example     ← Plantilla con TODAS las variables necesarias
│   └── domain-setup.md       ← Guía para configurar dominio personalizado
│
├── .github/workflows/
│   └── update-laliga.yml     ← GitHub Actions: actualiza datos cada 30 min
│
├── DEPLOY_FINAL.sh           ← Script maestro de despliegue (un solo comando)
├── docker-compose.yml        ← Levantar todo en local con Docker
├── .gitignore                ← Archivos que Git debe ignorar
└── README.md                 ← Documentación general del proyecto
```

---

## EXPLICACIÓN ARCHIVO POR ARCHIVO

---

### `.gitignore` — Qué NO subir a GitHub

**¿Qué es?** Una lista de archivos que Git ignora al hacer commits. Evita subir secretos, archivos grandes o basura.

**¿Por qué existe?** Si subes un API key a GitHub, cualquiera puede verlo y usarlo (cobrándote dinero). Este archivo protege contra eso.

**Qué ignora:**
- `.env`, `azure.env` → Archivos con claves secretas (API keys, contraseñas)
- `embeddings_cache.json` → Archivo grande (>10MB) con vectores precalculados
- `node_modules/`, `.venv/` → Dependencias instaladas (se regeneran con `npm install` / `pip install`)
- `documentos/` → CV y cartas personales
- `preguntas.json` → Logs de preguntas (datos operacionales)

---

### `docker-compose.yml` — Levantar todo en local

**¿Qué es?** Un archivo que define cómo arrancar el backend y el frontend juntos en tu ordenador, usando Docker (contenedores).

**¿Qué es Docker?** Imagina una "caja" que contiene todo lo que necesita una aplicación para funcionar (código, librerías, sistema operativo). Esa caja funciona igual en cualquier ordenador.

```yaml
services:
  backend:                          # Servicio 1: el servidor Python
    build: ./backend                # Construir desde la carpeta backend/
    env_file: ./backend/.env        # Leer variables secretas de este archivo
    ports: ["8000:8000"]            # Exponer en el puerto 8000
    volumes:
      - ./embeddings_cache.json:/app/embeddings_cache.json:ro  # Montar cache (solo lectura)

  frontend:                         # Servicio 2: la web React
    build: ./frontend               # Construir desde la carpeta frontend/
    args:
      VITE_API_URL: http://localhost:8000  # Decirle dónde está el backend
    ports: ["3000:80"]              # Exponer en el puerto 3000
```

**¿Cómo se usa?** `docker-compose up` y ya tienes la web completa funcionando en `http://localhost:3000`.

---

### `DEPLOY_FINAL.sh` — Desplegar en producción

**¿Qué es?** Un script bash que hace TODO el despliegue en Azure desde cero. Es el "botón gordo" para poner la web online.

**Pasos que ejecuta:**
1. Login en Azure con MFA (autenticación multifactor)
2. Selecciona la suscripción de Azure
3. Ejecuta `deploy_azure.sh` (construye imágenes Docker, las sube, configura servidores)
4. Indexa documentos del CV (genera embeddings)
5. Configura presupuesto de 15 USD/mes
6. Muestra instrucciones para configurar DNS en Hostinger
7. Muestra comandos para vincular el dominio `domingoberbel.com`
8. Indica cómo verificar que HTTPS funciona

**¿Por qué no es automático al 100%?** Porque la configuración DNS (paso 6) hay que hacerla manualmente en el panel de Hostinger, y necesita hasta 24h para propagarse.

---

### `.github/workflows/update-laliga.yml` — Automatización cada 30 minutos

**¿Qué es?** Un workflow de **GitHub Actions** (CI/CD). Es código que se ejecuta automáticamente en los servidores de GitHub.

**¿Qué es CI/CD?** Continuous Integration / Continuous Deployment = automatizar tareas repetitivas. En vez de ejecutar scripts a mano, GitHub lo hace solo.

**¿Cuándo se ejecuta?**
- Cada 30 minutos (cron: `*/30 * * * *`)
- Manualmente desde GitHub (workflow_dispatch)

**¿Qué hace?**
1. Instala Python 3.11 + dependencias (PySpark, XGBoost, scikit-learn)
2. Ejecuta `pipeline_laliga.py` → Descarga datos actuales de La Liga
3. Ejecuta `predict_laliga.py` → Genera predicciones con ML
4. Si los datos cambiaron, hace commit y push automático
5. Instala Node.js 20, compila el frontend (`npm run build`)
6. Despliega en Azure Static Web Apps

**Resultado:** La web siempre muestra datos actualizados sin intervención humana.

---

## BACKEND — El servidor inteligente

---

### `backend/Dockerfile` — Receta del contenedor

**¿Qué hace?**
1. Parte de una imagen base de Python 3.11 (ligera, "slim")
2. Copia `requirements.txt` e instala las dependencias
3. Copia el código de la app y el cache de embeddings
4. **Crea un usuario sin privilegios** (`appuser`) — por seguridad, la app no se ejecuta como root
5. Expone el puerto 8000
6. Arranca el servidor con Uvicorn

**¿Qué es Uvicorn?** Un servidor ASGI (protocolo para apps Python asíncronas). Es el "motor" que hace que FastAPI pueda recibir peticiones HTTP.

---

### `backend/requirements.txt` — Dependencias Python

| Librería | Para qué sirve |
|----------|----------------|
| `fastapi` | Framework web para crear APIs REST rápidamente |
| `uvicorn` | Servidor que ejecuta FastAPI |
| `pydantic` | Validación de datos (asegura que las peticiones tienen el formato correcto) |
| `openai` | Cliente para hablar con ChatGPT / Azure OpenAI |
| `google-generativeai` | Cliente para generar embeddings con Google Gemini |
| `rank-bm25` | Búsqueda por palabras clave (complementa la búsqueda semántica) |
| `python-docx` | Leer archivos .docx (Word) para extraer texto del CV |
| `httpx` | Cliente HTTP asíncrono (para validar captchas) |
| `numpy` | Operaciones matemáticas con vectores (similitud coseno) |

---

### `backend/app/config.py` — Configuración centralizada

**¿Qué hace?** Define TODAS las variables configurables del backend en un solo sitio. Usa Pydantic `BaseSettings` que lee automáticamente de variables de entorno o de un archivo `.env`.

**¿Por qué?** Para no tener valores hardcodeados en el código. Si quieres cambiar el modelo de IA, cambias una variable de entorno, no el código.

**Variables principales:**
- `openai_api_key` / `azure_openai_api_key` → Claves de la IA
- `google_api_key` → Clave para generar embeddings
- `cors_origins` → Qué dominios pueden hacer peticiones al backend
- `max_requests_per_minute_per_ip` → Límite anti-abuso (20/min)
- `max_tokens_per_day` → Presupuesto diario de tokens (50.000)
- `turnstile_secret_key` → Clave del captcha

---

### `backend/app/main.py` — Punto de entrada del servidor

**¿Qué hace?** Crea la aplicación FastAPI y le añade:

1. **SecurityHeadersMiddleware** — Añade cabeceras de seguridad a TODAS las respuestas:
   - `X-Content-Type-Options: nosniff` → Evita que el navegador "adivine" el tipo de archivo
   - `X-Frame-Options: DENY` → Prohíbe que alguien meta tu web dentro de un iframe (evita clickjacking)
   - `Strict-Transport-Security` → Fuerza HTTPS siempre
   - `Permissions-Policy` → Desactiva acceso a micrófono, cámara, geolocalización

2. **CORSMiddleware** — Controla qué dominios pueden hacer peticiones:
   - En desarrollo: permite todo (`*`)
   - En producción: **prohíbe wildcard** (solo `domingoberbel.com`)

3. **Lifespan** — Al arrancar, carga el cache de embeddings en memoria (para que las búsquedas sean instantáneas).

4. **Endpoint `/health`** — Devuelve `{"status": "ok"}`. Lo usan los sistemas de monitoreo para saber si el servidor está vivo.

---

### `backend/app/models.py` — Modelos de datos

**¿Qué es un modelo de datos?** Define la "forma" que deben tener los datos. Si alguien manda una petición sin el campo `question`, Pydantic devuelve un error automáticamente.

**Modelos:**
- `ChatRequest` → Lo que el usuario manda: `{question: "¿A qué se dedica?", history: [...], captcha_token: "..."}`
- `ChatResponse` → Lo que el servidor responde: `{answer: "Domingo es...", citations: [...], needs_contact_form: false}`
- `HistoryMessage` → Un mensaje del historial: `{role: "user", content: "hola"}`
- `Citation` → Una referencia al documento fuente: `{source: "CV.docx", chunk: "texto relevante..."}`

---

### `backend/app/api/chat.py` — Los endpoints del chat

**¿Qué es un endpoint?** Una URL a la que puedes hacer peticiones. Como un "buzón" que acepta preguntas y devuelve respuestas.

**Endpoints:**

#### `POST /api/chat` — Chat normal (no streaming)
1. Verifica que no has excedido el límite de peticiones por minuto
2. Valida el captcha (si está configurado)
3. Comprueba que no se ha superado el presupuesto diario de tokens
4. Llama al RAG Service para obtener la respuesta
5. Guarda la pregunta en los logs
6. Devuelve la respuesta

#### `POST /api/chat/stream` — Chat con streaming (SSE)
Igual que el anterior, pero devuelve la respuesta **palabra por palabra** en tiempo real (como ChatGPT). Usa Server-Sent Events (SSE): el servidor va mandando trocitos de texto conforme el LLM los genera.

**¿Por qué streaming?** Porque esperar 5-10 segundos a que se genere toda la respuesta es mala experiencia de usuario. Con streaming, ves las palabras aparecer al instante.

#### `GET /api/admin/questions` — Panel de administración
Protegido con una clave secreta (`X-Admin-Key`). Devuelve las últimas 200 preguntas que ha recibido el chatbot. Útil para saber qué preguntan los visitantes.

---

### `backend/app/services/rag_service.py` — El cerebro del chatbot

Este es el archivo MÁS IMPORTANTE del backend (~1400 líneas). Implementa el sistema RAG completo.

**¿Qué es RAG? (Retrieval-Augmented Generation)**

```
Pregunta del usuario
        │
        ▼
┌─────────────────┐
│ 1. FILTRADO     │  ← ¿Es un saludo? ¿Es inapropiada? ¿Es off-topic?
│    PREVIO       │     Si sí → respuesta rápida sin gastar tokens
└────────┬────────┘
         │ (pregunta válida)
         ▼
┌─────────────────┐
│ 2. RETRIEVAL    │  ← Busca en los documentos del CV los trozos más relevantes
│    (Búsqueda)   │     Usa DOS métodos combinados:
│                 │     • Embeddings (similitud semántica) → entiende el SIGNIFICADO
│                 │     • BM25 (palabras clave) → busca coincidencias EXACTAS
└────────┬────────┘
         │ (chunks relevantes)
         ▼
┌─────────────────┐
│ 3. GENERATION   │  ← Manda los chunks + la pregunta a OpenAI/Azure OpenAI
│    (Generación) │     El LLM genera una respuesta basada en el contexto REAL
└────────┬────────┘
         │
         ▼
   Respuesta al usuario
```

**Sistema de filtrado previo (intent detection):**

Antes de usar el LLM (que cuesta dinero), el servicio comprueba:
- `_is_greeting_question()` → "hola", "hello" → respuesta hardcodeada
- `_is_contact_question()` → "¿cómo contacto?" → devuelve emails/LinkedIn
- `_is_inappropriate_question()` → contenido sexual/ofensivo → bloqueo
- `_is_generic_technical_help_question()` → "¿cómo instalo pip?" → rechaza (no es un tutor)
- `_is_clearly_offtopic_question()` → "¿quién descubrió América?" → rechaza

**Búsqueda híbrida (Retrieval):**

1. **Embeddings (búsqueda semántica)**:
   - Convierte la pregunta en un vector de 3072 dimensiones (usando Google Gemini)
   - Compara contra todos los chunks del CV (similitud coseno)
   - Entiende que "experiencia laboral" y "en qué ha trabajado" son lo mismo

2. **BM25 (búsqueda por palabras clave)**:
   - Busca coincidencias exactas de palabras
   - Complementa la búsqueda semántica (a veces el LLM falla con nombres propios)

3. **RRF (Reciprocal Rank Fusion)**:
   - Combina ambos rankings en uno solo
   - Fórmula: `score = 1/(K + rank_embedding) + 1/(K + rank_bm25)` con K=60

**Query augmentation:**
Para preguntas sobre temas específicos, el sistema añade palabras clave antes de buscar:
- Pregunta sobre empresa → añade "Data Equity Suministros Medina"
- Pregunta sobre idiomas → añade "bilingüe comunicación"
- Pregunta sobre educación → añade "máster grado matrícula honor"

**System prompt (instrucciones al LLM):**
Un prompt de ~2000 tokens que le dice al LLM:
- "Eres un asistente del perfil profesional de Domingo Berbel"
- "NO eres un asistente de propósito general"
- "Rechaza preguntas de tutoring, código, recetas, etc."
- "Sé persuasivo y profesional, como un elevator pitch"
- "Ajusta la longitud: simple=50-90 palabras, detallada=180-280"
- "Menciona siempre el portfolio chatbot como ejemplo de proyecto"

---

### `backend/app/services/embedding_service.py` — Generador de embeddings

**¿Qué es un embedding?** Un vector numérico (lista de 3072 números) que representa el SIGNIFICADO de un texto. Textos similares tienen vectores similares.

```
"Domingo trabaja como Data Scientist"  →  [0.23, -0.45, 0.12, ..., 0.87]  (3072 números)
"¿En qué trabaja Domingo?"            →  [0.21, -0.43, 0.15, ..., 0.85]  (muy parecido!)
"El gato sube al tejado"              →  [-0.67, 0.33, -0.91, ..., 0.02] (muy diferente)
```

Usa el modelo `gemini-embedding-001` de Google para generar estos vectores.

---

### `backend/app/services/analytics_store.py` — Logging de preguntas

**¿Qué hace?** Guarda TODAS las preguntas y respuestas del chatbot en dos sitios:

1. **SQLite** → Base de datos relacional (en `/tmp/rag_analytics.db`)
   - Tabla `question_logs`: fecha, IP del usuario, pregunta, vista previa de respuesta, si fue off-topic
   - Tabla `daily_usage`: tokens consumidos por día (para el presupuesto)

2. **JSON** → Archivo plano (`/tmp/rag_qa_logs.json`)
   - Máximo 50 MB o 5000 entradas (rotación automática)
   - Más fácil de descargar y analizar

**¿Por qué dos?** SQLite es rápido para consultas. JSON es cómodo para exportar.

---

### `backend/app/services/captcha_service.py` — Anti-bots

**¿Qué es un CAPTCHA?** Un sistema que verifica que el usuario es humano, no un programa automático.

Usa **Cloudflare Turnstile** (alternativa moderna a reCAPTCHA). El frontend muestra un widget invisible, el usuario interactúa, y el frontend obtiene un token que manda al backend. El backend valida el token contra la API de Cloudflare.

Si no está configurado (desarrollo), se desactiva automáticamente.

---

### `backend/app/services/guards.py` — Protección anti-abuso

**Rate limiting (por minuto):**
- Máximo 20 peticiones por minuto por IP
- Usa una ventana deslizante (guarda los timestamps de las últimas peticiones)
- Si te pasas: "Has hecho demasiadas preguntas. Prueba de nuevo en 1 minuto"

**Token budget (por día):**
- Máximo 50.000 tokens/día en total (para todos los usuarios)
- Cada respuesta del LLM consume tokens (aprox. 200-500 por pregunta)
- Si se agota: "Se ha alcanzado el límite diario. Intenta más tarde"

**¿Por qué?** Las APIs de OpenAI cuestan dinero por token. Sin límites, alguien podría hacer miles de consultas y generar una factura enorme.

---

## FRONTEND — Lo que ve el usuario

---

### `frontend/Dockerfile` — Construcción en dos fases

```
FASE 1: Builder (Node.js)          FASE 2: Runtime (Nginx)
┌─────────────────────┐           ┌─────────────────────┐
│ npm install          │           │ Solo nginx + HTML/JS │
│ npm run build        │──copy──▶ │ compilado            │
│ (compila React →     │  dist/   │                      │
│  HTML/JS estáticos)  │           │ Imagen final: ~25MB  │
└─────────────────────┘           └─────────────────────┘
   (imagen ~500MB,                   (imagen ligera,
    se descarta)                      solo lo necesario)
```

**¿Por qué dos fases?** Para que la imagen final sea pequeña. La fase de compilación necesita Node.js, npm, y miles de paquetes. Pero en producción solo necesitas los archivos estáticos (HTML, JS, CSS) y Nginx para servirlos.

---

### `frontend/index.html` — Página HTML base

Un HTML mínimo que:
1. Carga las fuentes (Space Grotesk, Inter, Material Symbols)
2. Define un `<div id="root">` vacío
3. Carga `src/main.jsx` como módulo

React se encarga de rellenar el `<div id="root">` con toda la interfaz.

---

### `frontend/nginx.conf` — Servidor web

**¿Qué es Nginx?** Un servidor web de alto rendimiento. Recibe peticiones HTTP y devuelve archivos (HTML, JS, imágenes).

**Configuración clave:**
- **SPA routing**: Cualquier URL que no sea un archivo real → devuelve `index.html` (React se encarga de la navegación)
- **Cache**: `index.html` nunca se cachea (siempre la última versión). Los assets (`/assets/*`) se cachean 1 año (tienen hash en el nombre, si cambian el hash cambia)
- **Seguridad**: Cabeceras CSP (Content Security Policy) que dicen al navegador qué puede cargar y qué no
- **Redirect**: `domingoberbel.com` → `www.domingoberbel.com`

---

### `frontend/package.json` — Dependencias JavaScript

| Librería | Para qué |
|----------|----------|
| `react` + `react-dom` | Framework UI — componentes, estado, renderizado |
| `recharts` | Gráficos (barras, radar, scatter, etc.) basados en React |
| `vite` | Empaquetador ultrarrápido (compila JSX → JS, optimiza todo) |
| `tailwindcss` | Framework CSS utility-first (clases como `bg-black text-green-400 p-4`) |
| `postcss` + `autoprefixer` | Procesado de CSS (compatibilidad entre navegadores) |

---

### `frontend/tailwind.config.js` — Diseño y colores

Define el tema visual de la web:
- **Colores Material Design 3**: Verde primario (#9cff93), naranja (#fcaf00), cian (#81ecff), rojo (#ff7351)
- **Fuentes**: Space Grotesk (títulos), Inter (texto)
- **Dark mode**: Activado por clase CSS (`.dark`)

---

### `frontend/vite.config.js` — Configuración de Vite

**¿Qué es Vite?** El empaquetador del frontend. Convierte JSX, Tailwind y módulos ES en archivos optimizados para producción.

Configuración mínima: servidor en `0.0.0.0:5173` (accesible desde contenedores Docker).

---

### `frontend/public/staticwebapp.config.json` — Azure Static Web Apps

Configura el comportamiento de Azure SWA:
- **Routing SPA**: Todas las rutas → `index.html`
- **Cabeceras de seguridad**: CSP, HSTS, X-Frame-Options
- **CSP `img-src`**: Permite imágenes de `sportsrc.org` (escudos de equipos)

---

### `frontend/src/main.jsx` — Punto de entrada React

```jsx
ReactDOM.createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

Monta el componente `<App />` dentro del `<div id="root">` del HTML.

---

### `frontend/src/styles.css` — Estilos globales y efectos CRT

Además de las directivas de Tailwind (`@tailwind base/components/utilities`), define:

- **Efecto CRT retro**: La web tiene aspecto de terminal/monitor antiguo
  - `.scanline-overlay` → Líneas horizontales semitransparentes
  - `.flicker` → Parpadeo sutil de pantalla (0.1s)
  - `.crt-glow` → Resplandor verde en el texto
  - `.cursor-blink` → Cursor parpadeante tipo terminal
  - Fondo con rejilla de puntos y fórmulas matemáticas semitransparentes

- **`.viz-panel`** → Contenedor de cada gráfico (borde, padding, línea degradada arriba)
- **`.viz-title`** → Título estilo terminal para cada visualización

---

### `frontend/src/App.jsx` — Componente principal

**¿Qué hace?** Es el "esqueleto" de la web. Define el layout y la navegación.

**Layout:**
```
┌──────────────────────────────────────────────────┐
│  HEADER: NEURAL_LINK_DS_V1.0  │  ☰ (mobile)     │
├──────────┬───────────────────────────────────────┤
│          │                                       │
│  SIDEBAR │        CONTENIDO PRINCIPAL            │
│  (nav)   │   (cambia según sección activa)       │
│          │                                       │
│  • Chat  │   ┌─────────────────────────────┐     │
│  • Viz   │   │  Chat / Visualizaciones /   │     │
│  • ML    │   │  Modelos / Certificaciones  │     │
│  • Certs │   └─────────────────────────────┘     │
│          │                                       │
├──────────┴───────────────────────────────────────┤
│  FOOTER: TRAINING_SET: 100%  │  OPTIMIZER: ADAM   │
└──────────────────────────────────────────────────┘
```

**Estado:** `activeSection` controla qué componente se muestra. Puede ser:
- `chat_cv` → `<Chat />`
- `visualizaciones` → `<Visualizaciones />`
- `modelos_predictivos` → `<ModelosPredictivos />`
- `certificaciones` → `<Certificaciones />`

**Mascota:** Un icono flotante en el lateral izquierdo (solo desktop) con un tooltip que dice: "Hola! Prueba el asistente de IA, o explora las visualizaciones de La Liga, el modelo predictivo, y mis certificaciones."

---

### `frontend/src/components/Chat.jsx` — Interfaz del chatbot

**¿Qué hace?** La interfaz de chat estilo terminal.

**Flujo de una conversación:**
1. Al cargar, manda un ping a `/health` (despierta al backend si estaba "dormido")
2. El usuario escribe una pregunta en el input
3. Se muestra un "boot log" simulado (efecto estético de terminal)
4. Se envía POST a `/api/chat/stream` con la pregunta + historial + token captcha
5. Se lee la respuesta por SSE (Server-Sent Events): van llegando tokens uno a uno
6. Los tokens se van mostrando en pantalla (efecto de escritura en tiempo real)
7. Si el backend dice `needs_contact_form: true`, se muestra un formulario de contacto

**Estética terminal:**
- Semáforo (●●●) rojo/amarillo/verde en la cabecera
- Indicador "KERNEL: IDLE / BUSY (PYTHON 3.11)"
- Prompt `>` antes de cada input del usuario
- Cursor parpadeante mientras se genera la respuesta

---

### `frontend/src/components/Visualizaciones.jsx` — 6 gráficos de La Liga

**Datos:** Lee `/data/la_liga_data.json` (actualizado cada 30 min).

**6 visualizaciones:**

#### 1. ClasificacionTable — Tabla de clasificación
Una tabla HTML con los 20 equipos: posición, escudo, nombre, partidos jugados, victorias, empates, derrotas, goles a favor, goles en contra, diferencia de goles, puntos. Cada fila coloreada por zona:
- 🟢 Verde = Champions League (1-4)
- 🔵 Azul = Europa League (5-6)
- ⚪ Gris = Zona media (7-17)
- 🔴 Rojo = Descenso (18-20)

#### 2. PointsDistribution — Distribución de puntos
Gráfico de barras horizontales. Cada barra = un equipo, longitud = puntos acumulados. Coloreado por zona.

#### 3. AttackVsDefense — Ataque vs Defensa
Gráfico de dispersión (scatter). Eje X = goles a favor, Eje Y = goles en contra. Tamaño de la burbuja = puntos del equipo. Los buenos equipos están arriba-derecha (muchos GF, pocos GA).

#### 4. GoalDiffSpectrum — Espectro de diferencia de goles
Barras divergentes. Cada barra sale del 0 hacia la derecha (diferencia positiva, verde) o izquierda (diferencia negativa, rojo). Muy visual para ver quién mete más de lo que encaja.

#### 5. WinRateMatrix — Matriz de Victoria/Empate/Derrota
Barras apiladas al 100%. Cada barra se divide en % de victorias (verde), empates (amarillo), derrotas (rojo). Permite comparar el "estilo" de cada equipo.

#### 6. Top5Radar — Radar de los 5 mejores
Gráfico de radar con 5 ejes (victorias, empates, derrotas, goles a favor, goles en contra) para los top 5 equipos. Valores normalizados (0-100) para que sean comparables, pero el tooltip muestra valores reales.

---

### `frontend/src/components/ModelosPredictivos.jsx` — Predicciones ML

**Datos:** Lee `/data/la_liga_predictions.json` (generado por `predict_laliga.py`).

**5 paneles:**

#### 1. ChampionProb — Probabilidad de ser campeón
Barras horizontales con el % de probabilidad de ganar la liga (sale de las 1000 simulaciones Monte Carlo).

#### 2. ProjectedPoints — Puntos proyectados con intervalo de confianza
Barras con "bigotes" (error bars) que muestran el percentil 10 y 90. Es decir, "con un 80% de probabilidad, este equipo acabará entre X e Y puntos".

#### 3. GoalProbabilities — Probabilidades de goles
3 mini-gráficos de barras, separados por líneas verticales:
- **Más goleador**: ¿Quién tiene más probabilidad de ser el equipo que más goles mete?
- **Más goleado**: ¿Quién tiene más probabilidad de ser el que más goles encaja?
- **Menos goleado**: ¿Quién tiene más probabilidad de encajar menos goles?

#### 4. FeatureImportance — Importancia de características
Barras horizontales mostrando qué features usó XGBoost y cuánto peso les dio. Permite ver si "puntos por partido" es más predictivo que "goles a favor por partido", etc.

#### 5. ProjectedTable — Tabla de clasificación proyectada
Tabla completa con: posición actual, equipo, puntos actuales, puntos proyectados (media), intervalo de confianza (P10, P90), y la zona que XGBoost predice.

**Sección de metodología:** Explica los 4 pasos del modelo (Feature Engineering, Simulación Poisson, Monte Carlo, XGBoost).

---

### `frontend/src/components/Certificaciones.jsx` — Galería de certificados

**¿Qué hace?** Muestra las 6 certificaciones profesionales en una cuadrícula responsive.

**Certificados:**
1. Snowflake SnowPro Associate
2. Databricks Fundamentals
3. Databricks Generative AI Fundamentals
4. Kaggle Advanced SQL
5. IBM Data Analysis Using Python
6. LinkedIn Power BI Avanzado

**Funcionalidades:**
- Grid: 1 columna (móvil), 2 columnas (tablet), 3 columnas (desktop)
- Hover: La imagen se agranda ligeramente
- Click: Se abre un lightbox (modal a pantalla completa) con la imagen grande
- Cada certificado muestra: nombre, plataforma, fecha, y tags de habilidades

---

## SCRIPTS — Automatización y procesamiento de datos

---

### `scripts/pipeline_laliga.py` — ETL de datos de La Liga

**¿Qué es un ETL?** Extract-Transform-Load. Extraer datos de una fuente → transformarlos → cargarlos en un destino.

**Flujo:**

```
API SportsRC                    PySpark                      JSON
(internet)                    (transformación)             (archivo)
    │                              │                          │
    ▼                              ▼                          ▼
fetch_standings()  ──────▶  DataFrame con schema  ──────▶  la_liga_data.json
fetch_matches()              explícito (StructType)        (20 equipos con
fetch_scores()               + zone classification          stats completas)
                             + win/draw/loss rates
```

**¿Qué es PySpark?** La versión Python de Apache Spark, un motor de procesamiento de datos masivos. Aquí se usa para transformar los datos de forma declarativa (como SQL pero en Python).

**¿Por qué PySpark si son solo 20 equipos?** Por demostración de habilidades profesionales. En un entorno real de Data Science, PySpark se usa para millones de registros. Aquí demuestra que Domingo sabe usarlo.

**Schema explícito:** Se define la estructura exacta de los datos con `StructType` en vez de dejar que Spark la "adivine". Esto evita errores cuando algún campo viene como `null` (por ejemplo, el campo `form` de la API a veces viene vacío).

**Clasificación por zonas:**
```python
# Si posición 1-4 → Champions, 5-6 → Europa, 18-20 → Descenso, resto → Media
F.when(col("position") <= 4, "champions")
 .when(col("position") <= 6, "europa")
 .when(col("position") >= 18, "relegation")
 .otherwise("mid")
```

**API usada:** SportsRC (`https://api.sportsrc.org/`). Es gratuita y devuelve datos de La Liga en JSON.

---

### `scripts/predict_laliga.py` — Modelo predictivo (XGBoost + Monte Carlo)

Este es uno de los archivos más interesantes del proyecto. Implementa un modelo de Machine Learning que predice cómo acabará la liga.

#### PASO 1: Feature Engineering

**¿Qué es Feature Engineering?** Crear variables nuevas a partir de las existentes para que el modelo tenga mejor información.

A partir de los datos crudos (partidos jugados, victorias, goles...), se calculan **ratios por partido**:

| Feature | Fórmula | ¿Qué mide? |
|---------|---------|-------------|
| `ppg` | puntos / partidos_jugados | Puntos Por Partido — rendimiento general |
| `winRate` | victorias / partidos_jugados | % de victorias |
| `drawRate` | empates / partidos_jugados | % de empates |
| `lossRate` | derrotas / partidos_jugados | % de derrotas |
| `gfPerGame` | goles_a_favor / partidos_jugados | Poder ofensivo por partido |
| `gaPerGame` | goles_en_contra / partidos_jugados | Debilidad defensiva por partido |
| `gdPerGame` | diferencia_goles / partidos_jugados | Balance neto por partido |

**¿Por qué ratios y no valores absolutos?** Porque si un equipo ha jugado 30 partidos y otro 28, comparar "goles totales" es injusto. Los ratios normalizan.

#### PASO 2: Simulación de Poisson

**¿Qué es la distribución de Poisson?** Una distribución de probabilidad que modela "cuántas veces ocurre algo en un intervalo". Es perfecta para goles en fútbol porque:
- Los goles son eventos discretos (0, 1, 2, 3...)
- Son relativamente raros (media de ~1.3 por equipo por partido)
- Son "independientes" (simplificación, pero funciona)

**¿Cómo funciona?**

Para cada partido que queda por jugar:
1. Se calcula λ_gf (lambda goles a favor) = goles a favor por partido del equipo local
2. Se calcula λ_ga (lambda goles en contra) = goles en contra por partido del equipo visitante
3. Se genera un número aleatorio: `goles_local ~ Poisson(λ_gf)`
4. Se genera otro: `goles_visitante ~ Poisson(λ_ga)`
5. Se determina el resultado: victoria local (3 puntos), empate (1 punto), derrota (0 puntos)

**Ejemplo:** Si el Barça mete 2.5 goles/partido de media y el rival encaja 1.8:
- La simulación puede dar: 3-1 (victoria), 0-2 (derrota), 2-2 (empate)...
- Cada simulación es diferente (aleatoria), pero sigue la tendencia estadística

#### PASO 3: Monte Carlo (1000 temporadas simuladas)

**¿Qué es Monte Carlo?** Repetir una simulación aleatoria muchas veces para obtener una distribución de resultados posibles.

```
Simulación 1:  Barça 91 pts, Madrid 87, Atleti 75 ...
Simulación 2:  Barça 94 pts, Madrid 90, Atleti 78 ...
Simulación 3:  Madrid 89 pts, Barça 88, Atleti 80 ...
...
Simulación 1000: Barça 92 pts, Madrid 88, Atleti 76 ...
```

Con 1000 simulaciones puedes calcular:
- **Media de puntos**: E[puntos] = media de las 1000 simulaciones
- **Desviación estándar**: ¿cuánta variedad hay? (equipo estable vs impredecible)
- **Percentil 10 (P10)**: En el peor 10% de los escenarios, ¿cuántos puntos saca?
- **Percentil 90 (P90)**: En el mejor 10%, ¿cuántos?
- **Probabilidad de campeón**: En cuántas de las 1000 simulaciones acabó primero
- **Probabilidad de máximo goleador**: En cuántas fue el que más goles metió

**¿Por qué 1000?** Es un balance entre:
- Precisión (más simulaciones = resultados más estables)
- Velocidad (en GitHub Actions, tiene que terminar en minutos)
- 1000 es suficiente para que las probabilidades converjan

#### PASO 4: XGBoost (clasificador de zonas)

**¿Qué es XGBoost?** Un algoritmo de Machine Learning basado en árboles de decisión potenciados (boosted trees). Es uno de los más usados en competiciones de Data Science.

**¿Qué hace aquí?** Clasifica cada equipo en una zona:
- Champions (1-4)
- Europa League (5-6)
- Zona media (7-17)
- Descenso (18-20)

**Configuración:**
```python
XGBClassifier(
    n_estimators=50,      # 50 árboles de decisión
    max_depth=3,          # Cada árbol tiene máximo 3 niveles (simple, evita overfitting)
    objective='multi:softprob'  # Devuelve PROBABILIDADES por clase, no solo la predicción
)
```

**¿Qué es `multi:softprob`?** En vez de decir "este equipo es Champions", dice "este equipo tiene 85% probabilidad Champions, 10% Europa, 4% media, 1% descenso". Mucho más útil.

**Features de entrada:**
```
[ppg, winRate, drawRate, lossRate, gfPerGame, gaPerGame, gdPerGame]
```

**Feature Importance:** XGBoost te dice qué features fueron más útiles para la predicción. Típicamente `ppg` (puntos por partido) es la más importante.

**¿Por qué XGBoost Y Monte Carlo?** Son complementarios:
- **Monte Carlo** → "¿Cuántos puntos sacará?" (distribución numérica)
- **XGBoost** → "¿En qué zona acabará?" (clasificación categórica)

---

### `scripts/credit_scoring_pipeline.py` — Modelo de Credit Scoring (banca)

Este script entrena un modelo bancario de **credit scoring** (decidir si un cliente que pide un préstamo va a pagar o entrar en mora) y exporta sus resultados a un JSON que el frontend renderiza en la sección **`modelo_scoring`**.

#### ¿Qué problema resuelve?

Un banco recibe miles de solicitudes de préstamo. No puede revisar cada una a mano. Necesita un modelo automático que, dadas las características del solicitante (ingresos, historial de pagos, utilización de crédito, etc.), devuelva una probabilidad de impago y un **score 300–850** estilo FICO.

#### PASO 1: Generación de dataset sintético

Como no podemos publicar datos reales de clientes, generamos **5 000 solicitantes ficticios** con distribuciones realistas:

| Feature | Distribución | ¿Qué representa? |
|---------|--------------|-------------------|
| `age` | uniforme(21, 70) | Edad |
| `annual_income` | log-normal(μ=10.8, σ=0.6) | Ingresos anuales (€) |
| `employment_years` | exponencial(escala=6) | Años en empleo actual |
| `loan_amount` | log-normal(μ=9.5, σ=0.7) | Importe del préstamo |
| `payment_history_pct` | beta(8, 2) · 100 | % pagos a tiempo |
| `credit_utilization` | beta(2, 4) · 100 | % de utilización de crédito |
| `credit_age_years` | exponencial(escala=7) | Antigüedad del historial |
| `num_credit_accounts` | poisson(λ=4) | Nº de cuentas de crédito |
| `recent_inquiries` | poisson(λ=2) | Consultas recientes |
| `derogatory_marks` | poisson(λ=0.3) | Marcas negativas (impagos pasados) |
| `debt_to_income` | derivada | Cuota mensual / ingreso mensual |
| `loan_to_income` | derivada | Préstamo / ingreso anual |
| `loan_purpose` | categórica | personal, auto, mortgage, education, business |
| `home_ownership` | categórica | rent, own, mortgage |

La etiqueta `default` (1 = impago, 0 = paga) se construye con un **modelo log-odds calibrado** para que la tasa de default sea realista (~17%):

```python
log_odds = -3.0 - 0.04·payment_history_pct + 0.025·credit_utilization
         + 0.18·recent_inquiries + 0.55·derogatory_marks + 1.20·debt_to_income
         - 0.07·credit_age_years - 0.03·employment_years - ...
prob_default = 1 / (1 + exp(-log_odds))
default = 1 si rand() < prob_default
```

#### PASO 2: Preprocesado (sklearn `ColumnTransformer`)

```
NUMERICAL_FEATURES ──▶ StandardScaler   (centrar y escalar)
CATEGORICAL_FEATURES ──▶ OneHotEncoder  (texto → columnas binarias)
```

**¿Qué es StandardScaler?** Resta la media y divide por la desviación estándar de cada feature numérica → todas en la misma escala (media 0, std 1). Necesario para que la regresión logística no dé más peso a "ingresos" (50 000) que a "% utilización" (30) solo por el rango.

**¿Qué es OneHotEncoder?** Convierte una variable categórica con N niveles en N columnas binarias. Ej.: `home_ownership = "own"` → `[1, 0, 0]` para `[own, rent, mortgage]`.

**Split estratificado 75/25:** se separa un 25% del dataset que el modelo NO ve durante entrenamiento (held-out test set). La estratificación mantiene la misma proporción de defaults en ambas particiones.

#### PASO 3: Dos modelos en paralelo

##### a) Logistic Regression — modelo INTERPRETABLE

Es la regresión clásica para clasificación binaria. Output:

$$P(\text{default}|x) = \sigma(\beta_0 + \beta_1 x_1 + \beta_2 x_2 + ... + \beta_n x_n)$$

donde σ es la función sigmoide. Su gran ventaja: cada coeficiente β tiene significado directo. Si β para `derogatory_marks` es +0.4, significa que **cada marca negativa adicional multiplica las odds de default por e^0.4 ≈ 1.5**.

**Por qué la usamos para la inferencia interactiva del navegador:** los coeficientes son una lista pequeña de números. Los exportamos al JSON y el navegador puede ejecutar la predicción sin servidor.

```python
LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced", solver="lbfgs")
```

- **`C=0.5`**: regularización L2 (penaliza coeficientes grandes para evitar overfitting). Inversa de λ: a menor C, más regularización.
- **`class_weight="balanced"`**: como la clase minoritaria (default) es ~17%, sklearn pondera más sus errores para que no la ignore.

##### b) Gradient Boosting Classifier — modelo PRECISO

Conjunto de árboles de decisión que se entrenan en serie: cada árbol corrige los errores del anterior. Más potente que la regresión logística porque captura **interacciones no lineales** entre features.

```python
GradientBoostingClassifier(n_estimators=300, learning_rate=0.04, max_depth=4, subsample=0.8, min_samples_leaf=20)
```

- **`n_estimators=300`**: 300 árboles encadenados.
- **`learning_rate=0.04`**: cuánto contribuye cada árbol nuevo. Bajo = más estable pero requiere más árboles.
- **`max_depth=4`**: profundidad máxima de cada árbol (evita memorizar).
- **`subsample=0.8`**: cada árbol se entrena con un 80% aleatorio de los datos (stochastic gradient boosting).

**Calibración con sigmoid (Platt scaling):** los gradient boosters tienden a devolver probabilidades extremas (cerca de 0 o 1). Para que `P(default)=0.7` realmente signifique "70% de los casos con esa puntuación impagaron", se ajusta una sigmoide encima del output. Lo hace `CalibratedClassifierCV(method="sigmoid", cv=3)`.

#### PASO 4: Métricas — qué significa cada una

##### Validación cruzada estratificada (5-fold)

Se parte el train set en 5 trozos. El modelo se entrena 5 veces, cada una dejando un trozo fuera para evaluar. Las métricas finales son la media ± desviación. Garantiza que las métricas no dependen de un split afortunado.

##### Métricas en el held-out test set

| Métrica | Definición | ¿Qué significa? | Buena en credit scoring |
|---------|------------|------------------|--------------------------|
| **AUC-ROC** | Área bajo la curva ROC | Probabilidad de que un default cualquiera tenga score más alto que un no-default cualquiera. 0.5 = aleatorio, 1.0 = perfecto | > 0.70 |
| **GINI** | 2·AUC − 1 | Equivalente a AUC pero en escala 0–1. La banca europea reporta GINI más que AUC | > 0.40 |
| **KS** (Kolmogorov-Smirnov) | max(TPR − FPR) | Máxima separación entre la distribución de scores de buenos vs malos. Métrica reina en credit scoring | > 0.30 |
| **Average Precision** | Área bajo la curva Precision-Recall | Útil cuando hay desbalance de clases (pocos defaults) | -- |
| **F1 Score** | 2·P·R/(P+R) | Media armónica de precisión y recall (al threshold 0.5) | > 0.40 |
| **Brier Score** | Media de (p − y)² | Mide calidad de calibración (qué tan bien las probabilidades reflejan la realidad). Menor = mejor | < 0.20 |

##### Curva ROC

Cada punto de la curva es un threshold distinto. Eje X = FPR (% no-defaults clasificados como default = falsos rechazos). Eje Y = TPR (% defaults detectados). La diagonal es el clasificador aleatorio.

##### Permutation Feature Importance

Para cada feature, se mezcla aleatoriamente sus valores y se mide cuánto cae el AUC. Cuanto más cae → más importante era esa feature. Es **model-agnostic** (sirve para LR, GBM, redes neuronales…).

#### PASO 5: Scorecard PDO 300–850

PDO = "Points to Double the Odds". Es la fórmula estándar de la industria:

```
factor = PDO / ln(2)
offset = base_score − factor · ln(base_odds)
score  = offset + factor · ln((1 − p) / p)
score  = clip(score, 300, 850)
```

Con PDO=50, base_score=600, base_odds=50: cada vez que las odds de pagar se duplican, el score sube 50 puntos. Si tu probabilidad de default es 0.5 (50/50), te dan ~458; si es 0.02 (1 entre 50 impaga), te dan ~706.

Los rangos comerciales (FICO):

| Score | Banda | Riesgo |
|-------|-------|--------|
| <580 | Poor | Muy alto |
| 580-669 | Fair | Alto |
| 670-739 | Good | Moderado |
| 740-799 | Very Good | Bajo |
| 800-850 | Exceptional | Muy bajo |

#### PASO 6: Inferencia en el navegador (client-side)

Esta es la parte poco habitual. En lugar de servir el modelo desde un endpoint, **se exportan los coeficientes** de la regresión logística y el navegador ejecuta la predicción:

```js
// frontend/src/components/ModelosScoring.jsx
function predictWithLR(weights, applicant) {
  let z = weights.intercept;
  for (const f of weights.numerical) {
    z += ((applicant[f.feature] - f.mean) / f.std) * f.coef;
  }
  for (const c of weights.categorical) {
    if (applicant[c.feature] === c.level) z += c.coef;
  }
  return 1 / (1 + Math.exp(-z));   // sigmoide
}
```

El JSON exportado contiene: `intercept`, `coefs[]`, `mean[]`, `std[]` (para reaplicar el StandardScaler), y la lista de niveles del OHE. El usuario mueve sliders → se reconstruye el vector → dot-product + sigmoide → score. Sin red, sin servidor, latencia 0.

#### Pipeline de datos resumido

```
[ Local / GitHub Actions ]
         │
         ▼
generate_credit_dataset(n=5000)        ← seed=42 (determinista)
         │
         ▼
   train_test_split(75/25, stratified)
         │
         ├─▶ Logistic Regression  ──▶ exporta coefs (browser-friendly)
         └─▶ Gradient Boosting   ──▶ Calibración sigmoid
                                      ROC, KS, AUC, importance
         │
         ▼
   credit_scoring.json   (20 KB, en frontend/public/data/)
         │
         ▼
   npm run build
         │
         ▼
   Azure Static Web Apps  ──▶ domingoberbel.com
```

**¿Dónde se ejecuta?** El script Python se ejecuta una sola vez (en local o como parte del build) porque el dataset es sintético y determinista. No hay re-entrenamiento periódico — el JSON se commitea al repo. **No usa el backend ni la base de datos.** Toda la inferencia sucede en el navegador del visitante.

---

### `scripts/recommendation_engine.py` — Recomendador de productos (Content-Based + MMR)

Este script entrena un sistema de recomendación content-based y exporta el catálogo + la matriz de features para que el frontend de **`modelo_recomendation`** ejecute la inferencia en el navegador.

#### ¿Qué problema resuelve?

Un e-commerce con 32 productos quiere sugerir productos similares a los que le interesan a un usuario, sin obligarle a buscar. Mejora conversión (más clicks → más ventas) y descubrimiento (productos de la cola larga que el usuario nunca habría buscado).

#### ¿Qué tipos de recomendadores existen?

| Tipo | Cómo funciona | Pros | Contras |
|------|----------------|------|---------|
| **Content-Based** (este) | Usa atributos del ítem (descripción, categoría, precio) para encontrar similares | Funciona desde el día 1 (no necesita histórico de usuarios). No tiene "cold-start" para ítems nuevos | No descubre gustos sorpresa |
| **Collaborative Filtering** | "Usuarios parecidos a ti compraron X" | Encuentra patrones latentes | Necesita muchos usuarios e histórico |
| **Hybrid** | Combina ambos | Mejor cobertura | Más complejo |

Aquí elegimos content-based porque es el adecuado para una demo sin usuarios reales.

#### PASO 1: Catálogo (32 productos en 4 categorías)

```python
CATALOG = [
    {"id": 1, "name": "Pro Laptop 15\"", "category": "electronics",
     "price": 1299, "rating": 4.7,
     "description": "high performance laptop professional productivity portable computing developer workstation"},
    ...
]
```

Cada producto tiene: id, nombre, categoría, precio, rating y una **descripción rica en tags** (palabras clave que describen al producto desde múltiples ángulos: uso, público, atributo).

#### PASO 2: Feature engineering — convertir cada producto en un vector

Tres bloques de features se concatenan en un único vector:

##### a) TF-IDF (sobre la descripción)

**TF-IDF = Term Frequency × Inverse Document Frequency.** Es el clásico para representar texto como números.

- **TF** (term frequency): cuántas veces aparece un término en el documento.
- **IDF** (inverse document frequency): logaritmo del inverso de en cuántos documentos aparece. Términos comunes (`the`, `and`) → IDF bajo. Términos raros y discriminativos (`bluetooth`, `lidar`) → IDF alto.
- **TF-IDF = TF · IDF.** Premia palabras frecuentes en este documento pero raras en el corpus general.

Configuración:

```python
TfidfVectorizer(max_features=120, ngram_range=(1, 2), stop_words="english")
```

- **`max_features=120`**: solo conserva los 120 términos más informativos del vocabulario. Mantiene el JSON pequeño.
- **`ngram_range=(1, 2)`**: indexa palabras sueltas (`laptop`) y bigramas (`noise canceling`). Captura frases.
- **`stop_words="english"`**: filtra `the`, `a`, `is`, etc.

Resultado: cada producto pasa a ser un vector de 120 dimensiones, mayoritariamente ceros (sparse) excepto en los términos que contiene.

##### b) One-Hot de categoría

`category` se convierte en un vector binario de 4 dimensiones (`[electronics, books, sports, home]`). Multiplicado por **0.6** para que la categoría tenga peso significativo pero no aplaste al TF-IDF.

##### c) MinMax-scaled price + rating

`MinMaxScaler` lleva precio y rating a [0, 1]. Multiplicado por **0.4** para que dos productos con precios similares se parezcan, pero sin dominar la similitud.

```
Vector final por producto = [120 dims TF-IDF | 4 dims OHE×0.6 | 2 dims num×0.4]
                          = 126 dimensiones
```

#### PASO 3: Perfil del usuario y similitud

El "perfil del usuario" es la **media de los vectores de los productos que ha seleccionado**:

```
u = (1/|S|) · Σ v_i  para i ∈ S
```

Esto representa al usuario como un punto en el mismo espacio que los productos. La similitud entre el perfil y cada producto candidato se calcula con **cosine similarity**:

$$\cos(\theta) = \frac{u \cdot v}{\|u\| \cdot \|v\|}$$

Devuelve un valor entre -1 y 1. Cuanto más cerca de 1, más parecido. Se prefiere a la distancia euclidiana porque es **invariante a la magnitud del vector** (un producto con descripción larga no se penaliza).

#### PASO 4: top_N — cuántas recomendaciones devolver

`top_N` es simplemente el **número de items que devolvemos al usuario**, ordenados por similaridad descendente. En el frontend hay un slider entre 3 y 10 para que el usuario lo cambie en vivo.

#### PASO 5: MMR — re-ranking para diversidad (Maximal Marginal Relevance)

El problema con el ranking puro por similaridad es que las top-6 recomendaciones suelen ser **casi idénticas**. Si seleccionas un libro de Python, te recomienda 6 libros de Python parecidos. Es redundante.

**MMR** equilibra relevancia y diversidad:

$$\text{MMR}(i) = \lambda \cdot \text{sim}(u, i) - (1 - \lambda) \cdot \max_{j \in S} \text{sim}(i, j)$$

donde:
- `sim(u, i)` = similaridad del item al perfil del usuario (relevancia)
- `max_{j ∈ S} sim(i, j)` = similaridad del item al item más parecido ya seleccionado (redundancia)
- `λ` = peso entre los dos términos (aquí 0.7: 70% relevancia, 30% diversidad)

El algoritmo es greedy: empieza con el más relevante y, en cada paso, elige el item que maximiza MMR (alta relevancia + poca redundancia con lo ya elegido). Resultado: lista variada.

#### PASO 6: Métricas de evaluación

Como no hay usuarios reales, evaluamos con **personas sintéticas** (Tech Enthusiast, Data Scientist, Fitness Fan, Home Professional). Cada una tiene un historial fijo y se mide:

| Métrica | Fórmula | Qué mide |
|---------|---------|----------|
| **Intra-list diversity** | 1 − media(cosine entre pares de la lista) | Cuán variada es una lista de recomendaciones (1 = todas distintas, 0 = todas iguales) |
| **Catalog coverage** | items únicos recomendados / tamaño catálogo | Qué % del catálogo aparece al menos una vez |

#### PASO 7: Inferencia client-side

Se exporta:
- `catalog`: lista de productos con metadata
- `featureMatrix`: 32×126 (la matriz completa)
- `tfidfVocab`: 120 términos del vocabulario (para explicabilidad)
- `personas`: resultados pre-computados como demo

El navegador implementa cosine similarity, `meanVec`, MMR en JS puro:

```js
function cosine(a, b) { return dot(a, b) / (norm(a) * norm(b)); }
function meanVec(matrix, indices) { /* media columna a columna */ }
function mmr(candidates, matrix, k, lambda) { /* greedy */ }
```

**Explicabilidad ("¿por qué este producto?"):** al hacer click en una recomendación, se descomponen los productos punto a punto:

```
contribución_total = Σ profile[i] · item[i]
contribución_tfidf = Σ sobre dims 0..119 (palabras clave que coinciden)
contribución_categoría = Σ sobre dims 120..123 (mismo segmento)
contribución_num = Σ sobre dims 124..125 (precio/rating similares)
```

Y se muestran los 5 términos TF-IDF que más contribuyen (los más "responsables" de la recomendación).

#### Pipeline resumido

```
[ Local / GitHub Actions ]
         │
         ▼
   CATALOG (32 productos hardcodeados)
         │
         ▼
   TfidfVectorizer + OneHotEncoder + MinMaxScaler
         │
         ▼
   feature_matrix [32 × 126]
         │
         ▼
   product_recommendations.json   (66 KB, en frontend/public/data/)
         │
         ▼
   npm run build → Azure Static Web Apps
         │
         ▼
   Browser: cosine + MMR sobre la matriz exportada
```

**Diferencias con el scoring:**
- El scoring exporta **coeficientes** (un modelo aprendido). El recomendador exporta la **matriz de features** (los datos crudos transformados); el "modelo" es la operación de cosine similarity, que es trivial de reimplementar en JS.
- Ambos comparten el mismo principio de portfolio: **cero coste de servidor por inferencia, latencia inmediata**, y todo se mantiene en versión bajo control.

---

### `scripts/index_documents.py` — Indexación de documentos del CV

**¿Qué hace?** Prepara los documentos del CV para que el chatbot pueda buscar en ellos.

**Flujo:**
1. Lee todos los `.docx` de la carpeta `documentos/` (CV, carta de motivación, etc.)
2. Extrae el texto de cada documento
3. **Chunking**: Divide el texto en trozos de 650 caracteres con 100 de solapamiento
4. **Embedding**: Para cada trozo, genera un vector de 3072 dimensiones con Google Gemini
5. Guarda todo en `embeddings_cache.json`

**¿Qué es chunking?** Dividir un documento largo en trozos pequeños. El LLM tiene un límite de contexto (no puedes mandarle 50 páginas de golpe). Con chunks, buscas solo los trozos relevantes.

**¿Qué es el solapamiento (overlap)?** Los últimos 100 caracteres de un chunk se repiten al principio del siguiente. Esto evita que una frase se corte a la mitad y pierda significado.

---

### `scripts/deploy_azure.sh` — Script de despliegue en Azure

**¿Qué hace?** Automatiza TODO el proceso de despliegue en la nube de Azure:

1. Valida que existan las variables de entorno necesarias
2. Registra los proveedores de Azure necesarios
3. Construye la imagen Docker del backend y la sube a GitHub Container Registry (GHCR)
4. Compila el frontend con Vite
5. Configura Azure Container Apps (backend) con la imagen, variables de entorno, réplicas
6. Crea Azure Static Web App (frontend) y despliega
7. Configura dominios personalizados

---

### `scripts/setup_budget.sh` — Límite de gasto Azure

Crea un presupuesto mensual de **15 USD** en Azure con alertas por email. Si el gasto se acerca al límite, envía emails de aviso.

**¿Por qué?** Azure cobra por uso. Sin un límite, un bug o un ataque podrían generar una factura inesperada.

---

### `scripts/sync_preguntas.py` — Sincronización de logs

Descarga las preguntas que los visitantes han hecho al chatbot (desde el endpoint admin del backend) y las guarda en un archivo JSON local. Útil para análisis offline.

---

### `scripts/deployment_checklist.sh` — Checklist de despliegue

Un script que imprime una lista de tareas pendientes para completar el despliegue. Es una guía paso a paso.

---

## INFRAESTRUCTURA

---

### `infra/aca/azure.env.example` — Plantilla de variables

Contiene TODAS las variables necesarias para desplegar en Azure, pero con valores de ejemplo (placeholders). Hay que copiar este archivo a `azure.env` y rellenar los valores reales.

**Secciones:**
- Datos de Azure (subscription, resource group, location)
- Registro de contenedores (GHCR)
- Container Apps (backend)
- Static Web App (frontend)
- Dominios
- Credenciales: OpenAI, Azure OpenAI, Google, Turnstile
- Límites: rate limiting, token budget

---

### `infra/aca/domain-setup.md` — Guía DNS

Instrucciones paso a paso para:
1. Obtener los FQDN generados por Azure
2. Crear registros CNAME en tu proveedor DNS
3. Obtener tokens de verificación
4. Vincular dominios en Azure
5. Esperar a que Azure emita certificados SSL automáticos

---

## GLOSARIO — Términos técnicos explicados

| Término | Explicación simple |
|---------|-------------------|
| **API** | "Puerta" para que programas hablen entre sí. El frontend manda una pregunta al backend a través de una API |
| **RAG** | Retrieval-Augmented Generation. Buscar info relevante en documentos y dársela al LLM para que responda. Es decir: antes de que la IA responda, buscamos la información relevante |
| **LLM** | Large Language Model. El modelo de IA que genera texto (GPT-4, etc.) |
| **Embedding** | Vector numérico que representa el significado de un texto |
| **Token** | "Trozo" de texto (~4 caracteres). Los LLMs cuentan y cobran por tokens |
| **SSE** | Server-Sent Events. Técnica para enviar datos del servidor al navegador en tiempo real |
| **Docker** | Sistema de contenedores. Empaqueta una app con todo lo que necesita para funcionar igual en cualquier sitio |
| **PySpark** | Versión Python de Apache Spark. Motor para procesar grandes volúmenes de datos |
| **XGBoost** | Algoritmo de ML basado en árboles de decisión potenciados. Muy potente para clasificación/regresión |
| **Monte Carlo** | Técnica de simulación: ejecutar algo aleatorio miles de veces para obtener probabilidades |
| **Poisson** | Distribución de probabilidad para eventos discretos y raros (perfecta para goles) |
| **CI/CD** | Continuous Integration/Deployment. Automatizar testing, compilación y despliegue |
| **CORS** | Cross-Origin Resource Sharing. Regla que controla qué webs pueden acceder a tu API |
| **CSP** | Content Security Policy. Regla que dice al navegador qué recursos puede cargar |
| **HSTS** | HTTP Strict Transport Security. Fuerza HTTPS siempre |
| **BM25** | Algoritmo clásico de búsqueda por palabras clave |
| **RRF** | Reciprocal Rank Fusion. Método para combinar dos rankings en uno |
| **SPA** | Single Page Application. Web que carga una sola vez y navega sin recargar la página |
| **Uvicorn** | Servidor ASGI para aplicaciones Python asíncronas |
| **FastAPI** | Framework Python para crear APIs web rápidas y con documentación automática |
| **React** | Librería JavaScript para construir interfaces de usuario con componentes |
| **Recharts** | Librería de gráficos para React, basada en D3.js |
| **Tailwind CSS** | Framework CSS basado en clases de utilidad (en vez de escribir CSS, usas clases predefinidas) |
| **Vite** | Empaquetador moderno para frontend (compila JSX, optimiza código) |
| **Nginx** | Servidor web de alto rendimiento |
| **GHCR** | GitHub Container Registry. Almacén de imágenes Docker en GitHub |
| **Azure SWA** | Azure Static Web Apps. Servicio para hospedar webs estáticas (HTML/JS/CSS) gratis |
| **Azure Container Apps** | Servicio para ejecutar contenedores Docker en la nube |
| **TF-IDF** | Term Frequency × Inverse Document Frequency. Convierte texto en vectores premiando palabras frecuentes en un documento pero raras en el corpus general |
| **n-gram** | Secuencia de n palabras consecutivas. Unigrama = una palabra, bigrama = dos palabras seguidas |
| **Cosine similarity** | Mide el ángulo entre dos vectores. Va de −1 a 1; 1 = idénticos. Insensible a la magnitud, perfecta para comparar textos |
| **OneHotEncoder** | Convierte una variable categórica con N valores en N columnas binarias. Necesario porque los modelos lineales no entienden texto |
| **StandardScaler** | Centra (resta media) y escala (divide por std) cada feature numérica. Pone todas a la misma escala |
| **MinMaxScaler** | Reescala cada feature al rango [0, 1] |
| **Logistic Regression** | Regresión clásica para clasificación binaria. Output = sigmoide de combinación lineal de features. Modelo interpretable: cada coeficiente tiene un significado directo |
| **Gradient Boosting** | Conjunto de árboles entrenados en serie, cada uno corrigiendo el error del anterior. Captura no-linealidades. XGBoost, LightGBM, sklearn.GBM son implementaciones |
| **Calibration (Platt scaling)** | Ajusta una sigmoide encima de un clasificador para que sus probabilidades reflejen la realidad (P=0.7 → realmente 70% de positivos) |
| **AUC-ROC** | Área bajo la curva ROC. Probabilidad de que un positivo cualquiera tenga score más alto que un negativo cualquiera. 0.5 = aleatorio, 1.0 = perfecto |
| **GINI** | 2·AUC − 1. Misma información que AUC pero en escala 0-1. Métrica estándar en banca europea |
| **KS** (Kolmogorov-Smirnov) | Máxima separación vertical entre la curva acumulada de positivos y la de negativos. Métrica reina en credit scoring |
| **Brier Score** | Media de (probabilidad − etiqueta_real)². Mide calidad de calibración. Menor = mejor |
| **PDO** | Points to Double the Odds. Fórmula estándar para mapear P(default) a un score 300-850 estilo FICO |
| **Permutation Importance** | Medida model-agnostic de importancia de features: mezcla aleatoriamente una feature y mide cuánto cae el AUC |
| **Stratified K-Fold** | Validación cruzada que mantiene la proporción de clases en cada fold. Imprescindible con clases desbalanceadas |
| **Held-out test set** | Trozo de datos que el modelo NUNCA ve durante entrenamiento. Sirve para estimar rendimiento en producción sin sesgo |
| **Content-based recommender** | Recomienda items por sus atributos. Funciona desde el día 1 sin necesitar histórico de usuarios |
| **Collaborative filtering** | Recomienda según patrones de "usuarios similares". Necesita histórico amplio |
| **MMR** | Maximal Marginal Relevance. Re-ranking que equilibra relevancia y diversidad para evitar listas redundantes. Fórmula: λ·rel − (1-λ)·max_redundancia |
| **top_N** | Número de items a devolver en una recomendación, ordenados por similaridad descendente |
| **Cold start** | Problema cuando no hay datos de un usuario (o item) nuevo. El content-based no lo sufre para items |
| **Intra-list diversity** | 1 − media de similitud entre pares de items recomendados. Mide cuán variada es una lista |
| **Catalog coverage** | % del catálogo que aparece al menos una vez en alguna recomendación |
| **Client-side inference** | Ejecutar el modelo en el navegador (JS) en vez de en un servidor. Cero latencia de red, cero coste de cómputo en backend |

---

## FLUJO COMPLETO: ¿Qué pasa cuando visitas la web?

```
1. Escribes domingoberbel.com en el navegador
        │
2. DNS resuelve → Azure Static Web Apps
        │
3. Nginx sirve index.html + JS/CSS compilados
        │
4. React se carga en tu navegador
   ├─ App.jsx monta el layout
   ├─ Chat.jsx hace ping a /health (despierta el backend)
   └─ Visualizaciones/Modelos cargan datos JSON estáticos
        │
5. Escribes una pregunta en el chat
        │
6. Chat.jsx → POST /api/chat/stream → api.domingoberbel.com
        │
7. Azure Container Apps recibe la petición
   ├─ guards.py: ¿rate limit OK? ¿token budget OK?
   ├─ captcha_service.py: ¿captcha válido?
   └─ chat.py: todo OK → llama al RAG Service
        │
8. rag_service.py:
   ├─ ¿Es saludo/contacto/inapropiada? → respuesta rápida
   └─ Si es pregunta válida:
       ├─ Genera embedding de la pregunta (Google Gemini)
       ├─ Busca chunks similares (coseno + BM25 + RRF)
       ├─ Construye prompt: system + contexto + pregunta
       └─ Llama a OpenAI/Azure OpenAI → genera respuesta
        │
9. La respuesta se envía por SSE (token a token)
        │
10. Chat.jsx muestra los tokens conforme llegan
        │
11. analytics_store.py guarda la pregunta en SQLite + JSON
```

---

## FLUJO COMPLETO: ¿Qué pasa cada 30 minutos? (GitHub Actions)

```
1. Cron trigger: */30 * * * *
        │
2. GitHub Actions runner (Ubuntu)
   ├─ Instala Python 3.11 + dependencias
   │
3. pipeline_laliga.py:
   ├─ Fetch API SportsRC → standings 20 equipos
   ├─ PySpark transforma: zonas, rates, stats
   └─ Guarda → la_liga_data.json
        │
4. predict_laliga.py:
   ├─ Feature engineering (7 ratios por equipo)
   ├─ Monte Carlo: 1000 temporadas simuladas (Poisson)
   ├─ XGBoost: clasifica zonas con probabilidades
   └─ Guarda → la_liga_predictions.json
        │
5. Git commit + push (si hay cambios)
        │
6. npm ci + npm run build (compila frontend con datos nuevos)
        │
7. Deploy → Azure Static Web Apps
        │
8. Web actualizada con datos frescos
```
