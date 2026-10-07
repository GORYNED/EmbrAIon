# Policy recipes

Recipes for `.embraion/policy.yaml`. Read the whole file first and change only the keys the request names; keep every other key. `embraion validate --strict` checks only key names. The loader commands below check the full shape, so always run them.

An `owner-decision` entry widens access or lowers a safety setting. Make that change only when the user's request states it. When the request is vague, ask one short question first, with a recommendation.

## protect-paths

Fills `sources.canonical`, `sources.protected`, `sources.generated`, `sources.external`. Each is a list of path patterns.

- `canonical`: first-party source of truth. `protected`: ordinary writable work must not change it without a separate approval. `generated`: build output or derived files. `external`: third-party material governed outside the project.
- Discover: check that each named folder exists (`git ls-files <folder>`); find vendor, build, and generated folders; read `.gitattributes` and `.gitignore` for generated markers.
- A path the user names explicitly and asks to protect is evidence enough; do not widen it to other folders on your own judgment. Without such a request, do not mark a file protected only because it is important, and do not call a folder external because of its layout.
- Ask only when the request does not say which class a path belongs to.
- Write: add patterns to the existing list and keep the old ones. Use `folder/**` for a folder. `*` also matches across separators, and a whole `**/` segment matches zero folders. Patterns longer than 4096 characters or with more than eight `**/` segments are rejected.

```yaml
sources:
  canonical: [src/**]
  protected: [vendor/**]
  generated: [build/**]
  external: [third-party/**]
```

Verify: `embraion policy show` (pattern counts), then `embraion check`. A protected path is enforced in CI only after the enforcement recipe has run.

## classify-privacy

Fills `privacy.default-class` (`PUBLIC`, `PRIVATE`, or `CONFIDENTIAL`) and the optional `privacy.sources` map from a stable source id to its class.

- Discover: the current default; source ids already named in `.embraion/execution.yaml` (`sourceIds`) and in `privacy.sources`.
- Ask for the class of each named source. An unknown class fails closed: ask, and never guess `PUBLIC`. Lowering a class is an owner decision.
- With `privacy.sources` declared, an execution request may name only listed sources, and its data class must be at least the highest class among them. Add every source id the project already uses, or those requests start failing.

```yaml
privacy:
  default-class: PRIVATE
  sources:
    PublicDocs: PUBLIC
    InternalApp: PRIVATE
```

Verify: `embraion policy show`, `embraion policy check`.

## set-review-rule

Fills `review.substantial-required` (`true` or `false`). Setting `false` is an owner decision. Verify: `embraion policy show`.

## enable-enforcement

Fills `enforcement.enabled`, `enforcement.validation-profile`, `enforcement.require-review`, and the optional `enforcement.protected-sources`. Do not flip the first three by hand; the command also writes the CI workflow.

- Discover: validation profiles that are not empty (`embraion validation list`); the CI system.
- Ask: which profile CI runs, whether an approved review is required, and permission to add `.github/workflows/embraion-enforcement.yml`. This adds a file to the repository, so wait for the answer.
- Run `embraion enforcement install --surface github-actions --validation-profile <profile>` and add `--require-review` when asked. It refuses to replace different workflow content; never add `--force` on your own. It needs an exact framework pin.
- `protected-sources` is `name` (default; matches changed file names) or `base-tree`. `base-tree` reads the protected list at the merge base and compares protected paths by Git object ID, so editing the list or moving a folder in the same change does not bypass it. Ask whether the user wants that stronger mode; it needs full Git history in CI. Set it in the policy, or run `embraion enforcement check --base-ref <base> --protected-sources base-tree`.
- Making the check a required status check is a repository setting only the owner can change; say so.

Verify: `embraion enforcement status`, `embraion policy show`, `embraion enforcement check --base-ref <base>`.

## set-merge-mode

Fills `merge.mode`: `human-only` (the default when `merge` is absent) or `owner-permission`.

- "Allow you to merge after green checks", «Разреши тебе мержить после зелёных проверок» mean `owner-permission`. "Only a human merges" means `human-only`; remove the `merge` key or set that value.
- Tell the user what `owner-permission` allows: you may merge a pull request only when the owner explicitly permits that pull request, required checks pass on its final head, and the independent reviewer confirmed that exact head. It is not a standing permission. Auto-merge stays off in both modes.
- Do not merge anything as part of this request.
- The mode is written into the projected Core rules of each host. After the edit, run `embraion status` to list installed hosts, then `embraion install --host <host> --destination .` for each, then verify. Never use `--force` and never edit projected files.

```yaml
merge:
  mode: owner-permission
```

Verify: `embraion policy show`, `embraion projection verify --host <host> --destination .` (it reports a stale line until install ran).

## set-policy-ceilings

Fills `ceilings`: the most the project allows. Deployments, execution bindings, and routing may narrow it, never widen it.

- Discover: providers in `.embraion/deployments.yaml`, bindings in `.embraion/execution.yaml`, routing targets.
- Ask, for each provider: which data classes, access modes (`read-only`, `workspace-write`), roles, and source ids it may have. This is a policy decision; do not infer it from the provider name.
- Keys: `providers.<provider>` with `data-classes`, `access-modes`, `roles`, `sources`, `binding-required-billing-modes`; `data-classes.<CLASS>.providers`; `sources.<id>.providers`; `task-classes.<id>` with `route-class`, `role`, `data-class`; `critical.justifications`.

```yaml
ceilings:
  providers:
    example:
      data-classes: [PUBLIC]
      access-modes: [read-only]
  data-classes:
    CONFIDENTIAL: {providers: [other-provider]}
```

Verify: `embraion policy check` and `embraion route --validate`. A finding names the file and the ceiling it exceeds; fix the deployment or routing, never the ceiling, unless the user asks.

## configure-check

Fills `check.validation-profiles` (project validation profiles that `embraion check` also runs; each must exist, have commands, and pass), `check.organization` (list of `full`, `compare`), `check.fail-on` (`info`, `low`, `medium`, `high`, `critical`; default `high`), `check.all-files` (boolean; default `false`). `embraion check` reads them so CI needs no flags.

- Ask the lowest severity that fails CI only when the request does not say. Only a framework release that contains the section accepts it; check `embraion status` first.
- Never lower `fail-on` to make a failing scan pass. Name a validation profile only when it is non-empty and safe to run in CI; an empty or unknown profile fails the check.

```yaml
check:
  organization: [full, compare]
  fail-on: medium
  all-files: true
  validation-profiles: [affected]
```

Verify: `embraion policy show`, `embraion check`.

## configure-projection-checks

Fills `projection.<host>.components`, and for Codex also `config-mode`, `strict-root`, `forbidden-root-keys`, `allowed-root-keys`. `embraion check` verifies the declared components.

- Discover: installed hosts and components from `embraion status` and the host folders. Components: Codex `config`, `agents`, `skills`; Copilot `agents`, `skills`; Claude Code `agents`, `skills`, `scoped-agents`, `hooks`.
- Declare only components that are actually installed, or `embraion check` fails.
- Codex `config-mode` is `replace` (default) or `merge`; `merge` keeps user-owned config. `forbidden-root-keys` only adds to the Core defaults.

```yaml
projection:
  codex:
    components: [config, agents, skills]
    config-mode: merge
  claude-code:
    components: [agents, skills]
```

Verify: `embraion projection verify --host <host> --destination .` for each declared host, then `embraion check`.
