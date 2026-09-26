from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .common import find_project_root, framework_root, project_root
from .context import build_context, read_context
from .contracts import (
    PROJECT_CONTRACT_SLOT_NAMES,
    project_contract_status,
)
from .evidence import complete_run, read_run, start_run
from .execution import execute
from .enforcement import (
    check_enforcement,
    enforcement_status,
    install_enforcement_surface,
)
from .harness import audit_harness
from .evals import compare, create_baseline, run_case
from .learning import observe, transition
from .policy import effective_policy, read_knowledge_config
from .pricing import calculate_cost, pricing_status, refresh_pricing
from .project import (
    init_project,
    install,
    projection_is_verified,
    projection_plan,
    sync,
    update_project,
)
from .project_validation import (
    run_validation_profile,
    validation_profile_specs,
)
from .runtime import (
    create_dispatch,
    get_deployment,
    list_deployments,
    read_session,
    route,
    start_session,
    update_session,
)
from .security import (
    SEVERITY_ORDER,
    collect_findings,
    redact_text,
    save_mcp_inventory,
)
from .validation import collect_issues
from .worktree import create_worktree, gc_worktrees, list_worktrees, salvage_worktree
from .versioning import (
    cache_home,
    find_project_manifest,
    list_cached_runtimes,
    package_version_for_pin,
    project_runtime_status,
    prune_cache,
    read_project_pin,
    resolve_project_runtime,
)


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _subprocess_error_message(error: subprocess.CalledProcessError) -> str:
    for value in (error.stderr, error.stdout):
        if value and value.strip():
            return value.strip()
    return str(error)


def _print_main_help(file: object | None = None) -> None:
    stream = file or sys.stdout
    lines = [
        f"EmbrAIon {__version__} — AI-First Engineering System",
        "",
        "Usage",
        "  embraion <command> [options]",
        "  embraion help [command]",
        "",
        "Project & setup",
        "  init       Add EmbrAIon to a project and create .embraion/project.yaml",
        "  install    Install a host projection (Codex, Copilot, Claude Code, Portable)",
        "  projection Preview ownership-aware projection changes",
        "  policy     Inspect the effective project policy overlay",
        "  update     Change the current project's pinned EmbrAIon version",
        "  sync       Generate disposable host projections without installing them",
        "",
        "Health & runtime",
        "  doctor     Run framework and project diagnostics",
        "  status     Show launcher, project pin, active runtime, cache, and host projections",
        "  validate   Validate the framework, schemas, catalog, and localization",
        "  cache      Inspect or clean cached project-pinned EmbrAIon runtimes",
        "",
        "AI execution",
        "  deployment Inspect the project-owned deployment/provider registry",
        "  route      Resolve host-default or project routing for a task route class",
        "  dispatch   Create a bounded execution plan with access and owned-path constraints",
        "  execute    Process a versioned execution request from stdin",
        "  pricing    Inspect or explicitly refresh approved official pricing sources",
        "  context    Select project knowledge with provenance and privacy metadata",
        "  run        Record structured execution evidence for an engineering run",
        "  session    Create, inspect, or update normalized task/session state",
        "",
        "Engineering controls",
        "  validation Run project validation profiles and record evidence",
        "  enforcement Check or explicitly install project enforcement gates",
        "  security   Scan a path for secrets and policy drift",
        "  mcp        Inspect and record privacy-safe MCP configuration",
        "  harness    Audit host agents, skills, and native enforcement surfaces",
        "  worktree   List, create, clean, or salvage Git worktrees",
        "  learning   Record evidence and manage gated learning candidates",
        "  eval       Run behavioral evals and compare baselines",
        "",
        "Help",
        "  help       Show this command catalog or detailed help for one command",
        "",
        "Examples",
        "  embraion init",
        "  embraion doctor",
        "  embraion status",
        "  embraion install --host codex --destination .",
        "  embraion help status",
        "  embraion cache prune --older-than 90",
        "",
        "More",
        "  embraion help <command>       Detailed help for a command",
        "  embraion <command> --help     Same command-specific help",
        "  embraion --version            Show the active runtime version",
    ]
    print("\n".join(lines), file=stream)


class EmbrAIonArgumentParser(argparse.ArgumentParser):
    def print_help(self, file: object | None = None) -> None:
        if self.prog == "embraion":
            _print_main_help(file)
            return
        super().print_help(file)


def _find_subparser(
    parser: argparse.ArgumentParser,
    command_path: list[str],
) -> argparse.ArgumentParser | None:
    current = parser

    for command in command_path:
        action = next(
            (
                item
                for item in current._actions
                if isinstance(item, argparse._SubParsersAction)
            ),
            None,
        )
        if action is None or command not in action.choices:
            return None
        current = action.choices[command]

    return current


def _cmd_help(args: argparse.Namespace) -> int:
    root_parser = args.root_parser
    topics = list(args.topic or [])

    if not topics:
        root_parser.print_help()
        return 0

    target = _find_subparser(root_parser, topics)
    if target is None:
        print(f"Unknown help topic: {' '.join(topics)}", file=sys.stderr)
        print("Run 'embraion help' to see available commands.", file=sys.stderr)
        return 2

    target.print_help()
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = framework_root(Path(args.root) if args.root else None)
    issues = collect_issues(root)

    if args.json:
        _print_json({"issues": issues, "count": len(issues)})
    elif issues:
        for issue in issues:
            print(
                f"{issue['severity'].upper():7} "
                f"{issue['code']:22} "
                f"{issue['path']}: {issue['message']}"
            )
    else:
        print("PASS: no validation issues.")

    return 1 if any(item["severity"] == "error" for item in issues) else 0


def _cmd_init(args: argparse.Namespace) -> int:
    path = init_project(
        Path(args.path or "."),
        name=args.name,
        force=args.force,
    )
    print(f"Created {path}")
    return 0


def _print_projection_plan(plan: dict[str, object]) -> None:
    print(f"Projection: {plan['host']}")
    print(f"Destination: {plan['destination']}")
    print(f"Components: {', '.join(plan.get('components', []))}")
    if plan.get("config-mode"):
        print(f"Codex config mode: {plan['config-mode']}")
    for key in (
        "create",
        "update",
        "unchanged",
        "conflict",
        "obsolete-owned",
        "obsolete-modified",
    ):
        values = list(plan.get(key, []) or [])
        print(f"{key}: {len(values)}")
        for value in values:
            print(f"  {value}")


def _cmd_install(args: argparse.Namespace) -> int:
    plan = install(
        args.host,
        Path(args.destination or "."),
        force=args.force,
        dry_run=args.dry_run,
        prune=args.prune,
        components=args.component,
        config_mode=args.config_mode,
    )
    if args.json:
        _print_json(plan)
    elif args.dry_run:
        _print_projection_plan(plan)
    else:
        print(f"Installed {args.host} projection into {Path(args.destination or '.').resolve()}")
        print(
            f"Created {len(plan['create'])}, updated {len(plan['update'])}, "
            f"unchanged {len(plan['unchanged'])}."
        )
    return 0


def _cmd_projection_diff(args: argparse.Namespace) -> int:
    plan = projection_plan(
        args.host,
        Path(args.destination or "."),
        components=args.component,
        config_mode=args.config_mode,
    )
    if args.json:
        _print_json(plan)
    else:
        _print_projection_plan(plan)
    return 1 if plan["conflict"] or plan["obsolete-modified"] else 0


def _cmd_projection_verify(args: argparse.Namespace) -> int:
    plan = projection_plan(
        args.host,
        Path(args.destination or "."),
        components=args.component,
        config_mode=args.config_mode,
    )
    verified = projection_is_verified(plan)
    if args.json:
        _print_json({**plan, "verified": verified})
    else:
        _print_projection_plan(plan)
        print(f"verified: {'yes' if verified else 'no'}")
    return 0 if verified else 1


def _cmd_policy_show(args: argparse.Namespace) -> int:
    policy = effective_policy()
    if args.json:
        _print_json(policy)
    else:
        print("EmbrAIon Project Policy")
        print()
        print(f"Default privacy: {policy['privacy']['default-class']}")
        print(
            "Substantial review required: "
            f"{policy['review']['substantial-required']}"
        )
        validation_specs = validation_profile_specs()
        for name, spec in validation_specs.items():
            print(
                f"Validation {name}: {len(spec['commands'])} command(s), "
                f"{len(spec.get('parameters') or {})} parameter(s)"
            )
        for category, patterns in policy["sources"].items():
            print(f"Sources {category}: {len(patterns)} pattern(s)")
        print(f"Routing override hosts: {len(policy['routing']['overrides'])}")
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    previous, current = update_project(
        Path(args.path or "."),
        version=args.framework_version,
    )
    print(f"Updated framework version: {previous} -> {current}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    root = framework_root()
    output = Path(args.output or (root / "build/generated")).resolve()
    generated = sync(args.host, output, force=args.force)

    for path in generated:
        print(f"Generated {path}")

    return 0


def _cmd_deployment_list(args: argparse.Namespace) -> int:
    report = list_deployments()
    if args.json:
        _print_json(report)
        return 0
    print("EmbrAIon Project Deployments")
    print()
    print(f"Providers: {report['provider-count']}")
    print(f"Deployments: {report['deployment-count']}")
    for deployment_id, definition in report["deployments"].items():
        state = "enabled" if definition.get("enabled", True) else "disabled"
        print(
            f"  {deployment_id}: host={definition['host']} "
            f"model={definition['model']} ({state})"
        )
    return 0


def _cmd_deployment_show(args: argparse.Namespace) -> int:
    deployment = get_deployment(args.deployment_id)
    if args.json:
        _print_json(deployment)
        return 0
    print(f"Deployment: {deployment['id']}")
    print(f"Host: {deployment['host']}")
    print(f"Provider: {deployment.get('provider') or '-'}")
    print(f"Model: {deployment['model']}")
    print(f"Enabled: {deployment.get('enabled', True)}")
    print(f"Efforts: {', '.join(deployment.get('efforts') or []) or '-'}")
    print(f"Default effort: {deployment.get('default-effort') or '-'}")
    return 0


def _cmd_route(args: argparse.Namespace) -> int:
    _print_json(route(args.host, args.route_class, args.data, role=args.role))
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    _print_json(
        create_dispatch(
            args.task,
            args.role,
            args.host,
            args.route_class,
            args.data,
            args.access,
            args.owned_path or [],
        )
    )
    return 0


def _cmd_pricing_status(args: argparse.Namespace) -> int:
    report = pricing_status()
    if args.json:
        _print_json(report)
    else:
        print(f"Pricing snapshot: {'valid' if report['valid'] else 'missing/invalid'}")
        print(f"Digest: {report['digest'] or '-'}")
        for source in report["sources"]:
            state = "STALE" if source["stale"] else "current"
            print(f"{source['id']}: {state} ({', '.join(source['reasons']) or 'verified'})")
        for deployment in report["orphanEntries"]:
            print(f"{deployment}: STALE (source or SKU no longer configured)")
        if report["lastRefresh"]:
            print(f"Last refresh: {report['lastRefresh']['status']}")
    return 1 if args.fail_on_stale and (report["stale"] or not report["valid"]) else 0


def _cmd_pricing_refresh(args: argparse.Namespace) -> int:
    report = refresh_pricing(source_id=args.source)
    if args.json:
        _print_json(report)
    else:
        print(f"Pricing refresh: {report['status']} ({report['digest']})")
        for change in report["changes"]:
            print(f"  {change['kind']}: {change['deployment']} {change['sku']}")
    return 0


def _cmd_pricing_calculate(args: argparse.Namespace) -> int:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise RuntimeError("Pricing calculation stdin is not valid JSON.") from error
    if not isinstance(request, dict) or set(request) - {"deployment", "usage", "usageSemantics", "billing", "providerExact", "adapterCost", "reportedCurrency", "atUtc", "batch", "discount"}:
        raise RuntimeError("Pricing calculation request has unknown fields.")
    if not isinstance(request.get("deployment"), str) or not request["deployment"]:
        raise RuntimeError("Pricing calculation requires a deployment ID.")
    from datetime import datetime
    at = datetime.fromisoformat(request["atUtc"].replace("Z", "+00:00")) if request.get("atUtc") else None
    _print_json(calculate_cost(
        request["deployment"], request.get("usage"), at=at,
        billing=request.get("billing", "api"), provider_exact=request.get("providerExact"),
        adapter_cost=request.get("adapterCost"), batch=request.get("batch", False),
        discount=request.get("discount"), usage_semantics=request.get("usageSemantics"),
        reported_currency=request.get("reportedCurrency"),
    ))
    return 0


def _cmd_execute(args: argparse.Namespace) -> int:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise RuntimeError("Execution stdin is not valid JSON.") from error
    result = execute(request)
    _print_json(result)
    return 0 if result["status"] in {"completed", "handoff-required"} else 1


def _cmd_context_build(args: argparse.Namespace) -> int:
    _print_json(
        build_context(
            args.task,
            args.role,
            args.data,
            max_chars=args.max_chars,
            slots=args.slot,
        )
    )
    return 0


def _cmd_context_show(args: argparse.Namespace) -> int:
    _print_json(read_context(args.context_id))
    return 0


def _cmd_context_slots(args: argparse.Namespace) -> int:
    project = find_project_root()
    if project is None:
        raise RuntimeError("No EmbrAIon project detected.")

    report = project_contract_status(
        read_knowledge_config(project),
        project,
    )
    if args.json:
        _print_json(report)
        return 0

    print("Project Contract Slots")
    print()
    for item in report["slots"]:
        if item["configured"]:
            if item.get("inside-project") is False:
                state = "INVALID"
            else:
                state = "OK" if item["exists"] else "MISSING"
            print(f"[{state}] {item['id']}: {item['path']}")
        else:
            print(f"[UNBOUND] {item['id']}")
    print()
    print(
        f"Configured: {report['configured']}/{report['total']}  "
        f"Available: {report['available']}/{report['total']}"
    )
    return 0


def _cmd_run_start(args: argparse.Namespace) -> int:
    _print_json(
        start_run(
            args.run_id,
            args.task,
            args.role,
            args.host,
            args.route_class,
            args.data,
            args.access,
            args.owned_path or [],
            context_id=args.context_id,
            substantial=args.substantial,
        )
    )
    return 0


def _validation_entries(values: list[str] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in values or []:
        if "=" not in value:
            raise RuntimeError("--validation must use PROFILE=STATUS.")
        profile, status = value.split("=", 1)
        rows.append({"profile": profile.strip(), "status": status.strip()})
    return rows


def _cmd_run_complete(args: argparse.Namespace) -> int:
    _print_json(
        complete_run(
            args.run_id,
            changed_paths=args.changed_path or [],
            validation=_validation_entries(args.validation),
            review=args.review,
            outcome=args.outcome,
            residual_risks=args.residual_risk or [],
        )
    )
    return 0


def _cmd_run_show(args: argparse.Namespace) -> int:
    _print_json(read_run(args.run_id))
    return 0


def _cmd_session_start(args: argparse.Namespace) -> int:
    _print_json(
        start_session(
            args.session_id,
            args.task,
            role=args.role,
            host=args.host,
            model=args.model,
            effort=args.effort,
            access=args.access,
        )
    )
    return 0


def _cmd_session_show(args: argparse.Namespace) -> int:
    _print_json(read_session())
    return 0


def _cmd_session_set(args: argparse.Namespace) -> int:
    _print_json(
        update_session(
            state=args.state,
            validation=args.validation,
            review=args.review,
        )
    )
    return 0


def _named_values(
    values: list[str] | None,
    *,
    option: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise RuntimeError(f"{option} must use NAME=VALUE.")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise RuntimeError(f"{option} requires a non-empty parameter name.")
        if name in parsed:
            raise RuntimeError(f"Duplicate {option} parameter: {name}")
        parsed[name] = value
    return parsed


def _cmd_validation_list(args: argparse.Namespace) -> int:
    specs = validation_profile_specs()
    if args.json:
        _print_json(
            {
                "profiles": {
                    name: {
                        "commands": list(spec["commands"]),
                        "command-count": len(spec["commands"]),
                        "parameters": spec.get("parameters") or {},
                    }
                    for name, spec in specs.items()
                }
            }
        )
        return 0

    print("EmbrAIon Project Validation Profiles")
    print()
    if not specs:
        print("No validation profiles configured.")
        return 0

    for name, spec in specs.items():
        commands = list(spec["commands"])
        parameters = spec.get("parameters") or {}
        print(
            f"{name}: {len(commands)} command(s), "
            f"{len(parameters)} parameter(s)"
        )
        for command in commands:
            print(f"  {command}")
        for parameter, definition in parameters.items():
            target = (
                f"argument {definition['argument']}"
                if definition.get("argument")
                else f"environment {definition['environment']}"
            )
            required = "required" if definition.get("required") else "optional"
            print(f"  param {parameter}: {target} ({required})")
    return 0


def _cmd_validation_run(args: argparse.Namespace) -> int:
    record = run_validation_profile(
        args.profile,
        run_id=args.run_id,
        fail_fast=args.fail_fast,
        timeout=args.timeout,
        parameters=_named_values(args.param, option="--param"),
    )

    if args.json:
        _print_json(record)
    else:
        print(f"Validation profile: {record['profile']}")
        print(f"Status: {record['status']}")
        if record["status"] == "skipped":
            print("No commands are configured for this profile.")
        for item in record["commands"]:
            label = {
                "passed": "PASS",
                "failed": "FAIL",
                "timed-out": "TIMEOUT",
            }[item["status"]]
            exit_code = (
                "-"
                if item["exit-code"] is None
                else str(item["exit-code"])
            )
            print(
                f"[{label}] {item['index']}/{record['command-count']} "
                f"exit={exit_code} {item['duration-ms']}ms"
            )
            print(f"  {item['command']}")
            if item["stdout"]:
                print(item["stdout"].rstrip())
            if item["stderr"]:
                print(item["stderr"].rstrip(), file=sys.stderr)
        print(f"Evidence: {record['evidence-path']}")
        if record.get("run-id"):
            print(f"Attached run: {record['run-id']}")

    return 1 if record["status"] == "failed" else 0


def _cmd_enforcement_status(args: argparse.Namespace) -> int:
    report = enforcement_status()
    if args.json:
        _print_json(report)
    else:
        policy = report["policy"]
        surface = report["surfaces"]["github-actions"]
        print("EmbrAIon Enforcement")
        print()
        print(f"Enabled: {policy['enabled']}")
        print(f"Validation profile: {policy['validation-profile']}")
        print(f"Review required: {policy['require-review']}")
        print(
            "GitHub Actions gate: "
            + ("present" if surface["present"] else "not installed")
        )
    return 0


def _cmd_enforcement_check(args: argparse.Namespace) -> int:
    record = check_enforcement(
        base_ref=args.base_ref,
        run_id=args.run_id,
        external_review_gate=args.external_review_gate,
    )
    if args.json:
        _print_json(record)
    else:
        print("EmbrAIon Enforcement Check")
        print()
        print(f"Base ref: {record['base-ref']}")
        print(f"Changed paths: {len(record['changed-paths'])}")
        for item in record["checks"]:
            print(f"{item['id']}: {item['status']}")
            for path in item.get("changed-paths") or []:
                print(f"  {path}")
        print(f"Evidence: {record['evidence-path']}")
        print("PASS" if record["passed"] else "FAIL")
    return 0 if record["passed"] else 1


def _cmd_enforcement_install(args: argparse.Namespace) -> int:
    report = install_enforcement_surface(
        surface=args.surface,
        validation_profile=args.validation_profile,
        require_review=args.require_review,
        force=args.force,
    )
    if args.json:
        _print_json(report)
    else:
        print(f"Installed enforcement surface: {report['surface']}")
        print(f"Path: {report['path']}")
        print(f"Validation profile: {report['validation-profile']}")
        print(f"Review required: {report['require-review']}")
        print(report["note"])
    return 0


def _cmd_security_scan(args: argparse.Namespace) -> int:
    root = Path(args.path or ".").resolve()
    findings = collect_findings(root)

    if args.json:
        _print_json({"findings": findings})
    elif findings:
        for finding in findings:
            print(
                f"{finding['severity'].upper():8} "
                f"{finding['category']:18} "
                f"{finding.get('path', '')}: {finding['message']}"
            )
    else:
        print("PASS: no security findings.")

    threshold = SEVERITY_ORDER[args.fail_on]
    return (
        1
        if any(
            SEVERITY_ORDER[finding["severity"]] >= threshold
            for finding in findings
        )
        else 0
    )


def _cmd_security_redact(args: argparse.Namespace) -> int:
    print(redact_text(args.text))
    return 0


def _cmd_harness_audit(args: argparse.Namespace) -> int:
    report = audit_harness(args.host)
    _print_json(report)
    return 0 if all(item["ready"] for item in report["hosts"]) else 1


def _cmd_mcp_inventory(args: argparse.Namespace) -> int:
    project = project_root(Path(args.path) if args.path else None)
    output = Path(args.output).resolve() if args.output else None
    _print_json(save_mcp_inventory(project, output))
    return 0


def _cmd_worktree_list(args: argparse.Namespace) -> int:
    _print_json(list_worktrees())
    return 0


def _cmd_worktree_create(args: argparse.Namespace) -> int:
    destination = (
        Path(args.path).resolve()
        if args.path
        else None
    )
    created = create_worktree(
        args.branch,
        destination=destination,
        base=args.base or "origin/main",
    )
    print(f"Created {created}")
    return 0


def _cmd_worktree_gc(args: argparse.Namespace) -> int:
    candidates = gc_worktrees(
        base=args.base,
        apply=args.apply,
    )

    if not candidates:
        print("No safely removable worktrees found.")
        return 0

    for item in candidates:
        print(
            f"CANDIDATE {item.get('branch')} "
            f"{item['path']} {item.get('head')}"
        )

    if not args.apply:
        print("Dry run only. Re-run with --apply to remove these candidates.")

    return 0


def _cmd_worktree_salvage(args: argparse.Namespace) -> int:
    destination = salvage_worktree(
        Path(args.path),
        output=Path(args.output).resolve() if args.output else None,
    )
    print(f"Salvaged worktree evidence to {destination}")
    return 0


def _cmd_learning_observe(args: argparse.Namespace) -> int:
    _print_json(
        observe(
            args.id,
            args.kind,
            args.target_type,
            args.target_id,
            args.summary,
            run_id=args.run_id,
            eval_id=args.eval_id,
        )
    )
    return 0


def _cmd_learning_transition(args: argparse.Namespace) -> int:
    _print_json(transition(args.id, args.action))
    return 0


def _cmd_eval_run(args: argparse.Namespace) -> int:
    report = run_case(
        args.case,
        Path(args.record),
        output=Path(args.output).resolve() if args.output else None,
    )
    _print_json(report)
    return 0 if report["passed"] else 1


def _cmd_eval_baseline(args: argparse.Namespace) -> int:
    _print_json(
        create_baseline(
            Path(args.reports),
            Path(args.output),
        )
    )
    return 0


def _cmd_eval_compare(args: argparse.Namespace) -> int:
    result = compare(
        Path(args.baseline),
        Path(args.reports),
    )
    _print_json(result)
    return 0 if result["pass-rate-delta"] >= 0 else 1


def _detect_host_projections(project: Path | None) -> list[str]:
    if project is None:
        return []

    projections: list[str] = []

    if (project / ".codex" / "config.toml").is_file():
        projections.append("Codex")

    copilot = project / ".github" / "agents"
    if copilot.is_dir() and any(copilot.glob("*.agent.md")):
        projections.append("GitHub Copilot")

    claude = project / ".claude" / "agents"
    if claude.is_dir() and any(claude.glob("*.md")):
        projections.append("Claude Code")

    portable_candidates = [
        project / "vendor" / "embraion" / "embraion" / "plugin.json",
        project / "vendor" / "embraion" / "plugin.json",
        project / "embraion" / "plugin.json",
    ]
    if any(path.is_file() for path in portable_candidates):
        projections.append("Portable")

    return projections


def _cmd_status(args: argparse.Namespace) -> int:
    status = project_runtime_status(__version__)
    project = Path(str(status["project"])) if status["project"] else None
    projections = _detect_host_projections(project)
    status["host-projections"] = projections

    if args.json:
        _print_json(status)
        return 0

    print("EmbrAIon Status")
    print()
    print(f"Launcher: {status['launcher-version']}")

    if status["project"] is None:
        print("Project: not detected")
        print(f"Active runtime: launcher ({status['resolved-version']})")
    else:
        print(f"Project: {status['project']}")
        print(f"Project pin: {status['project-pin']}")
        print(f"Resolved runtime: {status['resolved-version']}")
        print(f"Runtime source: {status['runtime-source']}")
        if status["runtime-cache"]:
            state = "ready" if status["runtime-cached"] else "not cached yet"
            print(f"Runtime cache: {status['runtime-cache']} ({state})")

        if projections:
            print(f"Host projections: {', '.join(projections)}")
        else:
            print("Host projections: none detected")

    print(f"Cache root: {status['cache-root']}")
    print(f"Cached versions: {status['cached-versions']}")
    return 0


def _cmd_cache_list(args: argparse.Namespace) -> int:
    entries = list_cached_runtimes()

    if args.json:
        _print_json({"cache-root": str(cache_home()), "runtimes": entries})
        return 0

    print("EmbrAIon Runtime Cache")
    print()

    if not entries:
        print("No cached project runtimes.")
        return 0

    for item in entries:
        last_used = item["last-used-utc"] or "unknown"
        print(
            f"{item['version']}  {item['state']}  "
            f"last used {last_used}"
        )
        print(f"  {item['path']}")

    return 0


def _cmd_cache_prune(args: argparse.Namespace) -> int:
    protected = [__version__]
    manifest = find_project_manifest()
    if manifest is not None:
        protected.append(read_project_pin(manifest))

    candidates = prune_cache(
        apply=args.apply,
        older_than_days=args.older_than,
        protected_versions=protected,
    )

    if args.json:
        _print_json(
            {
                "apply": args.apply,
                "older-than-days": args.older_than,
                "candidates": candidates,
            }
        )
        return 0

    if not candidates:
        print("No cache entries are eligible for pruning.")
        return 0

    action = "Removed" if args.apply else "Would remove"
    for item in candidates:
        print(f"{action}: {item['path']} ({item['reason']})")

    if not args.apply:
        print()
        print("Dry run only. Re-run with --apply to remove these entries.")

    return 0


def _print_doctor_report(
    report: dict[str, object],
    security: list[dict[str, str]],
) -> None:
    validation_errors = int(report["validation-errors"])
    validation_warnings = int(report["validation-warnings"])
    high_security = sum(
        1
        for item in security
        if SEVERITY_ORDER[item["severity"]] >= SEVERITY_ORDER["high"]
    )

    print("EmbrAIon Doctor")
    print()
    print(f"[OK] Framework {report['framework']}")

    if validation_errors:
        print(
            f"[ERROR] Framework validation: {validation_errors} error(s), "
            f"{validation_warnings} warning(s)"
        )
    elif validation_warnings:
        print(
            f"[WARN] Framework validation passed with "
            f"{validation_warnings} warning(s)"
        )
    else:
        print("[OK] Framework validation passed")

    print()
    project = report["project"]

    if project is None:
        print("No EmbrAIon project detected.")
        print("Project diagnostics were skipped.")
    else:
        print(f"[OK] Project: {project}")

        if security:
            if high_security:
                print(
                    f"[ERROR] Security scan: {len(security)} finding(s), "
                    f"{high_security} high-severity"
                )
            else:
                print(f"[WARN] Security scan: {len(security)} finding(s)")
        else:
            print("[OK] Security scan passed")

        print(
            f"[OK] MCP configuration checked "
            f"({report['mcp-servers']} server(s))"
        )
        print(f"[OK] Worktrees checked ({report['worktrees']})")

    print()
    if validation_errors or high_security:
        print("Doctor found issues that need attention.")
    elif validation_warnings or security:
        print("Doctor completed with warnings.")
    else:
        print("Everything looks good.")


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = framework_root()
    project = find_project_root()

    validation = collect_issues(root)
    security: list[dict[str, str]] = []
    mcp_count = 0
    worktree_count = 0

    if project is not None:
        security = collect_findings(project)

        try:
            mcp = save_mcp_inventory(project)
            mcp_count = len(mcp.get("servers", []))
        except Exception:
            mcp_count = 0

        try:
            worktree_count = len(list_worktrees())
        except Exception:
            worktree_count = 0

    report = {
        "framework": __version__,
        "project": str(project) if project is not None else None,
        "project-diagnostics": "enabled" if project is not None else "skipped-no-project",
        "validation-errors": sum(
            1 for item in validation if item["severity"] == "error"
        ),
        "validation-warnings": sum(
            1 for item in validation if item["severity"] == "warning"
        ),
        "security-findings": len(security),
        "mcp-servers": mcp_count,
        "worktrees": worktree_count,
    }

    if args.json:
        _print_json(report)
    else:
        _print_doctor_report(report, security)

    has_high_security = any(
        SEVERITY_ORDER[item["severity"]] >= SEVERITY_ORDER["high"]
        for item in security
    )

    return 1 if report["validation-errors"] or has_high_security else 0


def build_parser() -> argparse.ArgumentParser:
    parser = EmbrAIonArgumentParser(
        prog="embraion",
        description="EmbrAIon AI-First Engineering System CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    help_parser = sub.add_parser(
        "help",
        help="Show the command catalog or detailed command help",
        description="Show the EmbrAIon command catalog or detailed help for one command path.",
    )
    help_parser.add_argument(
        "topic",
        nargs="*",
        help="Optional command path, for example: status or cache prune",
    )
    help_parser.set_defaults(func=_cmd_help, root_parser=parser)

    validate = sub.add_parser(
        "validate",
        help="Validate the canonical EmbrAIon framework",
        description="Validate framework schemas, catalog, localization, and canonical data.",
    )
    validate.add_argument("--root")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=_cmd_validate)

    init = sub.add_parser("init", help="Add EmbrAIon to a project", description="Create a project-local .embraion/project.yaml overlay.")
    init.add_argument("path", nargs="?")
    init.add_argument("--name")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_cmd_init)

    install_parser = sub.add_parser("install", help="Install a host projection", description="Generate and install a Codex, Copilot, Claude Code, or Portable projection.")
    install_parser.add_argument(
        "--host",
        required=True,
        choices=["codex", "copilot", "claude-code", "portable"],
    )
    install_parser.add_argument("--destination", default=".")
    install_parser.add_argument(
        "--component",
        action="append",
        choices=["config", "agents", "skills", "bundle"],
        help=(
            "Install only this projection component; repeat to select multiple. "
            "Omit to install the complete host projection."
        ),
    )
    install_parser.add_argument(
        "--config-mode",
        choices=["replace", "merge"],
        default="replace",
        help=(
            "Codex config ownership mode. 'replace' keeps whole-file projection "
            "semantics; 'merge' manages only EmbrAIon's [agents] keys and "
            "preserves project-owned Codex settings."
        ),
    )
    install_parser.add_argument("--force", action="store_true")
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.add_argument("--prune", action="store_true")
    install_parser.add_argument("--json", action="store_true")
    install_parser.set_defaults(func=_cmd_install)

    projection = sub.add_parser(
        "projection",
        help="Preview host projection lifecycle changes",
        description="Inspect ownership-aware create/update/conflict/obsolete projection state.",
    )
    projection_sub = projection.add_subparsers(
        dest="projection-command",
        required=True,
    )
    projection_diff = projection_sub.add_parser(
        "diff",
        help="Preview projection changes",
        description="Preview generated projection changes without mutating the project.",
    )
    projection_diff.add_argument(
        "--host",
        required=True,
        choices=["codex", "copilot", "claude-code", "portable"],
    )
    projection_diff.add_argument("--destination", default=".")
    projection_diff.add_argument(
        "--component",
        action="append",
        choices=["config", "agents", "skills", "bundle"],
        help=(
            "Diff only this projection component; repeat to select multiple. "
            "Omit to diff the complete host projection."
        ),
    )
    projection_diff.add_argument(
        "--config-mode",
        choices=["replace", "merge"],
        default="replace",
        help="Use the selected Codex config ownership mode while diffing.",
    )
    projection_diff.add_argument("--json", action="store_true")
    projection_diff.set_defaults(func=_cmd_projection_diff)

    projection_verify = projection_sub.add_parser(
        "verify",
        help="Fail unless the installed projection matches canonical output",
        description=(
            "Verify that the selected host projection is fully current: no "
            "create/update/conflict/obsolete drift is allowed."
        ),
    )
    projection_verify.add_argument(
        "--host",
        required=True,
        choices=["codex", "copilot", "claude-code", "portable"],
    )
    projection_verify.add_argument("--destination", default=".")
    projection_verify.add_argument(
        "--component",
        action="append",
        choices=["config", "agents", "skills", "bundle"],
        help=(
            "Verify only this projection component; repeat to select multiple. "
            "Omit to verify the complete host projection."
        ),
    )
    projection_verify.add_argument(
        "--config-mode",
        choices=["replace", "merge"],
        default="replace",
        help="Use the selected Codex config ownership mode while verifying.",
    )
    projection_verify.add_argument("--json", action="store_true")
    projection_verify.set_defaults(func=_cmd_projection_verify)

    validation = sub.add_parser(
        "validation",
        help="Run project validation profiles",
        description=(
            "List or execute project validation profiles from "
            ".embraion/validation.yaml and record structured evidence."
        ),
    )
    validation_sub = validation.add_subparsers(
        dest="validation-command",
        required=True,
    )
    validation_list = validation_sub.add_parser(
        "list",
        help="List configured validation profiles",
        description="List project validation profiles and their commands.",
    )
    validation_list.add_argument("--json", action="store_true")
    validation_list.set_defaults(func=_cmd_validation_list)

    validation_run = validation_sub.add_parser(
        "run",
        help="Execute one validation profile",
        description=(
            "Execute a project validation profile from the project root and "
            "persist redacted structured evidence."
        ),
    )
    validation_run.add_argument("profile")
    validation_run.add_argument("--run-id")
    validation_run.add_argument("--fail-fast", action="store_true")
    validation_run.add_argument("--timeout", type=float)
    validation_run.add_argument(
        "--param",
        action="append",
        metavar="NAME=VALUE",
        help=(
            "Supply one declared runtime parameter; repeat for multiple values. "
            "Unknown or missing required parameters fail closed."
        ),
    )
    validation_run.add_argument("--json", action="store_true")
    validation_run.set_defaults(func=_cmd_validation_run)

    policy = sub.add_parser(
        "policy",
        help="Inspect project policy",
        description="Inspect normalized source, validation, review, and privacy policy.",
    )
    policy_sub = policy.add_subparsers(dest="policy-command", required=True)
    policy_show = policy_sub.add_parser("show", help="Show effective project policy")
    policy_show.add_argument("--json", action="store_true")
    policy_show.set_defaults(func=_cmd_policy_show)

    update = sub.add_parser("update", help="Change the project version pin", description="Update the EmbrAIon version recorded by the current project.")
    update.add_argument("path", nargs="?")
    update.add_argument("--framework-version")
    update.set_defaults(func=_cmd_update)

    sync_parser = sub.add_parser("sync", help="Generate disposable host projections", description="Generate one or all supported host projections into an output directory.")
    sync_parser.add_argument(
        "--host",
        default="all",
        choices=["all", "codex", "copilot", "claude-code", "portable"],
    )
    sync_parser.add_argument("--output")
    sync_parser.add_argument("--force", action="store_true")
    sync_parser.set_defaults(func=_cmd_sync)

    deployment = sub.add_parser(
        "deployment",
        help="Inspect project deployment registry",
        description="Inspect project-owned providers and reusable execution deployments.",
    )
    deployment_sub = deployment.add_subparsers(
        dest="deployment-command",
        required=True,
    )
    deployment_list = deployment_sub.add_parser("list", help="List project deployments")
    deployment_list.add_argument("--json", action="store_true")
    deployment_list.set_defaults(func=_cmd_deployment_list)
    deployment_show = deployment_sub.add_parser("show", help="Show one project deployment")
    deployment_show.add_argument("deployment_id")
    deployment_show.add_argument("--json", action="store_true")
    deployment_show.set_defaults(func=_cmd_deployment_show)

    pricing = sub.add_parser("pricing", help="Inspect or refresh approved official pricing")
    pricing_sub = pricing.add_subparsers(dest="pricing-command", required=True)
    pricing_status_parser = pricing_sub.add_parser("status", help="Inspect the offline validated pricing snapshot")
    pricing_status_parser.add_argument("--json", action="store_true")
    pricing_status_parser.add_argument("--fail-on-stale", action="store_true")
    pricing_status_parser.set_defaults(func=_cmd_pricing_status)
    pricing_refresh_parser = pricing_sub.add_parser("refresh", help="Refresh configured official pricing sources")
    pricing_refresh_parser.add_argument("--source", help="Configured source ID; omit to refresh all sources")
    pricing_refresh_parser.add_argument("--json", action="store_true")
    pricing_refresh_parser.set_defaults(func=_cmd_pricing_refresh)
    pricing_calculate_parser = pricing_sub.add_parser("calculate", help="Calculate cost offline from a JSON stdin request")
    pricing_calculate_parser.set_defaults(func=_cmd_pricing_calculate)

    execute_parser = sub.add_parser("execute", help="Execute a versioned JSON request from stdin")
    execute_parser.set_defaults(func=_cmd_execute)

    route_parser = sub.add_parser("route", help="Resolve host-default or project routing", description="Resolve host-default or project routing for a host, route class, role, and data class.")
    route_parser.add_argument(
        "--host",
        required=True,
        help="Execution host/surface name. Project deployments may use custom hosts.",
    )
    route_parser.add_argument(
        "--route-class",
        required=True,
        choices=[
            "bounded-read",
            "bounded-write",
            "ordinary",
            "substantial",
            "complex",
            "critical",
        ],
    )
    route_parser.add_argument("--role")
    route_parser.add_argument(
        "--data",
        default="PRIVATE",
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    route_parser.set_defaults(func=_cmd_route)

    dispatch = sub.add_parser("dispatch", help="Create a bounded execution plan", description="Create a privacy-aware execution plan with explicit access and owned-path constraints.")
    dispatch.add_argument("--task", required=True)
    dispatch.add_argument("--role", default="worker")
    dispatch.add_argument(
        "--host",
        required=True,
        help="Execution host/surface name. Project deployments may use custom hosts.",
    )
    dispatch.add_argument(
        "--route-class",
        required=True,
        choices=[
            "bounded-read",
            "bounded-write",
            "ordinary",
            "substantial",
            "complex",
            "critical",
        ],
    )
    dispatch.add_argument(
        "--data",
        default="PRIVATE",
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    dispatch.add_argument(
        "--access",
        default="inspect",
        choices=["inspect", "plan", "review", "write", "external-read"],
    )
    dispatch.add_argument("--owned-path", action="append")
    dispatch.set_defaults(func=_cmd_dispatch)

    context = sub.add_parser(
        "context",
        help="Build selective project context",
        description="Select eligible project knowledge with provenance and privacy metadata.",
    )
    context_sub = context.add_subparsers(dest="context-command", required=True)
    context_build = context_sub.add_parser("build", help="Build a context selection record")
    context_build.add_argument("--task", required=True)
    context_build.add_argument("--role", default="lead")
    context_build.add_argument(
        "--data",
        default="PRIVATE",
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    context_build.add_argument("--max-chars", type=int, default=20000)
    context_build.add_argument(
        "--slot",
        action="append",
        choices=PROJECT_CONTRACT_SLOT_NAMES,
        help=(
            "Force-include a configured canonical project contract slot. "
            "Repeat for multiple slots."
        ),
    )
    context_build.set_defaults(func=_cmd_context_build)

    context_slots = context_sub.add_parser(
        "slots",
        help="Show canonical project contract slot bindings",
    )
    context_slots.add_argument("--json", action="store_true")
    context_slots.set_defaults(func=_cmd_context_slots)

    context_show = context_sub.add_parser("show", help="Show a context selection record")
    context_show.add_argument("context_id")
    context_show.set_defaults(func=_cmd_context_show)

    run_parser = sub.add_parser(
        "run",
        help="Record execution evidence",
        description="Create and complete privacy-safe engineering run evidence.",
    )
    run_sub = run_parser.add_subparsers(dest="run-command", required=True)

    run_start = run_sub.add_parser("start", help="Start an execution evidence record")
    run_start.add_argument("--run-id", required=True)
    run_start.add_argument("--task", required=True)
    run_start.add_argument("--role", default="worker")
    run_start.add_argument(
        "--host",
        required=True,
        choices=["codex", "copilot", "claude-code"],
    )
    run_start.add_argument(
        "--route-class",
        required=True,
        choices=[
            "bounded-read",
            "bounded-write",
            "ordinary",
            "substantial",
            "complex",
            "critical",
        ],
    )
    run_start.add_argument(
        "--data",
        default="PRIVATE",
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    run_start.add_argument(
        "--access",
        default="inspect",
        choices=["inspect", "plan", "review", "write", "external-read"],
    )
    run_start.add_argument("--owned-path", action="append")
    run_start.add_argument("--context-id")
    run_start.add_argument("--substantial", action="store_true")
    run_start.set_defaults(func=_cmd_run_start)

    run_complete = run_sub.add_parser("complete", help="Complete an execution evidence record")
    run_complete.add_argument("run_id")
    run_complete.add_argument("--changed-path", action="append")
    run_complete.add_argument("--validation", action="append")
    run_complete.add_argument(
        "--review",
        default="not-required",
        choices=["not-required", "passed", "failed", "skipped"],
    )
    run_complete.add_argument(
        "--outcome",
        default="completed",
        choices=["completed", "blocked", "failed", "cancelled"],
    )
    run_complete.add_argument("--residual-risk", action="append")
    run_complete.set_defaults(func=_cmd_run_complete)

    run_show = run_sub.add_parser("show", help="Show an execution evidence record")
    run_show.add_argument("run_id")
    run_show.set_defaults(func=_cmd_run_show)

    doctor = sub.add_parser("doctor", help="Run diagnostics", description="Check framework health and, inside a project, project security, MCP, and worktree state.")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    status = sub.add_parser("status", help="Show project/runtime status", description="Show launcher version, project pin, resolved runtime, runtime cache, and detected host projections.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=_cmd_status)

    cache = sub.add_parser("cache", help="Inspect or clean runtime cache", description="Inspect and safely clean cached project-pinned EmbrAIon runtimes.")
    cache_sub = cache.add_subparsers(
        dest="cache-command",
        required=True,
    )

    cache_list = cache_sub.add_parser("list", help="List cached runtimes", description="List cached project-pinned EmbrAIon runtimes and their last-use timestamps.")
    cache_list.add_argument("--json", action="store_true")
    cache_list.set_defaults(func=_cmd_cache_list)

    cache_prune = cache_sub.add_parser("prune", help="Find or remove cache entries", description="Dry-run or apply conservative cleanup of invalid, stale, or explicitly old cached runtimes.")
    cache_prune.add_argument("--older-than", type=int)
    cache_prune.add_argument("--apply", action="store_true")
    cache_prune.add_argument("--json", action="store_true")
    cache_prune.set_defaults(func=_cmd_cache_prune)

    session = sub.add_parser("session", help="Manage normalized session state", description="Create, inspect, or update EmbrAIon task/session state.")
    session_sub = session.add_subparsers(
        dest="session-command",
        required=True,
    )

    session_start = session_sub.add_parser("start", help="Start session state", description="Create normalized EmbrAIon session/task state.")
    session_start.add_argument("--session-id", required=True)
    session_start.add_argument("--task", required=True)
    session_start.add_argument("--role", default="lead")
    session_start.add_argument("--host", default="codex")
    session_start.add_argument("--model")
    session_start.add_argument("--effort")
    session_start.add_argument("--access", default="plan")
    session_start.set_defaults(func=_cmd_session_start)

    session_show = session_sub.add_parser("show", help="Show session state", description="Show the current normalized EmbrAIon session/task state.")
    session_show.set_defaults(func=_cmd_session_show)

    session_set = session_sub.add_parser("set", help="Update session state", description="Update selected fields in the current normalized session/task state.")
    session_set.add_argument("--state")
    session_set.add_argument("--validation")
    session_set.add_argument("--review")
    session_set.set_defaults(func=_cmd_session_set)

    enforcement = sub.add_parser(
        "enforcement",
        help="Check or install explicit enforcement gates",
        description=(
            "Evaluate project enforcement policy or explicitly install an "
            "opt-in CI enforcement surface."
        ),
    )
    enforcement_sub = enforcement.add_subparsers(
        dest="enforcement-command",
        required=True,
    )

    enforcement_status_parser = enforcement_sub.add_parser(
        "status",
        help="Show enforcement policy and installed surfaces",
    )
    enforcement_status_parser.add_argument("--json", action="store_true")
    enforcement_status_parser.set_defaults(func=_cmd_enforcement_status)

    enforcement_check_parser = enforcement_sub.add_parser(
        "check",
        help="Evaluate protected paths, validation, and review evidence",
    )
    enforcement_check_parser.add_argument("--base-ref", required=True)
    enforcement_check_parser.add_argument("--run-id")
    enforcement_check_parser.add_argument(
        "--external-review-gate",
        action="store_true",
        help=(
            "Delegate required review enforcement to an explicit external "
            "surface such as the generated GitHub Actions approval gate."
        ),
    )
    enforcement_check_parser.add_argument("--json", action="store_true")
    enforcement_check_parser.set_defaults(func=_cmd_enforcement_check)

    enforcement_install_parser = enforcement_sub.add_parser(
        "install",
        help="Explicitly install an enforcement surface",
    )
    enforcement_install_parser.add_argument(
        "--surface",
        required=True,
        choices=["github-actions"],
    )
    enforcement_install_parser.add_argument(
        "--validation-profile",
        default="affected",
    )
    enforcement_install_parser.add_argument(
        "--require-review",
        action="store_true",
    )
    enforcement_install_parser.add_argument("--force", action="store_true")
    enforcement_install_parser.add_argument("--json", action="store_true")
    enforcement_install_parser.set_defaults(func=_cmd_enforcement_install)

    security = sub.add_parser("security", help="Run security checks", description="Scan files for likely secrets and policy drift.")
    security_sub = security.add_subparsers(
        dest="security-command",
        required=True,
    )

    scan = security_sub.add_parser("scan", help="Scan a path", description="Scan text/configuration files for likely secrets and policy drift.")
    scan.add_argument("--path")
    scan.add_argument(
        "--fail-on",
        choices=list(SEVERITY_ORDER),
        default="high",
    )
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=_cmd_security_scan)

    redact = security_sub.add_parser(
        "redact",
        help="Redact likely credentials from text",
        description="Remove likely credentials before persisting or forwarding diagnostic text.",
    )
    redact.add_argument("--text", required=True)
    redact.set_defaults(func=_cmd_security_redact)

    harness = sub.add_parser(
        "harness",
        help="Audit host enforcement surfaces",
        description="Audit generated agents/skills and report native hook capability metadata.",
    )
    harness_sub = harness.add_subparsers(dest="harness-command", required=True)
    harness_audit = harness_sub.add_parser("audit", help="Audit host projection surfaces")
    harness_audit.add_argument(
        "--host",
        default="all",
        choices=["all", "codex", "copilot", "claude-code"],
    )
    harness_audit.set_defaults(func=_cmd_harness_audit)

    mcp = sub.add_parser("mcp", help="Inspect MCP configuration", description="Create a privacy-safe inventory of project MCP configuration.")
    mcp_sub = mcp.add_subparsers(
        dest="mcp-command",
        required=True,
    )

    inventory = mcp_sub.add_parser("inventory", help="Write MCP inventory", description="Create a privacy-safe inventory of detected MCP servers and configuration.")
    inventory.add_argument("--path")
    inventory.add_argument("--output")
    inventory.set_defaults(func=_cmd_mcp_inventory)

    worktree = sub.add_parser("worktree", help="Manage Git worktrees", description="List, create, safely clean, or salvage Git worktrees.")
    worktree_sub = worktree.add_subparsers(
        dest="worktree-command",
        required=True,
    )

    worktree_list = worktree_sub.add_parser("list", help="List worktrees", description="List Git worktrees for the current repository.")
    worktree_list.set_defaults(func=_cmd_worktree_list)

    worktree_create = worktree_sub.add_parser("create", help="Create a worktree", description="Create an isolated Git worktree for a branch.")
    worktree_create.add_argument("branch")
    worktree_create.add_argument("--path")
    worktree_create.add_argument("--base")
    worktree_create.set_defaults(func=_cmd_worktree_create)

    worktree_gc = worktree_sub.add_parser("gc", help="Find safe cleanup candidates", description="Find safely removable worktrees; use --apply to remove them.")
    worktree_gc.add_argument("--base", default="origin/main")
    worktree_gc.add_argument("--apply", action="store_true")
    worktree_gc.set_defaults(func=_cmd_worktree_gc)

    worktree_salvage = worktree_sub.add_parser("salvage", help="Salvage worktree evidence", description="Copy useful evidence from a worktree before cleanup.")
    worktree_salvage.add_argument("path")
    worktree_salvage.add_argument("--output")
    worktree_salvage.set_defaults(func=_cmd_worktree_salvage)

    learning = sub.add_parser("learning", help="Manage learning evidence", description="Record evidence and move learning candidates through gated lifecycle states.")
    learning_sub = learning.add_subparsers(
        dest="learning-command",
        required=True,
    )

    learning_observe = learning_sub.add_parser("observe", help="Record learning evidence", description="Record repeated evidence that may become a reviewed framework improvement.")
    learning_observe.add_argument("--id", required=True)
    learning_observe.add_argument("--kind", required=True)
    learning_observe.add_argument(
        "--target-type",
        required=True,
        choices=["rule", "skill", "workflow", "routing", "knowledge", "eval"],
    )
    learning_observe.add_argument("--target-id")
    learning_observe.add_argument("--summary", required=True)
    learning_observe.add_argument("--run-id")
    learning_observe.add_argument("--eval-id")
    learning_observe.set_defaults(func=_cmd_learning_observe)

    learning_help = {
        "propose": "Move evidence into proposed state",
        "approve": "Approve a proposed learning candidate",
        "reject": "Reject a learning candidate",
        "promote": "Mark an approved candidate ready for implementation",
    }
    for action in ("propose", "approve", "reject", "promote"):
        item = learning_sub.add_parser(action, help=learning_help[action])
        item.add_argument("id")
        item.set_defaults(
            func=_cmd_learning_transition,
            action=action,
        )

    eval_parser = sub.add_parser("eval", help="Run behavioral evaluations", description="Run behavioral eval cases, build baselines, and compare reports.")
    eval_sub = eval_parser.add_subparsers(
        dest="eval-command",
        required=True,
    )

    eval_run = eval_sub.add_parser("run", help="Run one eval case", description="Evaluate an execution record against a behavioral eval case.")
    eval_run.add_argument("--case", required=True)
    eval_run.add_argument("--record", required=True)
    eval_run.add_argument("--output")
    eval_run.set_defaults(func=_cmd_eval_run)

    eval_baseline = eval_sub.add_parser("baseline", help="Create an eval baseline", description="Create a baseline summary from evaluation reports.")
    eval_baseline.add_argument("--reports", required=True)
    eval_baseline.add_argument("--output", required=True)
    eval_baseline.set_defaults(func=_cmd_eval_baseline)

    eval_compare = eval_sub.add_parser("compare", help="Compare eval reports", description="Compare evaluation reports against a saved baseline.")
    eval_compare.add_argument("--baseline", required=True)
    eval_compare.add_argument("--reports", required=True)
    eval_compare.set_defaults(func=_cmd_eval_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(argv if argv is not None else sys.argv[1:])

    try:
        delegated = resolve_project_runtime(actual_argv, __version__)
        if delegated is not None:
            return delegated
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"ERROR: {_subprocess_error_message(error)}", file=sys.stderr)
        return error.returncode or 2

    parser = build_parser()
    args = parser.parse_args(actual_argv)

    try:
        return int(args.func(args))
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"ERROR: {_subprocess_error_message(error)}", file=sys.stderr)
        return error.returncode or 2


if __name__ == "__main__":
    raise SystemExit(main())
