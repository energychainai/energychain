from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest

from energychain._cloud_client import (
    CLOUD_ORIGIN,
    PRODUCTION_CANARY_ORIGIN,
    STAGING_ORIGIN,
    CloudClient,
    CloudError,
    canonical_json,
)
from energychain.cloud_cli import SystemCredentials, _load_workflow, main

_ACCESS = "ec_cli_" + "T" * 43
_WORKFLOW_ID = "1" * 32
_PROJECT = {
    "organization_id": "energychain-staging",
    "project_id": "battery-staging",
    "environments": ["staging"],
}
_LINK = {
    "organization_id": _PROJECT["organization_id"],
    "project_id": _PROJECT["project_id"],
    "environment": "staging",
    "cloud_origin": STAGING_ORIGIN,
}
_WORKFLOWS = "/v1/projects/battery-staging/workflows"


class _Credentials:
    def __init__(self):
        self.token = None

    def get(self):
        return self.token

    def save(self, token):
        self.token = token

    def remove(self):
        self.token = None


class _FixtureAPI:
    def __init__(self):
        self.requests = []
        self.versions = {}

    def login(self, *, show_code, open_browser):
        assert open_browser is None
        show_code(STAGING_ORIGIN + "/auth/cli/authorize", "BCDF-GHJK")
        return _ACCESS

    def request(self, method, path, *, token, json_data=None):
        assert token == _ACCESS
        self.requests.append((method, path, json_data))
        if path == "/v1/projects":
            return {"projects": [_PROJECT]}
        if path == _WORKFLOWS and method == "POST":
            assert json_data == {"name": "test-workflow"}
            return {"workflow_id": _WORKFLOW_ID}
        if path == f"{_WORKFLOWS}/{_WORKFLOW_ID}/revisions" and method == "POST":
            identity = (json_data["source_digest"], json_data["graph_definition_digest"])
            result = self.versions.setdefault(identity, len(self.versions) + 1)
            return {"revision_id": result, "version": result, "source_digest": identity[0],
                    "graph_definition_digest": identity[1]}
        if path.startswith(_WORKFLOWS + "?"):
            return {"workflows": [{"name": "test-workflow", "workflow_id": _WORKFLOW_ID}]}
        if path == f"{_WORKFLOWS}/{_WORKFLOW_ID}/revisions?limit=1":
            return {"revisions": [{"revision_id": max(self.versions.values())}]}
        if path == "/v1/projects/battery-staging/deployments":
            return json_data
        if path == "/v1/auth/revoke":
            return None
        raise AssertionError(f"Unexpected fixture call {method} {path}")


def test_cli_login_link_push_and_deploy_keep_credentials_out_of_metadata(tmp_path, monkeypatch, capsys):
    client, credentials = _FixtureAPI(), _Credentials()

    def run(*args):
        return main(("--cloud-origin", STAGING_ORIGIN, *args), client=client, credentials=credentials, cwd=tmp_path)

    assert run("projects", "list") == 1
    assert run("auth", "login", "--no-browser") == 0
    assert credentials.token == _ACCESS
    assert "BCDF-GHJK" in capsys.readouterr().out
    assert run("projects", "list") == 0
    assert "battery-staging" in capsys.readouterr().out
    assert run("project", "link", "other-project") == 1
    assert run("project", "link", "battery-staging") == 0
    config = tmp_path / ".energychain" / "project.staging.energychain.app.json"
    assert json.loads(config.read_text()) == _LINK

    graph = {
        "schema_version": "engraph.graph.v1", "id": "test-workflow", "revision": "1", "entry": "first",
        "nodes": [{"id": "first", "label": "First", "kind": "task"}],
        "edges": [{"source": "first", "target": "__end__"}],
    }
    source = ["# workflow version 1\n"]
    monkeypatch.setattr("energychain.cloud_cli._load_workflow", lambda app, cwd: (source[0], graph))
    monkeypatch.setattr("energychain.cloud_cli._open_browser", lambda _: pytest.fail("Opened browser"))

    for _ in range(2):
        assert run("workflow", "push") == 0
    assert len(client.versions) == 1
    assert all("/deployments" not in item[1] for item in client.requests)
    source[0] = "# workflow version 2\n"
    assert run("workflow", "push") == 0
    assert len(client.versions) == 2
    _, pushed_path, pushed = client.requests[-1]
    assert pushed_path.endswith(f"/{_WORKFLOW_ID}/revisions")
    assert pushed["source_digest"] == hashlib.sha256(source[0].encode()).hexdigest()
    assert pushed["graph_definition_digest"] == hashlib.sha256(canonical_json(graph)).hexdigest()
    assert pushed["app_symbol"] == "graph"
    assert run("workflow", "deploy", "--environment", "production") == 1
    assert run("workflow", "deploy", "--environment", "staging") == 0
    assert client.requests[-1] == ("POST", "/v1/projects/battery-staging/deployments", {
        "workflow_id": _WORKFLOW_ID, "revision_id": 2, "environment": "staging",
    })
    assert run("workflow", "deploy", "--name", "test-workflow", "--revision", "1") == 0
    assert client.requests[-1][2]["revision_id"] == 1
    assert run("workflow", "deploy", "--name", "test-workflow") == 0
    assert client.requests[-1][2]["revision_id"] == 2
    for metadata in config.parent.iterdir():
        assert _ACCESS not in metadata.read_text()
        assert source[0] not in metadata.read_text()

    config.write_text(json.dumps(dict(_LINK, project_id="other-project")))
    calls = len(client.requests)
    assert run("workflow", "push") == 1
    assert client.requests[calls:] == [("GET", "/v1/projects", None)]
    config.write_text(json.dumps(dict(_LINK, cloud_origin="https://example.invalid")))
    assert run("workflow", "deploy") == 1
    assert run("auth", "logout") == 0
    assert client.requests[-1][1] == "/v1/auth/revoke"
    assert credentials.token is None
    logs = capsys.readouterr()
    assert _ACCESS not in logs.out + logs.err


@pytest.mark.parametrize("production_origin", [CLOUD_ORIGIN, PRODUCTION_CANARY_ORIGIN])
def test_production_origin_keeps_credentials_links_and_deployment_separate(tmp_path, monkeypatch, production_origin):
    stored = {("EnergyChain Cloud", CLOUD_ORIGIN): _ACCESS}

    class Keyring:
        priority = 1

        def get_password(self, service, account):
            return stored.get((service, account))

        def set_password(self, service, account, token):
            stored[service, account] = token

        def delete_password(self, service, account):
            del stored[service, account]

    staging = _FixtureAPI()
    production_grant = {
        "organization_id": "example-workspace", "project_id": "example-project", "environments": ["production"],
    }
    production_token = "ec_cli_" + "P" * 43
    collection = "/v1/projects/example-project/workflows"

    class Production:
        def __init__(self):
            self.deployments = []

        def login(self, *, show_code, open_browser):
            assert open_browser is None
            show_code(production_origin + "/auth/cli/authorize", "BCDF-GHJK")
            return production_token

        def request(self, method, path, *, token, json_data=None):
            assert token == production_token
            if (method, path) == ("GET", "/v1/projects"):
                return {"projects": [production_grant]}
            if (method, path) == ("POST", collection):
                return {"workflow_id": "2" * 32}
            if (method, path) == ("POST", f"{collection}/{'2' * 32}/revisions"):
                assert json_data["environment"] == "production"
                return {**json_data, "revision_id": 3}
            if (method, path) == ("POST", "/v1/projects/example-project/deployments"):
                self.deployments.append(json_data)
                return json_data
            if (method, path) == ("POST", "/v1/auth/revoke"):
                return None
            pytest.fail(f"Unexpected production request {method} {path}")

    production = Production()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "keyring.backends.Windows", SimpleNamespace(WinVaultKeyring=Keyring))
    monkeypatch.setattr("energychain.cloud_cli.CloudClient",
                        lambda *, origin: {STAGING_ORIGIN: staging, production_origin: production}[origin])
    monkeypatch.setattr("energychain.cloud_cli._load_workflow",
                        lambda app, cwd: ("# workflow\n", {"id": "test-workflow"}))
    monkeypatch.setenv("EC_CLOUD_ORIGIN", STAGING_ORIGIN)

    def run(*args):
        return main(args, cwd=tmp_path)

    assert run("projects", "list") == 1
    assert run("auth", "login", "--no-browser") == 0
    assert run("project", "link", "battery-staging") == 0
    assert run("workflow", "push") == 0
    metadata = tmp_path / ".energychain"
    legacy_link = metadata / "project.json"
    legacy_link.write_text(json.dumps({
        "organization_id": "example-workspace", "project_id": "example-project",
        "environment": "production", "cloud_origin": production_origin,
    }))
    if production_origin == CLOUD_ORIGIN:
        monkeypatch.delenv("EC_CLOUD_ORIGIN")
    else:
        monkeypatch.setenv("EC_CLOUD_ORIGIN", production_origin)
    assert run("projects", "list") == 1
    assert run("auth", "login", "--no-browser") == 0
    assert run("workflow", "push") == 1
    assert run("project", "link", "example-project", "--environment", "staging") == 1
    assert run("project", "link", "example-project") == 0
    assert run("workflow", "push") == 0
    assert run("workflow", "deploy", "--environment", "staging") == 1
    assert run("workflow", "deploy") == 0
    assert production.deployments == [{"workflow_id": "2" * 32, "revision_id": 3, "environment": "production"}]
    assert run("--cloud-origin", STAGING_ORIGIN, "workflow", "deploy") == 0
    assert staging.requests[-1][2]["environment"] == "staging"
    for kind in ("project", "workflow"):
        for origin in (STAGING_ORIGIN, production_origin):
            path = metadata / f"{kind}.{origin.removeprefix('https://')}.json"
            assert json.loads(path.read_text())["cloud_origin"] == origin
    assert run("auth", "logout") == 0
    assert SystemCredentials(production_origin).get() is None
    assert SystemCredentials(STAGING_ORIGIN).get() == _ACCESS
    assert stored[("EnergyChain Cloud", CLOUD_ORIGIN)] == _ACCESS


def test_cli_rejects_the_old_staging_grant_at_the_production_default(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("EC_CLOUD_ORIGIN", raising=False)
    client, credentials = _FixtureAPI(), _Credentials()
    assert main(("auth", "login", "--no-browser"), client=client, credentials=credentials, cwd=tmp_path) == 1
    assert credentials.token is None
    assert client.requests == [("GET", "/v1/projects", None), ("POST", "/v1/auth/revoke", None)]
    assert "outside the selected production site" in capsys.readouterr().err


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"


@pytest.mark.parametrize("origin", [CLOUD_ORIGIN, STAGING_ORIGIN, PRODUCTION_CANARY_ORIGIN])
def test_http_device_login_proves_verifier_and_waits_for_slow_down(origin):
    grant = {
        "device_code": "D" * 43, "user_code": "BCDF-GHJK", "expires_in": 60, "interval": 5,
        "verification_uri": origin + "/auth/cli/authorize",
    }
    forms = []

    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url.startswith(origin + "/v1/auth/")
            assert request.get_method() == "POST"
            assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
            assert not request.get_header("Authorization")
            forms.append(parse_qs(request.data.decode()))
            if len(forms) == 1:
                return _Response(grant)
            if len(forms) in (2, 3):
                kind = "authorization_pending" if len(forms) == 2 else "slow_down"
                body = _Response({"error": kind})
                raise HTTPError(request.full_url, 400, "", body.headers, body)
            return _Response({"token_type": "Bearer", "access_token": _ACCESS,
                              "scope": "cloud:workflow", "expires_in": 60})

    client = CloudClient(origin=origin, opener=Opener())
    waits, prompts, opened = [], [], []
    token = client.login(show_code=lambda url, code: prompts.append((url, code)), open_browser=opened.append,
                         monotonic=lambda: sum(waits), sleep=waits.append)
    assert token == _ACCESS
    assert waits == [5, 5, 10]
    assert prompts == [(grant["verification_uri"], grant["user_code"])]
    assert opened == [grant["verification_uri"]]
    verifier = forms[1]["code_verifier"][0].encode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode()
    assert forms[0] == {"code_challenge": [challenge], "code_challenge_method": ["S256"]}
    assert forms[1] == forms[2] == forms[3]
    assert forms[1]["device_code"] == [grant["device_code"]]


@pytest.mark.parametrize("verification_uri", [
    "https://unrelated.invalid/auth/cli/authorize",
    STAGING_ORIGIN + "/auth/cli/authorize",
    PRODUCTION_CANARY_ORIGIN + "/auth/cli/authorize",
    CLOUD_ORIGIN + "/auth/cli/authorize?code=unexpected",
])
def test_login_never_opens_an_unexpected_verification_url(verification_uri):
    class Opener:
        def open(self, request, *, timeout):
            return _Response({"verification_uri": verification_uri})

    with pytest.raises(CloudError, match="unexpected authorization page"):
        CloudClient(opener=Opener()).login(
            show_code=lambda *_: pytest.fail("Displayed an untrusted page"),
            open_browser=lambda *_: pytest.fail("Opened an untrusted page"),
        )


@pytest.mark.parametrize("origin", [
    "http://cloud.energychain.app",
    "https://cloud.energychain.app/",
    "https://cloud.energychain.app.example.invalid",
    "https://ca-ec-production-identity.unrelated.spaincentral.azurecontainerapps.io",
    "https://cloud.energychain.app@example.invalid",
])
def test_cli_rejects_an_unapproved_cloud_origin_before_using_credentials(origin, monkeypatch):
    monkeypatch.setattr("energychain.cloud_cli.SystemCredentials", lambda *_: pytest.fail("Opened credential store"))
    assert main(["--cloud-origin", origin, "projects", "list"]) == 1


def test_real_engraph_projection_excludes_runtime_capture_and_metadata(tmp_path):
    pytest.importorskip("engraph")
    path = tmp_path / "workflow.py"
    path.write_bytes(b"""from typing import TypedDict
from engraph import END, Graph

class State(TypedDict):
    private_field: str

class Patch(TypedDict):
    complete: bool

class Workspace(TypedDict):
    private_field: str
    complete: bool

def step(state: State, context) -> Patch:
    return {"complete": bool(state["private_field"])}

workflow = Graph("test-workflow", state_type=Workspace, revision="1")
workflow.add_node("measure", step, input_type=State, output_type=Patch)
workflow.set_entry_point("measure").add_edge("measure", END)
graph = workflow.compile(capture_fields={"private_field"})
""")
    source, topology = _load_workflow("workflow.py:graph", tmp_path)
    assert source.encode() == path.read_bytes()
    assert topology["schema_version"] == "engraph.graph.v1"
    assert topology["entry"] == "measure"
    assert topology["nodes"] == [{"id": "measure", "label": "measure", "kind": "task"}]
    assert topology["edges"] == [{"source": "measure", "target": "__end__"}]
    assert b"private_field" not in canonical_json(topology)
