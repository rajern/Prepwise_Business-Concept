# Milestone 1 QA and security review

Review date: 2026-09-24

This document records the evidence used to close Milestone 1. It does not contain credentials,
tokens, connection strings or raw production logs.

## Automated product verification

* Backend quality: Ruff, formatting, mypy and 59 pytest tests pass.
* Frontend quality: ESLint, TypeScript, production build and 27 Vitest tests pass.
* Critical E2E: four Playwright flows pass in CI against React, FastAPI and PostgreSQL.
* Clean database: CI applies every Alembic migration to a fresh PostgreSQL instance before E2E.
* Production smoke: frontend, API liveness, database-backed readiness, catalogue, meal detail,
  CORS, TLS and frontend security headers are checked after every deployment.
* Delivery: failed CI, E2E or smoke checks prevent the production workflow from succeeding.

## Security and configuration review

| Control | Evidence | Result |
| --- | --- | --- |
| Committed secrets | Gitleaks 8.30.0 scanned all 29 commits. The only allowlisted values are one public Entra application ID and deterministic test-only identities/tokens. | Pass |
| Dependency advisories | `pnpm audit --prod` and PyPA `pip-audit` reported no known vulnerabilities. | Pass |
| Authentication | Invalid or missing bearer tokens return 401. Entra signature, issuer, audience, tenant, version and delegated scope are validated. | Pass |
| Authorization | Every `/api/admin/*` endpoint uses the admin dependency; customer access returns 403 in API and E2E tests. Anonymous production probes return 401. | Pass |
| Test authentication isolation | The E2E adapter requires both `APP_ENV=test` and `E2E_AUTH_ENABLED=true`; enabling it with `APP_ENV=production` fails closed. Production has no E2E flag. | Pass |
| Browser boundary | Production CORS grants only the deployed frontend origin. A disallowed-origin probe receives no access-control grant. | Pass |
| Transport security | Container Apps has `allowInsecure=false`; production URLs and smoke checks require HTTPS with TLS 1.2 or newer. Neon connections force `sslmode=require`. | Pass |
| Secret storage | `DATABASE_URL` is a Key Vault secret reference. The user-assigned runtime identity has `Key Vault Secrets User` only on the `database-url` secret. The migration credential is not attached to the application. | Pass |
| Frontend hardening | Static Web Apps sets CSP, HSTS, anti-framing, MIME-sniffing, referrer and permissions headers; deployment smoke verifies the critical headers. | Pass |
| Safe logging | Application code omits headers and query values and tests cover token/database-error redaction. An aggregate scan of 1,176 production log records found zero configured sensitive patterns. | Pass |
| Operations | Health probes, Application Insights traces/dependencies, three-region availability testing and enabled availability/error/latency alerts were verified. | Pass |

Key Vault uses its public endpoint with Entra authentication and RBAC. The public endpoint is not
anonymous access: secret reads still require authorization. A private endpoint would add cost and
network complexity and is not required for this low-cost portfolio deployment.

## Final authenticated production pass

The security-header deployment and its production smoke test passed in GitHub Actions run
`35981251676`. The application owner then confirmed in production that External ID sign-in works,
the meal catalogue, cart and order history load, and **Admin → Orders** can inspect an order.

Together with the earlier live customer/admin journey checks and the current Playwright suite,
this closes T8.3, T8.4 and Milestone 1.
