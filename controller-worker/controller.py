import aiohttp
import asyncio

async def dispatch_load(session, worker_url, users, request_url, duration):
    try:
        async with session.post(
            f"{worker_url}/run",
            json = {"users": users, "url": request_url, "duration": duration},
            timeout = aiohttp.ClientTimeout(total = duration + 10)
        ) as response: 
            return await response.json()
    except(aiohttp.ClientError, asyncio.TimeoutError) as e:
        return e

async def run_distributed_test(request_url, total_users, workers, duration):
    base, remainder = divmod(total_users, len(workers))
    user_distribution = [base + 1 if i < remainder else base for i in range(len(workers))]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for worker_url, users in zip(workers, user_distribution):
            tasks.append(dispatch_load(session, worker_url, users, request_url, duration))
        responses = await asyncio.gather(*tasks)

    successes = [response for response in responses if not isinstance(response, Exception)]
    failures = [response for response in responses if  isinstance(response, Exception)]

    print(workers, user_distribution, successes, failures)

async def main():
    request_url = "http://localhost:3000/average_list" #the actual api endpoint we are testing
    total_users = 100
    workers = ["http://localhost:8081"]
    duration = 5

    await run_distributed_test(request_url, total_users, workers, duration)

if __name__ == "__main__":
    asyncio.run(main())