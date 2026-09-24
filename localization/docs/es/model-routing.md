# Routing (Enrutamiento)

El routing de EmbrAIon es completamente agnóstico respecto a los modelos.

Core clasifica el trabajo mediante `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex` y `critical`. Estas clases describen el trabajo y el riesgo, no la potencia, el precio, el proveedor ni un modelo concreto.

Si el proyecto no define un override, el cliente de IA elegido conserva su selección de modelo predeterminada o automática. Cuando se necesita una selección explícita, el proyecto puede guardar valores arbitrarios de `model`, `effort` y `options` propios del host en `.embraion/project.yaml` → `routing.overrides`.

El usuario puede pedir directamente a la IA del repositorio que configure EmbrAIon con los modelos disponibles. La skill instalada `routing-configuration` indica dónde escribir el override y qué políticas no deben debilitarse.

EmbrAIon no mantiene un catálogo canónico de modelos. Privacy, access, ownership, validation y review permanecen independientes de la selección de modelo.
