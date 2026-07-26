import docker
import math
import time
from prometheus_client.parser import text_string_to_metric_families
import urllib.request
import urllib.error
import urllib.parse
import json

docker_client = docker.from_env()
PROMETHEUS_TARGETS_PATH = "/etc/prometheus/targets/workers.json"
PROMETHEUS_URL = "http://prometheus:9090"
CPU_THRESHOLD = 80

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

def query_prometheus(promql):
    query = urllib.parse.urlencode({"query": promql})
    try:
        body = urllib.request.urlopen(f"{PROMETHEUS_URL}/api/v1/query?{query}", timeout=2).read().decode()
    except (urllib.error.URLError, ConnectionError):
        return None

    result = json.loads(body)["data"]["result"]
    return {r["metric"]["instance"]: float(r["value"][1]) for r in result}

def avg_cpu_by_worker(window="2m"):
    result = query_prometheus(f"avg_over_time(worker_cpu_percent[{window}])")
    if result is None:
        return {}
    return {f"http://{instance}": value for instance, value in result.items()}

def get_worker_headroom(worker_url, max_users_per_worker, avg_cpu=None):
    active = get_worker_metrics(worker_url, "worker_active_users") or 0
    headroom = max(0, max_users_per_worker - active)
    if avg_cpu is not None and avg_cpu >= CPU_THRESHOLD:
        return 0
    return headroom

def boot_up_workers(total_users, max_users_per_worker):
    workers = discover_workers_url()
    avg_cpu = avg_cpu_by_worker()
    headroom = {w: get_worker_headroom(w, max_users_per_worker, avg_cpu.get(w)) for w in workers}
    shortfall = max(0, total_users - sum(headroom.values()))
    workers_to_create = math.ceil(shortfall / max_users_per_worker) if shortfall else 0

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

    remaining = total_users
    user_distribution = []
    for worker in workers:
        available = headroom.get(worker, max_users_per_worker)
        users_to_assign = min(available, remaining)
        user_distribution.append(users_to_assign)
        remaining -= users_to_assign

    return workers, user_distribution

def get_worker_metrics(worker_url, metric):
    try:
        body = urllib.request.urlopen(f"{worker_url}/metrics", timeout=2).read().decode()
    except (urllib.error.URLError, ConnectionError):
        return None
    
    for family in text_string_to_metric_families(body):
        if family.name == metric:
            return family.samples[0].value if family.samples else 0
    return None