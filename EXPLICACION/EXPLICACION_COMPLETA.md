# Cómo funciona esta web, explicado de arriba abajo

> Reescrito el 2026-08-18. La versión anterior tenía 1.392 líneas y describía una
> arquitectura que ya no existe: hablaba de Azure OpenAI y Azure AI Search, que se
> borraron de la suscripción, y no mencionaba ni FUTBOARD ni Neon. Documentación
> que miente es peor que no tener ninguna, así que esta es corta y cierta.

## Qué es

Un portfolio con el que se puede hablar. Cinco cosas dentro de una sola web:

| Sección | Qué es |
|---|---|
| **chat_cv** | Un asistente que responde sobre mi carrera buscando en documentos reales |
| **visualizaciones** | La tabla de La Liga, actualizada sola cada 30 minutos |
| **modelos** | Tres modelos de machine learning que se ejecutan en tu propio navegador |
| **certificaciones** | Las certificaciones verificadas |
| **futboard** | Un marcador para los partidos de fútbol con mis amigos |

Todo en inglés y en español, con un selector en la cabecera.

## El mapa general

```
                 tu navegador
                      │
        ┌─────────────┴─────────────┐
        │                           │
   ficheros estáticos          preguntas del chat
   (HTML, JS, JSON)            y datos de FUTBOARD
        │                           │
        ▼                           ▼
┌──────────────────┐      ┌──────────────────────┐
│ Azure Static     │      │ Azure Container Apps │
│ Web Apps         │      │ FastAPI (Python)     │
│ React + Vite     │      │ 0,25 vCPU / 0,5 GiB  │
└──────────────────┘      └──────┬───────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
            OpenAI API     Google Gemini     Neon Postgres
            (redacta)      (embeddings)      (FUTBOARD)
```

**Frontend** es lo que ves; se ejecuta en tu navegador. **Backend** es el servidor
que piensa; se ejecuta en la nube. Hablan por una **API**, que es simplemente un
conjunto de direcciones a las que el frontend envía preguntas.

## El chat: por qué no se inventa cosas

Esto es lo que técnicamente se llama **RAG** (generación aumentada por
recuperación). La idea en una frase: en vez de pedirle a un modelo de lenguaje que
recuerde mi CV, le damos una herramienta de búsqueda y le obligamos a responder
solo con lo que encuentre.

El recorrido de una pregunta:

1. **`data/profile.yml`** es el único fichero que escribo a mano. Todo lo demás se
   genera de ahí: los documentos que se buscan, el vocabulario permitido y las
   certificaciones que ve la web.
2. `scripts/build_kb.py` lo convierte en **32 documentos**, uno por cada cosa real
   (un empleo, un proyecto, una carrera, una certificación).
3. `scripts/index_documents.py` convierte cada documento en un **vector**: una
   lista de números que representa su significado. Así se puede buscar por
   sentido y no solo por palabras exactas.
4. Cuando preguntas, el backend busca de **dos formas a la vez**: por significado
   (vectores) y por palabras literales (BM25), y combina ambas puntuaciones.
5. El modelo recibe **herramientas de búsqueda**, no un texto fijo. Decide qué
   buscar y puede volver a buscar si lo primero no le sirve.
6. Antes de devolver nada, un **comprobador de fundamento** revisa cada nombre
   propio de la respuesta contra el vocabulario permitido. Si aparece una
   tecnología que no está en mi perfil, la respuesta se regenera sin ella.

Ese último paso existe por un fallo real: la versión anterior llegó a atribuirme
experiencia con MongoDB, que no aparece en ninguna parte de mis documentos.

**Dato medido, no supuesto:** para combinar las dos búsquedas se probó primero
Reciprocal Rank Fusion y salió peor (13 de 18 preguntas reales frente a 18 de 18).
El motivo es que RRF tira la magnitud de la puntuación y solo mira el puesto, así
que una coincidencia de palabras floja podía desplazar a una coincidencia
semántica segura.

## Los tres modelos: se ejecutan en tu móvil

Ninguno de los tres llama al servidor. Se entrenan antes en Python, y sus
coeficientes se exportan a JSON; el cálculo ocurre en tu navegador. Por eso
responden al instante y no cuestan dinero por uso.

- **Predicción de La Liga** — proyecta cómo acaba la temporada con tres piezas: un
  ritmo de puntos, una simulación de Poisson repetida mil veces (Monte Carlo), y
  un clasificador XGBoost para las zonas. Con una sola jornada jugada no
  extrapola: contrae los números hacia la media, porque multiplicar un partido por
  38 no es un pronóstico.
- **Scoring de crédito** — una regresión logística que estima la probabilidad de
  impago y la convierte en un score de 300 a 850. El panel "por qué este score"
  muestra qué variable suma y cuál resta.
- **Recomendador** — compara productos por su descripción (TF-IDF) más categoría,
  precio y valoración, y reordena con MMR para no devolver seis cosas casi
  idénticas.

## La Liga: la parte que se mueve sola

Un workflow de GitHub Actions se ejecuta **cada 30 minutos**: descarga los datos,
los transforma con PySpark, recalcula las predicciones, **comprueba que el
resultado tiene sentido** antes de publicarlo, hace commit y vuelve a desplegar el
frontend.

Esa comprobación existe porque una vez publicó la tabla final de una temporada ya
terminada como si fuera la actual. El código no falló, simplemente acertó a estar
equivocado, y nada lo miraba.

## FUTBOARD

Un marcador para los partidos del domingo. Registras equipos y jugadores, eliges
dos equipos, y el móvil lleva el reloj con avisos sonoros para los cambios y para
el final de cada parte.

Tres decisiones que explican el resto:

- **El reloj sale de marcas de tiempo**, no de contar segundos. Un móvil congela
  los temporizadores cuando bloqueas la pantalla, así que un reloj que suma
  volvería atrasado del bolsillo. Este calcula "hora de ahora menos hora de
  inicio", y por eso siempre vuelve correcto.
- **Cada gol es una fila con goleador opcional.** El marcador del equipo se cuenta
  a partir de esas filas, así que es correcto se anote o no quién marcó. No hay
  dos números que puedan descuadrarse.
- **El partido vive en el navegador** mientras se juega y se guarda de una sola
  vez al final. Sobrevive a una recarga y no necesita cobertura hasta el pitido.

La base de datos es **Neon** (Postgres gratuito). Se duerme a los 5 minutos sin
uso, lo cual es correcto y **deliberadamente no se evita**: el plan da 100 horas de
cómputo al mes y mantenerla despierta costaría 182, así que se quedaría sin cuota
a mitad de mes. El precio es medio segundo de espera la primera vez, que la
interfaz dice en voz alta en vez de disimular.

## Estructura de carpetas

```
data/profile.yml          ← lo único que se edita a mano
data/kb/                  ← generado: los documentos que busca el asistente
backend/app/
  api/                    ← las direcciones de la API (chat, futboard)
  services/
    retrieval.py          ← la búsqueda combinada
    agent.py              ← el bucle que decide qué buscar
    grounding.py          ← el comprobador de invenciones
    futboard_store.py     ← el único sitio con SQL
frontend/src/
  i18n/                   ← los textos, en inglés y español
  components/             ← cada sección de la web
  lib/                    ← reloj, sonidos, clientes de API
scripts/                  ← generación, pipelines, despliegue
tests/                    ← 262 pruebas
```

## Trabajar en él

```bash
# Comprobar que el perfil es válido y regenerar lo que depende de él
python scripts/build_kb.py --check
python scripts/build_kb.py

# Levantar todo en local
docker compose up --build      # web en :3000, API en :8000

# Pruebas
python -m pytest
```

## Desplegar

```bash
git push origin main           # OBLIGATORIO antes de desplegar
source infra/aca/azure.env
./scripts/deploy_azure.sh
```

El `git push` no es una formalidad. El workflow de La Liga recompila el frontend
desde `origin/main` cada media hora, así que **un despliegue cuyos commits no
estén subidos se revierte solo en menos de 30 minutos**. Pasó el 2026-08-18: la
web volvió a una versión anterior sin que nada diera error. El script ahora se
niega a desplegar si detecta commits sin subir.
