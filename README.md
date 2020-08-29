# Introduction 

Create an Azure Kubernetes Service (AKS) cluster, resource group and key vault using the Azure Python SDK.

# Running the tool

python aksdriver.py -f [toml config file]

# Method

The code reads a toml file and creates an AKS cluster based on entries in the file.

# Notes

This is an incomplete work in progress. While the code does create all the objects in Azure I planned, it has not been well tested and will not run as-is. It does provide examples for a number of Azure APIs including those for AKS, resource groups and key vault operations.

The code reads a client id and secret from the environment, instantiates an Azure client and then uses the client to read a second client id and secret from a Key Vault. The only role the client id read from the environment has is 'Get' on objects in the Key Vault. The second id (api-user-client-id) has the required roles in Azure to create a cluster and the other objects. A third client id is assigned as the cluster 'management' service principal though a better option would be to use an Azure Managed Identity as the management service principal.