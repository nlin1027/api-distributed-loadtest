import aiohttp
import asyncio
import time
import numpy as np
import psutil
from prometheus_client import Gauge

active_users = Gauge("worker_active_users", "Virtual users currently assigned to this worker")
cpu_percent = Gauge("worker_cpu_percent", "CPU usage percent of this worker process")
target_p50 = Gauge("target_latency_p50_seconds", "Target p50 latency, last reporting interval")
target_p95 = Gauge("target_latency_p95_seconds", "Target p95 latency, last reporting interval")
target_p99 = Gauge("target_latency_p99_seconds", "Target p99 latency, last reporting interval")
target_error_rate = Gauge("target_error_rate", "Target error rate, last reporting interval")

def update_active_users():
    active_users.set(sum(active_users_set.values()))

#sends a single request
async def request(session, url):
    start = time.perf_counter()
    try:
        async with session.get(url) as response:
            await response.read()
            latency = time.perf_counter() - start
            return response.status, latency, None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        latency = time.perf_counter() - start
        return None, latency, e
    
#reports the status of the load session
async def reporter(duration, results, result_intervals):
    requests_last = 0
    while time.monotonic() < duration:
        await asyncio.sleep(1)
        requests_current = len(results) - requests_last

        interval_latencies = []
        errors = 0
        for r in results[requests_last:]:
            status, latency, error = r
            if error is None and status < 400:
                interval_latencies.append(latency)
            else:
                errors += 1

        if interval_latencies:
            interval_p50 = float(np.percentile(interval_latencies, 50))
            interval_p95 = float(np.percentile(interval_latencies, 95))
            interval_p99 = float(np.percentile(interval_latencies, 99))
        else:
            interval_p50 = interval_p95 = interval_p99 = 0.0

        interval_error_rate = errors / requests_current if results[requests_last:] else 0

        target_p50.set(interval_p50)
        target_p95.set(interval_p95)
        target_p99.set(interval_p99)
        target_error_rate.set(interval_error_rate)
        cpu_percent.set(psutil.cpu_percent())

        result_intervals.append((requests_current, interval_p50, interval_p95, interval_p99, interval_error_rate))
        requests_last += requests_current
    print(result_intervals)

#one "batch" of requests
async def simulate_user(session, url, duration, results):
    while time.monotonic() < duration:
        result, latency, error = await request(session, url)
        results.append((result, latency, error))

active_users_set = {}

#function to start load session
async def run_load_test(test_id, users, url, duration):
    results = []
    result_intervals = []
    timeout = aiohttp.ClientTimeout(total=10)

    active_users_set[test_id] = users
    update_active_users()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        duration = time.monotonic() + duration
        start = time.monotonic()
        tasks.append(asyncio.create_task(reporter(duration, results, result_intervals)))
        for i in range(users):
            tasks.append(asyncio.create_task(simulate_user(session, url, duration, results)))
        await asyncio.gather(*tasks)
        time_elapsed = time.monotonic() - start

    del active_users_set[test_id]
    update_active_users()

    latencies = []
    errors = 0
    for r in results:
        status, latency, error = r
        if error is None and status < 400:
            latencies.append(latency)
        else:
            errors += 1

    throughput = len(results) / time_elapsed
    if latencies:
        p50, p95, p99 = float(np.percentile(latencies, 50)), float(np.percentile(latencies, 95)), float(np.percentile(latencies, 99))
    else:
        p50 = p95 = p99 = 0.0
    error_rate = errors / len(results) if results else 0.0

    return {"throughput": throughput, 
            "p50": p50, 
            "p95": p95, 
            "p99": p99, 
            "error rate": error_rate,
            "latencies": latencies,
            "total requests": len(results),
            "errors": errors
           }