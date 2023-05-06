import asyncio
from contextlib import asynccontextmanager
import time
from tkinter import messagebox
from gui import ReadConnectionStateChanged, SendingConnectionStateChanged, NicknameReceived
from requests import ConnectionError as RequestsConnectionError

AUTHORIZED = False
MAX_RECONNECT_ATTEMPTS = 3


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


def set_username(username, status_updates_queue):

    event = NicknameReceived(username)
    status_updates_queue.put_nowait(event)
