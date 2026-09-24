# Project Overlay（项目叠加层）

使用 EmbrAIon 的仓库把项目配置存放在 `.embraion/` 下。

各文件职责：

- `project.yaml`：EmbrAIon repository/version、项目身份和 `capabilities`；
- `knowledge.yaml`：project knowledge 引用和 context-selection metadata；
- `policy.yaml`：source classes、review policy 和 privacy；
- `routing.yaml`：可选的 model/effort/options override；
- `validation.yaml`：validation profiles；
- `agents.yaml`：project-specific agents。

Project Overlay 可以增加更严格的规则，但不得暗中削弱 Core（核心）的强制限制。

## 自动版本解析

对于普通命令，全局 launcher 会找到最近的 `.embraion/project.yaml`，读取 `framework.version` 并与自身版本比较。如果不同，EmbrAIon 会在 `~/.embraion/versions/<version>/` 中创建隔离 runtime，并从 PyPI 安装准确的 `embraion==<version>` 包。

随后命令会由该缓存版本执行。因此，一台电脑只需一个全局 launcher，不同仓库仍可以固定在不同的 EmbrAIon 发布版本。

`embraion init` 和 `embraion update` 会刻意绕过项目 runtime：

- `init` 创建模块化配置并写入全局 launcher 版本；
- `update` 只修改当前仓库的版本固定；
- `--framework-version` 可以明确选择某个具体发布版本。

`EMBRAION_HOME` 是开发时的明确 override，并会在当前进程中关闭自动版本委派。

项目仓库本身仍然是产品规格、架构、兼容性契约、验证证据和领域知识的规范来源。
