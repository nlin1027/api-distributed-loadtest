import aiohttp
import asyncio
import math
import numpy as np
from scaler import discover_workers_container, boot_up_workers
import uuid

async def dispatch_load(session, worker_url, users, request_url, duration, test_id):
    try:
        async with session.post(
            f"{worker_url}/run",
            json = {"test_id": test_id, "users": users, "url": request_url, "duration": duration},
            timeout = aiohttp.ClientTimeout(total = duration + 10)
        ) as response: 
            return await response.json()
    except(aiohttp.ClientError, asyncio.TimeoutError) as e:
        return e
    
def aggregate_data(successes, duration):
    latencies = []
    total_requests = 0
    errors = 0

    for response in successes:
        latencies.extend(response["latencies"])
        total_requests += response["total requests"]
        errors += response["errors"]
    
    if latencies:
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
    else:
        p50 = p95 = p99 = 0.0

    throughput = total_requests / duration
    error_rate = errors / total_requests if total_requests else 0.0

    return {"throughput": throughput, 
            "p50": p50, 
            "p95": p95, 
            "p99": p99, 
            "error rate": error_rate,
            "total requests": total_requests,
            "errors": errors
           }

async def run_distributed_test(request_url, total_users, workers, duration):
    base, remainder = divmod(total_users, len(workers))
    user_distribution = [base + 1 if i < remainder else base for i in range(len(workers))]
    test_id = str(uuid.uuid4())

    async with aiohttp.ClientSession() as session:
        tasks = []
        for worker_url, users in zip(workers, user_distribution):
            tasks.append(dispatch_load(session, worker_url, users, request_url, duration, test_id))
        responses = await asyncio.gather(*tasks)

    successes = [response for response in responses if not isinstance(response, Exception)]
    failures = [(worker_url, response) for worker_url, response in zip(workers, responses) if  isinstance(response, Exception)]

    print(f"{len(successes)} of {len(workers)} responded")
    for worker_url, error in failures:
        print(f"{worker_url} FAILED --> {type(error).__name__}: {error}")
    if not successes:
        raise RuntimeError("all workers failed, no data to aggregate")
    
    return aggregate_data(successes, duration)

async def main():
    request_url = "http://host.docker.internal:3000/average_list" #the actual api endpoint we are testing
    total_users = 100
    max_users_per_worker = 30
    workers = boot_up_workers(total_users, max_users_per_worker)
    duration = 20

    print(await run_distributed_test(request_url, total_users, workers, duration))

if __name__ == "__main__":
    asyncio.run(main())