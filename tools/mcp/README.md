# MCP

`tools/mcp/` owns normalized inventory and drift inspection for MCP server configuration across supported hosts.

The inventory is descriptive, not a credential store.

Each observed server may record:

- stable server ID;
- host/client surface;
- configuration source;
- command or transport boundary;
- declared access category;
- expected or observed state;
- executable/version evidence when available;
- environment-variable names without their values.

## Drift examples

- expected server is missing;
- unexpected server exists;
- command or endpoint changed;
- access became broader;
- executable identity changed;
- one host differs from another;
- credential value appears directly in configuration.

The inventory must redact or reject secret values.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
