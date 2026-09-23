# Architecture

## Layers

1. **Core** — vendor-neutral rules, agents, skills, workflows, routing, and knowledge.
2. **Adapters** — concrete hosts, models, providers, and transports.
3. **Tools** — deterministic runtime, worktree, validation, sync, install, doctor, and CLI behavior.
4. **Project overlay** — consuming-project agents, domains, source classes, compatibility rules, and product knowledge.
5. **External capabilities** — recommended or optional systems such as Spec Kit and domain-specific plugins.

## Agent model

Core agents use job-like names: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher, and Steward.

Project-specific domain specialists remain in the consuming project rather than becoming generic Core roles.

## Model ownership

Core routing selects provider-neutral route classes. Adapter catalogs own current model identities, efforts, pricing, lifecycle, and host selectors.

## Spec Kit

Spec Kit is composed as an external capability. EmbrAIon recommends it for substantial specification work but does not vendor its skills, templates, or runtime.
