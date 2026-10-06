# Prepwise assistant security and usage limits

This document describes the implemented local code, not a claim that these changes
have been deployed or that all attacks are prevented. No live, billable model eval
was run for this round. Existing eval results describe their recorded prompt and
configuration only; they cannot certify the new prompt or its 800-token budget.

## What the assistant can do

The application owns a small Responses API loop. It does not use Agents SDK,
LangChain, LangGraph or MCP. The model receives an explicit allow-list of meal,
cart, order, pickup and curated knowledge tools. It has no shell, browser, free SQL,
arbitrary HTTP or environment-reading capability. Introducing a framework would
not replace authorization, bounded execution or checks at each side effect.

The approved scope covers Prepwise meals, nutrition, ingredients and allergens,
carts, customer orders, pickup, storage/reheating, and account/service guidance.
The prompt asks for a short refusal for unrelated questions and personalized
medical advice. This is a probabilistic text boundary: it is not a deterministic
topic classifier. A refusal still consumes the admitted request quota. Backend
capabilities remain limited even if a model answers an unrelated question.

## Enforced by code

- Entra authentication establishes the user before AI admission. Tool schemas do
  not accept a user ID; backend services use the authenticated identity.
- Tool arguments reject unknown fields, bound quantities and result sizes, and
  invoke ordinary application services with their authorization and validation.
- Order creation requires a server-issued token owned by the same customer,
  a later request with the exact confirmation phrase, an unchanged cart, a valid
  explicitly selected date/time, an unused token and an unexpired confirmation.
- Cart writes require final authoritative cart verification before a successful
  assistant reply. If a budget or timeout stops a partially completed workflow,
  earlier service commits can remain. The frontend refreshes customer state on
  both success and failure; there is no claim of transactional rollback across
  the whole agent workflow.
- Accepted requests are persisted in PostgreSQL: 15 per rolling 10 minutes per
  user, 45 per user per Oslo calendar day, and 100 globally per Oslo calendar day.
  The rolling window continues across midnight. Day boundaries use Europe/Oslo,
  including summer/winter time. Clearing browser storage does not reset quotas.
- A short singleton-row lock serializes the quota counts and insertion in the
  same transaction. Independent workers/restarts share the same database state.
  Database failure, missing migrations or unsupported production databases reject
  admission before a paid call. PostgreSQL is required in production; SQLite is
  supported only for sequential unit tests.
- One active request is permitted per user. A persisted lease blocks overlapping
  admission for the workflow deadline plus 15 seconds (normally 60 seconds).
  Completion releases the lease, including model failures; a crashed process's
  lease expires. Accepted failed/timed-out requests remain counted. Requests
  rejected by authentication, validation, quotas or the kill switch do not count.
- Quota rejection returns 429, a stable `rate_limit_exceeded` code and `Retry-After`
  in seconds. CORS exposes this header to the customer frontend so it can honor
  the real wait time. Limits may be configured lower but not above the approved ceilings.
- The workflow has at most 12 logical model rounds, 10 function-call attempts,
  6 executed writing-tool attempts, 800 generated tokens per model attempt, and a
  45-second deadline. Identical failed calls are blocked without repeating their
  application side effect. Parallel tool calls are disabled.
- A 60,000-token per-workflow allowance counts successful input/output usage and
  charges failed provider attempts conservatively. Before each provider attempt,
  a UTF-8 byte ceiling for text/schema input plus formatting headroom and the
  output cap must fit the remaining allowance. Missing usage fails closed. This
  conservative estimate can stop requests earlier than actual token usage would.
  One explicit transient-provider retry is allowed per model round; SDK automatic
  retries are disabled for Responses so failed attempts can be accounted for.
- The aggregate allowance applies to Responses generation. Knowledge searches
  additionally use bounded embedding requests (at most one 1,000-character query
  per knowledge-tool call, with the shared single-retry setting). These are bounded
  by tool count and the workflow deadline, not included in Responses token totals.
- Async timeout bounds provider calls, retries and retrieval. PostgreSQL statements
  in the workflow receive the remaining deadline and a maximum 2-second lock wait.
  No later tool starts after the deadline. This is not process isolation: OS-level
  stalls or an unresponsive database connection still require infrastructure
  timeouts/worker supervision.
- `ASSISTANT_ENABLED=false` stops new AI admission. Settings are read at process
  startup, so changing the switch requires a restart/new revision.

## Prompt-controlled behavior and remaining gaps

### Customer-experience update (2026-10-01, local implementation)

- Successful add/remove services commit and immediately read the authoritative cart. This fresh
  read is validated as CartResponse and reused for verification, instead of asking the model to
  select get_cart again. Failed writes still trigger a separate read; failed verification stops
  the workflow. No tool/write/token limit was increased. Five-item regression now uses seven
  mocked model rounds instead of nine; this is not a measured live latency/quality result.
- JSON and SSE share authentication, atomic admission and quotas. SSE text is labelled as a
  draft, never persisted as confirmed history until done, reset before a tool continuation and
  removed on errors. Neither transport automatically resubmits a possibly executed write.
  Producer cancellation, bounded queue publication and transaction cleanup release the durable
  quota lease once after work stops; a stalled client cannot retain provider work indefinitely.
- Diet metadata is authored for the unchanged declared seed recipes. Unknown/edited recipes
  remain unclassified; absence of a meat word is not evidence of vegetarian/allergen safety.
  Tool pages include explicit coverage/counts so filtered/partial results cannot legitimately
  be described as an exhaustive catalogue. Actual correct model interpretation is still
  prompt-controlled and requires an owner-approved live eval to establish reliability.
- Chat cannot cancel or reschedule orders, or silently choose a named pickup group. Those
  changes use the authenticated UI and server rules. A legacy confirmation becomes invalid
  when named-group items appear; the user must review groups in the cart.
- Existing code-only rollback is not valid for this additive schema/persisted-state update;
  do not deploy without the separately reviewed compatibility/release plan.

Explicit current-message intent, relevant-question refusal, interpreting objective
meal constraints and ignoring prompt injections are prompt-controlled. Strict tool
schemas cannot prove that a user intended a valid cart write. Cart changes do not
have a separate deterministic confirmation step. Order creation has a stronger,
server-enforced confirmation boundary. History is supplied by the client and may
be forged; only user/assistant roles, ten entries and 8,000 total characters are
accepted. It is untrusted context and cannot replace current-message confirmation.

There is no extra classifier or moderation-model call. There is no general network
or MCP approval flow because those capabilities are not exposed. Per-account
quotas do not stop mass account creation: the global cap is the cost backstop.
The local 2026-10-06 repair adds owner/key/payload-hash replay guards for keyed chat
requests. A durable pre-write marker commits before any write tool; uncertain/applied
keys cannot re-execute the workflow. Attempt fencing prevents an expired read-only
worker from starting a write after replacement. No prompts/replies are stored in the
receipt and successful replies are not cached/replayed. This conservative design
may refuse an action that ultimately did not commit: the customer must inspect state.
Legacy unkeyed callers still have no durable duplicate protection, and a new key can
repeat the same intent. The single-active lease and guard are not transaction-wide
atomicity or proof that the model interpreted the customer correctly.

UI checkout separately uses an authoritative reviewed snapshot plus a user-scoped
idempotency key; replay returns the original order without consuming later cart items.
Stale item/group edits fail comparison checks rather than overwriting newer state.
Assistant order confirmation retains its exact phrase/prior-message/expiry rules and
now binds the full reviewed location, window, bilingual names and cart content.
Actual SDK multi-round streaming payloads are tested with offline HTTP/SSE fixtures;
SDK-only parsed fields must not be sent back to the provider. This establishes wire
compatibility locally, not measured live model reliability or production deployment.

The 800-token cap includes invisible reasoning and visible tool arguments/replies.
Incomplete provider responses are rejected rather than described as success.
The selected model remains `gpt-5.6-terra`, reasoning `low`. Real model evals are
needed to establish whether 800 tokens is adequate for the chosen model and
multistep tasks; these offline tests validate enforcement, not model quality.

## Secrets, content and observability

The OpenAI key is read by the backend from a local ignored environment file or the
production Key Vault reference/managed identity. It must never be put in Vite
variables, frontend assets, tool outputs, screenshots or committed files. Source
inspection cannot prove current cloud secret settings: see `REPO_REVIEW.md` for
the separate repository audit and its limits.

Requests use `store=false`; Prepwise does not persist messages or replies. Client
history stays in the current tab and is cleared on logout. `store=false` disables
Responses application-state storage; it does not promise zero provider retention
or erase provider abuse-monitoring logs. See the provider's data controls.

Telemetry records safe model/call/token/error counts and tool names, not message
text, tool arguments or retrieved/customer output. Quota rows store user identity,
timestamps and lease status only. Old usage rows are pruned on admission once
outside the current quota windows (older than two days before today's boundary).
There is no scheduled deletion when the assistant is unused. There is no automatic
abuse detector; existing operational alerts and manual usage review remain useful.

## Good and weak patterns

| Concern | Implemented pattern | Weak alternative |
| --- | --- | --- |
| Identity | Backend establishes current user; tools use it | Model/client chooses user ID |
| Capabilities | Fixed tools call validated services | Free SQL, shell, arbitrary endpoints |
| Orders | Exact later-message confirmation validated by server | Trust `confirmed=true` from model |
| Cost | Durable, atomic quotas plus bounded workflow | Only a browser counter or prompt limit |
| Scope | Prompt refusal plus restricted real capabilities | Prompt alone controls broad privileges |
| Secrets | Server environment/Key Vault only | Key in frontend bundle or repository |
| State | Verify cart; refresh UI even after errors | Assume a narrated action succeeded |
| Evaluation | Adversarial fixtures and enforcement tests | Treat framework choice as proof of safety |

## Verification and follow-up

Offline tests cover authenticated admission, validation/history role spoofing,
rolling/daily/global quotas, Oslo midnight/DST, lease expiry/release, fail-closed
admission, output/token/loop/write limits, deadline cancellation, strict tools,
cross-user access, and exact order confirmation. Additional refusal and injection
cases are included in the eval dataset. Adding a dataset case is not executing a
live eval. Real PostgreSQL concurrency tests passed against a disposable schema:
six simultaneous requests for one user admitted exactly one; four different users
competing for the final global slot admitted exactly one (99 to 100). New sessions
remained blocked by the persisted state. Run these tests using
`PREPWISE_TEST_DATABASE_URL`; SQLite cannot establish row-lock correctness.

Before release, apply the migrations, run live selected-model evals with controlled
spend and review any new consequential capabilities. Supplier spend controls remain
an additional backstop, not a replacement for these application limits.

Sources: [OpenAI agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety),
[reasoning token limits](https://developers.openai.com/api/docs/guides/reasoning),
[provider data controls](https://developers.openai.com/api/docs/guides/your-data).
