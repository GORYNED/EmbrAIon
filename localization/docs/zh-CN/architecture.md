# 架构

## 层次

1. **Core（核心）** — 与具体模型和供应商无关的规则、代理角色、技能、工作流、路由和知识。
2. **Adapters（适配器）** — 面向 AI host、transport 和可移植软件包的投影层。
3. **Tools（工具）** — 用于状态、学习、安全、MCP、Git worktree、验证、同步、安装、诊断和 CLI 的确定性逻辑。
4. **Project Overlay（项目叠加层）** — 项目专属知识、约束和可选 routing override。
5. **External Capabilities（外部能力）** — 推荐或可选的附加系统与集成。
6. **Evidence（证据）** — 测试、行为评估、参考结果和报告。

## 代理模型

Core 使用职位式角色：Lead、Worker、Reviewer、Architect、Analyst、Validator、Researcher 和 Steward。选择角色并不意味着选择某个具体模型。

## 模型选择的归属

Core 使用面向任务的 route class 对工作进行分类。EmbrAIon 不维护全局模型目录、价格或 lifecycle。AI host 负责模型可用性和默认/自动选择。项目仅在需要时把自己的 host-specific override 保存在 `.embraion/routing.yaml` 中。

## State 与 Learning

执行状态被标准化为 privacy-safe 记录。重复证据可以形成改进候选，但修改 Core 仍需要评审和明确批准。

## Spec Kit

Spec Kit 作为外部能力接入，不替代 Core 规则、项目事实或 validation evidence。
