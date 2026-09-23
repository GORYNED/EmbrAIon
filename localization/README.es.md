<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System de GORYNED" width="100%">
</p>

<p align="center">
  <a href="../README.md">Inglés</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>Español</strong> ·
  <a href="README.hi.md">हिन्दी</a>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

> Where sparks become AI-built products *(Donde las chispas se convierten en productos creados con IA)*

EmbrAIon es un AI-First Engineering System portátil para organizar la ingeniería de software asistida por IA mediante roles explícitos, habilidades reutilizables, flujos de trabajo, enrutamiento de modelos, control de acceso, validación, revisión independiente, seguridad, aprendizaje del sistema y capas específicas de cada proyecto.

No está ligado a un único lenguaje de programación ni a un único entorno. Un proyecto Unity/C#, un servicio Python, una aplicación web u otro repositorio de software pueden utilizar el mismo núcleo de EmbrAIon y añadir únicamente su conocimiento y sus reglas específicas.

## Qué hace EmbrAIon

EmbrAIon divide el sistema de ingeniería en componentes independientes:

- **[Agent (Agente)](../core/agents/)** — quién es responsable del trabajo: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher o Steward.
- **[Skill (Habilidad)](../core/skills/)** — cómo realizar una clase de trabajo repetible.
- **[Rule (Regla)](../core/rules/)** — qué comportamiento es obligatorio, está prohibido o debe protegerse.
- **[Workflow (Flujo de trabajo)](../core/workflows/)** — en qué orden se combinan las capacidades.
- **[Routing (Enrutamiento)](../core/routing/)** — qué perfil de acceso, nivel de modelo, cliente y proveedor pueden ejecutar una tarea.
- **[Adapter (Adaptador)](../adapters/)** — cómo se representan las capacidades canónicas en Codex, GitHub Copilot, Claude Code, proveedores de API o un paquete Portable.
- **[Tool (Herramienta)](../tools/)** — lógica ejecutable determinista, como validación, análisis de seguridad, gestión de árboles de trabajo Git, sincronización y diagnóstico.
- **[Eval (Evaluación de comportamiento)](../evals/)** — comprobación de que la IA realmente cumple el contrato de ingeniería previsto.

`core/catalog.yaml` es el índice de descubrimiento de capacidades. En vez de cargar todo EmbrAIon para cada tarea, el sistema puede cargar únicamente las reglas, roles, habilidades y flujos necesarios para el trabajo actual.

## Clases de datos

EmbrAIon utiliza tres clases de datos canónicas:

| Clase | Significado |
| --- | --- |
| `PUBLIC` | Información pública que puede enviarse a sistemas externos autorizados |
| `PRIVATE` | Información interna o propietaria del proyecto; el uso externo requiere una ruta expresamente autorizada |
| `CONFIDENTIAL` | Nivel de máxima protección; el envío externo está prohibido salvo que una ruta lo permita expresamente |

Una clasificación desconocida o ambigua produce una denegación segura. Elegir un modelo más potente nunca amplía los permisos de acceso o privacidad.

## Adaptadores compatibles

- **[Codex](https://openai.com/codex/)** — catálogo de modelos, correspondencia entre modelo/nivel de razonamiento y rutas, y generación de agentes y configuración del proyecto.
- **[GitHub Copilot](https://github.com/features/copilot)** — catálogo de modelos compatibles, rutas recomendadas y generación de agentes personalizados.
- **[Claude Code](https://code.claude.com/docs/en/overview)** — catálogo de modelos Claude, rutas y generación de subagentes.
- **[Portable](../adapters/portable/)** — paquete de capacidades portátil e independiente de un cliente de IA concreto.
- **[Proveedores de API](../adapters/providers/)** — catálogos directos de [OpenAI](https://openai.com/), [Anthropic](https://www.anthropic.com/), [Google](https://ai.google.dev/) y [DeepSeek](https://www.deepseek.com/), además de información de conexión.

El Core permanece independiente de modelos concretos. Las identidades actuales de modelos y los selectores específicos de cada cliente viven únicamente en `adapters/`.

## Instalación

### Instalar una vez por equipo

EmbrAIon se distribuye mediante [PyPI](https://pypi.org/project/embraion/). Para el uso normal, instale el CLI una sola vez en cada equipo Windows o macOS con `pipx`. No es necesario clonar el repositorio ni usar `git clone`.

También se admite una instalación normal con `pip` si administra explícitamente el entorno de Python, pero `pipx` es la opción recomendada para el CLI.

#### Windows

EmbrAIon requiere Python 3.11 o posterior.

1. Compruebe Python:

```powershell
py --version
```

Si `py` no está disponible o la versión es anterior a 3.11, instale una versión actual de Python 3 desde las [descargas oficiales de Python para Windows](https://www.python.org/downloads/windows/) y vuelva a abrir PowerShell.

2. Instale [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) y añada su directorio de comandos a `PATH`:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

3. Cierre y vuelva a abrir PowerShell y, después, instale EmbrAIon:

```powershell
pipx install embraion
```

Si utiliza deliberadamente un entorno Python administrado por usted en lugar de `pipx`, también se admite:

```powershell
py -m pip install embraion
```

#### macOS

Si ya utiliza [Homebrew](https://brew.sh/), la ruta más sencilla es:

```bash
brew install pipx
pipx ensurepath
```

Abra una nueva ventana de Terminal e instale EmbrAIon:

```bash
pipx install embraion
```

Sin Homebrew, compruebe primero Python:

```bash
python3 --version
```

Si falta Python o la versión es anterior a 3.11, instale una versión actual de Python 3 desde las [descargas oficiales de Python para macOS](https://www.python.org/downloads/macos/). Después instale `pipx`:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Abra una nueva ventana de Terminal y ejecute:

```bash
pipx install embraion
```

También se admite `python3 -m pip install embraion` si administra explícitamente el entorno de Python.

#### Verificación

```bash
embraion --version
embraion validate
embraion doctor
```

`embraion validate` comprueba los datos del sistema incluidos en la instalación activa de EmbrAIon. `embraion doctor` también analiza el contexto del proyecto o árbol de trabajo actual, por lo que conviene ejecutarlo dentro del repositorio que quiera diagnosticar o desde una carpeta de prueba vacía.

#### Actualización

```bash
pipx upgrade embraion
```

La instalación global con `pipx` hace que el comando `embraion` esté disponible desde cualquier proyecto del equipo. **No activa EmbrAIon automáticamente en todos los repositorios** ni los modifica en segundo plano.

## Añadir EmbrAIon a cada proyecto

Cada repositorio se incorpora de forma explícita. Desde la raíz del proyecto:

```bash
cd /path/to/your/project
embraion init
```

De forma predeterminada, `init` usa el nombre de la carpeta como nombre del proyecto. Utilice `--name MyProject` solo si quiere sobrescribirlo.

Se crea:

```text
.embraion/
└── project.yaml
```

El Project Overlay (Capa del proyecto) conserva en Git la versión declarada de EmbrAIon y la configuración específica del proyecto.

### Instalar la representación para un cliente

Instale una representación para cada cliente de IA utilizado por el repositorio.

[Codex](https://openai.com/codex/):

```bash
embraion install --host codex --destination .
```

[GitHub Copilot](https://github.com/features/copilot):

```bash
embraion install --host copilot --destination .
```

[Claude Code](https://code.claude.com/docs/en/overview):

```bash
embraion install --host claude-code --destination .
```

Paquete Portable:

```bash
embraion install --host portable --destination ./vendor/embraion
```

Si el proyecto usa varios clientes, ejecute una vez el comando `install` correspondiente a cada uno. Los archivos generados existentes están protegidos contra sobrescritura de forma predeterminada; use `--force` solo de manera intencionada.

### Resolución automática de la versión del proyecto

`v0.2.0` añade resolución automática de la versión de EmbrAIon para cada proyecto.

Para los comandos normales, el `embraion` global busca hacia arriba desde el directorio actual hasta encontrar el `.embraion/project.yaml` más cercano y lee `framework.version`. Si la versión fijada por el proyecto es distinta de la versión del launcher global, EmbrAIon instala el paquete exacto desde PyPI en una caché aislada:

```text
~/.embraion/versions/<version>/
```

El primer uso de una versión puede necesitar descargarla desde PyPI. Los usos posteriores reutilizan la caché. Así, distintos proyectos en el mismo PC con Windows o Mac pueden utilizar diferentes versiones de EmbrAIon con una sola instalación global del CLI.

Los Project Overlay (Capas del proyecto) creados por `v0.1.0` pueden contener `0.1.0-dev`. El nuevo resolver interpreta ese pin heredado como la distribución publicada `0.1.0`.

`embraion init` y `embraion update` se ejecutan intencionadamente en el launcher global y no se delegan a la versión antigua del proyecto:

- `embraion init` incorpora un repositorio nuevo a la versión del launcher global;
- después de `pipx upgrade embraion`, `embraion update` mueve únicamente el proyecto actual;
- `embraion update --framework-version X.Y.Z` fija explícitamente una versión publicada, que el siguiente comando normal resolverá automáticamente.

Para desarrollar EmbrAIon, `EMBRAION_HOME` sigue siendo una selección explícita del checkout del framework. También se puede desactivar la resolución automática con `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.

## Cómo fluye una tarea por EmbrAIon

```text
Objetivo del usuario
  ↓
Project Overlay + catálogo del Core
  ↓
Reglas / agentes / habilidades / flujos necesarios
  ↓
Clase de datos + perfil de acceso + complejidad
  ↓
Adaptador del cliente + ruta del modelo
  ↓
Implementación
  ↓
Validación
  ↓
Revisión independiente
  ↓
Verificación final
  ↓
Entrega / merge humano
```

Para trabajo importante que se beneficie de una especificación formal, se recomienda [Spec Kit](https://github.com/github/spec-kit) como complemento independiente. Ayuda con especificación y planificación, pero no sustituye las reglas del Core, la verdad del proyecto, los contratos de compatibilidad ni la evidencia de validación.

## CLI

Comandos principales:

```text
embraion init
embraion install
embraion update
embraion sync
embraion validate
embraion doctor
```

### Routing (Enrutamiento)

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

### Plan de ejecución acotado

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path "src/**"
```

La ejecución con permiso de escritura exige rutas de propiedad explícitas y no puede planificarse desde la rama estable `main`/`master`.

### Session (Sesión)

```bash
embraion session start --session-id task-001 --task "Implement feature" --role lead --host codex --access plan
embraion session show
embraion session set --state review --validation passed
```

### Security (Seguridad)

```bash
embraion security scan --path .
```

### Inventario MCP

```bash
embraion mcp inventory
```

El inventario se guarda de forma segura en `.embraion/state/`. Se pueden registrar nombres de variables de entorno, pero no se guardan valores secretos de forma intencionada.

### Árboles de trabajo Git

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree salvage /path/to/worktree
```

`gc` funciona como vista previa por defecto. Para eliminar candidatos seguros es necesario indicar `--apply`.

### Learning (Aprendizaje)

```bash
embraion learning observe \
  --id repeated-review-gap \
  --kind repeated-failure \
  --target-type skill \
  --target-id review \
  --summary "Repeated review gap"
```

El proceso es:

```text
observación → acumulación de evidencia → propuesta → aprobación → promoción
```

La promoción nunca modifica el Core automáticamente. El cambio final sigue necesitando el proceso normal de ingeniería, revisión y validación.

### Eval (Evaluación de comportamiento)

```bash
embraion eval run --case reviewer-readonly --record path/to/execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

## Generar representaciones de adaptadores

```bash
embraion sync --host all --output build/generated --force
```

Los archivos generados son representaciones derivadas y pueden recrearse en cualquier momento. La política canónica permanece en `core/`.

## Estructura del repositorio

```text
brand/         marca y recursos para README
core/          reglas, agentes, habilidades, flujos, enrutamiento y conocimiento canónicos
adapters/      integraciones con Codex, Copilot, Claude Code, Portable y proveedores API
tools/         CLI, ejecución, aprendizaje, seguridad, MCP, árboles de trabajo, validación y sincronización
schemas/       contratos legibles por máquina
templates/     plantillas de Project Overlay
docs/          documentación canónica en inglés
localization/  documentación localizada
tests/         pruebas unitarias y de integración deterministas
evals/         escenarios de comportamiento, referencias, evaluadores, muestras e informes
examples/      ejemplos de integración
```

## Validación y CI

Cada push y pull request ejecuta validación de esquemas y catálogo, comprobación de localizaciones, pruebas unitarias y de integración, análisis de seguridad, generación de todas las representaciones de clientes y evaluaciones básicas de comportamiento.

Los releases con Git tag generan archivos de código fuente, Codex, Copilot, Claude Code y Portable.

## Documentación

Documentación canónica en inglés: [docs/](../docs/README.md)

Documentación en español: [localization/docs/es/](docs/es/README.md)

## Licencia y marca

El código fuente y la documentación de EmbrAIon se distribuyen bajo [MIT License](../LICENSE), salvo que un archivo o directorio indique expresamente lo contrario.

Los nombres **EmbrAIon** y **GORYNED**, los logotipos, marcas denominativas, signos visuales y archivos de `brand/assets/` **no se licencian bajo MIT**. Política canónica: [TRADEMARKS.md](../TRADEMARKS.md).

## Estado actual

EmbrAIon está en fase **preestable**. La arquitectura y la primera versión ejecutable del CLI ya existen, pero el contrato público de compatibilidad todavía no está congelado.

Antes de la primera versión estable todavía pueden cambiar los catálogos de modelos, las representaciones generadas, la cobertura de validación, las reglas de seguridad, la instalación y el empaquetado de releases.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>Última actualización: 2026-09-23 22:00 UTC</sub>
