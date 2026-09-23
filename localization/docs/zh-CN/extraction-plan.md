# Framework 提取计划

应以非破坏方式从现有项目中分离 framework。

## 顺序

1. 审计现有 reusable 与 project-specific 内容。
2. 建立 EmbrAIon canonical structure。
3. 向 upstream 提取 reusable capabilities。
4. 在可行时，在 parity validation 期间同时保持旧路径与新路径可用。
5. 验证 behavior、routing、review 与 tooling parity。
6. 将 consuming projects 切换到 versioned framework。
7. 只有在 parity 被证明后才删除 duplicated legacy definitions。

目标是在 ownership boundary 被证明之前避免破坏性迁移。
