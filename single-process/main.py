import aiohttp
import asyncio
import time
import numpy as np

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

        result_intervals.append((requests_current, interval_p50, interval_p95, interval_p99, interval_error_rate))
        requests_last += requests_current
    print(result_intervals)


async def simulate_user(session, url, duration, results):
    while time.monotonic() < duration:
        result, latency, error = await request(session, url)
        results.append((result, latency, error))

async def main():
    url = "http://localhost:3000/average_list"
    duration = 10
    users = 25
    results = []
    result_intervals = []
    time_elapsed = 0.0
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        duration = time.monotonic() + duration
        start = time.monotonic()
        tasks.append(asyncio.create_task(reporter(duration, results, result_intervals)))
        for i in range(users):
            tasks.append(asyncio.create_task(simulate_user(session, url, duration, results)))
        await asyncio.gather(*tasks)
        time_elapsed = time.monotonic() - start

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
    print(throughput, (p50, p95, p99), error_rate)

asyncio.run(main())