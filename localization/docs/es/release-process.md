# Proceso de releases

EmbrAIon utiliza releases versionados del sistema.

El contrato previsto es:

- GitHub es la fuente de verdad.
- Los releases de EmbrAIon utilizan etiquetas Git y documentación.
- Los proyectos nuevos comienzan desde una versión publicada.
- Los proyectos existentes fijan una versión concreta de EmbrAIon en `.embraion/project.yaml`.
- El launcher global resuelve automáticamente los pins publicados en runtimes aislados almacenados en `~/.embraion/versions/`.
- Las actualizaciones se realizan de forma intencionada, con notas de cambios y validación; `embraion update` cambia únicamente el pin del proyecto actual.

El repositorio aún está en una fase previa a la estabilidad. El proceso de releases se reforzará antes de publicar la primera versión estable.
