import aiohttp
import asyncio
import time

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
    
async def simulate_user(session, url, duration, results):
    while time.monotonic() < duration:
        result, latency, error = await request(session, url)
        results.append((result, latency, error))

async def main():
    url = "http://localhost:3000/average_list"
    duration = 10
    users = 25
    results = []
    time_elapsed = 0.0
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        duration = time.monotonic() + duration
        start = time.monotonic()
        for i in range(users):
            tasks.append(asyncio.create_task(simulate_user(session, url, duration, results)))
        await asyncio.gather(*tasks)
        time_elapsed = time.monotonic() - start
    throughput = len(results) / time_elapsed
    print(throughput)

asyncio.run(main())