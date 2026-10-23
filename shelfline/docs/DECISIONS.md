# Architecture Decision Records (ADRs)

This directory records significant architectural decisions for the SHELFLINE project.

## Format

Each decision is recorded as a separate Markdown file with the naming convention:
`NNNN-short-description.md` (e.g., `0001-use-fastapi-for-backend.md`)

## Template

```markdown
# ADR NNNN: Title

## Status
Proposed | Accepted | Superseded

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?

### Positive
- ...

### Negative
- ...

## Alternatives Considered
- Alternative 1: ...
- Alternative 2: ...

## Related Decisions
- ADR NNNN: ...
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | Use FastAPI for backend API | Accepted |
| 0002 | Use React + TypeScript + Vite for frontend | Accepted |
| 0003 | Use PostgreSQL with asyncpg for database | Accepted |
| 0004 | Use Alembic for database migrations | Accepted |
| 0005 | Use structured JSON logging with structlog | Accepted |
| 0006 | Use SimClock/RealClock abstraction for time | Accepted |
| 0007 | Event sourcing with append-only event log | Accepted |
| 0008 | Lease-based assignment with TTL and reaper | Accepted |
| 0009 | P90 ETA for safety gate feasibility | Accepted |
| 0010 | Greedy EDF planner with CP-SAT improvement | Accepted |