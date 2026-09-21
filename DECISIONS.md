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

Use PostgreSQL locally, in tests and in production.

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

Azure is the production cloud platform for the project.

### Azure Container Apps

The FastAPI backend runs as a Docker container in Azure Container Apps.

### Azure Static Web Apps

The React frontend is deployed separately as a static web application.

### Bicep

Azure infrastructure is defined as code with Bicep.

Bicep is preferred over Terraform because this project is Azure-specific and the additional complexity is lower.

### GitHub Actions

CI/CD runs through GitHub Actions.

Cloud deployment should be part of the normal development workflow rather than a manual final step.

### OIDC

GitHub Actions authenticates to Azure using OIDC rather than long-lived Azure credentials.

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
