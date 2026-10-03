---
name: unity-player-validation
description: Choose and run relevant Unity Editor and Player checks while keeping platform claims tied to actual execution.
---

# Unity Player Validation

Load when a Unity change can differ between Editor and Player, affects a target platform, or requires a build/runtime claim. Skip Player execution for a documentation-only or other trivial reversible change when no project gate requires it.

1. Identify the project's Unity version, target platform, scripting backend, build configuration, symbols, and configured validation profile. Map risks to Edit Mode, Play Mode, build, and actual Player runtime checks.
2. For IL2CPP or other ahead-of-time targets, check concrete reflection, generic instantiation, code stripping, serialization, native plugin, and platform API paths affected by the change. Use actual project link settings and build logs; do not assume Editor success covers them.
3. Run the smallest checks that can falsify the risk. Capture exact Unity version, command or profile, platform, backend, result, and relevant logs. A successful build verifies compilation and packaging; claim runtime behavior only after running the Player on the stated target.
4. Report unavailable devices, build infrastructure, or unexecuted platforms as limitations and route required missing evidence through the project's validation gate.

Output: risk-to-check matrix, fresh Editor/build/Player results with environment, and precise limits. Follow Core test-design and validation procedures; do not auto-install Unity or a test package.
