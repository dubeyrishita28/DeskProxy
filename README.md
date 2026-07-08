
A production-ready semantic query cache built with FastAPI, ChromaDB, and Sentence Transformers (all-MiniLM-L6-v2). Incoming queries are normalised, embedded, and matched against a vector store — identical or semantically similar queries are served from cache without hitting the cloud backend.

Architecture

POST /query
    │
    ▼
QueryProcessingService       ← normalise, expand abbreviations, fix typos
    │
    ▼
SemanticEmbeddingService     ← encode with all-MiniLM-L6-v2 (384-dim)
    │
    ▼
VectorSearchRepository       ← cosine nearest-neighbour search in ChromaDB
    │
    ├─ HIT  (similarity ≥ threshold) ──► return cached result from SQLite
    │
    └─ MISS ────────────────────────► CloudExecutionSimulator
                                           │
                                           ▼
                                       persist to SQLite + ChromaDB
                                           │
                                           ▼
                                       return result
    │
    ▼
TelemetryAggregator          ← record event, invalidate analytics cache
Quick Start

# 1. Clone and enter the project
git clone <repo-url> deskproxy
cd deskproxy

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) copy and edit environment config
cp .env.example .env

# 5. Start the server
uvicorn app.main:app --reload
The API is now live at http://localhost:8000. Interactive docs: http://localhost:8000/docs

API Reference

POST /query

Submit a natural language query.

{
  "query": "Show me the Q3 revenue dashboard",
  "metadata": {"user_id": "u42"}
}
Response:

{
  "query_id": "...",
  "original_query": "Show me the Q3 revenue dashboard",
  "normalized_query": "third quarter revenue dashboard",
  "cache_hit": false,
  "similarity_score": null,
  "matched_query": null,
  "result": "Revenue analysis complete. ...",
  "latency_ms": 214.7,
  "timestamp": "2025-01-15T10:30:00Z"
}
GET /health

Returns operational status of all subsystems.

GET /cache/entries

Lists all stored cache entries with access counts.

DELETE /cache

Purges all entries from SQLite and ChromaDB.

GET /telemetry/summary

Aggregated statistics: hit rate, p95/p99 latency, average similarity score.

Configuration

All settings are driven by environment variables. See .env.example for the full list.

Variable	Default	Description
SIMILARITY_THRESHOLD	0.72	Cosine similarity cutoff for cache hits
EMBEDDING_MODEL	sentence-transformers/all-MiniLM-L6-v2	Embedding model
ANALYTICS_CACHE_TTL	300	Telemetry cache TTL in seconds
LOG_LEVEL	INFO	Logging verbosity
LOG_JSON	false	Emit structured JSON logs
Running Tests

# Unit + integration tests (no model download required for most)
pytest -m "not semantic"

# All tests including semantic matching (requires model download)
pytest

# Manual end-to-end smoke test against a running server
python scripts/test_endpoints.py --base-url http://localhost:8000
Docker Deployment

# Build and start
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
Data is persisted in named Docker volumes (deskproxy_data, deskproxy_logs).

Project Structure

deskproxy/
├── app/
│   ├── main.py                          # FastAPI app factory + lifespan
│   ├── config.py                        # ApplicationSettings (all env vars)
│   ├── api/
│   │   ├── query_router.py              # POST /query
│   │   ├── cache_router.py              # GET /cache/entries, DELETE /cache
│   │   ├── telemetry_router.py          # GET /telemetry/summary
│   │   └── health_router.py             # GET /health
│   ├── core/
│   │   └── logging_config.py            # Structured logging setup
│   ├── db/
│   │   ├── sqlite_repository.py         # SQLite CRUD (no ORM)
│   │   └── vector_search_repository.py  # ChromaDB vector store
│   ├── models/
│   │   └── schemas.py                   # Pydantic request/response models
│   └── services/
│       ├── cache_orchestration_service.py  # Core pipeline
│       ├── query_processing_service.py     # Normalisation + abbreviations
│       ├── semantic_embedding_service.py   # SentenceTransformers wrapper
│       ├── cloud_execution_simulator.py    # Simulated cloud backend
│       └── telemetry_aggregator.py         # Stats + analytics cache
├── tests/
│   ├── test_api_endpoints.py
│   ├── test_query_processing.py
│   ├── test_sqlite_repository.py
│   ├── test_semantic_cache.py
│   └── test_cloud_simulator.py
├── scripts/
│   ├── start.sh
│   └── test_endpoints.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── .env.example
└── .gitignore
