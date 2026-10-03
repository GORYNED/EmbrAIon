---
name: unity-lifecycle-review
description: Review a Unity component's event, asynchronous, and native-resource lifetime across real project play-mode settings.
---

# Unity Lifecycle Review

Load for a Unity lifecycle bug or a change to callbacks, subscriptions, coroutines, async work, or native resources. Skip for pure data code with no Unity object lifetime or event ownership.

1. Read the project's Unity version and Play Mode/domain-reload settings, affected component ownership, and coding-standard exceptions. Map `Awake`, `OnEnable`, `Start`, `OnDisable`, `OnDestroy`, scene transitions, and object pooling paths that actually occur.
2. Match every subscription, callback, coroutine, task, and native resource to an owner and a release point. Check cancellation and stale continuation behavior when objects disable or destroy; account for Unity object lifetime semantics and any project-specific async framework.
3. Examine disabled/re-enabled, duplicate enable, scene unload, and domain reload configurations relevant to the project. Identify leaks, duplicate listeners, access after destroy, and native handles left alive. Do not impose a universal callback order or generic disposal pattern without project evidence.
4. Validate the affected lifecycle with focused Play Mode or Editor tests and targeted manual reproduction when automation cannot express the path.

Output: lifecycle trace, ownership/release table or concise mapping, concrete findings and changes, observed tests, and unresolved mode-specific risk. Follow Core review and validation gates.
