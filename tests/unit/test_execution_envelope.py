"""Committed-content context envelopes, readiness preflight, and an end-to-end CLI run."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion.adapters.litellm_execution import LiteLLMLoopbackAdapter
from embraion.envelope import EnvelopeRefused, build_payload, with_payload
from embraion.execution import preflight_execution
from embraion.project import init_project


# The fixture host checks the provenance MAC, then echoes only the context paths
# and boundary so the test can prove which envelope reached the adapter.
_FIXTURE = r'''
import hashlib, hmac, json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import TCPServer
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        context = body["input"][0]["content"][0]["text"]
        signed = ("EmbrAIonContext/v1\n" + body["correlationId"] + "\n" + body["workItemId"] + "\n" +
                  os.environ["EMBRAION_UPSTREAM_MODEL"] + "\n" + body["nonce"] + "\n" + context).encode()
        expected = hmac.new(bytes.fromhex(os.environ["EMBRAION_PROVENANCE_KEY"]), signed, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(expected, body["provenanceMac"])
        envelope = json.loads(context)
        answer = envelope["boundary"] + " " + ",".join(item["path"] for item in envelope["context"])
        value = {"status": "completed", "correlationId": body["correlationId"], "callId": "call-1",
                 "adapterVersion": "1.88.6", "observedProvider": "example",
                 "observedModel": "example-model-a-2026-09-01", "outputText": answer,
                 "usage": {"input_tokens": 10, "output_tokens": 2}, "adapterCost": None}
        encoded = json.dumps(value).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(encoded))); self.end_headers()
        self.wfile.write(encoded)
class LoopbackServer(HTTPServer):
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]
server = LoopbackServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
server.handle_request()
server.server_close()
'''

# Built at runtime so the repository scanner never sees credential-shaped literals.
_FAKE_TOKEN = "sk-" + "Q7x" * 14
_FAKE_ASSIGNMENT = "api" + "_key = " + "'" + "z" * 24 + "'"
_FAKE_HOME_PATH = "/" + "home" + "/alice-example/project/notes.txt"
_CREDENTIAL_ENV = "EXAMPLE_ENVELOPE_TEST_KEY"


def _git(root: Path, *arguments: str, data: bytes | None = None) -> str:
    completed = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                                "-c", "commit.gpgsign=false", "-C", str(root), *arguments],
                               input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return completed.stdout.decode("utf-8").strip()


def make_project(directory: Path) -> Path:
    project = directory / "repo"
    project.mkdir()
    init_project(project)
    folder = project / ".embraion"
    policy = yaml.safe_load((folder / "policy.yaml").read_text(encoding="utf-8"))
    policy["sources"]["protected"] = ["vendor/**"]
    (folder / "policy.yaml").write_text(yaml.safe_dump(policy), encoding="utf-8")
    knowledge = yaml.safe_load((folder / "knowledge.yaml").read_text(encoding="utf-8"))
    knowledge["restricted"] = {"path": "docs/restricted.md", "data-class": "CONFIDENTIAL"}
    (folder / "knowledge.yaml").write_text(yaml.safe_dump(knowledge), encoding="utf-8")
    capabilities = {"data-classes": ["PUBLIC", "PRIVATE"], "access-modes": ["read-only"],
                    "roles": ["worker"], "task-classes": ["ordinary"]}
    deployments = {
        "api-first": {"host": "test-host", "model": "example-model-a", "enabled": True,
                      "billing": {"mode": "api"}, "capabilities": capabilities},
        "api-second": {"host": "test-host", "model": "example-model-b", "enabled": True,
                       "billing": {"mode": "api"}, "capabilities": capabilities},
        "native-main": {"host": "native-host", "model": "example-native", "enabled": True,
                        "billing": {"mode": "subscription"}, "capabilities": capabilities},
    }
    (folder / "deployments.yaml").write_text(yaml.safe_dump({"providers": {}, "deployments": deployments}),
                                             encoding="utf-8")
    bindings = {name: {"adapter": "litellm-loopback", "selector": f"example/{deployments[name]['model']}",
                       "expectedProvider": "example", "credentialRef": f"env:{_CREDENTIAL_ENV}",
                       "sourceIds": ["source-a"], "trustLevels": ["verified"],
                       "contextBoundary": "ProjectContext/v1",
                       "expectedResponseModelPattern": r"^example-model-[ab]-[0-9]{4}-[0-9]{2}-[0-9]{2}$"}
                for name in ("api-first", "api-second")}
    (folder / "execution.yaml").write_text(yaml.safe_dump({"schemaVersion": 1, "bindings": bindings}),
                                           encoding="utf-8")
    files = {
        "src/app.py": "def answer() -> int:\n    return 42\n",
        "src/large.txt": "x" * 300,
        "vendor/lib.py": "VALUE = 1\n",
        "docs/restricted.md": "# Restricted\n",
        "src/token.txt": "value " + _FAKE_TOKEN + "\n",
        "src/assignment.py": _FAKE_ASSIGNMENT + "\n",
        "src/machine.md": "See " + _FAKE_HOME_PATH + "\n",
        "src/root-machine.md": "See /root/.ssh/id_rsa\n",
        "src/opt-machine.md": "See /opt/private/config\n",
        "src/unicode-machine.md": "See /opt/私有/config\n",
        "src/symbol-machine.md": "See /opt/📁/config and /opt/[private]/config\n",
        "src/drive-machine.md": "See " + r"D:\Secrets\token.txt" + "\n",
        "src/unc-machine.md": "See " + r"\\server\private\token.txt" + "\n",
        "src/mac-machine.md": "See /Volumes/Private/notes.txt\n",
        "src/safe-links.md": "Read src/app.py and https://example.com/api/v1.\n",
        "assets/model.bin": "version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64 + "\nsize 12\n",
        ".env": "EMPTY=1\n",
        "config/Server.PEM": "placeholder\n",
        "keys/id_ED25519.pub": "placeholder\n",
        "certs/client.p12": "placeholder\n",
        ".npmrc": "registry=https://registry.example.com/\n",
    }
    for relative, text in files.items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    (project / "src" / "blob.dat").write_bytes(b"\x00\x01\x02")
    _git(project, "init", "-q")
    _git(project, "add", "-A")
    # A committed symbolic link without relying on host symlink support.
    blob = _git(project, "hash-object", "-w", "--stdin", data=b"src/app.py")
    _git(project, "update-index", "--add", "--cacheinfo", f"120000,{blob},src/link.py")
    _git(project, "commit", "-q", "-m", "fixture")
    return project


def make_request() -> dict:
    return {"schemaVersion": 1, "runId": "run-1", "workItemId": "work-1", "taskId": "task-1",
            "role": "worker", "routeClass": "ordinary", "host": "test-host", "dataClass": "PRIVATE",
            "sourceIds": ["source-a"], "trustLevel": "verified", "access": "read-only", "ownedPaths": [],
            "contextRef": "context-1", "timeoutSeconds": 10, "maxAttempts": 2,
            "candidates": [{"deployment": "api-first"}, {"deployment": "api-second"},
                           {"deployment": "native-main"}]}


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.project = make_project(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def build(self, paths: list[str], **options: object) -> dict:
        return build_payload(make_request(), paths=paths, task="Explain answer().", project=self.project, **options)

    def test_builds_adapter_accepted_envelope_for_every_bound_candidate(self) -> None:
        payload = self.build(["./src/app.py"], max_output_tokens=256)
        self.assertEqual({"api-first", "api-second"}, set(payload["inputsByDeployment"]))
        self.assertEqual(256, payload["maxOutputTokens"])
        head = _git(self.project, "rev-parse", "HEAD")
        envelope = json.loads(payload["inputsByDeployment"]["api-second"][0]["content"][0]["text"])
        self.assertEqual("ProjectContext/v1", envelope["boundary"])
        self.assertEqual("api-second", envelope["workItem"]["deploymentId"])
        self.assertEqual("example-model-b", envelope["workItem"]["model"])
        self.assertEqual(head, envelope["provenance"]["commit"])
        self.assertEqual([("src/app.py", 35)], [(item["path"], item["bytes"]) for item in envelope["context"]])
        self.assertEqual(64, len(envelope["context"][0]["sha256"]))
        adapter = LiteLLMLoopbackAdapter(self.project)
        request = {**make_request(), "payload": payload,
                   "_adapterCandidateDeployments": ["api-first", "api-second"]}
        deployments = yaml.safe_load((self.project / ".embraion/deployments.yaml").read_text())["deployments"]
        bindings = yaml.safe_load((self.project / ".embraion/execution.yaml").read_text())["bindings"]
        for name in ("api-first", "api-second"):
            adapter.preflight({**request, "selected": {"deployment": name}}, deployments[name], bindings[name])

    def test_reads_committed_blob_not_working_tree(self) -> None:
        target = self.project / "src" / "app.py"
        original = target.read_bytes()
        target.write_bytes(b"uncommitted edit\n")
        try:
            payload = self.build(["src/app.py"])
        finally:
            target.write_bytes(original)
        envelope = json.loads(payload["inputsByDeployment"]["api-first"][0]["content"][0]["text"])
        self.assertEqual(original.decode("utf-8"), envelope["context"][0]["content"])

    def test_refuses_unsafe_paths_and_content(self) -> None:
        cases = {
            "../outside.txt": "outside the repository",
            "src/../vendor/lib.py": "outside the repository",
            "/etc/hosts": "outside the repository",
            "C:/Windows/win.ini": "outside the repository",
            "vendor/lib.py": "protected",
            ".env": "protected",
            ".git/config": "protected",
            "docs/restricted.md": "more sensitive",
            "src/token.txt": "credential",
            "src/assignment.py": "credential",
            "src/machine.md": "machine-local",
            "src/root-machine.md": "machine-local",
            "src/opt-machine.md": "machine-local",
            "src/unicode-machine.md": "machine-local",
            "src/symbol-machine.md": "machine-local",
            "src/drive-machine.md": "machine-local",
            "src/unc-machine.md": "machine-local",
            "src/mac-machine.md": "machine-local",
            "assets/model.bin": "LFS pointer",
            "src/blob.dat": "binary",
            "src/link.py": "symbolic link",
            "src": "not a regular",
            "src/missing.py": "absent",
            "config/Server.PEM": "protected",
            "keys/id_ED25519.pub": "protected",
            "certs/client.p12": "protected",
            ".npmrc": "protected",
            "VENDOR/lib.py": "protected",
            "Vendor/Lib.py": "protected",
            ".ENV": "protected",
            ".Git/config": "protected",
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                with self.assertRaisesRegex(EnvelopeRefused, reason):
                    self.build([path])

    def test_refuses_sensitive_request_strings(self) -> None:
        cases = {"workItemId": "work " + _FAKE_TOKEN, "taskId": "task " + _FAKE_HOME_PATH}
        for field, value in cases.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(EnvelopeRefused, "Work item ID|Task ID"):
                    build_payload({**make_request(), field: value}, paths=[], task="t", project=self.project)

    def test_git_environment_overrides_and_replace_refs_are_ignored(self) -> None:
        overrides = {"GIT_DIR": str(self.project / "missing"), "GIT_OBJECT_DIRECTORY": str(self.project / "missing"),
                     "GIT_INDEX_FILE": str(self.project / "missing"), "GIT_CONFIG_PARAMETERS": "'core.quotepath'='true'"}
        original = _git(self.project, "rev-parse", "HEAD:src/app.py")
        replacement = _git(self.project, "hash-object", "-w", "--stdin", data=b"replaced content\n")
        _git(self.project, "replace", original, replacement)
        try:
            self.assertEqual("replaced content", _git(self.project, "cat-file", "blob", original))
            with patch.dict(os.environ, overrides):
                payload = self.build(["src/app.py"])
        finally:
            _git(self.project, "replace", "-d", original)
        envelope = json.loads(payload["inputsByDeployment"]["api-first"][0]["content"][0]["text"])
        self.assertEqual("def answer() -> int:\n    return 42\n", envelope["context"][0]["content"])

    def test_refuses_oversize_content_and_bad_bounds(self) -> None:
        with self.assertRaisesRegex(EnvelopeRefused, "byte bound"):
            self.build(["src/large.txt"], max_file_bytes=100)
        with self.assertRaisesRegex(EnvelopeRefused, "byte bound"):
            self.build(["src/app.py", "src/large.txt"], max_total_bytes=310)
        with self.assertRaisesRegex(EnvelopeRefused, "between"):
            self.build([], max_file_bytes=0)

    def test_refuses_sensitive_task_text_and_unknown_commit(self) -> None:
        for task in ("Use " + _FAKE_TOKEN, "Read " + _FAKE_HOME_PATH,
                     "Read /root/.ssh/id_rsa", "Read /opt/private/config",
                     "Read /home/张三/秘密.txt", "Read /opt/私有/config",
                     "Read /opt/📁/config", "Read /opt/[private]/config",
                     "Read /opt/<private>/config",
                     "path:/opt/private/config", "Use `/opt/private/config`",
                     "Read " + r"D:\Secrets\token.txt", "Read " + r"\\server\private\token.txt",
                     "Read /Volumes/Private/notes.txt",
                     "Read " + str(self.project.resolve() / "x"), " "):
            with self.subTest(task=task[:12]):
                with self.assertRaises(EnvelopeRefused):
                    build_payload(make_request(), paths=[], task=task, project=self.project)
        for commit in ("--output=x", "no-such-revision"):
            with self.subTest(commit=commit):
                with self.assertRaisesRegex(EnvelopeRefused, "commit|Git"):
                    self.build([], commit=commit)

    def test_allows_relative_paths_web_urls_and_safe_task_text(self) -> None:
        for task in ("Read src/app.py", "Open https://example.com/api/v1",
                     "Open https://example.com/文档/开始",
                     "Read 📁/opt/config", "Read [draft]/opt/config",
                     "Open http://example.com/docs/setup.html", "Compare 1/2 with 3/4"):
            with self.subTest(task=task):
                build_payload(make_request(), paths=[], task=task, project=self.project)
        self.build(["src/safe-links.md"])

    def test_refuses_configured_credential_value_and_ineligible_requests(self) -> None:
        with patch.dict(os.environ, {_CREDENTIAL_ENV: "def answer"}):
            with self.assertRaisesRegex(EnvelopeRefused, "credential"):
                self.build(["src/app.py"])
        request = {**make_request(), "sourceIds": ["unapproved"]}
        with self.assertRaisesRegex(EnvelopeRefused, "ceilings"):
            build_payload(request, paths=[], task="t", project=self.project)
        request = {**make_request(), "candidates": [{"deployment": "native-main"}]}
        with self.assertRaisesRegex(EnvelopeRefused, "no candidate"):
            build_payload(request, paths=[], task="t", project=self.project)

    def test_public_request_cannot_carry_default_private_files(self) -> None:
        request = {**make_request(), "dataClass": "PUBLIC"}
        with self.assertRaisesRegex(EnvelopeRefused, "more sensitive"):
            build_payload(request, paths=["src/app.py"], task="t", project=self.project)

    def test_existing_payload_input_is_never_replaced(self) -> None:
        payload = self.build([])
        with self.assertRaisesRegex(EnvelopeRefused, "already supplies"):
            with_payload({**make_request(), "payload": {"inputsByDeployment": {}}}, payload)
        merged = with_payload({**make_request(), "payload": {"maxOutputTokens": 64}}, payload)
        self.assertEqual(64, merged["payload"]["maxOutputTokens"])


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.project = make_project(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def run_preflight(self, request: dict | None = None, **options: object) -> dict:
        return preflight_execution(request, project=self.project,
                                   adapters={"litellm-loopback": LiteLLMLoopbackAdapter(self.project)}, **options)

    def test_ready_request_reports_presence_only(self) -> None:
        secret_value = "example-" + "v" * 30
        with patch.dict(os.environ, {_CREDENTIAL_ENV: secret_value}):
            report = self.run_preflight(make_request(), paths=["src/app.py"])
        self.assertTrue(report["ready"], report)
        self.assertEqual(["api-first", "api-second"], [item["deployment"] for item in report["deployments"]])
        self.assertEqual({"present"}, {item["credential"] for item in report["deployments"]})
        self.assertEqual({"passed"}, {item["requestPreflight"] for item in report["deployments"]})
        self.assertEqual([{"deployment": "native-main", "host": "native-host", "reason": "host-boundary"}],
                         report["handoff"])
        self.assertNotIn(secret_value, json.dumps(report))

    def test_missing_credential_is_not_ready(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(_CREDENTIAL_ENV, None)
            report = self.run_preflight(make_request())
        self.assertFalse(report["ready"])
        self.assertEqual({"missing"}, {item["credential"] for item in report["deployments"]})

    def test_protected_context_path_is_not_ready(self) -> None:
        with patch.dict(os.environ, {_CREDENTIAL_ENV: "example-" + "v" * 30}):
            report = self.run_preflight(make_request(), paths=["vendor/lib.py"])
        self.assertFalse(report["ready"])
        self.assertIn("protected", " ".join(report["reasons"]))

    def test_request_consistency_failures_are_not_ready(self) -> None:
        cases = [
            ({"candidates": [{"deployment": "api-first"}, {"deployment": "api-first"}]}, "repeats a deployment"),
            ({"routeClass": "critical"}, "requires justification"),
            ({"escalation": "quality"}, "requires a project task class"),
            ({"taskClass": "no-such-task-class"}, ""),
        ]
        with patch.dict(os.environ, {_CREDENTIAL_ENV: "example-" + "v" * 30}):
            for change, reason in cases:
                with self.subTest(change=change):
                    report = self.run_preflight({**make_request(), **change})
                    self.assertFalse(report["ready"])
                    self.assertEqual([], report["deployments"])
                    self.assertTrue(report["reasons"][0].startswith("Request consistency: "))
                    self.assertIn(reason, report["reasons"][0])

    def test_deployment_mode_checks_binding_without_request(self) -> None:
        with patch.dict(os.environ, {_CREDENTIAL_ENV: "example-" + "v" * 30}):
            ready = self.run_preflight(deployments=["api-first"])
            missing = self.run_preflight(deployments=["api-first", "native-main", "unknown"])
        self.assertTrue(ready["ready"], ready)
        self.assertEqual("not-run", ready["deployments"][0]["requestPreflight"])
        self.assertFalse(missing["ready"])
        self.assertEqual(["complete", "unbound", "undeclared"],
                         [item["binding"] for item in missing["deployments"]])

    def test_incomplete_binding_is_not_ready(self) -> None:
        path = self.project / ".embraion" / "execution.yaml"
        original = path.read_text(encoding="utf-8")
        config = yaml.safe_load(original)
        del config["bindings"]["api-first"]["expectedResponseModelPattern"]
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        try:
            with patch.dict(os.environ, {_CREDENTIAL_ENV: "example-" + "v" * 30}):
                report = self.run_preflight(deployments=["api-first"])
        finally:
            path.write_text(original, encoding="utf-8")
        self.assertFalse(report["ready"])
        self.assertEqual("incomplete", report["deployments"][0]["binding"])


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = make_project(Path(directory.name))
        fixture = Path(directory.name) / "host.py"
        fixture.write_text(_FIXTURE, encoding="utf-8")
        self.task = Path(directory.name) / "task.md"
        self.task.write_text("Explain answer().\n", encoding="utf-8")
        environment = patch.dict(os.environ, {"EMBRAION_TEST_MODE": "1",
                                              "EMBRAION_LITELLM_TEST_SERVER_SCRIPT": str(fixture)})
        environment.start()
        self.addCleanup(environment.stop)
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)

    def cli(self, arguments: list[str], stdin: str = "") -> tuple[int, str, str]:
        from embraion.cli import main
        output, errors = io.StringIO(), io.StringIO()
        with (patch("embraion.cli.resolve_project_runtime", return_value=None),
              patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(output), redirect_stderr(errors)):
            code = main(arguments)
        return code, output.getvalue(), errors.getvalue()

    def test_envelope_execute_ledger_and_health_end_to_end(self) -> None:
        request = make_request()
        request["candidates"] = request["candidates"][:2]
        code, built, _ = self.cli(["execution", "envelope", "--path", "src/app.py",
                                   "--task-file", str(self.task)], json.dumps(request))
        self.assertEqual(0, code)
        code, output, errors = self.cli(["execute"], built)
        self.assertEqual(0, code, errors)
        result = json.loads(output)
        self.assertEqual("completed", result["status"], result)
        self.assertEqual("ProjectContext/v1 src/app.py", result["outputText"])
        ledger = (self.project / ".embraion" / "state" / "execution-attempts.jsonl").read_text(encoding="utf-8")
        self.assertEqual(1, len(ledger.splitlines()))
        self.assertNotIn("return 42", ledger)
        self.assertNotIn("Explain answer", ledger)
        self.assertNotIn("ProjectContext/v1 src/app.py", ledger)
        self.assertEqual("api-first", json.loads(ledger)["attempt"]["deployment"])
        code, output, _ = self.cli(["execution", "health", "--json"])
        self.assertEqual(0, code)
        health = json.loads(output)
        self.assertEqual([("api-first", "healthy", 1)],
                         [(item["deployment"], item["state"], item["attempts"]) for item in health["deployments"]])

    def test_envelope_refusal_and_preflight_exit_codes(self) -> None:
        code, _, errors = self.cli(["execution", "envelope", "--path", "../outside.txt",
                                    "--task-file", str(self.task)], json.dumps(make_request()))
        self.assertEqual(2, code)
        self.assertIn("outside the repository", errors)
        os.environ.pop(_CREDENTIAL_ENV, None)
        code, output, _ = self.cli(["execution", "preflight", "--json"], json.dumps(make_request()))
        self.assertEqual(1, code)
        self.assertFalse(json.loads(output)["ready"])
        with patch.dict(os.environ, {_CREDENTIAL_ENV: "example-" + "v" * 30}):
            code, output, _ = self.cli(["execution", "preflight", "--deployment", "api-first"])
        self.assertEqual(0, code, output)
        self.assertIn("api-first: ready", output)


if __name__ == "__main__":
    unittest.main()
