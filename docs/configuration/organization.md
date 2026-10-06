# Organization Checks

Projects can opt in with `.embraion/organization.yaml`. The checker reads source and Unity metadata; it never changes files. It reports each finding with its path, rule code, message, and, in incremental mode, `new` or `preexisting` status. An absent configuration returns `skipped`.

```yaml
exclude:
  - Assets/Vendor/**
  - Assets/Generated/**

namespaces:
  enabled: true
  rules:
    - path: Assets/Project/Runtime
      namespace: Example.Project
      require_declaration: true
      exceptions:
        - path: Assets/Project/Runtime/Interop
          namespace: Example.Interop
        - path: Assets/Project/Runtime/GlobalTypes
          allow_missing: true

assemblies:
  enabled: true
  enforce_platforms: true
  roots: [Assets/Project]
  path_rules:
    - {path: Assets/Project/Runtime, layer: Runtime}
    - {path: Assets/Project/Editor, layer: Editor}
    - {path: Assets/Project/Tests, layer: Tests}
  allowed_edges:
    - {from: Example.Project.Runtime, to: Example.Project.EditorBridge}

unity_meta:
  enabled: true
  roots: [Assets/Project]
  require_for_extensions: [.cs, .asmdef]
  check_move_identity: true
```

Each check kind is optional and can be disabled independently. Paths are repository-relative directory prefixes, except `exclude` patterns, which also accept shell-style wildcards. Assign namespace rules to project-owned code only. A C# namespace can equal the configured prefix or add dot-separated segments. Files without a declaration are allowed unless `require_declaration` is true. An exception can use another namespace or permit a missing declaration. The checker masks ordinary comments and quoted strings before finding namespace declarations. This is a bounded lexical check, not a full C# compiler: advanced raw/interpolated string syntax or preprocessor branches may need compiler-backed validation.

Assembly rules apply to actual `.asmdef` files under `roots`; they do not require one assembly per directory. Every scanned assembly must match a `path_rules` layer. References use Unity's name strings or `GUID:<32 hex digits>` resolved from adjacent `.asmdef.meta` files. Unresolved GUID references, duplicate assembly names, duplicate metadata GUIDs, dependency cycles, and forbidden layer edges are findings. Name references outside configured roots can belong to packages and are left unresolved. By default Runtime may reference Runtime, Editor may reference Runtime or Editor, and Tests may reference all three. `allowed_edges` grants a specific assembly-name pair an exception to a layer restriction. With `enforce_platforms` (on by default), an Editor assembly must declare `includePlatforms: [Editor]`, and references between scanned assemblies must be compatible with their declared include/exclude platforms. Complex Unity platform and define-constraint behavior can require project-specific compiler validation.

Metadata checks look for GUIDs in `.meta` files and require an adjacent `.meta` for configured asset extensions. `require_for_all` instead requires one for every file under `roots`, except files inside dot-prefixed or `~`-suffixed folders, dot-prefixed or `~`-suffixed names, and excluded paths, which Unity does not import. `check_orphans` reports `meta_orphan` for a `.meta` whose asset file or folder is missing; a root's own `<root>.meta` counts. Incremental checks detect GUID changes at an existing path. A detected Git asset rename compares its original adjacent metadata GUID with the destination GUID; a matching filename alone is insufficient. Untracked moves without a common Git history cannot prove identity. Exclude vendor or generated trees when the project does not own their metadata.

## Filenames

The optional `filenames` section checks file names:

```yaml
filenames:
  roots: [docs, tools]          # "." checks the whole repository
  extensions: [.md, .yaml, .json]
  allow: [NOTICE.md]
  suffixes:
    - {path: docs/decisions, suffix: .adr.md}
  case_collisions: true

unity_meta:
  roots: [Assets/Project]
  require_for_all: true
  check_orphans: true
```

Only files under `roots` whose extension appears in `extensions` are checked. The name before the extension must be lowercase kebab-case, optionally ending in a numeric version such as `migration-1.0.0.md` (`filename_style`); an uppercase spelling of a listed extension is `filename_extension_case`. Ecosystem, package-manager, and agent-host basenames such as `README.md`, `CHANGELOG.md`, `AGENTS.md`, `SKILL.md`, and `package.json` are built in, `allow` adds exact basenames, and dot-prefixed names such as `.gitignore` are skipped. A host-native suffix is accepted only directly inside its folder, and the identifier before it must still be kebab-case. Built-in suffixes are `.agent.md` in `.github/agents`, `.instructions.md` in `.github/instructions`, and `.prompt.md` in `.github/prompts`; `suffixes` adds more. Generated `.claude/agents/embraion--<role>-<12 hex digits>.md` profiles use a reserved namespace and are exempt. `case_collisions` (on by default) reports `filename_collision` for paths anywhere in the inventory that differ only by case.

Filename, `require_for_all`, and `check_orphans` checks read a file inventory: Git-tracked plus untracked, not ignored files for the worktree, or the tree of the commit for a ref.

## Running the check

`embraion organization check` performs a full worktree scan. For an incremental gate, pass a Git base and optional head. Both refs must resolve to commits. The checker compares the complete set of findings at the base with the selected head and fails only on new findings. Request `--include-worktree` to evaluate the current tracked and untracked files after the head; otherwise the head commit is the evaluated state. The response includes both resolved commit IDs so the baseline is reproducible. An unavailable base is an error, never a passing comparison. `--require-config` makes a missing configuration fail instead of returning `skipped`. Symbolic links are not followed, Git internals are ignored, scans have file and byte limits, and Git LFS pointers are reported without treating them as source content.

Rules are advisory to source organization only. No `.meta` is generated, no C# namespace or assembly is rewritten, and no mass file rearrangement is attempted.
