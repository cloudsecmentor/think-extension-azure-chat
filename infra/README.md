# Infrastructure (Terraform)

Provisions:
- Resource Group (default `rg-sidecar-helloworld`)
- Azure Container Registry (ACR)
- App Service Plan (Linux)
- Linux Web App with system-assigned identity

Defaults align with Sweden Central region.

## Variables
- `subscription_id` (required)
- `location` (default: `swedencentral`)
- `resource_group_name` (default: `rg-sidecar-helloworld`)
- `acr_name` (required)
- `acr_sku` (default: `Basic`)
- `app_service_plan_name` (default: `aspsidecarhelloworld01`)
- `app_service_plan_sku` (default: `B1`)
- `webapp_name` (required)

## Usage
```
terraform init
terraform apply -var="subscription_id=<sub>" -var="acr_name=<acr>" -var="webapp_name=<webapp>"
```

