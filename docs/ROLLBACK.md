# Production code-only rollback

This runbook uses the existing `main -> required CI -> production deployment -> smoke tests`
delivery path. It does not install an automatic rollback controller or change production.
It permits a new, ordinary Git revert commit only after every gate below is satisfied.
An unavailable check is a failed gate, not permission to assume safety.

## Customer groups/cancellation release and compatible recovery (2026-10-01)

The pending `f6a7b8c9d0e1` migration adds persistent cart groups and the `cancelled` order status.
The prior release would combine all cart rows at checkout and cannot decode cancelled orders.
Therefore a plain Git revert to the historical baseline is NOT a safe rollback after feature use.
The migration's downgrade deliberately refuses to discard groups or cancelled business rows;
it is not a recovery plan. Never solve compatibility by deleting orders/groups, downgrading the
database or temporarily weakening authentication/confirmation controls.

The owner authorized release validation and conditional delivery, including paid changed-chunk
embeddings, on2026-10-01. The resumed isolated PostgreSQL run passed all177 tests and migrations;
all9 browser scenarios passed against that migrated DB. No production business test writes.

Delivery uses two contiguous commits, pushed together after validation:

1. **Compatible feature recovery point:** groups/cancellation/schema/grants, current KB and
   frontend, search improvements and existing approved AI guards, with the authenticated JSON
   assistant endpoint. Frontend accepts JSON even when requesting SSE. Validated171 backend
   tests,54 frontend tests,9 migrated-PG browser scenarios and Docker build; a synthetic image
   drill proved scoped group checkout, other-group retention, cancelled-history decoding and
   authenticated JSON fallback without any provider calls. Exact SHA is recorded at delivery.
2. **SSE delivery commit:** only the assistant HTTP endpoint,6 streaming regressions and release
   evidence. Schema/grants/KB/domain/frontend/seed/dependencies are identical to point1.

For a confirmed SSE endpoint regression, fresh remote/queue/image/runtime/schema/index checks
must pass, then one ordinary revert of commit2 can restore point1's JSON route through existing
CI/deploy, without database/index rollback. Verify the diff against point1: only that route,
its tests and evidence may differ; reject any protected/schema/knowledge/domain change.
Never revert commit1 or select `5a99117` after migration/feature use. Point1 is locally validated,
not a previously serving production artifact; this is NOT a completed production rollback drill
or an automatic controller. Domain/feature defects are outside this narrow recovery and require
a reviewed compatible forward repair. Mixed/failed migration/index/deploy remains a stop and
inspect condition, not permission for blind revert. Stop after one failed recovery attempt.

The single-code-only-commit/no-op procedure below remains applicable to later eligible releases.
For this two-commit feature release only commit2 is the eligible candidate and point1 its base;
the code-only recovery itself must make no new migration, seed, role or embedding changes.

## Known public baseline (2026-09-30)

| Item | Observed value |
| --- | --- |
| Deployed commit | `5f80726f58b540185d4cc800e9152f89548bb7fb` |
| Production workflow | [36697238645](https://github.com/rajern/Prepwise_Business-Concept/actions/runs/36697238645), completed / success |
| Backend image repository | `ghcr.io/rajern/prepwise-api`; tag equals the deployed commit above |
| Latest ready revision | `ca-prepwise-prod--0000040` |
| Resource group / Container App | `rg-prepwise-prod` / `ca-prepwise-prod` |
| Frontend | `https://nice-island-080f30a0f.6.azurestaticapps.net` |
| Backend | `https://ca-prepwise-prod.ashyforest-425ce6b9.norwayeast.azurecontainerapps.io` |
| Public probes | Frontend HTTP 200/title, five security headers, live/ready `status: ok`, 12 meals/detail and frontend CORS |
| Schema/index snapshot | Alembic `e5f6a7b8c9d0`, 12 meals, 12 knowledge chunks; exact source hash/key/model match |

This commit changes only `TASKS.md` relative to round-1 commit
`6e33e579ee6d55be11555d26951f91d1f4702cfd`. Public checks establish availability,
not authenticated assistant quality, every runtime privilege, or every production configuration.
Do not select a pre-round-1 commit: round 1 changed the schema and assistant safety controls.

Before each release, record a **fresh** baseline: exact main SHA, successful workflow ID,
deployed image and ready revision, public smoke result, schema/index no-op evidence and any
owner-confirmed authenticated checks. Record safe metadata, never tokens, connection strings,
secret values, raw environment output, customer records or unfiltered runtime logs.
The historical baseline above is not automatically valid after another deployment.

## Scope and mandatory stop conditions

A candidate must be one identified, non-merge commit on `main`, immediately after the recorded
baseline. Multi-commit, merge, intervening-owner-change and unknown-history incidents require
an operator-reviewed plan; do not guess which commits to undo.

Stop and request an owner decision if any of these apply:

- Changes to Alembic revisions/configuration, ORM models, schema constraints, seed logic,
  database roles/grants, persisted-data formats or interpretation, or an external data backfill.
- Secret rotation, identity/RBAC/Entra changes, infrastructure, environment configuration,
  dependencies/build images, CI/CD configuration or release/smoke tooling changed.
- Knowledge documents, chunking/indexing logic, embedding model or indexed content changed.
- Rollback would remove authentication, authorization, confirmation or approved usage guards,
  or reintroduce a known vulnerability. Availability is not sufficient to waive security.
- Current database schema is unknown/incompatible, catalogue is empty, or knowledge index
  cannot be proven synchronized without a paid call. See the no-op checks below.
- Production changed externally since the recorded baseline, baseline itself was unhealthy,
  another deploy is queued/running, permissions are missing, or Git is dirty/diverged.
- A revert conflicts, verification fails or the replacement deployment fails. Do not try a
  second speculative revert, reset, force push, disable a protection, or downgrade the database.

File review is necessary but not sufficient: a change inside a service can alter persisted
semantics without touching a model or migration. Review the actual diff and compatibility.
Ordinary customer cart/order writes made during the release remain valid data; a code revert
does not reverse them. Never delete orders, clear quota records, expire all confirmations or
run a seed/backfill to make an old implementation appear compatible.

## Deployment side effects must be proven no-op

The existing workflow always runs, in order:

1. Build/publish a new backend image, including the mutable `latest` tag.
2. `alembic upgrade head` using the migration credential.
3. `prepwise-seed-if-empty` using the migration credential.
4. `prepwise-index-knowledge` using the migration credential and OpenAI key.
5. Deploy backend, check backend health, build/deploy frontend and run public smoke tests.

Consequently, a code-only Git diff **does not** establish a side-effect-free redeployment.
Before an unattended rollback/release, an authorized read-only inspection must establish:

- The single current Alembic revision equals the unchanged source head; the migration directory
  and `env.py` are identical to the healthy baseline. Do not run `upgrade` to inspect production.
- The existing catalogue contains meals, so unchanged `seed_database_if_empty` will not seed it.
- Knowledge documents, chunking code and model are unchanged. Compare generated source drafts
  with production rows by `(source_path, chunk_index)`, content hash and embedding model.
  The key sets must match exactly, with no missing, changed, model-mismatched or stale chunks.
  Inspect only those non-sensitive metadata fields, not source/customer text or vectors.
- No external changes occurred between this inspection and release. If concurrent privileged
  changes cannot be excluded, stop: the checks are snapshots, not a database lock.

`OpenAIEmbeddingProvider.embed([])` returns without a provider call. The indexer still opens a
transaction and commits; only the metadata checks above establish that it has nothing to insert,
update or delete. Missing/drifted content can cause paid embeddings, and stale rows can be deleted.
Do not approve those effects implicitly as part of code rollback. A new explicit authorization
or separate deployment-path change would be needed if no-op cannot be established.

## Read-only preflight commands

Run from this repository in PowerShell. These snippets neither fetch secret values nor mutate
Git/production. Use the actual selected baseline and candidate; the placeholder must be replaced
before execution. If a command returns nonzero or a response is unavailable, stop.

```powershell
$rollbackBaseline = '5f80726f58b540185d4cc800e9152f89548bb7fb'
$rollbackCandidate = '<full-bad-commit-sha>'
if ($rollbackCandidate -notmatch '^[0-9a-f]{40}$') { throw 'Select an exact candidate SHA.' }
if (git status --porcelain) { throw 'Working tree is not clean.' }
if ((git branch --show-current) -ne 'main') { throw 'Wrong branch.' }
$rollbackHead = git rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $rollbackHead -ne $rollbackCandidate) { throw 'Unexpected HEAD.' }
$rollbackRemote = git ls-remote origin refs/heads/main
if ($LASTEXITCODE -ne 0) { throw 'Remote inspection failed.' }
if (($rollbackRemote -split '\s+')[0] -ne $rollbackCandidate) { throw 'Remote main changed.' }
$rollbackParents = (git rev-list --parents -n 1 $rollbackCandidate) -split ' '
if ($LASTEXITCODE -ne 0 -or $rollbackParents.Count -ne 2 -or
    $rollbackParents[1] -ne $rollbackBaseline) { throw 'Not one linear release after baseline.' }
git diff --stat $rollbackBaseline $rollbackCandidate
git diff --name-only $rollbackBaseline $rollbackCandidate
# Review the complete diff locally without copying sensitive material into reports.
git diff $rollbackBaseline $rollbackCandidate
git diff --check $rollbackBaseline $rollbackCandidate
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed.' }
```

Check deploy status through the public GitHub API (GitHub CLI is not required). Check both
the exact candidate and the repository-wide deployment queue; filter by workflow name and
confirm no queued/in-progress deploy before starting recovery. Do not inspect raw logs/secrets.

```powershell
$rollbackRepoApi = 'https://api.github.com/repos/rajern/Prepwise_Business-Concept/actions'
$rollbackRuns = Invoke-RestMethod -Uri "$rollbackRepoApi/runs?head_sha=$rollbackCandidate&per_page=100"
$rollbackRuns.workflow_runs | Where-Object name -eq 'Deploy production' |
    Select-Object id, head_sha, status, conclusion, html_url
foreach ($rollbackRunState in @('queued', 'in_progress', 'waiting', 'requested', 'pending')) {
    $rollbackActive = Invoke-RestMethod -Uri "$rollbackRepoApi/runs?status=$rollbackRunState&per_page=100"
    if ($rollbackActive.workflow_runs | Where-Object name -eq 'Deploy production') {
        throw 'Another production deploy is active; operator coordination required.'
    }
}
az containerapp show --resource-group rg-prepwise-prod --name ca-prepwise-prod `
    --query '{revision:properties.latestReadyRevisionName,image:properties.template.containers[0].image}' `
    --output json
if ($LASTEXITCODE -ne 0) { throw 'Azure inspection failed.' }
$rollbackBackend = 'https://ca-prepwise-prod.ashyforest-425ce6b9.norwayeast.azurecontainerapps.io'
$rollbackFrontend = 'https://nice-island-080f30a0f.6.azurestaticapps.net'
Invoke-RestMethod -Uri "$rollbackBackend/health/live" -TimeoutSec 30
Invoke-RestMethod -Uri "$rollbackBackend/health/ready" -TimeoutSec 30
$rollbackPage = Invoke-WebRequest -Uri $rollbackFrontend -UseBasicParsing -TimeoutSec 30
if ($rollbackPage.StatusCode -ne 200 -or
    -not $rollbackPage.Content.Contains('<title>Prepwise</title>')) { throw 'Frontend probe failed.' }
```

The current failed candidate may have unhealthy probes: record that failure rather than using
it as baseline evidence. Verify the **recorded baseline** was healthy before that release.
Do not proceed solely because `latestReadyRevisionName` exists: it may name the previous image
while a newer revision is unhealthy. Compare desired image, revision identity, workflow steps
and live traffic evidence; unknown/mixed traffic requires operator investigation.

## Recovery through a new revert commit (mutating; not executed during validation)

Only after all gates pass and scoped push/redeploy authorization applies:

1. Keep a clean, owner-approved checkout at the exact candidate. Do not switch/reset a dirty
   checkout or reuse unowned files. Run `git revert --no-edit $rollbackCandidate` to create a
   new revert commit. A conflict is a stop condition. Use `git revert --abort` only for this
   newly started conflicted sequence, not for a pre-existing owner sequence.
2. Confirm only the intended candidate changes were reversed, all protected paths are unchanged,
   and `git diff --check` passes. Run required backend Ruff/format/mypy/pytest, frontend
   lint/typecheck/tests/build, disposable PostgreSQL/E2E tests, Docker/Bicep validation and
   redacted secret scanning as CI requires. Never run tests against Neon or customer accounts.
3. Record the new revert SHA with `git rev-parse HEAD`. Repeat remote-main and deployment-queue
   checks immediately before push. `git push --dry-run origin HEAD:main` checks routing/access;
   it does not guarantee branch protection approval, unattended permissions or deployment health.
4. Push normally with `git push origin HEAD:main`; never force. A race/non-fast-forward rejection
   is a stop condition, not an instruction to merge/rebase/revert additional owner changes.
5. Wait for the **exact revert SHA's** production workflow. Check required CI separately from
   deploy outcome. A successful CI run alone says nothing about production restoration.
6. Confirm Azure desired image uses the revert SHA, its new revision is ready and serves traffic.
   Run `scripts/smoke-production.sh FRONTEND_URL BACKEND_URL` in the supported Bash/curl/jq
   environment used by CI, then check bilingual meals, five pickup dates/two windows and exposed
   Retry-After. Use an isolated authorized test account for any authenticated flow; paid assistant
   calls need a separately approved budget and are not part of routine public smoke.
7. Update `TASKS.md` with candidate/baseline/revert SHAs, workflow IDs, public verification,
   separate authenticated checks, incident impact and any outstanding blocker. Stop after one
   recovery attempt if it fails; do not perform an automatic rollback of the rollback.

A revert restores source content, not the exact old deployment artifact: dependencies are not
fully locked, actions use release tags and the workflow rebuilds the image. CI and post-deploy
checks remain mandatory. Never recover using the floating `latest` image, manually move traffic
to an arbitrary revision or apply Bicep as a shortcut to roll back both applications.

## Partial-deployment decision table

| Last successful step / failure | Safe interpretation and action |
| --- | --- |
| Required CI / image publication fails | Serving applications may still be unchanged; confirm revision/traffic/frontend. Do not automatically revert production that never received the candidate. `latest` may nevertheless have changed after publication. |
| Migration, seed or knowledge step fails | Database/index may already have changed before the failure. Stop and inspect with authorized read-only access; never downgrade/delete/reseed. A green previous image does not undo those effects. |
| Backend deployment/health fails before frontend | Backend may be mixed/failed while frontend is old. Confirm image, ready revision and traffic. One code-only revert may redeploy both only if every no-op/compatibility gate passes. |
| Frontend deployment or final smoke fails | Backend may be new and frontend old/new/partially uploaded. Treat as mixed until checked. Revert through the same full workflow only if gates pass; do not assume SWA has an atomic paired backend rollback. |
| Schema, secret, infrastructure, dependency, knowledge or persisted semantics changed | No unattended code-only rollback. Record exact failed step and safe metadata; owner chooses a compatible forward fix or a separately planned recovery. |
| Replacement workflow fails or permissions are denied | Record current serving state and owner action needed. Stop; no bypass or repeated speculative production mutations. |

## Validation and remaining limits

On 2026-09-30 this runbook was checked against `.github/workflows/deploy-production.yml`,
reusable CI, `scripts/smoke-production.sh`, architecture, seed and knowledge-index code.
Git inspected the two baseline commits and confirmed the intervening change was TASKS-only.
Read-only GitHub/Azure/HTTP checks returned the exact successful workflow, SHA-tagged image,
ready revision and public health listed above. Git option help and PowerShell syntax were
validated without executing a revert, push, deploy, migration, seed or model call.
The two PowerShell code blocks parsed with no errors. All five deployment-queue queries returned
zero active production runs. The parallel read-only production inspection confirmed the
schema/catalogue/knowledge no-op snapshot above; this must be repeated before a future release.

`bash -n scripts/smoke-production.sh` passed with approved process permissions. Running that
script locally reached backend liveness but stopped because this Windows Bash environment
does not have `jq`. Equivalent non-mutating PowerShell probes passed all of its public checks,
including the five frontend security headers, catalogue/detail and CORS. The original smoke
script is available in GitHub Actions' Bash/curl/jq environment; local execution still requires
the missing prerequisite. Do not report the incomplete local Bash invocation as a passing run.

This is a validated procedure, **not a successful rollback drill**. End-to-end unattended Git
permissions, environment approvals, actual revert/deploy behaviour, database/index no-op gates
and authenticated smoke must still be established for each release. GitHub deployment
concurrency serializes jobs but does not lock remote main or external database/config changes.
Do not claim automatic recovery is enabled merely because this document exists.
