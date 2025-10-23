import json
import os
import subprocess
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())


def _strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")
    ):
        return value[1:-1].strip()
    return value


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return _strip_quotes(os.getenv(name, default))


def _get_subscription_id() -> str:
    # Use provided env if present, else query az account show
    env_val = _env("AZURE_SUBSCRIPTION_ID") or _env("AZ_SUBSCRIPTION_ID")
    if env_val:
        return env_val
    proc = subprocess.run([
        "az", "account", "show", "--query", "id", "--output", "tsv"
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to get subscription id: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def _build_env_for_job() -> Dict[str, str]:
    # pass through most .env vars; exclude control vars used by this script
    excluded_prefixes = ("ACA_", "ACI_")
    excluded_exact = {"AZURE_SUBSCRIPTION_ID", "AZ_SUBSCRIPTION_ID"}
    env_map: Dict[str, str] = {}
    for key, val in os.environ.items():
        if key in excluded_exact or key.startswith(excluded_prefixes):
            continue
        if val is None:
            continue
        env_map[key] = val
    return env_map


def _job_exists(resource_group: str, job_name: str) -> bool:
    proc = subprocess.run([
        "az", "containerapp", "job", "show",
        "--resource-group", resource_group,
        "--name", job_name,
    ], capture_output=True, text=True)
    return proc.returncode == 0


def _create_or_update_job(resource_group: str,
                          environment_name: str,
                          job_name: str,
                          image: str,
                          acr_server: str,
                          mi_resource_id: Optional[str],
                          cpu: float,
                          memory_gb: float,
                          parallelism: int,
                          replica_completion_count: int,
                          replica_retry_limit: int,
                          env_map: Dict[str, str]) -> None:
    base_args = [
        "--name", job_name,
        "--resource-group", resource_group,
        "--environment", environment_name,
        "--trigger-type", "Manual",
        "--parallelism", str(parallelism),
        "--replica-timeout", "1800",
        "--replica-completion-count", str(replica_completion_count),
        "--min-executions", "0",
        "--max-executions", "1",
        "--replica-retry-limit", str(replica_retry_limit),
        "--image", image,
        "--cpu", str(cpu),
        "--memory", f"{memory_gb}Gi",
        "--registry-server", acr_server,
    ]
    if mi_resource_id:
        base_args += [
            "--mi-user-assigned", mi_resource_id,
            "--registry-identity", mi_resource_id,
        ]

    if env_map:
        base_args.append("--env-vars")
        for k, v in env_map.items():
            base_args.append(f"{k}={v}")

    if _job_exists(resource_group, job_name):
        cmd = ["az", "containerapp", "job", "update"] + base_args
    else:
        cmd = ["az", "containerapp", "job", "create"] + base_args

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"az failed: {proc.stderr.strip() or proc.stdout.strip()}")


def _start_job(resource_group: str, job_name: str) -> None:
    proc = subprocess.run([
        "az", "containerapp", "job", "start",
        "--resource-group", resource_group,
        "--name", job_name,
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"az failed: {proc.stderr.strip() or proc.stdout.strip()}")


def main():
    subscription_id = _get_subscription_id()

    resource_group = _env("ACA_RESOURCE_GROUP", "")
    environment_name = _env("ACA_ENVIRONMENT", "")
    if not environment_name:
        raise RuntimeError("Missing required environment variable: ACA_ENVIRONMENT (Container Apps environment name)")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    job_name = _env("ACA_JOB_NAME", f"think-job-{timestamp}")

    acr_name = _env("ACA_ACR_NAME", "")
    acr_server = _env("ACA_ACR_SERVER", f"{acr_name}.azurecr.io")
    image = _env("ACA_IMAGE", f"{acr_server}/think-container:latest")

    mi_name = _env("ACA_MI_NAME", "")
    mi_rg = _env("ACA_MI_RESOURCE_GROUP", "")
    mi_resource_id = _env("ACA_MI_ID") or f"/subscriptions/{subscription_id}/resourceGroups/{mi_rg}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{mi_name}"

    cpu = float(_env("ACA_CPU", "0.5"))
    memory_gb = float(_env("ACA_MEMORY_GB", "1"))
    parallelism = int(_env("ACA_PARALLELISM", "1"))
    replica_completion_count = int(_env("ACA_REPLICA_COMPLETION_COUNT", "1"))
    replica_retry_limit = int(_env("ACA_REPLICA_RETRY_LIMIT", "1"))

    env_map = _build_env_for_job()
    _create_or_update_job(
        resource_group, 
        environment_name, 
        job_name, 
        image, 
        acr_server, 
        mi_resource_id, cpu, memory_gb, parallelism, replica_completion_count, replica_retry_limit, env_map)
    _start_job(resource_group, job_name)
    print(json.dumps({"status": "Started", "job": job_name, "resourceGroup": resource_group, "environment": environment_name}))


if __name__ == "__main__":
    main()


