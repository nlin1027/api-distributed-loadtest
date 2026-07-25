import aiohttp
import asyncio
from aiohttp import web
import math
import numpy as np
from scaler import discover_workers_container, boot_up_workers
import uuid

tests = {}
scale_lock = asyncio.Lock()
MAX_USERS_PER_WORKER = 30

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

async def run_distributed_test(test_id, request_url, total_users, workers, duration, user_distribution):
    dispatched = [(worker_url, users) for worker_url, users in zip(workers, user_distribution) if users > 0]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for worker_url, users in dispatched:
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

async def execute_test(test_id, request_url, total_users, duration):
    try:
        async with scale_lock:
            loop = asyncio.get_running_loop()
            workers, user_distribution = await loop.run_in_executor(None, boot_up_workers, total_users, MAX_USERS_PER_WORKER)

        result = await run_distributed_test(test_id, request_url, total_users, workers, duration, user_distribution)
        tests[test_id] = {"status": "complete", "result": result}
    except Exception as e:
        tests[test_id] = {"status": "failed", "error": str(e)}

async def handle_submit_test(request):
    body = await request.json()

    try:
        request_url = body["url"]
        total_users = body["total_users"]
        duration = body["duration"]
    except KeyError as e:
        return web.json_response({"error": f"missing field {e}"}, status=400)

    test_id = str(uuid.uuid4())
    tests[test_id] = {"status": "running"}
    asyncio.create_task(execute_test(test_id, request_url, total_users, duration))

    return web.json_response({"test_id": test_id, "status": "running"}, status=202)

async def handle_get_test(request):
    test_id = request.match_info["test_id"]
    test = tests.get(test_id)

    if test is None:
        return web.json_response({"status": "test not found"}, status=404)

    return web.json_response({"test_id": test_id, **test})

app = web.Application()
app.router.add_post("/tests", handle_submit_test)
app.router.add_get("/tests/{test_id}", handle_get_test)

if __name__ == "__main__":
    web.run_app(app, port=8000)