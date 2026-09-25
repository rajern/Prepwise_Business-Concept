# Prepwise — Business Concept

Prepwise is a meal-prep ordering concept for health- and fitness-conscious users in Oslo.

The project is built as a realistic production application to demonstrate practical software, cloud, DevOps and AI engineering.

> This is a portfolio project and business concept, not a live commercial meal-prep service.

## Product

Customers can:

* browse available meals
* view prices, ingredients, allergens and nutritional information
* create an account and log in
* maintain a persistent shopping cart
* choose between pickup locations
* place an order
* view order history and status

A protected admin interface allows employees to manage meals, pickup locations and orders.

See [`PRODUCT.md`](./PRODUCT.md) for the product scope.

## Architecture

Core architecture:

`React + TypeScript → FastAPI → PostgreSQL`

The frontend and backend are hosted on Microsoft Azure. The production PostgreSQL database is hosted by Neon.

Main technologies:

* React, TypeScript and Vite
* Python and FastAPI
* PostgreSQL, SQLAlchemy and Alembic
* Docker and Docker Compose
* Microsoft Entra External ID
* Azure Container Apps
* Azure Static Web Apps
* Neon PostgreSQL
* GitHub Container Registry
* Azure Key Vault
* Azure Monitor and Application Insights
* OpenTelemetry
* Bicep
* GitHub Actions
* pytest, Vitest and Playwright

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the technical architecture and [`DECISIONS.md`](./DECISIONS.md) for the main design decisions.

## Milestone 1 — Production application

**Status: Complete and production verified.**

The first milestone is a complete non-AI application with:

* customer and admin interfaces
* authentication and authorization
* relational PostgreSQL data model
* persistent cart and ordering
* Docker-based development
* Azure deployment
* Infrastructure as Code
* CI/CD
* secrets management
* logging, monitoring and distributed tracing
* automated testing and production health checks

Milestone 1 is intended to be independently portfolio-ready.

## Milestone 2 — AI application layer

The second milestone adds an AI assistant on top of the production system.

Planned capabilities include:

* tool/function calling over application functionality
* RAG for unstructured service knowledge
* multi-step agent workflows
* systematic AI evals
* AI tracing and observability
* safeguards around state-changing actions

T9.1 provides the first authenticated, single-turn Responses API integration. The local backend
reads `OPENAI_API_KEY` from the ignored root `.env`; production reads `openai-api-key` from Azure
Key Vault through the Container App managed identity. Model and reasoning settings remain
environment-configurable.

Structured application data remains accessed through controlled backend tools rather than direct model access to the database.

MCP and multi-agent architecture are intentionally excluded unless a real architectural need appears.

## Development approach

The project is built incrementally:

`foundation → minimal vertical slice → early Azure deployment → auth → customer flow → admin → production QA → AI layer`

Production concerns such as testing, logging, security and observability are added throughout development rather than at the end.

See [`ROADMAP.md`](./ROADMAP.md) for the development sequence and [`TASKS.md`](./TASKS.md) for the implementation plan.

## Repository structure

```text
prepwise/
├── frontend/
├── backend/
├── infra/
├── docs/
├── .github/
│   └── workflows/
├── README.md
├── PRODUCT.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── ROADMAP.md
├── TASKS.md
├── docker-compose.yml
└── .env.example
```

## Local development

Prerequisites:

* Node.js 22 or newer with Corepack
* Python 3.11 or newer
* Docker Desktop for the containerised development environment

Install and run the frontend:

```powershell
cd frontend
corepack enable
pnpm install
Copy-Item .env.example .env.local
pnpm dev
```

Install and run the backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn prepwise_api.main:app --reload --port 8000
```

The frontend is available at `http://localhost:3000`. Backend liveness and readiness are available
at `http://localhost:8000/health/live` and `http://localhost:8000/health/ready`, and the public catalogue endpoint is available at
`http://localhost:8000/api/meals`. Vite proxies local `/api` requests to FastAPI.

Run the containerised backend and PostgreSQL from the repository root:

```powershell
docker compose up --build -d
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python -m prepwise_api.seed
Invoke-RestMethod http://localhost:8000/health/ready
```

The seed command synchronises the development catalogue and can safely be run more than once.
For a deployed frontend, set `VITE_API_BASE_URL` to the Azure Container Apps origin during the
frontend build and set the backend's `CORS_ALLOWED_ORIGINS` to the Static Web Apps origin.

The frontend uses browser-delegated Microsoft Entra External ID for customer sign-up, sign-in and
sign-out. FastAPI validates delegated API tokens and maps the immutable Entra identity to a local
user when the frontend calls the protected `GET /api/me` endpoint. The meal catalogue remains
public. Customer/admin roles are stored locally and enforced by backend dependencies; no public
role-assignment endpoint exists. Configuration and trust boundaries are documented in
[`docs/ENTRA_EXTERNAL_ID.md`](./docs/ENTRA_EXTERNAL_ID.md).

Stop the containers without deleting PostgreSQL data:

```powershell
docker compose down
```

Copy `.env.example` to `.env` to override local defaults; never commit `.env`.

## Quality checks

Run the frontend checks from `frontend/`:

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build
```

The Playwright suite runs against the real frontend, FastAPI backend and PostgreSQL database.
CI starts and seeds the isolated stack, provisions deterministic customer/admin test identities,
and runs the browser flows without external Entra credentials. The test identity adapter is
fail-closed and can only be enabled when the backend runs with `APP_ENV=test`.

Run the backend checks from `backend/`:

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy .
.venv\Scripts\python -m pytest
```

Pull requests run the same backend and frontend checks in GitHub Actions, build the backend
Docker image and run the critical Playwright flows. The workflow has read-only repository
permissions and does not use deployment credentials or production secrets.

Pushes to `main` first reuse those CI checks and then deploy through the protected `production`
environment. The deployment publishes the backend to GHCR, migrates Neon using the dedicated
migration role, deploys Container Apps and Static Web Apps, and runs production smoke checks for
the frontend, API, database-backed readiness, public catalogue/detail endpoints and browser CORS.
Any failed smoke check fails the deployment workflow.
Azure authentication uses OIDC; production database credentials are read from Key Vault only for
the step that needs them.

## Status

**Milestone 1 complete. Milestone 2 not started.**

The complete non-AI product is implemented, tested and running in production. Customer and admin
journeys, security controls, CI/CD, observability, alerting and production smoke tests have been
verified. The next development phase is the AI application layer defined in `TASKS.md`.
