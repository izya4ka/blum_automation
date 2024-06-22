import asyncio

from client import Client
from config import NICKNAMES


async def main():
    clients = [Client(i) for i in NICKNAMES]
    for client in clients:
        await client.refresh_token()
    await asyncio.gather(*(client.start() for client in clients))


asyncio.run(main())
