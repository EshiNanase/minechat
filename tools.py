import asyncio
from contextlib import asynccontextmanager
import time
from tkinter import messagebox
from gui import ReadConnectionStateChanged, SendingConnectionStateChanged, NicknameReceived

AUTHORIZED = False
MAX_RECONNECT_ATTEMPTS = 3


@asynccontextmanager
async def open_reader_socket(host, port, status_updates_queue, messages_queue):
    writer = None
    attempts = 0

    try:
        status_updates_queue.put_nowait(ReadConnectionStateChanged.ESTABLISHED)
        reader, writer = await asyncio.open_connection(host, port)
        yield reader

    except ConnectionError:
        status_updates_queue.put_nowait(ReadConnectionStateChanged.INITIATED)
        messages_queue.put_nowait('Соединение нарушено!')
        if attempts < MAX_RECONNECT_ATTEMPTS:
            messages_queue.put_nowait('Попытка восстановить соединение...')
            time.sleep(15)
            attempts += 1
        else:
            status_updates_queue.put_nowait(ReadConnectionStateChanged.CLOSED)
            messages_queue.put_nowait('Невозможно установить соединение!')
            messagebox.showerror('Ошибка!', 'Соединение с сервером нарушено!')
            raise RuntimeError('Соединение с сервером нарушено!')

    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None


@asynccontextmanager
async def open_writer_socket(host, port, status_updates_queue, messages_queue):
    writer = None
    attempts = 0

    try:
        status_updates_queue.put_nowait(SendingConnectionStateChanged.ESTABLISHED)
        reader, writer = await asyncio.open_connection(host, port)
        yield (reader, writer)

    except ConnectionError:
        status_updates_queue.put_nowait(SendingConnectionStateChanged.INITIATED)
        messages_queue.put_nowait('Соединение нарушено!')
        if attempts < MAX_RECONNECT_ATTEMPTS:
            messages_queue.put_nowait('Попытка восстановить соединение...')
            time.sleep(15)
            attempts += 1
        else:
            status_updates_queue.put_nowait(SendingConnectionStateChanged.CLOSED)
            messages_queue.put_nowait('Невозможно установить соединение!')
            messagebox.showerror('Ошибка!', 'Соединение с сервером нарушено!')
            raise RuntimeError('Соединение с сервером нарушено!')

    finally:
        writer.close() if writer else None
        await writer.wait_closed() if writer else None


def set_username(username, status_updates_queue):

    event = NicknameReceived(username)
    status_updates_queue.put_nowait(event)
