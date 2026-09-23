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

> Where sparks become AI-built products

> 本文件是规范英文 README 的翻译。如有差异，以英文版本为准。

EmbrAIon 是一个可复用的 AI-First Engineering System，用于组织 agents、skills、workflows、model routing、validation、review、tooling 与 project orchestration。

## Core

Core 按 capability 类型组织：

- **Rules** — 必须遵守、禁止或受保护的行为。
- **Agents** — 职位式角色：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher、Steward。
- **Skills** — 仅在相关任务中加载的流程。
- **Workflows** — 工作、review 与 learning 的 orchestration。
- **Routing** — access、complexity、privacy、fallback 与 health。
- **Knowledge** — 共享 concepts 与 terminology。

`core/catalog.yaml` 决定特定任务真正需要加载哪些 capabilities。

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

<sub>最后更新：2026-09-23 20:30 UTC</sub>
