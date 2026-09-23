# Spec Kit

Spec Kit 是 EmbrAIon 推荐的外部 companion。

当 substantial feature work 需要明确 specification、clarification、planning、task decomposition、checklists 或 implementation tracking 时使用它。

不要把 upstream Spec Kit internals 复制进 EmbrAIon Core。保持其独立可更新，并通过 documented workflows 或 host adapters 集成。

Spec Kit artifacts 可以细化工作，但不能覆盖：

- EmbrAIon Core rules；
- project architecture；
- product truth；
- compatibility contracts；
- validation evidence；
- human merge gates。
