using '../main.bicep'

param workloadName = 'prepwise'
param environmentName = 'prod'
param primaryLocation = 'norwayeast'
param staticWebAppLocation = 'eastus2'

// Deployment uses immutable commit tags; latest is the reproducible Bicep fallback.
param backendContainerImage = 'ghcr.io/rajern/prepwise-api:latest'
param backendContainerPort = 8000
param entraTenantId = '1a782388-bf90-4ea8-af8f-bcc755f5cd7e'
param entraTenantSubdomain = 'prepwisecustomers'
param entraApiClientId = '82773ea0-fcf3-4874-81c3-3cd0da7d00c7'
param entraApiScope = 'access_as_user'

param logDailyQuotaGb = '0.1'
param databaseSecretName = 'database-url'
param openAiSecretName = 'openai-api-key'
param openAiModel = 'gpt-5.6-terra'
param openAiReasoningEffort = 'low'
param openAiTimeoutSeconds = 30
param tags = {
  project: 'Prepwise-Business-Concept'
  purpose: 'portfolio'
}
