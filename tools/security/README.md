# Security

`tools/security/` owns deterministic security inspection of AI engineering infrastructure.

The scanner is intended to inspect configuration and generated surfaces such as:

- agents and access profiles;
- skills and executable scripts;
- provider and model routes;
- external tool/server integrations;
- generated adapter configuration;
- automated commands when a host supports them;
- credential references;
- project overlay permissions.

## Example finding classes

- embedded secret or credential value;
- unexpected wildcard write access;
- unsafe command construction;
- untrusted executable boundary;
- unexpected external integration;
- provider/privacy mismatch;
- generated configuration drift;
- forbidden policy override.

The scanner reports findings by severity and evidence. It never weakens policy or rewrites a failing configuration merely to pass.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
