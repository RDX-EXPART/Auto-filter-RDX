# Telegram Stars subscriptions: /plan menu, invoices and payment updates.
import logging

from pyrogram import Client, filters, StopPropagation
from pyrogram.raw import functions as raw_functions, types as raw_types

from info import PREMIUM_AND_REFERAL_MODE
from stars_plans import (
    PLAN_BY_KEY,
    parse_payload,
    grant_plan,
    plan_detail_markup,
    plan_detail_text,
    plans_menu_markup,
    plans_menu_text,
    send_stars_invoice,
)

logger = logging.getLogger(__name__)


# group=-1: pm_filter.py has catch-all text handlers (group 0) that would otherwise swallow
# this command because they are registered before this file.
@Client.on_message(filters.command(["plan", "plans"]), group=-1)
async def plans_command(client, message):
    if PREMIUM_AND_REFERAL_MODE == False:
        return
    mention = message.from_user.mention if message.from_user else "there"
    await message.reply_text(plans_menu_text(mention), reply_markup=plans_menu_markup(), quote=True)
    raise StopPropagation


# group=-1 runs before the catch-all callback handler in pm_filter.py
@Client.on_callback_query(filters.regex(r"^(plans_menu|buy_premium|plan_view#|plan_pay#)"), group=-1)
async def plans_callbacks(client, query):
    data = query.data
    mention = query.from_user.mention

    if data in ("plans_menu", "buy_premium"):
        try:
            await query.message.edit_text(plans_menu_text(mention), reply_markup=plans_menu_markup())
        except Exception:
            await query.message.reply_text(plans_menu_text(mention), reply_markup=plans_menu_markup())
        await query.answer()
        raise StopPropagation

    plan = PLAN_BY_KEY.get(data.split("#", 1)[1])
    if plan is None:
        await query.answer("This plan is no longer available.", show_alert=True)
        raise StopPropagation

    if data.startswith("plan_view#"):
        try:
            await query.message.edit_text(plan_detail_text(plan, mention), reply_markup=plan_detail_markup(plan))
        except Exception:
            await query.message.reply_text(plan_detail_text(plan, mention), reply_markup=plan_detail_markup(plan))
        await query.answer()
        raise StopPropagation

    # plan_pay# -> send the invoice in the user's private chat
    try:
        await send_stars_invoice(client, query.from_user.id, query.from_user.id, plan)
        await query.answer("Invoice sent ⭐ Check your private chat with the bot.", show_alert=False)
    except Exception as error:
        name = type(error).__name__
        if name in ("PeerIdInvalid", "UserIsBlocked", "InputUserDeactivated"):
            await query.answer("Please start the bot in private chat first, then try again.", show_alert=True)
        else:
            logger.exception("Could not send the Stars invoice")
            await query.answer("Payment is temporarily unavailable. Please try again later.", show_alert=True)
    raise StopPropagation


@Client.on_raw_update(group=-10)
async def stars_raw_updates(client, update, users, chats):
    """Answer pre-checkout queries and activate the plan after a successful payment."""
    try:
        if isinstance(update, raw_types.UpdateBotPrecheckoutQuery):
            plan, user_id = parse_payload(update.payload)
            ok = (
                plan is not None
                and user_id == update.user_id
                and update.currency == "XTR"
                and update.total_amount == plan["stars"]
            )
            if ok:
                await client.invoke(raw_functions.messages.SetBotPrecheckoutResults(
                    query_id=update.query_id, success=True))
            else:
                await client.invoke(raw_functions.messages.SetBotPrecheckoutResults(
                    query_id=update.query_id, success=False,
                    error="This plan changed or is no longer available. Please open /plan again."))
            return

        if isinstance(update, (raw_types.UpdateNewMessage, raw_types.UpdateNewChannelMessage)):
            message = getattr(update, "message", None)
            action = getattr(message, "action", None)
            if isinstance(action, raw_types.MessageActionPaymentSentMe):
                plan, user_id = parse_payload(action.payload)
                if plan is None:
                    logger.error("Stars payment with an unknown payload: %r", action.payload)
                    return
                charge = getattr(action, "charge", None)
                telegram_charge_id = getattr(charge, "id", None)
                provider_charge_id = getattr(charge, "provider_charge_id", None)
                charge_id = telegram_charge_id or provider_charge_id or f"{user_id}-{getattr(message, 'id', '')}"
                await grant_plan(
                    client, user_id, plan, charge_id, action.total_amount,
                    telegram_charge_id=telegram_charge_id or provider_charge_id,
                )
    except Exception:
        logger.exception("Stars payment update failed")
