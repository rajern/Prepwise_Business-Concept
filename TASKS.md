# Prepwise — Tasks

## Purpose

This file is the operational implementation plan for Codex.

Work through tasks in order unless a dependency or concrete implementation issue requires a change.

For each task:

* keep changes focused
* preserve the architecture defined in `ARCHITECTURE.md`
* run relevant tests before considering the task complete
* update this file when a task is completed
* do not introduce new infrastructure or major dependencies without a clear need

---

# Milestone 1 — Production application

## 1. Repository foundation

### T1.1 — Initialise frontend and backend

**Status:** Complete

**Goal:** Create the runnable application skeleton.

**Implement:**

* React + TypeScript + Vite frontend
* FastAPI backend
* basic project structure
* dependency management
* `.gitignore`
* `.env.example`

**Acceptance criteria:**

* frontend runs locally
* backend runs locally
* backend exposes a basic health endpoint
* no secrets are committed

---

### T1.2 — Add development quality tooling

**Status:** Complete

**Implement:**

* Python linting and formatting
* Python type checking
* frontend linting
* TypeScript type checking
* pytest
* Vitest / React Testing Library

**Acceptance criteria:**

* all checks can be run locally
* initial test suites pass
* commands are documented

---

### T1.3 — Add PostgreSQL and Docker Compose

**Status:** Complete

**Implement:**

* local PostgreSQL container
* backend Dockerfile
* Docker Compose for backend + PostgreSQL
* environment-based database configuration

**Acceptance criteria:**

* backend connects to PostgreSQL
* environment can be started reproducibly
* backend container starts successfully
* no production credentials are required locally

---

## 2. Database and minimal vertical slice

### T2.1 — Create initial database models

**Status:** Complete

Create the core relational model for:

* users
* meals
* ingredients
* meal ingredients
* allergens
* meal allergens
* pickup locations
* cart items
* orders
* order items

**Acceptance criteria:**

* relationships and constraints are explicit
* monetary and nutritional values use appropriate types
* order items preserve historical purchase values
* models work with PostgreSQL

---

### T2.2 — Set up Alembic migrations

**Status:** Complete

**Acceptance criteria:**

* database can be created from migrations
* migrations can be applied from a clean database
* schema changes are not dependent on manual SQL

---

### T2.3 — Add seed data

**Status:** Complete

Create realistic development data including approximately:

* 10–15 meals
* ingredients
* allergens
* 3–4 Oslo pickup locations

**Acceptance criteria:**

* seed process is separate from migrations
* seed process is repeatable
* frontend/API has enough data for development

---

### T2.4 — Build the first frontend → API → database flow

**Status:** Complete

Expose meals through FastAPI and display them in React.

**Acceptance criteria:**

* frontend retrieves meals through the REST API
* backend retrieves them from PostgreSQL
* loading and API failure states are visible
* at least one API integration test exists

---

## 3. Early Azure deployment

### T3.1 — Define initial Azure infrastructure with Bicep

**Status:** Complete

Provision the minimum production infrastructure required for the vertical slice.

Include:

* Azure Container Apps
* Azure Static Web Apps
* Key Vault
* monitoring resources required by the architecture

**Acceptance criteria:**

* Azure infrastructure is represented in `/infra`
* required Neon configuration is documented separately and is not presented as Bicep-managed infrastructure
* Azure deployment does not depend on undocumented manual resource creation
* environment-specific values are configurable

---

### T3.2 — Configure production secrets and identity

**Status:** Complete

**Implement:**

* Key Vault
* Managed Identity where appropriate
* secure application configuration
* Neon production database and TLS connection configuration
* GitHub → Azure OIDC authentication

**Acceptance criteria:**

* production secrets are not stored in GitHub or source code
* backend can access required secrets securely
* GitHub Actions does not use a long-lived Azure credential
* production uses Neon while local development and CI remain on separate PostgreSQL instances
* manual Neon setup required outside the repository is documented

---

### T3.3 — Create initial CI pipeline

**Status:** Complete

For pull requests run:

* backend lint
* backend type checking
* backend tests
* frontend lint
* frontend type checking
* frontend tests
* frontend production build
* backend Docker build

**Acceptance criteria:**

* failing checks make the workflow fail
* CI runs automatically on pull requests

---

### T3.4 — Create initial deployment pipeline

**Status:** Complete

On merge to `main`:

* run required CI checks
* build backend image
* push image to GitHub Container Registry
* deploy backend
* deploy frontend
* apply migrations safely to Neon
* verify backend health

**Acceptance criteria:**

* minimal application is publicly deployed
* deployment is triggered from GitHub Actions
* frontend successfully calls the deployed API
* Neon PostgreSQL is used in production

---

## 4. Authentication and authorization

### T4.1 — Configure Entra External ID

**Status:** Complete

Implement customer signup and login.

**Acceptance criteria:**

* user can create an account
* user can log in and log out
* frontend obtains a valid access token
* passwords are not handled by Prepwise

---

### T4.2 — Protect the backend API

**Status:** Complete

**Implement:**

* token validation
* authenticated-user resolution
* local user creation/mapping

**Acceptance criteria:**

* protected endpoints reject unauthenticated requests
* authenticated requests resolve the correct local user
* invalid or expired tokens fail safely

---

### T4.3 — Implement customer/admin authorization

**Status:** In progress — implementation underway

**Acceptance criteria:**

* new users default to `customer`
* admin role can be assigned explicitly
* customer cannot call admin endpoints
* authorization is enforced in backend
* authorization tests exist

---

## 5. Customer product

### T5.1 — Meal catalogue

Implement:

* meal list
* availability
* basic filtering/display
* responsive customer UI

**Acceptance criteria:**

* only relevant available meals are purchasable
* required nutrition and price information is visible

---

### T5.2 — Meal details

Display:

* description
* image
* price
* calories
* protein
* carbohydrates
* fat
* ingredients
* allergens
* availability

**Acceptance criteria:**

* data comes from the backend
* missing/unavailable meals have clear states

---

### T5.3 — Persistent shopping cart

Implement:

* get cart
* add meal
* remove meal
* change quantity
* calculate totals

**Acceptance criteria:**

* cart survives refresh/login
* cart belongs to the authenticated user
* invalid quantities are rejected by backend
* unavailable meals cannot be newly added

---

### T5.4 — Pickup selection

**Acceptance criteria:**

* active pickup locations come from PostgreSQL
* customer selects a location during checkout
* invalid/inactive location is rejected server-side

---

### T5.5 — Order creation

Implement transactional checkout.

The backend must:

1. validate cart
2. validate meal availability
3. read authoritative prices
4. create order
5. create order items
6. clear appropriate cart items
7. commit atomically

**Acceptance criteria:**

* partial orders cannot be created
* frontend-supplied prices are never trusted
* order contains historical item price
* failed checkout leaves data consistent
* integration tests cover success and key failure cases

---

### T5.6 — Order history and details

**Acceptance criteria:**

* user sees only their own orders
* order details show items, totals, pickup location and status
* unauthorized access to another user's order is blocked

---

## 6. Admin product

### T6.1 — Admin shell

Create protected `/admin` routes and simple navigation.

**Acceptance criteria:**

* admin can access interface
* customer cannot access usable admin functionality
* backend remains the authoritative authorization layer

---

### T6.2 — Meal administration

Allow admin to:

* create meals
* edit meals
* change availability
* manage nutritional/product information

**Acceptance criteria:**

* changes persist to PostgreSQL
* inputs are validated
* customer catalogue reflects changes

---

### T6.3 — Pickup location administration

Allow admin to:

* create/edit pickup locations
* activate/deactivate locations

**Acceptance criteria:**

* inactive locations cannot be selected for new orders

---

### T6.4 — Order administration

Allow admin to:

* list orders
* inspect order details
* update status

Use the agreed simple lifecycle:

`received → preparing → ready for pickup → completed`

**Acceptance criteria:**

* invalid transitions are rejected if transition rules are implemented
* customer sees updated status

---

## 7. Production hardening

These requirements should also be applied continuously during earlier tasks.

### T7.1 — Structured logging

Add structured application logging.

Include:

* request/correlation ID
* request information
* exceptions
* important domain events such as order creation

**Acceptance criteria:**

* logs are useful for debugging
* secrets and access tokens are never logged
* unnecessary personal data is avoided

---

### T7.2 — Health checks

Implement:

* `/health/live`
* `/health/ready`

**Acceptance criteria:**

* liveness verifies application process
* readiness checks critical dependencies such as PostgreSQL
* Azure Container Apps uses appropriate probes

---

### T7.3 — Error handling and validation

Ensure consistent handling of:

* invalid input
* authentication failures
* authorization failures
* not-found resources
* database failures
* external-service failures

**Acceptance criteria:**

* API exposes safe and consistent errors
* internal stack traces are not leaked to users
* frontend exposes clear failure states

---

### T7.4 — OpenTelemetry and Application Insights

Instrument the backend.

**Acceptance criteria:**

* requests appear in Application Insights
* backend latency is visible
* exceptions are visible
* Neon PostgreSQL dependency activity is traceable from the application where practical
* traces can connect relevant operations through a request
* Neon platform-level monitoring remains separate from Azure application monitoring

---

### T7.5 — Production monitoring

Configure monitoring for at least:

* availability
* request volume
* response latency
* error rate

Create at least one meaningful Azure alert.

**Acceptance criteria:**

* production problems can be detected without manually inspecting the application

---

## 8. Milestone 1 verification

### T8.1 — Add critical Playwright E2E flows

Cover a small number of high-value flows:

* browse meal → add to cart
* authenticated checkout → order created
* view order history
* admin updates order status
* customer cannot perform admin operation

**Acceptance criteria:**

* critical flows pass against a realistic application environment

---

### T8.2 — Production smoke tests

After deployment verify at least:

* frontend available
* backend live
* backend ready
* database connectivity
* critical public API functionality

**Acceptance criteria:**

* smoke test runs automatically after deployment
* failed smoke test causes deployment workflow to report failure

---

### T8.3 — Security and configuration review

Verify:

* no committed secrets
* correct authorization
* production TLS
* secure environment configuration
* no sensitive data in logs
* admin endpoints protected
* Neon connections require TLS and production credentials are protected

---

### T8.4 — Milestone 1 final QA

Verify the complete customer journey:

`browse → account → cart → pickup → checkout → order history`

Verify the complete admin journey:

`admin login → manage product/order → customer sees result`

Verify:

* migrations from clean state
* tests
* CI
* CD
* observability
* alerting
* health checks
* production deployment

**Milestone 1 is complete only when the non-AI system is working live end-to-end.**

At this point Prepwise is ready to be presented on CV and GitHub.

---

# Milestone 2 — AI application layer

## 9. AI foundation

### T9.1 — Add model integration

Create the backend foundation for the AI assistant.

**Acceptance criteria:**

* authenticated customer can send a message
* model credentials use existing secrets infrastructure
* model errors and timeouts are handled
* calls can be traced

---

### T9.2 — Define AI tool layer

Expose controlled application capabilities such as:

* search meals
* get meal details
* get cart
* add to cart
* remove from cart
* get user orders
* get pickup locations

**Acceptance criteria:**

* tools call application/service logic rather than accessing PostgreSQL directly
* authenticated user context is preserved
* existing authorization and validation apply
* tool schemas are explicit

---

### T9.3 — Implement tool-calling assistant

Support questions such as:

> Find meals with at least 40 g protein and below 800 kcal.

**Acceptance criteria:**

* assistant selects appropriate tools
* structured data is retrieved from the backend
* responses are grounded in current application data
* the model does not invent unavailable meals or values

---

## 10. RAG

### T10.1 — Create knowledge base

Add a small set of unstructured documents covering areas such as:

* service FAQ
* pickup rules
* storage guidance
* reheating guidance
* general service information

Do not duplicate structured meal/order data into the knowledge base.

---

### T10.2 — Implement retrieval

Prefer PostgreSQL + `pgvector` if it meets the requirements.

**Acceptance criteria:**

* documents are chunked/indexed
* relevant passages can be retrieved
* source metadata is preserved
* retrieval can be evaluated independently

---

### T10.3 — Integrate RAG into assistant

**Acceptance criteria:**

* assistant uses retrieval for relevant unstructured questions
* structured application questions continue to use tools
* responses remain grounded in retrieved material

---

## 11. Agent workflow

### T11.1 — Implement controlled multi-step workflow

Support tasks such as:

> Find five meals with at least 40 g protein and under 800 kcal and add them to my cart.

Possible flow:

`interpret constraints → search meals → validate results → select meals → modify cart → report result`

**Acceptance criteria:**

* multiple tool calls can be coordinated
* workflow can recover from expected tool failures
* final result reflects actual backend state

---

### T11.2 — Add side-effect controls

Classify tools as read or write operations.

**Acceptance criteria:**

* unauthorized writes are impossible
* meaningful side effects are explicit
* final order creation requires explicit user confirmation
* model cannot bypass normal application validation

---

## 12. AI evals

### T12.1 — Create evaluation dataset

Include representative cases for:

* meal search
* nutritional constraints
* allergens
* cart operations
* order questions
* RAG questions
* ambiguous requests
* invalid or unsafe actions

---

### T12.2 — Implement automated AI evaluation

Evaluate at least:

* tool selection
* tool arguments
* constraint satisfaction
* retrieval relevance
* grounding
* workflow outcome
* unwanted side effects

**Acceptance criteria:**

* eval suite is repeatable
* results can be compared across model/prompt changes
* failures are inspectable

---

## 13. AI observability

### T13.1 — Trace AI workflows

Make it possible to inspect:

`user → LLM → retrieval/tool → backend/database → LLM → response`

Capture where appropriate:

* latency
* model calls
* token usage
* tool calls
* retrieval
* errors
* agent steps

**Acceptance criteria:**

* one production AI request can be followed through its major stages
* sensitive information is not unnecessarily recorded

---

## 14. Milestone 2 final QA

Verify:

* direct AI questions
* structured tool use
* RAG
* multi-step workflows
* authentication/authorization
* write-operation safeguards
* eval suite
* traces
* failure handling

**Milestone 2 is complete when the AI assistant works reliably on top of the production application and its behaviour can be tested and observed.**

---

# Deferred

Do not implement unless a concrete requirement appears:

* MCP
* multi-agent architecture
* separate vector database
* Redis
* message queues
* microservices
* Kubernetes

If one of these becomes necessary, document the reason in `DECISIONS.md` before adding it.
