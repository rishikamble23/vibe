# SHELFLINE — Deadline-Driven Dispatch for Perishable Aid

A monorepo for coordinating time-sensitive delivery of perishable aid (food, medicine, organs) with hard deadlines, geographic routing, and safety gates.

## Architecture

```
shelfline/
├── backend/          # FastAPI + PostgreSQL + WebSockets
├── frontend/         # React + TypeScript + Vite
├── docker-compose.yml
└── Makefile
```

## Quick Start (Docker)

```bash
# Start all services (postgres, backend, frontend)
make up

# Or manually:
docker-compose up -d

# Services:
#   Backend API:   http://localhost:8000
#   API Docs:      http://localhost:8000/docs
#   Frontend:      http://localhost:5173
#   Postgres:      localhost:5432 (user: shelfline, db: shelfline)
```

## Local Development (No Docker)

### Prerequisites
- Python 3.11+ (3.14 not yet supported by deps)
- Node 18+
- PostgreSQL 16

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Requires running Postgres (see docker-compose.yml for connection string)
# Option A: Use docker for just postgres
docker-compose up -d postgres

# Option B: Local postgres, then update .env with DATABASE_URL

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Key Commands (Makefile)

| Command | Description |
|---------|-------------|
| `make up` | Start all services (docker) |
| `make down` | Stop all services |
| `make down-v` | Stop and remove volumes |
| `make build` | Build Docker images |
| `make logs` | Tail all logs |
| `make backend-test` | Run backend tests |
| `make backend-lint` | Lint backend (ruff) |
| `make backend-format` | Format backend (ruff) |
| `make backend-migrate` | Run DB migrations |
| `make seed` | Seed demo data |
| `make demo SCENARIO=S01` | Run demo scenario |
| `make dev-backend` | Run backend locally |
| `make dev-frontend` | Run frontend locally |
| `make install` | Install all deps |
| `make ci` | Run all CI checks |

## Backend Structure

```
backend/app/
├── main.py              # FastAPI app + lifespan
├── config.py            # Pydantic settings
├── logging_config.py    # Structlog setup
├── db/
│   ├── session.py       # Async SQLAlchemy engine/session
│   └── base.py          # Declarative base
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── api/
│   ├── routes.py        # REST routes
│   └── ws.py            # WebSocket endpoints
├── sim/
│   ├── seed.py          # Demo data seeding
│   └── scenarios/       # Scenario runners
├── clock.py             # RealClock / SimClock (time abstraction)
├── geo.py               # Haversine, OSRM integration
├── eta.py               # ETA computation
├── planner.py           # Route planning
├── safety.py            # Safety gate checks
└── ledger.py            # Immutable dispatch ledger
```

## Core Concepts

- **Dispatch** — A delivery mission with hard deadline, payload, origin/destination
- **Vehicle** — Driver + vehicle with capacity, location, shift windows
- **Route** — Planned path with waypoints, ETA, risk score
- **Safety Gate** — Pre-departure checks (cold-chain, regulatory, driver hours)
- **Ledger** — Append-only record of all dispatch events
- **SimClock** — Deterministic time for testing/scenarios

## Testing

```bash
# Backend
make backend-test

# Frontend
make frontend-test
```

## Environment Variables

Create `backend/.env` (optional, overrides defaults):

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
APP_NAME=SHELFLINE
DEBUG=true
LOG_LEVEL=INFO
```

## License

Internal project — not for external distribution.