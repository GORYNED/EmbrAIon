# Security Policy

Security issues should be reported privately.

## Reporting a vulnerability

Do **not** open a public GitHub Issue, Discussion, or Pull Request for a vulnerability that could expose credentials, private data, access-control weaknesses, code-execution paths, supply-chain risk, or another exploitable condition.

Use GitHub Private Vulnerability Reporting for this repository:

https://github.com/GORYNED/EmbrAIon/security/advisories/new

If the private-reporting UI is unavailable, do not publish sensitive details publicly. Contact the GORYNED maintainer privately through GitHub before sharing exploit details.

A useful report includes:

- affected EmbrAIon version;
- affected operating system / Python version when relevant;
- a concise description of the impact;
- reproducible steps or a minimal proof of concept;
- whether credentials, private data, or remote execution are involved;
- any suggested mitigation.

## Supported security scope

The latest public EmbrAIon release receives primary security attention.

Older pre-1.0 versions may remain installable for project pinning and reproducibility, but fixes are not guaranteed to be backported. When practical, users should update the global launcher and migrate projects intentionally after reviewing release notes.

See [SUPPORT.md](SUPPORT.md) for the broader compatibility policy.

## Research guidelines

Please:

- test only systems and data you are authorized to test;
- avoid accessing or retaining other people's data;
- avoid service disruption;
- avoid publishing a vulnerability before a fix or mitigation can be evaluated;
- do not use discovered access for unrelated activity.

Good-faith reports are evaluated on their technical impact and reproducibility.
