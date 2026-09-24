targetScope = 'subscription'

metadata description = 'Subscription-level entry point for the Prepwise Azure infrastructure.'

@description('Short workload name used in Azure resource names.')
@minLength(2)
@maxLength(20)
param workloadName string = 'prepwise'

@description('Deployment environment name.')
@allowed([
  'dev'
  'prod'
])
param environmentName string

@description('Primary Azure region for the backend, secrets and observability resources.')
param primaryLocation string

@description('Azure region used by Static Web Apps.')
param staticWebAppLocation string

@description('Backend container image. T3.4 overrides the placeholder with a GHCR image.')
param backendContainerImage string

@description('Port exposed by the backend container image.')
@minValue(1)
@maxValue(65535)
param backendContainerPort int

@description('Microsoft Entra External ID tenant ID used to validate API access tokens.')
param entraTenantId string

@description('Microsoft Entra External ID tenant subdomain used to retrieve signing keys.')
param entraTenantSubdomain string

@description('Application ID of the Prepwise API registration; expected as the v2 token audience.')
param entraApiClientId string

@description('Delegated scope required by protected Prepwise API endpoints.')
param entraApiScope string = 'access_as_user'

@description('Maximum daily Log Analytics ingestion in GB, represented as a decimal string. Use -1 for no cap.')
param logDailyQuotaGb string = '0.1'

@description('Operator email for Azure Monitor alerts. Leave empty to create monitoring without email delivery.')
param alertEmailAddress string = ''

@description('Name of the existing Key Vault secret containing the production runtime database URL.')
param databaseSecretName string = 'database-url'

@description('Additional tags applied to every resource.')
param tags object = {}

var nameSuffix = take(uniqueString(subscription().subscriptionId, environmentName), 6)
var namePrefix = toLower('${workloadName}-${environmentName}')
var resourceGroupName = 'rg-${namePrefix}'
var commonTags = union(tags, {
  application: workloadName
  environment: environmentName
  managedBy: 'Bicep'
})

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: resourceGroupName
  location: primaryLocation
  tags: commonTags
}

module frontend './modules/static-web-app.bicep' = {
  name: 'frontend-${environmentName}'
  scope: resourceGroup
  params: {
    name: 'swa-${namePrefix}-${nameSuffix}'
    location: staticWebAppLocation
    tags: commonTags
  }
}

module secrets './modules/key-vault.bicep' = {
  name: 'secrets-${environmentName}'
  scope: resourceGroup
  params: {
    name: take(toLower('kv-${replace(workloadName, '-', '')}-${environmentName}-${nameSuffix}'), 24)
    location: primaryLocation
    tags: commonTags
  }
}

module backend './modules/backend-hosting.bicep' = {
  name: 'backend-${environmentName}'
  scope: resourceGroup
  params: {
    namePrefix: namePrefix
    location: primaryLocation
    containerImage: backendContainerImage
    containerPort: backendContainerPort
    corsAllowedOrigins: 'https://${frontend.outputs.defaultHostname}'
    logDailyQuotaGb: logDailyQuotaGb
    alertEmailAddress: alertEmailAddress
    keyVaultName: secrets.outputs.name
    keyVaultUri: secrets.outputs.uri
    databaseSecretName: databaseSecretName
    entraTenantId: entraTenantId
    entraTenantSubdomain: entraTenantSubdomain
    entraApiClientId: entraApiClientId
    entraApiScope: entraApiScope
    tags: commonTags
  }
}

output resourceGroupName string = resourceGroup.name
output backendName string = backend.outputs.containerAppName
output backendUrl string = 'https://${backend.outputs.fqdn}'
output frontendName string = frontend.outputs.name
output frontendUrl string = 'https://${frontend.outputs.defaultHostname}'
output keyVaultName string = secrets.outputs.name
output keyVaultUri string = secrets.outputs.uri
output applicationInsightsName string = backend.outputs.applicationInsightsName
output availabilityTestName string = backend.outputs.availabilityTestName
output alertActionGroupName string = backend.outputs.alertActionGroupName
output backendIdentityName string = backend.outputs.managedIdentityName
output backendIdentityPrincipalId string = backend.outputs.managedIdentityPrincipalId
