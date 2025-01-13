from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    gather,
    sleep,
)
from functools import partial
from io import BytesIO
from os import getcwd
from time import time

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from aiofiles.os import remove, rename
from aioshutil import rmtree
from pyrogram.filters import create
from pyrogram.handlers import MessageHandler

from bot import (
    LOGGER,
    aria2,
    aria2_options,
    drives_ids,
    drives_names,
    extension_filter,
    index_urls,
    intervals,
    task_dict,
)
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.core.startup import update_variables
from bot.helper.ext_utils.bot_utils import SetInterval, new_task, sync_to_async
from bot.helper.ext_utils.db_handler import database
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_file,
    send_message,
    update_status_message,
)

from .rss import add_job
from .search import initiate_search_tools

start = 0
state = "view"
handler_dict = {}
DEFAULT_VALUES = {
    "DOWNLOAD_DIR": "/usr/src/app/downloads/",
    "LEECH_SPLIT_SIZE": TgClient.MAX_SPLIT_SIZE,
    "RSS_DELAY": 600,
    "SEARCH_LIMIT": 0,
    "UPSTREAM_BRANCH": "main",
    "DEFAULT_UPLOAD": "rc",
}


async def get_buttons(key=None, edit_type=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.data_button("Config Variables", "botset var")
        buttons.data_button("Private Files", "botset private")
        buttons.data_button("Close", "botset close")
        msg = "Bot Settings:"
    elif edit_type is not None:
        if edit_type == "botvar":
            msg = ""
            buttons.data_button("Back", "botset var")
            if key not in ["TELEGRAM_HASH", "TELEGRAM_API", "OWNER_ID", "BOT_TOKEN"]:
                buttons.data_button("Default", f"botset resetvar {key}")
            buttons.data_button("Close", "botset close")
            if key in [
                "CMD_SUFFIX",
                "OWNER_ID",
                "USER_SESSION_STRING",
                "TELEGRAM_HASH",
                "TELEGRAM_API",
                "BOT_TOKEN",
                "DOWNLOAD_DIR",
                "SUDO_USERS",
                "AUTHORIZED_CHATS",
            ]:
                msg += "Restart required for this edit to take effect! You will not see the changes in bot vars, the edit will be in database only!\n\n"
            msg += f"Send a valid value for {key}. Current value is '{Config.get(key)}'. Timeout: 60 sec"
    elif key == "var":
        conf_dict = Config.get_all()
        for k in list(conf_dict.keys())[start : 10 + start]:
            if (
                key
                in [
                    "CMD_SUFFIX",
                    "OWNER_ID",
                    "USER_SESSION_STRING",
                    "TELEGRAM_HASH",
                    "TELEGRAM_API",
                    "BOT_TOKEN",
                    "DOWNLOAD_DIR",
                    "SUDO_USERS",
                    "AUTHORIZED_CHATS",
                ]
                and not Config.DATABASE_URL
            ):
                continue
            if k == "DATABASE_URL" and state != "view":
                continue
            buttons.data_button(k, f"botset botvar {k}")
        if state == "view":
            buttons.data_button("Edit", "botset edit var")
        else:
            buttons.data_button("View", "botset view var")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(conf_dict), 10):
            buttons.data_button(
                f"{int(x / 10)}",
                f"botset start var {x}",
                position="footer",
            )
        msg = f"Config Variables | Page: {int(start / 10)} | State: {state}"
    elif key == "private":
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        msg = """Send private file: config.py, token.pickle, rclone.conf, accounts.zip, list_drives.txt, cookies.txt, .netrc or any other private file!
To delete private file send only the file name as text message.
Note: Changing .netrc will not take effect for aria2c until restart.
Timeout: 60 sec"""
    button = buttons.build_menu(1) if key is None else buttons.build_menu(2)
    return msg, button


async def update_buttons(message, key=None, edit_type=None):
    msg, button = await get_buttons(key, edit_type)
    await edit_message(message, msg, button)


@new_task
async def edit_variable(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
        if key == "INCOMPLETE_TASK_NOTIFIER" and Config.DATABASE_URL:
            await database.trunc_table("tasks")
    elif key == "DOWNLOAD_DIR":
        if not value.endswith("/"):
            value += "/"
    elif key == "TORRENT_TIMEOUT":
        value = int(value)
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": f"{value}"},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = f"{value}"
    elif key == "LEECH_SPLIT_SIZE":
        value = min(int(value), TgClient.MAX_SPLIT_SIZE)
    elif key == "EXTENSION_FILTER":
        fx = value.split()
        extension_filter.clear()
        extension_filter.extend(["aria2", "!qB"])
        for x in fx:
            x = x.lstrip(".")
            extension_filter.append(x.strip().lower())
    elif key == "GDRIVE_ID":
        if drives_names and drives_names[0] == "Main":
            drives_ids[0] = value
        else:
            drives_ids.insert(0, value)
    elif key == "INDEX_URL":
        if drives_names and drives_names[0] == "Main":
            index_urls[0] = value
        else:
            index_urls.insert(0, value)
    elif value.isdigit():
        value = int(value)
    elif (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        value = eval(value)
    if key not in [
        "CMD_SUFFIX",
        "OWNER_ID",
        "USER_SESSION_STRING",
        "TELEGRAM_HASH",
        "TELEGRAM_API",
        "BOT_TOKEN",
        "DOWNLOAD_DIR",
        "SUDO_USERS",
        "AUTHORIZED_CHATS",
    ]:
        Config.set(key, value)
    await update_buttons(pre_message, "var")
    await delete_message(message)
    await database.update_config({key: value})
    if key in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
        await initiate_search_tools()
    elif key in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
        await start_from_queued()
    elif key in [
        "RCLONE_SERVE_URL",
        "RCLONE_SERVE_PORT",
        "RCLONE_SERVE_USER",
        "RCLONE_SERVE_PASS",
    ]:
        await rclone_serve_booter()
    elif key == "RSS_DELAY":
        add_job()


@new_task
async def update_private_file(_, message, pre_message):
    handler_dict[message.chat.id] = False
    if not message.media and (file_name := message.text):
        fn = file_name.rsplit(".zip", 1)[0]
        if await aiopath.isfile(fn) and file_name != "config.py":
            await remove(fn)
        if fn == "accounts":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            Config.USE_SERVICE_ACCOUNTS = False
            await database.update_config({"USE_SERVICE_ACCOUNTS": False})
        elif file_name in [".netrc", "netrc"]:
            await (await create_subprocess_exec("touch", ".netrc")).wait()
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (
                await create_subprocess_exec("cp", ".netrc", "/root/.netrc")
            ).wait()
        await delete_message(message)
    elif doc := message.document:
        file_name = doc.file_name
        fpath = f"{getcwd()}/{file_name}"
        if await aiopath.exists(fpath):
            await remove(fpath)
        await message.download(file_name=fpath)
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            await (
                await create_subprocess_exec(
                    "7z",
                    "x",
                    "-o.",
                    "-aoa",
                    "accounts.zip",
                    "accounts/*.json",
                )
            ).wait()
            await (
                await create_subprocess_exec("chmod", "-R", "777", "accounts")
            ).wait()
        elif file_name == "list_drives.txt":
            drives_ids.clear()
            drives_names.clear()
            index_urls.clear()
            if Config.GDRIVE_ID:
                drives_names.append("Main")
                drives_ids.append(Config.GDRIVE_ID)
                index_urls.append(Config.INDEX_URL)
            async with aiopen("list_drives.txt", "r+") as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().split()
                    drives_ids.append(temp[1])
                    drives_names.append(temp[0].replace("_", " "))
                    if len(temp) > 2:
                        index_urls.append(temp[2])
                    else:
                        index_urls.append("")
        elif file_name in [".netrc", "netrc"]:
            if file_name == "netrc":
                await rename("netrc", ".netrc")
                file_name = ".netrc"
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (
                await create_subprocess_exec("cp", ".netrc", "/root/.netrc")
            ).wait()
        elif file_name == "config.py":
            await load_config()
        await delete_message(message)
    if file_name == "rclone.conf":
        await rclone_serve_booter()
    await update_buttons(pre_message)
    await database.update_private_file(file_name)
    if await aiopath.exists("accounts.zip"):
        await remove("accounts.zip")


async def event_handler(client, query, pfunc, rfunc, document=False):
    chat_id = query.message.chat.id
    handler_dict[chat_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(
            user.id == query.from_user.id
            and event.chat.id == chat_id
            and (event.text or (event.document and document)),
        )

    handler = client.add_handler(
        MessageHandler(pfunc, filters=create(event_filter)),
        group=-1,
    )
    while handler_dict[chat_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[chat_id] = False
            await rfunc()
    client.remove_handler(*handler)


@new_task
async def edit_bot_settings(client, query):
    data = query.data.split()
    message = query.message
    handler_dict[message.chat.id] = False
    if data[1] == "close":
        await query.answer()
        await delete_message(message.reply_to_message)
        await delete_message(message)
    elif data[1] == "back":
        await query.answer()
        globals()["start"] = 0
        await update_buttons(message, None)
    elif data[1] == "var":
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == "resetvar":
        await query.answer()
        value = ""
        if data[2] in DEFAULT_VALUES:
            value = DEFAULT_VALUES[data[2]]
        elif data[2] == "EXTENSION_FILTER":
            extension_filter.clear()
            extension_filter.extend(["aria2", "!qB"])
        elif data[2] == "TORRENT_TIMEOUT":
            downloads = await sync_to_async(aria2.get_downloads)
            for download in downloads:
                if not download.is_complete:
                    try:
                        await sync_to_async(
                            aria2.client.change_option,
                            download.gid,
                            {"bt-stop-timeout": "0"},
                        )
                    except Exception as e:
                        LOGGER.error(e)
            aria2_options["bt-stop-timeout"] = "0"
            await database.update_aria2("bt-stop-timeout", "0")
        elif data[2] == "BASE_URL":
            await (
                await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")
            ).wait()
        elif data[2] == "BASE_URL_PORT":
            value = 80
            if Config.BASE_URL:
                await (
                    await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")
                ).wait()
                await create_subprocess_shell(
                    "gunicorn web.wserver:app --bind 0.0.0.0:80 --worker-class gevent",
                )
        elif data[2] == "GDRIVE_ID":
            if drives_names and drives_names[0] == "Main":
                drives_names.pop(0)
                drives_ids.pop(0)
                index_urls.pop(0)
        elif data[2] == "INDEX_URL":
            if drives_names and drives_names[0] == "Main":
                index_urls[0] = ""
        elif data[2] == "INCOMPLETE_TASK_NOTIFIER":
            await database.trunc_table("tasks")
        Config.set(data[2], value)
        await update_buttons(message, "var")
        if data[2] == "DATABASE_URL":
            await database.disconnect()
        await database.update_config({data[2]: value})
        if data[2] in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
            await initiate_search_tools()
        elif data[2] in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
            await start_from_queued()
        elif data[2] in [
            "RCLONE_SERVE_URL",
            "RCLONE_SERVE_PORT",
            "RCLONE_SERVE_USER",
            "RCLONE_SERVE_PASS",
        ]:
            await rclone_serve_booter()
    elif data[1] == "private":
        await query.answer()
        await update_buttons(message, data[1])
        pfunc = partial(update_private_file, pre_message=message)
        rfunc = partial(update_buttons, message)
        await event_handler(client, query, pfunc, rfunc, True)
    elif data[1] == "botvar" and state == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_variable, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, "var")
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "botvar" and state == "view":
        value = f"{Config.get(data[2])}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "edit":
        await query.answer()
        globals()["state"] = "edit"
        await update_buttons(message, data[2])
    elif data[1] == "view":
        await query.answer()
        globals()["state"] = "view"
        await update_buttons(message, data[2])
    elif data[1] == "start":
        await query.answer()
        if start != int(data[3]):
            globals()["start"] = int(data[3])
            await update_buttons(message, data[2])


@new_task
async def send_bot_settings(_, message):
    handler_dict[message.chat.id] = False
    msg, button = await get_buttons()
    globals()["start"] = 0
    await send_message(message, msg, button)


async def load_config():
    Config.load()
    drives_ids.clear()
    drives_names.clear()
    index_urls.clear()
    await update_variables()

    if not await aiopath.exists("accounts"):
        Config.USE_SERVICE_ACCOUNTS = False

    if len(task_dict) != 0 and (st := intervals["status"]):
        for key, intvl in list(st.items()):
            intvl.cancel()
            intervals["status"][key] = SetInterval(
                1,
                update_status_message,
                key,
            )

    downloads = aria2.get_downloads()
    if not Config.TORRENT_TIMEOUT:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": "0"},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = "0"
        await database.update_aria2("bt-stop-timeout", "0")
    else:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(
                        aria2.client.change_option,
                        download.gid,
                        {"bt-stop-timeout": Config.TORRENT_TIMEOUT},
                    )
                except Exception as e:
                    LOGGER.error(e)
        aria2_options["bt-stop-timeout"] = Config.TORRENT_TIMEOUT
        await database.update_aria2("bt-stop-timeout", Config.TORRENT_TIMEOUT)

    if not Config.INCOMPLETE_TASK_NOTIFIER:
        await database.trunc_table("tasks")

    await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
    if Config.BASE_URL:
        await create_subprocess_shell(
            f"gunicorn web.wserver:app --bind 0.0.0.0:{Config.BASE_URL_PORT} --worker-class gevent",
        )

    if Config.DATABASE_URL:
        await database.connect()
        config_dict = Config.get_all()
        await database.update_config(config_dict)
    else:
        await database.disconnect()
    await gather(initiate_search_tools(), start_from_queued(), rclone_serve_booter())
    add_job()
