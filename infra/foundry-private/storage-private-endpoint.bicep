targetScope = 'resourceGroup'

@description('Existing storage account in the deployment resource group. Its settings and role assignments are not modified.')
param storageAccountName string = 'saportfoliomanagement'

@description('Region for the VNet and private endpoint. Keep this aligned with the Foundry region.')
param location string = resourceGroup().location

param virtualNetworkName string = 'vnet-portfoliomanagement'
param virtualNetworkPrefix string = '172.20.0.0/16'
param agentSubnetPrefix string = '172.20.0.0/24'
param privateEndpointSubnetPrefix string = '172.20.1.0/24'

resource storageAccount 'Microsoft.Storage/storageAccounts@2026-09-01' existing = {
  name: storageAccountName
}

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2026-07-01' = {
  name: virtualNetworkName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        virtualNetworkPrefix
      ]
    }
    subnets: [
      {
        name: 'snet-agents'
        properties: {
          addressPrefix: agentSubnetPrefix
          delegations: [
            {
              name: 'agent-environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'snet-private-endpoints'
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource blobPrivateEndpoint 'Microsoft.Network/privateEndpoints@2026-07-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  properties: {
    subnet: {
      id: resourceId('Microsoft.Network/virtualNetworks/subnets', virtualNetwork.name, 'snet-private-endpoints')
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccountName}-blob'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
}

resource blobPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: blobPrivateDnsZone
  name: '${virtualNetwork.name}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetwork.id
    }
  }
}

resource blobPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2026-07-01' = {
  parent: blobPrivateEndpoint
  name: 'blob'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobPrivateDnsZone.id
        }
      }
    ]
  }
}

output virtualNetworkId string = virtualNetwork.id
output agentSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', virtualNetwork.name, 'snet-agents')
output privateEndpointId string = blobPrivateEndpoint.id
output privateDnsZoneId string = blobPrivateDnsZone.id
output storageBlobHostname string = '${storageAccountName}.blob.${environment().suffixes.storage}'
