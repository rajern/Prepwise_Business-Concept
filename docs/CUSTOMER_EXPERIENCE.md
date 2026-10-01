# Customer experience update — 2026-10-01

Implemented after owner approval; resumed release validation is complete, **delivery pending**.
Starting point: clean `main`, `2ac190cd505da8db378358b63e0fcdbb06bc72c4`.

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
| Full backend pytest |168 passed;9 PostgreSQL-dependent tests skipped |
| Backend Ruff lint/format and strict mypy |Pass |
| Frontend unit tests |53 passed |
| Frontend ESLint, TypeScript, production build |Pass |
| Playwright customer/admin/layout/image scenarios |9 passed using isolated SQLite API |
| Desktop/mobile screenshot review |8 screens: meal dialog, grouped cart, upcoming orders, history;1280/390 widths |
| New SSE offline regressions |Auth/quota, draft reset/final confirmation, incomplete/missing usage, disconnect<=1s, bounded queue and exactly-once lease cleanup |
| Gitleaks redacted changed/new source and complete history |Pass;63 commits scanned |

Browser checks establish UX/API behaviour, **not** PostgreSQL migrations, transaction advisory
locks, races, runtime grants or pgvector. Local helper `backend/scripts/local_ui_test_server.py`
creates a disposable SQLite test database, provisions only test identities, binds loopback and
disables AI. Production never uses the helper. Normal CI retains migrated PostgreSQL coverage.

No new billable model/embedding calls were made. Five-item synthetic workflow uses7 model rounds
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

New policy documents intentionally change KB12->14 chunks; the existing deployment indexer may
now synchronize changed chunks under the owner's explicit embedding approval. Conversational
model evaluation/image generation remains unapproved; no such paid calls were made.

Then follow existing CI/deploy for the exact pushed SHA, including public smoke and fresh runtime
grant/knowledge-state verification. Production is unchanged by this work.

API streaming follows [official OpenAI streaming guidance](https://developers.openai.com/api/docs/guides/streaming-responses);
reducing redundant serial calls follows [latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization).
