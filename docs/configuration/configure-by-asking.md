# Configure by asking

You do not need to know the `.embraion/` files, their keys, or the `embraion` commands. Ask your AI client in plain words, in any language, and it fills the right file.

> Set up EmbrAIon for this project.
>
> Protect the `vendor/` folder.
>
> Declare our MCP server.
>
> Allow you to merge after green checks.
>
> Require a decision record for dependency changes.

## How the agent handles a request

1. It matches your words to one entry of the configuration matrix. The matrix ships with the `project-bootstrap` skill as `references/configuration-matrix.yaml`.
2. It loads the skill and recipe that entry names: `project-bootstrap`, `routing-configuration`, or `architecture-decision`.
3. It reads the repository and the current `.embraion/` file first. It asks only for what the repository cannot answer, one short question at a time.
4. It changes only the fields of that entry and keeps everything else.
5. It runs the checks named in the entry and reports each one as passed, failed, or not run.

Manual editing and the `embraion` commands stay available. This page is the map from a request to the result.

## Settings only you decide

Rows marked ● widen access or lower a safety setting: housekeeping that deletes branches, privacy classes, review rules, enforcement, merge mode, policy ceilings, execution bindings, integrations, external capabilities, the write policy of registered sources, project agents (their access), and validation changes that make checks optional or narrower. The agent changes them only when your request says so. Otherwise it asks first.

`merge.mode: owner-permission` is not a standing permission to merge. The agent may merge a pull request only when you permit that pull request, the required checks pass on its final head, and the independent reviewer confirmed that exact head. Auto-merge stays off.

## Request map

| Entry | Example request | Fills | Owner decision | Proved by |
| --- | --- | --- | --- | --- |
| `set-up` | Set up EmbrAIon for this project | bundle: `bind-knowledge`, `protect-paths`, `project-validation`, `project-agents`, `project-identity` |  | `embraion doctor`<br>`embraion validate --strict`<br>`embraion check` |
| `bind-knowledge` | Register our architecture document | `knowledge.yaml`: slots, custom entries |  | `embraion context slots`<br>`embraion validate --strict` |
| `project-validation` | Add our test command to validation | `validation.yaml`: profiles |  | `embraion validation list`<br>`embraion validation run fast` |
| `validation-guards` | Fail validation if the tests modify the working tree | `validation.yaml`: profiles | ● | `embraion validation list`<br>`embraion validation run <profile>` |
| `plan-validation` | Run only the checks that match what changed | `validation.yaml`: areas, impact, full-reasons, default-area | ● | `embraion validation list`<br>`embraion validation explain <profile> --base-ref <base>` |
| `project-agents` | Add a read-only reviewer for our API | `agents.yaml`: agents | ● | `embraion projection diff --host <installed-host> --destination .`<br>`embraion install --host <installed-host> --destination .` |
| `project-identity` | Rename the project in EmbrAIon | `project.yaml`: project, capabilities |  | `embraion status`<br>`embraion validate --strict` |
| `update-framework` | Update EmbrAIon to the latest release | `project.yaml`: framework |  | `embraion update --check`<br>`embraion doctor`<br>`embraion status` |
| `task-housekeeping` | Clean up old agent branches and worktrees automatically | `project.yaml`: housekeeping | ● | `embraion worktree gc` |
| `declare-sources` | Register our repositories and say which ones you may write | `sources.yaml`: schema-version, sources | ● | `embraion sources list`<br>`embraion sources status`<br>`embraion validate --strict` |
| `hydrate-lfs-worktrees` | Fetch Git LFS files in new worktrees | `project.yaml`: worktree |  | `embraion policy show` |
| `add-pr-template` | Add a pull request template | creates `.github/pull_request_template.md` |  | `embraion pr-template` |
| `protect-paths` | Protect these folders | `policy.yaml`: sources |  | `embraion policy show`<br>`embraion check` |
| `classify-privacy` | Treat this source as confidential | `policy.yaml`: privacy | ● | `embraion policy show`<br>`embraion policy check` |
| `set-review-rule` | Require review for substantial changes | `policy.yaml`: review | ● | `embraion policy show` |
| `enable-enforcement` | Enforce the rules in CI | `policy.yaml`: enforcement | ● | `embraion enforcement status`<br>`embraion policy show`<br>`embraion enforcement check --base-ref <base>` |
| `set-merge-mode` | Allow you to merge after green checks | `policy.yaml`: merge | ● | `embraion policy show`<br>`embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |
| `set-policy-ceilings` | Never send confidential data to this provider | `policy.yaml`: ceilings | ● | `embraion policy check`<br>`embraion route --validate` |
| `configure-check` | Make one command run all project checks in CI | `policy.yaml`: check |  | `embraion check`<br>`embraion policy show` |
| `configure-projection-checks` | Verify the installed agent files in CI | `policy.yaml`: projection |  | `embraion projection verify --host <installed-host> --destination .`<br>`embraion check` |
| `configure-routing` | Configure routing | `routing.yaml`: overrides, task-classes, candidate-groups; `deployments.yaml`: providers, deployments |  | `embraion route --validate`<br>`embraion deployment list`<br>`embraion route --host <host> --route-class <class> --data PRIVATE`<br>`embraion route --audit-authority`<br>`embraion policy check` |
| `declare-execution-binding` | Let EmbrAIon call this provider through an API key in the environment | `execution.yaml`: schemaVersion, bindings | ● | `embraion execution preflight --deployment <deployment-id>`<br>`embraion policy check` |
| `declare-pricing` | Track what provider calls cost | `pricing.yaml`: schemaVersion, sources |  | `embraion pricing status` |
| `declare-integration` | Declare our MCP server | `integrations.yaml`: schema-version, servers | ● | `embraion security scan --path . --fail-on high`<br>`embraion doctor` |
| `declare-external-capability` | Record that this plugin is installed for the team | `external-capabilities.yaml`: schema-version, capabilities | ● | `embraion capabilities --path . --host <installed-host>` |
| `bind-decisions` | Require a decision record for dependency changes | `decisions.yaml`: index, template, triggers, extra-triggers; `knowledge.yaml`: slots.decisions |  | `embraion decisions check --require-config --path . --base-ref <base>`<br>`embraion context slots`<br>`embraion check --base-ref <base>` |
| `limit-code-structure` | Enforce lowercase file names in docs | `organization.yaml`: exclude, namespaces, assemblies, unity_meta, filenames |  | `embraion organization check --require-config --path .` |
| `track-doc-sources` | Warn me when the architecture doc is out of date with the code | `knowledge-maintenance.yaml`: documents |  | `embraion knowledge audit --path .` |
| `shape-final-report` | Use these sections in your final reports | `report.yaml`: schema-version, sections, workers, pull-request, guidance |  | `embraion report template`<br>`embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |
| `claude-native-agents` | Make the reviewer route available as a native Claude agent | `claude-native.yaml`: bindings, assignments, read-policy |  | `embraion claude-native status` |
| `project-skill` | Add a project skill for our release process | `.embraion/skills/`: `<name>/SKILL.md` |  | `embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |

`embraion validate --strict` and `embraion doctor` check key names, not the full shape of a file. The commands in the last column load the file and check its full shape, so the agent always runs them. After a change that is copied into host files (merge mode, report contract, agents, project skills, native Claude agents), the agent also runs `embraion install --host <host> --destination .` and `embraion projection verify` for each installed host.

## Not configured by request

- `project.yaml` `framework`: moves only with `embraion update`; see [Updating safely](../getting-started/updating.md).
- `.embraion/pricing.snapshot.json`: written by `embraion pricing refresh`.
- `.embraion/state/` and `.embraion/.gitignore`: local runtime state.

## Keeping the map complete

The matrix is a data file next to the skill. A unit test reads the schemas, lists every `.embraion/` file and every top-level and section key, and fails when one has no matrix entry. A new key must therefore get an entry, a recipe, and a row here.

Related pages: [Project Bootstrap](bootstrap.md), [Conversational configuration](ai-hosts.md), [Project files](project-files.md).
