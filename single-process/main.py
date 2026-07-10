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

async def main():
    url = "http://localhost:3000/average_list"
    async with aiohttp.ClientSession() as session:
        result, latency, error = await request(session, url)
        print(f"status: {result} | latency: {latency} | error: {error}")

asyncio.run(main())