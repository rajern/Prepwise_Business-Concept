# Prepwise — Roadmap

## Purpose

This roadmap defines the order of development and the boundary between the two main milestones.

The goal is to get a small production system live early, then extend it incrementally.

## Milestone 1 — Production application

Milestone 1 is complete when the full non-AI product is implemented, tested, deployed and documented.

It includes:

* customer-facing web application
* meal catalogue and meal details
* authentication and authorization
* persistent cart
* pickup selection
* checkout and order creation
* order history and status
* admin interface
* PostgreSQL and migrations
* Docker
* Azure deployment
* Bicep infrastructure
* CI/CD
* secrets management
* logging
* monitoring and observability
* health checks
* production-relevant testing and error handling

When Milestone 1 is complete, the project should already be ready for CV and GitHub use.

## Development order for Milestone 1

### 1. Repository and development foundation

Set up the repository structure, frontend, backend, local PostgreSQL, Docker Compose, testing tools and basic CI.

### 2. Minimal end-to-end application

Create the initial database model, migrations, seed data, FastAPI API and React frontend.

Verify:

`frontend → API → PostgreSQL`

### 3. Early Azure deployment

Deploy the minimal application before building the full product.

Set up the initial Azure infrastructure, Bicep and CI/CD deployment flow.

### 4. Authentication and authorization

Add Entra External ID, local users, customer/admin roles and protected frontend/backend access.

### 5. Core customer journey

Implement:

`meals → cart → pickup → checkout → order → order history`

### 6. Admin workflow

Implement the minimal operational interface for:

* meals
* availability
* pickup locations
* orders
* order status

### 7. Production hardening

Testing, validation, logging, security, health checks, error handling and observability are added continuously while features are built.

They are not postponed until the end.

### 8. Milestone 1 QA

Before Milestone 1 is considered complete:

* verify critical end-to-end flows
* verify production deployment
* verify authentication and authorization
* verify migrations
* verify logs and traces
* configure monitoring and alerts
* run smoke tests
* clean the repository
* complete documentation
* confirm the live application works

## Milestone 2 — AI application layer

Milestone 2 starts only after Milestone 1 is stable.

Planned order:

1. model integration and AI foundation
2. backend tool/function calling
3. RAG for unstructured knowledge
4. multi-step agent workflow
5. AI evals
6. AI tracing and observability
7. AI-specific security and failure handling
8. final QA

MCP and multi-agent architecture are not planned requirements and should only be added if a real architectural need appears.

## Development principle

Build in small vertical slices.

The preferred workflow is:

`plan → implement → test → review → next task`

Avoid building the entire system locally before validating deployment and production infrastructure.
