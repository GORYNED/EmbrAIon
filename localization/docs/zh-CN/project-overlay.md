# Project Overlay（项目叠加层）

使用 EmbrAIon 的仓库通过 `.embraion/project.yaml` 明确接入系统。

项目叠加层记录：

- 声明的 EmbrAIon 仓库和系统版本；
- 项目标识；
- 项目知识所在位置；
- 仅属于该项目的 Agent（代理角色）；
- 外部能力。

项目叠加层可以增加更严格的规则，但不得暗中削弱 Core（核心）的强制限制。

## 自动版本解析

公共版本 `v0.1.0` 会记录项目版本，但还不会自动解析它。当前 `main` 已为下一版本实现 resolver。

对于普通命令，全局 launcher 会找到最近的 `.embraion/project.yaml`，读取 `framework.version` 并与自身版本比较。如果不同，EmbrAIon 会在 `~/.embraion/versions/<version>/` 中创建隔离 runtime，并从 PyPI 安装准确的 `embraion==<version>` 包。

随后命令会由该缓存版本执行。因此，一台电脑只需一个全局 launcher，不同仓库仍可以固定在不同的 EmbrAIon 发布版本。

`embraion init` 和 `embraion update` 会刻意绕过项目 runtime：

- `init` 把全局 launcher 版本写入新的 Project Overlay；
- `update` 只修改当前仓库的版本固定；
- `--framework-version` 可以明确选择某个具体发布版本。

首个版本写入的旧标记 `0.1.0-dev` 会自动映射到已发布的 `0.1.0` 包。

`EMBRAION_HOME` 是开发时的明确 override，并会在当前进程中关闭自动版本委派。

项目仓库本身仍然是产品规格、架构、兼容性契约、验证证据和领域知识的规范来源。
