targetScope = 'resourceGroup'

metadata description = 'Low-cost Container Apps hosting and Azure observability for FastAPI.'

param namePrefix string
param location string
param containerImage string
param containerPort int
param corsAllowedOrigins string
param logDailyQuotaGb string
param keyVaultName string
param keyVaultUri string
param databaseSecretName string
param tags object

var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: keyVaultName
}

resource databaseSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' existing = {
  parent: keyVault
  name: databaseSecretName
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${namePrefix}-api'
  location: location
  tags: tags
}

resource databaseSecretAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(databaseSecret.id, managedIdentity.id, keyVaultSecretsUserRoleId)
  scope: databaseSecret
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleId
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${namePrefix}'
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: json(logDailyQuotaGb)
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${namePrefix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    Request_Source: 'rest'
    RetentionInDays: 30
    SamplingPercentage: 100
    WorkspaceResourceId: logAnalytics.id
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-${namePrefix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-${namePrefix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: databaseSecretName
          keyVaultUrl: '${keyVaultUri}secrets/${databaseSecretName}'
          identity: managedIdentity.id
        }
      ]
      ingress: {
        allowInsecure: false
        external: true
        targetPort: containerPort
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          env: [
            {
              name: 'APP_ENV'
              value: 'production'
            }
            {
              name: 'CORS_ALLOWED_ORIGINS'
              value: corsAllowedOrigins
            }
            {
              name: 'DATABASE_URL'
              secretRef: databaseSecretName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http-requests'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [databaseSecretAccess]
}

output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output applicationInsightsId string = applicationInsights.id
output applicationInsightsName string = applicationInsights.name
output logAnalyticsWorkspaceId string = logAnalytics.id
output managedIdentityName string = managedIdentity.name
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
