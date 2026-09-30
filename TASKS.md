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

## Active automation queue

This queue, not the historical milestone checklists below, controls unattended work.
Only tasks marked **Ready** or an unblocked **In progress** may be implemented.
Continue the active task only while it remains prioritized and its dependencies are satisfied.
When blocked, record the precise question/action needed and select the next independent Ready task.
If none exists, stop; do not invent tasks, repeat unchanged failures or reopen completed milestones.
Only the main agent updates this queue. At most two subagents may work on disjoint subtasks.
Never overwrite unrelated changes or start a second worker on an already claimed task.

**Active task:** N7 (replacement provisioned; deployment/retirement verification in progress).
**Next independent task:** N6 (approved image style; implementation may follow round 2 delivery).

| Priority / ID | Task | Status | Depends on | Completion criteria / blocker |
| --- | --- | --- | --- | --- |
| 1 / N1 | Prepare nightly queue and verify delivery access | Complete, 2026-09-30 | None | Clean baseline `6e33e57`; Git remote and push dry-run pass with approved network access; Azure login valid; existing CI/deploy successful; public frontend, health, bilingual meals, pickup windows and CORS checked. Scheduler and unattended permission limitations are documented below. |
| 2 / N2 | Document and validate a code-only rollback runbook | Complete, 2026-09-30 | N1 | [ROLLBACK.md](docs/ROLLBACK.md) records exact baseline `5f80726`, fresh no-op preflight, ordinary revert/redeploy, partial-deploy handling and fail-closed stops. Commands validated read-only; no actual rollback/drill or automatic controller enabled. |
| 3 / N3 | Verify production assistant runtime grants/configuration | Review complete; security finding open in N7 | N1 | [Production review](docs/PRODUCTION_AI_REVIEW.md): approved limits/auth, anonymous 401, scoped Key Vault bindings, TLS and migrations verified read-only. Runtime has needed quota DML but also `neon_superuser` and broad administrative attributes; least privilege is NOT satisfied. No production permissions/data changed. |
| 3a / N7 | Remediate overprivileged production database runtime role | In progress, owner-approved 2026-09-30 | N3 | Dedicated restricted SQL-created login provisioned, exact grants and TLS checked; Key Vault/reference switched. Deployment and retiring the former privileged login remain. Owner approved controlled switch, recovery and commit/push/deploy. No blind inherited-grant revocation or business-row changes. |
| 4 / N4 | Evaluate the selected model with the new 800-token cap | Complete bounded smoke, 2026-09-30 | N3 review | Owner approved max 10 attempts/USD 1. Exactly 10 calls, five synthetic isolated cases passed; estimated USD 0.041908, conservative reservation USD 0.353880. No production data or embeddings. Incomplete handling tested offline; no incomplete live response. [Evidence](docs/AI_EVAL_ROUND2.md). This approval is exhausted; no paid rerun/full eval without new approval. |
| 5 / N5 | Approve one meal-image sample | Complete, owner-approved 2026-09-30 | None | Owner approved [chicken-teriyaki-v1.png](docs/image-samples/chicken-teriyaki-v1.png): realistic photo, natural light and neutral background. Reuse this sample in the final set. [Prompt and caveats](docs/image-samples/README.md). |
| 6 / N6 | Generate and integrate the complete meal-image set | Ready after N7 delivery | N5, N7 delivery | Generate the remaining 11 matching meal images with the built-in image tool, reuse the sample, integrate and verify mobile/desktop. Use illustrative AI-image disclosure. No additional paid model evals or external image API fallback without separate approval. |

### Round 2 delivery record — 2026-09-30

- Rollback procedure and read-only production review completed; runtime privilege remediation
  needs separate owner approval. Existing nightly runs must not alter roles/secrets or repeat
  the exhausted live evaluation/image generation while the queue is blocked.
- Live selected-model smoke: five cases passed using all ten approved model attempts; new
  bounded runner preserves an ignored write-ahead journal and refuses accidental reruns.
- One meal-image sample generated with the built-in tool and saved for owner review; no
  catalogue/image URL changes, full image set, production mutations, commit or push in round 2.
- Final local verification: 144 backend tests passed, four PostgreSQL integration tests skipped
  (not rerun this round), Ruff lint/format and strict mypy passed. Changed/new text files passed
  a redacted Gitleaks scan. Rollback PowerShell/Bash syntax and equivalent public production
  probes passed; the local Bash smoke invocation lacks jq and is not claimed as a full pass.
  No production authenticated customer session or full live RAG/eval suite was used by this round.

### Approved round 2 closure / production delivery

- Owner approved the sample, controlled DB-role switch and commit/push/deploy on 2026-09-30.
- Provisioned the new SQL-created runtime login and exact grant map; read-only live inspection
  verifies no administrative attributes/membership/schema CREATE or grant options, with TLS.
  New Key Vault version/reference is in place; the former login remains available until the
  replacement release is verified, then must be retired to prevent historical-version access.
- Added repeatable deployment-time grant application through the migration owner, explicit
  coverage for every ORM table, positive/negative isolated PostgreSQL service tests and operator
  helpers that never emit credentials. Migration secrets and business rows were not changed.
- Fixed a frontend cooldown race: Retry-After now updates the countdown and deadline together.
- Pre-release verification: 150 backend tests passed with all six PostgreSQL integration tests;
  the additional grant-map completeness test passed separately (151 total). Ruff/format/full
  strict mypy passed. Frontend lint/types/build and all 36 tests passed after the cooldown fix.
- Release SHA, CI/deploy and final login retirement will be recorded after verification.

### Nightly execution and release rules

- The approved schedule is a daily follow-up in this chat at **01:00 Europe/Oslo**.
  The computer must remain awake, the desktop app running, and the project available locally.
  Automation `nattarbeid-prepwise` is **ACTIVE**, attached to this chat; creation and view confirmed.
- Run one bounded approved task batch, test it, and update status/evidence/remaining questions.
  Stop when the eligible queue is empty or when access requires human action.
- Commit/push authorization covers only the automation's own verified changes. Never stage all
  dirty files blindly, force-push, reset user work or change branch protections.
- Existing `push main -> required CI -> production deployment -> smoke checks` is the delivery path.
  Wait for the exact pushed SHA; report CI success, deploy success and public checks separately.
  Code-only automatic rollback requires the completed N2 runbook and a known-good baseline.
- Do not change secrets, perform destructive migrations or launch paid external API/image calls
  without separate approval. A deployment can index changed knowledge documents with paid
  embeddings: do not push a release that would trigger unapproved new AI work.
- Use the current permission boundary; no unattended Full Access escalation or security bypass.
  Read/write testing and network commands previously needed reviewed escalation. A successful
  interactive dry-run does not prove that an unattended run has the same permissions.
  If a scheduled command is denied, document it and stop/choose an independent permitted task.
- Report meaningful completion, a new actionable blocker or failure; remain quiet when state
  is unchanged and no approved work is available. Do not keep retrying an identical blocker.

### Setup evidence (2026-09-30)

The owner has already pushed round 1 as `6e33e579ee6d55be11555d26951f91d1f4702cfd`.
[Production workflow 36693508361](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36693508361)
completed successfully. This setup did not push/deploy additional application changes.
Non-mutating production probes passed for frontend/title, live/ready, 12 meals in both languages
with translated names, five pickup dates/two windows, allowed frontend CORS and exposed Retry-After.
The production revision observed was `ca-prepwise-prod--0000039`.
These public probes do not establish authenticated assistant privileges or live model quality.
GitHub CLI is not on PATH; public Actions REST status is readable, and Git uses existing credentials.
Branch protection/environment approval details and unattended Git/network access remain unproven.
The controlled setup run also passed frontend lint and all 36 frontend unit tests. Git push was
dry-run only. Production probes and Azure inspection were read-only; no paid AI calls were made.

---

# Milestone 1 — Production application

**Status:** Complete — production verified 2026-09-24

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

**Status:** Complete

**Acceptance criteria:**

* new users default to `customer`
* admin role can be assigned explicitly
* customer cannot call admin endpoints
* authorization is enforced in backend
* authorization tests exist

---

## 5. Customer product

### T5.1 — Meal catalogue

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

**Acceptance criteria:**

* active pickup locations come from PostgreSQL
* customer selects a location during checkout
* invalid/inactive location is rejected server-side

---

### T5.5 — Order creation

**Status:** Complete — production verified

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

**Status:** Complete — production verified

**Acceptance criteria:**

* user sees only their own orders
* order details show items, totals, pickup location and status
* unauthorized access to another user's order is blocked

---

## 6. Admin product

### T6.1 — Admin shell

**Status:** Complete — production verified

Create protected `/admin` routes and simple navigation.

**Acceptance criteria:**

* admin can access interface
* customer cannot access usable admin functionality
* backend remains the authoritative authorization layer

---

### T6.2 — Meal administration

**Status:** Complete — production verified

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

**Status:** Complete — production verified

Allow admin to:

* create/edit pickup locations
* activate/deactivate locations

**Acceptance criteria:**

* inactive locations cannot be selected for new orders

---

### T6.4 — Order administration

**Status:** Complete — production verified

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

**Status:** Complete

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

**Status:** Complete

Implement:

* `/health/live`
* `/health/ready`

**Acceptance criteria:**

* liveness verifies application process
* readiness checks critical dependencies such as PostgreSQL
* Azure Container Apps uses appropriate probes

---

### T7.3 — Error handling and validation

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete

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

**Status:** Complete — production verified

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

**Status:** Complete — production verified 2026-09-27

## 9. AI foundation

### T9.1 — Add model integration

**Status:** Complete — production verified

Create the backend foundation for the AI assistant.

**Acceptance criteria:**

* authenticated customer can send a message
* model credentials use existing secrets infrastructure
* model errors and timeouts are handled
* calls can be traced

---

### T9.2 — Define AI tool layer

**Status:** Complete — production verified

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

**Status:** Complete — production verified

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

**Status:** Complete

Add a small set of unstructured documents covering areas such as:

* service FAQ
* pickup rules
* storage guidance
* reheating guidance
* general service information

Do not duplicate structured meal/order data into the knowledge base.

---

### T10.2 — Implement retrieval

**Status:** Complete — production verified

Prefer PostgreSQL + `pgvector` if it meets the requirements.

**Acceptance criteria:**

* documents are chunked/indexed
* relevant passages can be retrieved
* source metadata is preserved
* retrieval can be evaluated independently

---

### T10.3 — Integrate RAG into assistant

**Status:** Complete — production verified

**Acceptance criteria:**

* assistant uses retrieval for relevant unstructured questions
* structured application questions continue to use tools
* responses remain grounded in retrieved material

---

## 11. Agent workflow

### T11.1 — Implement controlled multi-step workflow

**Status:** Complete — production verified

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

**Status:** Complete — production verified

Classify tools as read or write operations.

**Acceptance criteria:**

* unauthorized writes are impossible
* meaningful side effects are explicit
* final order creation requires explicit user confirmation
* model cannot bypass normal application validation

---

## 12. AI evals

### T12.1 — Create evaluation dataset

**Status:** Complete — production verified

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

**Status:** Complete — production verified

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

**Status:** Complete — production verified

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

**Status:** Complete — production verified 2026-09-27

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

Final verification passed with 32/32 live AI eval cases, a 0.997 mean score, all CI and critical
E2E jobs, production smoke tests, authenticated write-safeguard checks, and complete production
traces for structured writes and RAG.

**Milestone 2 is complete when the AI assistant works reliably on top of the production application and its behaviour can be tested and observed.**

---

# Post-Milestone 2 — customer experience and usage controls

**Status:** Round 1 implemented and verified locally; subsequently deployed by the owner,
2026-09-30. Public production checks passed; authenticated AI verification remains open.

**Delivery update, 2026-09-30:** Subsequently pushed/deployed by the owner as `6e33e57`;
the production workflow and the non-mutating public checks above passed. Authenticated AI runtime
verification and new live model evals remain separate open tasks (N3/N4).

- Repository/configuration audit and targeted cleanup: completed locally; see
  [review evidence and live checks still outstanding](./docs/REPO_REVIEW.md).
- Implemented Norwegian-default customer UI and English switch, including persisted meal translations.
- Implemented cart side panel, feedback, quantity badge and refresh after assistant actions.
- Implemented validated pickup date/window selection: tomorrow through the next five calendar days,
  all weekdays, `16:00–18:00` or `18:00–20:00`, in `Europe/Oslo`.
- Implemented floating authenticated chat with current-tab history and guest sign-in prompt.
- Implemented backend AI usage limits: 15/10 minutes/user, 45/day/user, 100/day/application, one active
  request/user; bounded workflow and Prepwise-only scope. See [agent security](./docs/AGENT_SECURITY.md).
- Implemented bilingual portfolio footer with approved name, LinkedIn, email and verified source link.
- Remediated the three installed backend dependency audit findings; fresh local audit is clean.
- Local verification passed: 135 backend tests (including two PostgreSQL quota race tests and
  two PostgreSQL order/confirmation tests), 36 frontend tests and six Chromium E2E tests.
  Backend formatting/lint/strict types, frontend lint/types/production build, Docker build
  and Bicep compilation passed. Mobile chat/cart layout was also inspected.
- Live selected-model evals and production configuration/grants still need fresh verification.
  No paid model calls, deployment or commit were performed in this round.

Later rounds retain the meal-image style approval, full image set, production validation and
any follow-up fixes. Historical milestone verification above applies to the previous release.

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
