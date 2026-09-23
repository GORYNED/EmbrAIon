# 架构

## 层次

1. **Core** — vendor-neutral rules、agents、skills、workflows、routing 和 knowledge。
2. **Adapters** — 具体 hosts、models、providers、transports 与 package projections。
3. **Tools** — deterministic runtime、learning、security、MCP inventory、worktree、validation、sync、install、doctor 与 CLI。
4. **Project overlay** — consuming project 的 agents、domains、source classes、compatibility rules 与 product knowledge。
5. **External capabilities** — 推荐或可选的 companion systems 与 domain-specific integrations。
6. **Evidence** — deterministic tests、behavioral evals、baselines 与 reports。

## Agent 模型

Core agents 使用职位式名称：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher、Steward。

Project-specific domain specialists 留在 consuming project 中，而不是成为 generic Core roles。

## State 与 learning

Runtime state 被标准化为 privacy-safe session records。重复结果可以形成 learning candidates，但 canonical capability promotion 始终需要 review 与 approval。

## Integrations

外部 server/tool 配置独立于 Core policy 进行 inventory。Inventory 保存 metadata 与 drift，不保存 secret values。

## 模型 ownership

Core routing 选择 provider-neutral route classes。Adapter catalogs 管理当前 model identities、effort、pricing、lifecycle 与 host selectors。

## Spec Kit

Spec Kit 作为外部 capability 组合使用。EmbrAIon 推荐它用于 substantial specification work，但不会把其 skills、templates 或 runtime 内置到 Core。
