from scaler import discover_workers_container, get_worker_metrics, sync_prometheus_targets
import time
import urllib
import json

POLL_INTERVAL = 5
IDLE_COOLDOWN = 30
MIN_WORKERS = 1

CONTROLLER_ASSIGNMENTS_URL = "http://controller:8000/assignments"

idle_since = {}

def get_active_workers():
    try:
        body = urllib.request.urlopen(CONTROLLER_ASSIGNMENTS_URL, timeout=2).read().decode()
        return set(json.loads(body)["active_workers"])
    except (urllib.error.URLError, ConnectionError):
        return None

def main():
    while True:
        containers = discover_workers_container()
        now = time.monotonic()

        active_workers = get_active_workers()
        if active_workers is None:
            time.sleep(POLL_INTERVAL)
            continue

        for c in containers:
            active_users = get_worker_metrics(f"http://{c.name}:8080", "worker_active_users")
            if active_users == 0:
                idle_since.setdefault(c.id, now)
            elif active_users is not None:
                idle_since.pop(c.id, None)
        
        reapable = [
            c for c in containers 
            if c.id in idle_since 
            and (now - idle_since[c.id]) >= IDLE_COOLDOWN
            and f"http://{c.name}:8080" not in active_workers
        ]

        surplus = max(0, len(containers) - MIN_WORKERS)
        for c in reapable[:surplus]:
            c.stop()
            c.remove()
            idle_since.pop(c.id, None)
            print(f"reaped idle worker {c.name}")
        
        if reapable[:surplus]: sync_prometheus_targets()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()