# Customer experience update — 2026-10-01

Implemented, pushed and production-verified after owner approval on2026-10-01.
Starting point: clean `main`, `2ac190cd505da8db378358b63e0fcdbb06bc72c4`.
Delivery: `281c8b4ab8b91c2d22c45415823f787cc6657884`,
[successful CI/deploy/smoke workflow36851140473](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36851140473).

## Implemented behaviour

- Persistent pickup groups independently store location/date/window. Items can be moved or the
  same meal added to different groups. Each selected-group checkout creates one order atomically,
  leaves other groups intact, and validates the reviewed choices. Unassigned legacy items remain
  supported; multi-group assistant checkout requires the website, never an implicit group choice.
- Confirmed customer cancellation is allowed strictly before midnight at the beginning of the
  pickup day in Europe/Oslo, with DST-aware server checks. Cancellation/completion are terminal;
  historical quantities/prices remain. Pickup edits after checkout require cancel/new order.
- Upcoming active orders appear in a collapsible section above meals. Completed/cancelled orders
  appear at `/orders` through top navigation. Overdue active orders are not silently completed.
  Details toggle closed or switch orders without late asynchronous responses restoring old state.
- Meal details use a native accessible dialog, Escape/focus restoration and repeated-click/abort
  guards. Norwegian default, English switch, meal illustrations and disclosures remain.
- Search tools expose the full current12-meal menu within default page20, explicit total matches,
  total available, unknown diet count, next offset and has_more. Authored meat/fish/vegetarian
  categories require exact known recipe names/ingredient sets; changed recipes remain unknown.
  These reflect declared recipes, not medical/allergen certification. Text searches no longer
  discard ingredient-only matches when a broad word also appears in another meal's name.
- The existing model `gpt-5.6-terra`, low effort and15/10min/user,45/day/user,100/day/global limits
  remain. Successful cart writes commit then read the cart; that authoritative response is
  validated/reused rather than selecting an extra verification tool via the model. Failed writes
  still require a separate fresh cart read. No increased tool/write/token budgets.
- SSE uses the same authenticated admission as JSON. Text is a labelled unconfirmed draft until
  done, withdrawn on continuation/error and excluded from stored history until confirmation.
  Disconnect stops the producer/provider stream; publication is bounded, read/failed-write
  transactions end and the quota lease releases once. No automatic mutation resubmission.

## Verification

| Check | Result |
| --- | --- |
| Full backend pytest |177 passed;9 real PostgreSQL-dependent cases included, no skips |
| Backend Ruff lint/format and strict mypy |Pass |
| Frontend unit tests |54 passed, including compatible JSON recovery regression |
| Frontend ESLint, TypeScript, production build |Pass |
| Playwright customer/admin/layout/image scenarios |9 passed using isolated migrated PostgreSQL API; CI also passed |
| Desktop/mobile screenshot review |8 screens: meal dialog, grouped cart, upcoming orders, history;1280/390 widths |
| New SSE offline regressions |Auth/quota, draft reset/final confirmation, incomplete/missing usage, disconnect<=1s, bounded queue and exactly-once lease cleanup |
| Gitleaks redacted changed/new source and complete history |Pass;65 commits scanned before release push |

Initial SQLite browser checks established UX/API behaviour, not PostgreSQL evidence. The resumed
release reran browsers against migrated PostgreSQL and all9 PG backend cases without skipping.
Local helper `backend/scripts/local_ui_test_server.py`
creates a disposable SQLite test database, provisions only test identities, binds loopback and
disables AI. Production never uses the helper. Normal CI retains migrated PostgreSQL coverage.

No new billable conversational model calls were made; changed-chunk deployment embeddings were
explicitly owner-approved and the resulting14-chunk index matches local metadata. Five-item synthetic workflow uses7 model rounds
instead of9, but mock responses do not prove actual live quality or response-time improvement.
Real model evals require a fresh explicitly bounded approval; the earlier10-call approval is spent.

## Resumed release validation

On2026-10-01 the owner approved paid changed-chunk embedding calls and conditional deployment.
Docker now responds with reviewed permissions. An isolated loopback PostgreSQL container passed
all migrations and177 tests (no skipped cases). All9 Playwright scenarios passed against the
migrated PostgreSQL API;54 frontend unit tests, lint/types/build and Bicep validation pass.

The first delivery commit is a compatible JSON recovery point preserving the entire new domain,
schema, policies, frontend and safety limits. Its171 non-SSE backend tests, Docker build and
synthetic image drill pass: group checkout preserved another group, cancelled orders/history
decoded, and the new frontend's JSON fallback was exercised without provider calls. A second
commit enables only the SSE HTTP route and6 regressions. Reverting that second commit, after
fresh gates, preserves the migration/business state and does not re-index changed policies.
This is not a production rollback drill, nor a way to undo all features; domain defects require
a compatible forward repair. See `ROLLBACK.md`; never downgrade/delete business data.

Validated compatible recovery commit: `ac4cbcdbc2be79c2d3d3b2709477256a3d1adb55`.
The delivery commit281c8b4 changes only the SSE route/regressions and release evidence;
all migration, persisted-domain, runtime-grant, frontend and knowledge files remain identical.

New policy documents intentionally changed KB12->14 chunks; the existing deployment indexer
synchronized changed chunks under the owner's explicit embedding approval. Conversational
model evaluation/image generation remains unapproved; no such paid calls were made.

## Production delivery evidence

All6 required CI jobs, deployment and workflow smoke passed for the exact pushed SHA above.
Azure image is SHA-tagged281c8b4, latest/ready revision `ca-prepwise-prod--0000043`,100% latest
traffic. Read-only production confirms schema `f6a7b8c9d0e1`,12 meals,14 exact matching knowledge
source/hash/model tuples, client TLS and the restricted runtime identity separate from migrations.
All16 tables match the reviewed privileges with no grant options, including new cart_groups.
Independent public checks passed the new frontend bundle `/assets/app-yljkoTip.js`, security
headers, live/ready,12 NO/EN meals,6meat/4vegetarian/2fish categories, every image's local hash,
missing-image404,5 pickup days/2 slots, CORS/Retry-After, new group/cancel routes and unauthenticated
SSE401. No authenticated real-customer order/chat request was made; do not claim measured live
model latency/quality or a production rollback drill. Temporary local test API/container removed.

API streaming follows [official OpenAI streaming guidance](https://developers.openai.com/api/docs/guides/streaming-responses);
reducing redundant serial calls follows [latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization).
