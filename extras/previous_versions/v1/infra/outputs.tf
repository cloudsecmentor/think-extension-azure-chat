output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "webapp_identity_principal_id" {
  value = azurerm_linux_web_app.app.identity[0].principal_id
}


