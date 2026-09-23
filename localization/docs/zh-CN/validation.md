# Validation

Validation 是 framework change 保持预期 contracts 的 evidence。

Validation system 分层发展：

- schema validation；
- capability-reference validation；
- adapter/projection parity；
- routing-policy validation；
- installation 与 doctor checks；
- security 与 integration inventory checks；
- integration tests；
- behavioral eval 与适用 baseline 的对比。

PASS 应明确说明实际检查了什么，而不只是返回 generic success。

Behavioral improvement 与 deterministic correctness 分开评估。更好的 aggregate eval score 永远不能覆盖 security、privacy、permission、compatibility 或 mutation 的 hard failure。
