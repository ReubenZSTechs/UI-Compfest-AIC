# Pabrikers Backend

The FastAPI service behind Pabrikers. It stores the factory **digital twin** in PostgreSQL and builds the **simulation configuration** the browser runs. It also maps a finished simulation onto **RL inputs** and trains **Maskable PPO** scenarios in the background. Finally, it answers **chatbot** questions through LLM agents served by vLLM.

See the [root README](../README.md) for the full setup, Docker usage and configuration.

## Run

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/pabrikers"
export CORS_ALLOW_ORIGINS='["http://localhost:5173"]'
uvicorn app.main:app --reload --port 8000     # Swagger UI: http://localhost:8000/docs
```

- Tables are created on startup (`app/db/create_all.py`).
- Run a **single** worker process, because RL training and compatibility-matrix jobs are tracked in memory.

## Layout

```
app/
├── main.py                     App factory, lifespan (create tables, sweep stale jobs, agent registry, stop RL jobs)
├── api/
│   ├── deps.py                 get_db and other dependencies
│   └── v1/
│       ├── router.py           Mounts every endpoint module under /api/v1
│       └── endpoints/
│           ├── factories.py              Factory CRUD, digital twin, simulation design & config
│           ├── digital_twin_ingestion.py Read-only twin views (assets, workers, job desks, compatibility)
│           ├── simulation.py             Simulation design save / overview
│           ├── document_parser.py        Document pipeline steps 3–5, CV upload, compatibility jobs
│           ├── node_autofill.py          LLM auto-fill for a canvas node
│           ├── rl_optimization.py        Start RL training, poll status, fetch scenarios
│           └── agent_chat.py             Chatbot routed to the scenario explainer / twin analyst / general agent
├── modules/                    Domain logic: models.py, schemas.py, service.py, repository.py per domain
│   ├── digital_twin_ingestion/ Canonical twin tables (factories, assets, stages, shifts, job desks, workers, evaluations)
│   ├── simulation/             Stations and settings; builds the SimulationConfig consumed by the frontend engine
│   ├── documents/              Document parse and compatibility-matrix jobs, persistence of parsed factories
│   └── rl_optimization/        RL twin view (service.py) and in-process training jobs (training_jobs.py)
├── optimization/
│   ├── factory_env.py          Gymnasium environment: assignment + capital actions, human-factors dynamics, action masks
│   ├── reward_function.py      Step/terminal rewards and Pareto front
│   ├── train_ppo.py            Maskable PPO training for the three scenarios, baseline calibration, export, CLI
│   ├── snapshot_from_db.py     Maps the DB twin + browser simulation state onto SnapshotBuilder inputs
│   └── scenario_store.py       Paths and atomic JSON I/O for RL artifacts
├── services/
│   ├── call_llm_service.py     OpenAI-compatible Agent client (plain and structured output)
│   ├── agent_registry_service.py  Loads agents from agent/configs by role
│   ├── snapshot_builder.py     Builds the numeric EnvSnapshot used by the RL environment
│   ├── node_autofill_service.py
│   └── …                       Document pipeline helpers (CV parsing, workbook extraction, worker profiles, GNN compatibility)
├── agent/
│   ├── configs/                One YAML per LLM agent role (system prompt, generation settings)
│   └── schemas/                JSON schemas for structured agent output
├── worker/tasks.py             In-process runner for the compatibility-matrix job
├── core/                       Settings, logging, middleware, exceptions, LLM call logging
└── db/                         Engine/session, declarative base, create_all
```

## Main endpoints

All routes are prefixed with `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `POST` / `GET` | `/factories` | Create / list factories |
| `GET` | `/factories/{factory_id}` | Factory summary and build status |
| `PUT` | `/factories/{factory_id}/simulation` | Save the canvas design into the twin tables |
| `GET` | `/factories/{factory_id}/digital-twin` | Full digital twin |
| `GET` | `/factories/{factory_id}/simulation-config` | Configuration for the browser simulation |
| `GET` | `/digital-twin/{factory_id}`, `/digital-twin/{factory_id}/compatibility-matrix` | Twin views |
| `POST` | `/documents/step-4` | Upload a `.zip` of worker CVs |
| `POST` | `/documents/step-5/jobs` | Start the compatibility-matrix job |
| `GET` / `DELETE` | `/documents/step-5/jobs/{job_id}` | Poll / cancel that job |
| `POST` | `/agents/node-autofill` | Suggest attributes for a canvas node |
| `POST` | `/rl-optimization/{factory_id}/optimize` | Start RL training (`end_state`, `working_state`, `total_timesteps`) |
| `GET` | `/rl-optimization/{factory_id}/optimize/status` | Latest job: `queued`, `running`, `converged` or `failed`, with progress |
| `GET` | `/rl-optimization/optimize/{job_id}` | Status of a single job |
| `GET` | `/rl-optimization/{factory_id}/scenarios` | Trained scenario bundle |
| `GET` | `/rl-optimization/digital-twin?factory_id=` | Twin in the RL schema |
| `POST` | `/agents/chat` | Chatbot (`message`, `factory_id`, `scenario_id`, `history`) |

## RL pipeline

1. `POST /rl-optimization/{factory_id}/optimize`:
   - `snapshot_from_db.load_rl_inputs` reads the twin and adds the posted browser state.
   - `SnapshotBuilder` validates the result; invalid input returns `422`.
2. `training_jobs.enqueue`:
   - Writes the inputs to `outputs/rl/<factory_id>/inputs/`.
   - Runs training on a single background thread.
3. `train_ppo.calibrate_baselines` computes the "before" KPIs from a do-nothing rollout.
4. `train_ppo.train_all_scenarios` trains `scenario_01..03`.
5. `export_scenarios` writes `optimal_state.json`.
6. `GET /scenarios` serves that file.

The artifact location is controlled by `RL_OUTPUT_DIR`; the default is `backend/outputs/rl`, which is git-ignored:

```
outputs/rl/<factory_id>/
├── inputs/              factory_md.json, worker_md.json, init_state.json, simulation_state.json, simulation_summary.json
├── training/            scenario_0N/policy.zip, scenario_0N/vecnormalize.pkl
├── optimal_state.json
└── status.json
```

For a longer run, use the CLI from this directory:

```bash
python -m app.optimization.train_ppo --factory-id <factory_id> --timesteps 200000 --sequential
```

## Chatbot routing

`POST /agents/chat` picks an agent based on what data exists for the factory:

| Data available | Agent (`agent/configs`) | Context sent |
|---|---|---|
| RL results | `chatbot_scenario_explainer` | Selected scenario (or all three), bundle meta, simulation summary |
| Twin only | `chatbot_twin_analyst` | Assets, job descriptions, workers, simulation summary |
| Nothing | `chatbot_general` | — |

- The last `AGENT_CHAT_HISTORY_TURNS` messages are passed to the agent as prior conversation turns.
- If the LLM call fails or times out, the endpoint returns `503` and the frontend falls back to local replies.

## Settings

| File | Covers |
|---|---|
| `app/core/config.py` | Database, CORS, RL budget (`RL_*`) and chatbot (`AGENT_CHAT_*`) settings |
| `app/core/agent_config.py` | LLM and embedding endpoints (`LLM_BRIDGE_URL`, `EMBEDDING_BRIDGE_URL`, served model names) and agent directories |

Every value can be set through environment variables or a `.env` file in this directory.

## Tests

From the repository root:

```bash
python -m pytest tests/optimization tests/api_chat
```
