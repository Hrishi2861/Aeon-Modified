from asyncio import create_subprocess_exec, create_subprocess_shell
from os import environ

from aiofiles import open as aiopen
from aiofiles.os import makedirs, remove
from aiofiles.os import path as aiopath
from aioshutil import rmtree

from bot import (
    LOGGER,
    aria2,
    aria2_options,
    drives_ids,
    drives_names,
    extension_filter,
    index_urls,
    qbit_options,
    rss_dict,
    user_data,
    xnox_client,
)
from bot.helper.ext_utils.db_handler import database

from .aeon_client import TgClient
from .config_manager import Config


def update_qb_options():
    if not qbit_options:
        qbit_options.update(dict(xnox_client.app_preferences()))
        del qbit_options["listen_port"]
        for k in list(qbit_options.keys()):
            if k.startswith("rss"):
                del qbit_options[k]
        qbit_options["web_ui_password"] = "mltbmltb"
        xnox_client.app_set_preferences({"web_ui_password": "mltbmltb"})
    else:
        xnox_client.app_set_preferences(qbit_options)


def update_aria2_options():
    if not aria2_options:
        aria2_options.update(aria2.client.get_global_option())
    else:
        aria2.set_global_options(aria2_options)


async def load_settings():
    if not Config.DATABASE_URL:
        return
    await database.connect()
    if database.db is not None:
        BOT_ID = Config.BOT_TOKEN.split(":", 1)[0]
        config_file = Config.get_all()
        old_config = await database.db.settings.deployConfig.find_one(
            {"_id": BOT_ID},
        )
        if old_config is None:
            database.db.settings.deployConfig.replace_one(
                {"_id": BOT_ID},
                config_file,
                upsert=True,
            )
        else:
            del old_config["_id"]
        if old_config and old_config != config_file:
            await database.db.settings.deployConfig.replace_one(
                {"_id": BOT_ID},
                config_file,
                upsert=True,
            )
        else:
            config_dict = await database.db.settings.config.find_one(
                {"_id": BOT_ID},
                {"_id": 0},
            )
            if config_dict:
                Config.load_dict(config_dict)

        if pf_dict := await database.db.settings.files.find_one(
            {"_id": BOT_ID},
            {"_id": 0},
        ):
            for key, value in pf_dict.items():
                if value:
                    file_ = key.replace("__", ".")
                    async with aiopen(file_, "wb+") as f:
                        await f.write(value)

        if a2c_options := await database.db.settings.aria2c.find_one(
            {"_id": BOT_ID},
            {"_id": 0},
        ):
            aria2_options.update(a2c_options)

        if qbit_opt := await database.db.settings.qbittorrent.find_one(
            {"_id": BOT_ID},
            {"_id": 0},
        ):
            qbit_options.update(qbit_opt)

        if await database.db.users.find_one():
            rows = database.db.users.find({})
            async for row in rows:
                uid = row["_id"]
                del row["_id"]
                thumb_path = f"Thumbnails/{uid}.jpg"
                rclone_config_path = f"rclone/{uid}.conf"
                token_path = f"tokens/{uid}.pickle"
                if row.get("thumb"):
                    if not await aiopath.exists("Thumbnails"):
                        await makedirs("Thumbnails")
                    async with aiopen(thumb_path, "wb+") as f:
                        await f.write(row["thumb"])
                    row["thumb"] = thumb_path
                if row.get("rclone_config"):
                    if not await aiopath.exists("rclone"):
                        await makedirs("rclone")
                    async with aiopen(rclone_config_path, "wb+") as f:
                        await f.write(row["rclone_config"])
                    row["rclone_config"] = rclone_config_path
                if row.get("token_pickle"):
                    if not await aiopath.exists("tokens"):
                        await makedirs("tokens")
                    async with aiopen(token_path, "wb+") as f:
                        await f.write(row["token_pickle"])
                    row["token_pickle"] = token_path
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")

        if await database.db.rss[BOT_ID].find_one():
            rows = database.db.rss[BOT_ID].find({})
            async for row in rows:
                user_id = row["_id"]
                del row["_id"]
                rss_dict[user_id] = row
            LOGGER.info("Rss data has been imported from Database.")


async def save_settings():
    if database.db is None:
        return
    config_dict = Config.get_all()
    await database.db.settings.config.replace_one(
        {"_id": TgClient.ID},
        config_dict,
        upsert=True,
    )
    if await database.db.settings.aria2c.find_one({"_id": TgClient.ID}) is None:
        await database.db.settings.aria2c.update_one(
            {"_id": TgClient.ID},
            {"$set": aria2_options},
            upsert=True,
        )
    if await database.db.settings.qbittorrent.find_one({"_id": TgClient.ID}) is None:
        await database.save_qbit_settings()


async def update_variables():
    if (
        Config.LEECH_SPLIT_SIZE > TgClient.MAX_SPLIT_SIZE
        or Config.LEECH_SPLIT_SIZE == 2097152000
        or not Config.LEECH_SPLIT_SIZE
    ):
        Config.LEECH_SPLIT_SIZE = TgClient.MAX_SPLIT_SIZE

    Config.MIXED_LEECH = bool(Config.MIXED_LEECH and TgClient.IS_PREMIUM_USER)
    Config.USER_TRANSMISSION = bool(
        Config.USER_TRANSMISSION and TgClient.IS_PREMIUM_USER,
    )

    if Config.AUTHORIZED_CHATS:
        aid = Config.AUTHORIZED_CHATS.split()
        for id_ in aid:
            chat_id, *thread_ids = id_.split("|")
            chat_id = int(chat_id.strip())
            if thread_ids:
                thread_ids = [int(x.strip()) for x in thread_ids]
                user_data[chat_id] = {"is_auth": True, "thread_ids": thread_ids}
            else:
                user_data[chat_id] = {"is_auth": True}

    if Config.SUDO_USERS:
        aid = Config.SUDO_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {"is_sudo": True}

    if Config.EXTENSION_FILTER:
        fx = Config.EXTENSION_FILTER.split()
        for x in fx:
            x = x.lstrip(".")
            extension_filter.append(x.strip().lower())

    if Config.GDRIVE_ID:
        drives_names.append("Main")
        drives_ids.append(Config.GDRIVE_ID)
        index_urls.append(Config.INDEX_URL)

    if await aiopath.exists("list_drives.txt"):
        async with aiopen("list_drives.txt", "r+") as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.split()
                drives_ids.append(temp[1])
                drives_names.append(temp[0].replace("_", " "))
                if len(temp) > 2:
                    index_urls.append(temp[2])
                else:
                    index_urls.append("")


async def load_configurations():
    if not await aiopath.exists(".netrc"):
        async with aiopen(".netrc", "w"):
            pass
    await (await create_subprocess_shell("chmod 600 .netrc")).wait()
    await (await create_subprocess_shell("cp .netrc /root/.netrc")).wait()

    PORT = environ.get("PORT") or environ.get("BASE_URL_PORT", 80)
    await create_subprocess_shell(
        f"gunicorn web.wserver:app --bind 0.0.0.0:{PORT} --worker-class gevent",
    )

    if await aiopath.exists("accounts.zip"):
        if await aiopath.exists("accounts"):
            await rmtree("accounts")
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
        await (await create_subprocess_exec("chmod", "-R", "777", "accounts")).wait()
        await remove("accounts.zip")

    if not await aiopath.exists("accounts"):
        Config.USE_SERVICE_ACCOUNTS = False
