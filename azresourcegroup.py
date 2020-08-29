import logging
from azure.mgmt.resource.resources.models import ResourceGroup

# pip install azure-mgmt-resource
# This doesn't create the RG with the correct name
class AZResourceGroup:
    def __init__(self):
        self.logger = logging.getLogger('azlogger')

    def exists(self, resource_client, resource_group):
        """ Return true or false if the resource_group exists """
        self.logger.info('Checking resource group %s', resource_group)

        return resource_client.resource_groups.check_existence(resource_group)

    def create(self, resource_client, resource_group, location, tags):
        """ Create a resource group in the specified location """
        # Need to pass parameters to here not set them here
        self.rg_params = ResourceGroup(location=location, tags=tags)
        self.logger.info('Creating resource group %s', resource_group)

        # Set an API version here
        return resource_client.resource_groups.create_or_update(resource_group, self.rg_params)
 