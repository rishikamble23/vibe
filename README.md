# Vibeathon — SHELFLINE Monorepo

This repository contains the **SHELFLINE** project: a deadline-driven dispatch system for perishable aid (food, medicine, organs) with hard deadlines, geographic routing, and safety gates.

## Project Structure

```
vibe/
├── shelfline/          # Main monorepo (FastAPI + React + PostgreSQL)
│   ├── backend/        # FastAPI + PostgreSQL + WebSockets
│   ├── frontend/       # React + TypeScript + Vite
│   ├── docker-compose.yml
│   ├── Makefile
│   └── README.md       # Detailed project documentation
├── doc/                # Project specifications (PDFs)
└── .opencode/          # Local OpenCode session data (ignored)
```

## Quick Start

```bash
cd shelfline
make up
```

This starts all services via Docker:
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:5173
- **PostgreSQL**: localhost:5432 (user: shelfline, db: shelfline)

## Development

See [shelfline/README.md](shelfline/README.md) for detailed setup, commands, and architecture.

## Key Features

- **127/127 unit tests passing** (Phases 0-7 complete)
- Real-time WebSocket endpoints for control room, riders, shelters
- Deterministic SimClock for testing/scenarios
- Greedy EDF planner with multi-drop insertion
- Rules engine with YAML configuration
- Safety gates (cold-chain, regulatory, driver hours)
- Immutable dispatch ledger

## License

Internal project — not for external distribution.