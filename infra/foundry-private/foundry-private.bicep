targetScope = 'resourceGroup'

@description('New account name and globally unique endpoint subdomain. Never use the existing public account name.')
param accountName string = 'foundry-portfoliomanagement-private'

param projectName string = 'proj-portfoliomanagement-private'

@description('Must match the existing VNet region.')
param location string = 'swedencentral'

param virtualNetworkName string = 'vnet-portfoliomanagement'
param agentSubnetName string = 'snet-agents'
param privateEndpointSubnetName string = 'snet-private-endpoints'

@description('Object ID of the user who will manage agents in the new project.')
param projectUserObjectId string

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2026-07-01' existing = {
  name: virtualNetworkName
}

resource agentSubnet 'Microsoft.Network/virtualNetworks/subnets@2026-07-01' existing = {
  parent: virtualNetwork
  name: agentSubnetName
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2026-07-01' existing = {
  parent: virtualNetwork
  name: privateEndpointSubnetName
}

resource account 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
      bypass: 'AzureServices'
    }
    networkInjections: [
      {
        scenario: 'agent'
        subnetArmId: agentSubnet.id
        useMicrosoftManagedNetwork: false
      }
    ]
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2026-07-01' = {
  name: 'pe-${accountName}'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: accountName
        properties: {
          privateLinkServiceId: account.id
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

var dnsZoneNames = [
  'privatelink.services.ai.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.cognitiveservices.azure.com'
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for name in dnsZoneNames: {
  name: name
  location: 'global'
}]

resource dnsLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (name, index) in dnsZoneNames: {
  parent: dnsZones[index]
  name: '${virtualNetwork.name}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetwork.id
    }
  }
}]

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2026-07-01' = {
  parent: privateEndpoint
  name: 'foundry'
  properties: {
    privateDnsZoneConfigs: [for (name, index) in dnsZoneNames: {
      name: 'foundry-${index}'
      properties: {
        privateDnsZoneId: dnsZones[index].id
      }
    }]
  }
  dependsOn: [
    dnsLinks
  ]
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' = {
  parent: account
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Portfolio management - private'
    description: 'Basic agent setup using platform-managed storage and customer VNet injection.'
  }
  dependsOn: [
    dnsZoneGroup
  ]
}

resource projectUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, projectUserObjectId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    principalId: projectUserObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// The Basic VNet sample uses this legacy API; its kind property is missing from the published Bicep types.
resource agentCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  parent: project
  name: 'agents'
  properties: {
    #disable-next-line BCP037
    capabilityHostKind: 'Agents'
  }
}

output accountId string = account.id
output projectId string = project.id
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'
output agentSubnetId string = agentSubnet.id
output privateEndpointId string = privateEndpoint.id
