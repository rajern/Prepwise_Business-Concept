# Prepwise — Decisions

## Purpose

This file records the main product and architecture decisions that should not be reopened during implementation unless a concrete problem requires it.

## Product

### Meal-prep ordering concept

Prepwise is a portfolio-oriented business concept for a meal-prep service in Oslo.

The goal is to build a realistic production application, not to validate the business model.

### Target user

Health- and fitness-conscious users who care about convenience, nutrition, ingredients and allergens.

### Pickup only

Milestone 1 supports multiple pickup locations in Oslo.

Home delivery and delivery logistics are excluded.

### No real payment

Checkout creates a real order in the system, but no payment provider is integrated in Milestone 1.

### Minimal admin interface

The same application includes protected admin routes for managing meals, pickup locations and orders.

A separate admin product is unnecessary.

---

## Application architecture

### Modular monolith

Use:

`React → FastAPI → PostgreSQL`

Do not introduce microservices unless a real requirement appears.

### React + TypeScript + Vite

Chosen instead of Next.js because Prepwise already has a separate Python backend and does not require SSR or a second server layer.

### FastAPI

Chosen to build a clear Python REST API while extending existing Python experience into production backend development.

### REST instead of GraphQL

The product has straightforward resources and workflows. GraphQL would add complexity without solving a current problem.

### PostgreSQL

Use PostgreSQL locally, in tests and in production. Production PostgreSQL is hosted by Neon, while local development and CI use separate local or containerised PostgreSQL instances.

Do not substitute SQLite for integration testing.

### Persistent cart

The shopping cart is stored in the backend/database rather than only in frontend state.

This makes the application behaviour more realistic and creates meaningful backend/API/database work.

---

## Authentication

### Microsoft Entra External ID

Use managed customer authentication instead of implementing password storage ourselves.

### Local application roles

Prepwise keeps `customer` and `admin` roles in its own application data.

Authorization is always enforced by the backend.

---

## Cloud and deployment

### Microsoft Azure

Azure is the primary production hosting platform for the frontend, backend, secrets and application observability. The production database is an explicit exception and is hosted by Neon.

### Azure Container Apps

The FastAPI backend runs as a Docker container in Azure Container Apps.

### Azure Static Web Apps

The React frontend is deployed separately as a static web application.

The production Static Web App resource is created in East US 2 because Azure currently blocks
new-customer creation in West Europe. This does not move the backend or other Azure resources
from Norway East.

### Neon PostgreSQL

Use Neon for the managed production PostgreSQL database.

Azure Database for PostgreSQL Flexible Server is more Azure-native, but its ongoing fixed cost is not justified for a portfolio application with very low traffic. Neon preserves the relevant PostgreSQL, SQLAlchemy, Alembic, relational modelling, query and transaction experience while allowing the deployed application to remain available at little or no database cost within the applicable usage limits.

Azure Container Apps connects to Neon over TLS. Neon operates and monitors the database platform; Azure observability covers the application, backend traffic and database dependency spans emitted by the application.

Production uses separate Neon runtime and migration/owner roles. The running backend receives only
the runtime connection through a Key Vault reference; the migration credential is reserved for
the deployment migration step.

Neon is configured separately from the Azure infrastructure. Do not introduce Terraform or another infrastructure-as-code tool solely to provision Neon at this stage.

### GitHub Container Registry

Backend container images are published to GitHub Container Registry and pulled by Azure Container Apps.

Azure Container Registry is not used because its fixed cost is unnecessary for the expected traffic and GitHub Container Registry already fits the GitHub Actions delivery workflow.

The production GHCR package is public so Container Apps can pull immutable commit-tagged images
without storing a GitHub PAT or registry password in Azure. GitHub Actions publishes with its
short-lived `GITHUB_TOKEN`.

### Bicep

Azure infrastructure is defined as code with Bicep.

Bicep is preferred over Terraform because this project is Azure-specific and the additional complexity is lower.

Bicep covers only Azure resources and must not imply that Neon is provisioned through the Azure deployment.

### GitHub Actions

CI/CD runs through GitHub Actions.

Cloud deployment should be part of the normal development workflow rather than a manual final step.

### OIDC

GitHub Actions authenticates to Azure using OIDC rather than long-lived Azure credentials.

### Runtime managed identity

The Container App uses a user-assigned managed identity. Its Key Vault RBAC assignment is scoped
to the `database-url` secret, rather than the whole vault, and the application receives the value
through a Container Apps secret reference. Secret values are not part of Bicep outputs or GitHub
configuration.

---

## Engineering practices

### Alembic migrations

Database schema changes are made through versioned migrations.

Production database schemas should not be edited manually.

### Seed data separate from migrations

Demo meals, allergens and pickup locations are created through seed tooling rather than schema migrations.

### Production hardening during development

Testing, validation, logging, error handling and observability are added alongside functionality.

They should not be postponed until the end.

### OpenTelemetry + Azure observability

Use OpenTelemetry with Application Insights / Azure Monitor instead of introducing a separate observability stack.

---

## AI

### One AI assistant

Milestone 2 uses one assistant with tools and multi-step workflows.

A multi-agent architecture is not currently justified.

### Tools for structured data

Meal, nutrition, cart and order data should be accessed through controlled backend tools.

The model must not access PostgreSQL directly.

### RAG only for unstructured knowledge

Do not copy structured application data into a vector store simply to demonstrate RAG.

RAG is reserved for documents and unstructured knowledge where semantic retrieval is appropriate.

### PostgreSQL + pgvector first

If vector search is needed, prefer extending the existing PostgreSQL database with `pgvector` before introducing another database.

### MCP deferred

MCP is not part of the planned implementation.

Add it only if a later requirement makes external exposure of Prepwise tools/data genuinely useful.

### No multi-agent by default

Use a single agent unless implementation reveals a clear problem that genuinely benefits from multiple specialized agents.

---

## Scope principle

Do not add technologies or features solely because they look valuable on a CV.

Prefer the simplest architecture that solves the product requirement while still demonstrating the intended engineering skill.
