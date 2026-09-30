# Production assistant review — 2026-09-30

The initial review was read-only, not a penetration test or a claim that secrets cannot leak.
The subsequently owner-approved remediation is recorded separately below.

## Evidence

- Serving commit: `5f80726f58b540185d4cc800e9152f89548bb7fb`.
  Ready revision `ca-prepwise-prod--0000040`; the image repository is
  `ghcr.io/rajern/prepwise-api` and its tag equals that commit. This SHA changes only TASKS
  relative to round 1.
- Container configuration sets `APP_ENV=production`, `OPENAI_MODEL=gpt-5.6-terra`,
  and `OPENAI_REASONING_EFFORT=low`. No `E2E_AUTH_ENABLED` or `ASSISTANT_*` overrides exist.
  The matching deployed source therefore uses Entra auth (test auth disabled), assistant enabled,
  15 messages per rolling ten minutes/user, 45 per Oslo day/user, 100 per Oslo day/application,
  800 output tokens/model attempt, 60,000 aggregate Responses tokens/workflow and 45 seconds.
  This is configuration/source evidence, not 100 paid requests to exercise the global quota.
- An anonymous `POST /api/assistant/messages` returned **401** before AI admission.
- Both runtime credentials are Container App `secretRef`s pointing to Key Vault through the
  user-assigned managed identity. Its listed Azure assignments are `Key Vault Secrets User`
  on only `database-url` and `openai-api-key`; the migration secret is not attached to the app.
  This inspection does not audit all human identities, all cloud logs or provider retention.
- Database inspection used `SET TRANSACTION READ ONLY` before any data query. Credentials were
  captured only in process memory; no URL/password or raw exception message was printed/saved.
- Runtime and migration connection usernames are different. The runtime does not own either
  quota table and cannot grant their privileges, truncate them, create triggers or references.
  `assistant_usage_events` has SELECT/INSERT/UPDATE/DELETE, as required. The quota lock has those
  same four privileges; DELETE is unnecessary for its admission logic.
- Alembic is `e5f6a7b8c9d0`; there are 12 meals and 12 knowledge chunks. The index key sets,
  content hashes and `text-embedding-3-small` model match the local documents exactly.
- TLS is required explicitly by the inspecting client and `PGconn.ssl_in_use` is **true**.
  `pg_stat_ssl` reports false on the pooled database-side connection: that alone does not
  describe encryption between this client and the pooler. No plaintext-client claim is made.

## Original security finding: former runtime role was overprivileged

The live runtime login has `CREATEDB`, `CREATEROLE`, `REPLICATION` and `BYPASSRLS`, and is a member
of `neon_superuser`. `rolsuper=false` and public-schema CREATE=false do **not** make it a
least-privileged login. Separate runtime/migration usernames are insufficient on their own.

Neon's [official role documentation](https://github.com/neondatabase/website/blob/main/content/docs/manage/roles.md)
explains that roles created through its Console/API/CLI receive this administrator membership;
roles created through SQL can be granted narrowly. This matches the observed privileges but
does not establish how this particular role was originally provisioned.

The model cannot issue arbitrary SQL or access this credential through its tools. Nevertheless,
an application/credential compromise has a larger database blast radius than intended. This
finding is **not evidence of an exposed key, a compromised account or a successful attack**.

Recommended separately approved remediation:

1. Inventory required table/sequence/schema grants and default grants for future migrations.
2. Provision a dedicated SQL-created runtime login without administrative membership/attributes;
   test required services, quotas and migrations' future-table grants in an isolated environment.
3. Approve a controlled Key Vault/runtime switch with a recovery plan, then validate authenticated
   read/write workflows and verify the old privileged credential is no longer used by runtime.
4. Grant quota-lock SELECT/INSERT/UPDATE only; keep usage-event DELETE for bounded pruning.

Do not blindly revoke the live role's membership: some existing application grants may currently
be inherited, so a direct revoke could interrupt ordering/chat. The initial task was read-only;
the owner subsequently approved controlled remediation, secret switch and production delivery.

## Approved remediation status

A dedicated SQL-created `prepwise_app_runtime` login is provisioned without administrator
attributes, inherited memberships, schema CREATE, table ownership, grant options or TRUNCATE.
All effective table privileges were checked against the explicit reviewed map before switching
Key Vault. Knowledge chunks are SELECT-only; the quota lock no longer has DELETE. No business
rows changed. The migration identity/credential remains separate and unchanged.

Neon's SQL provisioning requires plaintext passwords in the protocol and does not support
pre-hashed passwords (official role documentation linked above). Initial SCRAM-verifier attempts
were rejected at commit and rolled back. Provisioning then used a new high-entropy password
only in process memory over required TLS, with SQL echo disabled and no credential-containing
exception output. No credential was written to files or passed as a CLI argument. This does
not independently certify provider-side logging/retention.

The Container App database secret reference is version-pinned to the new Key Vault version.
The previous version is retained for controlled recovery. Because the runtime identity can read
historical versions under this secret scope, the former privileged login must be disabled and
its existing sessions ended after the replacement release is verified, not left active.
Deployment/retirement outcome is recorded in TASKS; provisioning alone is not completion.

The deploy workflow now applies `prepwise_api.runtime_permissions` using the migration owner
after Alembic. No broad future-table defaults are granted: introducing an ORM table requires an
explicit reviewed map update (enforced by a test). Isolated PostgreSQL tests exercise real auth,
admin catalogue/pickup/order flows, cart, confirmation/checkout, quota and local-vector retrieval;
negative tests exercise permission denials. These are not production customer/JWT or paid AI tests.

Recovery requires an authorized migration operator to re-enable the former login if necessary,
restore the previous Key Vault version/reference, then deploy/restart and verify. This is a
credential/privilege change, so the code-only automatic rollback procedure does not apply.
One-time helpers require explicit approval flags and refuse existing-role/repeated switches.

## Repeating the database snapshot

From `backend`, using an authorized Azure CLI session:

```powershell
.venv\Scripts\python.exe scripts/verify_production_readonly.py
```

The helper reads the runtime URL and, if permitted, the migration URL into memory to compare
login identities. It connects only with the runtime credential and sets the transaction read-only.
It outputs metadata/booleans/counts, never secrets or customer records. Failures output the
exception class only. A denied check is not a reason to bypass access controls.
Exit code zero means the inspection completed, not that the security review passed;
the privilege findings in the returned metadata must still be evaluated.

For rollback no-op gates and remaining unattended limitations, see [ROLLBACK.md](ROLLBACK.md).
Live model behavior is assessed separately using synthetic SQLite data, not this production DB;
see [AI_EVAL_ROUND2.md](AI_EVAL_ROUND2.md).
