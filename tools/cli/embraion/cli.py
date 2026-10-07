from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .capabilities import diagnose_external_capabilities
from .checkpoints import create_checkpoint, resume_checkpoint
from .knowledge_audit import audit_knowledge, snapshot_knowledge
from .decisions import check_decisions, new_decision
from .organization import check_organization
from .skill_evals import run_suite
from .artifacts import read_framework_pin, read_project_artifact_lock, verify_project_artifact
from .bootstrap import _safe_path as bootstrap_safe_path, apply_bootstrap, plan_bootstrap
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
from .pricing import calculate_cost, pricing_status, refresh_pricing, verify_pricing_fixtures
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
from .worktree import (
    create_branch, create_detached_worktree, create_worktree, gc_report, list_worktrees, prepare_task,
    publish_branch, register_worktree, restore_cleanup, salvage_worktree,
)
from .versioning import (
    cache_home,
    find_project_manifest,
    install_project_runtime,
    list_cached_runtimes,
    package_version_for_pin,
    project_runtime_status,
    prune_cache,
    read_project_pin,
    resolve_project_runtime,
    update_check_report,
)


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _subprocess_error_message(error: subprocess.CalledProcessError) -> str:
    for value in (error.stderr, error.stdout):
        if value and value.strip():
            return value.strip()
    # Exception stringification includes the full command, which can contain
    # credentials. Empty-output failures need only the exit code.
    return f"External command failed with exit code {error.returncode}."


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
        "  bootstrap  Plan or apply evidence-bound project contract configuration",
        "  install    Install a host projection (Codex, Copilot, Claude Code, Portable)",
        "  projection Preview ownership-aware projection changes",
        "  policy     Inspect the effective project policy overlay or check its ceilings",
        "  report     Render or validate the project completion report contract",
        "  update     Sync the project pin with a verified release artifact lock",
        "  framework  Install or verify the project-pinned framework artifact",
        "  sync       Generate disposable host projections without installing them",
        "",
        "Health & runtime",
        "  doctor     Run framework and project diagnostics",
        "  status     Show launcher, project pin, active runtime, cache, and host projections",
        "  validate   Validate the framework, schemas, catalog, and localization",
        "  check      Run every check the project configuration selects, for CI",
        "  cache      Inspect or clean cached project-pinned EmbrAIon runtimes",
        "",
        "AI execution",
        "  deployment Inspect the project-owned deployment/provider registry",
        "  route      Resolve host-default or project routing for a task route class",
        "  dispatch   Create a bounded execution plan with access and owned-path constraints",
        "  execute    Process a versioned execution request from stdin",
        "  execution  Build context envelopes, check readiness, or show attempt health",
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
        "  capabilities Diagnose declared external and selected built-in capabilities",
        "  organization Check configured namespace, assembly, and Unity metadata rules",
        "  decisions  Check that architectural changes carry a decision record or waiver",
        "  adr        Create the next numbered architecture decision record",
        "  checkpoint Record or inspect local task continuity anchors",
        "  knowledge  Snapshot or audit declared documentation/source relationships",
        "  claude-native Inspect scoped Claude agents and install guard/observer hooks",
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
    project = find_project_root()
    if project is not None and (project / ".embraion" / "policy.yaml").is_file():
        from .ceilings import check_policy_ceilings
        try:
            findings = check_policy_ceilings(project)
        except RuntimeError as error:
            findings = [{"code": "policy-invalid", "path": ".embraion", "message": str(error)}]
        issues += [
            {"severity": "error", "code": "policy-ceiling", "path": item["path"],
             "message": f"{item['code']}: {item['message']}"}
            for item in findings
        ]
    if project is not None:
        from .project import ignored_projection_outputs

        ignored = ignored_projection_outputs(project) or []
        if ignored:
            shown = ", ".join(ignored[:5]) + (f" (+{len(ignored) - 5} more)" if len(ignored) > 5 else "")
            issues.append({"severity": "warning", "code": "projection-ignored", "path": ignored[0],
                           "message": f"{len(ignored)} projection output(s) are ignored by git, so new "
                                      f"projected files stay untracked: {shown}", "paths": ignored})
    if project is not None and (project / ".embraion" / "project.yaml").is_file():
        from .validation import collect_project_config_issues
        severity = "error" if args.strict else "warning"
        issues += [{**item, "severity": severity} for item in collect_project_config_issues(project, root)]

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


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    root = project_root(Path(args.path))
    if args.bootstrap_command == "plan":
        result = plan_bootstrap(root)
        if args.output:
            output = Path(args.output).resolve()
            state_output = output.is_relative_to(root / ".embraion" / "state")
            if state_output:
                bootstrap_safe_path(root, output.relative_to(root).as_posix())
            if output.is_relative_to(root) and not state_output:
                raise RuntimeError("Write bootstrap plans outside the repository so output cannot invalidate discovery evidence.")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _print_json(result)
    else:
        try:
            plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RuntimeError(f"Cannot read bootstrap plan: {error}") from error
        _print_json(apply_bootstrap(root, plan))
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
    findings = list(plan.get("root-findings", []) or [])
    if "root-findings" in plan:
        label = "error" if plan.get("strict-root") else "warning"
        print(f"root-findings: {len(findings)} ({label})")
        for finding in findings:
            print(f"  {finding['code']} {finding['path']}: {finding['message']}")


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
    if args.strict_root:
        if "root-findings" not in plan:
            raise RuntimeError("--strict-root applies only to the Codex config component in merge mode.")
        plan["strict-root"] = True
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
        derived = len(policy["derived-sources"]["generated"])
        for category, patterns in policy["sources"].items():
            note = f" ({derived} from projection ledgers)" if category == "generated" and derived else ""
            print(f"Sources {category}: {len(patterns)} pattern(s){note}")
        print(f"Routing override hosts: {len(policy['routing']['overrides'])}")
        print(f"Merge mode: {policy['merge']['mode']}")
    return 0


def _cmd_policy_check(args: argparse.Namespace) -> int:
    from .ceilings import check_policy_ceilings, read_ceilings

    project = project_root(Path(args.path) if args.path else None)
    declared = bool(read_ceilings(project))
    findings = check_policy_ceilings(project)
    if args.json:
        _print_json({"ceilings-declared": declared, "valid": not findings, "findings": findings})
    elif not declared:
        print("No policy ceilings declared in .embraion/policy.yaml.")
    elif findings:
        for item in findings:
            print(f"ERROR   {item['code']:28} {item['path']}: {item['message']}")
    else:
        print("PASS: deployments, execution bindings, and routing stay within policy ceilings.")
    return 1 if findings else 0


def _cmd_report_template(args: argparse.Namespace) -> int:
    from .report import read_report_contract, render_report_template

    contract = read_report_contract(path=Path(args.contract) if args.contract else None)
    sys.stdout.write(render_report_template(contract))
    return 0


def _cmd_report_validate(args: argparse.Namespace) -> int:
    from .report import read_report_contract, validate_report

    contract = read_report_contract(path=Path(args.contract) if args.contract else None)
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"Cannot read report: {error}") from error
    issues = validate_report(text, contract, kind=args.kind, pull_request=args.pull_request,
                             missing_pull_request=args.pull_request_not_created)
    if args.json:
        _print_json({"kind": args.kind, "valid": not issues, "issues": issues})
    elif issues:
        for issue in issues:
            location = f"line {issue['line']}" if issue["line"] else "report"
            print(f"ERROR   {issue['code']:28} {location}: {issue['message']}")
    else:
        print(f"PASS: {args.kind} report satisfies the completion report contract.")
    return 1 if issues else 0


def _cmd_update(args: argparse.Namespace) -> int:
    if args.check:
        return _cmd_update_check(args)
    if args.json:
        raise RuntimeError("--json is only supported with 'embraion update --check'.")

    destination = Path(args.path or ".")
    previous, current = update_project(
        destination,
        version=args.framework_version,
    )
    manifest = find_project_manifest(destination)
    if manifest is None:
        raise RuntimeError("Updated project manifest could not be located.")
    artifact_lock = read_project_artifact_lock(manifest, required=True)
    assert artifact_lock is not None

    print(f"Updated framework version: {previous} -> {current}")
    print(
        f"Locked artifact: {artifact_lock.release}/{artifact_lock.asset} "
        f"({artifact_lock.digest})"
    )
    return 0


def _cmd_update_check(args: argparse.Namespace) -> int:
    if args.framework_version:
        raise RuntimeError("--check cannot be combined with --framework-version.")

    report = update_check_report(__version__, start=Path(args.path or "."))
    if args.json:
        _print_json(report)
        return 0

    print(f"Launcher: {report['launcher-version']} ({report['launcher-status']})")
    if report["project"] is None:
        print("Project: none found")
    else:
        locked = "locked" if report["artifact-locked"] else "unlocked"
        print(
            f"Project pin: {report['project-pin']} "
            f"({report['project-status']}, {locked})"
        )
    print(f"Latest release: {report['latest-version']} ({report['latest-digest']})")
    actions = report["actions"]
    if actions:
        print()
        print("Next steps:")
        for action in actions:
            print(f"- {action}")
    elif report["launcher-status"] == "current" and report["project-status"] in {None, "current"}:
        print("Up to date.")
    return 0


def _cmd_framework_install(args: argparse.Namespace) -> int:
    manifest = find_project_manifest(Path(args.path or "."))
    if manifest is None:
        raise RuntimeError("No .embraion/project.yaml found.")

    runtime = install_project_runtime(manifest)
    artifact_lock = read_project_artifact_lock(manifest, required=True)
    assert artifact_lock is not None

    report = {
        "version": artifact_lock.version,
        "release": artifact_lock.release,
        "asset": artifact_lock.asset,
        "digest": artifact_lock.digest,
        "runtime": str(runtime.framework_root),
        "python": str(runtime.python),
    }
    if args.json:
        _print_json(report)
    else:
        print(
            f"Installed verified EmbrAIon {artifact_lock.version} from "
            f"{artifact_lock.release}/{artifact_lock.asset}"
        )
        print(f"Digest: {artifact_lock.digest}")
        print(f"Runtime: {runtime.framework_root}")
    return 0


def _cmd_framework_verify(args: argparse.Namespace) -> int:
    manifest = find_project_manifest(Path(args.path or "."))
    if manifest is None:
        raise RuntimeError("No .embraion/project.yaml found.")

    report = verify_project_artifact(manifest)
    if args.json:
        _print_json(report)
    else:
        print(
            f"Verified EmbrAIon {report['version']} release artifact "
            f"{report['release']}/{report['asset']}"
        )
        print(f"Digest: {report['digest']}")
    return 0


def _cmd_framework_pin(args: argparse.Namespace) -> int:
    manifest = find_project_manifest(Path(args.path or "."))
    if manifest is None:
        raise RuntimeError("No .embraion/project.yaml found.")
    pin = read_framework_pin(manifest)
    if args.json:
        _print_json(pin)
    else:
        # key=value lines suit both people and $GITHUB_OUTPUT.
        print(f"version={pin['version']}")
        if pin["digest"]:
            print(f"digest={pin['digest']}")
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
    if args.audit_authority:
        from .routing_authority import audit_routing_authority
        findings = audit_routing_authority()
        _print_json({"valid": not findings, "findings": findings})
        return 1 if findings else 0
    if args.validate:
        from .runtime import validate_task_routes
        _print_json(validate_task_routes())
        return 0
    if args.task_class:
        from .runtime import resolve_task_route
        if args.host or args.route_class:
            raise RuntimeError("--task-class cannot be combined with --host or --route-class.")
        _print_json(resolve_task_route(args.task_class, data_class=args.data,
                                       role=args.role, access=args.access,
                                       escalation=args.escalation,
                                       justification=args.justification, shape=args.shape))
    else:
        if not args.host or not args.route_class:
            raise RuntimeError("Route requires --host and --route-class, or --task-class.")
        if args.escalation or args.shape:
            raise RuntimeError("Escalation and shape require --task-class.")
        _print_json(route(args.host, args.route_class, args.data or "PRIVATE", role=args.role,
                          access=args.access, justification=args.justification))
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    record = create_dispatch(
        args.task,
        args.role,
        args.host,
        args.route_class,
        args.data,
        args.access,
        args.owned_path or [],
        native_surface=args.native_surface,
        native_agent=args.native_agent,
        task_class=args.task_class,
        justification=args.justification,
        verified_native_fields=args.verified_native_field,
    )
    _print_json(record)
    return 1 if record["state"] == "blocked" else 0


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


def _native_requirements(value: str) -> list[str]:
    from .claude_native import parse_requirements
    try:
        return parse_requirements(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def _cmd_claude_native(args: argparse.Namespace) -> int:
    from .claude_native import observe, observer_status

    if args.native_command == "status":
        status = observer_status()
        if not args.require:
            _print_json(status)
            return 0
        from .claude_native import gate_status
        required = [name for value in args.require for name in value]
        status["gate"] = gate_status(status, list(dict.fromkeys(required)))
        _print_json(status)
        return 1 if status["gate"]["failed"] else 0
    if args.native_command == "install-hooks":
        from .claude_hooks import install_observer_hooks
        _print_json(install_observer_hooks(dry_run=args.dry_run))
        return 0
    if args.native_command == "guard":
        from .claude_guard import guard
        try:
            payload = json.load(sys.stdin)
            decision = guard(payload)
        except (ValueError, TypeError, OSError, RuntimeError):
            decision = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "EmbrAIon cannot verify the native assignment configuration."}}
        if decision:
            _print_json(decision)
        return 0
    # Hook stdin can contain private tool inputs and answers. Neither echo it
    # nor include parser exceptions in stdout/stderr.
    try:
        payload = json.load(sys.stdin)
        observe(payload)
    except (ValueError, TypeError, OSError, RuntimeError):
        # This observer records evidence; it is not an enforcement hook.
        return 0
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


def _cmd_pricing_verify(args: argparse.Namespace) -> int:
    report = verify_pricing_fixtures(Path(args.fixtures))
    if args.json:
        _print_json(report)
    else:
        for item in report["fixtures"]:
            state = "PASS" if item["passed"] else "FAIL (" + ", ".join(item["mismatches"]) + ")"
            print(f"{item['id']}: {state} {item['actual']['state']} {item['actual']['amount'] or '-'} "
                  f"{item['actual']['currency'] or ''}".rstrip())
        print(f"Pricing fixtures: {'passed' if report['passed'] else 'failed'}")
    return 0 if report["passed"] else 1


def _read_execution_request(label: str) -> dict[str, Any]:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise RuntimeError(f"{label} stdin is not valid JSON.") from error
    if not isinstance(request, dict):
        raise RuntimeError(f"{label} stdin must be a JSON object.")
    return request


def _read_task_file(path: str | None) -> str | None:
    if path is None:
        return None
    from .envelope import MAX_TASK_BYTES
    target = Path(path)
    try:
        if not target.is_file() or target.stat().st_size > MAX_TASK_BYTES:
            raise RuntimeError(f"Task file must be a regular file of at most {MAX_TASK_BYTES} bytes.")
        return target.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RuntimeError("Task file cannot be read as UTF-8 text.") from error


def _cmd_execute(args: argparse.Namespace) -> int:
    import warnings

    from .execution import ExecutionEvidenceWarning
    request = _read_execution_request("Execution")
    from .adapters.litellm_execution import LiteLLMLoopbackAdapter
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ExecutionEvidenceWarning)
        result = execute(request, adapters={"litellm-loopback": LiteLLMLoopbackAdapter()}, persist_attempts=True)
    _print_json(result)
    for item in caught:
        if issubclass(item.category, ExecutionEvidenceWarning):
            print(f"WARNING: {item.message}", file=sys.stderr)
        else:
            # Recording catches every warning; re-emit unrelated ones instead of dropping them.
            warnings.showwarning(item.message, item.category, item.filename, item.lineno, item.file, item.line)
    return 0 if result["status"] in {"completed", "handoff-required"} else 1


def _cmd_execution_envelope(args: argparse.Namespace) -> int:
    from .envelope import build_payload, with_payload
    request = _read_execution_request("Execution envelope")
    payload = build_payload(request, paths=args.path or [], task=_read_task_file(args.task_file) or "",
                            commit=args.commit, max_file_bytes=args.max_file_bytes,
                            max_total_bytes=args.max_total_bytes, max_output_tokens=args.max_output_tokens)
    _print_json(payload if args.payload_only else with_payload(request, payload))
    return 0


def _cmd_execution_preflight(args: argparse.Namespace) -> int:
    from .adapters.litellm_execution import LiteLLMLoopbackAdapter
    from .execution import preflight_execution
    request = None if args.deployment else _read_execution_request("Execution preflight")
    report = preflight_execution(request, deployments=args.deployment,
                                 adapters={"litellm-loopback": LiteLLMLoopbackAdapter()},
                                 paths=args.path or [], task=_read_task_file(args.task_file), commit=args.commit)
    if args.json:
        _print_json(report)
    else:
        for item in report["deployments"]:
            state = "ready" if item["ready"] else "NOT READY"
            print(f"{item['deployment']}: {state} (binding {item['binding']}, credential {item['credential']}, "
                  f"request preflight {item['requestPreflight']}, health {item['health']})")
            for reason in item["reasons"]:
                print(f"  - {reason}")
        for item in report["handoff"]:
            print(f"{item['deployment']}: handoff ({item['reason']})")
        for reason in report["reasons"]:
            print(f"- {reason}")
        print(f"Execution preflight: {'ready' if report['ready'] else 'not ready'}")
    return 0 if report["ready"] else 1


def _cmd_execution_health(args: argparse.Namespace) -> int:
    from .ledger import health_report
    report = health_report(project_root())
    if args.json:
        _print_json(report)
        return 0
    print(f"Attempt ledger: {report['records']} records, {report['corruptLines']} unreadable lines")
    for item in report["deployments"]:
        cooldown = f", cooldown until {item['cooldownUntilUtc']}" if item["cooldownUntilUtc"] else ""
        print(f"{item['deployment']}: {item['state']} ({item['attempts']} attempts, "
              f"{item['operationalFailures']} recent operational failures, last {item['lastStatus']}{cooldown})")
    return 0


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
            justification=args.justification,
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
            independent=args.independent_task,
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
                "blocked": "BLOCKED",
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
            if item.get("reason"):
                print(f"  reason: {item['reason']}")
            if item.get("required") is False:
                print("  optional: a failure here is a warning")
            print(f"  log: {item['log-path']}")
            if item["stdout"]:
                print(item["stdout"].rstrip())
            if item["stderr"]:
                print(item["stderr"].rstrip(), file=sys.stderr)
        if record.get("clean-tree"):
            print(f"Clean tree: {record['clean-tree']['status']}")
        for reason in record.get("failure-reasons") or []:
            print(f"Failure: {reason}")
        if record.get("warnings"):
            print(f"Warnings: {record['warnings']} optional command(s) did not pass")
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
    skipped: list[str] = []
    findings = collect_findings(root, all_files=args.all_files, skipped=skipped)

    if args.json:
        _print_json({"findings": findings, **({"machine-path-waived-files": len(skipped)} if args.all_files else {})})
    elif findings:
        for finding in findings:
            print(
                f"{finding['severity'].upper():8} "
                f"{finding['category']:18} "
                f"{finding.get('path', '')}: {finding['message']}"
            )
    else:
        print("PASS: no security findings.")
    if args.all_files and not args.json:
        print(f"Machine-path check waived for {len(skipped)} file(s) under .embraion/policy.yaml "
              "sources.external or sources.generated.")

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
    if args.detach:
        if args.branch or destination is None:
            raise ValueError("--detach requires --path and no branch name.")
        created = create_detached_worktree(destination, base=args.base or "origin/main",
                                            task_id=args.task_id, host=args.host,
                                            independent=args.independent_task)
        print(f"Created {created}")
        return 0
    if not args.branch:
        raise ValueError("A branch name is required unless --detach is selected.")
    if args.branch_only:
        if destination is not None:
            raise ValueError("--branch-only cannot be combined with --path.")
        created_branch = create_branch(args.branch, base=args.base or "origin/main",
                                      task_id=args.task_id, host=args.host,
                                      independent=args.independent_task)
        print(f"Created branch {created_branch}")
        return 0
    created = create_worktree(
        args.branch,
        destination=destination,
        base=args.base or "origin/main",
        task_id=args.task_id,
        host=args.host,
        independent=args.independent_task,
    )
    print(f"Created {created}")
    return 0


def _cmd_worktree_gc(args: argparse.Namespace) -> int:
    report = gc_report(base=args.base, apply=args.apply)
    _print_worktree_report(report, json_output=args.json)
    return int(any(item.get("status") == "failed" for item in report["resources"]))


def _print_worktree_report(report: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _print_json(report)
        return
    for item in report.get("resources", []):
        print(f"{item['status'].upper()} {item.get('branch') or item.get('path') or item.get('kind')} "
              f"({item['reason']})")
    if not report.get("resources"):
        print("No safely removable worktrees found.")
    if report.get("cleanup-id"):
        print(f"Recovery: {report['cleanup-id']}")
    if report.get("dry-run"):
        print("Dry run only. Re-run with --apply to remove eligible resources.")


def _cmd_worktree_prepare(args: argparse.Namespace) -> int:
    report = prepare_task(args.task_id, host=args.host, branch=args.branch,
                          path=Path(args.path).resolve() if args.path else None,
                          base=args.base, writable=not args.read_only,
                          independent=not args.subtask)
    _print_worktree_report(report, json_output=args.json)
    if report.get("receipt-id") and not args.json:
        print(f"Creation receipt: {report['receipt-id']}")
    return 0


def _cmd_worktree_register(args: argparse.Namespace) -> int:
    _print_json(register_worktree(args.task_id, args.host,
                                  path=Path(args.path).resolve() if args.path else None,
                                  receipt_id=args.receipt_id))
    return 0


def _cmd_worktree_publish(args: argparse.Namespace) -> int:
    _print_json(publish_branch(args.task_id, args.branch))
    return 0


def _cmd_worktree_restore(args: argparse.Namespace) -> int:
    report = restore_cleanup(args.cleanup_id)
    _print_json(report)
    return int(any(item.get("status") in {"failed", "preserved"}
                   for item in report.get("resources", [])))


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


def _cmd_capabilities(args: argparse.Namespace) -> int:
    project = project_root(Path(args.path))
    observation = None
    if args.observation:
        path = Path(args.observation)
        if not path.is_file() or path.stat().st_size > 65536:
            raise RuntimeError("Invalid or oversized capability observation file.")
        try:
            observation = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            raise RuntimeError("Invalid capability observation JSON.") from error
    report = diagnose_external_capabilities(framework_root(), project, args.host, observation=observation)
    if args.json:
        _print_json(report)
    else:
        for entry in report["capabilities"]:
            print(f"{entry['id']}: " + ", ".join(f"{stage}={value['status']}" for stage, value in entry["stages"].items()))
        print(f"Observation: {report['observation-status']}; host loading and execution require independent evidence.")
    return 1 if any(item.get("issue") for item in report["capabilities"]) else 0


def _cmd_organization_check(args: argparse.Namespace) -> int:
    report = check_organization(Path(args.path), base_ref=args.base_ref, head_ref=args.head_ref,
                               include_worktree=args.include_worktree,
                               config_path=Path(args.config) if args.config else None,
                               require_config=args.require_config)
    if args.json:
        _print_json(report)
    else:
        print(f"Organization: {report['status']} ({report.get('mode', 'unconfigured')})"
              + (f": {report['reason']}" if report.get("reason") else ""))
        for finding in report.get("findings", []):
            print(f"{finding.get('status', '')}: {finding.get('path', '')}: {finding.get('code', '')}: {finding.get('message', '')}")
    return 0 if report["passed"] else 1


def _cmd_decisions_check(args: argparse.Namespace) -> int:
    report = check_decisions(Path(args.path), base_ref=args.base_ref, head_ref=args.head_ref,
                             waiver=args.waiver, require_config=args.require_config)
    if args.json:
        _print_json(report)
    else:
        print(f"Decisions: {report['status']}" + (f" ({report['outcome']})" if report.get("outcome") else "")
              + (f": {report['reason']}" if report.get("reason") else ""))
        for item in report["triggers"]:
            print(f"trigger: {item['path']}: {item['change']}: {item['trigger']}")
        for path in report["records"]:
            print(f"record: {path}")
        for text in report["waivers"]:
            print(f"waiver: {text}")
    return 0 if report["passed"] else 1


def _cmd_adr_new(args: argparse.Namespace) -> int:
    report = new_decision(args.title, Path(args.path), locales=args.locale, slug=args.slug,
                          status=args.status, day=args.date)
    if args.json:
        _print_json(report)
    else:
        for path in report["created"] + report["paths"]:
            print(path)
        print(f"Record {report['number']} added to {report['index']} with status {report['status']}.")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from .check import planned_checks, run_check

    project = project_root()
    checks = planned_checks(project, base_ref=args.base_ref, fail_on=args.fail_on, all_files=args.all_files)
    parser = build_parser()
    results = []
    with contextlib.chdir(project):
        for check in checks:
            if check["argv"] is None:
                results.append({**check, "exit": None, "passed": None, "output": check["not-run"]})
                continue
            code, output = run_check(parser, check["argv"])
            results.append({**check, "exit": code, "passed": code == 0, "output": output})
    failed = [item["id"] for item in results if item["passed"] is False]
    if args.json:
        _print_json({"passed": not failed, "failed": failed, "checks": results})
    else:
        for item in results:
            if item["passed"] is None:
                print(f"NOT RUN  {item['id']:21} {item['output']}")
                continue
            print(f"{'PASS' if item['passed'] else 'FAIL'}  {item['id']:21} embraion {' '.join(item['argv'])}")
            if not item["passed"]:
                for line in item["output"].rstrip().splitlines():
                    print(f"      {line}")
        print(f"Check: {'passed' if not failed else 'failed (' + ', '.join(failed) + ')'}")
    return 1 if failed else 0


def _cmd_checkpoint(args: argparse.Namespace) -> int:
    project = Path(args.path)
    if args.checkpoint_command == "create":
        report = create_checkpoint(args.id, task_id=args.task_id, phase=args.phase,
            decision_id=args.decision_id, next_action_id=args.next_action_id,
            acceptance_path=args.acceptance_path, remaining_path=args.remaining_path,
            context_id=args.context_id, run_id=args.run_id, project=project)
    else:
        report = resume_checkpoint(args.id, project=project)
    _print_json(report)
    return 1 if report.get("status") in {"stale", "missing"} else 0


def _cmd_knowledge(args: argparse.Namespace) -> int:
    function = snapshot_knowledge if args.knowledge_command == "snapshot" else audit_knowledge
    _print_json(function(project=Path(args.path)))
    return 0


def _cmd_eval_skills_run(args: argparse.Namespace) -> int:
    project = project_root(Path(args.path))
    host_command = None
    if args.host_command is not None:
        try:
            host_command = json.loads(args.host_command)
        except ValueError:
            raise RuntimeError("--host-command must be a JSON array of strings.") from None
    selected = route(args.host, args.route_class, args.data, role="worker", access="workspace-write", project=project)
    if selected.get("options") or selected.get("provider"):
        raise RuntimeError("Live skill eval cannot apply this route's provider or additional options; use an applicable declared route.")
    model, effort = selected.get("model"), selected.get("effort")
    if selected["resolution"] != "host-default":
        if ((args.model is not None and args.model != model)
                or (args.effort is not None and args.effort != effort)):
            raise RuntimeError("Live eval model/effort must match the resolved project route.")
    else:
        model, effort = args.model, args.effort
    try:
        report = run_suite(Path(args.suite), host=args.host, model=model, effort=effort,
                           attempts=args.attempts, output=Path(args.output), timeout_seconds=args.timeout,
                           host_binary=args.host_binary, host_command=host_command, skill_directory=args.skill_dir)
    except (ValueError, OSError) as error:
        raise RuntimeError("Cannot run live skill evaluation: " + redact_text(str(error))) from error
    _print_json(report)
    return 0 if all(row["behavior-passed"] for row in report["runs"] if row["variant"] == "candidate") else 1


def _cmd_eval_experiment(args: argparse.Namespace) -> int:
    try:
        return _eval_experiment(args)
    except (ValueError, OSError, KeyError) as error:
        raise RuntimeError("Cannot evaluate experiment: invalid input or unavailable environment (" + type(error).__name__ + ").") from None


def _eval_experiment(args: argparse.Namespace) -> int:
    from .experiment_evals import capture_snapshot, prepare_baseline, run_experiment, _load
    from .experiment_gates import promotion_eligibility
    if args.experiment_command == "snapshot":
        report = capture_snapshot(Path(args.source), Path(args.output), Path(args.manifest), host=args.host,
                                  regenerate=args.regenerate)
    elif args.experiment_command == "assess":
        from jsonschema import Draft202012Validator, ValidationError
        from .experiment_evals import load_baseline_reports, suite_fixture_digests
        evidence = _load(Path(args.report))
        experiment_path = Path(args.experiment).absolute()
        experiment = _load(experiment_path)
        suite_path = Path(args.suite).absolute() if getattr(args, "suite", None) else None
        suite = _load(suite_path) if suite_path else None
        try:
            Draft202012Validator(_load(framework_root() / "schemas/experiment-report.schema.json")).validate(evidence)
            Draft202012Validator(_load(framework_root() / "schemas/experiment.schema.json")).validate(experiment)
            if suite is not None:
                Draft202012Validator(_load(framework_root() / "schemas/experiment-suite.schema.json")).validate(suite)
        except ValidationError:
            raise ValueError("invalid experiment assessment evidence") from None
        baselines, _ = load_baseline_reports(experiment, experiment_path)
        candidate_suite = ({"suite": suite, "fixture-digests": suite_fixture_digests(suite, suite_path)}
                           if suite is not None else None)
        report = promotion_eligibility(evidence, experiment, baseline_reports=baselines,
                                      candidate_suite=candidate_suite)
    elif args.experiment_command == "prepare":
        pilot = getattr(args, "pilot", "foundation")
        if getattr(args, "target", None) is not None and pilot != "evolution-target":
            raise ValueError("--target requires --pilot evolution-target")
        if getattr(args, "structured_output", False) and pilot != "evolution-target":
            raise ValueError("--structured-output requires --pilot evolution-target")
        if pilot == "evolution-target":
            if getattr(args, "target", None) is None or getattr(args, "role", None) is not None:
                raise ValueError("evolution target requires --target and owns its role/access")
            from .experiment_targets import prepare_target_baseline
            report = prepare_target_baseline(Path(args.source), Path(args.output), target=args.target,
                                             host=args.host, regenerate=args.regenerate,
                                             structured_output=getattr(args, "structured_output", False))
        elif pilot == "finite-role":
            if getattr(args, "role", None) is None:
                raise ValueError("finite role pilot requires --role")
            from .experiment_cases import prepare_role_baseline
            report = prepare_role_baseline(Path(args.source), Path(args.output), role=args.role,
                                           host=args.host, regenerate=args.regenerate)
        else:
            if getattr(args, "role", None) is not None:
                raise ValueError("--role requires --pilot finite-role")
            report = prepare_baseline(Path(args.source), Path(args.output), host=args.host, regenerate=args.regenerate)
    else:
        from jsonschema import Draft202012Validator, ValidationError
        suite = _load(Path(args.suite))
        try:
            Draft202012Validator(_load(framework_root() / "schemas/experiment-suite.schema.json")).validate(suite)
        except ValidationError:
            raise ValueError("invalid experiment suite schema") from None
        execution = suite.get("execution", {"role": "worker", "access": "workspace-write"})
        project = project_root(Path(args.path))
        selected = route(args.host, args.route_class, args.data, role=execution["role"],
                         access=execution["access"], project=project)
        if selected.get("role") not in (None, execution["role"]) or selected.get("access") not in (None, execution["access"]):
            raise ValueError("resolved experiment role or access mismatch")
        # Access remains independent of role/model and is applied by the native
        # adapter. The resolver may omit the validated access from its result.
        selected = {**selected, "role": execution["role"], "access": execution["access"]}
        report = run_experiment(Path(args.suite), host=args.host, model=selected.get("model"),
            effort=selected.get("effort"), route=selected, output=Path(args.output), attempts=args.attempts,
            phase=args.phase, timeout_seconds=args.timeout, binary=args.binary or args.host,
            experiment=Path(args.experiment) if args.experiment else None)
    _print_json(report)
    return 0 if report.get("status") in {None, "pass", "eligible", "prepared"} else 1


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

    for name, result in (report.get("project-controls") or {}).items():
        status = result.get("status", "declared; host loading and execution unverified")
        print(f"[INFO] {name}: {status}")
    for message in report.get("project-control-errors", []):
        print(f"[ERROR] {message}")
    print()
    if validation_errors or high_security or report.get("project-control-errors"):
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
    project_controls: dict[str, object] = {}
    control_errors: list[str] = []

    if project is not None:
        security = collect_findings(project)
        for name, inspect_control in (
            ("capabilities", lambda: diagnose_external_capabilities(root, project, "codex")),
            ("organization", lambda: check_organization(project)),
            ("knowledge", lambda: audit_knowledge(project=project)),
        ):
            try:
                result = inspect_control()
                project_controls[name] = result
                if name == "organization" and not result["passed"]:
                    control_errors.append("organization findings require attention")
                if name == "capabilities" and any(item.get("issue") for item in result["capabilities"]):
                    control_errors.append("capability configuration is unverified or incomplete")
            except (RuntimeError, ValueError, OSError) as error:
                control_errors.append(name + ": " + redact_text(str(error)))
                project_controls[name] = {"status": "error"}

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
        "project-controls": project_controls,
        "project-control-errors": control_errors,
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

    return 1 if report["validation-errors"] or has_high_security or control_errors else 0


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
    validate.add_argument("--strict", action="store_true",
                          help="Report project .embraion configuration warnings as errors")
    validate.set_defaults(func=_cmd_validate)

    init = sub.add_parser("init", help="Add EmbrAIon to a project", description="Create a project-local .embraion/project.yaml overlay.")
    init.add_argument("path", nargs="?")
    init.add_argument("--name")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_cmd_init)

    bootstrap = sub.add_parser("bootstrap", help="Plan or apply conservative project configuration", description="Discover evidence without executing commands. Review the plan and repository sources before applying. Routing and agents are preserved; use the Project Bootstrap skill for semantic inspection and verification.")
    bootstrap_sub = bootstrap.add_subparsers(dest="bootstrap_command", required=True)
    bootstrap_plan = bootstrap_sub.add_parser("plan", help="Inspect an initialized repository without mutation", description="Produce a freshness-bound plan. No dependencies are installed and no repository commands run.")
    bootstrap_plan.add_argument("--path", default=".", help="Initialized project path")
    bootstrap_plan.add_argument("--output", help="Explicit JSON output outside the repository or in .embraion/state")
    bootstrap_plan.set_defaults(func=_cmd_bootstrap)
    bootstrap_apply = bootstrap_sub.add_parser("apply", help="Apply a reviewed, unchanged, fresh plan", description="Fill unbound slots and empty profiles; preserve populated settings. Does not execute validation or configure models.")
    bootstrap_apply.add_argument("--path", default=".", help="Initialized project path")
    bootstrap_apply.add_argument("--plan", required=True, help="Reviewed JSON plan path")
    bootstrap_apply.set_defaults(func=_cmd_bootstrap)

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
        choices=["config", "agents", "skills", "scoped-agents", "hooks", "bundle"],
        help=(
            "Install only this projection component; repeat to select multiple. "
            "Omit for standard components; scoped-agents and hooks require explicit opt-in."
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
        choices=["config", "agents", "skills", "scoped-agents", "hooks", "bundle"],
        help=(
            "Diff only this projection component; repeat to select multiple. "
            "Omit for standard components; scoped-agents and hooks require explicit opt-in."
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
        choices=["config", "agents", "skills", "scoped-agents", "hooks", "bundle"],
        help=(
            "Verify only this projection component; repeat to select multiple. "
            "Omit for standard components; scoped-agents and hooks require explicit opt-in."
        ),
    )
    projection_verify.add_argument(
        "--config-mode",
        choices=["replace", "merge"],
        default="replace",
        help="Use the selected Codex config ownership mode while verifying.",
    )
    projection_verify.add_argument(
        "--strict-root",
        action="store_true",
        help=(
            "In Codex merge mode, fail on root findings: forbidden model/effort "
            "keys, keys outside allowed-root-keys, or root instructions outside "
            "the managed block. Also enabled by policy projection.codex.strict-root."
        ),
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
    validation_run.add_argument("--run-id", help="Attach evidence to an active run and expose it to commands as EMBRAION_RUN_ID")
    validation_run.add_argument("--fail-fast", action="store_true")
    validation_run.add_argument("--timeout", type=float, help="Per-command timeout in seconds; overrides the profile's timeout-seconds")
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
    policy_check = policy_sub.add_parser(
        "check",
        help="Fail when configuration widens policy ceilings",
        description=(
            "Check that deployments, execution bindings, and routing stay within "
            "the ceilings declared in .embraion/policy.yaml. 'embraion validate' "
            "runs the same check inside a project."
        ),
    )
    policy_check.add_argument("--path", help="Project path (default: current directory)")
    policy_check.add_argument("--json", action="store_true")
    policy_check.set_defaults(func=_cmd_policy_check)

    report = sub.add_parser(
        "report",
        help="Render or check the completion report contract",
        description="Render the project completion report template from .embraion/report.yaml or validate a report text against it.",
    )
    report_sub = report.add_subparsers(dest="report-command", required=True)
    report_template = report_sub.add_parser("template", help="Print the report template")
    report_template.add_argument("--contract", help="Contract path (default: .embraion/report.yaml)")
    report_template.set_defaults(func=_cmd_report_template)
    report_validate = report_sub.add_parser(
        "validate",
        help="Validate a final report or an intermediate update",
        description="Check sections, Workers table, Task status, table hygiene, and the pull request link.",
    )
    report_validate.add_argument("file", help="Report file, or '-' for stdin")
    report_validate.add_argument("--kind", choices=["final", "intermediate"], default="final")
    pull_request_state = report_validate.add_mutually_exclusive_group()
    pull_request_state.add_argument("--pull-request", action="store_true",
                                    help="A pull request was created; require its full URL.")
    pull_request_state.add_argument("--pull-request-not-created", action="store_true",
                                    help="A pull request was needed but not created; require a compare URL.")
    report_validate.add_argument("--contract", help="Contract path (default: .embraion/report.yaml)")
    report_validate.add_argument("--json", action="store_true")
    report_validate.set_defaults(func=_cmd_report_validate)

    update = sub.add_parser(
        "update",
        help="Update the project version pin and release artifact lock",
        description=(
            "Atomically synchronize framework.version with the exact published "
            "wheel identity and verified GitHub SHA-256 digest."
        ),
    )
    update.add_argument("path", nargs="?")
    update.add_argument("--framework-version")
    update.add_argument(
        "--check",
        action="store_true",
        help="Report available releases without changing project files",
    )
    update.add_argument("--json", action="store_true", help="With --check, print JSON")
    update.set_defaults(func=_cmd_update)

    framework_parser = sub.add_parser(
        "framework",
        help="Install or verify the pinned framework artifact",
        description=(
            "Use the framework-owned release lock in .embraion/project.yaml "
            "instead of consumer-specific download/checksum logic."
        ),
    )
    framework_sub = framework_parser.add_subparsers(
        dest="framework-command",
        required=True,
    )
    framework_install = framework_sub.add_parser(
        "install",
        help="Install the exact digest-verified pinned release",
        description=(
            "Download the exact locked wheel, verify SHA-256, and install it "
            "into the isolated EmbrAIon runtime cache."
        ),
    )
    framework_install.add_argument("path", nargs="?")
    framework_install.add_argument("--json", action="store_true")
    framework_install.set_defaults(func=_cmd_framework_install)

    framework_verify = framework_sub.add_parser(
        "verify",
        help="Verify the exact pinned release artifact and digest",
        description=(
            "Download the exact locked wheel and fail unless its SHA-256 "
            "matches the project lock."
        ),
    )
    framework_verify.add_argument("path", nargs="?")
    framework_verify.add_argument("--json", action="store_true")
    framework_verify.set_defaults(func=_cmd_framework_verify)

    framework_pin = framework_sub.add_parser(
        "pin",
        help="Print the exact pinned version and artifact lock digest",
        description="Print framework.version and, when locked, the artifact digest; "
        "fail on a missing or inexact pin. Reads only the local manifest.",
    )
    framework_pin.add_argument("path", nargs="?")
    framework_pin.add_argument("--json", action="store_true")
    framework_pin.set_defaults(func=_cmd_framework_pin)

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
    pricing_verify_parser = pricing_sub.add_parser("verify", help="Compare snapshot costs with reviewed usage fixtures")
    pricing_verify_parser.add_argument("--fixtures", required=True, help="YAML file of usage fixtures and expected costs")
    pricing_verify_parser.add_argument("--json", action="store_true")
    pricing_verify_parser.set_defaults(func=_cmd_pricing_verify)

    execute_parser = sub.add_parser("execute", help="Execute a versioned JSON request from stdin")
    execute_parser.set_defaults(func=_cmd_execute)

    execution_parser = sub.add_parser("execution", help="Build context envelopes, check readiness, or show attempt health")
    execution_sub = execution_parser.add_subparsers(dest="execution_command", required=True)
    from .envelope import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_TOTAL_BYTES
    envelope_parser = execution_sub.add_parser(
        "envelope", help="Attach committed-content context envelopes to a stdin request",
        description="Read an execution request from stdin and print it with payload.inputsByDeployment "
                    "for every adapter-bound candidate. Only committed blobs at --commit are read.")
    preflight_parser = execution_sub.add_parser(
        "preflight", help="Check bindings, credential presence, and adapter preflight without a call",
        description="Check adapter-bound candidates of a stdin request, or --deployment bindings, "
                    "without printing credentials or calling a provider.")
    for item in (envelope_parser, preflight_parser):
        item.add_argument("--path", action="append", help="Repository-relative committed file; repeatable")
        item.add_argument("--task-file", required=item is envelope_parser, help="UTF-8 task text file")
        item.add_argument("--commit", default="HEAD", help="Commit to read context from (default HEAD)")
    envelope_parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    envelope_parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    envelope_parser.add_argument("--max-output-tokens", type=int)
    envelope_parser.add_argument("--payload-only", action="store_true", help="Print only the payload object")
    envelope_parser.set_defaults(func=_cmd_execution_envelope)
    preflight_parser.add_argument("--deployment", action="append", help="Check a declared deployment binding instead of a stdin request; repeatable")
    preflight_parser.add_argument("--json", action="store_true")
    preflight_parser.set_defaults(func=_cmd_execution_preflight)
    health_parser = execution_sub.add_parser("health", help="Show per-deployment health from the local attempt ledger")
    health_parser.add_argument("--json", action="store_true")
    health_parser.set_defaults(func=_cmd_execution_health)

    route_parser = sub.add_parser("route", help="Resolve host-default or project routing", description="Resolve host-default or project routing for a host, route class, role, and data class.")
    route_parser.add_argument(
        "--host",
        required=False,
        help="Execution host/surface name. Project deployments may use custom hosts.",
    )
    route_parser.add_argument(
        "--route-class",
        required=False,
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
    route_parser.add_argument("--task-class", help="Resolve a project task class's effective candidate plan.")
    route_parser.add_argument("--access", choices=["inspect", "plan", "review", "write", "external-read", "read-only", "workspace-write"])
    route_parser.add_argument("--escalation", choices=["quality", "critical"])
    route_parser.add_argument("--justification")
    route_parser.add_argument("--shape", help="Optional project work-shape key for candidate-group preference.")
    route_parser.add_argument("--validate", action="store_true", help="Validate task candidates and every direct routing override.")
    route_parser.add_argument("--audit-authority", action="store_true", help="Find duplicate concrete routing facts outside .embraion.")
    route_parser.add_argument(
        "--data",
        default=None,
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    route_parser.set_defaults(func=_cmd_route)

    dispatch = sub.add_parser("dispatch", help="Create a bounded execution plan", description="Create a privacy-aware execution plan with explicit access and owned-path constraints.")
    dispatch.add_argument("--task", required=True)
    dispatch.add_argument("--role")
    dispatch.add_argument(
        "--host",
        required=False,
        help="Execution host/surface name. Project deployments may use custom hosts.",
    )
    dispatch.add_argument(
        "--route-class",
        required=False,
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
        default=None,
        choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
    )
    dispatch.add_argument(
        "--access",
        default="inspect",
        choices=["inspect", "plan", "review", "write", "external-read"],
    )
    dispatch.add_argument("--owned-path", action="append")
    dispatch.add_argument("--task-class", help="Resolve the selected project task-class candidate before preparing dispatch.")
    dispatch.add_argument("--justification", help="Reason required when dispatch selects a critical route.")
    dispatch.add_argument("--native-surface", help="Prepare native arguments/definition overrides; this never executes a host.")
    dispatch.add_argument("--native-agent", help="Native agent definition to prepare, independent of the routing role.")
    dispatch.add_argument("--verified-native-field", action="append", help="Conditional field observed in the installed native schema; retain evidence before invocation.")
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
    run_start.add_argument("--justification", help="Reason required for a critical run; retained in redacted evidence.")
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
    session_scope = session_start.add_mutually_exclusive_group()
    session_scope.add_argument("--independent-task", action="store_true",
                               help="Confirm a new independent task eligible for opted-in housekeeping")
    session_scope.add_argument("--subtask", action="store_true",
                               help="Start a subtask without automatic housekeeping")
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
    scan.add_argument(
        "--all-files",
        action="store_true",
        help="Also check every other tracked or unignored text file up to 2 MiB, such as source code, "
        "for private keys, access tokens and machine paths; skips policy external and generated paths",
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

    native = sub.add_parser("claude-native", help="Inspect startup scoped agents and advisory callback metadata")
    native_sub = native.add_subparsers(dest="native_command", required=True)
    native_status = native_sub.add_parser("status", help="Inspect installed scoped definitions and reported hook evidence")
    native_status.add_argument("--require", action="append", type=_native_requirements, metavar="installed,hooks",
                               help="Exit 1 unless these verifiable facts hold; model and effort cannot gate")
    native_status.set_defaults(func=_cmd_claude_native)
    native_sub.add_parser("observe", help="Read a native hook event from stdin; store metadata only").set_defaults(func=_cmd_claude_native)
    native_sub.add_parser("guard", help="Validate a scoped native call or read boundary from hook stdin").set_defaults(func=_cmd_claude_native)
    native_hooks = native_sub.add_parser("install-hooks", help="Explicitly merge guard and metadata observer hooks into Claude settings")
    native_hooks.add_argument("--dry-run", action="store_true")
    native_hooks.set_defaults(func=_cmd_claude_native)

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
    worktree_create.add_argument("branch", nargs="?")
    worktree_create.add_argument("--path")
    worktree_create.add_argument("--base")
    worktree_create.add_argument("--task-id", help="Bind newly created resources to a task.")
    worktree_create.add_argument("--host", default="codex", choices=["codex", "claude-code", "portable"])
    worktree_create_modes = worktree_create.add_mutually_exclusive_group()
    worktree_create_modes.add_argument("--branch-only", action="store_true", help="Create a managed branch without a checkout.")
    worktree_create_modes.add_argument("--detach", action="store_true", help="Create a managed detached worktree at --path.")
    create_scope = worktree_create.add_mutually_exclusive_group()
    create_scope.add_argument("--independent-task", action="store_true",
                              help="Confirm independent task scope for opted-in housekeeping")
    create_scope.add_argument("--subtask", action="store_true",
                              help="Create a subtask resource without automatic housekeeping")
    worktree_create.set_defaults(func=_cmd_worktree_create)

    worktree_gc = worktree_sub.add_parser("gc", help="Find safe cleanup candidates", description="Find safely removable worktrees; use --apply to remove them.")
    worktree_gc.add_argument("--base", default="origin/main")
    worktree_gc.add_argument("--apply", action="store_true")
    worktree_gc.add_argument("--json", action="store_true")
    worktree_gc.set_defaults(func=_cmd_worktree_gc)

    worktree_prepare = worktree_sub.add_parser("prepare", help="Perform opted-in housekeeping before an independent task")
    worktree_prepare.add_argument("--task-id", required=True)
    worktree_prepare.add_argument("--host", default="codex", choices=["codex", "claude-code", "portable"])
    worktree_prepare.add_argument("--branch", help="Capture nonexistence before creating this branch.")
    worktree_prepare.add_argument("--path", help="Exact expected path of the new worktree.")
    worktree_prepare.add_argument("--base", default="origin/main")
    worktree_prepare.add_argument("--read-only", action="store_true")
    worktree_prepare.add_argument("--subtask", action="store_true")
    worktree_prepare.add_argument("--json", action="store_true")
    worktree_prepare.set_defaults(func=_cmd_worktree_prepare)

    worktree_register = worktree_sub.add_parser("register", help="Register a new resource against its pre-creation receipt")
    worktree_register.add_argument("--task-id", required=True)
    worktree_register.add_argument("--host", required=True, choices=["codex", "claude-code", "portable"])
    worktree_register.add_argument("--receipt-id", required=True)
    worktree_register.add_argument("--path")
    worktree_register.set_defaults(func=_cmd_worktree_register)

    worktree_publish = worktree_sub.add_parser("publish", help="Create or update a remote branch with verified agent provenance")
    worktree_publish.add_argument("--task-id", required=True)
    worktree_publish.add_argument("--branch", required=True)
    worktree_publish.set_defaults(func=_cmd_worktree_publish)

    worktree_restore = worktree_sub.add_parser("restore", help="Restore local resources from a retained cleanup snapshot")
    worktree_restore.add_argument("--cleanup-id", required=True)
    worktree_restore.set_defaults(func=_cmd_worktree_restore)

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

    capabilities_parser = sub.add_parser("capabilities", help="Diagnose optional external capability declarations")
    capabilities_parser.add_argument("--path", default=".")
    capabilities_parser.add_argument("--host", default="codex", choices=["codex", "claude-code", "copilot", "portable"])
    capabilities_parser.add_argument("--observation")
    capabilities_parser.add_argument("--json", action="store_true")
    capabilities_parser.set_defaults(func=_cmd_capabilities)

    organization_parser = sub.add_parser("organization", help="Check project-configured source organization")
    organization_sub = organization_parser.add_subparsers(dest="organization_command", required=True)
    organization_check = organization_sub.add_parser("check")
    organization_check.add_argument("--path", default=".")
    organization_check.add_argument("--base-ref")
    organization_check.add_argument("--head-ref", default="HEAD")
    organization_check.add_argument("--include-worktree", action="store_true")
    organization_check.add_argument("--config")
    organization_check.add_argument("--require-config", action="store_true",
                                    help="Fail instead of skipping when the organization configuration is missing")
    organization_check.add_argument("--json", action="store_true")
    organization_check.set_defaults(func=_cmd_organization_check)

    decisions_parser = sub.add_parser("decisions", help="Check that architectural changes carry a decision record")
    decisions_sub = decisions_parser.add_subparsers(dest="decisions_command", required=True)
    decisions_check = decisions_sub.add_parser("check")
    decisions_check.add_argument("--path", default=".")
    decisions_check.add_argument("--base-ref", required=True)
    decisions_check.add_argument("--head-ref", default="HEAD")
    decisions_check.add_argument("--waiver", help="Reason no decision record is needed, for example from the pull request body")
    decisions_check.add_argument("--require-config", action="store_true",
                                 help="Fail instead of skipping when the decisions configuration is missing")
    decisions_check.add_argument("--json", action="store_true")
    decisions_check.set_defaults(func=_cmd_decisions_check)

    adr_parser = sub.add_parser("adr", help="Scaffold architecture decision records")
    adr_sub = adr_parser.add_subparsers(dest="adr_command", required=True)
    adr_new = adr_sub.add_parser("new")
    adr_new.add_argument("title")
    adr_new.add_argument("--path", default=".")
    adr_new.add_argument("--locale", action="append", default=[], help="Also create a localized copy, for example ru; repeatable")
    adr_new.add_argument("--slug", help="File name words in lowercase kebab-case when the title has no ASCII words")
    adr_new.add_argument("--status", default="Proposed")
    adr_new.add_argument("--date", help="Record date as YYYY-MM-DD (default: today, UTC)")
    adr_new.add_argument("--json", action="store_true")
    adr_new.set_defaults(func=_cmd_adr_new)

    check_parser = sub.add_parser(
        "check",
        help="Run every check the project configuration selects",
        description="Run, from the project root, the configuration, routing, declared projection, Claude native, "
        "organization, and security checks that the project configuration selects, and fail if any fails.",
    )
    check_parser.add_argument("--base-ref", help="Base ref for the organization check, for example origin/main")
    check_parser.add_argument("--fail-on", choices=list(SEVERITY_ORDER),
                              help="Lowest security finding severity that fails the check "
                              "(default: policy check.fail-on, else high)")
    check_parser.add_argument("--all-files", action="store_true", default=None,
                              help="Pass --all-files to the security scan (default: policy check.all-files)")
    check_parser.add_argument("--json", action="store_true")
    check_parser.set_defaults(func=_cmd_check)

    checkpoint_parser = sub.add_parser("checkpoint", help="Record or inspect local task continuity metadata")
    checkpoint_sub = checkpoint_parser.add_subparsers(dest="checkpoint_command", required=True)
    for command in ("create", "resume"):
        command_parser = checkpoint_sub.add_parser(command)
        command_parser.add_argument("id")
        command_parser.add_argument("--path", default=".")
        if command == "create":
            command_parser.add_argument("--task-id", required=True)
            command_parser.add_argument("--phase", required=True, choices=["planning", "implementing", "validating", "reviewing", "blocked", "complete"])
            for name in ("decision-id", "next-action-id", "acceptance-path", "remaining-path", "context-id", "run-id"):
                command_parser.add_argument("--" + name)
        command_parser.set_defaults(func=_cmd_checkpoint)

    knowledge_parser = sub.add_parser("knowledge", help="Explicitly snapshot or read-only audit knowledge source relationships")
    knowledge_sub = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)
    for command in ("snapshot", "audit"):
        command_parser = knowledge_sub.add_parser(command)
        command_parser.add_argument("--path", default=".")
        command_parser.set_defaults(func=_cmd_knowledge)

    eval_parser = sub.add_parser("eval", help="Run behavioral evaluations", description="Run behavioral eval cases, build baselines, and compare reports.")
    eval_sub = eval_parser.add_subparsers(
        dest="eval-command",
        required=True,
    )

    eval_skills = eval_sub.add_parser("skills", help="Evaluate skills in real isolated host sessions")
    eval_skills_sub = eval_skills.add_subparsers(dest="eval_skills_command", required=True)
    eval_skills_run = eval_skills_sub.add_parser("run")
    eval_skills_run.add_argument("--suite", required=True)
    eval_skills_run.add_argument("--host", default="codex", choices=["codex", "claude-code", "portable"])
    eval_skills_run.add_argument("--host-binary", help="native CLI to launch for codex or claude-code (default: codex or claude)")
    eval_skills_run.add_argument("--host-command", help="portable host: JSON array with the agent CLI argument vector; the prompt arrives on stdin")
    eval_skills_run.add_argument("--skill-dir", help="portable host: project-relative directory the agent discovers skills in (default: .agents/skills)")
    eval_skills_run.add_argument("--model")
    eval_skills_run.add_argument("--effort")
    eval_skills_run.add_argument("--attempts", type=int, default=2)
    eval_skills_run.add_argument("--output", required=True)
    eval_skills_run.add_argument("--timeout", type=int, default=180)
    eval_skills_run.add_argument("--path", default=".")
    eval_skills_run.add_argument("--route-class", default="ordinary", choices=["bounded-write", "ordinary", "substantial", "complex"])
    eval_skills_run.add_argument("--data", default="PRIVATE", choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"])
    eval_skills_run.set_defaults(func=_cmd_eval_skills_run)

    eval_experiment = eval_sub.add_parser("experiment", help="Capture and compare immutable full-Core variants")
    experiment_sub = eval_experiment.add_subparsers(dest="experiment_command", required=True)
    prepare = experiment_sub.add_parser("prepare")
    prepare.add_argument("--source", default=".")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--host", default="codex", choices=["codex", "claude-code", "copilot", "portable"])
    prepare.add_argument("--pilot", default="foundation", choices=["foundation", "finite-role", "evolution-target"])
    prepare.add_argument("--role", choices=["lead", "worker", "reviewer", "validator", "researcher", "steward"])
    from .experiment_targets import TARGETS
    prepare.add_argument("--target", choices=sorted(TARGETS))
    prepare.set_defaults(func=_cmd_eval_experiment)
    prepare.add_argument("--regenerate", action="store_true", help="Explicitly refresh only staged baseline projections")
    prepare.add_argument("--structured-output", action="store_true", help="Opt into registered response syntax; requires a new baseline")
    capture = experiment_sub.add_parser("snapshot")
    capture.add_argument("--source", default=".")
    capture.add_argument("--output", required=True)
    capture.add_argument("--manifest", required=True)
    capture.add_argument("--regenerate", action="store_true", help="Explicitly prepare projections from unchanged Core")
    capture.add_argument("--host", default="codex", choices=["codex", "claude-code", "copilot", "portable"])
    capture.set_defaults(func=_cmd_eval_experiment)
    native_run = experiment_sub.add_parser("run")
    native_run.add_argument("--suite", required=True)
    native_run.add_argument("--output", required=True)
    native_run.add_argument("--experiment")
    native_run.add_argument("--host", default="codex", choices=["codex", "claude-code", "copilot", "portable"])
    native_run.add_argument("--binary")
    native_run.add_argument("--path", default=".")
    native_run.add_argument("--route-class", default="substantial", choices=["bounded-write", "ordinary", "substantial", "complex"])
    native_run.add_argument("--data", default="PRIVATE", choices=["PUBLIC", "PRIVATE", "CONFIDENTIAL"])
    native_run.add_argument("--phase", default="exploratory", choices=["baseline", "exploratory", "confirmatory"])
    native_run.add_argument("--attempts", type=int)
    native_run.add_argument("--timeout", type=int, default=180)
    native_run.set_defaults(func=_cmd_eval_experiment)
    assess = experiment_sub.add_parser("assess")
    assess.add_argument("--report", required=True)
    assess.add_argument("--experiment", required=True)
    assess.add_argument("--suite", help="Preserved candidate suite and fixtures; required for promotion eligibility")
    assess.set_defaults(func=_cmd_eval_experiment)

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
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"ERROR: {_subprocess_error_message(error)}", file=sys.stderr)
        return error.returncode or 2


if __name__ == "__main__":
    raise SystemExit(main())
