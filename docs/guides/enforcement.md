# Enforcement

EmbrAIon separates **project policy** from **merge-time enforcement**.

Policy can exist without installing executable CI. Enforcement is explicit and opt-in.

## Before enabling enforcement

First make sure these are trustworthy:

1. protected/canonical/generated/external paths in `.embraion/policy.yaml`;
2. the selected validation profile in `.embraion/validation.yaml`;
3. review policy if review will be required.

Check them:

```bash
embraion doctor
embraion policy show
embraion validation list
embraion validation run affected
```

Do not use an empty validation profile as a merge gate; it will report `skipped`, not `passed`.

## Inspect enforcement status

```bash
embraion enforcement status
```

By default enforcement is disabled.

## Install the GitHub Actions surface

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

To require a current approved PR review as well:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected \
  --require-review
```

This explicitly creates:

```text
.github/workflows/embraion-enforcement.yml
```

and enables the matching project policy block.

Existing different workflow content is not silently replaced; intentional replacement requires `--force`.

## What the gate checks

The enforcement check combines:

- protected-source mutation detection;
- a fresh executable validation profile result;
- review evidence when configured.

Protected detection includes deletions, rename sources, and dot-prefixed paths.

Run it manually when useful:

```bash
embraion enforcement check --base-ref origin/main
```

With structured run evidence:

```bash
embraion enforcement check \
  --base-ref origin/main \
  --run-id task-001
```

## Make it a mandatory merge gate

Installing the workflow does **not** automatically change repository branch rules.

If GitHub should block merges when the gate fails, configure the generated **EmbrAIon enforcement** status check as required in the repository ruleset/branch rules.

This separation is intentional: repository administration remains an explicit human decision.

## What EmbrAIon does not do silently

`embraion init`, host `install`, and `harness audit` do not silently install executable hooks or enforcement workflows.

`harness audit` reports available surfaces; it is not an installer.
