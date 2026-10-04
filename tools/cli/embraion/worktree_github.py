"""Read-only GitHub evidence for conservative worktree cleanup."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .common import run
from .environment import child_environment


def _gh(*args: str) -> Any:
    result = subprocess.run(["gh", *args], text=True, capture_output=True,
                            env=child_environment(), check=True, timeout=30)
    return json.loads(result.stdout)


def repository_name(repo: Path) -> str:
    url = run(["git", "-C", str(repo), "remote", "get-url", "origin"]).stdout.strip()
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([\w.-]+/[\w.-]+?)(?:\.git)?/?", url)
    if not match:
        raise ValueError("origin is not an unambiguous GitHub repository")
    return match.group(1)


def github_evidence(repo: Path) -> dict[str, Any]:
    """Unknown credentials, rules, pagination, or repository identity fail closed."""
    name = repository_name(repo)
    metadata = _gh("api", f"repos/{name}")
    if (not isinstance(metadata, dict) or not isinstance(metadata.get("full_name"), str)
            or not isinstance(metadata.get("default_branch"), str)
            or metadata["full_name"].lower() != name.lower()):
        raise ValueError("GitHub repository identity mismatch")
    pages = _gh("api", "--paginate", "--slurp", f"repos/{name}/pulls?state=all&per_page=100")
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub pull request response is incomplete")
    pulls = [pull for page in pages for pull in page]
    if any(not isinstance(pull, dict) or not isinstance(pull.get("head"), dict)
           or not isinstance(pull.get("base"), dict) for pull in pulls):
        raise ValueError("malformed GitHub pull request metadata")
    return {"name": name, "default-branch": metadata["default_branch"],
            "pulls": pulls, "metadata": metadata}


def branch_rules(evidence: dict[str, Any], branch: str) -> bool:
    """Return True only after branch rules and protection are both readable."""
    from urllib.parse import quote
    name = evidence["name"]
    branch_data = _gh("api", f"repos/{name}/branches/{quote(branch, safe='')}")
    rules = _gh("api", f"repos/{name}/rules/branches/{quote(branch, safe='')}")
    if (not isinstance(rules, list) or not isinstance(branch_data, dict)
            or not isinstance(branch_data.get("protected"), bool)):
        raise ValueError("unknown branch protection")
    return branch_data["protected"] or bool(rules)


def integration_proof(repo: Path, branch: str, head: str, base: str,
                      evidence: dict[str, Any]) -> tuple[bool, str]:
    """Require one merged exact-head PR and no open PR mentioning the branch."""
    pulls = evidence["pulls"]
    if (not isinstance(pulls, list) or any(not isinstance(pr, dict)
            or not isinstance(pr.get("head"), dict) or not isinstance(pr.get("base"), dict)
            or not isinstance(pr["head"].get("repo"), dict)
            or not isinstance(pr["base"].get("repo"), dict)
            or not isinstance(pr["head"]["repo"].get("full_name"), str)
            or not isinstance(pr["base"]["repo"].get("full_name"), str)
            or not isinstance(pr["head"].get("ref"), str)
            or not isinstance(pr["base"].get("ref"), str) for pr in pulls)):
        return False, "github-pr-metadata-unknown"
    matches = [pr for pr in pulls if pr["head"].get("ref") == branch
               and pr["head"]["repo"].get("full_name", "").lower() == evidence["name"].lower()]
    if any(pr.get("state") == "open" for pr in matches):
        return False, "open-pr"
    if any(pr.get("state") == "open" and pr.get("base", {}).get("ref") == branch for pr in pulls):
        return False, "open-pr-base"
    expected_base = base.removeprefix("origin/")
    merged = [pr for pr in matches if pr.get("merged_at")]
    if len(merged) != 1 or merged[0]["head"].get("sha") != head:
        return False, "merged-pr-proof-missing-or-ambiguous"
    if (merged[0]["base"].get("ref") != expected_base
            or merged[0]["base"]["repo"].get("full_name", "").lower() != evidence["name"].lower()):
        return False, "merged-pr-base-mismatch"
    merge_sha = merged[0].get("merge_commit_sha")
    if not isinstance(merge_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", merge_sha):
        return False, "merge-commit-unknown"
    result = run(["git", "-C", str(repo), "merge-base", "--is-ancestor", merge_sha, base], check=False)
    if result.returncode != 0:
        return False, "merge-commit-not-on-base"
    ancestry = run(["git", "-C", str(repo), "merge-base", "--is-ancestor", head, base], check=False)
    if ancestry.returncode == 0:
        return True, "merged-pr-ancestry"
    if ancestry.returncode != 1:
        return False, "head-ancestry-unknown"
    return True, "merged-pr-squash-evidence"


def remote_head(repo: Path, branch: str) -> str | None:
    result = run(["git", "-C", str(repo), "ls-remote", "--heads", "origin", f"refs/heads/{branch}"])
    lines = result.stdout.splitlines()
    if len(lines) > 1:
        raise ValueError("ambiguous remote branch")
    if not lines:
        return None
    sha, ref = lines[0].split("\t", 1)
    if ref != f"refs/heads/{branch}" or not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
        raise ValueError("unexpected remote branch")
    return sha.lower()


def pr_identity(evidence: dict[str, Any], branch: str, head: str) -> dict[str, Any] | None:
    """Metadata for a proof already checked against fresh provider and Git evidence."""
    for pull in evidence.get("pulls", []):
        if (pull.get("head", {}).get("ref") == branch
                and pull.get("head", {}).get("sha") == head
                and pull.get("merged_at") and isinstance(pull.get("number"), int)):
            return {"repository": evidence["name"], "number": pull["number"],
                    "head-sha": head, "merge-sha": pull["merge_commit_sha"],
                    "target": pull["base"]["ref"]}
    return None
