"""The optional EnergyChain Cloud developer command line."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from ._cloud_client import CLOUD_ORIGIN, CloudClient, CloudError, CloudHTTPError, canonical_json

_SLUG = re.compile(r"[a-z][a-z0-9-]{0,62}")
_WORKFLOW_ID = re.compile(r"[0-9a-f]{32}")
_PROJECT_KEYS = {"organization_id", "project_id", "environment", "cloud_origin"}
_SOURCE_LIMIT = 32 * 1024
_GRAPH_LIMIT = 24 * 1024


class SystemCredentials:
    """Store a developer bearer in the built-in OS credential backend."""

    _service = "EnergyChain Cloud"
    _account = CLOUD_ORIGIN

    def __init__(self):
        try:
            if sys.platform == "win32":
                from keyring.backends.Windows import WinVaultKeyring as Backend
            elif sys.platform == "darwin":
                from keyring.backends.macOS import Keyring as Backend
            elif sys.platform.startswith("linux"):
                from keyring.backends.SecretService import Keyring as Backend
            else:
                raise CloudError("EnergyChain Cloud credential storage is unavailable on this operating system.")
            self._backend = Backend()
            if self._backend.priority <= 0:
                raise CloudError("A system credential store is required for Cloud authorization.")
        except CloudError:
            raise
        except ImportError:
            raise CloudError("Install the EnergyChain cloud extra and enable your system credential store.") from None
        except Exception:
            raise CloudError("EnergyChain could not access the system credential store.") from None

    def get(self) -> str | None:
        try:
            return self._backend.get_password(self._service, self._account)
        except Exception:
            raise CloudError("EnergyChain could not read the system credential store.") from None

    def save(self, token: str) -> None:
        try:
            self._backend.set_password(self._service, self._account, token)
        except Exception:
            raise CloudError("EnergyChain could not save the Cloud authorization securely.") from None

    def remove(self) -> None:
        try:
            self._backend.delete_password(self._service, self._account)
        except Exception:
            raise CloudError("EnergyChain could not remove the authorization from the system credential store.") from None


def _valid_id(value, pattern=_SLUG) -> bool:
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _valid_revision(value) -> bool:
    return type(value) is int and 1 <= value <= 2_147_483_647


def _metadata_file(directory: Path, name: str) -> Path:
    base = directory / ".energychain"
    path = base / name
    if base.is_symlink() or path.is_symlink() or base.resolve().parent != directory:
        raise CloudError("Use a regular .energychain directory and metadata files inside the project.")
    return path


def _write_metadata(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".tmp-", delete=False) as file:
            temporary = Path(file.name)
            file.write(canonical_json(data) + b"\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_metadata(path: Path) -> dict:
    try:
        with path.open("rb") as file:
            raw = file.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError, RecursionError):
        pass
    raise CloudError("Could not read EnergyChain project metadata. Run energychain project link or workflow push.")


def _projects(client: CloudClient, token: str) -> list[dict]:
    result = client.request("GET", "/v1/projects", token=token)
    projects = result.get("projects") if result else None
    if not isinstance(projects, list):
        raise CloudError("Cloud returned an unexpected list of projects.")
    for project in projects:
        if (not isinstance(project, dict) or not _valid_id(project.get("organization_id"))
                or not _valid_id(project.get("project_id")) or not isinstance(project.get("environments"), list)
                or not all(_valid_id(environment) for environment in project["environments"])):
            raise CloudError("Cloud returned invalid project metadata.")
    return projects


def _find_project(projects: list[dict], project_id: str, environment: str, organization=None) -> dict:
    matches = [
        project for project in projects
        if project["project_id"] == project_id and environment in project["environments"]
        and (organization is None or project["organization_id"] == organization)
    ]
    if len(matches) != 1:
        raise CloudError("The requested project and environment are unavailable to this identity.")
    return matches[0]


def _read_link(root: Path) -> tuple[Path, dict]:
    for directory in (root, *root.parents):
        path = _metadata_file(directory, "project.json")
        if path.is_file():
            link = _read_metadata(path)
            if (link.keys() == _PROJECT_KEYS and link["cloud_origin"] == CLOUD_ORIGIN
                    and all(_valid_id(link[key]) for key in _PROJECT_KEYS - {"cloud_origin"})):
                return directory, link
            break
    raise CloudError("The current folder has no valid Cloud project link. Run energychain project link.")


def _load_workflow(app: str, cwd: Path) -> tuple[str, dict]:
    path_text, separator, symbol = app.rpartition(":")
    if not separator or not path_text or symbol != "graph" or Path(path_text).suffix != ".py":
        raise CloudError("Choose one trusted Python file with --app workflow.py:graph.")
    try:
        from engraph.cli import load_app
        from engraph.graph import CompiledGraph
    except ImportError:
        raise CloudError("Install the energygraph package to push an EnGraph workflow.") from None

    try:
        with (cwd / path_text).open("rb") as file:
            raw = file.read(_SOURCE_LIMIT + 1)
        if not raw or len(raw) > _SOURCE_LIMIT or b"\x00" in raw:
            raise CloudError("Choose a non-empty UTF-8 workflow file no larger than 32 KiB.")
        source = raw.decode("utf-8")
    except (OSError, UnicodeError):
        raise CloudError("Could not read the trusted UTF-8 workflow file.") from None

    try:
        # A fresh file ensures the topology comes from these exact artifact bytes.
        with TemporaryDirectory(prefix="energychain-app-") as temporary:
            snapshot = Path(temporary) / Path(path_text).name
            snapshot.write_bytes(raw)
            with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
                graph = load_app(str(snapshot) + ":graph")
                if not isinstance(graph, CompiledGraph):
                    raise CloudError("Export one compiled EnGraph workflow as graph.")
                definition = graph.definition()
    except CloudError:
        raise
    except (Exception, SystemExit):
        raise CloudError("The trusted local workflow could not be loaded or compiled. Check it with engraph dev.") from None

    if definition["schema_version"] != "engraph.graph.v1":
        raise CloudError("This EnGraph graph definition is unsupported by Cloud.")
    topology = {key: definition[key] for key in ("schema_version", "id", "revision", "entry")}
    topology["nodes"] = [
        {key: node[key] for key in ("id", "label", "kind")} for node in definition["nodes"]
    ]
    topology["edges"] = [
        {key: edge[key] for key in ("source", "target", "route") if key in edge}
        for edge in definition["edges"]
    ]
    return source, topology


def _workflow_collection(link: dict) -> str:
    return f'/v1/projects/{link["project_id"]}/workflows'


def _push(args, client: CloudClient, token: str, root: Path, link: dict, cwd: Path) -> None:
    source, topology = _load_workflow(args.app, cwd)
    name = args.name if args.name is not None else topology["id"].lower()
    if not _valid_id(name):
        raise CloudError("Set --name to a stable lower-case workflow name with letters, digits or hyphens.")
    graph_bytes = canonical_json(topology)
    if len(graph_bytes) > _GRAPH_LIMIT:
        raise CloudError("The compiled graph topology exceeds the 24 KiB staging limit.")
    source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    graph_digest = hashlib.sha256(graph_bytes).hexdigest()
    collection = _workflow_collection(link)
    registered = client.request("POST", collection, token=token, json_data={"name": name})
    workflow_id = registered.get("workflow_id") if registered else None
    if not _valid_id(workflow_id, _WORKFLOW_ID):
        raise CloudError("Cloud returned an invalid workflow identifier.")
    pushed = client.request("POST", f"{collection}/{workflow_id}/revisions", token=token, json_data={
        "source": source,
        "source_digest": source_digest,
        "graph_definition": topology,
        "graph_definition_digest": graph_digest,
        "app_symbol": "graph",
        "environment": link["environment"],
    })
    revision_id = pushed.get("revision_id") if pushed else None
    if (not _valid_revision(revision_id) or pushed.get("source_digest") != source_digest
            or pushed.get("graph_definition_digest") != graph_digest):
        raise CloudError("Cloud did not confirm this workflow revision and its digests.")
    _write_metadata(_metadata_file(root, "workflow.json"), {
        "name": name, "revision_id": revision_id, "workflow_id": workflow_id, **link,
    })
    print(f"Registered {name} revision {revision_id} in {link['project_id']}.")


def _resolve_workflow(client: CloudClient, token: str, collection: str, name: str) -> str:
    for offset in range(0, 10_001, 100):
        result = client.request("GET", f"{collection}?limit=100&offset={offset}", token=token)
        workflows = result.get("workflows") if result else None
        if not isinstance(workflows, list):
            raise CloudError("Cloud returned an unexpected workflow list.")
        for workflow in workflows:
            if isinstance(workflow, dict) and workflow.get("name") == name:
                workflow_id = workflow.get("workflow_id")
                if not _valid_id(workflow_id, _WORKFLOW_ID):
                    raise CloudError("Cloud returned an invalid workflow identifier.")
                return workflow_id
        if len(workflows) < 100:
            break
    raise CloudError("Could not find the named workflow in the linked project.")


def _deploy(args, client: CloudClient, token: str, root: Path, link: dict) -> None:
    environment = args.environment or link["environment"]
    if environment != link["environment"]:
        raise CloudError("Link the project to the requested environment before deploying.")
    collection = _workflow_collection(link)
    revision_id = args.revision
    if args.name is None:
        selection = _read_metadata(_metadata_file(root, "workflow.json"))
        workflow_id, name = selection.get("workflow_id"), selection.get("name")
        if (any(selection.get(key) != value for key, value in link.items())
                or not _valid_id(workflow_id, _WORKFLOW_ID) or not _valid_id(name)):
            raise CloudError("No workflow is selected for this link. Run workflow push or set --name.")
        if revision_id is None:
            revision_id = selection.get("revision_id")
    else:
        name = args.name
        if not _valid_id(name):
            raise CloudError("Choose a valid lower-case workflow name.")
        workflow_id = _resolve_workflow(client, token, collection, name)
        if revision_id is None:
            result = client.request("GET", f"{collection}/{workflow_id}/revisions?limit=1", token=token)
            revisions = result.get("revisions") if result else None
            if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict):
                revision_id = revisions[0].get("revision_id")
    if not _valid_revision(revision_id):
        raise CloudError("Choose an existing workflow revision or push the workflow first.")
    deployment = {
        "workflow_id": workflow_id, "revision_id": revision_id, "environment": environment,
    }
    activated = client.request("POST", f'/v1/projects/{link["project_id"]}/deployments', token=token,
                               json_data=deployment)
    if not activated or any(activated.get(key) != value for key, value in deployment.items()):
        raise CloudError("Cloud did not confirm the selected deployment.")
    print(f"Deployed {name} revision {revision_id} to {environment}.")


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError):
        pass  # The authorization address was already printed for manual use.


def _login(args, client: CloudClient, credentials: SystemCredentials) -> None:
    def show_code(url, user_code):
        print(f"Open {url} and enter this confirmation code\n{user_code}", flush=True)

    token = client.login(show_code=show_code, open_browser=None if args.no_browser else _open_browser)
    try:
        credentials.save(token)
    except CloudError:
        try:
            client.request("POST", "/v1/auth/revoke", token=token)
        except CloudError:
            pass  # The issued credential remains short-lived.
        raise
    print("Signed in to EnergyChain Cloud.")


def _run(args, client: CloudClient, credentials: SystemCredentials, cwd: Path) -> None:
    if args.command == "auth" and args.action == "login":
        _login(args, client, credentials)
        return
    token = credentials.get()
    if not token:
        raise CloudError("Run energychain auth login to connect to Cloud.")
    if args.command == "auth":
        try:
            client.request("POST", "/v1/auth/revoke", token=token)
        except CloudHTTPError as error:
            if error.status != 401:
                raise
        credentials.remove()
        print("Signed out of EnergyChain Cloud.")
        return
    projects = _projects(client, token)
    if args.command == "projects":
        for project in projects:
            environment_labels = ", ".join(project["environments"])
            print(f'{project["project_id"]}  {project["organization_id"]}  {environment_labels}')
        if not projects:
            print("No Cloud projects are assigned to this identity.")
    elif args.command == "project":
        project = _find_project(projects, args.project, args.environment)
        _write_metadata(_metadata_file(cwd, "project.json"), {
            "organization_id": project["organization_id"], "project_id": project["project_id"],
            "environment": args.environment, "cloud_origin": CLOUD_ORIGIN,
        })
        print(f'Linked this folder to {project["project_id"]} ({args.environment}).')
    else:
        root, link = _read_link(cwd)
        _find_project(projects, link["project_id"], link["environment"], link["organization_id"])
        if args.action == "push":
            _push(args, client, token, root, link, cwd)
        else:
            _deploy(args, client, token, root, link)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="energychain", description="EnergyChain Cloud developer tools")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="authorize the CLI with EnergyChain Cloud")
    auth_actions = auth.add_subparsers(dest="action", required=True)
    login = auth_actions.add_parser("login", help="sign in using your browser")
    login.add_argument("--no-browser", action="store_true", help="open the verification page manually")
    auth_actions.add_parser("logout", help="revoke this CLI session")
    projects = commands.add_parser("projects", help="list authorized Cloud projects")
    projects.add_subparsers(dest="action", required=True).add_parser("list")
    project = commands.add_parser("project", help="link a local folder to Cloud")
    link = project.add_subparsers(dest="action", required=True).add_parser("link")
    link.add_argument("project")
    link.add_argument("--environment", default="staging")
    workflow = commands.add_parser("workflow", help="register and deploy trusted EnGraph workflows")
    workflow_actions = workflow.add_subparsers(dest="action", required=True)
    push = workflow_actions.add_parser("push", help="register a revision from trusted local Python")
    push.add_argument("--app", default="workflow.py:graph", help="trusted_file.py:graph (executes local Python)")
    push.add_argument("--name", help="stable Cloud name (defaults to the graph ID)")
    deploy = workflow_actions.add_parser("deploy", help="activate a previously registered revision")
    deploy.add_argument("--environment")
    deploy.add_argument("--name", help="select a workflow by name (defaults to the last push in this folder)")
    deploy.add_argument("--revision", type=int, help="select an immutable revision")
    return parser


def main(argv=None, *, client=None, credentials=None, cwd=None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run(args, client or CloudClient(), credentials or SystemCredentials(), (cwd or Path.cwd()).resolve())
    except CloudError as error:
        print(error, file=sys.stderr)
        return 1
    except OSError:
        print("Could not access the local EnergyChain project files.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cloud command interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
