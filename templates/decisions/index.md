# Architecture Decision Records

This directory is the index and home for Architecture Decision Records (ADRs). ADRs capture durable
decisions that are costly to reverse or easy to misunderstand later. They do not replace current-state
architecture documentation; update it when an accepted decision changes the implemented architecture.

## When an ADR is required

Create an ADR for decisions such as:

- a new or changed module, assembly, or package dependency direction;
- moving ownership between components or repositories;
- a persisted format, stable identifier, serialization, or migration strategy;
- a platform, build, or deployment strategy;
- a validation or CI contract that becomes authoritative;
- adoption or replacement of a foundational dependency.

Small local implementation choices normally do not need an ADR.

## Naming and lifecycle

Use `NNNN-short-kebab-case-title.md`, beginning with `0001`. Create records with
`embraion adr new "<title>"`, which copies `0000-template.md`, allocates the next unused number, and
adds the record to the index below. ADR numbers are never reused.

Statuses are:

- **Proposed**: under review and not authoritative;
- **Accepted**: governs new work;
- **Superseded**: replaced by a later ADR, linked in both records;
- **Deprecated**: retained for history but no longer recommended;
- **Rejected**: considered and explicitly not adopted.

An accepted ADR is immutable except for typo and link fixes and status or supersession metadata.
Change a decision by adding a new ADR that explains and supersedes the old one.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| `0000-template.md` | Template | Copy this file when recording a decision. |
