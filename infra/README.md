# Azure infrastructure

This directory defines the Azure-owned production infrastructure for Prepwise. The entry point
uses subscription scope so the resource group is created by Bicep rather than through an
undocumented portal step.

## Resources

The production parameter file creates:

* one resource group
* one Azure Static Web App on the Free plan
* one Azure Container Apps environment and externally reachable Container App
* one RBAC-enabled Azure Key Vault without secrets
* one Log Analytics workspace with a low daily ingestion cap
* one workspace-based Application Insights resource

Container Apps uses consumption-based scaling from zero to one replica. The committed production
parameters deploy a public placeholder image. T3.4 replaces it with a versioned Prepwise image
from GitHub Container Registry.

## Prerequisites

Install Azure CLI with Bicep support, sign in, select the intended subscription and register the
resource providers once:

```powershell
az login
az account set --subscription "<subscription-id>"
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.Insights --wait
az provider register --namespace Microsoft.KeyVault --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.Web --wait
```

No Azure resource must be created manually before the deployment.

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

The template outputs the frontend URL, backend URL, Key Vault URI and main resource names.

## Configuration boundary

Environment-specific, non-secret values belong in `.bicepparam` files. Secrets must not be added
to Bicep files, parameter files, deployment commands or outputs. T3.2 adds managed identity,
Key Vault access and secure runtime configuration.

Neon is explicitly outside this Bicep deployment. See [`NEON.md`](./NEON.md) for that boundary.
