from azure.mgmt.containerservice.models import ContainerServiceNetworkProfile
from azure.mgmt.containerservice.models import ContainerServiceLinuxProfile
from azure.mgmt.containerservice.models import ContainerServiceSshConfiguration
from azure.mgmt.containerservice.models import ContainerServiceSshPublicKey
from azure.mgmt.containerservice.models import ManagedClusterServicePrincipalProfile
from azure.mgmt.containerservice.models import ManagedClusterSKU
from azure.mgmt.containerservice.models import ManagedCluster
from azure.mgmt.containerservice.models import ManagedClusterAgentPoolProfile
import logging
import os
import sys

class AZContainerService:
    cloud = 'AZ'
    orchestrator = 'KUB'
    node_resource_group_prefix = 'RG_MC_'

    def __init__(self, keyfile, config):
        self.logger = logging.getLogger('azlogger')
        self.keyfile = keyfile
        self.config = config

        self.vm_config = {
            'count' : config['agent_pool_profile']['count'],
            'vm_size' : config['agent_pool_profile']['vm_size'],
            'max_pods' : config['agent_pool_profile']['max_pods'],
            'max_count' : config['agent_pool_profile']['max_count'],
            'min_count' : config['agent_pool_profile']['min_count']
        } 
        self.logger.debug('vm_config %s', self.vm_config)

        self.location = config['aks_cluster']['location']
        self.region = config['aks_cluster']['region']
        self.region_code = config['aks_cluster']['region_code']
        self.sequence = config['aks_cluster']['sequence']
        self.code1 = config['aks_cluster']['code1']
        self.code2 = config['aks_cluster']['code2']
        self.env = config['aks_cluster']['env']
        self.tenant = config['aks_cluster']['tenant']

        # resource_name is the cluster name
        self.resource_name = '%s%s%s%s%s%s%s%s' % (
            self.cloud, 
            self.region, 
            self.region_code, 
            self.sequence, 
            self.orchestrator,
            self.code1, 
            self.env,
            self.sequence
        )

        self.node_resource_group = '%s%s%s%s%s' % (
            self.node_resource_group_prefix, 
            self.orchestrator, 
            self.code1, 
            self.env, 
            self.sequence
        )

    def create(self, container_client, rg_name, resource_name, tags, k8s_version, api_version):
        self.logger.debug('Creating cluster %s ', resource_name)
        self.container_client = container_client
        self.api_version = api_version
        params = self._set_all_cluster_params(tags, k8s_version)

        return container_client.managed_clusters.create_or_update(rg_name, resource_name, params, api_version=api_version)

    def validate_k8s_version(self, container_client, k8s_version, location, api_version):
        self.container_client = container_client,
        self.k8s_version = k8s_version,
        self.location = location
        self.orchestrator_type = 'Kubernetes'
        self.api_version = api_version
        
        self.logger.debug('Getting list of orchestrators')

        # api_version 2020-03-01 throws NotImplementedError
        # ("APIVersion {} is not available".format(api_version))
        k8s_list = container_client.container_services.list_orchestrators(
            location=self.location, api_version=api_version
        )

        valid_versions = {}
        # Create a dictionary of orchestrator versions of type Kubernetes
        for t in k8s_list.orchestrators:
            if t.orchestrator_type == self.orchestrator_type:
                valid_versions[t.orchestrator_version] = t.is_preview

        self.logger.debug('Azure k8s orchestrators %s', valid_versions)

        if not k8s_version:
            self.logger.debug('k8s version not specified, getting latest non-preview version')
            f_k8s = self._get_latest_k8s_version(valid_versions)
        elif k8s_version not in valid_versions.keys():
            self.logger.debug('k8s version %s is not valid, getting latest non-preview version', k8s_version)
            f_k8s = self._get_latest_k8s_version(valid_versions)
        elif (k8s_version in valid_versions.keys() and valid_versions.get(k8s_version) == True):
            self.logger.debug('k8s version %s is in preview, getting latest non-preview version', k8s_version)
            f_k8s = self._get_latest_k8s_version(valid_versions)
        else:
            f_k8s = k8s_version

        return f_k8s

    def _set_all_cluster_params(self, tags, kubernetes_version):
        location = self.location
        dns_prefix = self.resource_name
        agent_pool = self._create_agent_pool_profile(self.vm_config)
        linux_pool =  self._create_linux_pool_profile(self.keyfile)
        #self.logger.debug('Create Linux profile %s', linux_pool)
        service_principal = self._create_serviceprincipal_profile()
        #self.logger.debug('Create SP profile %s', service_principal) 
        net_profile = self._create_network_profile()
        sku = self._create_sku()
        enable_rbac = True

        return ManagedCluster(
            location = self.location, 
            tags = tags, 
            kubernetes_version = kubernetes_version, 
            dns_prefix = dns_prefix, 
            agent_pool_profiles = agent_pool, 
            linux_profile = linux_pool, 
            service_principal_profile = service_principal, 
            node_resource_group = self.node_resource_group, 
            enable_rbac = enable_rbac, 
            network_profile = net_profile, 
            sku = sku
    )

    # Can set node_labels 
    # vnet_subnet_id set here
    # Fails if mode not set but mode isn't documented as required
    def _create_agent_pool_profile(self, vm_config):
        # Type is 'VirtualMachineScaleSets' or 'AvailabilitySet'
        agent_pool_type = 'VirtualMachineScaleSets'
        agent_pool_name = 'agentpool'
        mode = 'System'
        enable_auto_scaling = True
        os_disk_size_gb = 0
        count = self.vm_config['count']
        vm_size = self.vm_config['vm_size']
        max_pods = self.vm_config['max_pods']
        max_count = self.vm_config['max_count']
        min_count = self.vm_config['min_count']

        return [ 
            ManagedClusterAgentPoolProfile(
            name = agent_pool_name, 
            count = count, 
            vm_size = vm_size,
            os_disk_size_gb = os_disk_size_gb, 
            max_pods = max_pods, 
            max_count = max_count, 
            min_count = min_count, 
            enable_auto_scaling = enable_auto_scaling,
            mode = mode, 
            type = agent_pool_type
            ) 
        ]

    def _create_serviceprincipal_profile(self):
        client_id = ''
        client_secret = ''

        return ManagedClusterServicePrincipalProfile(
            client_id = client_id, 
            secret = client_secret
        )

    def _create_network_profile(self):
        network_plugin = 'kubenet'
        network_policy = 'calico'
        network_mode = 'transparent'
        pod_cidr = '10.244.0.0/16'
        service_cidr = '10.0.0.0/16'
        dns_service_ip = '10.0.0.10'
        docker_bridge_cidr = '172.17.0.1/16'
        outbound_type = 'loadBalancer' 
        load_balancer_sku = 'basic'

        return ContainerServiceNetworkProfile(
            network_plugin = network_plugin, 
            network_policy = network_policy, 
            network_mode = network_mode, 
            pod_cidr = pod_cidr, 
            service_cidr = service_cidr, 
            dns_service_ip = dns_service_ip,
            docker_bridge_cidr = docker_bridge_cidr, 
            outbound_type = outbound_type, 
            load_balancer_sku = load_balancer_sku
        )

    # Provide an ssh public key 
    def _create_linux_pool_profile(self, keyfile):
        if not keyfile: 
            return None
        admin_username = 'SP2'
        ssh_keyfile = keyfile
        try:
            f = open(ssh_keyfile, 'r')
        except (FileNotFoundError, IOError) as e:
            self.logger.info('Keyfile error %s, linux_pool_profile not set', e)
            return None

        with f: 
            cert_lines = f.read()

        f.close()

        public_keys = [ 
            ContainerServiceSshPublicKey(key_data=cert_lines) 
        ]

        return ContainerServiceLinuxProfile(admin_username=admin_username,
            ssh=ContainerServiceSshConfiguration(public_keys=public_keys)) 

    def _create_sku(self):
        sku_name = 'Basic'
        sku_tier = 'Paid'
        return ManagedClusterSKU(name=sku_name, tier=sku_tier)

    def _get_latest_k8s_version(self,v):
        self.major = 0
        self.minor = 0
        self.fix = 0
        # version is a string like '1.16.7'
        # is_preview is None or True
        for version, is_preview in v.items():
            # Ignore any version in preview
            if is_preview:
                continue
            newmaj, newmin, newfix = version.split('.')
            if int(newmaj) > int(self.major):
                major = newmaj
                minor = newmin
                fix = newfix
            elif int(newmin) > int(self.minor):
                major = newmaj
                minor = newmin
                fix = newfix
            elif int(newmaj) == int(self.major) and int(newmin) == int(self.minor) and int(newfix) > int(self.fix):
                major = newmaj
                minor = newmin
                fix = newfix

        return (major+'.'+minor+'.'+fix)
