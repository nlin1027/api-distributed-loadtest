import aiohttp
import asyncio

async def request(session, url):
    async with session.get(url) as response:
        await response.read()
        return response.status

async def main():
    url = "http://localhost:3000/average_list"
    async with aiohttp.ClientSession() as session:
        result = await request(session, url)
        print(result)

asyncio.run(main())