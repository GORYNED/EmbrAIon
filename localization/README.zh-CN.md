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

`embraion validate` 检查当前 EmbrAIon 安装所携带的系统数据。`embraion doctor` 还会检查当前项目或 Git worktree 的上下文，因此请在需要诊断的仓库中运行，或者在空测试目录中将其作为安装检查使用。

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

### 当前 `init`、`install` 和 `sync` 的行为

- `embraion init` 创建仓库本地的 `.embraion/project.yaml` 叠加层。
- `embraion install` 使用**当前正在运行的 CLI** 可访问的系统数据生成一个客户端表示，并把它复制到指定目录。
- `embraion sync` 在输出目录中生成可重新创建的表示；它不会自动发现、初始化或接入这台电脑上的所有项目。

### v0.1.x 中的项目版本固定

`.embraion/project.yaml` 会记录系统版本，但当前 `v0.1.x` CLI **不会自动解析并运行该记录版本**。`install` 和 `sync` 使用当前正在运行的 EmbrAIon 可执行程序所携带的系统数据。

如果需要严格可复现，请运行与项目记录版本一致的 CLI/系统发行版本。因此在 `v0.1.x` 中，项目版本字段是兼容性声明和更新边界，还不是自动选择每个项目 runtime 版本的解析器。

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
