# Prepwise — Architecture

## Overview

Prepwise is a small production-style web application built as a modular monolith.

Core flow:

`React frontend → FastAPI REST API → PostgreSQL`

The architecture should stay simple unless a concrete requirement justifies additional infrastructure.

## Frontend

* React
* TypeScript
* Vite
* One frontend application
* Customer routes and protected admin routes in the same app
* Hosted on Azure Static Web Apps

Next.js is intentionally not used. The application already has a separate Python backend and does not require SSR.

## Backend

* Python
* FastAPI
* REST API under `/api/v1`
* Pydantic for validation
* SQLAlchemy 2 for database access
* Alembic for schema migrations

The backend should keep a simple separation between routes, application logic and database access without unnecessary enterprise abstractions.

## Database

PostgreSQL is the primary database locally and in production.

Production uses Azure Database for PostgreSQL Flexible Server.

Core entities include:

* users
* meals
* ingredients
* allergens
* pickup locations
* cart items
* orders
* order items

Ingredients and allergens should be modelled relationally rather than stored only as free text.

The shopping cart is persistent.

Order creation must be transactional, and order items must preserve relevant historical values such as the price at purchase time.

## Authentication and authorization

Authentication uses Microsoft Entra External ID.

The frontend authenticates the user and sends access tokens to the API.

FastAPI validates the token and maps the external identity to the local user record.

Application roles:

* `customer`
* `admin`

Authorization is enforced in the backend. Frontend route protection alone is not sufficient.

Prepwise does not implement its own password storage.

## Admin

The admin interface uses the same frontend and backend as the customer application.

Admin functionality is limited to operational needs:

* meal management
* availability
* pickup locations
* orders
* order status

It is not a separate product.

## Docker and local development

The backend is containerised with Docker.

Docker Compose is used locally for at least:

* FastAPI
* PostgreSQL

The frontend may run directly through Vite during local development.

Components should only be containerised when there is a real operational reason.

## Azure

Production infrastructure uses:

* Azure Static Web Apps
* Azure Container Apps
* Azure Database for PostgreSQL Flexible Server
* Azure Container Registry
* Azure Key Vault
* Azure Monitor
* Application Insights

The architecture should use low-cost configurations appropriate for a portfolio application.

## Infrastructure as Code

Azure resources are defined with Bicep under `/infra`.

Infrastructure should be reproducible from the repository rather than depending on undocumented manual configuration in Azure Portal.

## Secrets and identity

Secrets must not be stored in source control.

Use:

* Azure Key Vault for production secrets
* Managed Identity where appropriate
* `.env` locally
* `.env.example` without real values

GitHub Actions should authenticate to Azure through OIDC rather than long-lived Azure credentials.

## CI/CD

GitHub Actions is used for CI/CD.

Pull requests should run relevant:

* linting
* type checking
* tests
* frontend build
* Docker build verification

Merge to `main` should deploy the production application automatically.

The deployment flow should include database migrations and a production health check.

## Testing

Backend:

* pytest
* unit tests for important logic
* API/integration tests
* PostgreSQL-backed tests

Frontend:

* Vitest
* React Testing Library

End-to-end:

* Playwright for a small number of critical user and admin flows

Tests should focus on important behaviour rather than coverage percentage.

## Logging and observability

The backend uses structured logging.

Important logs include:

* requests
* exceptions
* relevant domain events
* request or correlation IDs

OpenTelemetry is used for tracing and telemetry.

Application Insights and Azure Monitor provide visibility into:

* requests
* latency
* errors
* dependencies
* database calls
* traces
* relevant metrics

Sensitive credentials, tokens and unnecessary personal information must not be logged.

## Monitoring and health

Backend health endpoints:

* `/health/live`
* `/health/ready`

Production monitoring should cover at least:

* availability
* request volume
* latency
* error rate

At least one real Azure alert should be configured.

## Robustness

The application should include production-relevant safeguards where appropriate:

* input validation
* clear HTTP error responses
* global exception handling
* database transactions
* timeouts for external services
* clear frontend loading and failure states
* proper unauthorized and forbidden handling

Retries should only be added where they are safe and justified.

## AI architecture

Milestone 2 adds one AI assistant on top of the existing application.

The assistant does not access PostgreSQL directly.

### Tool calling

Structured application data and actions are accessed through controlled backend tools, for example:

* search meals
* inspect meal details
* inspect cart
* modify cart
* retrieve user orders
* retrieve pickup locations

Existing authentication, authorization and validation rules still apply.

### RAG

RAG is used for unstructured knowledge such as:

* FAQ
* pickup rules
* storage and reheating guidance
* general service information

Structured meal, nutrition, cart and order data should continue to come from PostgreSQL through backend tools.

PostgreSQL with `pgvector` is the preferred first option if vector search is required.

### Agent workflow

The system uses one agent capable of multi-step reasoning and tool use.

Example flow:

`understand request → retrieve relevant data → check constraints → use tools → return result`

Multi-agent orchestration is not part of the planned scope.

### AI safety

Read operations may run automatically when authorized.

Actions with meaningful side effects require stricter controls.

Final order creation must require explicit user confirmation.

### AI evals

A fixed evaluation set should test important behaviours such as:

* tool selection
* tool arguments
* nutritional constraints
* allergen handling
* retrieval quality
* grounded responses
* workflow outcome
* unwanted side effects

### AI observability

AI requests should be traceable across:

`user → LLM → retrieval/tool → backend → database → LLM → response`

Observability should include relevant latency, model calls, token usage, tool calls, retrieval and errors.

## MCP

MCP is not part of the initial architecture.

It should only be added if Prepwise later needs to expose its tools or data cleanly to external AI clients or agent systems.

## Explicit non-goals

The architecture should not introduce the following without a concrete need:

* microservices
* Kubernetes
* Redis
* message queues
* GraphQL
* custom authentication servers
* separate observability infrastructure
* multi-agent systems

The default architecture remains:

**one frontend + one backend + one PostgreSQL database**
