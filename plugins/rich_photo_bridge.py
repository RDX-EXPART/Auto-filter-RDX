"""Runs before every callback so a rich message that carries a poster/backdrop still looks like a
photo card to the filter code (message.photo / message.caption).  See rich_results.py."""
from pyrogram import Client

import rich_results


@Client.on_callback_query(group=-100)
async def rich_photo_impersonation(client, query):
    try:
        rich_results.impersonate_photo(getattr(query, "message", None))
    except Exception:
        pass
