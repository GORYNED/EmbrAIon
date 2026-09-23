# Capability 模型

EmbrAIon 使用明确的 capability 类型，避免混合 policy、responsibility、procedure、orchestration 与 facts。

| 类型 | 目的 |
| --- | --- |
| Rule | 必须 / 禁止 / 受保护的行为 |
| Agent | Responsibility 与 ownership |
| Skill | 可重复 procedure |
| Workflow | 有序 orchestration |
| Routing | Model/provider/effort/execution 选择 |
| Tool | Deterministic operation |
| Adapter | Host/provider integration |
| Knowledge | Facts 与 architecture |

Canonical capability 应只有一个主要类型。优先通过 cross-reference 连接能力，而不是在多个类型中复制同一内容。
