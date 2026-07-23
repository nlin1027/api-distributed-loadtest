from scaler import discover_workers_container, get_worker_metrics, sync_prometheus_targets
import time

POLL_INTERVAL = 5
IDLE_COOLDOWN = 30
MIN_WORKERS = 1

idle_since = {}

def main():
    while True:
        containers = discover_workers_container()
        now = time.monotonic()

        for c in containers:
            active_users = get_worker_metrics(f"http://{c.name}:8080", "worker_active_users")
            if active_users == 0:
                idle_since.setdefault(c.id, now)
            elif active_users is not None:
                idle_since.pop(c.id, None)
        
        reapable = [c for c in containers if c.id in idle_since and (now - idle_since[c.id]) >= IDLE_COOLDOWN]

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