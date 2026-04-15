#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import importlib.metadata
import json
import os
import pathlib
import platform
import shutil
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import stripe


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
REPORT_PATH = ROOT / ".tooling-report.json"

MANDATORY_KEYS = [
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "HOSTINGER_API_TOKEN",
    "HOSTINGER_DOMAIN",
    "FLYIO_API_TOKEN",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "CLERK_SECRET_KEY",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "PYPI",
]

OPTIONAL_KEYS = [
    "ANTHROPIC_API_KEY",
    "GH_TOKEN",
    "NPM_TOKEN",
    "NEXT_PUBLIC_POSTHOG_KEY",
    "TELEGRAM_BOT_TOKEN",
    "HEARTBEAT_BEACON_URL",
    "BEACON_WRITE_SECRET",
    "RESEND_API_KEY",
]

HOSTINGER_TARGET_ZONES = [
    "systemzero.dev",
    "system0.dev",
]

NETWORK_TARGETS = {
    "github": "https://api.github.com",
    "stripe": "https://api.stripe.com",
    "fly": "https://api.fly.io",
    "npm": "https://registry.npmjs.org",
    "pypi": "https://pypi.org",
    "openai": "https://api.openai.com/v1/models",
    "groq": "https://api.groq.com",
    "supabase": "https://supabase.com",
    "clerk": "https://api.clerk.com",
    "resend": "https://api.resend.com",
    "posthog": "https://app.posthog.com",
    "hostinger": "https://developers.hostinger.com",
}


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_env_file(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def mask_value(value: str) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def run_shell(command: str) -> str:
    result = subprocess.run(
        command,
        shell=True,
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, check=True, cwd=ROOT, text=True, capture_output=True)
    output = result.stdout.strip()
    if output:
        return output
    return result.stderr.strip()


def maybe_command_output(command: list[str]) -> str:
    try:
        return command_output(command)
    except Exception:
        return "missing"


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 15,
) -> tuple[int | None, str]:
    request = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return exc.code, body
    except Exception as exc:
        return None, str(exc)


def curl_request(
    url: str,
    *,
    method: str = "GET",
    headers: list[str] | None = None,
    data: str | None = None,
    timeout: int = 15,
) -> tuple[int | None, str]:
    command = [
        "curl",
        "-sS",
        "-X",
        method,
        "--max-time",
        str(timeout),
        "-w",
        "\n%{http_code}",
    ]
    for header in headers or []:
        command.extend(["-H", header])
    if data is not None:
        command.extend(["--data", data])
    command.append(url)
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = result.stdout
    if "\n" not in output:
        return None, (result.stderr or output).strip()
    body, status_text = output.rsplit("\n", 1)
    try:
        status = int(status_text.strip())
    except ValueError:
        return None, output.strip()
    return status, body


def curl_request_with_retries(
    url: str,
    *,
    method: str = "GET",
    headers: list[str] | None = None,
    data: str | None = None,
    timeout: int = 15,
    attempts: int = 3,
    retry_statuses: set[int] | None = None,
) -> tuple[int | None, str]:
    retry_statuses = retry_statuses or {429, 500, 502, 503, 504}
    last_status: int | None = None
    last_body = ""
    for attempt in range(attempts):
        status, body = curl_request(
            url,
            method=method,
            headers=headers,
            data=data,
            timeout=timeout,
        )
        last_status, last_body = status, body
        if status not in retry_statuses or attempt == attempts - 1:
            break
    return last_status, last_body


def basic_auth_header(username: str, password: str = "") -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def network_status(url: str) -> str:
    status, _ = http_request("GET", url, timeout=10)
    return str(status) if status is not None else "UNREACHABLE"


def split_key_prefix(value: str, segments: int = 2) -> str:
    if not value:
        return ""
    parts = value.split("_")
    return "_".join(parts[:segments]) if len(parts) >= segments else parts[0]


def decode_clerk_publishable_key(value: str) -> str:
    encoded = value.split("_", 2)[2]
    for suffix in ("", "=", "==", "==="):
        try:
            return base64.urlsafe_b64decode(encoded + suffix).decode("utf-8").rstrip("$")
        except Exception:
            continue
    raise ValueError("unable to decode Clerk publishable key")


def project_ref(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    return hostname.split(".")[0]


def parse_json(body: str) -> dict:
    try:
        return json.loads(body)
    except Exception:
        return {}


def build_platform_section() -> dict[str, str]:
    system = platform.system()
    section = {
        "system": system,
        "architecture": platform.machine(),
    }
    if system == "Darwin":
        for key, command in {
            "product_name": ["sw_vers", "-productName"],
            "product_version": ["sw_vers", "-productVersion"],
            "build_version": ["sw_vers", "-buildVersion"],
        }.items():
            section[key] = maybe_command_output(command)
    return section


def build_python_section() -> dict[str, str]:
    pip_version = command_output([sys.executable, "-m", "pip", "--version"])
    pipx_version = command_output(["pipx", "--version"])
    return {
        "version": sys.version.split()[0],
        "executable": sys.executable,
        "pip_version": pip_version,
        "pipx_version": pipx_version,
    }


def build_tools_section() -> dict[str, str]:
    tools = {
        "git": ["git", "--version"],
        "curl": ["curl", "--version"],
        "jq": ["jq", "--version"],
        "tar": ["tar", "--version"],
        "unzip": ["unzip", "-v"],
        "make": ["make", "--version"],
        "bash": ["bash", "--version"],
        "openssl": ["openssl", "version"],
        "dig": ["dig", "-v"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "gh": ["gh", "--version"],
        "fly": ["fly", "version"],
    }
    versions: dict[str, str] = {}
    for name, command in tools.items():
        tool_path = shutil.which(command[0])
        if not tool_path:
            versions[name] = "missing"
            continue
        try:
            versions[name] = command_output(command).splitlines()[0]
        except Exception:
            versions[name] = f"present ({tool_path})"
    return versions


def build_python_packages_section() -> dict[str, str]:
    packages = [
        "pyyaml",
        "jsonschema",
        "click",
        "rich",
        "platformdirs",
        "fastapi",
        "uvicorn",
        "stripe",
        "httpx",
        "supabase",
        "resend",
    ]
    return {package: importlib.metadata.version(package) for package in packages}


def validate_openai(env: dict[str, str]) -> tuple[bool, str]:
    status, _ = http_request(
        "GET",
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}"},
    )
    return status == 200, f"GET /v1/models -> HTTP {status}"


def validate_groq(env: dict[str, str]) -> tuple[bool, str]:
    status, _ = curl_request(
        "https://api.groq.com/openai/v1/models",
        headers=[f"Authorization: Bearer {env['GROQ_API_KEY']}"],
    )
    return status == 200, f"GET /openai/v1/models -> HTTP {status}"


def validate_fly(env: dict[str, str]) -> tuple[bool, str]:
    payload = json.dumps({"query": "{ viewer { id } }"})
    status, body = curl_request(
        "https://api.fly.io/graphql",
        method="POST",
        headers=[
            f"Authorization: Bearer {env['FLYIO_API_TOKEN']}",
            "Content-Type: application/json",
        ],
        data=payload,
    )
    return status == 200, f"POST /graphql -> HTTP {status}"


def validate_stripe_secret(env: dict[str, str]) -> tuple[bool, str]:
    status, body = http_request(
        "GET",
        "https://api.stripe.com/v1/account",
        headers={"Authorization": basic_auth_header(env["STRIPE_SECRET_KEY"])},
    )
    account_id = parse_json(body).get("id", "")
    return bool(status == 200 and account_id.startswith("acct_")), f"GET /v1/account -> HTTP {status}"


def validate_stripe_publishable(env: dict[str, str]) -> tuple[bool, str]:
    data = urllib.parse.urlencode(
        {
            "card[number]": "4242424242424242",
            "card[exp_month]": "12",
            "card[exp_year]": "2030",
            "card[cvc]": "123",
        }
    ).encode("utf-8")
    status, body = http_request(
        "POST",
        "https://api.stripe.com/v1/tokens",
        headers={
            "Authorization": basic_auth_header(env["STRIPE_PUBLISHABLE_KEY"]),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
    )
    parsed = parse_json(body)
    token_id = parsed.get("id", "")
    error_code = parsed.get("error", {}).get("decline_code") or parsed.get("error", {}).get("code")
    valid = (status == 200 and token_id.startswith("tok_")) or (
        status == 402 and error_code == "live_mode_test_card"
    )
    evidence = f"POST /v1/tokens with publishable key -> HTTP {status}"
    if error_code:
        evidence += f" ({error_code})"
    return valid, evidence


def validate_stripe_webhook_secret(env: dict[str, str]) -> tuple[bool, str]:
    secret = env["STRIPE_WEBHOOK_SECRET"]
    payload = b'{"id":"evt_test_webhook","object":"event"}'
    timestamp = str(int(dt.datetime.now(dt.UTC).timestamp()))
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    try:
        stripe.Webhook.construct_event(payload=payload, sig_header=header, secret=secret)
    except Exception as exc:
        return False, f"local webhook signature round-trip failed: {exc}"
    prefix_ok = secret.startswith("whsec_")
    return prefix_ok, "local webhook signature round-trip via stripe.Webhook.construct_event"


def validate_hostinger_token_and_domain(env: dict[str, str]) -> tuple[bool, bool, str]:
    endpoint = "https://developers.hostinger.com/api/dns/v1"
    status, _ = curl_request(
        f"{endpoint}/zones/{env['HOSTINGER_DOMAIN']}",
        headers=[f"Authorization: Bearer {env['HOSTINGER_API_TOKEN']}"],
    )
    ok = status == 200
    return ok, ok, endpoint if ok else ""


def validate_hostinger_target_zones(
    env: dict[str, str],
    endpoint: str,
) -> dict[str, dict[str, object]]:
    zone_results: dict[str, dict[str, object]] = {}
    for zone in HOSTINGER_TARGET_ZONES:
        status, _ = curl_request(
            f"{endpoint}/zones/{zone}",
            headers=[f"Authorization: Bearer {env['HOSTINGER_API_TOKEN']}"],
        )
        zone_results[zone] = {
            "validated": status == 200,
            "evidence": f"GET {endpoint}/zones/{zone} -> HTTP {status}",
        }
    return zone_results


def validate_supabase_service(env: dict[str, str]) -> tuple[bool, bool, str]:
    headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
    }
    status, _ = http_request("GET", f"{env['SUPABASE_URL'].rstrip('/')}/rest/v1/", headers=headers)
    evidence = f"GET {env['SUPABASE_URL'].rstrip('/')}/rest/v1/ with service role -> HTTP {status}"
    ok = status == 200
    return ok, ok, evidence


def validate_supabase_public(env: dict[str, str]) -> tuple[bool, bool, str]:
    public_url = env["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/")
    status, _ = curl_request(
        f"{public_url}/auth/v1/settings",
        headers=[f"apikey: {env['NEXT_PUBLIC_SUPABASE_ANON_KEY']}"],
    )
    same_project = project_ref(env["SUPABASE_URL"]) == project_ref(public_url)
    ok = status == 200 and same_project
    evidence = f"GET {public_url}/auth/v1/settings with anon key -> HTTP {status}; project-ref-match={same_project}"
    return ok, ok, evidence


def validate_clerk_secret(env: dict[str, str]) -> tuple[bool, str]:
    status, _ = curl_request_with_retries(
        "https://api.clerk.com/v1/users",
        headers=[f"Authorization: Bearer {env['CLERK_SECRET_KEY']}"],
    )
    return status == 200, f"GET /v1/users -> HTTP {status}"


def validate_clerk_publishable(env: dict[str, str]) -> tuple[bool, str]:
    frontend_api = decode_clerk_publishable_key(env["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"])
    status, body = curl_request(f"https://{frontend_api}/v1/client")
    response_object = parse_json(body).get("response", {}).get("object")
    valid = status == 200 and response_object == "client"
    evidence = f"decoded frontend API {frontend_api}; GET /v1/client -> HTTP {status}"
    return valid, evidence


def validate_pypi(env: dict[str, str]) -> tuple[bool, str]:
    token = env["PYPI"]
    prefix_ok = token.startswith("pypi-")
    long_enough = len(token) > 30
    return prefix_ok and long_enough, f"token prefix={split_key_prefix(token, 1)} length={len(token)}"


def validate_resend(env: dict[str, str]) -> tuple[bool, str]:
    if not env.get("RESEND_API_KEY"):
        return False, "RESEND_API_KEY absent"
    status, _ = http_request(
        "GET",
        "https://api.resend.com/domains",
        headers={"Authorization": f"Bearer {env['RESEND_API_KEY']}"},
    )
    return status == 200, f"GET /domains -> HTTP {status}"


def validate_optional_presence(env: dict[str, str], key: str) -> dict[str, object]:
    value = env.get(key, "")
    return {
        "present": bool(value),
        "validated": False,
        "masked_value": mask_value(value),
        "validation_method": "not-validated-in-phase-00",
        "evidence": "optional key presence check only" if value else "absent (ok)",
    }


def main() -> int:
    if not ENV_PATH.exists():
        print("NO .env", file=sys.stderr)
        return 1

    env = read_env_file(ENV_PATH)

    credentials: dict[str, dict[str, object]] = {}

    def record(
        key: str,
        *,
        present: bool,
        validated: bool,
        method: str,
        evidence: str,
    ) -> None:
        credentials[key] = {
            "present": present,
            "validated": validated,
            "masked_value": mask_value(env.get(key, "")),
            "validation_method": method,
            "evidence": evidence,
        }

    openai_ok, openai_evidence = validate_openai(env)
    record("OPENAI_API_KEY", present=bool(env.get("OPENAI_API_KEY")), validated=openai_ok, method="remote-api", evidence=openai_evidence)

    groq_ok, groq_evidence = validate_groq(env)
    record("GROQ_API_KEY", present=bool(env.get("GROQ_API_KEY")), validated=groq_ok, method="remote-api", evidence=groq_evidence)

    stripe_secret_ok, stripe_secret_evidence = validate_stripe_secret(env)
    record("STRIPE_SECRET_KEY", present=bool(env.get("STRIPE_SECRET_KEY")), validated=stripe_secret_ok, method="remote-api", evidence=stripe_secret_evidence)

    stripe_pub_ok, stripe_pub_evidence = validate_stripe_publishable(env)
    record("STRIPE_PUBLISHABLE_KEY", present=bool(env.get("STRIPE_PUBLISHABLE_KEY")), validated=stripe_pub_ok, method="remote-api", evidence=stripe_pub_evidence)

    stripe_webhook_ok, stripe_webhook_evidence = validate_stripe_webhook_secret(env)
    record("STRIPE_WEBHOOK_SECRET", present=bool(env.get("STRIPE_WEBHOOK_SECRET")), validated=stripe_webhook_ok, method="local-cryptographic-roundtrip", evidence=stripe_webhook_evidence)

    hostinger_token_ok, hostinger_domain_ok, hostinger_endpoint = validate_hostinger_token_and_domain(env)
    record("HOSTINGER_API_TOKEN", present=bool(env.get("HOSTINGER_API_TOKEN")), validated=hostinger_token_ok, method="remote-api", evidence=f"GET {hostinger_endpoint}/zones/{env['HOSTINGER_DOMAIN']} -> HTTP 200" if hostinger_token_ok else f"GET /zones/{env['HOSTINGER_DOMAIN']} failed")
    record("HOSTINGER_DOMAIN", present=bool(env.get("HOSTINGER_DOMAIN")), validated=hostinger_domain_ok, method="remote-api", evidence=f"exact zone lookup for {env['HOSTINGER_DOMAIN']} -> HTTP 200" if hostinger_domain_ok else f"exact zone lookup for {env['HOSTINGER_DOMAIN']} failed")
    hostinger_target_zones = (
        validate_hostinger_target_zones(env, hostinger_endpoint) if hostinger_endpoint else {}
    )

    fly_ok, fly_evidence = validate_fly(env)
    record("FLYIO_API_TOKEN", present=bool(env.get("FLYIO_API_TOKEN")), validated=fly_ok, method="remote-api", evidence=fly_evidence)

    supabase_url_ok, supabase_service_ok, supabase_service_evidence = validate_supabase_service(env)
    record("SUPABASE_URL", present=bool(env.get("SUPABASE_URL")), validated=supabase_url_ok, method="remote-api", evidence=supabase_service_evidence)
    record("SUPABASE_SERVICE_ROLE_KEY", present=bool(env.get("SUPABASE_SERVICE_ROLE_KEY")), validated=supabase_service_ok, method="remote-api", evidence=supabase_service_evidence)

    public_url_ok, anon_ok, public_evidence = validate_supabase_public(env)
    record("NEXT_PUBLIC_SUPABASE_URL", present=bool(env.get("NEXT_PUBLIC_SUPABASE_URL")), validated=public_url_ok, method="remote-api", evidence=public_evidence)
    record("NEXT_PUBLIC_SUPABASE_ANON_KEY", present=bool(env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")), validated=anon_ok, method="remote-api", evidence=public_evidence)

    clerk_secret_ok, clerk_secret_evidence = validate_clerk_secret(env)
    record("CLERK_SECRET_KEY", present=bool(env.get("CLERK_SECRET_KEY")), validated=clerk_secret_ok, method="remote-api", evidence=clerk_secret_evidence)

    clerk_pub_ok, clerk_pub_evidence = validate_clerk_publishable(env)
    record("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", present=bool(env.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")), validated=clerk_pub_ok, method="decoded-frontend-api", evidence=clerk_pub_evidence)

    pypi_ok, pypi_evidence = validate_pypi(env)
    record("PYPI", present=bool(env.get("PYPI")), validated=pypi_ok, method="format-and-length", evidence=pypi_evidence)

    for key in OPTIONAL_KEYS:
        credentials[key] = validate_optional_presence(env, key)

    resend_ok, resend_evidence = validate_resend(env)
    if env.get("RESEND_API_KEY"):
        credentials["RESEND_API_KEY"]["validated"] = resend_ok
        credentials["RESEND_API_KEY"]["validation_method"] = "remote-api"
        credentials["RESEND_API_KEY"]["evidence"] = resend_evidence

    report = {
        "generated_at": utc_now(),
        "workspace": str(ROOT),
        "branch": run_shell("git branch --show-current"),
        "phase_completion_state": {
            "git_branch": run_shell("git branch --show-current"),
            "git_head": run_shell("git rev-parse HEAD"),
            "mode": "workspace-state",
        },
        "platform": build_platform_section(),
        "python": build_python_section(),
        "tools": build_tools_section(),
        "python_packages": build_python_packages_section(),
        "network": {name: network_status(url) for name, url in NETWORK_TARGETS.items()},
        "runtime_dirs": {
            "user_sz_dir_creatable": (pathlib.Path.home() / ".sz").mkdir(parents=True, exist_ok=True) is None
        },
        "dns_strategy": "hostinger-only",
        "hostinger_endpoint": hostinger_endpoint,
        "hostinger_target_zones": hostinger_target_zones,
        "credentials": credentials,
    }

    missing_or_invalid = [
        key
        for key in MANDATORY_KEYS
        if not credentials.get(key, {}).get("present") or not credentials.get(key, {}).get("validated")
    ]
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")

    if missing_or_invalid:
        print("Invalid mandatory credentials:", ", ".join(missing_or_invalid), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
