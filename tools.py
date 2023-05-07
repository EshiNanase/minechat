import asyncio
from contextlib import asynccontextmanager
from gui import NicknameReceived

AUTHORIZED = False


@asynccontextmanager
async def open_socket(host, port):
    writer = None

    try:
        reader, writer = await asyncio.open_connection(host, port)
        yield (reader, writer)

    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None


def set_username(username, status_updates_queue):

    event = NicknameReceived(username)
    status_updates_queue.put_nowait(event)
