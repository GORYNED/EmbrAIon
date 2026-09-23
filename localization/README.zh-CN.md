<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — GORYNED 的 AI-First Engineering System" width="100%">
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <strong>简体中文</strong>
</p>

# EmbrAIon

**[GORYNED](https://goryned.com) 的 AI-First Engineering System**

> Where sparks become AI-built products（让火花化为 AI 构建的产品）

EmbrAIon 是一个可复用的 AI-First Engineering System，用于组织 agents、skills、workflows、model routing、validation、review、tooling 与 project orchestration。

## EmbrAIon 的作用

EmbrAIon 将工程系统拆分为彼此独立的组成部分：

- **Agent（代理角色）** — 谁负责执行工作：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher 或 Steward。
- **Skill（技能）** — 如何执行一类可重复的工作。
- **Rule（规则）** — 哪些行为是必须的、禁止的或受保护的。
- **Workflow（工作流）** — 各项能力按照什么顺序组合执行。
- **Routing（路由）** — 哪种访问配置、模型级别、客户端和 provider 可以执行任务。
- **Adapter（适配器）** — 如何将 EmbrAIon 的规范能力映射到 Codex、GitHub Copilot、Claude Code、API providers 或中立的 Portable package。
- **Tool（工具）** — 确定性的可执行逻辑，例如 validation、security scan、Git worktree 管理、同步和诊断。
- **Eval（行为评估）** — 检查 AI 是否真正遵循预期的工程约束。

`core/catalog.yaml` 是能力发现索引。系统无需为每个任务加载整个 EmbrAIon，而是只加载与当前工作相关的规则、角色、技能和工作流。

## Operational layers

- **Runtime** — privacy-safe 的统一 session/task state。
- **Learning** — 重复模式成为经过 review 的 improvement candidates，不会自动修改 Core。
- **Security** — 对 permissions、credentials、routes、integrations 与 generated configuration 进行 deterministic scan。
- **MCP inventory** — 统一记录 server state 与 drift，但不保存 secret values。
- **Worktrees** — isolated workspace lifecycle、safe cleanup 与 salvage。
- **Evals** — behavioral cases、baselines 与 comparison reports。

## 文档

完整简体中文文档：[localization/docs/zh-CN](docs/zh-CN/README.md)。

## 许可证与品牌

除非某个文件或目录另有明确说明，EmbrAIon 的源代码与文档采用 [MIT License](../LICENSE)。

**EmbrAIon** 与 **GORYNED** 名称、logos、wordmarks、visual marks 以及 `brand/assets/` 中的文件**不属于 MIT 授权范围**。MIT License 不授予 trademark 或 brand identity 权利。规范政策见 [TRADEMARKS.md](../TRADEMARKS.md)。

## Spec Kit

Spec Kit 是推荐的独立 companion capability，适用于 substantial specification-driven 工作。它不会替代 Core rules、project truth、compatibility contracts 或 validation evidence。

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>最后更新：2026-09-23 20:40 UTC</sub>
