<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — GORYNED 的 AI-First Engineering System" width="100%">
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README.ru.md">Русский</a> ·
  <strong>简体中文</strong>
</p>

# EmbrAIon

**GORYNED 的 AI-First Engineering System**

> Where sparks become AI-built products

> 本文件是规范英文 README 的翻译。如有差异，以英文版本为准。

EmbrAIon 是一个可复用的 AI-First Engineering System，用于组织 agents、skills、workflows、model routing、validation、review、tools 和 project orchestration。

本仓库是可复用工程系统的 upstream 单一事实来源。具体产品的知识与约束应保留在 project overlays 中，而不是进入 EmbrAIon Core。

## Core

Core 按 capability 类型组织：

- **Rules** — 必须遵守、禁止或受保护的行为。
- **Agents** — 职位式角色：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher、Steward。
- **Skills** — 可重复执行的流程。
- **Workflows** — 有序 orchestration。
- **Routing** — complexity、privacy、fallback 与 health policy。
- **Knowledge** — 共享事实、concepts 和 terminology。

Agents 保持 model-neutral。具体模型、effort、lifecycle、pricing 与 host selectors 由对应 adapter 的 model catalog 维护。

## 架构

```text
EmbrAIon Core
    +
Tool / provider adapters
    +
Project overlay
    =
有效工程上下文
```

## 仓库结构

```text
brand/         品牌规范与 README assets
core/          vendor-neutral rules、agents、skills、workflows、routing、knowledge
adapters/      Codex、Copilot、provider 与 transport integrations
tools/         runtime、worktree、CLI、install、doctor、sync、validation
schemas/       machine-readable contracts
templates/     project overlay templates
docs/          architecture 与 engineering documentation
examples/      reference integrations
tests/         framework validation
localization/  README translations
```

## Spec Kit

Spec Kit 是推荐的外部 companion capability，适用于 substantial features、cross-cutting architecture 与 specification-driven 工作。

它不属于 EmbrAIon Core，也不能替代 Core rules、project architecture、product truth、compatibility contracts 或 validation evidence。

## Project overlays

使用 EmbrAIon 的项目在自己的仓库中维护 domain truth，并通过 `.embraion/project.yaml` 引用固定版本的 EmbrAIon。

Generic reusable behavior 上移到 EmbrAIon；product semantics、compatibility contracts、domain agents 与 application-specific knowledge 仍保留在项目中。

## 状态

EmbrAIon 目前处于 foundation 阶段。初始 model catalogs 来自已验证的 routing registry 和 observed model snapshot，之后由对应 adapters 独立维护。

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **by GORYNED**

<sub>最后更新：2026-09-23 19:04 UTC</sub>
