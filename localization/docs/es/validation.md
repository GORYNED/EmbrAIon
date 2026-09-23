# Validation (Validación)

La validación aporta evidencia de que un cambio en EmbrAIon conserva los contratos esperados.

El sistema de validación se desarrolla por capas:

- validación de esquemas;
- validación de referencias entre capacidades;
- comprobación de equivalencia entre adaptadores y representaciones generadas;
- validación de reglas de enrutamiento;
- comprobaciones de instalación y diagnóstico;
- comprobaciones de seguridad e inventario de integraciones;
- pruebas de integración;
- comparación de evaluaciones de comportamiento con resultados de referencia adecuados.

El estado `PASS` debe indicar qué se ha comprobado realmente y no limitarse a devolver una señal genérica de éxito.

La mejora del comportamiento de la IA se evalúa por separado de la corrección determinista. Un resultado global de comportamiento más alto nunca anula un fallo grave de seguridad, privacidad, permisos, compatibilidad o derechos de modificación.
