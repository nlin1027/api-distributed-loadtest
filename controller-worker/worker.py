from aiohttp import web
from engine import run_load_test
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

async def handle_run(request):
    body = await request.json()
    stats = await run_load_test(body["test_id"], body["users"], body["url"],body["duration"])
    return web.json_response(stats)

async def handle_metrics(request):
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

app = web.Application()
app.router.add_post("/run", handle_run)
app.router.add_get("/metrics", handle_metrics)

if __name__ == "__main__":
    web.run_app(app, port=8080)