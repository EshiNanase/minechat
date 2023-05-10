import asyncio
import json
import socket
import sys
import gui
import argparse
import aiofiles
from datetime import datetime
from functools import partial
import tools
import logging
from anyio import create_task_group, ExceptionGroup
from tkinter import messagebox
from async_timeout import timeout

WATCHDOG_TIMEOUT = 60
MAX_RECONNECT_ATTEMPTS = 5
CHECK_CONN_TIMEOUT = 30

watchdog_logger = logging.getLogger('watchdog_logger')


async def save_message(text):

    async with aiofiles.open('history.txt', 'a', encoding='utf-8') as file:
        await file.write(f'[{datetime.now().strftime("%d.%m %H:%M")}] {text}')


async def write_down_account_info(account_info):
    async with aiofiles.open('account.txt', 'w', encoding='utf-8') as file:
        await file.write(account_info)


async def register(reader, writer, sending_queue, messages_queue, status_updates_queue):

    messages_queue.put_nowait('Введите ник, который бы хотели использовать')
    username = await sending_queue.get()
    writer.write(f'{username}\n'.encode())
    await writer.drain()

    response = await reader.readline()
    response_decoded = response.decode()
    logging.debug(response_decoded)
    await write_down_account_info(response_decoded)

    tools.set_username(username, status_updates_queue)
    messages_queue.put_nowait(f'Добро пожаловать, {username}!')
    messages_queue.put_nowait('Ваша информация об аккаунте была записана в account.txt!')

    writer.write('\n'.encode())
    await writer.drain()
    await reader.readline()


async def login(reader, writer, hash, sending_queue, messages_queue, status_updates_queue):

    writer.write(f'{hash}\n'.encode())
    await writer.drain()
    response = await reader.readline()
    response_decoded = response.decode()

    logging.debug(response_decoded)

    if 'null' in response_decoded:
        messagebox.showinfo('Неверный хеш!', 'Неверный хеш, дружище, отправляй ник!')
        await register(reader, writer, sending_queue, messages_queue, status_updates_queue)
        return

    writer.write('\n'.encode())
    await writer.drain()
    await reader.readline()

    username = json.loads(response_decoded)['nickname']
    tools.set_username(username, status_updates_queue)
    messages_queue.put_nowait(f'Добро пожаловать, {username}!')


async def authorize(reader, writer, sending_queue, messages_queue, status_updates_queue, watchdog_queue):

    response = await reader.readline()
    response_decoded = response.decode()
    logging.debug(response_decoded)

    messages_queue.put_nowait('Добро пожаловать в чат майнкрафтера!')
    messages_queue.put_nowait('Есть ли у вас хеш? Если да, то отправьте его, если нет - напишите "нет"')
    watchdog_queue.put_nowait('Prompt before auth')

    while True:
        message = await sending_queue.get()

        if 'нет' == message.lower():
            writer.write('\n'.encode())
            await writer.drain()
            await reader.readline()
            await register(reader, writer, sending_queue, messages_queue, status_updates_queue)
            break
        else:
            await login(reader, writer, message, sending_queue, messages_queue, status_updates_queue)
            break
    watchdog_queue.put_nowait('Authorization done')


async def read_old_messages(messages_queue):

    try:
        async with aiofiles.open('history.txt', 'r', encoding='utf-8') as file:
            data = await file.readlines()

        for line in data:
            messages_queue.put_nowait(line)

    except FileNotFoundError:
        pass


async def write_in_chat(open_writer_socket_function,
                        authorize_function,
                        sending_queue,
                        watchdog_queue,
                        status_updates_queue):

    async with open_writer_socket_function() as streamers:
        reader, writer = streamers

        while True:

            if not tools.AUTHORIZED:
                await authorize_function(reader, writer)
                tools.AUTHORIZED = True
                status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)

            else:

                message = await sending_queue.get()
                message = message.replace('\n', '')
                writer.write(f'{message}\n\n'.encode())
                watchdog_queue.put_nowait('Message sent')
                await writer.drain()
                response = await reader.readline()
                logging.debug(response.decode())


async def read_chat(open_reader_socket_function, messages_queue, status_updates_queue, watchdog_queue):

    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)

    async with open_reader_socket_function() as streamers:
        reader = streamers[0]

        while True:

            if tools.AUTHORIZED:
                data = await reader.readline()
                data_decoded = data.decode()
                watchdog_queue.put_nowait('New message in chat')
                messages_queue.put_nowait(f'[{datetime.now().strftime("%d.%m %H:%M")}] {data_decoded}')
                await save_message(f'{data_decoded}')

            else:
                await asyncio.sleep(1)


async def watch_for_connection(watchdog_queue):

    while True:
        async with timeout(WATCHDOG_TIMEOUT) as time_out:
            try:
                msg = await watchdog_queue.get()
                watchdog_logger.debug(f'[{datetime.now().strftime("%d.%m %H:%M")}] Connection is alive. {msg}')
            finally:
                if time_out.expired:
                    watchdog_logger.debug(f'[{datetime.now().strftime("%d.%m %H:%M")}] Timeout is elapsed.')
                    raise ConnectionError


async def check_the_connection(open_writer_socket_function, messages_queue, status_updates_queue):

    attempts = 0
    while True:
        async with timeout(CHECK_CONN_TIMEOUT) as time_out:
            try:
                async with open_writer_socket_function() as streamers:

                    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
                    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)

                    reader, writer = streamers
                    writer.write('\n\n'.encode())
                    await writer.drain()
                    await reader.readline()
                    await asyncio.sleep(1)

            except (socket.gaierror, OSError, ExceptionGroup):
                status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
                status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
                messages_queue.put_nowait('Соединение нарушено!')
                if attempts < MAX_RECONNECT_ATTEMPTS:
                    messages_queue.put_nowait('Попытка восстановить соединение...')
                    await asyncio.sleep(5)
                    attempts += 1
                else:
                    messages_queue.put_nowait('Невозможно установить соединение!')
                    messagebox.showerror('Ошибка!', 'Соединение с сервером нарушено!')
                    raise RuntimeError('Соединение с сервером нарушено!')
            finally:
                if time_out.expired:
                    raise ConnectionError


async def handle_connection(check_the_connection_function,
                            watch_for_connection_function,
                            read_chat_function,
                            write_in_chat_function,
                            authorize_function,
                            open_reader_socket_function,
                            open_writer_socket_function):

    await save_message('Установлено соединение!\n')

    async with create_task_group() as task_group:
        task_group.start_soon(check_the_connection_function, open_writer_socket_function)
        task_group.start_soon(read_chat_function, open_reader_socket_function)
        task_group.start_soon(write_in_chat_function, open_writer_socket_function, authorize_function)
        task_group.start_soon(watch_for_connection_function)


async def main(args):

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    read_chat_function = partial(
        read_chat,
        messages_queue=messages_queue,
        watchdog_queue=watchdog_queue,
        status_updates_queue=status_updates_queue
    )
    write_in_chat_function = partial(
        write_in_chat,
        sending_queue=sending_queue,
        watchdog_queue=watchdog_queue,
        status_updates_queue=status_updates_queue
    )
    authorize_function = partial(
        authorize,
        sending_queue=sending_queue,
        messages_queue=messages_queue,
        status_updates_queue=status_updates_queue,
        watchdog_queue=watchdog_queue
    )
    open_reader_socket_function = partial(
        tools.open_socket,
        host=args.host,
        port=args.reading_port
    )
    open_writer_socket_function = partial(
        tools.open_socket,
        host=args.host,
        port=args.writing_port
    )
    watch_for_connection_function = partial(
        watch_for_connection,
        watchdog_queue=watchdog_queue
    )
    check_the_connection_function = partial(
        check_the_connection,
        messages_queue=messages_queue,
        status_updates_queue=status_updates_queue
    )

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    watchdog_logger.setLevel(level=logging.DEBUG)

    await read_old_messages(messages_queue)

    async with create_task_group() as task_group:

        task_group.start_soon(
            gui.draw,
            messages_queue,
            sending_queue,
            status_updates_queue),

        task_group.start_soon(
            handle_connection,
            check_the_connection_function,
            watch_for_connection_function,
            read_chat_function,
            write_in_chat_function,
            authorize_function,
            open_reader_socket_function,
            open_writer_socket_function),


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='указать хост', default='minechat.dvmn.org')
    parser.add_argument('--writing_port', type=int, help='указать порт для чтения сообщений из чата', default=5050)
    parser.add_argument('--reading_port', type=int, help='указать порт для отправки сообщений в чат', default=5000)
    parser.add_argument('--debug', action='store_true', help='указать включен/выключен дебаг сообщений в терминал')
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        sys.stderr.write("Чат завершен\n")
    except gui.TkAppClosed:
        sys.stderr.write("Вы вышли из чата\n")
