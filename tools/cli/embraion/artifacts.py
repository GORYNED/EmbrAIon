from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

CANONICAL_REPOSITORY = "GORYNED/EmbrAIon"
ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_SOURCE = "github-release"

_STABLE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class FrameworkArtifactLock:
    repository: str
    version: str
    schema: int
    source: str
    release: str
    asset: str
    digest: str

    def artifact_mapping(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source": self.source,
            "release": self.release,
            "asset": self.asset,
            "digest": self.digest,
        }

    def marker_mapping(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "version": self.version,
            **self.artifact_mapping(),
        }


def _expected_asset(version: str) -> str:
    return f"embraion-{version}-py3-none-any.whl"


def _expected_release(version: str) -> str:
    return f"v{version}"


def _validate_stable_version(version: str) -> str:
    normalized = str(version).strip()
    if not _STABLE_VERSION_PATTERN.fullmatch(normalized):
        raise RuntimeError(
            f"Artifact locking requires an exact stable EmbrAIon version, got '{normalized}'."
        )
    return normalized


def _release_api_url(version: str) -> str:
    return (
        "https://api.github.com/repos/"
        f"{CANONICAL_REPOSITORY}/releases/tags/{_expected_release(version)}"
    )


def artifact_download_url(lock: FrameworkArtifactLock) -> str:
    return (
        f"https://github.com/{lock.repository}/releases/download/"
        f"{lock.release}/{lock.asset}"
    )


def _request(url: str, *, accept: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "EmbrAIon-artifact-lock",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def _read_json_url(url: str) -> dict[str, object]:
    try:
        with urlopen(_request(url, accept="application/vnd.github+json"), timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not resolve EmbrAIon release metadata from {url}: {error}") from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"Malformed EmbrAIon release metadata from {url}.")
    return payload


def resolve_release_artifact(version: str) -> dict[str, object]:
    version = _validate_stable_version(version)
    release = _expected_release(version)
    asset_name = _expected_asset(version)
    metadata = _read_json_url(_release_api_url(version))

    if metadata.get("tag_name") != release:
        raise RuntimeError(
            f"Release metadata mismatch: expected tag {release}, got "
            f"{metadata.get('tag_name') or 'missing'}."
        )

    assets = metadata.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError(f"Release {release} has malformed assets metadata.")

    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == asset_name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Release {release} must contain exactly one artifact named {asset_name}; "
            f"found {len(matches)}."
        )

    asset = matches[0]
    digest = str(asset.get("digest") or "").strip().lower()
    if not _SHA256_PATTERN.fullmatch(digest):
        raise RuntimeError(
            f"Release artifact {asset_name} is missing a valid GitHub SHA-256 digest."
        )

    expected_url = (
        f"https://github.com/{CANONICAL_REPOSITORY}/releases/download/"
        f"{release}/{asset_name}"
    )
    actual_url = str(asset.get("browser_download_url") or "").strip()
    if actual_url != expected_url:
        raise RuntimeError(
            f"Release artifact URL mismatch for {asset_name}: expected {expected_url}, "
            f"got {actual_url or 'missing'}."
        )

    return {
        "schema": ARTIFACT_SCHEMA_VERSION,
        "source": ARTIFACT_SOURCE,
        "release": release,
        "asset": asset_name,
        "digest": digest,
    }


def artifact_lock_from_framework(
    framework: object,
    *,
    required: bool,
) -> FrameworkArtifactLock | None:
    if not isinstance(framework, dict):
        raise RuntimeError("Malformed framework configuration in .embraion/project.yaml.")

    repository = str(framework.get("repository") or "").strip()
    if repository != CANONICAL_REPOSITORY:
        raise RuntimeError(
            f"Unsupported EmbrAIon framework repository '{repository}'. "
            f"Artifact locking supports {CANONICAL_REPOSITORY} only."
        )

    version = str(framework.get("version") or "").strip()
    if not version:
        raise RuntimeError("Missing framework.version in .embraion/project.yaml.")

    artifact = framework.get("artifact")
    if artifact is None:
        if required:
            raise RuntimeError(
                "Missing framework.artifact lock in .embraion/project.yaml; "
                "run 'embraion update' with the target release launcher."
            )
        return None
    if not isinstance(artifact, dict):
        raise RuntimeError("Malformed framework.artifact lock: expected a mapping.")

    expected_keys = {"schema", "source", "release", "asset", "digest"}
    if set(artifact) != expected_keys:
        missing = sorted(expected_keys - set(artifact))
        unknown = sorted(set(artifact) - expected_keys)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise RuntimeError(
            "Malformed framework.artifact lock"
            + (": " + "; ".join(details) if details else ".")
        )

    version = _validate_stable_version(version)
    schema = artifact.get("schema")
    source = str(artifact.get("source") or "").strip()
    release = str(artifact.get("release") or "").strip()
    asset = str(artifact.get("asset") or "").strip()
    digest = str(artifact.get("digest") or "").strip().lower()

    if schema != ARTIFACT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Unsupported framework.artifact schema {schema!r}; "
            f"expected {ARTIFACT_SCHEMA_VERSION}."
        )
    if source != ARTIFACT_SOURCE:
        raise RuntimeError(
            f"Unsupported framework.artifact source '{source}'; "
            f"expected {ARTIFACT_SOURCE}."
        )
    if release != _expected_release(version):
        raise RuntimeError(
            f"framework.version/lock mismatch: version {version} requires release "
            f"{_expected_release(version)}, got {release or 'missing'}."
        )
    if asset != _expected_asset(version):
        raise RuntimeError(
            f"framework.version/lock mismatch: version {version} requires artifact "
            f"{_expected_asset(version)}, got {asset or 'missing'}."
        )
    if not _SHA256_PATTERN.fullmatch(digest):
        raise RuntimeError("Malformed framework.artifact digest; expected sha256:<64 lowercase hex>.")

    return FrameworkArtifactLock(
        repository=repository,
        version=version,
        schema=ARTIFACT_SCHEMA_VERSION,
        source=source,
        release=release,
        asset=asset,
        digest=digest,
    )


def read_project_artifact_lock(
    manifest: Path,
    *,
    required: bool = True,
) -> FrameworkArtifactLock | None:
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RuntimeError(f"Could not read EmbrAIon project manifest {manifest}: {error}") from error

    if not isinstance(data, dict):
        raise RuntimeError(f"Malformed EmbrAIon project manifest: {manifest}")
    return artifact_lock_from_framework(data.get("framework"), required=required)


def download_locked_artifact(
    lock: FrameworkArtifactLock,
    destination: Path,
) -> dict[str, str]:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    url = artifact_download_url(lock)
    hasher = hashlib.sha256()

    try:
        with urlopen(_request(url, accept="application/octet-stream"), timeout=60) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not download locked EmbrAIon artifact {lock.release}/{lock.asset}: {error}"
        ) from error

    actual = "sha256:" + hasher.hexdigest()
    if actual != lock.digest:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"Locked EmbrAIon artifact digest mismatch for {lock.asset}: "
            f"expected {lock.digest}, got {actual}."
        )

    temporary.replace(destination)
    return {
        "repository": lock.repository,
        "version": lock.version,
        "release": lock.release,
        "asset": lock.asset,
        "digest": lock.digest,
        "url": url,
        "path": str(destination),
    }


def verify_project_artifact(manifest: Path) -> dict[str, str]:
    lock = read_project_artifact_lock(manifest, required=True)
    assert lock is not None

    with tempfile.TemporaryDirectory(prefix="embraion-verify-") as temporary:
        report = download_locked_artifact(lock, Path(temporary) / lock.asset)

    report.pop("path", None)
    return report
