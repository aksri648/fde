from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient

from app.adapters.base_adapter import BaseAdapter
from app.config import get_settings
from app.models.deployment import DeploymentConfig
from app.utils.logger import get_logger

logger = get_logger("azure_adapter")


class AzureAdapter(BaseAdapter):
    def __init__(self):
        settings = get_settings()
        self.credential = DefaultAzureCredential()
        self.subscription_id = settings.AZURE_SUBSCRIPTION_ID

        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.aks_client = ContainerServiceClient(self.credential, self.subscription_id)
        self.app_client = ContainerAppsAPIClient(self.credential, self.subscription_id)
        self.acr_client = ContainerRegistryManagementClient(self.credential, self.subscription_id)

    async def deploy(self, config: DeploymentConfig) -> dict:
        return {"status": "configured", "strategy": config.strategy}

    async def teardown(self, deployment_id: str) -> dict:
        return {"status": "teardown_initiated", "deployment_id": deployment_id}

    def create_resource_group(self, name: str, location: str, tags: dict) -> dict:
        rg = self.resource_client.resource_groups.create_or_update(
            name, {"location": location, "tags": tags}
        )
        return {"name": rg.name, "location": rg.location, "id": rg.id}

    def create_virtual_network(
        self,
        resource_group: str,
        vnet_name: str,
        location: str,
        address_prefix: str,
        subnet_name: str,
        subnet_prefix: str,
    ) -> dict:
        from azure.mgmt.network.models import VirtualNetwork, Subnet

        vnet_poll = self.network_client.virtual_networks.begin_create_or_update(
            resource_group,
            vnet_name,
            VirtualNetwork(location=location, address_space={"address_prefixes": [address_prefix]}),
        )
        vnet = vnet_poll.result()

        subnet_poll = self.network_client.subnets.begin_create_or_update(
            resource_group,
            vnet_name,
            subnet_name,
            Subnet(address_prefix=subnet_prefix),
        )
        subnet = subnet_poll.result()

        return {"vnet_id": vnet.id, "subnet_id": subnet.id}

    def create_container_registry(
        self, resource_group: str, registry_name: str, location: str, sku: str = "Premium"
    ) -> dict:
        from azure.mgmt.containerregistry.models import Registry, Sku

        acr_poll = self.acr_client.registries.begin_create(
            resource_group,
            registry_name,
            Registry(location=location, sku=Sku(name=sku), admin_user_enabled=False),
        )
        acr = acr_poll.result()
        return {"login_server": acr.login_server, "id": acr.id}

    def provision_gpu_vm(
        self,
        resource_group: str,
        vm_name: str,
        location: str,
        vm_size: str,
        image_reference: dict,
        nic_id: str,
    ) -> dict:
        from azure.mgmt.compute.models import (
            VirtualMachine,
            HardwareProfile,
            StorageProfile,
            OSProfile,
            NetworkProfile,
            ImageReference,
            LinuxConfiguration,
            SshConfiguration,
            SshPublicKey,
        )

        vm_config = VirtualMachine(
            location=location,
            hardware_profile=HardwareProfile(vm_size=vm_size),
            storage_profile=StorageProfile(
                image_reference=ImageReference(**image_reference),
                os_disk={"create_option": "FromImage", "managed_disk": {"storage_account_type": "Standard_LRS"}},
            ),
            os_profile=OSProfile(
                computer_name=vm_name[:15],
                admin_username="azureuser",
                linux_configuration=LinuxConfiguration(
                    disable_password_authentication=True,
                    ssh=SshConfiguration(
                        public_keys=[SshPublicKey(path=f"/home/azureuser/.ssh/authorized_keys", key_data="")]
                    ),
                ),
            ),
            network_profile=NetworkProfile(
                network_interfaces=[{"id": nic_id, "properties": {"primary": True}}]
            ),
        )

        vm_poll = self.compute_client.virtual_machines.begin_create_or_update(
            resource_group, vm_name, vm_config
        )
        vm = vm_poll.result()

        self.compute_client.virtual_machine_extensions.begin_create_or_update(
            resource_group,
            vm_name,
            "NvidiaGpuDriverLinux",
            {
                "location": location,
                "publisher": "Microsoft.HpcCompute",
                "type": "NvidiaGpuDriverLinux",
                "type_handler_version": "1.6",
            },
        ).result()

        return {"vm_id": vm.id, "name": vm.name, "public_ip": ""}

    def create_aks_cluster(
        self,
        resource_group: str,
        cluster_name: str,
        location: str,
        gpu_vm_size: str,
        gpu_node_count: int,
        min_count: int,
        max_count: int,
    ) -> dict:
        from azure.mgmt.containerservice.models import (
            ManagedCluster,
            ManagedClusterAgentPoolProfile,
            AgentPoolProfile,
            ContainerServiceLinuxProfile,
        )

        system_pool = ManagedClusterAgentPoolProfile(
            name="system",
            count=1,
            vm_size="Standard_D2s_v3",
            os_type="Linux",
            mode="System",
        )

        gpu_pool = AgentPoolProfile(
            name="gpu",
            count=gpu_node_count,
            vm_size=gpu_vm_size,
            os_type="Linux",
            mode="User",
            node_taints=["sku=gpu:NoSchedule"],
            node_labels={"accelerator": "nvidia-gpu"},
            enable_auto_scaling=True,
            min_count=min_count,
            max_count=max_count,
        )

        cluster = ManagedCluster(
            location=location,
            agent_pools=[system_pool, gpu_pool],
            linux_profile=ContainerServiceLinuxProfile(
                admin_username="azureuser",
                ssh={"public_keys": [{"key_data": ""}]},
            ),
            service_principal_profile={"client_id": get_settings().AZURE_CLIENT_ID, "secret": get_settings().AZURE_CLIENT_SECRET},
        )

        cluster_poll = self.aks_client.managed_clusters.begin_create_or_update(
            resource_group, cluster_name, cluster
        )
        cluster_result = cluster_poll.result()

        return {
            "cluster_id": cluster_result.id,
            "fqdn": cluster_result.fqdn,
            "name": cluster_result.name,
        }

    def deploy_container_app(
        self,
        resource_group: str,
        app_name: str,
        location: str,
        environment_id: str,
        container_image: str,
        container_args: list,
        target_port: int,
        min_replicas: int,
        max_replicas: int,
    ) -> dict:
        from azure.mgmt.appcontainers.models import (
            ContainerApp,
            Container,
            ContainerResources,
            Scale,
            Ingress,
            Configuration,
        )

        container = Container(
            name=app_name,
            image=container_image,
            args=container_args,
            resources=ContainerResources(cpu=2.0, memory="4Gi"),
        )

        scale = Scale(
            min_replicas=min_replicas,
            max_replicas=max_replicas,
        )

        ingress = Ingress(
            external=True,
            target_port=target_port,
            transport="http",
        )

        config = Configuration(
            ingress=ingress,
        )

        app = ContainerApp(
            location=location,
            containers=[container],
            scale=scale,
            configuration=config,
        )

        app_poll = self.app_client.container_apps.begin_create_or_update(
            resource_group, environment_id or f"env-{app_name}", app_name, app
        )
        app_result = app_poll.result()

        return {
            "app_id": app_result.id,
            "fqdn": app_result.configuration.ingress.fqdn if app_result.configuration and app_result.configuration.ingress else "",
            "name": app_result.name,
        }

    async def check_status(self, deployment_id: str) -> dict:
        return {"status": "unknown", "deployment_id": deployment_id}
