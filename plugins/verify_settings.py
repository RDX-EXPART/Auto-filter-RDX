# Admin menu to choose how long one user verification stays valid.
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import ADMINS, VERIFY
from utils import VERIFY_HOUR_OPTIONS, get_verify_hours, set_verify_hours


async def _menu_markup():
    current = await get_verify_hours()
    buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if hours == current else ''}{hours} Hours",
            callback_data=f"vtime#{hours}",
        )
        for hours in VERIFY_HOUR_OPTIONS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("❌ Close", callback_data="vtime#close")])
    return InlineKeyboardMarkup(rows)


async def _menu_text():
    current = await get_verify_hours()
    status = "ON ✅" if VERIFY else "OFF ❌ (set VERIFY=True in config to enable)"
    return (
        "<b>🔐 Verification Settings</b>\n\n"
        f"• Verification system: <b>{status}</b>\n"
        f"• Current validity: <b>{current} hours</b>\n\n"
        "Choose how long a user stays verified after completing the verification link.\n"
        "<i>Users who are already verified keep their old expiry; the new time applies "
        "to the next verification. Premium users never need to verify.</i>"
    )


# group=-1 so the catch-all text handlers in pm_filter.py (group 0) cannot swallow the command
@Client.on_message(
    filters.command(["set_verify_time", "verify_setting", "verify_settings", "setverify"])
    & filters.user(ADMINS),
    group=-1,
)
async def verify_time_menu(client, message):
    await message.reply_text(await _menu_text(), reply_markup=await _menu_markup(), quote=True)
    raise StopPropagation


# group=-1 so this runs before the catch-all callback handler in pm_filter.py
@Client.on_callback_query(filters.regex(r"^vtime#"), group=-1)
async def verify_time_callback(client, query):
    if query.from_user.id not in ADMINS:
        await query.answer("Only the bot owner / admins can change this.", show_alert=True)
        raise StopPropagation
    value = query.data.split("#", 1)[1]
    if value == "close":
        await query.message.delete()
        raise StopPropagation
    try:
        hours = int(value)
    except ValueError:
        await query.answer("Invalid option.", show_alert=True)
        raise StopPropagation
    if hours not in VERIFY_HOUR_OPTIONS:
        await query.answer("Invalid option.", show_alert=True)
        raise StopPropagation
    await set_verify_hours(hours)
    await query.answer(f"Verification time set to {hours} hours ✅")
    try:
        await query.message.edit_text(await _menu_text(), reply_markup=await _menu_markup())
    except Exception:
        pass  # "message is not modified" when the same option is tapped twice
    raise StopPropagation
