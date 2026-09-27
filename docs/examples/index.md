# Usage Examples

EmbrAIon ships with three public reference projects. They exist to show how the engineering system composes with real repository shapes.

| Example | What it demonstrates |
| --- | --- |
| Minimal | Smallest complete project overlay and project knowledge |
| Python | Normal application code and tests with EmbrAIon layered around them |
| Unity | Runnable Unity 6 project with ordinary C# architecture and EmbrAIon project integration |

CI copies these examples into temporary directories and exercises the real consuming-project lifecycle. Generated host projections are recreated instead of being treated as canonical source.

Choose [Minimal](minimal.md), [Python](python.md), or [Unity](unity.md).


The three baseline examples intentionally stay small and do not simulate paid provider calls. For advanced provider-neutral runtime configuration, use [Execution & providers](../configuration/execution.md) and [Pricing & cost](../configuration/pricing.md).
