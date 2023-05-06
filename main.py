import asyncio
import json
import time
import gui
import argparse
import aiofiles
from datetime import datetime
from functools import partial
import tools
import logging
from anyio import sleep, create_task_group, run

MAX_RECONNECT_ATTEMPTS = 3
_authorized = False


async def save_message(text):

    async with aiofiles.open('history.txt', 'a', encoding='utf-8') as file:
        await file.write(f'[{datetime.now().strftime("%d.%m %H:%M")}] {text}')


async def write_down_account_info(account_info):
    async with aiofiles.open('account.txt', 'w', encoding='utf-8') as file:
        await file.write(account_info)


async def register(reader, writer, sending_queue, messages_queue):

    writer.write('\n'.encode())
    await writer.drain()
    response = await reader.readline()
    logging.debug(response.decode())

    messages_queue.put_nowait('Введите ник, который бы хотели использовать')
    while True:
        username = await sending_queue.get()
        break
    writer.write(f'{username}\n'.encode())
    await writer.drain()

    response = await reader.readline()
    response_decoded = response.decode()
    logging.debug(response_decoded)
    await write_down_account_info(response_decoded)

    username = json.loads(response_decoded)["nickname"]

    messages_queue.put_nowait(f'Добро пожаловать, {username}!')
    messages_queue.put_nowait('Ваша информация об аккаунте была записана в account.txt!')

    writer.write(f'\n'.encode())
    await writer.drain()
    await reader.readline()

    return username


async def authorize(reader, writer, sending_queue, messages_queue, hash):

    response = await reader.readline()
    response_decoded = response.decode()
    logging.debug(response_decoded)

        # if hash:
        #     await login(reader, writer, hash)
        # else:
        #     await register(reader, writer)

    await register(reader, writer, sending_queue, messages_queue)


async def read_old_messages(messages_queue):

    try:
        async with aiofiles.open('history.txt', 'r', encoding='utf-8') as file:
            data = await file.readlines()

        for line in data:
            messages_queue.put_nowait(line)

    except FileNotFoundError:
        pass


async def write_in_chat(open_writer_socket_function, authorize_function, sending_queue):

    global _authorized

    async with open_writer_socket_function() as streamers:
        reader, writer = streamers

        while True:

            if not tools.AUTHORIZED:
                await authorize_function(reader, writer)
                tools.AUTHORIZED = True

            message = await sending_queue.get()
            message = message.replace('\n', '')
            writer.write(f'{message}\n\n'.encode())
            await writer.drain()
            response = await reader.readline()
            logging.debug(response.decode())


async def read_chat(open_reader_socket_function, messages_queue):

    if not tools.AUTHORIZED:

        async with open_reader_socket_function() as reader:

            while True:
                data = await reader.readline()
                if data:
                    data_decoded = data.decode()
                    messages_queue.put_nowait(f'[{datetime.now().strftime("%d.%m %H:%M")}] {data_decoded}')
                    await save_message(f'{data_decoded}')


async def connect_endlessly(read_chat_function, write_in_chat_function, authorize_function, open_reader_socket_function, open_writer_socket_function):
    attempts = 0

    await save_message('Установлено соединение!\n')
    while True:

        try:
            async with create_task_group() as task_group:
                task_group.start_soon(read_chat_function, open_reader_socket_function)
                task_group.start_soon(write_in_chat_function, open_writer_socket_function, authorize_function)

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

    read_chat_function = partial(read_chat, messages_queue=messages_queue)
    write_in_chat_function = partial(write_in_chat, sending_queue=sending_queue)
    authorize_function = partial(authorize, sending_queue=sending_queue, messages_queue=messages_queue, hash=args.hash)
    open_reader_socket_function = partial(tools.open_reader_socket, host=args.host, port=args.reading_port)
    open_writer_socket_function = partial(tools.open_writer_socket, host=args.host, port=args.writing_port)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    await read_old_messages(messages_queue)

    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        connect_endlessly(read_chat_function, write_in_chat_function, authorize_function, open_reader_socket_function, open_writer_socket_function)
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
