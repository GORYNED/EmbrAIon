# Security

AI infrastructure is part of the engineering attack surface.

Agents, adapters, external integrations, execution permissions, routing overrides, generated configuration, credentials, and automated commands must be treated as security-relevant configuration.

Security checks should fail closed for:

- exposed or embedded secrets;
- unexpectedly broad write or command permissions;
- untrusted or unpinned executable boundaries where pinning is required;
- external-execution/privacy mismatches;
- unknown external integration state;
- unsafe mutation or command construction;
- integrity drift in generated or expected configuration.

A security scan reports evidence; it does not silently rewrite policy to make a failure disappear.
