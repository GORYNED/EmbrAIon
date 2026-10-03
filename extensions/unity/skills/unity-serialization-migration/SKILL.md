---
name: unity-serialization-migration
description: Plan and validate a scoped Unity serialized identity or data-shape change against real assets and scenes.
---

# Unity Serialization Migration

Load when changing serialized C# fields, types, namespaces, assemblies, asset references, or Unity metadata in a Unity project. Skip for code that is demonstrably outside Unity serialization and persistence surfaces.

1. Read the project's Unity version, architecture, source-authority, coding standard, compatibility and persistence contracts. Identify the affected scenes, prefabs, ScriptableObjects, saved data, assemblies, and actual consumers. Check whether domain-specific exceptions or package boundaries apply; do not create one `.asmdef` per folder by default.
2. Inventory old and new identities: asset GUID and `.meta`, script GUID, namespace/type/assembly identity, serialized field name and type, `SerializeReference` concrete types, and managed references. Decide which identities must remain stable and where a deliberate migration is needed.
3. Prefer the project's already installed Unity Editor APIs or official Unity tooling for mutations of serialized assets. Preserve GUIDs and `.meta` when moving assets, update references in the same scoped change, and use targeted Unity migration attributes only when their documented semantics fit the actual old/new shape. Do not apply `MovedFrom` indiscriminately.
4. Validate representative old assets and scenes in the project's Unity version. Check inspector values, prefab overrides, managed references, load/save round trips where relevant, and affected Player builds or tests when required by impact. Keep backups or a recovery path for destructive asset migrations.

Output: old-to-new identity map, affected assets and consumers, migration sequence, exact Editor/Player evidence, rollback limit, and unresolved data-loss risk. Follow Core's compatibility-migration and validation procedures and project privacy/review gates.
