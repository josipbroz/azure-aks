import logging
from azure.mgmt.keyvault.models import CheckNameAvailabilityResult

class AZKeyVault:
    def __init__(self):
        self.logger = logging.getLogger('azlogger')

    def check(self, resource_client, kv_name):
        ''' Check whether the KeyVault name is available for use '''
        self.kv_name = kv_name
        ret = resource_client.vaults.check_name_availability(kv_name)
        if ret.name_available:
            return True, None
        else:
            return False, ret.reason

    def create(self, resource_client, rg_name, kv_name, properties):
        self.rg_name = rg_name
        self.kv_name = kv_name
        self.properties = properties
        # Try calling result here and sending it back
        return resource_client.vaults.create_or_update(rg_name, kv_name, properties)

 