import asyncio
import time
import gui
import argparse
import aiofiles
from datetime import datetime
from functools import partial
from context_manager import open_socket

MAX_RECONNECT_ATTEMPTS = 3


async def save_message(text):

    async with aiofiles.open('history.txt', 'a', encoding='utf-8') as file:
        await file.write(f'[{datetime.now().strftime("%d.%m %H:%M")}] {text}')


async def read_old_messages(messages_queue):

    try:
        async with aiofiles.open('history.txt', 'r', encoding='utf-8') as file:
            data = await file.readlines()

        for line in data:
            messages_queue.put_nowait(line)

    except FileNotFoundError:
        pass


# async def write_in_chat(writer, sending_queue):
#


async def read_chat(reader, messages_queue):

    await save_message('Установлено соединение!\n')
    try:
        while True:
            data = await reader.readline()
            data_decoded = data.decode()
            messages_queue.put_nowait(f'[{datetime.now().strftime("%d.%m %H:%M")}] {data_decoded}')
            await save_message(f'{data_decoded}')

    except ConnectionError:
        await save_message('Соединение прервано!')


async def connect_endlessly(read_chat_function, open_socket_function):
    attempts = 0
    while True:

        try:
            async with open_socket_function() as streamers:
                reader = streamers[0]
                await read_chat_function(reader)

        except ConnectionError:
            await save_message('Соединение нарушено!')
            if attempts < MAX_RECONNECT_ATTEMPTS:
                await save_message('Попытка восстановить соединение...')
                time.sleep(15)
                attempts += 1
            else:
                await save_message('Невозможно установить соединение!')
                raise RuntimeError('Невозможно установить соединение')


async def main(args):

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    open_socket_function = partial(open_socket, host=args.host, port=args.reading_port)
    read_chat_function = partial(read_chat, messages_queue=messages_queue)

    await read_old_messages(messages_queue)

    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        connect_endlessly(read_chat_function, open_socket_function)
    )

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='указать хост', default='minechat.dvmn.org')
    parser.add_argument('--writing_port', type=int, help='указать порт для чтения сообщений из чата', default=5050)
    parser.add_argument('--reading_port', type=int, help='указать порт для отправки сообщений в чат', default=5000)
    parser.add_argument('--hash', help='указать хеш')
    parser.add_argument('--debug', action='store_true', help='указать включен/выключен дебаг сообщений в окно')
    args = parser.parse_args()

    asyncio.run(main(args))
