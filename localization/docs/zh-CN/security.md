# Security

EmbrAIon 将 execution permissions、data classification、provider eligibility、external integrations、generated configuration、credentials 与 mutation rights 视为可强制执行的 engineering constraints。

Security policy 属于 Core rules 与 routing。Host/provider adapters 实现 mechanics。`tools/security/` 执行 deterministic inspection，`tools/mcp/` 负责标准化 external server inventory 与 drift。

Framework 应在以下情况下 fail closed：

- task 无法安全分类；
- provider 不允许处理相关数据；
- integration 的 access 未知或意外扩大；
- secret 出现在 persisted configuration；
- generated configuration 与 approved source 发生 drift；
- writable action 超出其 access profile。

Security findings 是 evidence，不是削弱 controlling policy 的许可。
