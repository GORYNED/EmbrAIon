# Optional Unity Capabilities

The optional `unity` extension contains original EmbrAIon procedures for Unity engineering. Its manifest is `extensions/unity/manifest.yaml`; it is separate from vendor-neutral Core and does not alter a Unity project unless deliberately included. A consuming project remains the authority for its Unity version, assembly layout, coding standards, persistence formats, target platforms, and validation commands. These procedures do not install Unity, an AI plugin, or project packages.

| Skill | Use when | Evidence to keep |
| --- | --- | --- |
| `unity-serialization-migration` | Serialized field, type, asset, namespace, or assembly identity changes | Old/new identity map, representative assets, migration and recovery results |
| `unity-lifecycle-review` | Callback, subscription, async, pooling, or native-resource lifetime changes | Ownership/release mapping and relevant Play Mode results |
| `unity-player-validation` | A Player or target-platform behavior claim needs evidence | Unity version, build/backend/platform, actual Editor/build/Player results |
| `unity-asset-audit` | A named asset scope or broken-reference symptom needs inspection | Scoped findings, affected consumers, and verified fixes |

Unity stores references in assets and metadata as well as C# source. Preserve GUIDs and `.meta` files on moves; inspect serialized type and field identities, including `SerializeReference` cases, before migration. Use the Unity Editor APIs or official tooling already available in the project for serialized asset edits when possible. An independently installed official Unity plugin may provide such access, but it is an external integration with its own installation and permission checks. EmbrAIon does not bundle or copy that plugin's proprietary skills.

Editor, build, and Player results answer different questions. In particular, an Editor result does not establish IL2CPP stripping or target-device behavior, and a successful Player build does not establish runtime behavior until the Player runs. A documentation-only change ordinarily needs no Unity execution unless the project requires it. The general [engineering skills](engineering-skills.md) and [Unity example](../examples/unity.md) provide the surrounding workflow and repository shape.

The extension manifest is a package index, not proof that a given host has loaded its skills. Check the installed framework version and host projection after including the pack. For a repository-specific installation, follow its approved project overlay and host install process; keep project facts in that overlay.
