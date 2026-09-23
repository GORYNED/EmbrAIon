<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — GORYNED 的 AI-First Engineering System" width="100%">
</p>

<p align="center">
  <a href="../README.md">英文</a> ·
  <a href="README.ru.md">Русский</a> ·
  <strong>简体中文</strong> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.hi.md">हिन्दी</a>
</p>

# EmbrAIon

**[GORYNED](https://goryned.com) 的 AI-First Engineering System**

> Where sparks become AI-built products（让火花化为 AI 构建的产品）

EmbrAIon 是一个可复用的 AI-First Engineering System，用于通过明确的 Agent（代理角色）、Skill（技能）、Workflow（工作流）、Routing（路由）、访问控制、验证、审查、工具和 Project Overlay（项目叠加层）来组织 AI 辅助软件工程。

## EmbrAIon 的作用

EmbrAIon 将工程系统拆分为彼此独立的组成部分：

- **[Agent（代理角色）](../core/agents/)** — 谁负责执行工作：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher 或 Steward。
- **[Skill（技能）](../core/skills/)** — 如何执行一类可重复的工作。
- **[Rule（规则）](../core/rules/)** — 哪些行为是必须的、禁止的或受保护的。
- **[Workflow（工作流）](../core/workflows/)** — 各项能力按照什么顺序组合执行。
- **[Routing（路由）](../core/routing/)** — 哪种访问配置、模型级别、客户端和 Provider（提供方）可以执行任务。
- **[Adapter（适配器）](../adapters/)** — 如何将 EmbrAIon 的规范能力映射到 [Codex](https://openai.com/codex/)、[GitHub Copilot](https://github.com/features/copilot)、[Claude Code](https://code.claude.com/docs/en/overview)、API 提供方或中立的 Portable 包。
- **[Tool（工具）](../tools/)** — 确定性的可执行逻辑，例如验证、安全扫描、Git worktree 管理、同步和诊断。
- **[Eval（行为评估）](../evals/)** — 检查 AI 是否真正遵循预期的工程约束。

`core/catalog.yaml` 是能力发现索引。系统无需为每个任务加载整个 EmbrAIon，而是只加载与当前工作相关的规则、角色、技能和工作流。

## 运行层

- **运行时** — 使用不泄露隐私的统一会话与任务状态。
- **学习机制** — 重复出现的模式只有经过审查后才会成为改进候选，不会自动修改 [Core（核心）](../core/)。
- **安全** — 对权限、凭据、路由、集成和生成配置执行确定性检查。
- **MCP 清单** — 统一记录服务器状态和配置漂移，但不保存秘密值。
- **Git worktree** — 管理隔离工作区的生命周期、安全清理和证据恢复。
- **Eval（行为评估）** — 管理行为测试、基线和比较报告。

## 安装

### 每台电脑只安装一次

EmbrAIon 通过 [PyPI](https://pypi.org/project/embraion/) 分发。正常使用时，在每台 Windows 或 macOS 电脑上通过 `pipx` 安装一次 CLI 即可。无需克隆仓库，也无需执行 `git clone`。

如果您明确自行管理 Python 环境，也可以使用普通的 `pip` 安装；对于 CLI，仍推荐使用 `pipx`。

#### Windows

EmbrAIon 需要 Python 3.11 或更高版本。

1. 检查 Python：

```powershell
py --version
```

如果 `py` 不可用或版本低于 3.11，请从 [Python 官方 Windows 下载页面](https://www.python.org/downloads/windows/) 安装当前 Python 3，然后重新打开 PowerShell。

2. 安装 [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) 并把命令目录加入 `PATH`：

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

3. 关闭并重新打开 PowerShell，然后安装 EmbrAIon：

```powershell
pipx install embraion
```

如果您明确使用自己管理的 Python 环境而不是 `pipx`，也支持：

```powershell
py -m pip install embraion
```

#### macOS

如果已经安装 [Homebrew](https://brew.sh/)，最简单的方式是：

```bash
brew install pipx
pipx ensurepath
```

打开新的 Terminal 窗口，然后安装 EmbrAIon：

```bash
pipx install embraion
```

如果不使用 Homebrew，请先检查 Python：

```bash
python3 --version
```

如果 Python 不存在或版本低于 3.11，请从 [Python 官方 macOS 下载页面](https://www.python.org/downloads/macos/) 安装当前 Python 3。然后安装 `pipx`：

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

打开新的 Terminal 窗口并运行：

```bash
pipx install embraion
```

如果您自行管理 Python 环境，也支持 `python3 -m pip install embraion`。

#### 验证

```bash
embraion --version
embraion validate
embraion doctor
```

`embraion validate` 检查当前 EmbrAIon 安装所携带的系统数据。`embraion doctor` 默认输出适合人阅读的诊断报告，并会自动判断当前目录是否位于 Git 仓库或 EmbrAIon 项目中。在项目之外，它只执行安装和系统诊断，不会递归扫描用户主目录或其他普通文件夹。需要机器可读的结构化输出时，请使用 `embraion doctor --json`。

#### 更新

```bash
pipx upgrade embraion
```

通过 `pipx` 的全局安装会让这台电脑上的任意项目都能调用 `embraion` 命令。它**不会自动在所有仓库中启用 EmbrAIon**，也不会在后台修改这些仓库。

## 将 EmbrAIon 添加到每个项目

每个仓库都需要明确选择接入 EmbrAIon。请在项目根目录执行：

```bash
cd /path/to/your/project
embraion init
```

默认情况下，`init` 会使用目录名作为项目名。只有需要覆盖该名称时才使用 `--name MyProject`。

这会创建：

```text
.embraion/
└── project.yaml
```

Project Overlay（项目叠加层）会把声明的 EmbrAIon 版本和项目专用配置记录在 Git 中。

### 安装所需客户端的 Adapter（适配器）表示

为仓库使用的每个 AI 客户端安装对应表示。

[Codex](https://openai.com/codex/)：

```bash
embraion install --host codex --destination .
```

[GitHub Copilot](https://github.com/features/copilot)：

```bash
embraion install --host copilot --destination .
```

[Claude Code](https://code.claude.com/docs/en/overview)：

```bash
embraion install --host claude-code --destination .
```

Portable 包：

```bash
embraion install --host portable --destination ./vendor/embraion
```

如果一个项目同时使用多个客户端，请为每个客户端分别执行一次对应的 `install` 命令。已有的生成文件默认不会被覆盖；只有明确需要替换时才使用 `--force`。

### 自动解析项目版本

`v0.2.0` 加入按项目自动解析 EmbrAIon 版本的能力。

对于普通命令，全局 `embraion` 会从当前目录向上查找最近的 `.embraion/project.yaml`，读取其中的 `framework.version`。如果项目固定的版本与全局 launcher 不同，EmbrAIon 会从 PyPI 安装准确版本到隔离缓存：

```text
~/.embraion/versions/<version>/
```

某个版本第一次使用时可能需要从 PyPI 下载；之后会直接复用缓存。因此，同一台 Windows PC 或 Mac 只需一个全局 CLI，不同仓库仍可使用不同的 EmbrAIon 版本。

由 `v0.1.0` 创建的旧 Project Overlay（项目叠加层）可能包含 `0.1.0-dev`。新的 resolver 会把这个旧版本标记自动映射到已发布的 `0.1.0` 包。

`embraion init` 和 `embraion update` 会刻意由全局 launcher 执行，而不会委派给项目中的旧版本：

- `embraion init` 使用当前全局 launcher 版本初始化新仓库；
- 执行 `pipx upgrade embraion` 后，`embraion update` 只更新当前项目；
- `embraion update --framework-version X.Y.Z` 可以明确固定某个发布版本，下一条普通命令会自动解析它。

开发 EmbrAIon 本身时，`EMBRAION_HOME` 仍表示明确使用指定的 framework 源码目录。也可以通过 `EMBRAION_DISABLE_VERSION_RESOLUTION=1` 显式关闭自动解析。

### 查看状态和缓存

查看全局 launcher 版本、当前项目、固定版本、解析后的 runtime、缓存状态以及检测到的客户端表示：

```bash
embraion status
```

机器可读输出使用 `embraion status --json`。

查看缓存的 runtime：

```bash
embraion cache list
```

先以预览方式检查可清理内容：

```bash
embraion cache prune
```

只有添加 `--apply` 才会真正删除。还可以包含长时间未使用的 runtime：

```bash
embraion cache prune --older-than 90
embraion cache prune --older-than 90 --apply
```

当前 launcher 版本和当前项目需要的 runtime 不会因时间条件被删除。

### 命令帮助

查看分类后的完整命令目录：

```bash
embraion help
```

查看某条命令或嵌套命令的详细帮助：

```bash
embraion help status
embraion help cache prune
```

也可以继续使用标准形式 `embraion <command> --help`。

## 文档

完整简体中文文档：[localization/docs/zh-CN](docs/zh-CN/README.md)。

## 许可证与品牌

除非某个文件或目录另有明确说明，EmbrAIon 的源代码与文档采用 [MIT License](../LICENSE)。

**EmbrAIon** 与 **GORYNED** 的名称、徽标、文字标识、视觉标识以及 `brand/assets/` 中的文件**不属于 MIT 授权范围**。MIT License 不授予商标或品牌标识权利。规范政策见 [TRADEMARKS.md](../TRADEMARKS.md)。

## [Spec Kit](https://github.com/github/spec-kit)

[Spec Kit](https://github.com/github/spec-kit) 是推荐的独立配套能力，适合需要严格规格驱动的较大工作。它不会替代 [Core（核心）](../core/) 规则、项目事实来源、兼容性契约或验证证据。

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>最后更新：2026-09-23 22:00 UTC</sub>
