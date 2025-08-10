variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "swedencentral"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "acr_name" {
  type        = string
  description = "Azure Container Registry name (must be globally unique, 5-50 alphanumeric)"
}

variable "acr_sku" {
  type        = string
  description = "ACR SKU"
  default     = "Basic"
}

variable "app_service_plan_name" {
  type        = string
  description = "App Service Plan name"
}

variable "app_service_plan_sku" {
  type        = string
  description = "App Service Plan SKU, e.g. B1, P1v3"
  default     = "B1"
}

variable "webapp_name" {
  type        = string
  description = "Linux Web App name"
}

variable "api_base_url" {
  type        = string
  description = "Base URL used by frontend to reach the API (inherited as app setting)"
  default     = "http://localhost:5000"
}


