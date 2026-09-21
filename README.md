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

Local setup instructions will be added as the application foundation is implemented.

The intended development environment uses:

* React/Vite locally
* FastAPI in Docker
* PostgreSQL through Docker Compose
* environment variables defined from `.env.example`

## Status

**Planning complete. Implementation next.**

The product scope, architecture, milestones and development sequence have been defined before coding begins.
