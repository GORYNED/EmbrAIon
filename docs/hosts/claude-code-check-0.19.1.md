# Claude Code 0.19.1 Windows check

Date: 2026-10-03. Framework: EmbrAIon 0.19.1. Host: local Claude Code Desktop on Windows 11.

## Evidence source

This historical report summarizes maintainer-supplied results from two separate local worktree sessions. The upstream documentation author did not inspect the original host transcripts or rerun these Desktop sessions. Reported observations below retain that provenance; this document is not an independently authenticated execution attestation.

Original transcripts and hook journals remain private. Repository names, local paths, commit and session identifiers, agent IDs, raw payloads and private Thread links are omitted. Model and effort values below describe the reported checks, not framework defaults or routing instructions.

## Reported procedure

Both sessions used a worktree created from current main, a project pin and runtime of 0.19.1, and the current repository and projected orchestration instructions. The Lead resolved a bounded read-only Reviewer assignment, selected its exact hash-named profile from the active Thread's loaded registry, and invoked it without a model override. A prepared dispatch plan was not counted as execution.

The Reviewer checked project identity and native-assignment metadata. This was a bounded configuration check, not a full code review or a test of every guard boundary. Both reports state that the working tree remained clean and no PR, merge, release or synthetic hook event was created.

## Reported observations

| Observation | Session A | Session B |
| --- | --- | --- |
| Pin and runtime | 0.19.1 | 0.19.1 |
| Scoped profile | Loaded and invoked without override | Loaded and invoked without override |
| Host transcript model | Sonnet 5.5 | Opus 5.5 |
| Configured/requested effort | medium | high |
| Journal in active worktree | New matching PostToolUse and SubagentStop records | New matching PostToolUse and SubagentStop records |
| Callback state | none before launch; recorded after | recorded after launch |
| Reported effort comparison | match | match |
| Reviewer result | No inconsistencies in the bounded scope | No material findings in the bounded scope |

The maintainer reported matching session/agent identity, scoped type and definition digest in the new worktree journal records. Journal presence was checked in the active worktree; these reports do not establish the absence of copies elsewhere.

Model observations came from the host-written subagent transcript, separately from the observer journal and the agent's own statements. Session B also reported a transcript effort field; that identifies a requested setting and does not independently establish its effective application by the API.

## Interpretation and limits

These reports support native invocation of the loaded Reviewer profiles and callback storage in the active worktree on the tested Windows surface. They also provide maintainer-reported host transcript evidence of the selected models.

The observer correctly retained `execution`, `model` and effective `effort` as `unverified`, with `evidence-origin: unverified-command-input`. Its public command accepts JSON input: `callbacks: recorded` and `reported-effort: match` describe accepted metadata, not authenticated host origin, successful completion or effective effort. The source of each observation remains distinct.

`.claude/embraion-native.json` records assignment and definition identity; it is not the framework-version authority. Verify the pin, artifact and runtime separately. A read-only Reviewer need not have a shell or hashing tool: the Lead can run canonical projection verification to check exact generated content.

Cloud, macOS, resumed Threads, negative guard cases and writable-worker effort were not covered by these two checks. Historical success does not validate a later Thread, changed configuration or different host build. Effective effort remains unverified.

## Repeat a bounded check

1. Start a fresh local Thread from an up-to-date checkout or worktree. Read its applicable instructions and confirm its pin and runtime agree. If hooks start in another checkout, keep its runtime pin and artifact lock compatible with the event worktree.
2. Run `embraion framework install`, `embraion --version`, `embraion route --validate` and `embraion projection verify --host claude-code --component agents --component skills --component scoped-agents` in the active worktree.
3. Record `embraion claude-native status` before launch. Resolve the bounded review through the existing project role, route and privacy/access policy.
4. Invoke the exact returned scoped type from the loaded registry without a model override. Give it only the configuration files needed for this check.
5. After completion, run status in the same worktree and inspect new journal records matching that invocation. Keep raw records and identifiers local; do not synthesize callbacks.
6. Inspect host-provided model evidence when available and report requested effort separately from effective effort. Record unsupported fields as unverified.

See the [Claude Code guide](claude-code.md) for installation and observer semantics, and the [review lifecycle](../guides/runs-review.md) for production PR readiness and separate merge/release authorization.
