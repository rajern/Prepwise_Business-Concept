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

Customer UI defaults to Norwegian with an explicit English switch; admin remains English.
The cart is a navigation-controlled drawer backed by authoritative API state. The floating
chat is visible to guests but sending requires authentication. Tab-scoped conversation
history is untrusted context; assistant mutations refresh cart/order state even after failure.

Recipe illustrations are versioned WebP assets hosted by the frontend. Customer catalogue
responses resolve frontend-relative paths only for known unchanged ingredient sets without
writing to the database. Authored image URLs take precedence, admin responses expose the
stored field, and changed/unknown recipes retain a placeholder. Cards/details disclose
AI-generated illustrations in both languages; images are not evidence of nutrition/allergen
safety. The frontend handles missing/failed images without losing meal controls.

Next.js is intentionally not used. The application already has a separate Python backend and does not require SSR.

## Backend

* Python
* FastAPI
* REST API under `/api`
* Pydantic for validation
* SQLAlchemy 2 for database access
* Alembic for schema migrations

The backend should keep a simple separation between routes, application logic and database access without unnecessary enterprise abstractions.

## Database

PostgreSQL is the application database locally, in full-stack CI and in production.
The fast pytest suite uses SQLite fixtures for unit/API checks; these do not establish
PostgreSQL-specific behaviour.

Production uses managed PostgreSQL hosted by Neon. Azure Container Apps connects to Neon over TLS. Local development and CI use a separate local or containerised PostgreSQL instance and must not depend on Neon.

Core entities include:

* users
* meals
* ingredients
* allergens
* pickup locations
* cart items
* orders
* order items
* assistant usage events and the quota serialization lock

Ingredients and allergens should be modelled relationally rather than stored only as free text.

The shopping cart is persistent.

Cart items may belong to an owned persistent pickup group, or the legacy unassigned group.
Each named group stores its own location/date/slot. Checkout locks the user's cart, creates
one order for the selected group and consumes only that group's items. Named selections must
match the reviewed checkout; legacy assistant checkout rejects a multi-group cart rather than
choosing a group. Transaction advisory locks serialize user cart changes without granting
runtime UPDATE access to users. Empty groups can be explicitly removed only after moving items.

Customers can cancel through a confirmed website button before midnight at the beginning of
the pickup day in Europe/Oslo. Backend time/ownership checks and row locks enforce this deadline
and serialize against fulfillment. Cancelled/completed orders are terminal history; other
statuses stay upcoming even if overdue. Pickup changes after ordering require cancellation and
a new order. The demo has no payment/refund workflow.

Order creation must be transactional, and order items must preserve relevant historical values such as the price at purchase time.

Catalogue translations are authored database fields, not model-generated responses. Orders
preserve names in both languages. Backend-generated pickup options cover the next five dates
starting tomorrow in `Europe/Oslo`, with `16:00–18:00` and `18:00–20:00` windows. Validated
selections are stored as timestamps on orders and assistant confirmations.

## Authentication and authorization

Authentication uses Microsoft Entra External ID.

The React SPA uses browser-delegated authentication through MSAL and the OAuth 2.0 authorization
code flow with PKCE. Microsoft hosts the combined sign-up/sign-in and password recovery pages.

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

## Production platform

Azure-hosted application infrastructure uses:

* Azure Static Web Apps
* Azure Container Apps
* Azure Key Vault
* Azure Monitor
* Application Insights

External managed services use:

* Neon for production PostgreSQL
* GitHub Container Registry for backend container images

The architecture should use low-cost configurations appropriate for a portfolio application.

## Infrastructure as Code

Azure resources are defined with Bicep under `/infra`.

Infrastructure should be reproducible from the repository rather than depending on undocumented manual configuration in Azure Portal.

Neon is outside the scope of Bicep. Its required project, database and access configuration must be documented, but no additional infrastructure-as-code tool is introduced solely to provision Neon.

## Secrets and identity

Secrets must not be stored in source control.

Use:

* Azure Key Vault for production secrets
* Managed Identity for access to supported Azure resources such as Key Vault
* `.env` locally
* `.env.example` without real values

The Container App uses a user-assigned managed identity and a Key Vault secret reference to
receive `DATABASE_URL`. Its RBAC assignment is scoped to the runtime `database-url` secret. The
separate `database-migration-url` credential is not available to the running application.

`OPENAI_API_KEY` uses a separate Key Vault reference and secret-scoped role assignment.
The SPA receives only public API/Entra configuration, never these server credentials.

The Neon connection strings are stored as production secrets. Runtime and migration roles are
separate, and all production connections must use TLS.

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

The backend image is published to GitHub Container Registry and deployed to Azure Container Apps.

The deployment flow should apply database migrations safely to Neon and include a production health check.

## Testing

Backend:

* pytest
* unit tests for important logic
* API/integration tests
* SQLite-backed unit/API fixtures for fast behavioural checks
* offline PostgreSQL migration SQL checks (not live migration execution)
* disposable PostgreSQL quota concurrency tests, enabled with `PREPWISE_TEST_DATABASE_URL`
  in the backend CI job (optional for local pytest runs)

The backend CI job applies migrations to its disposable pgvector/PostgreSQL service before
running tests; its quota fixtures use generated schemas isolated from application tables.

Frontend:

* Vitest
* React Testing Library

End-to-end:

* Playwright for a small number of critical user and admin flows against a migrated,
  seeded PostgreSQL container

The pytest suite does not replace PostgreSQL integration coverage. Vector retrieval,
locking and concurrency need PostgreSQL-specific checks where relevant.

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

OpenTelemetry should expose database dependency spans from the application where practical. Neon remains responsible for monitoring and operating the database platform itself.

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

The selected model/low reasoning setting is unchanged. Small-catalogue search defaults to
twenty results (all twelve current meals), with explicit match/availability counts and next-page
metadata. Recipe-guarded authored categories distinguish meat (including poultry), fish and
vegetarian (including dairy/eggs); changed or unknown recipes remain unclassified. This is
declared-recipe metadata, not an allergen/medical guarantee. The LLM can retrieve broad data
and reason over preferences/constraints rather than treating dietary labels as literal words.

Successful cart mutation services commit and perform a fresh authoritative cart read. The agent
validates/reuses that read instead of spending a model turn selecting a redundant verification
tool; failed mutations still require an independently executed read. Tool/write/token limits
are unchanged. Authenticated SSE uses the same admission gate as JSON. Model text is displayed
as an unconfirmed draft, cleared on tool continuation/error, and stored as history only after
final workflow validation. Disconnect cancels the producer; bounded backpressure, transaction
cleanup and exactly-once lease release prevent a stalled socket retaining AI work indefinitely.

Example flow:

`understand request → retrieve relevant data → check constraints → use tools → return result`

Multi-agent orchestration is not part of the planned scope.

### AI safety

Read operations may run automatically when authorized.

Actions with meaningful side effects require stricter controls.

Final order creation must require explicit user confirmation.

Atomic PostgreSQL admission enforces the approved 15/10-minute/user, 45/day/user and
100/day/global quotas plus one active request per user. Bounded model output, workflow
tokens, calls, writes and elapsed time limit admitted work. Scope refusal is prompt-controlled;
authorization and consequential order confirmation are enforced by the application.
See [agent security](./docs/AGENT_SECURITY.md) for precise boundaries and remaining gaps.

### State consistency and request replay (2026-10-06, local repair)

Customer item updates carry the last observed quantity and pickup group. Group selection
updates carry a server-generated selection version. The backend compares these under the
existing owner-scoped cart lock and rejects stale writes; the browser refreshes for review
instead of silently replaying an absolute update.

UI checkout first obtains an authoritative server review of the selected scope. Its fingerprint
binds user, item IDs, quantities, bilingual names, prices, location/address and exact pickup
window. Confirmation submits that fingerprint and a user-scoped UUID key. One transaction
revalidates the reviewed state, snapshots the order and removes only the selected items.
A repeated identical key returns the existing order before validating today's date or cart;
changed input with the same key is rejected. Unassigned checkout no longer creates/moves a
group in the browser. Existing assistant order confirmation retains its exact later-message
phrase and expiry, now binding the same full snapshot.
An uncertain checkout keeps its original receipt across auth/network failures. Only an explicit
`checkout_not_created` rejection after locked key lookup proves absence and permits a fresh key;
a generic 4xx after a lost response is not treated as that proof.

Upcoming/history is a presentation classification: completed/cancelled orders and orders whose
pickup window has ended appear in history. An elapsed window does not prove collection and
does not silently change fulfillment status. The browser uses Oslo cancellation dates and
refreshes clock-dependent state on time ticks, focus and visibility changes.

Keyed assistant requests store only a canonical payload hash, owner/key, attempt fence, times
and mutation status. Before any write tool, an independent transaction records an uncertain
side effect; after success it records applied. Reusing that key cannot rerun possible writes.
This is conservative replay protection, not atomic rollback, exactly-once execution, cached
model replies or proof of user intent. A new key can still represent duplicate intent. Completed
keys are rejected; only read-only failed/expired attempts may retry with a fenced new attempt.
Quota rejection creates no new replay receipt. UI preserves failed attempts and
excludes failed/partial text from confirmed history. JSON and SSE share the same guard.

SDK output replay removes local parsed helpers while retaining actual Responses wire fields.
Regression tests use the real AsyncOpenAI client with an offline HTTP/SSE transport. Protected
browser requests silently acquire a current account-bound API token before sending; mutations
are not automatically resubmitted after HTTP failures. Request sequence/session guards prevent
late reads from replacing newer state, and a client deadline bounds waiting for chat output.

These repairs require the additive `a7b8c9d0e1f2` migration, runtime replay-table grants and the
matching frontend/API contracts. They are local only until separately authorized release gates
pass. The old checkout API/client is not a compatible recovery baseline for the new mandatory
review/CAS contract. Never downgrade populated replay receipts or improvise a database rollback.

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
