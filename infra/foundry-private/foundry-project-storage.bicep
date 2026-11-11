targetScope = 'resourceGroup'

param accountName string = 'foundry-portfoliomanagement-private'
param projectName string = 'proj-portfoliomanagement-private'
param storageAccountName string = 'saportfoliomanagement'

@description('Name of the existing default storage connection to update, not a new connection.')
param connectionName string = 'saportfoliomanagementzorlov'

resource account 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' existing = {
  parent: account
  name: projectName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2026-09-01' existing = {
  name: storageAccountName
}

var blobContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource projectBlobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, project.id, blobContributorRole)
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobContributorRole
  }
}

resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: connectionName
  properties: {
    authType: 'AAD'
    category: 'AzureStorageAccount'
    // Foundry accepts isDefault, but the connection schema omits it.
    #disable-next-line BCP037
    isDefault: true
    isSharedToAll: false
    sharedUserList: []
    target: 'https://${storageAccountName}.blob.${environment().suffixes.storage}/'
    useWorkspaceManagedIdentity: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccount.id
      displayName: storageAccountName
    }
  }
  dependsOn: [
    projectBlobAccess
  ]
}

output projectPrincipalId string = project.identity.principalId
output connectionId string = storageConnection.id
