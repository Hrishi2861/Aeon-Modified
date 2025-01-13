# ruff: noqa: E402
from asyncio import gather
from signal import SIGINT, signal

from pyrogram.filters import regex
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import BotCommand

from . import LOGGER, bot_loop
from .core.config_manager import Config
from .core.startup import (
    load_configurations,
    load_settings,
    save_settings,
    update_aria2_options,
    update_qb_options,
    update_variables,
)

# Initialize Configurations
Config.load()
bot_loop.run_until_complete(load_settings())


from .core.aeon_client import TgClient
from .core.handlers import add_handlers
from .helper.ext_utils.bot_utils import create_help_buttons, new_task, sync_to_async
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_message,
)
from .modules import (
    get_packages_version,
    initiate_search_tools,
    restart_notification,
)

# Commands and Descriptions
COMMANDS = {
    "MirrorCommand": "- Start mirroring",
    "LeechCommand": "- Start leeching",
    "YtdlCommand": "- Mirror yt-dlp supported link",
    "YtdlLeechCommand": "- Leech through yt-dlp supported link",
    "CloneCommand": "- Copy file/folder to Drive",
    "MediaInfoCommand": "- Get mediainfo",
    "ForceStartCommand": "- Start task from queue",
    "CountCommand": "- Count file/folder on Google Drive",
    "ListCommand": "- Search in Drive",
    "SearchCommand": "- Search in Torrent",
    "UserSetCommand": "- User settings",
    "StatusCommand": "- Get mirror status message",
    "StatsCommand": "- Check Bot & System stats",
    "CancelAllCommand": "- Cancel all tasks added by you to the bot",
    "HelpCommand": "- Get detailed help",
    "SpeedTest": "- Get speedtest result",
    "BotSetCommand": "- [ADMIN] Open Bot settings",
    "LogCommand": "- [ADMIN] View log",
    "RestartCommand": "- [ADMIN] Restart the bot",
    "RestartSessionsCommand": "- [ADMIN] Restart the session instead of the bot",
}


# Restart Sessions Handler
@new_task
async def restart_sessions_confirm(_, query):
    data = query.data.split()
    message = query.message

    if data[1] == "confirm":
        reply_to = message.reply_to_message
        restart_message = await send_message(reply_to, "Restarting Session(s)...")
        await delete_message(message)
        await TgClient.reload()
        add_handlers()
        TgClient.bot.add_handler(
            CallbackQueryHandler(
                restart_sessions_confirm,
                filters=regex("^sessionrestart") & CustomFilters.sudo,
            ),
        )
        await edit_message(restart_message, "Session(s) Restarted Successfully!")
    else:
        await delete_message(message)


# Setup Commands
COMMAND_OBJECTS = [
    BotCommand(
        getattr(BotCommands, cmd)[0]
        if isinstance(getattr(BotCommands, cmd), list)
        else getattr(BotCommands, cmd),
        description,
    )
    for cmd, description in COMMANDS.items()
]


# Set Bot Commands
async def set_commands():
    if Config.SET_COMMANDS:
        await TgClient.bot.set_bot_commands(COMMAND_OBJECTS)


# Main Function
async def main():
    await gather(TgClient.start_bot(), TgClient.start_user())
    await gather(load_configurations(), update_variables())
    await gather(
        sync_to_async(update_qb_options),
        sync_to_async(update_aria2_options),
        set_commands(),
    )
    await gather(
        save_settings(),
        sync_to_async(clean_all),
        initiate_search_tools(),
        get_packages_version(),
        restart_notification(),
        telegraph.create_account(),
        rclone_serve_booter(),
        sync_to_async(start_aria2_listener, wait=False),
    )
    create_help_buttons()
    add_handlers()
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            restart_sessions_confirm,
            filters=regex("^sessionrestart") & CustomFilters.sudo,
        ),
    )
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)


# Run Bot
bot_loop.run_until_complete(main())
bot_loop.run_forever()
