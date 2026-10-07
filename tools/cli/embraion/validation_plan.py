"""Declarative validation plan: map changed paths to the areas and commands that prove them.

The plan layer is optional. A project that declares none of ``areas``, ``impact``,
``full-reasons`` or ``default-area`` in ``.embraion/validation.yaml`` never reaches it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .common import project_root, read_json, state_root, write_json
from .environment import child_environment
from .security import redact_value
from .policy import normalize_project_path, path_matches, read_validation_config


PLAN_SCHEMA_VERSION = 1
PLAN_KEYS = ("areas", "impact", "full-reasons", "default-area")
FULL_PROFILE = "full"
STATE_PREFIX = ".embraion/state/"
LABEL = "Invalid .embraion/validation.yaml"


def declares_plan(config: dict[str, Any]) -> bool:
    """Return True when the configuration uses any plan key."""
    return any(key in config for key in PLAN_KEYS)


def declares_areas(config: dict[str, Any]) -> bool:
    return bool(config.get("areas"))


def _fail(message: str) -> RuntimeError:
    return RuntimeError(f"{LABEL}: {message}")


def validate_glob(pattern: str, where: str) -> None:
    """Fail closed on a path glob the shared matcher cannot use or that cannot match a project path."""
    if not pattern.strip():
        raise _fail(f"{where}: empty path pattern.")
    canonical = pattern.replace("\\", "/")
    if canonical.startswith("/"):
        raise _fail(f"{where}: path pattern '{pattern}' must be relative to the project root.")
    if ".." in canonical.split("/"):
        raise _fail(f"{where}: path pattern '{pattern}' must not contain '..'.")
    if canonical.count("[") != canonical.count("]"):
        raise _fail(f"{where}: path pattern '{pattern}' has an unbalanced bracket.")
    try:
        path_matches("probe", [canonical])
    except RuntimeError as error:
        raise _fail(f"{where}: path pattern '{pattern}': {error}") from error


def validate_plan_config(config: dict[str, Any]) -> None:
    """Check the cross-references of the plan keys; the schema checks their shape."""
    if not declares_plan(config):
        return
    areas = config.get("areas") or {}
    if not areas:
        raise _fail("impact, full-reasons and default-area require 'areas'.")
    profiles = set(config.get("profiles") or {})
    reasons = list(config.get("full-reasons") or [])

    for name, area in areas.items():
        for pattern in area["paths"]:
            validate_glob(pattern, f"areas.{name}.paths")
        unknown = sorted(set(area.get("profiles") or []) - profiles)
        if unknown:
            raise _fail(f"areas.{name}.profiles names unknown profile(s): {', '.join(unknown)}.")

    seen: set[str] = set()
    for rule in config.get("impact") or []:
        rule_id = rule["id"]
        if rule_id in seen:
            raise _fail(f"impact: duplicate rule id '{rule_id}'.")
        seen.add(rule_id)
        for pattern in rule["paths"]:
            validate_glob(pattern, f"impact.{rule_id}.paths")
        unknown = sorted(set(rule.get("areas") or []) - set(areas))
        if unknown:
            raise _fail(f"impact.{rule_id}.areas names unknown area(s): {', '.join(unknown)}.")
        reason = rule.get("full")
        if reason is not None and reason not in reasons:
            raise _fail(
                f"impact.{rule_id}.full '{reason}' is not in full-reasons"
                + (f" ({', '.join(reasons)})." if reasons else " (none declared).")
            )

    default = config.get("default-area")
    if default is not None and default not in areas:
        raise _fail(f"default-area names unknown area '{default}'.")
    if (reasons or any("full" in rule for rule in config.get("impact") or [])) and FULL_PROFILE not in profiles:
        raise _fail(f"full escalation requires a '{FULL_PROFILE}' profile.")


def config_digest(config: dict[str, Any]) -> str:
    """Return a stable digest of every key a plan depends on."""
    relevant = {key: config.get(key) for key in ("profiles", *PLAN_KEYS)}
    text = json.dumps(relevant, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Git inputs -----------------------------------------------------------------------------


def _git(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            env=child_environment(),
            check=False,
        )
    except OSError as error:
        raise RuntimeError(f"Cannot run git: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(arguments[:2])} failed: {detail}")
    return result.stdout


def _resolve(root: Path, ref: str) -> str:
    return _git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def _names(output: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in output.split(b"\0") if item]


def collect_changed_paths(
    root: Path,
    *,
    base_ref: str | None,
    head_ref: str | None,
    include_worktree: bool,
) -> tuple[list[str], dict[str, Any]]:
    """Return sorted changed paths (relative to the project root) and the resolved Git inputs."""
    if base_ref is None and not include_worktree:
        raise RuntimeError("A validation plan needs --base-ref or --include-worktree.")
    if include_worktree and head_ref is not None:
        raise RuntimeError("--head-ref cannot be combined with --include-worktree; local changes are compared with HEAD.")
    base_name = base_ref or "HEAD"
    head_name = head_ref or "HEAD"
    base_sha = _resolve(root, base_name)
    head_sha = _resolve(root, head_name)
    merge_base = _git(root, "merge-base", base_sha, head_sha).decode().strip()
    paths = set(_names(_git(root, "diff", "--name-only", "-z", "--no-renames", "--relative", merge_base, head_sha)))
    if include_worktree:
        paths.update(_names(_git(root, "diff", "--name-only", "-z", "--no-renames", "--relative", "HEAD")))
        paths.update(_names(_git(root, "ls-files", "--others", "--exclude-standard", "-z")))
    changed = sorted(
        path for path in (normalize_project_path(item) for item in paths)
        if not path.startswith(STATE_PREFIX)
    )
    return changed, {
        "base-ref": base_name,
        "base-sha": base_sha,
        "head-ref": head_name,
        "head-sha": head_sha,
        "merge-base-sha": merge_base,
        "include-worktree": include_worktree,
    }


# --- Plan computation -----------------------------------------------------------------------


def _profile_commands(specs: dict[str, dict[str, Any]], name: str) -> list[str]:
    return list(specs[name]["commands"])


def compute_plan(
    config: dict[str, Any],
    specs: dict[str, dict[str, Any]],
    profile: str,
    changed_paths: list[str],
    inputs: dict[str, Any],
    full_justification: str | None = None,
) -> dict[str, Any]:
    """Apply the declared rules to changed paths and return a deterministic plan."""
    if profile not in specs:
        raise RuntimeError(
            f"Unknown validation profile '{profile}'. Available profiles: {', '.join(sorted(specs)) or 'none'}."
        )
    areas: dict[str, Any] = config.get("areas") or {}
    if not areas:
        raise RuntimeError("This project declares no validation areas; a plan needs 'areas' in .embraion/validation.yaml.")
    rules = list(config.get("impact") or [])
    reasons = list(config.get("full-reasons") or [])
    paths = sorted(set(changed_paths))

    if full_justification is not None and full_justification not in reasons:
        allowed = ", ".join(reasons) if reasons else "none declared"
        raise RuntimeError(f"Full justification '{full_justification}' is not in full-reasons ({allowed}).")
    if profile == FULL_PROFILE and reasons and full_justification is None:
        raise RuntimeError("The full profile needs --full-justification; allowed: " + ", ".join(reasons) + ".")

    matched_rules: list[dict[str, Any]] = []
    by_area: dict[str, dict[str, set[str]]] = {}
    unmatched: list[str] = []
    rule_escalation: dict[str, str] | None = None
    for rule in rules:
        hit = [path for path in paths if path_matches(path, list(rule["paths"]))]
        if not hit:
            continue
        matched_rules.append({
            "rule": rule["id"],
            "paths": hit,
            "areas": list(rule.get("areas") or []),
            "full": rule.get("full"),
        })
        if rule.get("full") is not None and rule_escalation is None:
            rule_escalation = {"reason": rule["full"], "source": f"rule:{rule['id']}"}
    for path in paths:
        matched = False
        for name, area in areas.items():
            if path_matches(path, list(area["paths"])):
                by_area.setdefault(name, {"paths": set(), "rules": set()})["paths"].add(path)
                matched = True
        for entry in matched_rules:
            if path in entry["paths"]:
                matched = True
                for name in entry["areas"]:
                    by_area.setdefault(name, {"paths": set(), "rules": set()})
                    by_area[name]["paths"].add(path)
                    by_area[name]["rules"].add(entry["rule"])
        if not matched:
            unmatched.append(path)

    fallback: dict[str, Any] | None = None
    default_area = config.get("default-area")
    if unmatched:
        if default_area is not None:
            by_area.setdefault(default_area, {"paths": set(), "rules": set()})["paths"].update(unmatched)
        else:
            fallback = {"reason": "unmatched-paths", "paths": list(unmatched)}

    escalation: dict[str, str] | None = None
    if full_justification is not None:
        escalation = {"reason": full_justification, "source": "justification"}
    elif rule_escalation is not None:
        escalation = rule_escalation

    selected_areas = [
        {"area": name, "paths": sorted(by_area[name]["paths"]), "rules": sorted(by_area[name]["rules"])}
        for name in areas if name in by_area
    ]

    def add(table: dict[str, list[str]], command: str, source: str) -> None:
        sources = table.setdefault(command, [])
        if source not in sources:
            sources.append(source)

    selected: dict[str, list[str]] = {}
    if escalation is not None or profile == FULL_PROFILE:
        for command in _profile_commands(specs, FULL_PROFILE):
            add(selected, command, f"profile:{FULL_PROFILE}")
    elif fallback is not None:
        for command in _profile_commands(specs, profile):
            add(selected, command, f"profile:{profile}")
    for entry in selected_areas:
        area = areas[entry["area"]]
        for command in area.get("commands") or []:
            add(selected, command, f"area:{entry['area']}")
        for name in area.get("profiles") or []:
            for command in _profile_commands(specs, name):
                add(selected, command, f"area:{entry['area']}>profile:{name}")

    covered_whole = escalation is not None or profile == FULL_PROFILE or fallback is not None
    selected_names = {entry["area"] for entry in selected_areas}
    skipped_areas = [] if covered_whole else [
        {"area": name, "reason": "no changed path matched its paths or an impact rule"}
        for name in areas if name not in selected_names
    ]
    skipped_commands = [
        {"command": command, "reason": "no selected area proves it"}
        for command in dict.fromkeys(_profile_commands(specs, profile)) if command not in selected
    ]

    skip_reason: str | None = None
    if not selected:
        skip_reason = (
            "no changed paths" if not paths
            else "the selected areas declare no commands to run"
        )
    return {
        "schema-version": PLAN_SCHEMA_VERSION,
        "profile": profile,
        "config-digest": config_digest(config),
        "inputs": dict(inputs),
        "changed-paths": paths,
        "matched-rules": matched_rules,
        "selected-areas": selected_areas,
        "skipped-areas": skipped_areas,
        "escalation": escalation,
        "fallback": fallback,
        "selected-commands": [{"command": command, "sources": sources} for command, sources in selected.items()],
        "skipped-commands": skipped_commands,
        "status": "selected" if selected else "skipped",
        "skip-reason": skip_reason,
    }


def build_plan(
    profile: str,
    *,
    project: Path | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    include_worktree: bool = False,
    full_justification: str | None = None,
) -> dict[str, Any]:
    from .project_validation import validation_profile_specs

    root = project_root(project)
    config = read_validation_config(root)
    specs = validation_profile_specs(root)
    changed, inputs = collect_changed_paths(
        root, base_ref=base_ref, head_ref=head_ref, include_worktree=include_worktree,
    )
    return compute_plan(config, specs, profile, changed, inputs, full_justification)


def default_plan_path(project: Path) -> Path:
    return state_root(project) / "validation" / "plan.json"


def write_plan(plan: dict[str, Any], path: Path) -> None:
    # Paths and commands may carry secrets; stored plans are redacted like the run evidence.
    write_json(path, redact_value(plan))


# --- Explain --------------------------------------------------------------------------------


def explain_plan(plan: dict[str, Any]) -> str:
    inputs = plan["inputs"]
    lines = [f"Validation plan for profile '{plan['profile']}'"]
    if inputs.get("base-sha"):
        lines.append(f"Base: {inputs['base-ref']} ({inputs['base-sha'][:12]})")
        lines.append(f"Head: {inputs['head-ref']} ({inputs['head-sha'][:12]})")
        lines.append("Uncommitted changes: " + ("included" if inputs.get("include-worktree") else "not included"))
    paths = plan["changed-paths"]
    lines.append(f"Changed paths ({len(paths)}):")
    lines += [f"  {path}" for path in paths] or ["  none"]
    lines.append("Matched rules:")
    for rule in plan["matched-rules"]:
        effect = []
        if rule["areas"]:
            effect.append("areas " + ", ".join(rule["areas"]))
        if rule["full"]:
            effect.append(f"full escalation ({rule['full']})")
        lines.append(f"  {rule['rule']}: {len(rule['paths'])} path(s) -> " + "; ".join(effect))
    if not plan["matched-rules"]:
        lines.append("  none")
    lines.append("Selected areas:")
    for entry in plan["selected-areas"]:
        how = f"{len(entry['paths'])} changed path(s)"
        if entry["rules"]:
            how += ", rule(s) " + ", ".join(entry["rules"])
        lines.append(f"  {entry['area']}: selected by {how}")
    if not plan["selected-areas"]:
        lines.append("  none")
    if plan["skipped-areas"]:
        lines.append("Skipped areas:")
        lines += [f"  {item['area']}: {item['reason']}" for item in plan["skipped-areas"]]
    escalation = plan["escalation"]
    lines.append(
        f"Escalation: full profile because '{escalation['reason']}' ({escalation['source']})"
        if escalation else "Escalation: none"
    )
    fallback = plan["fallback"]
    if fallback:
        lines.append(
            f"Fallback: the whole '{plan['profile']}' profile runs because {len(fallback['paths'])} "
            "changed path(s) match no area or rule: " + ", ".join(fallback["paths"])
        )
    lines.append(f"Selected commands ({len(plan['selected-commands'])}):")
    for number, item in enumerate(plan["selected-commands"], start=1):
        lines.append(f"  {number}. {item['command']}  [{', '.join(item['sources'])}]")
    if plan["skipped-commands"]:
        lines.append("Commands of the profile not selected:")
        lines += [f"  {item['command']}: {item['reason']}" for item in plan["skipped-commands"]]
    lines.append(
        "Result: skipped - " + str(plan["skip-reason"]) if plan["status"] == "skipped" else "Result: run the selected commands"
    )
    return "\n".join(lines)


# --- Run integration ------------------------------------------------------------------------


def parse_source(source: Any) -> tuple[str | None, str | None]:
    """Split a command source into (area, profile): ``area:A``, ``profile:P`` or ``area:A>profile:P``."""
    if isinstance(source, str) and source.startswith("area:"):
        area, _, rest = source[len("area:"):].partition(">")
        if not rest:
            return area, None
        if rest.startswith("profile:"):
            return area, rest[len("profile:"):]
    elif isinstance(source, str) and source.startswith("profile:"):
        return None, source[len("profile:"):]
    raise RuntimeError(f"Validation plan has an unknown command source: {source!r}.")


def _check_sources(
    path: Path,
    selected: list[dict[str, Any]],
    config: dict[str, Any],
    specs: dict[str, dict[str, Any]],
) -> None:
    """Every selected command must come from the place its sources name, as the configuration declares it."""
    areas = config.get("areas") or {}
    for item in selected:
        command = item["command"]
        sources = item.get("sources")
        if not isinstance(sources, list) or not sources:
            raise RuntimeError(f"Validation plan {path} selects a command without a source.")
        for source in sources:
            area, owner = parse_source(source)
            if area is None:
                declared = True
            elif area not in areas:
                declared = False
            elif owner is None:
                declared = command in (areas[area].get("commands") or [])
            else:
                declared = owner in (areas[area].get("profiles") or [])
            if declared and owner is not None:
                declared = owner in specs and command in specs[owner]["commands"]
            if not declared:
                raise RuntimeError(
                    f"Validation plan {path} selects a command that is not declared in the configuration."
                )


def _check_inputs_current(path: Path, plan: dict[str, Any], root: Path) -> None:
    """A stored plan is valid only for the Git state it was computed from."""
    inputs = plan.get("inputs")
    keys = ("base-ref", "base-sha", "head-ref", "head-sha")
    if not isinstance(inputs, dict) or any(not isinstance(inputs.get(key), str) or not inputs[key] for key in keys):
        raise RuntimeError(f"Validation plan {path} has no usable Git inputs.")
    hint = "Run 'validation plan' again."
    for side in ("base", "head"):
        current = _resolve(root, inputs[f"{side}-ref"])
        if current != inputs[f"{side}-sha"]:
            raise RuntimeError(
                f"Validation plan {path} is stale: {side} ref '{inputs[f'{side}-ref']}' now resolves to "
                f"{current[:12]}, not {inputs[f'{side}-sha'][:12]}. {hint}"
            )
    if inputs.get("include-worktree"):
        current_paths, _ = collect_changed_paths(
            root, base_ref=inputs["base-ref"], head_ref=None, include_worktree=True,
        )
        if current_paths != plan.get("changed-paths"):
            raise RuntimeError(f"Validation plan {path} is stale: the changed files differ from the plan. {hint}")


def load_plan_file(path: Path, profile: str, project: Path | None = None) -> dict[str, Any]:
    """Read a stored plan and fail closed when it does not match the current configuration."""
    from .project_validation import validation_profile_specs

    root = project_root(project)
    if not path.is_file():
        raise RuntimeError(f"Unknown validation plan file: {path}")
    try:
        plan = read_json(path)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Unreadable validation plan {path}: {error}") from error
    if not isinstance(plan, dict) or plan.get("schema-version") != PLAN_SCHEMA_VERSION:
        raise RuntimeError(f"Validation plan {path} must use schema-version {PLAN_SCHEMA_VERSION}.")
    if plan.get("profile") != profile:
        raise RuntimeError(f"Validation plan {path} is for profile '{plan.get('profile')}', not '{profile}'.")
    config = read_validation_config(root)
    if plan.get("config-digest") != config_digest(config):
        raise RuntimeError(f"Validation plan {path} is stale: .embraion/validation.yaml changed. Run 'validation plan' again.")
    selected = plan.get("selected-commands")
    if not isinstance(selected, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("command"), str) for item in selected
    ):
        raise RuntimeError(f"Validation plan {path} has an invalid selected-commands list.")
    if plan.get("status") != ("selected" if selected else "skipped"):
        raise RuntimeError(f"Validation plan {path} has an inconsistent status.")
    specs = validation_profile_specs(root)
    _check_sources(path, selected, config, specs)
    _check_inputs_current(path, plan, root)
    inputs = plan["inputs"]
    include_worktree = inputs.get("include-worktree")
    if not isinstance(include_worktree, bool):
        raise RuntimeError(f"Validation plan {path} has invalid include-worktree input.")
    changed, current_inputs = collect_changed_paths(
        root, base_ref=inputs["base-ref"],
        head_ref=None if include_worktree else inputs["head-ref"],
        include_worktree=include_worktree,
    )
    escalation = plan.get("escalation")
    justification = (
        escalation.get("reason")
        if isinstance(escalation, dict) and escalation.get("source") == "justification"
        else None
    )
    expected = compute_plan(config, specs, profile, changed, current_inputs, justification)
    if plan != expected:
        raise RuntimeError(
            f"Validation plan {path} does not match the current Git diff and configured selection. "
            "Run 'validation plan' again."
        )
    return plan


def resolve_run_plan(
    profile: str,
    *,
    project: Path | None = None,
    plan_file: str | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    include_worktree: bool = False,
    full_justification: str | None = None,
) -> dict[str, Any] | None:
    """Return the plan a run must follow, or None for the unchanged full-profile run."""
    root = project_root(project)
    requested = bool(plan_file or base_ref or include_worktree)
    if not requested:
        if head_ref or full_justification:
            raise RuntimeError("--head-ref and --full-justification need --base-ref, --include-worktree or --plan.")
        return None
    config = read_validation_config(root)
    if not declares_areas(config):
        raise RuntimeError("This project declares no validation areas, so plan options cannot be used.")
    if plan_file:
        if base_ref or head_ref or include_worktree or full_justification:
            raise RuntimeError("--plan cannot be combined with --base-ref, --head-ref, --include-worktree or --full-justification.")
        return load_plan_file(Path(plan_file), profile, root)
    return build_plan(
        profile,
        project=root,
        base_ref=base_ref,
        head_ref=head_ref,
        include_worktree=include_worktree,
        full_justification=full_justification,
    )


def plan_spec(
    specs: dict[str, dict[str, Any]],
    profile: str,
    plan: dict[str, Any],
    parameters: dict[str, str] | None,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Return the planned profile's spec restricted to the plan's commands.

    Each command keeps the run semantics of the place it was selected from. A command
    from a profile uses that profile's entry, timeout and parameters (the planned
    profile first when several profiles list it). A command from ``area.commands`` is
    always required and has no prerequisites, timeout or parameters.
    """
    spec = specs[profile]
    commands: list[str] = []
    entries: list[dict[str, Any]] = []
    timeouts: list[float | None] = []
    owners: list[tuple[str | None, int]] = []
    # Profile safeguards apply to the entire planned run, independently of the
    # owner that supplies each command's timeout and parameters.
    guarded = [profile]
    if plan.get("escalation") is not None and FULL_PROFILE not in guarded:
        guarded.append(FULL_PROFILE)
    for item in plan["selected-commands"]:
        command = item["command"]
        sources = item.get("sources")
        if not sources:
            raise RuntimeError(f"Validation plan selects '{command}' without a source.")
        parsed = [parse_source(source)[1] for source in sources]
        profile_sources = [name for name in dict.fromkeys(parsed) if name is not None]
        for name in profile_sources:
            if name not in specs or command not in specs[name]["commands"]:
                raise RuntimeError(f"Validation plan selects '{command}' from profile '{name}', which does not declare it.")
            if name not in guarded:
                guarded.append(name)
        owner = profile if profile in profile_sources else (profile_sources[0] if profile_sources else None)
        entry: dict[str, Any] = {"required": True, "requires": {}}
        timeout: float | None = None
        position = -1
        if owner is not None:
            if owner not in specs or command not in specs[owner]["commands"]:
                raise RuntimeError(f"Validation plan selects '{command}' from profile '{owner}', which does not declare it.")
            position = specs[owner]["commands"].index(command)
            entry = specs[owner]["entries"][position]
            timeout = specs[owner]["timeouts"][position]
        if None in parsed:
            entry = {"required": True, "requires": {}}
            timeout = None
            owner, position = None, -1
        commands.append(command)
        entries.append(entry)
        timeouts.append(timeout)
        owners.append((owner, position))

    # A parameter applies only to the commands of the profile that declares it.
    used = list(dict.fromkeys(owner for owner, _ in owners if owner is not None))
    kept: dict[str, dict[str, Any]] = {}
    declared_by: dict[str, str] = {}
    for name in used:
        for parameter, definition in (specs[name].get("parameters") or {}).items():
            targets = {int(target) for target in definition.get("commands") or []}
            numbers = [
                number for number, (owner, position) in enumerate(owners, start=1)
                if owner == name and (not targets or position + 1 in targets)
            ]
            if not numbers:
                continue
            base = {key: value for key, value in definition.items() if key != "commands"}
            if parameter in kept:
                if {key: value for key, value in kept[parameter].items() if key != "commands"} != base:
                    raise RuntimeError(
                        f"Parameter '{parameter}' is declared differently by profiles "
                        f"'{declared_by[parameter]}' and '{name}', which this plan runs together."
                    )
                kept[parameter]["commands"] = sorted(set(kept[parameter]["commands"]) | set(numbers))
            else:
                kept[parameter] = {**base, "commands": numbers}
                declared_by[parameter] = name
    supplied_names = set(parameters or {})
    for parameter, definition in kept.items():
        if definition.get("required") and "default" not in definition and parameter not in supplied_names:
            raise RuntimeError(
                f"The plan runs commands of profile '{declared_by[parameter]}', which requires parameter "
                f"'{parameter}'; pass --param {parameter}=VALUE."
            )
    # A value for a parameter this plan does not need is ignored; unknown names still fail later.
    known = {name for other in specs.values() for name in (other.get("parameters") or {})}
    supplied = None if parameters is None else {
        key: value for key, value in parameters.items() if key in kept or key not in known
    }
    limits = [specs[name]["output-limit"] for name in guarded if specs[name].get("output-limit")]
    return {
        **spec,
        "commands": commands,
        "entries": entries,
        "parameters": kept,
        "timeouts": timeouts,
        "clean-tree": any(specs[name].get("clean-tree") for name in guarded),
        "output-limit": min(limits) if limits else None,
    }, supplied


def write_plan_evidence(project: Path, evidence_id: str, plan: dict[str, Any]) -> str:
    """Store the plan next to the run evidence; return its project-relative path."""
    path = state_root(project) / "validation" / evidence_id / "plan.json"
    write_plan(plan, path)
    return path.relative_to(project).as_posix()
