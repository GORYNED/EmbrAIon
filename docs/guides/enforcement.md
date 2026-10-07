# Enforcement

EmbrAIon separates **project policy** from **merge-time enforcement**.

Policy can exist without installing executable CI. Enforcement is explicit and opt-in.

![Validation and enforcement](../assets/diagrams/en/06-enforcement.svg){ loading=lazy }

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

The workflow installs EmbrAIon through the reusable `GORYNED/EmbrAIon/actions/setup` action, referenced at the release that generated it. The action reads the project pin when the job runs and installs exactly that release, verifying the artifact digest when the pin is locked, so `embraion update` needs no workflow edit. Installation refuses a missing or inexact pin before writing any file. See [Consumer CI](../reference/runtime-version-resolution.md#consumer-ci).

Existing different workflow content is not silently replaced; intentional replacement requires `--force`.

## What the gate checks

The enforcement check combines:

- protected-source mutation detection;
- a fresh executable validation profile result;
- review evidence when configured.

Protected detection includes deletions, rename sources, and dot-prefixed paths.

By default the check matches the **names** of changed files against the protected list of the checked-out policy. For stronger protection, see [Protect sources by Git object identity](#protect-sources-by-git-object-identity).

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

## Protect sources by Git object identity

Name matching has two weak spots. A change can edit the protected list in `.embraion/policy.yaml` together with the files it protects. And a protected directory that is renamed or moved no longer matches its old name.

The opt-in `base-tree` mode closes both. Set it in the policy:

```yaml
enforcement:
  enabled: true
  validation-profile: affected
  require-review: false
  protected-sources: base-tree
```

Or pin it for one run. The flag wins over every policy:

```bash
embraion enforcement check --base-ref origin/main --protected-sources base-tree
```

The default is `name`, which keeps the behavior described above. Any other value is an error.

The mode is also read from the policy at the merge base, and the stricter mode wins (`base-tree` is stricter than `name`). So once the base branch has `protected-sources: base-tree`, a change cannot turn it off by editing the policy. The first pull request that enables the mode relies on the policy at HEAD, because the base does not have the key yet. From the next pull request on, the base pins it. The evidence record then shows `mode-source: merge-base-policy` when only the base policy asked for it. A flag still overrides both, including `--protected-sources name`.

Without an explicit mode flag, an unprovable merge base or an unreadable or malformed existing base policy stops the gate before the weaker `name` mode can be selected. This includes shallow clones; fetch the full history. A proven legacy base with no policy file or mode still uses `name`.

In `base-tree` mode the gate does this:

1. It finds the merge base with `git merge-base <base-ref> HEAD`.
2. It reads `sources.protected` from the policy **at the merge base**, not from the head.
3. It requires every base entry to still be in the head list. You may add entries. You may not remove or narrow one. To widen an entry, keep the old one and add the new one beside it.
4. For each base entry, it lists the matching paths at the merge base and at HEAD with `git ls-tree` and compares them by Git object ID: a blob ID for a file, a tree ID for a directory.

Why object IDs beat names: an ID changes if and only if the content, the file mode, or the set of entries changes. A renamed file, a swapped file, a deleted file, and an added file all show up. A name-only check sees nothing when the name is no longer listed.

Any modification, addition, or deletion is a violation. There is one exception: a **complete relocation**. A protected directory may move when all of this is true:

- the entry has the form `<literal-directory>/**`;
- nothing is left under the old directory;
- the new location is new: it did not exist at the merge base, so a directory that already had an identical copy elsewhere cannot turn a deletion into a move;
- the tree ID at the new location is identical, so every byte, name, and mode matches;
- every file at the new location is covered by the head policy list.

The check is all-or-nothing. A partial move, a move with one changed byte, or a move to an unprotected location is a violation. A relocated entry may leave the head list because its new location must be listed.

Overlapping entries need care. If a moved directory is also matched by another entry that is not of the form `<literal-directory>/**` (for example `**/*.dll`), that other entry sees its files disappear from the old path and appear at the new one. It reports them as changed, so the move fails. Avoid such overlaps, or do not move that directory.

Uncommitted edits to protected paths are reported by name, because they are not in HEAD. Commit first.

Symlinks and Git submodule entries (gitlinks) are compared by their object IDs like files. Paths are read with NUL-separated Git output, so spaces, quotes, and non-ASCII characters are safe.

The check fails closed. It never passes when it cannot decide. These cases fail with a message:

| Message starts with | Cause |
| --- | --- |
| `Cannot resolve the base ref` | The base ref is not a commit. |
| `The repository is shallow` | The clone is shallow. A merge base found in a shallow clone may be older than the real one, so the check never trusts it. Fetch the full history, for example `fetch-depth: 0` in CI. |
| `No single merge base exists` | There is no merge base, or the history has several equally good ones (a criss-cross merge). Merge the base ref into the branch first. |
| `The policy at the merge base is unreadable` | `.embraion/policy.yaml` is not committed at the merge base. |
| `The policy at the merge base cannot be parsed` / `... has an unparsable ...` | The base policy is not valid YAML, or `sources.protected` is not a list of non-empty strings. |
| `Protected entry '<entry>' was removed or narrowed` | The head list lacks a base entry. |
| `Protected entry '<entry>' differs from the merge base` | A protected path was modified, added, or deleted, or a relocation was not complete. |
| `Uncommitted change to protected path` | The working tree has an uncommitted change to a protected path. |

The evidence record keeps the existing `protected-sources` check and adds `mode`, `merge-base`, `findings`, and, after a relocation, `relocated`. `mode-source` appears when the base policy chose the mode.

`embraion enforcement install` keeps a mode that is already set in the policy. When the mode is `base-tree`, the generated workflow passes `--protected-sources base-tree`, so the mode does not depend on any policy. A workflow generated before the mode was set has no flag; regenerate it with `--force` after you approve the replacement.

## Make it a mandatory merge gate

Installing the workflow does **not** automatically change repository branch rules.

If GitHub should block merges when the gate fails, configure the generated **EmbrAIon enforcement** status check as required in the repository ruleset/branch rules.

This separation is intentional: repository administration remains an explicit human decision.

## What EmbrAIon does not do silently

`embraion init`, host `install`, and `harness audit` do not silently install executable hooks or enforcement workflows.

`harness audit` reports available surfaces; it is not an installer.
