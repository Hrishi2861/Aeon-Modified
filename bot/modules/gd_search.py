from bot import LOGGER, user_data
from bot.helper.ext_utils.bot_utils import (
    get_telegraph_list,
    new_task,
    sync_to_async,
)
from bot.helper.mirror_leech_utils.gdrive_utils.search import GoogleDriveSearch
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import edit_message, send_message


async def list_buttons(user_id, is_recursive=True, user_token=False):
    buttons = ButtonMaker()
    buttons.data_button(
        "Folders",
        f"list_types {user_id} folders {is_recursive} {user_token}",
    )
    buttons.data_button(
        "Files",
        f"list_types {user_id} files {is_recursive} {user_token}",
    )
    buttons.data_button(
        "Both",
        f"list_types {user_id} both {is_recursive} {user_token}",
    )
    buttons.data_button(
        f"Recursive: {is_recursive}",
        f"list_types {user_id} rec {is_recursive} {user_token}",
    )
    buttons.data_button(
        f"User Token: {user_token}",
        f"list_types {user_id} ut {is_recursive} {user_token}",
    )
    buttons.data_button("Cancel", f"list_types {user_id} cancel")
    return buttons.build_menu(2)


async def _list_drive(key, message, item_type, is_recursive, user_token, user_id):
    LOGGER.info(f"listing: {key}")
    if user_token:
        user_dict = user_data.get(user_id, {})
        target_id = user_dict.get("gdrive_id", "") or ""
        LOGGER.info(target_id)
    else:
        target_id = ""
    telegraph_content, contents_no = await sync_to_async(
        GoogleDriveSearch(is_recursive=is_recursive, item_type=item_type).drive_list,
        key,
        target_id,
        user_id,
    )
    if telegraph_content:
        try:
            button = await get_telegraph_list(telegraph_content)
        except Exception as e:
            await edit_message(message, e)
            return
        msg = f"<b>Found {contents_no} result for <i>{key}</i></b>"
        await edit_message(message, msg, button)
    else:
        await edit_message(message, f"No result found for <i>{key}</i>")


@new_task
async def select_type(_, query):
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(maxsplit=1)[1].strip()
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="Not Yours!", show_alert=True)
    if data[2] == "rec":
        await query.answer()
        is_recursive = not bool(eval(data[3]))
        buttons = await list_buttons(user_id, is_recursive, eval(data[4]))
        return await edit_message(message, "Choose list options:", buttons)
    if data[2] == "ut":
        await query.answer()
        user_token = not bool(eval(data[4]))
        buttons = await list_buttons(user_id, eval(data[3]), user_token)
        return await edit_message(message, "Choose list options:", buttons)
    if data[2] == "cancel":
        await query.answer()
        return await edit_message(message, "list has been canceled!")
    await query.answer()
    item_type = data[2]
    is_recursive = eval(data[3])
    user_token = eval(data[4])
    await edit_message(message, f"<b>Searching for <i>{key}</i></b>")
    await _list_drive(key, message, item_type, is_recursive, user_token, user_id)
    return None


@new_task
async def gdrive_search(_, message):
    if len(message.text.split()) == 1:
        return await send_message(message, "Send a search key along with command")
    user_id = message.from_user.id
    buttons = await list_buttons(user_id)
    await send_message(message, "Choose list options:", buttons)
    return None
