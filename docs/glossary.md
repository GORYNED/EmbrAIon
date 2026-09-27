# Glossary

Use this page when an EmbrAIon term appears before you need the full engineering model.

!!! tip "In plain English"
    Most projects can start with **knowledge + policy + validation**. The rest of this vocabulary matters only when the repository needs more control.

| Term | Meaning |
| --- | --- |
| **Project contract** | The repository-owned EmbrAIon configuration and knowledge that define how AI-assisted engineering should work for this project. |
| **Core** | Reusable EmbrAIon mechanisms: schemas, generic roles/skills, routing contracts, validation/review mechanics, security mechanics, and host projection behavior. |
| **AI host** | The AI client that owns the conversation and its native reasoning/tools, such as Codex, GitHub Copilot, or Claude Code. |
| **Host projection** | Generated host-native files that deliver the project contract to an AI host. A projection is derived output, not a second source of truth. |
| **Knowledge** | Project facts and source-of-truth documents registered in `.embraion/knowledge.yaml`. |
| **Project Contract Slot** | A built-in knowledge role such as architecture, source authority, compatibility, persistence, engineering workflow, or specification. |
| **Policy** | Project-owned rules for source classes, privacy, review, protected paths, and optional enforcement. |
| **Canonical source/path** | Content treated as authoritative project truth for its concern. |
| **Protected source/path** | Content that AI work should not mutate unless the project explicitly permits the required path/process. |
| **Generated source/path** | Derived output that should normally be regenerated from its owner rather than edited as canonical project truth. |
| **External source/path** | Content owned outside the project contract, such as vendored or upstream material. |
| **Route class** | A stable description of work/risk such as `ordinary`, `substantial`, or `complex`. It is not a permanent model tier. |
| **`host-default`** | Routing result that leaves actual model selection to the AI host's current default/automatic behavior. |
| **Deployment** | A reusable project-owned concrete model/provider choice. Think **what can be selected**. |
| **Routing** | Rules that decide **when** a route or role should select a deployment or explicit host option. |
| **Execution binding** | Project configuration describing **how** an approved deployment may be invoked through EmbrAIon's optional provider-neutral runtime. |
| **Provider-neutral execution** | The optional `embraion execute` path where EmbrAIon owns a bounded external/API attempt loop. Ordinary host-native conversations do not pass through it. |
| **Validation profile** | A named set of real project commands used to prove that a change works. |
| **Evidence** | Structured records produced by validation, review, execution, or enforcement so claims can be tied to actual checks. |
| **Review** | Project rules/evidence for independent or human assessment of a change. |
| **Enforcement** | Deterministic delivery/merge checks for protected paths, validation, and optionally review. Text guidance alone is not enforcement. |
| **Runtime resolution** | Resolving the exact EmbrAIon version pinned by a repository, including an isolated cached runtime when needed. |

## The four advanced words most people mix up

| Concept | Question |
| --- | --- |
| Deployment | **What** concrete choice exists? |
| Routing | **When** should it be selected? |
| Execution binding | **How** may it be invoked safely? |
| Pricing | **How** is provider cost interpreted/refreshed? |

For the precise model, see [Engineering Model Deep Dive](reference/engineering-model.md).
