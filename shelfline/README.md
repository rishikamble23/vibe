# SHELFLINE — Deadline-Driven Dispatch for Perishable Aid

> **The Last-Mile Spoilage Trap**: Food and medicine spoil while waiting for coordination. SHELFLINE treats every batch as a ticking clock, not inventory.

## The Problem

Perishable aid (cooked meals, medicines, kits) has a hard deadline. Current solutions treat this as a marketplace — "claim this batch" — but that creates ghost reservations, double-counting, and no recovery when things go wrong.

**SHELFLINE's approach:**
- Every batch has a computed `deliver_by` deadline from cook time + shelf life
- Every assignment is a **short lease** that expires automatically unless the rider proves progress
- Every in-transit rider carries **pre-computed fallbacks** (Plan B, Plan C) so shelter closures or traffic don't strand cargo
- **Safety Gate** vetoes anything that could finish late using P90 (pessimistic) travel times, not averages
- Everything is an **event** — state is rebuildable, demo is replayable

## Quick Start

```bash
# Clone and enter
git clone <this-repo>
cd shelfline

# Start everything (Postgres + Backend + Frontend)
make up

# Seed demo data
make seed

# Open the apps
# Control Room:  http://localhost:5173/control
# Rider PWA:     http://localhost:5173/rider
# Shelter Tablet: http://localhost:5173/shelter
# Donor Form:    http://localhost:5173/donor
# API Docs:      http://localhost:8000/docs
```

## Architecture

```
shelfline/
├── backend/                 # FastAPI + SQLAlchemy + PostgreSQL
│   ├── app/
│   │   ├── api/            # REST endpoints + WebSockets
│   │   ├── db/             # Models, migrations (Alembic)
│   │   ├── clock.py        # RealClock / SimClock abstraction
│   │   ├── events.py       # Event log + idempotency
│   │   ├── geo.py          # Haversine, bounding box
│   │   ├── eta.py          # P50/P90 ETA service
│   │   ├── safety_gate.py  # is_safe() veto
│   │   ├── rules/          # YAML rules engine
│   │   ├── ledger.py       # Atomic shelter capacity
│   │   ├── batches.py      # Batch/lot intake
│   │   ├── leases.py       # Lease state machine
│   │   ├── reaper.py       # Background lease expiry loop
│   │   ├── planner/        # Greedy EDF + CP-SAT
│   │   ├── reroute.py      # Mid-transit recovery
│   │   └── sim/            # Rider agents, chaos console
│   └── tests/              # Unit, scenario, property, concurrency
├── frontend/               # React + TypeScript + Vite
│   ├── src/
│   │   ├── control/        # Control Room dashboard
│   │   ├── rider/          # Rider PWA
│   │   ├── shelter/        # Shelter tablet
│   │   ├── donor/          # Donor form
│   │   └── shared/         # API client, components
├── docs/                   # ARCHITECTURE.md, SCENARIOS.md, DECISIONS.md
├── docker-compose.yml
└── Makefile
```

## Design Laws (Print These)

1. **The clock is a resource** — Remaining safe time (slack) is what we schedule, spend, and protect
2. **A claim is a lease, never ownership** — Leases expire automatically. Nobody can "park" a batch
3. **Cargo in motion always has a Plan B** — A rider is never stranded; fallbacks are precomputed and continuously refreshed
4. **Safety is a veto, not a score** — A late or incompatible delivery is not a bad option, it is an illegal one
5. **Everything is an event** — State is rebuilt from an append-only log; the planner can be re-run at any moment
6. **Capacity is a ledger, not a flag** — `available = need − received − committed`, updated atomically
7. **Never trust the happy path** — Every API call is idempotent; every timer is persisted; every external dependency has a fallback

## Development

```bash
# Run all CI checks locally
make ci

# Backend only
make dev-backend        # Run with hot reload on :8000
make backend-test       # Run tests
make backend-lint       # Ruff check
make backend-migrate    # Run migrations

# Frontend only
make dev-frontend       # Run with hot reload on :5173
make frontend-lint      # ESLint
make frontend-typecheck # TypeScript check
make frontend-build     # Production build

# Database
make db-shell           # psql prompt
make db-reset           # Drop all tables, re-run migrations
```

## Demo / Chaos Console

```bash
# Run a scenario (S01-S22)
make demo SCENARIO=S06

# Inject chaos while running
# POST /admin/chaos/ghost_rider
# POST /admin/chaos/traffic_multiplier {"multiplier": 3.0}
# POST /admin/chaos/close_shelter {"shelter_id": 3}
# POST /admin/chaos/advance_clock {"minutes": 30}
```

## Testing Strategy

| Layer | Tool | Focus |
|-------|------|-------|
| Unit | pytest | Clock, ETA, Safety Gate, Ledger, Lease FSM |
| Scenario | pytest + SimClock | S01-S22 end-to-end |
| Property | Hypothesis | Invariants (Appendix F) over random event sequences |
| Concurrency | pytest | 50 simultaneous claims, duplicate idempotency keys |
| Restart | pytest | Kill backend mid-scenario, verify reaper resumes |

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Setup and foundations | 🟢 Done |
| 1 | Core primitives | ⏳ Next |
| 2 | Entities, batches, ledger | ⬜ |
| 3 | Lease engine (anti-ghost) | ⬜ |
| 4 | Planner | ⬜ |
| 5 | Reroute and fallbacks | ⬜ |
| 6 | Rules engine | ⬜ |
| 7 | API and realtime | ⬜ |
| 8 | Frontends | ⬜ |
| 9 | Simulator and Chaos Console | ⬜ |
| 10 | Hardening | ⬜ |
| 11 | Stretch | ⬜ |
| 12 | Docs, pitch, rehearsal | ⬜ |
| 13 | Freeze and demo protocol | ⬜ |

## Commit Convention

```
feat(area): what changed
fix(area): what was broken
refactor(area): restructuring
test(area): adding tests
docs(area): documentation
chore: maintenance
```

Areas: `clock`, `events`, `geo`, `eta`, `safety`, `rules`, `ledger`, `batches`, `leases`, `reaper`, `planner`, `reroute`, `api`, `ws`, `sim`, `frontend`, `ci`, `docs`

## License

MIT — see LICENSE file.

## Team

- **Engine Lead** — Phases 1, 3, 4, 5
- **Backend & Rules** — Phases 2, 6, 7
- **Frontend** — Phase 8
- **Sim, QA, Docs** — Phases 9, 10, 12