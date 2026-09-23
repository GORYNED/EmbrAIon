# Security (Seguridad)

EmbrAIon trata los permisos de ejecución, la clasificación de datos, la elegibilidad de proveedores, las integraciones externas, la configuración generada, las credenciales y los derechos de modificación como restricciones de ingeniería obligatorias.

Las reglas de seguridad viven en las reglas y el enrutamiento del Core. Los adaptadores de clientes y proveedores concretos implementan los mecanismos necesarios. `tools/security/` realiza comprobaciones deterministas y `tools/mcp/` normaliza el inventario de servidores externos y detecta diferencias.

**Fail Closed (Denegación segura)** se aplica cuando:

- una tarea no puede clasificarse de forma segura;
- un proveedor no está autorizado para la clase de datos correspondiente;
- una integración externa tiene acceso desconocido o inesperadamente ampliado;
- un valor secreto entra en una configuración persistente;
- la configuración generada difiere de la fuente aprobada;
- una operación con permiso de escritura excede su perfil de acceso.

Los resultados de seguridad constituyen evidencia de un problema y no un permiso para debilitar la regla de control.
