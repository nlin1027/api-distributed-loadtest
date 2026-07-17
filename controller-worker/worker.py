from aiohttp import web
from engine import run_load_test

async def handle_run(request):
    body = await request.json()
    stats = await run_load_test(body["users"], body["url"],body["duration"])
    return web.json_response(stats)

app = web.Application()
app.router.add_post("/run", handle_run)

if __name__ == "__main__":
    web.run_app(app, port=8081)