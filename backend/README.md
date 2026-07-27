backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # entry point, create FastAPI app, include routers
│   ├── core/                    # konfigurasi inti, tidak spesifik domain
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── security.py          # JWT, hashing, auth helpers
│   │   ├── logging.py           # setup logging
│   │   └── exceptions.py        # custom exception classes + handlers
│   │
│   ├── db/
│   │   ├── session.py           # SQLAlchemy engine, sessionmaker / async session
│   │   ├── base.py              # Base class untuk models
│   │   └── migrations/          # alembic
│   │
│   ├── api/
│   │   ├── deps.py              # shared dependencies (get_db, get_current_user)
│   │   └── v1/                  # versioning API
│   │       ├── router.py        # gabungkan semua router jadi satu APIRouter
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── documents.py
│   │       │   ├── qa.py
│   │       │   └── summarization.py
│   │
│   ├── modules/                 # domain-driven, satu folder per domain/fitur
│   │   ├── documents/
│   │   │   ├── models.py        # SQLAlchemy models
│   │   │   ├── schemas.py       # Pydantic request/response schemas
│   │   │   ├── service.py       # business logic
│   │   │   ├── repository.py    # query DB (CRUD layer)
│   │   │   └── exceptions.py    # domain-specific exceptions
│   │   ├── qa/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   └── summarization/
│   │       └── ...
│   │
│   ├── services/                # cross-domain / external services
│   │   ├── llm_client.py        # koneksi ke vLLM/LLM server kamu
│   │   ├── embedding_client.py  # koneksi ke BGE-M3 server
│   │   └── reranker_client.py
│   │
│   └── worker/                  # background task (kalau pakai Celery/RQ/arq)
│       └── tasks.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── alembic.ini
├── requirements.txt / pyproject.toml
├── Dockerfile
└── docker-compose.yml