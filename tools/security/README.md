# Security

The executable security scanner is:

```bash
embraion security scan --path .
```

It currently detects high-risk secret-like material and policy drift. Security policy is defined separately in `policy.yaml` so scanner behavior can expand without moving canonical policy into executable code.

The scanner reports evidence and fails according to configured severity; it never weakens policy to make a scan pass.

<sub>Last updated: 2026-09-23 20:05 UTC</sub>
