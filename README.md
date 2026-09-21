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
pnpm dev
```

Install and run the backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn prepwise_api.main:app --reload --port 8000
```

The frontend is available at `http://localhost:3000`. The backend health endpoint is available
at `http://localhost:8000/health`, and the public catalogue endpoint is available at
`http://localhost:8000/api/meals`. Vite proxies local `/api` requests to FastAPI.

Run the containerised backend and PostgreSQL from the repository root:

```powershell
docker compose up --build -d
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python -m prepwise_api.seed
Invoke-RestMethod http://localhost:8000/health/database
```

The seed command synchronises the development catalogue and can safely be run more than once.
For a deployed frontend, set `VITE_API_BASE_URL` to the Azure Container Apps origin during the
frontend build and set the backend's `CORS_ALLOWED_ORIGINS` to the Static Web Apps origin.

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
pnpm build
```

Run the backend checks from `backend/`:

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy .
.venv\Scripts\python -m pytest
```

## Status

**Implementation in progress.**

The runnable foundation, relational model, migrations, development catalogue and first
frontend-to-database vertical slice are complete. Development continues with the early Azure
deployment tasks in `TASKS.md`.
