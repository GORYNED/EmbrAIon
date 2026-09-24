# Overview

EmbrAIon is a reusable AI-First Engineering System.

Its Core uses job-like agents, capability-typed policy, task-oriented model-agnostic routing, and deterministic tooling. EmbrAIon does not own current model identities: the execution host owns model availability and automatic/default selection, while a consuming project may optionally supply opaque host-specific overrides.

This lets the framework evolve without tying its canonical behavior to Codex, GitHub Copilot, Claude Code, a particular provider, or a particular generation of models.

Spec Kit is a recommended external companion for substantial specification-driven work.

A consuming repository contributes its domain truth and optional routing overrides through a project overlay.
