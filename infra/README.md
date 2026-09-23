# Azure infrastructure

This directory defines the Azure-owned production infrastructure for Prepwise. The entry point
uses subscription scope so the resource group is created by Bicep rather than through an
undocumented portal step.

## Resources

The production parameter file creates:

* one resource group
* one Azure Static Web App on the Free plan
* one Azure Container Apps environment and externally reachable Container App
* one user-assigned managed identity for the Container App
* one RBAC-enabled Azure Key Vault whose secret values remain manually managed
* one secret-scoped Key Vault role assignment for the runtime identity
* one Log Analytics workspace with a low daily ingestion cap
* one workspace-based Application Insights resource

The production Static Web App uses `eastus2`. Azure currently rejects new-customer Static Web
Apps deployments in `westeurope`; the remaining Azure resources stay in `norwayeast`.

Container Apps uses consumption-based scaling from zero to one replica. The committed production
parameters use the public `ghcr.io/rajern/prepwise-api:latest` image on port `8000`. Production
deployments select an immutable commit tag; `latest` remains the Bicep fallback for later
infrastructure reconciliation.

## Prerequisites

Install Azure CLI with Bicep support, sign in, select the intended subscription and register the
resource providers once:

```powershell
az login
az account set --subscription "<subscription-id>"
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.Insights --wait
az provider register --namespace Microsoft.KeyVault --wait
az provider register --namespace Microsoft.ManagedIdentity --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.Web --wait
```

Do not recreate template-owned Azure resources manually. The existing Key Vault secrets, Neon
resources and GitHub OIDC trust are intentional external prerequisites documented below and in
[`NEON.md`](./NEON.md).

The deployment creates an RBAC role assignment on the existing `database-url` secret. The Azure
principal running this infrastructure deployment therefore needs
`Microsoft.Authorization/roleAssignments/write` at that scope. `Contributor` alone is not
sufficient. The current `gh-prepwise-prod` app registration is intentionally not used to apply
this T3.2 RBAC change.

## Validate and deploy

Run from the repository root:

```powershell
az bicep build --file infra/main.bicep
az deployment sub what-if `
  --name prepwise-prod `
  --location norwayeast `
  --template-file infra/main.bicep `
  --parameters infra/environments/prod.bicepparam
az deployment sub create `
  --name prepwise-prod `
  --location norwayeast `
  --template-file infra/main.bicep `
  --parameters infra/environments/prod.bicepparam
```

The template outputs the frontend URL, backend URL, Key Vault URI, runtime managed identity name
and principal ID, and the main resource names. It never outputs a secret value.

## Existing production prerequisites

The following values are created or configured outside Bicep:

* Neon production PostgreSQL with separate runtime and migration/owner roles
* Key Vault secrets `database-url` and `database-migration-url`
* GitHub Environment `production`
* App registration `gh-prepwise-prod` with an OIDC federated credential for
  `rajern/Prepwise-Business-Concept` and environment `production`
* GitHub environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
  `AZURE_SUBSCRIPTION_ID` and `AZURE_RESOURCE_GROUP`

No Azure client secret or database credential belongs in GitHub. The manually triggered
`Azure OIDC check` workflow only verifies OIDC login and read access to the configured resource
group; it does not deploy anything or read Key Vault secrets.

## Production delivery

`.github/workflows/deploy-production.yml` runs the required CI checks before deploying a push to
`main`. It publishes commit-tagged and `latest` backend images to GHCR, applies Alembic migrations
with `database-migration-url`, initialises demo data only when the database has no meals, deploys
the backend and frontend, and verifies health, database connectivity, catalogue access and CORS.

The workflow authenticates to Azure through OIDC. It reads the Static Web Apps deployment token
at runtime through Azure and masks it; the token is not stored in GitHub. The GHCR package must be
public so Container Apps can pull it without a PAT or registry password. The workflow verifies
anonymous image access before changing production.

## Configuration boundary

Environment-specific, non-secret values belong in `.bicepparam` files. Secrets must not be added
to Bicep files, parameter files, deployment commands or outputs. The Container App receives
`DATABASE_URL` through a Key Vault reference authenticated by its user-assigned identity. That
identity has `Key Vault Secrets User` only at the `database-url` secret scope and cannot read the
migration credential.

Neon is explicitly outside this Bicep deployment. See [`NEON.md`](./NEON.md) for that boundary.
