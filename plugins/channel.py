# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

"""Live indexing of every file posted in the CHANNELS.

* Every media type is indexed (document, video, audio, animation/GIF, voice, video note).
* Every post writes one clear log line, so you can always see what happened:
      INDEX saved      chat=... msg=... name=...
      INDEX duplicate  chat=... msg=... name=...
      INDEX error      chat=... msg=... name=...
      INDEX skipped    chat=... msg=... (photo / sticker / text ... is not a file)
* A post from a channel that is NOT in CHANNELS logs a warning once, which is the most
  common reason a re-upload "does nothing" (wrong CHANNELS value or bot not admin).
"""

import asyncio
import html
import logging
import re

from pyrogram import Client, filters, ContinuePropagation
from pymongo.errors import PyMongoError

from info import ADMINS, CHANNELS
from database.ia_filterdb import col, save_file
from search_filters import (
    build_search_pattern,
    extract_season_numbers,
    is_series_file,
    matches_filter,
)

logger = logging.getLogger(__name__)

media_filter = (
    filters.document | filters.video | filters.audio
    | filters.animation | filters.voice | filters.video_note
)
_warned_chats = set()
_SAVE_ATTEMPTS = 3

logger.info("Live indexing is watching CHANNELS=%s", CHANNELS)


def _describe(message, media):
    name = getattr(media, "file_name", None) or (message.caption or "")[:60] or "(no name)"
    return f"chat={message.chat.id} msg={message.id} name={name}"


@Client.on_message(filters.chat(CHANNELS) & media_filter, group=0)
async def media(bot, message):
    kind = message.media.value
    media_obj = getattr(message, kind, None)
    if media_obj is None:
        logger.info("INDEX skipped    chat=%s msg=%s (%s has no file)", message.chat.id, message.id, kind)
        return
    media_obj.caption = message.caption
    info = _describe(message, media_obj)
    for attempt in range(1, _SAVE_ATTEMPTS + 1):
        try:
            saved, code = await save_file(media_obj, source_message=message)
            break
        except PyMongoError as error:
            logger.warning("INDEX retry     %s (attempt %s/%s): %s", info, attempt, _SAVE_ATTEMPTS, error)
            await asyncio.sleep(2 * attempt)
        except Exception:
            logger.exception("INDEX error     %s", info)
            return
    else:
        logger.error("INDEX error     %s (database unreachable)", info)
        return
    if saved:
        logger.info("INDEX saved      %s", info)
    elif code == 0:
        logger.info("INDEX duplicate  %s (already in the database)", info)
    else:
        logger.error("INDEX error     %s (save_file returned code %s)", info, code)


@Client.on_message(filters.chat(CHANNELS) & filters.media & ~media_filter, group=0)
async def not_a_file(bot, message):
    logger.info(
        "INDEX skipped    chat=%s msg=%s (%s is not a file type that can be indexed)",
        message.chat.id, message.id, getattr(message.media, "value", "media"),
    )


@Client.on_message(filters.channel & media_filter & ~filters.chat(CHANNELS), group=5)
async def unwatched_channel(bot, message):
    if message.chat.id not in _warned_chats:
        _warned_chats.add(message.chat.id)
        logger.warning(
            "INDEX ignored    files posted in chat=%s (%s) are NOT indexed because it is not in "
            "CHANNELS=%s. Add its id to the CHANNELS setting and redeploy.",
            message.chat.id, getattr(message.chat, "title", ""), CHANNELS,
        )
    raise ContinuePropagation


def _series_report_sync(title):
    tokens = [t for t in re.split(r"[^\w]+", title) if t]
    if not tokens:
        return "Give a title, e.g. <code>/seriescheck The Legend of Hanuman</code>"
    loose = re.compile(".*?".join(re.escape(t) for t in tokens), re.I)
    records = list(col.find(
        {"$or": [{"file_name": loose}, {"caption": loose}]},
        {"file_name": 1, "caption": 1, "_id": 0},
    ))
    if not records:
        return f"No file in the database matches <b>{html.escape(title)}</b>."
    exact_query = f"{title} [[media:series]] [[series_exact:1]]"
    exact = re.compile(build_search_pattern(exact_query), re.I | re.S)
    per_season, no_season, not_matched = {}, [], []
    for record in records:
        name = str(record.get("file_name") or "")
        text = " ".join(v for v in (name, str(record.get("caption") or "")) if v)
        seasons = extract_season_numbers(name) or extract_season_numbers(text)
        for season in seasons:
            per_season[season] = per_season.get(season, 0) + 1
        if not seasons:
            no_season.append(name)
        if not exact.search(name) and not exact.search(text):
            not_matched.append(name)
    lines = [f"<b>{html.escape(title)}</b>: {len(records)} files found in the database"]
    lines.append("Seasons: " + (", ".join(f"S{s:02d}×{n}" for s, n in sorted(per_season.items())) or "none detected"))
    lines.append(f"Files without a season marker: {len(no_season)}")
    for name in no_season[:5]:
        lines.append(f"  • <code>{html.escape(name[:70])}</code>")
    lines.append(f"Files the Series button would NOT show: {len(not_matched)}")
    for name in not_matched[:5]:
        lines.append(f"  • <code>{html.escape(name[:70])}</code>")
    return "\n".join(lines)


@Client.on_message(filters.command("seriescheck") & filters.user(ADMINS))
async def series_check(bot, message):
    title = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""
    await message.reply_text(await asyncio.to_thread(_series_report_sync, title))
