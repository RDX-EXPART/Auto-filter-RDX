"""Telegram Stars (XTR) subscription plans: menu texts, invoices and activation.

Plans (prices come from info.py / env vars):
  Silver   - 1 day
  Gold     - 15 days
  Platinum - 30 days (monthly)
  Diamond  - lifetime
"""
import datetime
import json
import logging
import random

import aiohttp
from pyrogram.raw import functions as raw_functions, types as raw_types
from pymongo.errors import DuplicateKeyError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.users_chats_db import db
from info import (
    BOT_TOKEN,
    LOG_CHANNEL,
    STARS_PRICE_1DAY,
    STARS_PRICE_15DAYS,
    STARS_PRICE_30DAYS,
    STARS_PRICE_LIFETIME,
)

logger = logging.getLogger(__name__)

# "Lifetime" is stored as a far-future expiry so the existing premium checks keep working.
LIFETIME_EXPIRY = datetime.datetime(2099, 12, 31, 23, 59, 59)

PLANS = [
    {"key": "silver", "emoji": "🥈", "name": "Silver", "days": 1, "stars": STARS_PRICE_1DAY, "label": "1 Day"},
    {"key": "gold", "emoji": "🥇", "name": "Gold", "days": 15, "stars": STARS_PRICE_15DAYS, "label": "15 Days"},
    {"key": "platinum", "emoji": "🏅", "name": "Platinum", "days": 30, "stars": STARS_PRICE_30DAYS, "label": "30 Days (Monthly)"},
    {"key": "diamond", "emoji": "💎", "name": "Diamond", "days": None, "stars": STARS_PRICE_LIFETIME, "label": "Lifetime"},
]
PLAN_BY_KEY = {plan["key"]: plan for plan in PLANS}

_SMALL_CAPS = dict(zip(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ",
))


def sc(text):
    """Small-caps look used across the bot's messages."""
    return "".join(_SMALL_CAPS.get(ch, ch) for ch in str(text).lower())


def is_lifetime(expiry):
    return isinstance(expiry, datetime.datetime) and expiry.year >= 2090


# ------------------------------------------------------------------ menus
def plans_menu_text(mention):
    lines = [
        f"<b>👋 {sc('hey')} {mention},</b>",
        "",
        f"<b>⭐ {sc('premium plans')} — {sc('pay with telegram stars')}</b>",
        "",
    ]
    for plan in PLANS:
        lines.append(f"<b>{plan['emoji']} {sc(plan['name'])} ➛ {sc(plan['label'])} ➛ ⭐ {plan['stars']}</b>")
    lines += [
        "",
        f"<blockquote><b>✨ {sc('no verification')} · {sc('no shortlinks')} · {sc('direct files')}</b></blockquote>",
        "",
        f"<b>➛ {sc('tap a plan below to continue')}</b>",
        f"<b>➛ {sc('check your active plan')} : /myplan</b>",
    ]
    return "\n".join(lines)


def plans_menu_markup():
    rows = [
        [InlineKeyboardButton(
            f"{plan['emoji']} {plan['name']} • {plan['label']} • ⭐{plan['stars']}",
            callback_data=f"plan_view#{plan['key']}",
        )]
        for plan in PLANS
    ]
    rows.append([InlineKeyboardButton("⚠️ ᴄʟᴏsᴇ / ᴅᴇʟᴇᴛᴇ ⚠️", callback_data="close_data")])
    return InlineKeyboardMarkup(rows)


def plan_detail_text(plan, mention):
    return "\n".join([
        f"<b>👋 {sc('hey')} {mention},</b>",
        "",
        f"<b>{plan['emoji']} <u>{sc(plan['name'])} {sc('plan')}</u></b>",
        f"<b>⏰ {sc(plan['label'])}</b>",
        f"<b>⭐ {sc('plan price')} ➛ {plan['stars']} {sc('stars')}</b>",
        "",
        f"<b>➛ {sc('use')} /plan {sc('to see all our plans at once.')}</b>",
        f"<b>➛ {sc('check your active plan by using')} : /myplan</b>",
    ])


def plan_detail_markup(plan):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Pay {plan['stars']} Stars", callback_data=f"plan_pay#{plan['key']}")],
        [
            InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data="plans_menu"),
            InlineKeyboardButton("⚠️ ᴄʟᴏsᴇ", callback_data="close_data"),
        ],
    ])


# ---------------------------------------------------------------- payload
def build_payload(user_id, plan_key):
    return f"plan:{plan_key}:{user_id}"


def parse_payload(payload):
    """Return (plan, user_id) or (None, None) for an unknown payload."""
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        tag, plan_key, user_id = str(payload).split(":")
        if tag != "plan" or plan_key not in PLAN_BY_KEY:
            return None, None
        return PLAN_BY_KEY[plan_key], int(user_id)
    except Exception:
        return None, None


# ---------------------------------------------------------------- invoices
def _invoice_text(plan):
    title = f"{plan['emoji']} {plan['name']} Plan"
    description = f"{plan['label']} premium subscription: no verification, no shortlinks, direct files."
    return title, description


async def _create_invoice_link(plan, user_id):
    """Fallback: Bot API createInvoiceLink (works for Stars without any provider token)."""
    title, description = _invoice_text(plan)
    data = {
        "title": title,
        "description": description,
        "payload": build_payload(user_id, plan["key"]),
        "currency": "XTR",
        "prices": json.dumps([{"label": f"{plan['name']} - {plan['label']}", "amount": plan["stars"]}]),
    }
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=20)) as response:
            result = await response.json()
    if not result.get("ok"):
        raise RuntimeError(f"createInvoiceLink failed: {result}")
    return result["result"]


async def send_stars_invoice(client, chat_id, user_id, plan):
    """Send a Telegram Stars invoice message to ``chat_id``."""
    title, description = _invoice_text(plan)
    try:
        media = raw_types.InputMediaInvoice(
            title=title,
            description=description,
            invoice=raw_types.Invoice(
                currency="XTR",
                prices=[raw_types.LabeledPrice(label=f"{plan['name']} - {plan['label']}", amount=plan["stars"])],
            ),
            payload=build_payload(user_id, plan["key"]).encode("utf-8"),
            provider_data=raw_types.DataJSON(data="{}"),
        )
        markup = raw_types.ReplyInlineMarkup(rows=[
            raw_types.KeyboardButtonRow(buttons=[raw_types.KeyboardButtonBuy(text=f"⭐ Pay {plan['stars']} Stars")])
        ])
        await client.invoke(raw_functions.messages.SendMedia(
            peer=await client.resolve_peer(chat_id),
            media=media,
            message="",
            random_id=random.getrandbits(63),
            reply_markup=markup,
        ))
        return
    except Exception as error:
        # PeerIdInvalid / blocked bot must reach the caller; anything else -> try the link fallback.
        name = type(error).__name__
        if name in ("PeerIdInvalid", "UserIsBlocked", "InputUserDeactivated", "UserDeactivated"):
            raise
        logger.warning("Raw Stars invoice failed (%s: %s); falling back to an invoice link", name, error)

    link = await _create_invoice_link(plan, user_id)
    await client.send_message(
        chat_id,
        f"<b>{plan['emoji']} {sc(plan['name'])} {sc('plan')} ➛ ⭐ {plan['stars']} {sc('stars')}</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"⭐ Pay {plan['stars']} Stars", url=link)]]),
    )


# -------------------------------------------------------------- activation
async def grant_plan(client, user_id, plan, charge_id, stars, telegram_charge_id=None):
    """Activate the plan (extending an active one) and tell the user. Idempotent per charge."""
    try:
        await db.db.star_payments.insert_one({
            "_id": str(charge_id),
            "user_id": user_id,
            "plan": plan["key"],
            "stars": stars,
            "telegram_payment_charge_id": telegram_charge_id,
            "paid_at": datetime.datetime.utcnow(),
        })
        first_time = True
    except DuplicateKeyError:
        first_time = False
    if not first_time:
        logger.warning("Stars payment %s was already credited; skipping", charge_id)
        return None

    now = datetime.datetime.now()
    current = None
    user_data = await db.get_user(user_id)
    if user_data:
        current = user_data.get("expiry_time")
    if plan["days"] is None:
        expiry = LIFETIME_EXPIRY
    elif is_lifetime(current):
        expiry = current  # already lifetime, never shorten it
    else:
        start = current if isinstance(current, datetime.datetime) and current > now else now
        expiry = start + datetime.timedelta(days=plan["days"])
    await db.update_user({"id": user_id, "expiry_time": expiry})

    until = "Lifetime ♾️" if is_lifetime(expiry) else expiry.strftime("%d %b %Y, %I:%M %p")
    try:
        await client.send_message(
            user_id,
            f"<b>✅ {sc('payment received')}!\n\n"
            f"{plan['emoji']} {sc(plan['name'])} {sc('plan activated')} ({sc(plan['label'])})\n"
            f"⭐ {sc('paid')} : {stars} {sc('stars')}\n"
            f"🕒 {sc('valid until')} : {until}\n\n"
            f"{sc('no verification needed now. enjoy!')} 😀\n"
            f"{sc('check your plan')} : /myplan</b>",
        )
    except Exception:
        logger.exception("Could not notify user %s about the activated plan", user_id)
    try:
        await client.send_message(
            LOG_CHANNEL,
            f"<b>⭐ New Stars payment\n\nUser: <code>{user_id}</code>\nPlan: {plan['name']} ({plan['label']})\n"
            f"Stars: {stars}\nCharge: <code>{telegram_charge_id or charge_id}</code></b>",
        )
    except Exception:
        pass
    return expiry
