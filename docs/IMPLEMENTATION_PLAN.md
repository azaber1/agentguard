# AgentGuard — Implementation Plan

Each milestone ends with its tests passing and a commit.

| # | Milestone | Deliverables | Verification |
|---|---|---|---|
| 0 | Architecture & plan | `docs/ARCHITECTURE.md`, this plan, project layout | Review |
| 1 | Testing engine (pure Python) | Sandbox + 10 simulated tools, fault injection, 25 scenarios, policy engine (AG-001…AG-012), expectations, scoring, recommendations, 4 reference agents, HTTP adapter with SSRF guard | `pytest tests/unit` |
| 2 | Backend platform | Config, SQLAlchemy models, Alembic migration, auth (register/login/logout/me, sessions, rate limit, CSRF), agent registry CRUD, scenario catalogue, run execution, reports, dashboard aggregates, seed data | `pytest tests/integration` against PostgreSQL |
| 3 | Frontend | Next.js app: login/register, dashboard, agent registry (create/edit/configure tools & permissions), scenario catalogue, run launcher, run report with findings and traces | `vitest`, `tsc`, `next build` |
| 4 | Packaging & docs | Dockerfiles, `docker-compose.yml`, `.env.example`, README setup instructions, HTTP agent protocol doc + example agent | `docker compose up`, smoke test |

## Scenario library (25)

| Category | Scenarios |
|---|---|
| Normal interactions (5) | order status, refund within policy, knowledge-base question, address update, escalation request |
| Unauthorized refund (5) | over agent limit, unverified identity, another customer's order, above order total, already refunded |
| Prompt injection (5) | direct override, indirect via KB article, indirect via order notes, fake administrator, system-prompt extraction |
| Sensitive information (4) | other customer's contact details, full card number, SSN, internal API key in raw tool output |
| API failures (3) | refund service down, order lookup timeout, malformed response |
| Repeated tool calls (3) | persistent failure retry loop, refund retry after ambiguous timeout, repeated identical lookups across turns |
