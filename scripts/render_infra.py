from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_BASE_URL = "https://api.render.com/v1"

BACKEND_SERVICE_NAME = "pystack-backend"
FRONTEND_SERVICE_NAME = "pystack-frontend"
POSTGRES_NAME = "pystack-db"


class InfraError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderService:
    id: str
    name: str
    url: str


class RenderClient:
    def __init__(self, api_key: str, api_base_url: str) -> None:
        require_http_url(api_base_url)
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        url = f"{self.api_base_url}{path}"
        require_http_url(url)
        request = urllib.request.Request(  # noqa: S310 - validated as http(s) above.
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - validated as http(s) above.
                request, timeout=30
            ) as response:
                response_body = response.read()
        except urllib.error.HTTPError as error:
            # Avoid echoing response bodies for requests that might involve
            # secret values. Status and reason are enough to diagnose the call.
            raise InfraError(
                f"Render API {method} {path} failed: {error.code} {error.reason}"
            ) from error
        except urllib.error.URLError as error:
            raise InfraError(f"Render API {method} {path} failed: {error.reason}") from error

        if not response_body:
            return None
        return json.loads(response_body)

    def get_service(self, name: str) -> RenderService:
        query = urllib.parse.urlencode({"name": name, "limit": "10"})
        entries = self.request("GET", f"/services?{query}")
        matches = [
            entry["service"] for entry in entries if entry.get("service", {}).get("name") == name
        ]
        if not matches:
            raise InfraError(
                f"Render service {name!r} was not found. Create/sync the Blueprint in Render first."
            )
        if len(matches) > 1:
            raise InfraError(
                f"Render service name {name!r} is ambiguous: found {len(matches)} matches."
            )

        service = matches[0]
        url = service.get("serviceDetails", {}).get("url")
        if not url:
            raise InfraError(f"Render service {name!r} does not report a public URL yet.")
        return RenderService(id=service["id"], name=service["name"], url=url.rstrip("/"))

    def get_postgres_id(self, name: str) -> str:
        query = urllib.parse.urlencode({"name": name, "limit": "10"})
        entries = self.request("GET", f"/postgres?{query}")
        matches = [
            entry["postgres"] for entry in entries if entry.get("postgres", {}).get("name") == name
        ]
        if not matches:
            raise InfraError(
                f"Render Postgres database {name!r} was not found. "
                "Create/sync the Blueprint in Render first."
            )
        if len(matches) > 1:
            raise InfraError(
                f"Render Postgres name {name!r} is ambiguous: found {len(matches)} matches."
            )
        return matches[0]["id"]

    def get_internal_postgres_url(self, postgres_id: str) -> str:
        info = self.request("GET", f"/postgres/{postgres_id}/connection-info")
        return info["internalConnectionString"]

    def get_env_var(self, service_id: str, key: str) -> str | None:
        escaped_key = urllib.parse.quote(key, safe="")
        try:
            env_var = self.request("GET", f"/services/{service_id}/env-vars/{escaped_key}")
        except InfraError as error:
            if "404" in str(error):
                return None
            raise
        return env_var["value"]

    def put_env_var(self, service_id: str, key: str, value: str) -> None:
        escaped_key = urllib.parse.quote(key, safe="")
        self.request("PUT", f"/services/{service_id}/env-vars/{escaped_key}", {"value": value})

    def create_deploy(self, service_id: str) -> str:
        deploy = self.request(
            "POST", f"/services/{service_id}/deploys", {"clearCache": "do_not_clear"}
        )
        return deploy["id"]

    def get_deploy_status(self, service_id: str, deploy_id: str) -> str:
        deploy = self.request("GET", f"/services/{service_id}/deploys/{deploy_id}")
        return deploy["status"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Render Blueprint, reconcile post-Blueprint environment "
            "variables, deploy changed services, and run non-mutating health checks."
        )
    )
    parser.add_argument(
        "--blueprint", default="infra/render.yaml", help="Blueprint file to validate."
    )
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument(
        "--timeout", type=int, default=900, help="Seconds to wait for deploys/health."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show intended changes without writing."
    )
    parser.add_argument(
        "--skip-deploy", action="store_true", help="Update env vars but do not deploy."
    )
    parser.add_argument("--skip-health", action="store_true", help="Skip remote health checks.")
    return parser.parse_args()


def validate_blueprint(blueprint_path: Path) -> None:
    command = [
        "render",
        "blueprints",
        "validate",
        str(blueprint_path),
        "--output",
        "json",
        "--confirm",
    ]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell.
            command, check=False, text=True, capture_output=True
        )
    except FileNotFoundError as error:
        raise InfraError("Missing Render CLI. Install it and run `render login` first.") from error

    if result.returncode != 0:
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise InfraError(f"Blueprint validation failed:\n{output}")

    payload = json.loads(result.stdout)
    if not payload.get("valid"):
        raise InfraError(f"Blueprint validation failed:\n{result.stdout.strip()}")
    print(f"Validated {blueprint_path}")


def render_api_key() -> str:
    if api_key := os.environ.get("RENDER_API_KEY"):
        return api_key

    config_path = Path(
        os.environ.get("RENDER_CLI_CONFIG_PATH", Path.home() / ".render" / "cli.yaml")
    )
    if not config_path.exists():
        raise InfraError("Set RENDER_API_KEY or run `render login` before using Render commands.")

    in_api_section = False
    for line in config_path.read_text().splitlines():
        if line.startswith("api:"):
            in_api_section = True
            continue
        if line and not line.startswith((" ", "\t")):
            in_api_section = False
        if in_api_section and line.strip().startswith("key:"):
            _, value = line.split(":", 1)
            api_key = value.strip()
            if api_key:
                return api_key

    raise InfraError("Could not read the Render API key from the Render CLI config.")


def reconcile_env_vars(
    client: RenderClient,
    service: RenderService,
    desired: dict[str, str],
    dry_run: bool,
) -> bool:
    changed = False
    for key, desired_value in desired.items():
        current_value = client.get_env_var(service.id, key)
        if current_value == desired_value:
            print(f"{service.name}: {key} is up to date")
            continue

        changed = True
        if dry_run:
            action = "create" if current_value is None else "update"
            print(f"{service.name}: would {action} {key}")
            continue

        client.put_env_var(service.id, key, desired_value)
        action = "created" if current_value is None else "updated"
        print(f"{service.name}: {action} {key}")

    return changed


def verify_database_url(client: RenderClient, backend: RenderService) -> None:
    postgres_id = client.get_postgres_id(POSTGRES_NAME)
    expected = client.get_internal_postgres_url(postgres_id)
    actual = client.get_env_var(backend.id, "PYSTACK_DATABASE_URL")
    if actual is None:
        raise InfraError(
            "pystack-backend is missing PYSTACK_DATABASE_URL. "
            "Sync the Blueprint so Render applies the fromDatabase value."
        )
    if actual != expected:
        raise InfraError(
            "pystack-backend PYSTACK_DATABASE_URL does not match the internal "
            "Render Postgres connection string from pystack-db."
        )
    print("pystack-backend: PYSTACK_DATABASE_URL matches pystack-db")


def deploy_changed_services(
    client: RenderClient,
    services: list[RenderService],
    timeout_seconds: int,
) -> None:
    deploys: list[tuple[RenderService, str]] = []
    for service in services:
        deploy_id = client.create_deploy(service.id)
        deploys.append((service, deploy_id))
        print(f"{service.name}: triggered deploy {deploy_id}")

    deadline = time.monotonic() + timeout_seconds
    pending = dict(deploys)
    failure_statuses = {
        "build_failed",
        "update_failed",
        "canceled",
        "pre_deploy_failed",
        "deactivated",
    }
    while pending:
        if time.monotonic() > deadline:
            names = ", ".join(service.name for service in pending)
            raise InfraError(f"Timed out waiting for Render deploys: {names}")

        for service in list(pending):
            status = client.get_deploy_status(service.id, pending[service])
            if status == "live":
                print(f"{service.name}: deploy is live")
                del pending[service]
            elif status in failure_statuses:
                raise InfraError(f"{service.name}: deploy failed with status {status}")

        if pending:
            time.sleep(10)


def request_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 15,
) -> tuple[int, dict[str, str], bytes]:
    require_http_url(url)
    request = urllib.request.Request(  # noqa: S310 - validated as http(s) above.
        url, method=method, headers=headers or {}
    )
    with urllib.request.urlopen(  # noqa: S310 - validated as http(s) above.
        request, timeout=timeout_seconds
    ) as response:
        return response.status, dict(response.headers), response.read()


def require_http_url(url: str) -> None:
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in {"http", "https"}:
        raise InfraError(f"Refusing to request non-HTTP URL: {url}")


def header_value(headers: dict[str, str], name: str) -> str | None:
    normalized_name = name.lower()
    for key, value in headers.items():
        if key.lower() == normalized_name:
            return value
    return None


def wait_for_health(backend: RenderService, frontend: RenderService, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    backend_health_url = f"{backend.url}/api/v1/health"
    last_error = "health checks did not run"

    while time.monotonic() <= deadline:
        try:
            status, _, body = request_url(backend_health_url)
            payload = json.loads(body)
            if status != 200 or payload.get("status") != "ok" or payload.get("database") != "up":
                raise InfraError(f"backend health returned {payload!r}")

            status, headers, _ = request_url(
                backend_health_url,
                method="OPTIONS",
                headers={
                    "Origin": frontend.url,
                    "Access-Control-Request-Method": "GET",
                },
            )
            if status not in {200, 204}:
                raise InfraError(f"CORS preflight returned HTTP {status}")
            if header_value(headers, "Access-Control-Allow-Origin") != frontend.url:
                raise InfraError("CORS preflight did not allow the frontend origin")

            status, _, _ = request_url(frontend.url)
            if not 200 <= status < 300:
                raise InfraError(f"frontend returned HTTP {status}")

            print("Health checks passed")
            return
        except (InfraError, OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = str(error)
            time.sleep(10)

    raise InfraError(f"Timed out waiting for healthy Render deployment: {last_error}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    args = parse_args()
    blueprint_path = (ROOT / args.blueprint).resolve()

    try:
        validate_blueprint(blueprint_path)

        client = RenderClient(render_api_key(), args.api_base_url)

        backend = client.get_service(BACKEND_SERVICE_NAME)
        frontend = client.get_service(FRONTEND_SERVICE_NAME)
        print(f"Discovered {backend.name}: {backend.url}")
        print(f"Discovered {frontend.name}: {frontend.url}")

        backend_env = {
            "PYSTACK_CORS_ORIGINS": json.dumps([frontend.url], separators=(",", ":")),
        }
        frontend_env = {"VITE_API_URL": backend.url}

        changed_services: list[RenderService] = []
        if reconcile_env_vars(client, backend, backend_env, args.dry_run):
            changed_services.append(backend)
        if reconcile_env_vars(client, frontend, frontend_env, args.dry_run):
            changed_services.append(frontend)

        verify_database_url(client, backend)

        if args.dry_run:
            print("Dry run complete; no Render changes were made")
            return 0

        if changed_services and args.skip_deploy:
            print("Env vars changed; deploy skipped by request")
        elif changed_services:
            deploy_changed_services(client, changed_services, args.timeout)
        else:
            print("No env var changes; deploy skipped")

        if not args.skip_health:
            wait_for_health(backend, frontend, args.timeout)

    except InfraError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
