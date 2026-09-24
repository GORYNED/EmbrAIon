# Routing（路由）

EmbrAIon 的路由完全与具体模型无关。

Core 使用 `bounded-read`、`bounded-write`、`ordinary`、`substantial`、`complex` 和 `critical` 对任务进行分类。这些类别描述工作类型和风险，而不是模型强弱、价格、供应商或具体模型名称。

如果项目没有定义 override，所选 AI host 保留自己的默认或自动模型选择。需要显式选择时，项目可以把任意 host-specific 的 `model`、`effort` 和 `options` 写入 `.embraion/routing.yaml` → `overrides`。

用户可以直接要求仓库中的 AI 根据当前可用模型配置 EmbrAIon。安装的 `routing-configuration` skill 会告诉 AI 应把 override 写到哪里，以及哪些策略不能被削弱。

EmbrAIon 不维护规范模型目录。Privacy、access、ownership、validation 和 review 始终独立于模型选择。
