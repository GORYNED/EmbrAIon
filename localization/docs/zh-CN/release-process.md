# 发布流程

EmbrAIon 使用带版本管理的系统发布方式。

预期约定如下：

- GitHub 是事实来源。
- EmbrAIon 发布版本使用 Git 标签并配套文档。
- 新项目从已经发布的版本开始使用。
- 现有项目在 `.embraion/project.yaml` 中固定使用某个明确的 EmbrAIon 版本。
- 全局 launcher 会把已发布的版本固定自动解析为 `~/.embraion/versions/` 中的隔离 runtime。
- 升级必须有意进行，并附带变更说明和验证；`embraion update` 只修改当前项目的版本固定。

当前仓库仍处于稳定版之前的阶段。在发布第一个稳定版本之前，发布流程还会继续加强。
