# Integrations

External tool and server integrations must be discoverable, attributable to a configuration source, and reviewable.

Each integration should expose enough metadata to determine:

- identity;
- host or client surface;
- expected versus observed state;
- access level;
- executable or transport boundary;
- declared environment-variable names without secret values;
- drift from canonical expectations.

Secrets, tokens, passwords, and credential values must never be stored in the integration inventory.
