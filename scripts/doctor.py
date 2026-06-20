from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from render_infra import (
    BACKEND_SERVICE_NAME,
    DEFAULT_API_BASE_URL,
    FRONTEND_CUSTOM_ORIGIN,
    FRONTEND_SERVICE_NAME,
    POSTGRES_NAME,
    InfraError,
    RenderClient,
    RenderService,
    header_value,
    render_api_key,
    request_url,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

DEV_DATABASE_URL = "postgres://pystack:pystack@localhost:5432/pystack_dev?sslmode=disable"
TEST_DATABASE_URL = "postgres://pystack:pystack@localhost:5432/pystack_test?sslmode=disable"

LOCAL_REQUIRED_TOOLS = ["uv", "node", "npm", "docker", "dbmate", "gitleaks"]
LOCAL_REQUIRED_ENV = [
    "PYSTACK_OPENROUTER_API_KEY",
    "PYSTACK_CLERK_SECRET_KEY",
    "VITE_CLERK_PUBLISHABLE_KEY",
]
LOCAL_E2E_ENV = ["CLERK_TEST_USER_USERNAME", "CLERK_TEST_USER_PASSWORD"]

GITHUB_REQUIRED_SECRETS = [
    "PYSTACK_CLERK_SECRET_KEY",
    "VITE_CLERK_PUBLISHABLE_KEY",
    "CLERK_TEST_USER_USERNAME",
    "CLERK_TEST_USER_PASSWORD",
    "RENDER_API_KEY",
]

RESET = "\033[0m"
COLORS = {
    "PASS": "\033[32m",
    "WARN": "\033[33m",
    "FAIL": "\033[31m",
    "INFO": "\033[34m",
    "SECTION": "\033[1m",
    "FIX": "\033[2m",
}


@dataclass(frozen=True)
class CheckResult:
    status: str
    name: str
    detail: str
    fix: str | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class Doctor:
    def __init__(self, color: bool) -> None:
        self.results: list[CheckResult] = []
        self.color = color

    def pass_(self, name: str, detail: str) -> None:
        self.results.append(CheckResult("PASS", name, detail))

    def warn(self, name: str, detail: str, fix: str | None = None) -> None:
        self.results.append(CheckResult("WARN", name, detail, fix))

    def fail(self, name: str, detail: str, fix: str | None = None) -> None:
        self.results.append(CheckResult("FAIL", name, detail, fix))

    def info(self, name: str, detail: str) -> None:
        self.results.append(CheckResult("INFO", name, detail))

    def section(self, name: str) -> None:
        self.results.append(CheckResult("SECTION", name, ""))

    def colorize(self, value: str, style: str) -> str:
        if not self.color:
            return value
        return f"{COLORS[style]}{value}{RESET}"

    def print(self) -> int:
        printed_check = False
        for result in self.results:
            if result.status == "SECTION":
                if printed_check:
                    print()
                print(self.colorize(f"== {result.name} ==", "SECTION"))
                continue
            status = self.colorize(f"[{result.status.lower()}]", result.status)
            print(f"{status} {result.name}: {result.detail}")
            printed_check = True
            if result.fix:
                print(self.colorize(f"       fix: {result.fix}", "FIX"))

        counts = {status: 0 for status in ["PASS", "WARN", "FAIL", "INFO"]}
        for result in self.results:
            if result.status in counts:
                counts[result.status] += 1

        summary = (
            "\nSummary: "
            f"{self.colorize(str(counts['PASS']), 'PASS')} passed, "
            f"{self.colorize(str(counts['WARN']), 'WARN')} warnings, "
            f"{self.colorize(str(counts['FAIL']), 'FAIL')} failures, "
            f"{self.colorize(str(counts['INFO']), 'INFO')} info"
        )
        print(summary)
        return 1 if counts["FAIL"] else 0


def run_command(args: list[str], timeout: int = 15) -> CommandResult:
    try:
        result = subprocess.run(  # noqa: S603 - commands are fixed by check functions.
            args,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        return CommandResult(127, "", str(error))
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        return CommandResult(124, stdout, stderr or f"timed out after {timeout}s")

    return CommandResult(result.returncode, result.stdout.strip(), result.stderr.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local and hosted Pystack setup.")
    parser.add_argument(
        "scope",
        nargs="?",
        choices=["all", "dev", "services"],
        default="dev",
        help="Checks to run. Default: dev.",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Colorize output. Default: auto.",
    )
    return parser.parse_args()


def should_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def check_tool(suite: Doctor, tool: str, required: bool = True) -> bool:
    path = shutil.which(tool)
    if path:
        suite.pass_(f"{tool} installed", path)
        return True

    message = f"{tool} is not on PATH"
    if required:
        suite.fail(f"{tool} installed", message, install_hint(tool))
    else:
        suite.warn(f"{tool} installed", message, install_hint(tool))
    return False


def install_hint(tool: str) -> str:
    hints = {
        "uv": "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
        "node": "Install Node.js 24.16+; using nvm/fnm/asdf is fine.",
        "npm": "Install npm with Node.js.",
        "docker": "Install and start Docker Desktop.",
        "dbmate": "Install DBmate: go install github.com/amacneil/dbmate/v2@v2.30.0",
        "gitleaks": "Install gitleaks: go install github.com/zricethezav/gitleaks/v8@v8.30.0",
        "gh": "Install GitHub CLI and run gh auth login.",
        "render": "Install Render CLI and run render login.",
    }
    return hints.get(tool, f"Install {tool}.")


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(dotenv: dict[str, str], key: str) -> str | None:
    return os.environ.get(key) or dotenv.get(key)


def looks_unset(value: str | None) -> bool:
    return value is None or value.strip() == "" or "..." in value or value.lower() == "changeme"


def version_parts(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    major, minor, patch = (int(part) for part in [*parts[:3], "0", "0"][:3])
    return major, minor, patch


def check_node_version(suite: Doctor) -> None:
    expected = (ROOT / ".node-version").read_text().strip()
    result = run_command(["node", "-e", "console.log(process.versions.node)"])
    if result.returncode != 0:
        suite.fail("Node version", result.stderr or "could not execute node")
        return

    actual = result.stdout.strip()
    if version_parts(actual) >= version_parts(expected):
        suite.pass_("Node version", f"{actual} >= {expected}")
    else:
        suite.fail("Node version", f"{actual} is older than {expected}", "Install Node.js 24.16+.")


def check_docker(suite: Doctor) -> bool:
    compose = run_command(["docker", "compose", "version", "--short"])
    if compose.returncode == 0:
        suite.pass_("Docker Compose", compose.stdout)
    else:
        suite.fail("Docker Compose", compose.stderr or compose.stdout, "Install Docker Compose.")
        return False

    info = run_command(["docker", "info", "--format", "{{.ServerVersion}}"])
    if info.returncode == 0:
        suite.pass_("Docker daemon", f"running server {info.stdout}")
        return True

    suite.fail("Docker daemon", info.stderr or info.stdout, "Start Docker Desktop.")
    return False


def check_local_dependencies(suite: Doctor) -> None:
    if (BACKEND_DIR / ".venv").exists():
        suite.pass_("Backend virtualenv", "backend/.venv exists")
    else:
        suite.warn("Backend virtualenv", "backend/.venv is missing", "Run make backend-sync.")

    if (FRONTEND_DIR / "node_modules").exists():
        suite.pass_("Frontend dependencies", "frontend/node_modules exists")
    else:
        suite.warn(
            "Frontend dependencies",
            "frontend/node_modules is missing",
            "Run make frontend-install.",
        )

    hook = ROOT / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        suite.pass_("Pre-commit hook", ".git/hooks/pre-commit exists")
    else:
        suite.warn(
            "Pre-commit hook",
            "pre-commit hook is not installed",
            "Run make pre-commit-install.",
        )


def check_env_file(suite: Doctor) -> None:
    dotenv_path = ROOT / ".env"
    dotenv = load_dotenv(dotenv_path)
    if dotenv_path.exists():
        suite.pass_(".env file", ".env exists")
    else:
        suite.warn(
            ".env file",
            ".env is missing",
            "Copy .env.example to .env and fill real values.",
        )

    for key in LOCAL_REQUIRED_ENV:
        if looks_unset(env_value(dotenv, key)):
            suite.fail(f"Local env {key}", "missing or placeholder value", "Set it in .env.")
        else:
            suite.pass_(f"Local env {key}", "set")

    for key in LOCAL_E2E_ENV:
        if looks_unset(env_value(dotenv, key)):
            suite.warn(
                f"E2E env {key}",
                "missing or placeholder value",
                "Set it in .env before running make test-e2e.",
            )
        else:
            suite.pass_(f"E2E env {key}", "set")


def check_dbmate_status(suite: Doctor, name: str, url: str, no_dump_schema: bool = False) -> None:
    args = ["dbmate", "--url", url]
    if no_dump_schema:
        args.append("--no-dump-schema")
    args.append("status")
    result = run_command(args)
    if result.returncode != 0:
        suite.warn(f"{name} migrations", result.stderr or result.stdout, "Run make db-migrate.")
        return

    if "Pending: 0" in result.stdout:
        suite.pass_(f"{name} migrations", "no pending migrations")
    else:
        suite.warn(f"{name} migrations", "pending migrations found", "Run make db-migrate.")


def check_local_database(suite: Doctor, docker_running: bool) -> None:
    if not docker_running:
        suite.warn("Local database", "not checked because Docker is unavailable")
        return

    result = run_command(["docker", "compose", "ps", "db", "--format", "json"])
    if result.returncode != 0:
        suite.warn("Local database", result.stderr or result.stdout, "Run make db-up.")
        return
    if not result.stdout:
        suite.warn("Local database", "db container is not running", "Run make db-up.")
        return

    try:
        containers = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        suite.warn("Local database", f"could not parse docker compose status: {error}")
        return

    db_container = next(
        (container for container in containers if container.get("Service") == "db"), None
    )
    if not db_container:
        suite.warn("Local database", "db container is not running", "Run make db-up.")
        return

    state = str(db_container.get("State", "unknown"))
    health = str(db_container.get("Health", "unknown"))
    if state == "running" and health == "healthy":
        suite.pass_("Local database", "db container is running and healthy")
        check_dbmate_status(suite, "Development database", DEV_DATABASE_URL)
        check_dbmate_status(suite, "Test database", TEST_DATABASE_URL, no_dump_schema=True)
    else:
        suite.warn(
            "Local database",
            f"db container state={state}, health={health}",
            "Run make db-up.",
        )


def check_dev(suite: Doctor) -> None:
    suite.section("Local development")
    tool_status = {tool: check_tool(suite, tool) for tool in LOCAL_REQUIRED_TOOLS}
    if tool_status.get("node"):
        check_node_version(suite)
    docker_running = check_docker(suite) if tool_status.get("docker") else False
    check_local_dependencies(suite)
    check_env_file(suite)
    if tool_status.get("dbmate"):
        check_local_database(suite, docker_running)


def as_object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def check_github(suite: Doctor) -> str | None:
    if not check_tool(suite, "gh"):
        return None

    auth = run_command(["gh", "auth", "status"])
    if auth.returncode == 0:
        suite.pass_("GitHub auth", "gh is authenticated")
    else:
        suite.fail("GitHub auth", auth.stderr or auth.stdout, "Run gh auth login.")
        return None

    repo = run_command(["gh", "repo", "view", "--json", "nameWithOwner,defaultBranchRef,url"])
    if repo.returncode != 0:
        suite.fail("GitHub repository", repo.stderr or repo.stdout)
        return None

    try:
        payload = json.loads(repo.stdout)
    except json.JSONDecodeError as error:
        suite.fail("GitHub repository", f"could not parse gh output: {error}")
        return None

    repo_name = str(payload.get("nameWithOwner", ""))
    default_branch = as_object(payload.get("defaultBranchRef")).get("name")
    if repo_name:
        suite.pass_("GitHub repository", repo_name)
    else:
        suite.fail("GitHub repository", "could not determine repository")
        return None

    if default_branch == "main":
        suite.pass_("GitHub default branch", "main")
    else:
        suite.warn("GitHub default branch", f"expected main, found {default_branch!r}")

    check_github_secrets(suite, repo_name)
    return repo_name


def check_github_secrets(suite: Doctor, repo_name: str) -> None:
    result = run_command(["gh", "secret", "list", "--repo", repo_name, "--json", "name,updatedAt"])
    if result.returncode != 0:
        suite.fail("GitHub secrets", result.stderr or result.stdout)
        return

    try:
        secrets = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        suite.fail("GitHub secrets", f"could not parse gh output: {error}")
        return

    updated_by_name = {
        str(secret.get("name")): str(secret.get("updatedAt", "unknown"))
        for secret in secrets
        if isinstance(secret, dict)
    }
    for name in GITHUB_REQUIRED_SECRETS:
        updated_at = updated_by_name.get(name)
        if updated_at:
            suite.pass_(f"GitHub secret {name}", f"present, updated {updated_at}")
        else:
            suite.fail(
                f"GitHub secret {name}",
                "missing",
                "Set the missing secret in GitHub repository settings.",
            )

    if "DBMATE_PROD_DATABASE_URL" in updated_by_name:
        suite.info("GitHub DB URL override", "DBMATE_PROD_DATABASE_URL is set")
    else:
        suite.info(
            "GitHub DB URL override",
            "DBMATE_PROD_DATABASE_URL is not set; CI will use RENDER_API_KEY discovery",
        )


def check_render_cli(suite: Doctor) -> bool:
    if not check_tool(suite, "render"):
        return False

    whoami = run_command(["render", "whoami", "--output", "text"])
    if whoami.returncode == 0:
        suite.pass_("Render auth", "render CLI is authenticated")
    else:
        suite.fail("Render auth", whoami.stderr or whoami.stdout, "Run render login.")
        return False

    blueprint = run_command(
        ["render", "blueprints", "validate", "infra/render.yaml", "--output", "json", "--confirm"],
        timeout=30,
    )
    if blueprint.returncode != 0:
        suite.fail("Render Blueprint", blueprint.stderr or blueprint.stdout)
        return False

    try:
        payload = json.loads(blueprint.stdout)
    except json.JSONDecodeError as error:
        suite.fail("Render Blueprint", f"could not parse validation output: {error}")
        return False

    if payload.get("valid") is True:
        suite.pass_("Render Blueprint", "infra/render.yaml is valid")
    else:
        suite.fail("Render Blueprint", "Render reported the Blueprint is invalid")
        return False

    return True


def check_render_services(suite: Doctor, repo_name: str | None) -> None:
    try:
        client = RenderClient(render_api_key(), DEFAULT_API_BASE_URL)
    except InfraError as error:
        suite.fail("Render API key", str(error), "Set RENDER_API_KEY or run render login.")
        return

    suite.pass_("Render API key", "available")

    backend = get_render_service(suite, client, BACKEND_SERVICE_NAME)
    frontend = get_render_service(suite, client, FRONTEND_SERVICE_NAME)
    if backend is None or frontend is None:
        return

    expected_repo_url = f"https://github.com/{repo_name}" if repo_name else None
    check_render_service_settings(
        suite,
        client,
        backend,
        expected_root_dir="backend",
        expected_repo_url=expected_repo_url,
    )
    check_render_service_settings(
        suite,
        client,
        frontend,
        expected_root_dir="frontend",
        expected_repo_url=expected_repo_url,
    )
    check_render_postgres(suite, client)
    check_render_env(suite, client, backend, frontend)
    check_render_health(suite, backend, frontend)


def get_render_service(
    suite: Doctor, client: RenderClient, service_name: str
) -> RenderService | None:
    try:
        service = client.get_service(service_name)
    except InfraError as error:
        suite.fail(f"Render service {service_name}", str(error))
        return None

    suite.pass_(f"Render service {service_name}", f"{service.id} at {service.url}")
    return service


def render_service_payload(
    suite: Doctor, client: RenderClient, service: RenderService
) -> dict[str, object] | None:
    try:
        payload = client.request("GET", f"/services/{service.id}")
    except InfraError as error:
        suite.fail(f"{service.name} settings", str(error))
        return None

    if not isinstance(payload, dict):
        suite.fail(f"{service.name} settings", "Render API returned an unexpected payload")
        return None
    return payload


def check_render_service_settings(
    suite: Doctor,
    client: RenderClient,
    service: RenderService,
    expected_root_dir: str,
    expected_repo_url: str | None,
) -> None:
    payload = render_service_payload(suite, client, service)
    if payload is None:
        return

    check_render_field(suite, service.name, "autoDeploy", payload.get("autoDeploy"), "yes")
    check_render_field(
        suite,
        service.name,
        "autoDeployTrigger",
        payload.get("autoDeployTrigger"),
        "checksPass",
    )
    check_render_field(suite, service.name, "branch", payload.get("branch"), "main")
    check_render_field(suite, service.name, "rootDir", payload.get("rootDir"), expected_root_dir)
    if expected_repo_url:
        check_render_field(suite, service.name, "repo", payload.get("repo"), expected_repo_url)


def check_render_field(
    suite: Doctor, service_name: str, field: str, actual: object, expected: str
) -> None:
    if actual == expected:
        suite.pass_(f"{service_name} {field}", str(expected))
    else:
        suite.fail(f"{service_name} {field}", f"expected {expected!r}, found {actual!r}")


def check_render_postgres(suite: Doctor, client: RenderClient) -> None:
    query = f"name={POSTGRES_NAME}&limit=10"
    try:
        payload = client.request("GET", f"/postgres?{query}")
    except InfraError as error:
        suite.fail("Render Postgres", str(error))
        return

    if not isinstance(payload, list):
        suite.fail("Render Postgres", "Render API returned an unexpected payload")
        return

    matches = [
        entry.get("postgres")
        for entry in payload
        if isinstance(entry, dict)
        and isinstance(entry.get("postgres"), dict)
        and entry["postgres"].get("name") == POSTGRES_NAME
    ]
    if len(matches) != 1:
        suite.fail("Render Postgres", f"expected one {POSTGRES_NAME!r}, found {len(matches)}")
        return

    postgres = matches[0]
    status = postgres.get("status")
    if status == "available":
        suite.pass_("Render Postgres", "available")
    else:
        suite.fail("Render Postgres", f"status is {status!r}")

    plan = postgres.get("plan")
    expires_at = postgres.get("expiresAt")
    if plan == "free":
        detail = "free plan"
        if expires_at:
            detail += f", expires at {expires_at}"
        suite.warn(
            "Render Postgres plan",
            detail,
            "Upgrade before relying on this database for durable production data.",
        )
    else:
        suite.pass_("Render Postgres plan", str(plan))


def check_render_env(
    suite: Doctor,
    client: RenderClient,
    backend: RenderService,
    frontend: RenderService,
) -> None:
    origins = [frontend.url, FRONTEND_CUSTOM_ORIGIN]
    expected_origins = json.dumps(origins, separators=(",", ":"))
    expected_backend_env = {
        "PYSTACK_CORS_ORIGINS": expected_origins,
        "PYSTACK_CLERK_AUTHORIZED_PARTIES": expected_origins,
        "PYSTACK_ENVIRONMENT": "production",
    }
    for key, expected in expected_backend_env.items():
        check_render_env_value(suite, client, backend, key, expected)

    for key in ["PYSTACK_OPENROUTER_API_KEY", "PYSTACK_CLERK_SECRET_KEY"]:
        check_render_env_value(suite, client, backend, key)

    check_render_env_value(suite, client, frontend, "VITE_API_URL", backend.url)
    check_render_env_value(suite, client, frontend, "VITE_CLERK_PUBLISHABLE_KEY")
    check_database_url(suite, client, backend)


def check_render_env_value(
    suite: Doctor,
    client: RenderClient,
    service: RenderService,
    key: str,
    expected: str | None = None,
) -> None:
    try:
        actual = client.get_env_var(service.id, key)
    except InfraError as error:
        suite.fail(f"{service.name} env {key}", str(error))
        return

    if actual is None or actual == "":
        suite.fail(f"{service.name} env {key}", "missing")
        return

    if expected is None:
        suite.pass_(f"{service.name} env {key}", "set")
    elif actual == expected:
        suite.pass_(f"{service.name} env {key}", "matches expected value")
    else:
        suite.fail(f"{service.name} env {key}", "does not match expected value", "Run make infra.")


def check_database_url(suite: Doctor, client: RenderClient, backend: RenderService) -> None:
    try:
        postgres_id = client.get_postgres_id(POSTGRES_NAME)
        expected = client.get_internal_postgres_url(postgres_id)
        actual = client.get_env_var(backend.id, "PYSTACK_DATABASE_URL")
    except InfraError as error:
        suite.fail("Backend database URL", str(error))
        return

    if actual == expected:
        suite.pass_("Backend database URL", "matches Render Postgres internal URL")
    else:
        suite.fail("Backend database URL", "does not match Render Postgres", "Sync the Blueprint.")


def check_render_health(suite: Doctor, backend: RenderService, frontend: RenderService) -> None:
    backend_health_url = f"{backend.url}/api/v1/health"
    if not wait_for_backend_health(suite, backend_health_url):
        return

    for origin in [frontend.url, FRONTEND_CUSTOM_ORIGIN]:
        check_cors_preflight(suite, backend_health_url, origin)

    for url in [frontend.url, FRONTEND_CUSTOM_ORIGIN]:
        check_frontend_url(suite, url)


def wait_for_backend_health(suite: Doctor, backend_health_url: str) -> bool:
    deadline = time.monotonic() + 90
    last_error = "health check did not run"

    while time.monotonic() <= deadline:
        try:
            status, _, body = request_url(backend_health_url, timeout_seconds=30)
            payload = json.loads(body)
            if status == 200 and payload.get("status") == "ok" and payload.get("database") == "up":
                suite.pass_("Backend health", "healthy with database up")
                return True
            last_error = f"unexpected response: {payload!r}"
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = str(error)
        time.sleep(5)

    suite.fail("Backend health", last_error)
    return False


def check_cors_preflight(suite: Doctor, backend_health_url: str, origin: str) -> None:
    try:
        status, headers, _ = request_url(
            backend_health_url,
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
            timeout_seconds=30,
        )
    except (OSError, urllib.error.URLError) as error:
        suite.fail(f"CORS preflight {origin}", str(error))
        return

    if status in {200, 204} and header_value(headers, "Access-Control-Allow-Origin") == origin:
        suite.pass_(f"CORS preflight {origin}", "allowed")
    else:
        suite.fail(f"CORS preflight {origin}", f"unexpected HTTP {status}", "Run make infra.")


def check_frontend_url(suite: Doctor, url: str) -> None:
    try:
        status, _, _ = request_url(url, timeout_seconds=30)
    except (OSError, urllib.error.URLError) as error:
        suite.fail(f"Frontend {url}", str(error))
        return

    if 200 <= status < 300:
        suite.pass_(f"Frontend {url}", f"HTTP {status}")
    else:
        suite.fail(f"Frontend {url}", f"HTTP {status}")


def check_services(suite: Doctor) -> None:
    suite.section("Hosted services")
    repo_name = check_github(suite)
    check_render_cli(suite)
    check_render_services(suite, repo_name)


def main() -> int:
    args = parse_args()
    suite = Doctor(color=should_color(args.color))

    if args.scope in {"dev", "all"}:
        check_dev(suite)
    if args.scope in {"services", "all"}:
        check_services(suite)

    return suite.print()


if __name__ == "__main__":
    sys.exit(main())
