import docker
import math
import time
import urllib.request
import urllib.error

docker_client = docker.from_env()

def discover_workers():
    containers = docker_client.containers.list(filters={"label": "role=worker"})
    return [f"http://{c.name}:8080" for c in containers]

def check_worker_status(worker_url, timeout, interval):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{worker_url}/metrics", timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError):
            time.sleep(interval)
    return False

def boot_up_workers(total_users, max_users_per_worker):
    current_workers = len(discover_workers())
    needed_workers = math.ceil(total_users / max_users_per_worker)
    workers_to_create = needed_workers - current_workers if needed_workers > current_workers else 0

    for i in range(workers_to_create):
        docker_client.containers.run(
            "controller-worker-worker:latest",
            detach=True,
            network="controller-worker_default",
            labels={"role": "worker"}
        )

    workers = discover_workers()
    for worker in workers:
        check_worker_status(worker, 10, 0.2)
    return workers