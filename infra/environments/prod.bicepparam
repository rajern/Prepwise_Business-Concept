using '../main.bicep'

param workloadName = 'prepwise'
param environmentName = 'prod'
param primaryLocation = 'norwayeast'
param staticWebAppLocation = 'eastus2'

// Deployment uses immutable commit tags; latest is the reproducible Bicep fallback.
param backendContainerImage = 'ghcr.io/rajern/prepwise-api:latest'
param backendContainerPort = 8000

param logDailyQuotaGb = '0.1'
param databaseSecretName = 'database-url'
param tags = {
  project: 'Prepwise-Business-Concept'
  purpose: 'portfolio'
}
