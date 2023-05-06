import asyncio
from contextlib import asynccontextmanager

AUTHORIZED = False


@asynccontextmanager
async def open_reader_socket(host, port):
    writer = None
    try:
        reader, writer = await asyncio.open_connection(host, port)
        yield reader
    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None


@asynccontextmanager
async def open_writer_socket(host, port):
    writer = None
    try:
        reader, writer = await asyncio.open_connection(host, port)
        yield (reader, writer)
    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None
