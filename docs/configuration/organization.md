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

Metadata checks look for GUIDs in `.meta` files and require an adjacent `.meta` for configured asset extensions. Incremental checks detect GUID changes at an existing path. A detected Git asset rename compares its original adjacent metadata GUID with the destination GUID; a matching filename alone is insufficient. Untracked moves without a common Git history cannot prove identity. Exclude vendor or generated trees when the project does not own their metadata.

`embraion organization check` performs a full worktree scan. For an incremental gate, pass a Git base and optional head. Both refs must resolve to commits. The checker compares the complete set of findings at the base with the selected head and fails only on new findings. Request `--include-worktree` to evaluate the current tracked and untracked files after the head; otherwise the head commit is the evaluated state. The response includes both resolved commit IDs so the baseline is reproducible. An unavailable base is an error, never a passing comparison. Symbolic links are not followed, Git internals are ignored, scans have file and byte limits, and Git LFS pointers are reported without treating them as source content.

Rules are advisory to source organization only. No `.meta` is generated, no C# namespace or assembly is rewritten, and no mass file rearrangement is attempted.
