import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def open_socket(host, port):
    writer = None
    try:
        reader, writer = await asyncio.open_connection(host, port)
        yield (reader, writer)
    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None
