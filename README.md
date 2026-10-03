# Pabrikers

<a id="top"></a>

**Pabrikers** is a smart-factory workflow optimizer. You draw your factory (stations, machines, workers) on an interactive canvas, and Pabrikers turns it into a **digital twin**. It then **simulates a full work shift** and trains a **reinforcement learning (Maskable PPO)** agent. The agent picks the best actions for each worker and station: **fire / hire / move / stay / automate**. Pabrikers then shows the optimized twin next to before/after **KPI cards**. An **AI chatbot** explains what changed and why.

<details>
<summary><strong>Table of Contents</strong></summary>

- [How It Works](#how-it-works)
- [Optimization Scenarios](#optimization-scenarios)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Run with Docker (full stack)](#run-with-docker-full-stack)
- [Run Locally (development)](#run-locally-development)
- [Using the App](#using-the-app)
- [RL Training from the CLI](#rl-training-from-the-cli)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Known Limitations](#known-limitations)
- [License](#license)

</details>

---

## How It Works

1. **Intro** (`/intro`): pick a factory template or start empty.
2. **Live canvas** (`/live`): add process stations, machines and workers, and connect the flow. The canvas can auto-fill station attributes with the LLM and import worker CVs as a `.zip`.
3. **Build** (`/parser`): the backend persists the factory and computes the worker × job compatibility matrix in the background.
4. **Digital Twin** (`/digital-twin?factoryId=…`): shows assets, workers, job desks and the compatibility matrix.
5. **Simulate**: click **"Mulai Simulasi"** to run one shift in the browser (fatigue, stress, errors, breaks, WIP and bottlenecks). Speeds are 1x/2x/5x/10x.
6. **Optimize**: when the shift ends, the simulation result is sent to the backend automatically. The backend trains the RL agent in the background, and the header button shows `Melatih RL… N%`.
7. **Recommendations** (`/project/:id/recommendations`): the three RL scenarios, with the recommended one highlighted.
8. **Analytics report** (`/project/:id/recommendation/:scenarioId`): before/after KPI cards (throughput, human error rate, operating cost, cost per item), worker moves, automation and hires, an animated optimized flow, and station status.
9. **AI chatbot**: ask about any scenario. The full chat history is sent as context.

```mermaid
flowchart LR
    A[Canvas UI] -->|POST /factories<br/>PUT /factories/id/simulation<br/>/documents/step-4, step-5| B[(PostgreSQL<br/>digital twin)]
    B -->|GET /factories/id/simulation-config| C[Browser shift simulation]
    C -->|POST /rl-optimization/id/optimize<br/>end state + last working snapshot| D[Maskable PPO training<br/>background job]
    B --> D
    D -->|optimal_state.json| E[GET /rl-optimization/id/scenarios]
    E --> F[Recommendations & KPI report]
    F -->|POST /agents/chat + history| G[LLM chatbot agents]
    B --> G
```

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Optimization Scenarios

Each training run produces three scenarios with different constraints (`backend/app/optimization/train_ppo.py`, `SCENARIO_LIBRARY`):

| Scenario | Title | Move | Fire / standby | Hire | Automate | Capex budget |
|---|---|---|---|---|---|---|
| `scenario_01` | Realokasi SDM Murni (reallocate staff only) | ✓ | ✗ | ✗ | ✗ | Rp 0 |
| `scenario_02` | Substitusi Otomasi (automation) | ✓ | ✓ | ✗ | ✓ | Rp 70,000,000 |
| `scenario_03` | Full Optimization | ✓ | ✓ | ✓ (2 slots) | ✓ | Rp 120,000,000 |

- **Actions per step:**
  - Move a worker to a station.
  - Send a worker on a break.
  - Send a worker to standby (fire/mutate).
  - Automate a station or hire into a station.
  - A worker the policy never moves is reported as **stay**.
- **"Before" KPIs** come from a do-nothing rollout of the same environment: everyone stays, with no hires or automation. "Before" and "after" therefore share the same dynamics and units.
- The browser simulation's end state seeds each worker's fatigue, stress, error probability and speed.
- The design and math are documented in [`project.md`](project.md).

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, React Router 7, TanStack Query 5, Zustand 5, @xyflow/react 12 (canvas), Axios, Zod |
| Backend | Python 3.11+, FastAPI 0.115, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, PostgreSQL 16 |
| Reinforcement learning | Gymnasium 1.0, Stable-Baselines3 2.4.1, sb3-contrib 2.4.0 (Maskable PPO), PyTorch 2.14 (CPU is enough) |
| LLM | vLLM (OpenAI-compatible API) serving Llama-3.1-8B-Instruct (NVFP4); BGE-M3 embeddings; YAML agent definitions in `backend/app/agent/configs` |
| Infrastructure | Docker Compose, nginx (serves the SPA and proxies `/api`), pgAdmin |

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Project Structure

```
.
├── backend/            FastAPI app (API, digital twin, simulation config, RL, chatbot)  → backend/README.md
├── frontend/           React SPA (canvas, digital twin, simulation, RL report, chat)    → frontend/README.md
├── deployment/         Dockerfiles, compose files per service, nginx config, helper scripts
├── training/           GNN compatibility training scripts, datasets and checkpoint
├── tests/              pytest suites + Streamlit harness for the document pipeline
├── docker-compose.yaml Full stack: LLM, embedding, backend, postgres, pgadmin, frontend
├── requirements.txt    Python dependencies used by the root Docker build
└── project.md          RL / digital-twin design document
```

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Prerequisites

| Purpose | Requirement |
|---|---|
| Full stack (Docker) | Docker Engine + Docker Compose v2 |
| LLM services | NVIDIA GPU with the NVIDIA Container Toolkit. Model weights must already be in `./models` (vLLM runs with `HF_HUB_OFFLINE=1`): `models--nvidia--Llama-3.1-8B-Instruct-NVFP4` and `models--BAAI--bge-m3` |
| Local development | Python 3.11+, Node.js 20+, PostgreSQL 16 |

The LLM is only needed for AI features: node auto-fill, CV parsing, the compatibility matrix and chatbot answers. Simulation and RL run without it.

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Configuration

Create a `.env` file in the repository root. **Never commit it**; `.env` is already in `.gitignore`.

```env
# Database (docker-compose)
POSTGRES_USER=pabrikers
POSTGRES_PASSWORD=change-me
POSTGRES_DB=pabrikers

# Security & model access
SECRET_KEY=change-me-to-a-long-random-string
HF_TOKEN=hf_xxx

# pgAdmin
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change-me
```

Backend settings are read from environment variables (`backend/app/core/config.py`, `backend/app/core/agent_config.py`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/pabrikers` | Async SQLAlchemy DSN |
| `CORS_ALLOW_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed origins; add `http://localhost:5173` for Vite dev |
| `LLM_BRIDGE_URL` | `http://localhost:15000/v1` | vLLM chat endpoint |
| `LLM_SERVED_MODEL_NAME` | `LLM` | Served model name |
| `EMBEDDING_BRIDGE_URL` | `http://localhost:15001/v1` | Embedding endpoint |
| `RL_TOTAL_TIMESTEPS` | `20000` | PPO timesteps per scenario for on-demand training (~3 min total on 2 CPU threads) |
| `RL_MAX_TIMESTEPS` | `200000` | Upper bound for a per-request `total_timesteps` |
| `RL_N_ENVS` | `1` | Vectorized environments per scenario |
| `RL_TORCH_THREADS` | `2` | CPU threads used by PyTorch during training |
| `RL_OUTPUT_DIR` | `backend/outputs/rl` | Where RL inputs, models and results are stored |
| `AGENT_CHAT_TIMEOUT_SECONDS` | `60` | Chatbot LLM timeout |
| `AGENT_CHAT_HISTORY_TURNS` | `10` | Chat messages sent to the LLM as context |

Frontend settings are in `frontend/.env` (copy `frontend/.env.example`):

| Variable | Example | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend root (the client appends `/v1`). Defaults to `/api`, which matches the nginx proxy |
| `VITE_API_VERSION` | `v1` | API version segment |

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Run with Docker (full stack)

```bash
# 1. One-time: the compose file uses an external network
docker network create compfest-net

# 2. Create .env (see Configuration) and make sure ./models holds the model weights

# 3. Build and start everything
docker compose up -d --build

# Logs
docker compose logs -f backend
```

| Service | URL |
|---|---|
| Frontend (nginx, proxies `/api` to the backend) | http://localhost:3000 |
| Backend API + Swagger UI | http://localhost:8000/docs |
| PostgreSQL | `localhost:5433` |
| pgAdmin | http://localhost:5050 |
| LLM (vLLM) | http://localhost:15000/v1 |
| Embedding (vLLM) | http://localhost:15001/v1 |

The first start of the LLM container can take a long time (its health-check start period is 30 minutes). To run services separately, use the helper scripts from the repository root:

```bash
./deployment/scripts/manage-llm.sh up        # up | down | restart | build | logs | ps
./deployment/scripts/manage-backend.sh up
./deployment/scripts/manage-frontend.sh up
```

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Run Locally (development)

**1. Database**

```bash
createdb pabrikers            # or: psql -c "CREATE DATABASE pabrikers;"
```

**2. Backend**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/pabrikers"
export CORS_ALLOW_ORIGINS='["http://localhost:5173"]'
uvicorn app.main:app --reload --port 8000
```

- Tables are created automatically on startup.
- Run **one** uvicorn worker process. RL training jobs and compatibility-matrix jobs are tracked in memory.

**3. Frontend**

```bash
cd frontend
npm ci
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8000/api
npm run dev                   # http://localhost:5173
```

**4. LLM (optional)**

Point `LLM_BRIDGE_URL` and `EMBEDDING_BRIDGE_URL` at any running vLLM servers, or start only those containers with `./deployment/scripts/manage-llm.sh up`. Without them:
- The chatbot falls back to local replies.
- LLM-based steps on the canvas (auto-fill, CV parsing, compatibility matrix) are unavailable.

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Using the App

1. Open the app and click through to **Intro** to pick a template, then design the factory on **Live**.
2. Generate the factory from the canvas. You are taken to **`/parser`**, which polls the build and compatibility job, and then to the **Digital Twin** page.
3. On **Live Simulation**, choose a speed (`10x` runs a 9-hour shift in about a minute) and click **"Mulai Simulasi"**.
4. When the clock shows **SHIFT SELESAI**, RL training starts automatically, and the header button shows **`Melatih RL… N%`**.
   - You can also start training without a simulation by clicking **"Optimisasi Reinforcement Learning"**. Training then uses the design data only.
   - If training fails, the button changes to **"Coba Lagi Optimisasi RL"**.
5. Click **"Lihat Hasil Optimisasi RL"** to open the three scenarios, then open one for the full KPI report.
6. Ask the **AI Chatbot** panel questions such as "Kenapa skenario ini direkomendasikan?". Your earlier messages are sent along as context.

RL artifacts for each factory are written to `backend/outputs/rl/<factory_id>/`:

```
inputs/              factory_md.json, worker_md.json, init_state.json, simulation_state.json, simulation_summary.json
training/            scenario_0N/policy.zip, scenario_0N/vecnormalize.pkl
optimal_state.json   the scenario bundle served to the UI
status.json          latest job status
```

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## RL Training from the CLI

For a longer, higher-quality run, reuse the inputs that the API already wrote for a factory:

```bash
cd backend
python -m app.optimization.train_ppo --factory-id <factory_id> --timesteps 200000 --sequential
```

| Flag | Description |
|---|---|
| `--factory-id` | Reads `outputs/rl/<id>/inputs/` and writes `outputs/rl/<id>/optimal_state.json` |
| `--input-dir` | Custom directory with `factory_md.json`, `worker_md.json`, `init_state.json` (and optional `simulation_state.json`) |
| `--output` | Custom output path for the scenario bundle |
| `--timesteps` | PPO timesteps per scenario (default 2,000,000 on the CLI) |
| `--n-envs` | Vectorized environments |
| `--seed` | Random seed |
| `--sequential` | Train scenarios one after another instead of in parallel processes |

The UI picks up the new `optimal_state.json` on its next request.

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## API Reference

All routes are prefixed with `/api/v1`. Interactive docs are available at `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/factories` | Create a factory |
| `GET` | `/factories/{factory_id}` | Factory summary and build status |
| `PUT` | `/factories/{factory_id}/simulation` | Save the canvas design (assets, stages, shifts, job desks, stations) |
| `GET` | `/factories/{factory_id}/digital-twin` | Full digital twin |
| `GET` | `/factories/{factory_id}/simulation-config` | Configuration for the browser simulation |
| `POST` | `/documents/step-4` | Upload worker CVs (`.zip`) |
| `POST` / `GET` | `/documents/step-5/jobs`, `/documents/step-5/jobs/{job_id}` | Compatibility-matrix background job |
| `POST` | `/agents/node-autofill` | LLM auto-fill of a canvas node |
| `POST` | `/rl-optimization/{factory_id}/optimize` | Start RL training (body: `end_state`, `working_state`, optional `total_timesteps`) |
| `GET` | `/rl-optimization/{factory_id}/optimize/status` | Training status and progress |
| `GET` | `/rl-optimization/{factory_id}/scenarios` | The three trained scenarios |
| `POST` | `/agents/chat` | Chatbot (body: `message`, `factory_id`, `scenario_id`, `history`) |
| `GET` | `/health`, `/health/agents` | Health checks |

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Testing

```bash
# Backend unit tests (RL input mapping, chatbot endpoint)
pip install -r backend/requirements.txt
python -m pytest tests/optimization tests/api_chat

# Frontend type check, lint and production build
cd frontend
npm run lint
npm run build
```

`tests/services/factory_md_init_test.py` is a Streamlit harness for the document and LLM pipeline. It needs the LLM server; run it with `streamlit run tests/services/factory_md_init_test.py`. Sample CVs and factory documents are in `tests/services/test_files/`.

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## Known Limitations

- **Single worker process:** background jobs (RL training, compatibility matrix) live in memory, so run the backend with one uvicorn worker.
- **No real login:** authentication is not implemented, and `ProtectedRoute` lets every user through.
- **Short training budget:** the on-demand budget is small for responsiveness. Use the CLI for stronger policies.
- **LLM needed for AI features:** without vLLM, chat answers fall back to local templates.
- **Display quirks:** the throughput chart on the report page uses a fixed y-axis scale, and fatigue in the RL environment tends to saturate over a full shift.

<div align="right"><a href="#top">Back to top ⬆</a></div>

---

## License

Released under the [MIT License](LICENSE).
