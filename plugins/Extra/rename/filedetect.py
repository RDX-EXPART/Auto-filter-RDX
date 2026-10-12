# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

async def refunc(client, message, new_name, msg):
    try:
        file = getattr(msg, msg.media.value)
        filename = file.file_name
        types = file.mime_type.split("/")
        mime = types[0]
        try:
            if ".mp4" or ".mkv" in new_name:
                if ".mp4" in new_name:
                    new_name = new_name.replace(".mp4", "")  # Remove the dot from new_name
                if ".mkv" in new_name:
                    new_name = new_name.replace(".mkv", "")
            else:
                new_name = new_name
            if "." in new_name:
                new_name = new_name.replace(".", "")  
            if mime == "video":
                markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton("📁 Document", callback_data="upload_document"),
                    InlineKeyboardButton("🎥 Video", callback_data="upload_video")]])
            elif mime == "audio":
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                    "📁 Document", callback_data="upload_document"), InlineKeyboardButton("🎵 audio", callback_data="upload_audio")]])
            else:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]])
            await message.reply_text(f"**Select the output file type**\n**🎞New Name** :- ```{out_filename}```", reply_to_message_id=msg.id, reply_markup=markup)

        except:
            try:
                out = filename.split(".")
                out_name = out[-1]
                out_filename = new_name + "." + out_name
            except:
                await message.reply_text("**Error** :  No  Extension in File, Not Supporting")
                return
            if mime == "video":
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                    "📁 Document", callback_data="upload_document"), InlineKeyboardButton("🎥 Video", callback_data="upload_video")]])
            elif mime == "audio":
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                    "📁 Document", callback_data="upload_document"), InlineKeyboardButton("🎵 audio", callback_data="upload_audio")]])
            else:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]])
            await message.reply_text(f"**Select the output file type**\n**🎞New Name ->** :- {out_filename}", reply_to_message_id=msg.id, reply_markup=markup)
    except Exception as e:
        print(f"error: {e}")
