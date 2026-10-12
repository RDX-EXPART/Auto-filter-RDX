# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
from pyrogram import Client, filters
from urllib.parse import quote
from info import CHNL_LNK
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command(["share_text", "share", "sharetext"]))
async def share_text(client, message):
    vj = await client.ask(chat_id = message.from_user.id, text = "Now Send me your text.")
    if vj and (vj.text or vj.caption):
        input_text = vj.text or vj.caption
    else:
        await vj.reply_text(
            text=f"**Notice:**\n\n1. Send Any Text Messages.\n2. No Media Support\n\n**Join Update Channel**",               
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Updates Channel", url=CHNL_LNK)]])
            )                                                   
        return
    await vj.reply_text(
        text=f"**Here is Your Sharing Text 👇**\n\nhttps://t.me/share/url?url=" + quote(input_text),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♂️ Share", url=f"https://t.me/share/url?url={quote(input_text)}")]])       
    )
