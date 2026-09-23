# 模型路由

Routing 是 EmbrAIon 的一级 capability。

Canonical routing policy 决定 task characteristics 如何映射到 model/provider 选择、reasoning effort、execution permissions、escalation 与 review requirements。

Provider adapters 负责 invocation mechanics，但不拥有 canonical decision policy。

更详细的 routing contracts 会随着 framework 的演进被独立版本化。
