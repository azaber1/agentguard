# AgentGuard

AgentGuard tests AI agents for **reliability, security and policy compliance**
before they reach customers. Register an agent with its tools and permissions,
run it against a library of adversarial and everyday customer-support
scenarios in a **sandbox of simulated tools**, and get a report with failure
explanations, risk classifications and recommendations.

Every security verdict comes from **deterministic policy checks** over the
recorded execution trace. No LLM decides whether an agent behaved safely.

> **Passing tests does not guarantee an agent is secure.** A result describes
> how an agent behaved on these scenarios, in a simulated sandbox, on that
> run. Agents can fail on inputs not covered here, and model behaviour can
> change between runs. Use AgentGuard alongside least-privilege tool design,
> server-side authorization, human approval for high-impact actions and
> production monitoring.

## What's included

| Area | Details |
|---|---|
| Dashboard | Tests executed, pass/fail, reliability score, policy violations by severity and risk category, per-agent scores, recent runs |
| Agent registry | Create, edit and archive agents; wire tools in and authorize them separately; refund limit, identity-verification and tool-budget policies; encrypted write-only endpoint tokens |
| Testing engine | Sandbox with 10 simulated tools, fault injection (errors, timeouts, malformed data), world patches for planted injections, multi-turn scripted customers |
| Scenarios | 25 across normal interactions, unauthorized refunds, prompt injection, sensitive-data exposure, API failures and repeated tool calls |
| Policy engine | 12 deterministic rules (AG-001…AG-012) plus per-scenario expected-vs-actual checks, mapped to the OWASP Top 10 for LLM Applications (2025) |
| Reports | Per-scenario findings with evidence, expectation tables, full traces, aggregated recommendations, JSON export |
| Agents under test | Built-in reference agents (no API keys) or **your own agent over HTTP** (see [`docs/HTTP_AGENT_PROTOCOL.md`](docs/HTTP_AGENT_PROTOCOL.md)) |

Architecture, data model and rule catalogue: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick start (Docker Compose)

Requirements: Docker with Compose v2.

```bash
git clone https://github.com/azaber1/agentguard.git
cd agentguard
cp .env.example .env
# Fill in the two required secrets:
gen() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
sed -i.bak -e "s/^SECRET_KEY=.*/SECRET_KEY=$(gen 48)/" -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(gen 24)/" .env
docker compose up -d --build
```

Open <http://localhost:3000> and sign in with the demo account:

* **Email:** `demo@agentguard.dev`
* **Password:** `AgentGuard-demo-2026` (or whatever you set as `DEMO_PASSWORD`)

On first start the backend runs database migrations and, with
`SEED_DEMO_DATA=true`, seeds a demo organization, five agents and four completed
test runs:

| Agent | Profile | Typical result |
|---|---|---|
| Support Concierge | `guarded` | Passes all 25 scenarios |
| Order Assistant (beta) | `mostly_safe` | Follows instructions planted in tool output; leaks card numbers and secrets |
| RetryBot | `loop_prone` | Retry loops, including a double refund after a timeout |
| Refund Helper v1 | `naive` | Fails most security scenarios |
| Client Agent (HTTP) | HTTP | Placeholder: point it at your endpoint |

The reference agents are deterministic and rule-based, **not language
models**. They exist for demos and to prove the engine catches each class of
failure.

### Try the example HTTP agent

```bash
echo "ALLOW_PRIVATE_AGENT_URLS=true" >> .env   # local development only
docker compose --profile example up -d --build
```

Then register an agent with provider **HTTP endpoint** and URL
`http://example-agent:9000/agentguard/step`, and run the scenarios.

## Local development

Commands below run from the repository root unless noted.

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22, PostgreSQL 16.

```bash
# Database
createdb agentguard && createdb agentguard_test

# Backend (http://localhost:8000, API docs at /api/docs)
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agentguard
uv run alembic upgrade head
uv run python -m app.seed          # optional demo data
uv run uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000), in another terminal
cd frontend
npm install
npm run dev                        # proxies /api to BACKEND_URL (default http://localhost:8000)
```

## Tests

```bash
# Backend: 157 unit tests (no DB) + 42 integration tests (PostgreSQL)
cd backend
export TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agentguard_test
uv run pytest                  # everything
uv run pytest tests/unit       # engine only, no database needed
uv run ruff check app tests alembic

# Frontend: Vitest, ESLint, type-check, production build
cd frontend
npm test && npm run lint && npm run typecheck && npm run build
```

Integration tests build the schema from the Alembic migrations and always
use `TEST_DATABASE_URL`. They never touch `DATABASE_URL`, and they truncate
every table between tests. CI runs both suites
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local Postgres | SQLAlchemy URL (`postgresql+psycopg://…`) |
| `SECRET_KEY` | **required** | Derives the key that encrypts agent tokens at rest; production refuses the default |
| `ENVIRONMENT` | `development` | `production` enables Secure cookies and HSTS, and disables the API docs |
| `ALLOW_REGISTRATION` | `true` | Self-service sign-up |
| `COOKIE_SECURE` | auto | Force the Secure cookie flag on or off |
| `ALLOW_PRIVATE_AGENT_URLS` | `false` | Allow agent endpoints on private networks (dev only) |
| `SEED_DEMO_DATA` | `true` in Compose | Seed demo data on start (refused when `ENVIRONMENT=production`) |
| `SESSION_TTL_HOURS` | `12` | Session lifetime |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Per IP + email |

## Security model

* **Authentication before anything is exposed.** Every API route except
  health, login, registration and the registration-config flag requires a
  session. Passwords are hashed with bcrypt. Sessions are random tokens stored
  only as SHA-256 hashes, sent in an `HttpOnly`, `SameSite=Lax` cookie, and
  revoked server-side on logout. Login is rate-limited and doesn't reveal
  whether an email exists.
* **CSRF:** state-changing requests require `X-Requested-With: AgentGuard`,
  which browsers can't send cross-site without a CORS preflight the API never
  grants.
* **No secrets in the frontend.** The browser only talks to the Next.js
  origin, which proxies `/api/*` to the backend server-side. Agent endpoint
  tokens are Fernet-encrypted at rest, write-only through the API, and never
  appear in traces or reports.
* **Tenant isolation:** every query is scoped to the user's organization;
  other tenants' resources return 404.
* **Sandboxed execution:** there are no payment, email or account
  integrations in the codebase. "Refunds" and "emails" are simulated records
  discarded after each scenario. Customer agents are called over HTTP with
  SSRF protection (public hosts only, re-validated per request, no redirects,
  size and time limits).
* Security headers (CSP, frame denial, nosniff) on both tiers. Containers run
  as non-root users, and the backend isn't published outside the Compose
  network.

### Before exposing AgentGuard publicly

1. Set `ENVIRONMENT=production`, a strong `SECRET_KEY` and a strong `POSTGRES_PASSWORD`.
2. Set `SEED_DEMO_DATA=false`; the demo account has a published password.
3. Set `ALLOW_REGISTRATION=false` unless you want open sign-up.
4. Keep `ALLOW_PRIVATE_AGENT_URLS=false`.
5. Terminate TLS in front of the frontend (reverse proxy or load balancer).
6. The login rate limiter is in-process; behind several replicas, move it to a shared store.

## Project layout

```
agentguard/
├── backend/                 FastAPI app
│   ├── app/engine/          sandbox, scenarios, agents, policy engine, runner, scoring (pure Python)
│   ├── app/api/routes/      auth, agents, catalog, runs, dashboard, health
│   ├── app/services/        run execution and report building
│   ├── alembic/             database migrations
│   └── tests/               unit/ and integration/
├── frontend/                Next.js 15 + TypeScript + Tailwind CSS
│   └── src/app/             login, dashboard, agents, scenarios, runs/[id] report
├── examples/http_agent/     minimal agent implementing the HTTP step protocol
├── docs/                    architecture, implementation plan, HTTP protocol
└── docker-compose.yml
```

## Known limitations

* Runs execute in a FastAPI background task inside the API process, one
  scenario at a time. Interrupted runs are marked failed on restart. A worker
  queue is the next step for scale.
* Free-text checks (e.g. "must not claim the refund succeeded") use regular
  expressions. They are deterministic but heuristic, and an agent can phrase
  things in ways a pattern misses.
* The scenario library targets customer-support agents. Custom scenarios
  aren't editable in the UI yet.
