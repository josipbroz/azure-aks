from azure.identity import DefaultAzureCredential
from azure.common.credentials import ServicePrincipalCredentials
from azure.keyvault.secrets import SecretClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.containerservice.models import ContainerServiceVMSizeTypes
from azure.mgmt.keyvault.models import VaultProperties
#from azure.mgmt.keyvault.v2019_09_01.models._models import VaultProperties
#from azure.mgmt.keyvault.v2016_10_01.models._models_py3 import VaultCreateOrUpdateParameters
from azure.mgmt.keyvault.models import VaultCreateOrUpdateParameters
from azure.mgmt.keyvault.v2018_02_14.models import Sku
from azure.mgmt.keyvault.v2016_10_01.models._models_py3 import AccessPolicyEntry, Permissions

import argparse
import logging
import os
import sys
from configtoml import ConfigToml
from azcontainerservice import AZContainerService
from azresourcegroup import AZResourceGroup
from azkeyvault import AZKeyVault

date_format = '%y/%m/%d %H:%M:%S'
levels = ('INFO', 'DEBUG') 
api_version = '2020-01-01'
cloud = 'AZ'
orchestrator = 'KUB'
kv_abbr = 'VLT'
rg_prefix = 'RG_'
# Put in config file
app_user_object_id = ''
app_user_app_id = ''

logger = logging.getLogger('azlogger')

formatter = logging.Formatter('[%(asctime)s:%(msecs)03d] %(levelname)-8s %(message)s', datefmt=date_format)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logging.getLogger('azlogger').addHandler(console_handler)

parser = argparse.ArgumentParser(description='Create an AKS cluster')
parser.add_argument('-f', '--configfile', action='store', required=True, dest='configfile')
parser.add_argument('-k', '--keyfile', action='store', required=False, dest='keyfile')
parser.add_argument('-l', '--loglevel', default='INFO', choices=levels, dest='log_level')

args = parser.parse_args()

logging.getLogger('azlogger').setLevel(args.log_level)

cfg = ConfigToml()
config, err = cfg.readConfig(args.configfile)

if err:
    logging.info('Error reading config file %s', err)   
    sys.exit(1)

logger.info('Done reading config file')

vm = config['agent_pool_profile']['vm_size'].lower()
logger.info("Checking VM '%s'", vm)
# Check the configured VM against the list of valid Azure VM sizes
# vm_check will contain a single item if the configured VM is valid 
# (the same name of the VM type set in the config file) or the list 
# will be empty if the VM in the config file is not a valid VM type 
vm_check = [vm for name, member in ContainerServiceVMSizeTypes.__members__.items() if member.name == vm]
if not vm_check: 
    logger.info("VM '%s' is not a valid Azure VM type", vm)
    sys.exit(1)

# Create a credential object to read from the key vault
# DefaultAzureCredential() gets its values from the environment
credential = DefaultAzureCredential()

keyVaultName = os.environ['KEY_VAULT_NAME']
KVUri = 'https://' + keyVaultName + '.vault.azure.net'

secret_client = SecretClient(vault_url=KVUri, credential=credential)

# Get the data for SP1 from the key vault
retrieved_secret = secret_client.get_secret('api-user-client-secret')
retrieved_client = secret_client.get_secret('api-user-client-id')
retrieved_tenant = secret_client.get_secret('api-user-tenant-id')

# Create a credential object that is used to create the RG
# and the k8s clusters using the secrets in the key vault
akscredentials = ServicePrincipalCredentials(
    client_id = retrieved_client.value,
    secret = retrieved_secret.value,
    tenant = retrieved_tenant.value
)
subscription = os.environ['AZURE_SUBSCRIPTION']

cluster_tags = {
    'CODE1': config['aks_cluster']['code1'],
    'CODE2': config['aks_cluster']['code2'],
    'ENV'    : config['aks_cluster']['env'],
    'TENANT' : config['aks_cluster']['tenant']
}

rg = AZResourceGroup()
resource_client = ResourceManagementClient(akscredentials, subscription)

rg_name = '%s%s%s%s%s' % (
    rg_prefix, 
    orchestrator, 
    config['aks_cluster']['code1'], 
    config['aks_cluster']['env'],
    config['aks_cluster']['sequence'], 
)
if rg.exists(resource_client, rg_name):
    logger.info('The resource group %s exists in subscription %s', rg_name, subscription)
else:
    # Create resource group using SP1's credentials
    rg_name = rg.create(resource_client, rg_name, config['aks_cluster']['location'], cluster_tags)

kv = AZKeyVault()
kv_client = KeyVaultManagementClient(akscredentials, subscription)

kv_name = '%s%s%s%s%s%s%s%s' % (
    cloud, 
    config['aks_cluster']['region'], 
    config['aks_cluster']['region_code'], 
    config['aks_cluster']['sequence'], 
    kv_abbr,
    config['aks_cluster']['code1'], 
    config['aks_cluster']['env'],
    config['aks_cluster']['sequence']
)

#s = Sku(name='standard', family='A')
#s = Sku(name='standard')

# This access is for an application SP
# In this case the SP is 'app-user'
# The app SP onject id and application id should go
# in the config file since they are app-speciific
# See
# https://docs.microsoft.com/en-us/rest/api/keyvault/vaults/createorupdate
# Try using 0 for the ids/onjects and if 'all' doesn't work for
# the permissions list all of them
kv_access = AccessPolicyEntry(
    tenant_id=os.environ['AZURE_TENANT_ID'], 
    object_id=app_user_object_id, 
    permissions=Permissions(
        keys='all', 
        secrets='all',
        certificates='all'
    ), 
    application_id=app_user_app_id
)

kv_params = VaultCreateOrUpdateParameters(
    location=config['aks_cluster']['location'],
    properties=VaultProperties(
        tenant_id=os.environ["AZURE_TENANT_ID"], 
        sku=Sku(name='standard'),
        enabled_for_deployment=True, 
        enabled_for_template_deployment=True, 
        enable_rbac_authorization=True,
        access_policy=kv_access
    )
) 

kresult, err = kv.check(kv_client, kv_name)
if kresult:
    logger.info('Creating KeyVault %s', kv_name)
    # Create it
    # kv create returns a poller object like cluster create does
    # call result() on it as shown here
    # https://docs.microsoft.com/en-us/python/api/overview/azure/key-vault?view=azure-python
    # Don't fail if it can't be created
    v = kv.create(kv_client, rg_name, kv_name, kv_params)
    logger.info('KeyVault create result %s', v.result())
else:
    logger.info('The KeyVault %s cannot be created %s', kv_name, err)

if not args.keyfile: args.keyfile = None
c_service = AZContainerService(args.keyfile, config)

container_client = ContainerServiceClient(akscredentials, subscription)

logger.debug('Kubernetes version in config %s', config['aks_cluster']['k8s_version'])
# Check the configured k8s version against the list of valid
# Azure Kubernetes versions. Set the version to the latest non-preview
# version if needed.
# A client object is required to call the API
k8s = c_service.validate_k8s_version(container_client, 
    config['aks_cluster']['k8s_version'], 
    config['aks_cluster']['location'], 
    api_version=None 
)
logger.debug('Set Kubernetes version to %s', k8s)
logger.debug('Cluster name %s', c_service.resource_name)

# Create the AKS cluster
# Returns a poller object <msrest.polling.poller.LROPoller ...>
# Need to pass in the cluster name here, not create it in the class
# The raw JSON can be returned here (and from many other APIs)
cluster = c_service.create(container_client, rg_name, c_service.resource_name, cluster_tags, k8s, api_version=api_version)
logger.info('Status %s', cluster.status())
logger.info('Result %s', cluster.result())
