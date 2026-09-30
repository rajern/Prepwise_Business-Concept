# Repository and configuration review

Reviewed on 2026-09-30 for the first post-Milestone 2 implementation round.
The starting checkout was clean at `9396a1d`. This review distinguishes checks on repository
content from production settings that were not inspected.

## Verified locally

- Gitleaks 8.30.0 was downloaded from its official release and matched the published SHA-256
  checksum. `gitleaks git --redact --log-opts='--all'` scanned all 57 reachable commits:
  no leaks detected under the repository rules.
- A separate redacted Gitleaks directory scan of tracked working-tree files also detected
  no leaks. Ignored local credentials and generated dependencies were excluded.
- A follow-up scan included all tracked **and new non-ignored source/documentation files**
  after the final implementation work and CI changes (~808 KB), again with no detected leaks.
  A final re-scan of all 57 reachable commits also passed.
- `.env`, `.env.*` (except templates), virtual environments, frontend dependencies,
  build outputs and test artifacts are ignored. The local root `.env` is ignored.
  No `.env`, private-key or credential-file paths were tracked or found in the checked history.
- Environment templates contain public configuration, empty OpenAI credentials and
  explicitly local `change-me` database examples. Public Entra tenant/client IDs and
  delegated scopes are identifiers, not passwords or API keys.
- Frontend configuration contains public API and Entra values. The OpenAI key is loaded
  by backend settings as `SecretStr`, not exposed through frontend environment variables.
- Bicep supplies `DATABASE_URL` and `OPENAI_API_KEY` using Key Vault secret references and
  a managed identity. Role assignments target the two runtime secrets; the separate
  migration credential is not included in those assignments.
- Deployment uses Azure OIDC and a short-lived GitHub registry token. Secrets fetched
  during migrations/indexing/deployment are masked before further workflow use. Bicep
  outputs contain no secret values. The workflow does not enable shell tracing.
- CI scans complete Git history with redaction before production deployment proceeds.
  The Gitleaks allowlist is narrowly scoped to public identifiers and deterministic tests.
- Entra access tokens are validated for RS256 signature, issuer, audience, expiry,
  tenant, version and delegated scope. Backend admin authorization uses the stored role.
  Deterministic E2E identities are restricted to `APP_ENV=test`.
- The focused auth, database configuration, error handling and health test subset passed:
  **22 tests**, with one third-party AnyIO deprecation warning. `git diff --check` passed.
- Final integrated round-1 verification passed **135 backend tests**, including **four live
  PostgreSQL tests**, **36 frontend tests**, and **six browser E2E tests**. Frontend lint,
  type checking and production build, backend quality checks, Docker build and Bicep compilation
  also passed. These are local results; no deployment or live paid model eval was performed.
- Structured logging selects safe metadata and excludes exception messages. Telemetry
  tests check that credentials and sensitive request/error details are not returned or logged.

A clean secret scan means no matches were found within that scan's rules and scope.
It does not prove that no credential has ever been exposed elsewhere.

## Cleanup completed

- Added local environment/private-key exclusions to the backend Docker build context.
  The current Dockerfile already copies explicit application paths; the exclusion also
  prevents accidentally sending future credential files to a builder.
- Corrected the documented API prefix to `/api`.
- Corrected database-test claims: fast pytest fixtures use SQLite, migration tests render
  PostgreSQL SQL offline, and CI browser flows run against PostgreSQL.
- Corrected the managed-identity description to include the OpenAI runtime secret.
- Removed the unsupported blanket claim of production readiness and the brittle fixed
  backend test count. Kept the Milestone 2 eval result clearly labelled as historical.
- Added the missing local `.env` setup step to the README.
- Recorded the implemented bilingual customer, pickup, cart, chat and footer behaviour;
  updated the curated FAQ/pickup policy to match the selected booking rules. The deployment
  indexing step must run before production RAG reflects these document changes.
- Corrected outdated Neon documentation and recorded the need to check runtime privileges
  on newly migrated quota tables.
- Enabled a disposable PostgreSQL service in the backend CI job, applied migrations before
  pytest, and supplied `PREPWISE_TEST_DATABASE_URL` so concurrency tests no longer skip in CI.
- Forwarded all seven new assistant settings through Docker Compose, including the kill switch.
  `docker compose --env-file .env.example config --quiet` passed; captured configuration checks
  also verified a disabled switch and lower global limit without printing resolved credentials.

No user files, Git history or existing milestone records were deleted.

## Dependency audit

Initial read-only advisory checks ran on 2026-09-30 with registry access. Findings were then
remediated with targeted package and build-configuration changes, described below.

- `pnpm audit --prod` completed successfully: no known vulnerabilities reported for the
  locked frontend production dependency tree. Development/build dependencies are outside
  that command's scope.
- `python -m pip_audit --progress-spinner off --timeout 15` using backend `.venv` reported
  vulnerabilities in **three installed packages**. Its 21 advisory rows contain repeated IDs,
  so they must not be interpreted as 21 distinct vulnerabilities.

| Installed package | Version | Audit result | Scope |
| --- | --- | --- | --- |
| oauthlib | 3.3.1 | CVE-2026-49265; reported fix 4.0.0 | Runtime transitive dependency of Azure telemetry |
| pip | 24.0 | Multiple advisory IDs; reported fixes up to 26.2.0 | Local environment/package installation tool |
| setuptools | 65.5.0 | Multiple advisory IDs; reported fixes up to 83.0.0 | Local environment/build tool |

Installed metadata confirms the `oauthlib` dependency path:
`azure-monitor-opentelemetry → azure-monitor-opentelemetry-exporter → msrest → requests-oauthlib → oauthlib`.
Dependency presence is not proof that an affected code path is reachable from Prepwise requests;
the advisory still requires compatibility/exploitability review and a tested dependency update.

The editable `prepwise-api` package was skipped because it is not published on PyPI. The scan
examined the installed local environment, including development tools; it does not identify
the exact versions in the deployed Linux image. Fresh image dependency scanning is still needed.

### Targeted remediation

- Added `oauthlib>=4.0,<5.0` to runtime dependency constraints and raised the setuptools build
  requirement to `>=83,<84`.
- Docker now explicitly upgrades pip to `>=26.2,<27` and setuptools to `>=83,<84` before
  installing the application, so an older Python base-image toolchain is not silently retained.
- Updated only the three affected local packages: OAuthlib 4.0.0, pip 26.2.0 and setuptools 83.0.0.
- The [maintainer advisory](https://github.com/oauthlib/oauthlib/security/advisories/GHSA-xpv3-w29h-x7cv)
  identifies a PKCE verifier timing comparison in the OAuth authorization-server implementation.
  Prepwise delegates authorization to Entra rather than hosting that server. Direct exposure
  through Prepwise was not demonstrated.
- The [OAuthlib 4.0.0 changelog](https://raw.githubusercontent.com/oauthlib/oauthlib/v4.0.0/CHANGELOG.rst)
  includes the PKCE fix. Its documented breaking changes concern provider revocation and grant
  validation. Requests-OAuthlib 2.0.0 declares `oauthlib>=3.0.0` without an upper bound;
  installed metadata accepts version 4.
- After updating, `pip check` passed, and offline checks imported the Azure telemetry exporter
  and verified Requests-OAuthlib/MSRest client signing without an external request.
- The affected auth, telemetry, health and error-handling subset passed **24 tests** after
  the updates, with the same third-party AnyIO deprecation warning.
- A fresh backend `pip-audit` completed successfully with **no known vulnerabilities found**.
  The unpublished editable application remains outside package-advisory coverage.

The final rebuilt round-1 frontend `dist` generated on 2026-09-30 passed a separate redacted Gitleaks
scan (~566 KB). A literal-value comparison against the local configured credential values
found no matches in these build artifacts; no credential values were printed. This supplements
the pattern scan but does not replace live deployment or supply-chain checks.

## Remaining checks and limitations

- Live Azure role assignments, actual Key Vault values, Container Apps environment/revisions,
  Entra registration settings and Neon role/TLS configuration were not queried in this review.
  Repository configuration is not evidence that the live deployment exactly matches it.
- GitHub branch/environment protections, OIDC federation restrictions, organization permissions,
  registry visibility and historical workflow logs were not inspected.
- The Key Vault template allows public network access with RBAC; it does not use private endpoints.
- GitHub Actions use release tags rather than immutable action commit SHAs. Pinning to reviewed
  SHAs would strengthen supply-chain reproducibility.
- Python dependencies use version ranges and are not locked; frontend installs use a lockfile.
  The local package audit is clean after targeted remediation; the deployed image still needs
  its own dependency scan.
- SQLite pytest success alone does not verify PostgreSQL concurrency, locking, pgvector retrieval
  or migrations. The two isolated PostgreSQL quota concurrency cases passed locally in this
  round; the backend CI configuration now also enables them and migration execution.
  New GitHub workflow execution and a fresh production migration remain unverified.
- OpenAI usage limits configured outside the repository, project/key permissions and account
  billing controls were not inspected. Application-level usage controls are implemented by the
  separate AI workstream and documented in [agent security](./AGENT_SECURITY.md).
- Docker Desktop was initially unavailable, so secret scanning used the checksum-verified
  standalone binary. Subsequent round-1 Docker build and Bicep compilation passed; CI retains
  its Docker-based scanner and build checks. These local checks do not verify deployed resources.

No detected committed credential required rotation during this review. Rotate a credential if
later evidence shows it was exposed; a repository cleanup alone would not revoke it.
