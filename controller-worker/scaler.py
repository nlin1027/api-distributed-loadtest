import docker
import math
import time
from prometheus_client.parser import text_string_to_metric_families
import urllib.request
import urllib.error
import json

docker_client = docker.from_env()
PROMETHEUS_TARGETS_PATH = "/etc/prometheus/targets/workers.json"

def discover_workers_container():
    return docker_client.containers.list(filters={"label": "role=worker"})

def discover_workers_url():
    return [f"http://{c.name}:8080" for c in discover_workers_container()]

def check_worker_status(worker_url, timeout, interval):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{worker_url}/metrics", timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError):
            time.sleep(interval)
    return False

def sync_prometheus_targets():
    workers = discover_workers_container()
    targets = [{"targets": [f"{container.name}:8080"]} for container in workers]
    with open(PROMETHEUS_TARGETS_PATH, "w") as f:
        json.dump(targets, f)

def boot_up_workers(total_users, max_users_per_worker):
    current_workers = len(discover_workers_url())
    needed_workers = math.ceil(total_users / max_users_per_worker)
    workers_to_create = needed_workers - current_workers if needed_workers > current_workers else 0

    for i in range(workers_to_create):
        docker_client.containers.run(
            "controller-worker-worker:latest",
            detach=True,
            network="controller-worker_default",
            labels={"role": "worker"}
        )

    workers = discover_workers_url()
    for worker in workers:
        check_worker_status(worker, 10, 0.2)

    if workers_to_create: sync_prometheus_targets()

    return workers

def get_worker_metrics(worker_url, metric):
    try:
        body = urllib.request.urlopen(f"{worker_url}/metrics", timeout=2).read().decode()
    except (urllib.error.URLError, ConnectionError):
        return None
    
    for family in text_string_to_metric_families(body):
        if family.name == metric:
            return family.samples[0].value if family.samples else 0
    return None
        
