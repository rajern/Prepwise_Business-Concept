using '../main.bicep'

param workloadName = 'prepwise'
param environmentName = 'prod'
param primaryLocation = 'norwayeast'
param staticWebAppLocation = 'westeurope'

// T3.4 replaces this public placeholder with the versioned GHCR backend image.
param backendContainerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param backendContainerPort = 80

param logDailyQuotaGb = '0.1'
param tags = {
  project: 'Prepwise-Business-Concept'
  purpose: 'portfolio'
}
