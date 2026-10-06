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
Only the main agent updates this queue. At most two subagents may work on disjoint unattended subtasks.
The owner explicitly approved three disjoint workers for the interactive architecture-repair
batch below; this does not expand the nightly worker limit or authorize deployment.
Never overwrite unrelated changes or start a second worker on an already claimed task.

**Active task:** AR5 — owner-approved release validation and deployment, 2026-10-06.
**Next independent task:** None Ready. N8 remains administrator-only. Do not reopen historical completed tasks.
Historical P1–P4 delivery: two workers completed order backend / customer frontend; main completed
assistant/catalogue/integration. Baseline worktree was clean at `2ac190c` on main; delivery is
`281c8b4` with compatible JSON recovery point `ac4cbcd`.
Legacy-role cleanup N8 is separate from this batch. Owner reported rotating its password;
do not claim the role was disabled or retry administrator-only operations.

| Priority / ID | Task | Status | Depends on | Completion criteria / blocker |
| --- | --- | --- | --- | --- |
| 0 / AR1 | SDK replay and safe chat-request replay | Complete locally, 2026-10-06 | Owner-approved audit fixes | Real AsyncOpenAI/offline HTTP-SSE continuation; SDK parsed fields removed; owner/key/hash receipts, pre-write marker and fenced retries; correlated JSON/SSE outcomes; quota rejection creates no receipt. |
| 0 / AR2 | Reviewed checkout and cart concurrency | Complete locally, 2026-10-06 | AR3 API integration | Mandatory item/group CAS; authoritative reviewed snapshot, keyed repeat-safe checkout and explicit no-order rejection proof; atomic selected scope; same full snapshot in chat confirmation; PG concurrency regressions pass. |
| 0 / AR3 | Customer synchronization, time classification and token lifecycle | Complete locally, 2026-10-06 | AR1/AR2 agreed API contracts | History by pickup-window end without false completion; stale-response/draft/clock guards; safe checkout/chat retry receipts; account-bound silent tokens and bounded waits; 75 frontend and 9 browser tests pass. |
| 0 / AR4 | Integrate, verify and document architecture repairs | Complete locally, 2026-10-06 | AR1–AR3 | Migration/grants/model integration; 220 backend tests including15 real PG cases plus grant-plan metadata check, lint/format/mypy, frontend lint/types/build and redacted scans pass. No commit/push/deploy, production role/secret change or paid call. |
| 0 / AR5 | Validate and deliver architecture-repair release | In progress: owner approved release, 2026-10-06 | AR1–AR4 | Matching migration/runtime grants/frontend/API; compatible JSON recovery retaining review/CAS/replay guards; approved changed-chunk KB indexing; fresh CI/deploy/exact-SHA production checks. Old rollback targets remain unsafe. |
| 0a / P1 | Persistent multi-day cart groups and deadline-based cancellation | Complete, deployed2026-10-01 | None | Independent persisted pickup selections, selected-group transactional checkout, others preserved; button cancellation before pickup-day midnight Europe/Oslo; ownership, terminal status, DST and real PG concurrency/migration/runtime-grant checks pass. |
| 0b / P2 | Customer cart/order/detail UX | Complete, deployed2026-10-01 | P1 API contract | Editable groups, active orders above meals, terminal history navigation, close/switch details with stale guards, accessible meal dialog; bilingual/mobile unit and migrated-PG browser checks pass. |
| 0c / P3 | Assistant search quality and latency | Complete, deployed2026-10-01; no live quality/latency claim | P1 integration contract | Model/low effort/quotas unchanged; all12 menu items fit default page20 with counts; guarded recipe categories/unknowns, non-narrowing ingredient search, committed authoritative cart-read reuse; SSE drafts/final/error/disconnect/backpressure regressions pass. Only owner-approved changed-chunk embedding work, no new conversational model evaluation. |
| 0d / P4 | Production release preflight and delivery | Complete, production verified2026-10-01 | P1, P2, P3 | All177 backend/54 frontend/9 migrated-PG browser checks pass; compatible JSON recovery validated. Exact release281c8b4 CI/deploy/smoke successful, revision43 ready at100% traffic. Read-only production verifies headf6a7b8c9d0e1, exact16-table grants/TLS/restricted separate runtime identity,14 matching KB chunks. No pre-group rollback/DB downgrade or paid chat evaluation. |
| 1 / N1 | Prepare nightly queue and verify delivery access | Complete, 2026-09-30 | None | Clean baseline `6e33e57`; Git remote and push dry-run pass with approved network access; Azure login valid; existing CI/deploy successful; public frontend, health, bilingual meals, pickup windows and CORS checked. Scheduler and unattended permission limitations are documented below. |
| 2 / N2 | Document and validate a code-only rollback runbook | Complete, 2026-09-30 | N1 | [ROLLBACK.md](docs/ROLLBACK.md) records exact baseline `5f80726`, fresh no-op preflight, ordinary revert/redeploy, partial-deploy handling and fail-closed stops. Commands validated read-only; no actual rollback/drill or automatic controller enabled. |
| 3 / N3 | Verify production assistant runtime grants/configuration | Complete review and replacement verification | N1 | Initial overprivilege finding remediated for the serving application by N7. Approved limits/auth, Key Vault bindings, TLS, migrations and exact replacement privileges verified. Legacy administrator-role retirement remains N8; see [production review](docs/PRODUCTION_AI_REVIEW.md). |
| 3a / N7 | Remediate overprivileged production database runtime role | Replacement deployed and verified, 2026-09-30 | N3 | Restricted SQL-created login/grants/TLS verified; serving container confirms replacement username. Key Vault/reference switched and both historical credential versions disabled, not deleted. Exact release CI/deploy/public checks passed. No business-row changes; former DB login itself remains N8. |
| 3b / N8 | Retire former privileged database login | Blocked: Neon administrator action | N7 | Migration credential received SQLSTATE 42501 at ALTER ROLE NOLOGIN; transaction rolled back, no bypass attempted. Owner/Neon role administrator must disable/rotate the former unused privileged login and end its sessions using an authorized control-plane/operator plan. Historical KV versions are disabled and recoverable; do not re-enable them for runtime. No repeated unattended attempts. |
| 4 / N4 | Evaluate the selected model with the new 800-token cap | Complete bounded smoke, 2026-09-30 | N3 review | Owner approved max 10 attempts/USD 1. Exactly 10 calls, five synthetic isolated cases passed; estimated USD 0.041908, conservative reservation USD 0.353880. No production data or embeddings. Incomplete handling tested offline; no incomplete live response. [Evidence](docs/AI_EVAL_ROUND2.md). This approval is exhausted; no paid rerun/full eval without new approval. |
| 5 / N5 | Approve one meal-image sample | Complete, owner-approved 2026-09-30 | None | Owner approved [chicken-teriyaki-v1.png](docs/image-samples/chicken-teriyaki-v1.png): realistic photo, natural light and neutral background. Reuse this sample in the final set. [Prompt and caveats](docs/image-samples/README.md). |
| 6 / N6 | Generate and integrate the complete meal-image set | Complete, deployed/verified 2026-09-30 | N5, N7 delivery | Eleven native first-attempt images plus reused approved sample; versioned 960 × 720 WebPs, recipe-guarded presentation fallback and NO/EN AI disclosure. Full local tests, six required CI jobs, exact release deployment and public image checks pass. No additional paid model evals or external image API fallback were used. |

### Architecture repair release — 2026-10-06

- Owner explicitly approved completing release prerequisites, then commit/push/deploy.
  Approval includes changed-chunk embeddings for the revised public order/retry guidance;
  it does not include paid conversational/image evals, secret changes or database rollback.
- Fresh read-only production preflight: head `f6a7b8c9d0e1`,12 meals, exact16-table runtime
  privileges, no privileged role flags/membership/schema CREATE, client TLS. Current14 KB
  chunks become15:11 unchanged,4 changed/new,0 stale. Existing workflow performs the approved
  migration, grants and incremental indexing, not ad-hoc local production writes.
- Added ORM metadata for the existing HNSW knowledge index; freshly migrated local PostgreSQL
  now passes `alembic check` with no new operations, without dropping/rebuilding that index.
- Recovery uses a new JSON checkpoint with every review/CAS/receipt/domain/frontend guard intact,
  followed by a streaming-default-only activation commit. The built JSON image
  `sha256:f16cacdecedfeaccddb9f63b369d1470a994c5b0668a49ee9b17b591f02d1fb7`
  passed the offline migrated-PG drill in `scripts/recovery-image-drill.py`: cancelled keyed-order
  replay returns the original order, preserves other groups/newer cart, JSON fallback responds,
  and committed partial chat writes block replay. Zero provider calls; no production rollback drill.
- Compatible recovery source committed as `82498ac9cae0dc3530c2802f4072a9dbd040b41f`,
  `Guard chat retries and reviewed checkout with compatible recovery`. Streaming activation
  changes only its default, the default regression and this/runbook evidence; no schema/domain/
  frontend/KB/SDK/grant change. Both are intended to be pushed together after final checks.
- Backend222 tests and frontend75 tests pass; lint/format/strict types and frontend build pass.
  All9 browser scenarios pass against the migrated local PostgreSQL API; Docker image and
  Bicep compilation pass. Redacted Gitleaks history (66 commits) and current known source/docs/
  untracked scripts pass. Exact-SHA CI/deploy/production validation is still in progress.
  `scripts/release-readonly.py` checks safe production metadata in a read-only transaction and
  never prints credentials/customer records. The unchanged legacy login is still N8.

### Architecture repair batch — 2026-10-06 (initial local-only approval)

- Owner approved one interactive batch: main plus three non-overlapping workers. Baseline
  clean main `013b741`; serving release remains `281c8b4`. Local implementation/testing only.
- Scope: audit P1 SDK payload, partial-write/retry safety, reviewed checkout, stale cart
  updates and dated order classification; adjacent synchronization, atomic selected-scope
  checkout, token lifecycle and offline integration regressions. No new model/infrastructure.
- Agreed HTTP contracts: item PATCH requires original quantity and group; pickup group PATCH
  requires the server selection version. `/api/orders/review` returns authoritative lines,
  total/location/window and a state fingerprint; order POST requires that fingerprint plus
  an owner-scoped idempotency key. UI null-group checkout consumes only unassigned items even
  beside named groups; assistant legacy multi-group confirmation remains rejected.
- Keyed chat requests persist only payload hashes, attempt/safety state and timing metadata,
  not prompts/replies. A committed pre-write marker prevents replay after an uncertain outcome;
  retrying is not a transaction-wide rollback or a guarantee of model interpretation.
- Main owns migrations, shared model registration/grants, documentation and integration.
  Workers own assistant backend, order/cart backend, and frontend respectively.
- Final local evidence: all220 backend tests pass, with15 actual PostgreSQL quota/guard/cart/
  grant/migration cases plus the grant-plan metadata check (no skips); all75 frontend tests, lint/types/build and all9 browser
  scenarios pass. Critical real-domain flows use a freshly migrated/seeded loopback PG API;
  layout/image browser cases and the chat provider are mocked. Actual SDK HTTP/SSE continuation
  is tested with MockTransport, not a paid provider. No claim of live model quality/latency.
- Migration `a7b8c9d0e1f2` applied successfully to the disposable DB. A private-schema regression
  proves receipt/keyed-order downgrade refusal and safe empty-fixture downgrade; runtime can
  insert/update receipts but cannot delete/truncate them. This is not a production rollback drill.
- Final integration also preserves an uncertain checkout across auth/network errors; only an
  explicit `checkout_not_created` proof after locked key lookup permits a fresh purchase key.
  Locale changes during writes trigger fresh reads, and refresh timeout leaves an error instead
  of an endless loading state. Failed chat attempts retain original keys even after another turn.
- Cleanup: own loopback API and Playwright server stopped; only identity-validated
  `prepwise-architect-test-20261006` was stopped/auto-removed with its disposable test data.
  No listener remains on test ports8000/3000. Docker Desktop/cached images and all other user
  processes/data were preserved. Production remains unchanged; no paid model/embedding call.
- Redacted Gitleaks scan: all66 Git commits and current source/tests/migrations/docs (including
  untracked additions) pass; ignored local environment files were not mounted. Diff whitespace,
  backend Ruff/format/mypy and frontend lint/typecheck pass. Frontend build has a non-failing
  ~500KB chunk warning; existing dependency deprecation warnings are not treated as test failures.
- Generic `alembic check` reports only the pre-existing migration-created HNSW knowledge index
  absent from ORM index metadata (`ix_knowledge_chunks_embedding_hnsw`); no new receipt/order
  drift was detected, and dedicated real migration checks pass. Do not drop the vector index
  to silence this report. Resolve/document that parity before claiming a fully clean schema check.
- Deferred audit items: stronger deterministic cart-intent confirmation (product decision),
  async DB/resource/pagination architecture, broad admin-editor concurrency, dependency lock
  and production smoke/alert redesign. Legacy-role N8 remains administrator-only; audit verified
  `prepwise_app` still allows login. Do not alter secrets/roles or claim rotation disabled it.
- Release authorization is NOT included in this batch. Existing production stays unchanged;
  schema/client compatibility and fresh release gates must be reviewed before any later push.
  Knowledge-base order guidance remains unchanged and predates time-based history presentation;
  AR5 must reconcile the source/index and approve paid changed-chunk work before release.
  Do not index or initiate paid calls under this local implementation approval.

### Customer-experience release retry — 2026-10-01

- Delivered source `281c8b4ab8b91c2d22c45415823f787cc6657884`, commit
  `Stream assistant replies with bounded cleanup and verified recovery`, immediately after
  compatible recovery `ac4cbcdbc2be79c2d3d3b2709477256a3d1adb55`. Both pushed normally together.
  [Workflow36851140473](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36851140473)
  completed successfully: all6 required CI jobs, deploy, and production smoke passed.
- Fresh Azure inspection: desired/serving SHA281c8b4, latest/ready revision
  `ca-prepwise-prod--0000043`,100% latest traffic. Independent public smoke passed frontend
  headers/new bundle `/assets/app-yljkoTip.js`, live/ready,12 bilingual meals/categories
  (6meat/4vegetarian/2fish),12 WebPs identical to local hashes, missing-image404,5 days/2 slots,
  CORS/Retry-After, new groups/cancel OpenAPI routes and unauthenticated SSE401.
- Production READ ONLY inspection verifies `f6a7b8c9d0e1`,12 meals, all14 KB source-key/hash/model
  tuples matching local documents; exact16-table privilege map including cart_groups matches
  with no grant options. Client TLS, non-administrative/no-membership/no-schema-CREATE runtime,
  separate migration identity retained. No production authenticated customer/order test writes
  or paid conversational model calls; actual chat quality/latency needs separately approved eval.
- Changed/new-source scans and complete65-commit redacted history scan passed before push.
  Temporary loopback API stopped and ONLY the created test container/disposable volume removed.
  Docker Desktop and the locally built recovery image remain; no other user process/data cleanup.
  No remaining Ready task; N8 remains the prior owner/admin blocker, not retried or resolved here.
- Owner explicitly approved paid changed-chunk embeddings and conditional commit/push/deploy
  after successful validation. No new paid conversational model/image evaluation is authorized.
- Docker engine28.5.1 responds with reviewed access. Created only the dedicated loopback
  `prepwise-release-test-20261001` container/database; all migrations through `f6a7b8c9d0e1`
  and all177 backend tests pass, including9 actual PG quota/concurrency/runtime-grant cases.
- Compatible JSON recovery source retains the full new domain, schema, KB, frontend and guards.
  It passed171 non-SSE backend tests, lint/format/full mypy, Docker build and an image-level
  offline synthetic drill: independent groups, scoped checkout, cancelled order/history decode,
  another group's preservation, authenticated JSON response to the SSE-capable frontend.
  The new frontend JSON fallback regression passes;54 unit tests/types/lint/build and all9
  Playwright scenarios pass against migrated PostgreSQL. No provider call in these checks.
- Delivery preserved that recovery source as the first commit, then enabled only the SSE
  HTTP endpoint and its6 regressions in a second commit. An incident recovery may revert ONLY
  that second endpoint commit after fresh gates, leaving all business state/schema/policies.
  This is not a tested production rollback or permission to revert the entire feature batch.
  Domain defects require a reviewed forward repair. See [ROLLBACK.md](docs/ROLLBACK.md).
- Compatible recovery commit created locally: `ac4cbcdbc2be79c2d3d3b2709477256a3d1adb55`,
  `Add grouped pickup checkout and cancellable orders with compatible chat recovery`.
  It is not an old pre-feature baseline; streaming-only recovery retains every new business
  format and guard. At that checkpoint no push/deploy had occurred; the final endpoint commit
  subsequently passed177 tests and was delivered as recorded above.
- Fresh production preflight: remote main `2ac190c`, serving image `5a99117`, ready revision42
  with100% latest traffic; no queued production run. Runtime read-only role/TLS/least privileges
  intact, separate migration identity, current schema `e5f6a7b8c9d0`,12 meals/12 chunks.
  Expected new KB14 chunks differs intentionally; owner-approved deploy will synchronize it.

### Customer-experience batch — 2026-10-01 (initial local verification)

- Owner approved one combined batch with main agent plus two disjoint workers. Cancellation
  is UI-only, until midnight before pickup day (Oslo), never same-day; pickup changes after
  ordering require cancellation/new order. No new infrastructure/model or payment integration.
- Implemented persistent groups, independent selections, scoped checkout, terminal cancellation,
  upcoming/history navigation and race-safe closable meal/order details. Group migration adds
  schema/constraints without deleting legacy cart rows; downgrade refuses business-state loss.
- Assistant now returns all12 current meals within page20 and explicit paging/coverage metadata.
  Curated categories apply only to unchanged declared recipes; unknown recipes stay unknown.
  Broad ingredient search no longer loses matches merely because a name/description also matches.
- Successful cart tools already commit and read the authoritative cart; validate/reuse that fresh
  read rather than duplicate DB/model calls. Failed writes still need a separate fresh read.
  Five-item mocked workflow drops9->7 model rounds without increasing10-tool/6-write limits.
- SSE preserves auth/quota/budget/deadlines. Drafts reset before tools/errors and enter history
  only after done. Disconnect cancels provider work and clears the lease once; bounded publication
  prevents a stalled browser retaining a producer. Tests caught/fixed a wait_for cancellation race.
- Final backend:168 passed,9 PostgreSQL-dependent tests skipped; Ruff lint/format and strict mypy
  pass. Frontend:53 unit tests, lint, types and production build pass. All9 Playwright scenarios
  pass against a loopback disposable SQLite API (AI disabled), not migrated PostgreSQL. Eight
  desktop/mobile screenshots inspected, native dialog Escape/focus and overflow checks pass.
- Redacted Gitleaks changed/new-source scan and complete63-commit history scan pass. No secrets
  changed, paid API/embedding/image calls, production business writes, commit, push or deploy.
- Policy docs now describe the approved cancellation/group workflow; local KB has14 chunks
  versus previous12. The existing deployment indexer would make new paid embedding calls.
  P4 records this approval gate plus PostgreSQL and rollback limitations. No Ready task remains.
- Details/reproduction and limitations: [customer experience evidence](docs/CUSTOMER_EXPERIENCE.md).

### Round 3 implementation — 2026-09-30

- Owner authorized round 3 after sample approval and round 2 push/deploy. Two workers generated
  disjoint sets (5 + 6), all eleven first attempts accepted. No external image API, regeneration,
  paid model evaluation or knowledge-index update was initiated.
- Reused the approved teriyaki sample. Inspected all twelve encoded images; shipped 960 × 720
  WebPs total 1,248,192 bytes (81–130 kB each), not 28 MB of source PNGs. Removed only eleven
  temporary generated source copies from the public folder; native originals remain recoverable
  at the documented paths. [Prompts, provenance and image caveats](docs/image-samples/README.md).
- Published image paths are derived read-only for known unchanged ingredient sets. Authored
  image URLs and admin fields are preserved; unknown/changed recipes retain the placeholder.
  No DB migration, production catalogue reseed/backfill or business-data write is required.
- Responsive 4:3 cards/details have NO/EN illustrative AI disclosure and alternative text,
  lazy card/eager detail loading and accessible failure placeholders. SWA excludes `/images/*`
  from HTML fallback. The production smoke script checks returned image paths/content/size
  and a real missing-asset 404; the local Vite fallback is intentionally not used as SWA evidence.
- Pre-release backend: all 153 tests passed with six live local PostgreSQL cases; image/config
  checks passed separately after the final test-only adjustment. Ruff lint/format/full mypy pass.
  Complete-history scan (61 commits), new/changed source scans and smoke-shell syntax pass.
- Fresh read-only production preflight: TLS, restricted runtime attributes/grants and separate
  migration identity verified; knowledge metadata matches all 12 local chunks/model exactly.
  No knowledge document, migration, role or secret changes in this release. N8 remains blocked
  on the authorized Neon administrator, not retried or described as resolved.
- Final frontend lint/types/build and all 41 unit tests passed. All seven real local browser
  tests passed, including every image at desktop/mobile widths, bilingual disclosure/details,
  checkout/admin authorization and assistant-cart refresh. Inspected desktop/mobile screenshots.
  Exact release CI/deploy/public evidence recorded below.
- Pushed `5a9911768056f81705de81606237b4db8687df4f`, commit
  `Add bilingual illustrated meal catalogue and image delivery checks`.
  [Workflow 36707418377](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36707418377)
  completed successfully: all six required CI jobs, production deploy and enhanced image smoke.
  Azure latest/ready revision `ca-prepwise-prod--0000042` serves that exact SHA-tagged image.
- Final public checks: frontend 200, live/ready ok, 12 translated meals with identical per-meal
  image URLs in NO/EN, all 12 served as image/webp and SHA-256 identical to verified local assets,
  missing illustration 404, five pickup days with two windows each. No authenticated real-customer
  production order/assistant request was made. Local test API/database stopped after tests.
- Source/provenance and architecture documentation updated; no remaining eligible queue task.
  Unattended work must now stop quietly unless N8 receives the missing authorized administrator
  action or the owner adds a newly approved task. Do not regenerate images/repeat exhausted evals.

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
- Pushed release `5f1daed66f07906390978e31509a0b7829821b45`, commit message
  `Harden runtime database access and complete round 2 verification`.
  [Workflow 36702959276](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36702959276)
  completed successfully: all six required CI jobs, deployment and production smoke tests.
  Ready revision `ca-prepwise-prod--0000041` serves the SHA-tagged image. Read-only Azure exec
  confirms the container's configured database username is the restricted replacement role.
  Final frontend/live/ready, 12 bilingual meals and five pickup days/two windows passed.
- Former-login NOLOGIN was denied (42501), recorded as N8, not bypassed or claimed complete.
  Disabled both older KV versions while leaving the active replacement enabled; ready remains ok.
  Those versions were not deleted and an authorized operator can recover them. Local test PG
  was stopped after verification. No extra paid model calls were made.

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
