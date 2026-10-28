# Don't Remove Credit @rdxmovie_hd
# Subscribe YouTube Channel For Amazing Bot @ch_VJ
# Ask Doubt on telegram @rdx_personal

import os, logging, string, asyncio, time, re, ast, random, math, pytz, pyrogram, html
from datetime import datetime, timedelta, date
from Script import script
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatPermissions, WebAppInfo
from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from database.tmdb_client import (
    get_tmdb_imdb_id,
    get_tmdb_movie,
    get_tmdb_tv,
    get_tmdb_any,
    search_tmdb as search_tmdb_movie,
    search_tmdb_tv,
    image_url,
    fetch_tmdb_image,
    build_tmdb_card,
    release_status_label,
    SEPARATOR,
)
from database.omdb_client import get_omdb_ratings
from utils import tmdb_poster_row, tmdb_visuals_enabled, get_size, is_subscribed, pub_is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings, get_shortlink, get_tutorial, send_all, get_cap, reply_photo_or_text, get_auto_delete_seconds, auto_delete_minutes
from database.users_chats_db import db
from database.ia_filterdb import (
    col,
    db as vjdb,
    get_file_details,
    get_search_results,
    get_bad_files,
    get_episode_counts,
    get_available_filter_values,
    get_cached_filter_values,
    get_episode_values,
    clear_filter_discovery_cache,
)
from search_filters import (
    make_filter_query,
    parse_filter_query,
    clean_display_filename,
    extract_filter_values,
)
from database.filters_mdb import del_all, find_filter, get_filters
from database.connections_mdb import mydb, active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from database.gfilters_mdb import find_gfilter, get_gfilters, del_allg
from urllib.parse import quote_plus
from RDX.util.file_properties import get_name, get_hash, get_media_file_size

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# `schedule_delete` lives in utils.py. If an older utils.py is deployed together with this file
# (partial upload) importing it would fail, or - worse - the call would raise NameError right
# after a result was sent. Fall back to strongly-referenced in-memory timers and say so loudly.
try:
    from utils import schedule_delete
except ImportError:
    _FALLBACK_TIMERS = set()

    async def schedule_delete(client, chat_id, message_ids, delay_seconds, reason="search-result"):
        logger.error("utils.py is OUTDATED (no schedule_delete). Using in-memory timers; "
                     "please upload the complete project so deletions survive restarts.")

        async def _run(mid):
            await asyncio.sleep(delay_seconds)
            try:
                await client.delete_messages(chat_id, mid)
                logger.info("Auto-delete (fallback) done: chat=%s msg=%s", chat_id, mid)
            except Exception as error:
                logger.warning("Auto-delete (fallback) failed: chat=%s msg=%s: %s: %s",
                               chat_id, mid, type(error).__name__, error)

        ids = {int(mid) for mid in message_ids if mid}
        for mid in ids:
            task = asyncio.get_running_loop().create_task(_run(mid))
            _FALLBACK_TIMERS.add(task)
            task.add_done_callback(_FALLBACK_TIMERS.discard)
        return len(ids)

lock = asyncio.Lock()
_FILTER_VALUE_SCAN_LIMIT = 2000

BUTTON = {}
BUTTONS = {}
FRESH = {}
BUTTONS0 = {}
BUTTONS1 = {}
BUTTONS2 = {}
SPELL_CHECK = {}
MEDIA_SEARCH = {}
SEARCH_METADATA = {}
RESULT_PAGE_SIZES = {}

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    if message.chat.id != SUPPORT_CHAT_ID:
        settings = await get_settings(message.chat.id)
        chatid = message.chat.id 
        user_id = message.from_user.id if message.from_user else 0
        if settings['fsub'] != None:
            try:
                btn = await pub_is_subscribed(client, message, settings['fsub'])
                if btn:
                    btn.append([InlineKeyboardButton("Unmute Me 🔕", callback_data=f"unmuteme#{int(user_id)}")])
                    await client.restrict_chat_member(chatid, message.from_user.id, ChatPermissions(can_send_messages=False))
                    await reply_photo_or_text(message, photo=random.choice(PICS), caption=f"👋 Hello {message.from_user.mention},\n\nPlease join the channel then click on unmute me button. 😇", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
                    return
            except Exception as e:
                print(e)
            
        manual = await manual_filters(client, message)
        if manual == False:
            settings = await get_settings(message.chat.id)
            try:
                if settings['auto_ffilter']:
                    await _offer_media_type(client, message)
            except KeyError:
                grpid = await active_connection(str(message.from_user.id))
                await save_group_settings(grpid, 'auto_ffilter', True)
                settings = await get_settings(message.chat.id)
                if settings['auto_ffilter']:
                    await _offer_media_type(client, message)
    else: #a better logic to avoid repeated lines of code in auto_filter function
        search = message.text
        temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
        if total_results == 0:
            return
        else:
            return await message.reply_text(f"<b>Hᴇʏ {message.from_user.mention}, {str(total_results)} ʀᴇsᴜʟᴛs ᴀʀᴇ ғᴏᴜɴᴅ ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀsᴇ ғᴏʀ ʏᴏᴜʀ ᴏ̨ᴜᴇʀʏ {search}. \n\nTʜɪs ɪs ᴀ sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ sᴏ ᴛʜᴀᴛ ʏᴏᴜ ᴄᴀɴ'ᴛ ɢᴇᴛ ғɪʟᴇs ғʀᴏᴍ ʜᴇʀᴇ...\n\nJᴏɪɴ ᴀɴᴅ Sᴇᴀʀᴄʜ Hᴇʀᴇ - {GRP_LNK}</b>")

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    content = message.text
    if not message.from_user:
        return
    if content.startswith("/") or content.startswith("#"): return  # ignore commands and hashtags
    if _pm_search_is_enabled():
        ai_search = True
        await _offer_media_type(bot, message)
    else:
        await message.reply_text(
            "Private search is disabled on this deployment. Set PM_SEARCH=True in Heroku Config Vars and restart the bot to enable it."
        )


def _pm_search_is_enabled():
    """Read PM_SEARCH using normal boolean environment-variable semantics."""
    raw_value = os.environ.get("PM_SEARCH")
    if raw_value is None:
        return bool(PM_SEARCH)
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = BUTTONS.get(key) or FRESH.get(key)
   # if not search:
      #  await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
       # return

    if not search:
        return await query.answer("This search has expired. Please search again.", show_alert=True)

    # Acknowledge before Mongo queries, caption generation, or pagination work.
    await query.answer()
    if key in FILTER_PAGER:
        # Page turn inside a filtered result: same filter, same caption/keyboard layout.
        return await _show_filter_results(
            query, key, FILTER_PAGER[key], offset=offset,
            callback_answered=True, show_loading=False,
        )
    if parse_filter_query(search)[1].get("media"):
        # Movie/Series results use the same renderer for page turns and filters.
        return await _show_filter_results(
            query, key, search, offset=offset,
            callback_answered=True, show_loading=False,
        )
    settings = _effective_settings(await get_settings(query.message.chat.id), query.message)
    page_size = _get_result_page_size(
        key,
        settings,
        temp.GETALL.get(key),
        fallback=_filter_page_size(settings),
    )
    files, n_offset, total = await get_search_results(
        query.message.chat.id,
        search,
        max_results=page_size,
        offset=offset,
        filter=True,
    )
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    temp.GETALL[key] = files
    temp.SHORT[query.from_user.id] = query.message.chat.id
    pre = 'filep' if settings['file_secure'] else 'file'
    if parse_filter_query(search)[1].get("media"):
        btn = await _typed_result_keyboard(
            files, key, search, settings, pre, total, n_offset, req,
            offset=offset, include_files=settings.get("button", True), include_back=True,
        )
        if not settings.get("button", True):
            cap = await get_cap(
                settings, "0.00", files, query, total, search,
                fetch_metadata=False,
            )
            await query.message.edit_text(
                text=cap,
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
            )
        else:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        return
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=_file_button_text(file), callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]

        btn.insert(0, 
            [
                InlineKeyboardButton('ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
        btn.insert(2, [InlineKeyboardButton("🗂 Combined Files", callback_data=f"combined#{key}")])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton('ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
        btn.insert(2, [InlineKeyboardButton("🗂 Combined Files", callback_data=f"combined#{key}")])
    try:
        if settings['max_btn']:
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                        InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
        else:
            if 0 < offset <= int(MAX_B_TN):
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - int(MAX_B_TN)
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"),
                        InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
    except KeyError:
        await save_group_settings(query.message.chat.id, 'max_btn', True)
        if 0 < offset <= 10:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - 10
        if n_offset == 0:
            btn.append(
                [InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
            )
        elif off_set is None:
            btn.append([InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")])
        else:
            btn.append(
                [
                    InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                    InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")
                ],
            )
    btn.append([InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")])
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        cap = await get_cap(
            settings, remaining_seconds, files, query, total, search,
            fetch_metadata=False,
        )
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
  #  if not movies:
     #   return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movie = movies[(int(movie_))]
    movie = re.sub(r"[:\-]", " ", movie)
    movie = re.sub(r"\s+", " ", movie).strip()
    await query.answer(script.TOP_ALRT_MSG)
    gl = await global_filters(bot, query.message, text=movie)
    if gl == False:
        k = await manual_filters(bot, query.message, text=movie)
        if k == False:
            files, offset, total_results = await get_search_results(query.message.chat.id, movie, offset=0, filter=True)
            if files:
                k = (movie, files, offset, total_results)
                ai_search = True
                reply_msg = await query.message.edit_text(f"<b><i>Searching For {movie} 🔍</i></b>")
                await auto_filter(bot, movie, query, reply_msg, ai_search, k)
            else:
                reqstr1 = query.from_user.id if query.from_user else 0
                reqstr = await bot.get_users(reqstr1)
                if NO_RESULTS_MSG:
                    await bot.send_message(chat_id=LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, movie)))
                k = await query.message.edit(script.MVE_NT_FND)
                await asyncio.sleep(10)
                await k.delete()

# Year 
@Client.on_callback_query(filters.regex(r"^years#"))
async def years_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    btn = []
    for i in range(0, len(YEARS)-1, 4):
        row = []
        for j in range(4):
            if i+j < len(YEARS):
                row.append(
                    InlineKeyboardButton(
                        text=YEARS[i+j].title(),
                        callback_data=f"fy#{YEARS[i+j].lower()}#{key}"
                    )
                )
        btn.append(row)

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="sᴇʟᴇᴄᴛ ʏᴏᴜʀ ʏᴇᴀʀ", callback_data="ident"
            )
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fy#homepage#{key}")])

    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass

@Client.on_callback_query(filters.regex(r"^fy#"))
async def filter_yearss_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}", callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])

    if offset != "":
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
    
            else:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages")]
        )
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fy#homepage#{key}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass
    await query.answer()  

# Episode

@Client.on_callback_query(filters.regex(r"^episodes#"))
async def episodes_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    active = BUTTONS.get(key) or FRESH.get(key) or ""
    base, selected = parse_filter_query(active)
    season = selected.get("season")
    if not season or not str(season).isdigit():
        return await query.answer("Please select a season first.", show_alert=True)

    episodes = await get_episode_values(
        base, season, max_scan=_FILTER_VALUE_SCAN_LIMIT,
    )
    if not episodes:
        return await query.answer("No episodes are uploaded for this season.", show_alert=True)

    btn = []
    for i in range(0, len(episodes), 4):
        btn.append([
            InlineKeyboardButton(text=f"E{number:02d}", callback_data=f"fe#e{number:02d}#{key}")
            for number in episodes[i:i + 4]
        ])
    btn.insert(0, [InlineKeyboardButton(text="sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴇᴘɪsᴏᴅᴇ", callback_data="ident")])
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fe#homepage#{key}")])

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^fe#"))
async def filter_episodes_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}", callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])

    if offset != "":
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
    
            else:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages")]
        )
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fe#homepage#{key}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass
    await query.answer()
    


#languages

@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    btn = []
    for i in range(0, len(LANGUAGES)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=LANGUAGES[i].title(),
                callback_data=f"fl#{LANGUAGES[i].lower()}#{key}"
            ),
            InlineKeyboardButton(
                text=LANGUAGES[i+1].title(),
                callback_data=f"fl#{LANGUAGES[i+1].lower()}#{key}"
            ),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="👇 𝖲𝖾𝗅𝖾𝖼𝗍 𝖸𝗈𝗎𝗋 𝖫𝖺𝗇𝗀𝗎𝖺𝗀𝖾𝗌 👇", callback_data="ident"
            )
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ​↭", callback_data=f"fl#homepage#{key}")])

    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}", callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])

    if offset != "":
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
    
            else:
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages")]
        )
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fl#homepage#{key}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass
    await query.answer()
    
    
    
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def seasons_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass

    _, key = query.data.split("#")
    # Keep the current filters: the picker only chooses a season, it does not reset the result.
    active = BUTTONS.get(key) or FRESH.get(key) or ""
    base, _ = parse_filter_query(active)
    available = await get_available_filter_values(
        base, max_scan=_FILTER_VALUE_SCAN_LIMIT,
    )
    seasons = available.get("seasons", [])
    if not seasons:
        return await query.answer("No seasons are uploaded for this title.", show_alert=True)

    btn = [[InlineKeyboardButton(text="👇 Select Season 👇", callback_data="ident")]]
    for i in range(0, len(seasons), 2):
        btn.append([
            InlineKeyboardButton(text=f"Season {number:02d}", callback_data=f"fs#season {number}#{key}")
            for number in seasons[i:i + 2]
        ])
    btn.append([InlineKeyboardButton(text="All Seasons", callback_data=f"fs#all#{key}")])
    btn.append([InlineKeyboardButton(text="↩ Back to Results", callback_data=f"fback#{key}")])

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass

@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_seasons_cb_handler(client: Client, query: CallbackQuery):
    _, seas, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    sea = ""
    season_search = ["s01","s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "season 01","season 02","season 03","season 04","season 05","season 06","season 07","season 08","season 09","season 10", "season 1","season 2","season 3","season 4","season 5","season 6","season 7","season 8","season 9"]
    for x in range (len(season_search)):
        if season_search[x] in search:
            sea = season_search[x]
            break
    if sea:
        search = search.replace(sea, "")
    else:
        search = search
    
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    
    searchagn = search
    search1 = search
    search2 = search
    search = f"{search} {seas}"
    BUTTONS0[key] = search
    
    files, _, _ = await get_search_results(chat_id, search, max_results=10)
    files = [file for file in files if re.search(seas, file["file_name"], re.IGNORECASE)]
    
    seas1 = "s01" if seas == "season 1" else "s02" if seas == "season 2" else "s03" if seas == "season 3" else "s04" if seas == "season 4" else "s05" if seas == "season 5" else "s06" if seas == "season 6" else "s07" if seas == "season 7" else "s08" if seas == "season 8" else "s09" if seas == "season 9" else "s10" if seas == "season 10" else ""
    search1 = f"{search1} {seas1}"
    BUTTONS1[key] = search1
    files1, _, _ = await get_search_results(chat_id, search1, max_results=10)
    files1 = [file for file in files1 if re.search(seas1, file["file_name"], re.IGNORECASE)]
    
    if files1:
        files.extend(files1)
    
    seas2 = "season 01" if seas == "season 1" else "season 02" if seas == "season 2" else "season 03" if seas == "season 3" else "season 04" if seas == "season 4" else "season 05" if seas == "season 5" else "season 06" if seas == "season 6" else "season 07" if seas == "season 7" else "season 08" if seas == "season 8" else "season 09" if seas == "season 9" else "s010"
    search2 = f"{search2} {seas2}"
    BUTTONS2[key] = search2
    files2, _, _ = await get_search_results(chat_id, search2, max_results=10)
    files2 = [file for file in files2 if re.search(seas2, file["file_name"], re.IGNORECASE)]

    if files2:
        files.extend(files2)
        
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}", callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"next_{req}_{key}_{offset}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        total_results = len(files)
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=False,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    btn = []
    for i in range(0, len(QUALITIES)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=QUALITIES[i].title(),
                callback_data=f"fl#{QUALITIES[i].lower()}#{key}"
            ),
            InlineKeyboardButton(
                text=QUALITIES[i+1].title(),
                callback_data=f"fl#{QUALITIES[i+1].lower()}#{key}"
            ),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ ʏᴏᴜʀ ǫᴜᴀʟɪᴛʏ ⇊", callback_data="ident"
            )
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"fl#homepage#{key}")])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    _, qual, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    baal = qual in search
    if baal:
        search = search.replace(qual, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=False,
            )
    except:
        pass
    searchagain = search
    if lang != "homepage":
        search = f"{search} {qual}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    # files = [file for file in files if re.search(lang, file["file_name"], re.IGNORECASE)]
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}", callback_data=f'{pre}#{file["file_id"]}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])

    if offset != "":
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
                )
    
            else:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="😶 ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ 😶",callback_data="pages")]
        )
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ↭", callback_data=f"next_{req}_{key}_{offset}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        total_results = len(files)
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
                
async def _request_channel_url(client, fallback):
    """Invite link for the request channel. Uses the fallback URL if the link cannot be created."""
    if REQST_CHANNEL is None:
        return fallback
    try:
        invite = await client.create_chat_invite_link(REQST_CHANNEL, creates_join_request=True)
        return invite.invite_link
    except Exception:
        logger.exception("Could not create the request-channel invite link")
        return fallback


async def _is_group_settings_admin(client, group_id, user_id):
    """Authorize settings callbacks against the target group, not a user's active connection."""
    if user_id is None:
        return False
    if str(user_id) in {str(admin_id) for admin_id in ADMINS}:
        return True
    try:
        member = await client.get_chat_member(int(group_id), user_id)
    except Exception:
        return False
    return member.status in (
        enums.ChatMemberStatus.ADMINISTRATOR,
        enums.ChatMemberStatus.OWNER,
    )


async def _send_settings_to_pm(client, user_id, title, reply_markup):
    """Send settings into the user's private chat; group message IDs cannot be PM reply targets."""
    safe_title = html.escape(str(title or "your group"))
    return await client.send_message(
        chat_id=user_id,
        text=f"<b>Change your settings for {safe_title} as you wish ⚙</b>",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
    elif query.data == "get_trail":
        user_id = query.from_user.id
        free_trial_status = await db.get_free_trial_status(user_id)
        if not free_trial_status:            
            await db.give_free_trail(user_id)
            new_text = "**ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ 5 ᴍɪɴᴜᴛᴇs ꜰʀᴏᴍ ɴᴏᴡ 😀\n\nआप अब से 5 मिनट के लिए निःशुल्क ट्रायल का उपयोग कर सकते हैं 😀**"        
            await query.message.edit_text(text=new_text)
            return
        else:
            new_text= "**🤣 you already used free now no more free trail. please buy subscription here are our 👉 /plans**"
            await query.message.edit_text(text=new_text)
            return
            
    elif query.data == "gfiltersdeleteallconfirm":
        await del_allg(query.message, 'gfilters')
        await query.answer("Done !")
        return
    elif query.data == "gfiltersdeleteallcancel": 
        await query.message.reply_to_message.delete()
        await query.message.delete()
        await query.answer("Process Cancelled !")
        return
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Mᴀᴋᴇ sᴜʀᴇ I'ᴍ ᴘʀᴇsᴇɴᴛ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ!!", quote=True)
                    return await query.answer(MSG_ALRT)
            else:
                await query.message.edit_text(
                    "I'ᴍ ɴᴏᴛ ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ ᴀɴʏ ɢʀᴏᴜᴘs!\nCʜᴇᴄᴋ /connections ᴏʀ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ᴀɴʏ ɢʀᴏᴜᴘs",
                    quote=True
                )
                return await query.answer(MSG_ALRT)

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return await query.answer(MSG_ALRT)

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("Yᴏᴜ ɴᴇᴇᴅ ᴛᴏ ʙᴇ Gʀᴏᴜᴘ Oᴡɴᴇʀ ᴏʀ ᴀɴ Aᴜᴛʜ Usᴇʀ ᴛᴏ ᴅᴏ ᴛʜᴀᴛ!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("Tʜᴀᴛ's ɴᴏᴛ ғᴏʀ ʏᴏᴜ!!", show_alert=True)
    elif "groupcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Gʀᴏᴜᴘ Nᴀᴍᴇ : **{title}**\nGʀᴏᴜᴘ ID : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return await query.answer(MSG_ALRT)
    elif "connectcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Cᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!', parse_mode=enums.ParseMode.MARKDOWN)
        return await query.answer(MSG_ALRT)
    elif "disconnect" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Dɪsᴄᴏɴɴᴇᴄᴛᴇᴅ ғʀᴏᴍ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer(MSG_ALRT)
    elif "deletecb" in query.data:
        await query.answer()

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴄᴏɴɴᴇᴄᴛɪᴏɴ !"
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer(MSG_ALRT)
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "Tʜᴇʀᴇ ᴀʀᴇ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴄᴏɴɴᴇᴄᴛɪᴏɴs!! Cᴏɴɴᴇᴄᴛ ᴛᴏ sᴏᴍᴇ ɢʀᴏᴜᴘs ғɪʀsᴛ.",
            )
            return await query.answer(MSG_ALRT)
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Yᴏᴜʀ ᴄᴏɴɴᴇᴄᴛᴇᴅ ɢʀᴏᴜᴘ ᴅᴇᴛᴀɪʟs ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "gfilteralert" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_gfilter('gfilters', keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
        
    if query.data.startswith("file"):
        clicked = query.from_user.id
        try:
            typed = query.message.reply_to_message.from_user.id
        except:
            typed = query.from_user.id
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_
        title = clean_display_filename(files["file_name"])
        size = get_size(files["file_size"])
        f_caption = files["caption"]
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = clean_display_filename(files["file_name"])

        try:
            if settings['is_shortlink'] and not await db.has_premium_access(query.from_user.id):
                if clicked == typed:
                    temp.SHORT[clicked] = query.message.chat.id
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=short_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
            elif settings['is_shortlink'] and await db.has_premium_access(query.from_user.id):
                if clicked == typed:
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
                    
            else:
                if clicked == typed:
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
            
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#")
        settings = await get_settings(query.message.chat.id)
        pre = 'allfilesp' if settings['file_secure'] else 'allfiles'
        try:
            if settings['is_shortlink'] and not await db.has_premium_access(query.from_user.id):
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles1_{key}")
            elif settings['is_shortlink'] and await db.has_premium_access(query.from_user.id):
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={pre}_{key}")
                return 
            else:
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={pre}_{key}")
                
            
                
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
        except Exception as e:
            logger.exception(e)
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")

    elif query.data.startswith("unmuteme"):
        ident, userid = query.data.split("#")
        user_id = query.from_user.id
        settings = await get_settings(int(query.message.chat.id))
        if userid == 0:
            await query.answer("You are anonymous admin !", show_alert=True)
            return
        try:
            btn = await pub_is_subscribed(client, query, settings['fsub'])
            if btn:
                await query.answer("Kindly Join Given Channel Then Click On Unmute Button", show_alert=True)
            else:
                await client.unban_chat_member(query.message.chat.id, user_id)
                await query.answer("Unmuted Successfully !", show_alert=True)
                try:
                    await query.message.delete()
                except:
                    return
        except:
            await query.answer("Not For Your My Dear", show_alert=True)
   
    elif query.data.startswith("del"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_
        title = files['file_name']
        size = get_size(files['file_size'])
        f_caption = files['caption']
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files['file_name']}"
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")
    
    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("Jᴏɪɴ ᴏᴜʀ Bᴀᴄᴋ-ᴜᴘ ᴄʜᴀɴɴᴇʟ ᴍᴀʜɴ! 😒", show_alert=True)
            return
        ident, kk, file_id = query.data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={kk}_{file_id}")
    
    elif query.data == "pages":
        await query.answer()
    
    elif query.data.startswith("send_fsall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = BUTTONS.get(key)
     #   if not search:
      #      await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
      #      return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS1.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS2.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)
        
    elif query.data.startswith("send_fall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = FRESH.get(key)
     #   if not search:
       #     await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
      #      return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)
        
    elif query.data.startswith("killfilesdq"):
        ident, keyword = query.data.split("#")
        #await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
        files, total = await get_bad_files(keyword)
        await query.message.edit_text("<b>File deletion process will start in 5 seconds !</b>")
        await asyncio.sleep(5)
        deleted = 0
        async with lock:
            try:
                for file in files:
                    file_ids = file["file_id"]
                    file_name = file["file_name"]
                    result = col.delete_one({
                        'file_id': file_ids,
                    })
                    if result.deleted_count:
                        logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
                    deleted += 1
                    if deleted % 50 == 0:
                        await query.message.edit_text(f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
            except Exception as e:
                logger.exception(e)
                await query.message.edit_text(f'Error: {e}')
            else:
                if deleted:
                    clear_filter_discovery_cache()
                await query.message.edit_text(f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted)} files from database for your query {keyword}.</b>")
    
    elif query.data.startswith("opnsetgrp"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await _is_group_settings_admin(client, grp_id, userid):
            await query.answer("Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Tʜᴇ Rɪɢʜᴛs Tᴏ Dᴏ Tʜɪs !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["file_secure"] else '✘ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["imdb"] else '✘ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                tmdb_poster_row(settings, str(grp_id)),
                [
                    InlineKeyboardButton('TMDB BACKDROP', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ ON' if settings['tmdb_backdrop'] else '✘ OFF', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["spell_check"] else '✘ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["welcome"] else '✘ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton(f'✔ {auto_delete_minutes(settings)} Mɪɴs' if settings["auto_delete"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Dᴇʟᴇᴛᴇ Tɪᴍᴇ',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}'),
                    InlineKeyboardButton(f'{auto_delete_minutes(settings)} Mɪɴs',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["auto_ffilter"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["is_shortlink"] else '✘ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
            buttons.append([
                InlineKeyboardButton("✖ Close Menu", callback_data=f"close_settings#{grp_id}")
            ])
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=f"<b>Cʜᴀɴɢᴇ Yᴏᴜʀ Sᴇᴛᴛɪɴɢs Fᴏʀ {title} As Yᴏᴜʀ Wɪsʜ ⚙</b>",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
            await query.message.edit_reply_markup(reply_markup)
        
    elif query.data.startswith("opnsetpm"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await _is_group_settings_admin(client, grp_id, userid):
            await query.answer("Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Tʜᴇ Rɪɢʜᴛs Tᴏ Dᴏ Tʜɪs !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        if settings is None:
            await query.answer("Could not load this group's settings. Please retry.", show_alert=True)
            return
        buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["file_secure"] else '✘ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["imdb"] else '✘ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                tmdb_poster_row(settings, str(grp_id)),
                [
                    InlineKeyboardButton('TMDB BACKDROP', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ ON' if settings['tmdb_backdrop'] else '✘ OFF', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["spell_check"] else '✘ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["welcome"] else '✘ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton(f'✔ {auto_delete_minutes(settings)} Mɪɴs' if settings["auto_delete"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Dᴇʟᴇᴛᴇ Tɪᴍᴇ',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}'),
                    InlineKeyboardButton(f'{auto_delete_minutes(settings)} Mɪɴs',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["auto_ffilter"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["is_shortlink"] else '✘ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
        buttons.append([
            InlineKeyboardButton("✖ Close Menu", callback_data=f"close_settings#{grp_id}")
        ])
        settings_markup = InlineKeyboardMarkup(buttons)
        try:
            await _send_settings_to_pm(client, userid, title, settings_markup)
        except Exception:
            logger.exception("Could not send settings menu to private chat")
            await query.answer(
                "I couldn't DM you. Open the bot privately, tap Start, then press Open in PM again.",
                show_alert=True,
            )
            return
        await query.message.edit_text(
            f"<b>Settings for {html.escape(str(title or 'your group'))} were sent to your PM.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        check_pm_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Cʜᴇᴄᴋ PM", url=f"https://t.me/{temp.U_NAME}")
        ]])
        await query.message.edit_reply_markup(check_pm_markup)

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("Uɴᴀᴠᴀɪʟᴀʙʟᴇ", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("Uᴘʟᴏᴀᴅᴇᴅ", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ", callback_data=f"already_available#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("⚠️ Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️", callback_data=f"unalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=await _request_channel_url(client, query.message.link or "https://t.me")),
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Sᴏʀʀʏ Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Sᴏʀʀʏ Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("✅ Uᴘʟᴏᴀᴅᴇᴅ ✅", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=await _request_channel_url(client, query.message.link or "https://t.me")),
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("Rᴇᴏ̨ᴜᴇsᴛ Gʀᴏᴜᴘ Lɪɴᴋ", url="https://t.me/+KzbVzahVdqQ3MmM1")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uᴘʟᴏᴀᴅᴇᴅ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
            InlineKeyboardButton("🟢 Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ 🟢", callback_data=f"alalert#{from_user}")
        ]]
        btn2 = [[
            InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=await _request_channel_url(client, query.message.link or "https://t.me")),
            InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
        ],[
            InlineKeyboardButton("Rᴇᴏ̨ᴜᴇsᴛ Gʀᴏᴜᴘ Lɪɴᴋ", url="https://t.me/rdxmovie_hd")
        ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴏɴ ᴏᴜʀ ʙᴏᴛ's ᴅᴀᴛᴀʙᴀsᴇ. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴏɴ ᴏᴜʀ ʙᴏᴛ's ᴅᴀᴛᴀʙᴀsᴇ. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Uᴘʟᴏᴀᴅᴇᴅ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Uɴᴀᴠᴀɪʟᴀʙʟᴇ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("generate_stream_link"):
        _, file_id = query.data.split(":")
        try:
            log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=file_id)
            fileName = {quote_plus(get_name(log_msg))}
            stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
            download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
            button = [[
                InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
            ],[
                InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
            ]]
            await query.message.edit_reply_markup(InlineKeyboardMarkup(button))
        except Exception as e:
            print(e)
            await query.answer(f"something went wrong\n\n{e}", show_alert=True)
            return
    
    elif query.data == "reqinfo":
        await query.answer(text=script.REQINFO, show_alert=True)

    elif query.data == "select":
        await query.answer(text=script.SELECT, show_alert=True)

    elif query.data == "sinfo":
        await query.answer(text=script.SINFO, show_alert=True)

    elif query.data == "start":
        if PREMIUM_AND_REFERAL_MODE == True:
            buttons = [[
                InlineKeyboardButton('⤬ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ⤬', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
                InlineKeyboardButton('ᴇᴀʀɴ ᴍᴏɴᴇʏ', callback_data="shortlink_info"),
                InlineKeyboardButton('ᴍᴏᴠɪᴇ ɢʀᴏᴜᴘ', url=GRP_LNK)
            ],[
                InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
            ],[
                InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ ᴀɴᴅ ʀᴇғᴇʀʀᴀʟ', callback_data='subscription')
            ],[
                InlineKeyboardButton('ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=CHNL_LNK)
            ]]
        else:
            buttons = [[
                InlineKeyboardButton('⤬ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ⤬', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
                InlineKeyboardButton('ᴇᴀʀɴ ᴍᴏɴᴇʏ', callback_data="shortlink_info"),
                InlineKeyboardButton('ᴍᴏᴠɪᴇ ɢʀᴏᴜᴘ', url=GRP_LNK)
            ],[
                InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
            ],[
                InlineKeyboardButton('ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=CHNL_LNK)
            ]]
        if CLONE_MODE == True:
            buttons.append([InlineKeyboardButton('ᴄʀᴇᴀᴛᴇ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer(MSG_ALRT)

    elif query.data == "clone":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='start')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CLONE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        
    elif query.data == "filters":
        buttons = [[
            InlineKeyboardButton('Mᴀɴᴜᴀʟ FIʟᴛᴇʀ', callback_data='manuelfilter'),
            InlineKeyboardButton('Aᴜᴛᴏ FIʟᴛᴇʀ', callback_data='autofilter')
        ],[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('Gʟᴏʙᴀʟ Fɪʟᴛᴇʀs', callback_data='global_filters')
        ]]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.ALL_FILTERS.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "global_filters":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.GFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "help":
        # Answer the callback before making Telegram API edits so the button does
        # not keep spinning if the media edit takes a moment.
        await query.answer()
        buttons = [[
             InlineKeyboardButton('⚙️ ᴀᴅᴍɪɴ ᴏɴʟʏ 🔧', callback_data='admin'),
         ], [ 
             InlineKeyboardButton('ʀᴇɴᴀᴍᴇ', callback_data='r_txt'),   
             InlineKeyboardButton('sᴛʀᴇᴀᴍ/ᴅᴏᴡɴʟᴏᴀᴅ', callback_data='s_txt') 
         ], [ 
             InlineKeyboardButton('ꜰɪʟᴇ ꜱᴛᴏʀᴇ', callback_data='store_file'),   
             InlineKeyboardButton('ᴛᴇʟᴇɢʀᴀᴘʜ', callback_data='tele') 
         ], [ 
             InlineKeyboardButton('ᴄᴏɴɴᴇᴄᴛɪᴏɴꜱ', callback_data='coct'), 
             InlineKeyboardButton('ꜰɪʟᴛᴇʀꜱ', callback_data='filters')
         ], [
             InlineKeyboardButton('ʏᴛ-ᴅʟ', callback_data='ytdl'), 
             InlineKeyboardButton('ꜱʜᴀʀᴇ ᴛᴇxᴛ', callback_data='share')
         ], [
             InlineKeyboardButton('ꜱᴏɴɢ', callback_data='song'),
             InlineKeyboardButton('ᴇᴀʀɴ ᴍᴏɴᴇʏ', callback_data='shortlink_info')
         ], [
             InlineKeyboardButton('ꜱᴛɪᴄᴋᴇʀ-ɪᴅ', callback_data='sticker'),
             InlineKeyboardButton('ᴊ-ꜱᴏɴ', callback_data='json')
         ], [             
             InlineKeyboardButton('🏠 𝙷𝙾𝙼𝙴 🏠', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        try:
            await client.edit_message_media(
                query.message.chat.id,
                query.message.id,
                InputMediaPhoto(random.choice(PICS))
            )
        except MessageNotModified:
            # random.choice(PICS) can select the same photo already on this
            # message. Keep the existing media and still render the Help text.
            logger.debug("Help menu photo is unchanged; updating the menu text.")
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url=GRP_LNK),
            InlineKeyboardButton('Sᴏᴜʀᴄᴇ Cᴏᴅᴇ', url="https://github.com/RDX-EXPART/Auto-filter-RDX")
        ],[
            InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
            InlineKeyboardButton('Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "subscription":
        buttons = [[
            InlineKeyboardButton('⇚Back', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.SUBSCRIPTION_TXT.format(REFERAL_PREMEIUM_TIME, temp.U_NAME, query.from_user.id, REFERAL_COUNT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='filters'),
            InlineKeyboardButton('Bᴜᴛᴛᴏɴs', callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='manuelfilter')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('ᴇxᴛʀᴀ', callback_data='extra')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "store_file":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.FILE_STORE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "r_txt":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.RENAME_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "s_txt":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.STREAM_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='admin')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT.format(OWNER_LNK, CHNL_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('⟲ Rᴇғʀᴇsʜ', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        filesp = col.count_documents({})
        stats = vjdb.command('dbStats')
        used_dbSize = (stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))
        free_dbSize = 512-used_dbSize
        await query.message.edit_text(
            text=script.SEC_STATUS_TXT.format(total_users, totl_chats, filesp, round(used_dbSize, 2), round(free_dbSize, 2)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "rfrsh":
        await query.answer("Fetching MongoDb DataBase")
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('⟲ Rᴇғʀᴇsʜ', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        filesp = col.count_documents({})
        stats = vjdb.command('dbStats')
        used_dbSize = (stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))
        free_dbSize = 512-used_dbSize
        await query.message.edit_text(
            text=script.SEC_STATUS_TXT.format(total_users, totl_chats, filesp, round(used_dbSize, 2), round(free_dbSize, 2)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "shortlink_info":
        btn = [[
            InlineKeyboardButton("👇Select Your Language 👇", callback_data="laninfo")
        ],[
            InlineKeyboardButton("Tamil", callback_data="tamil_info"),
            InlineKeyboardButton("English", callback_data="english_info"),
            InlineKeyboardButton("Hindi", callback_data="hindi_info")
        ],[
            InlineKeyboardButton("Malayalam", callback_data="malayalam_info"),
            InlineKeyboardButton("Urdu", callback_data="urdu_info"),
            InlineKeyboardButton("Bangla", callback_data="bangladesh_info")
        ],[
            InlineKeyboardButton("Telugu", callback_data="telugu_info"),
            InlineKeyboardButton("Kannada", callback_data="kannada_info"),
            InlineKeyboardButton("Gujarati", callback_data="gujarati_info")
        ],[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SHORTLINK_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "tele":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TELE_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "ytdl":
        buttons = [[
            InlineKeyboardButton('⇍ ʙᴀᴄᴋ ⇏', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text="● ◌ ◌"
        )
        await query.message.edit_text(
            text="● ● ◌"
        )
        await query.message.edit_text(
            text="● ● ●"
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.YTDL_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "share":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SHARE_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "song":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SONG_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "json":
        buttons = [[
            InlineKeyboardButton('⇍ ʙᴀᴄᴋ ⇏', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text="● ◌ ◌"
        )
        await query.message.edit_text(
            text="● ● ◌"
        )
        await query.message.edit_text(
            text="● ● ●"
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.JSON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "sticker":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.STICKER_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "tamil_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TAMIL_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "english_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.ENGLISH_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "hindi_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.HINDI_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "telugu_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TELUGU_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "malayalam_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.MALAYALAM_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "urdu_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.URDU_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "bangladesh_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.BANGLADESH_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "kannada_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.KANNADA_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "gujarati_info":
        btn = [[
            InlineKeyboardButton("⟸ Bᴀᴄᴋ", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="https://t.me/Extra_Ordinary_boy")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.GUJARATI_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data.startswith("close_settings#"):
        try:
            _, grp_id = query.data.split("#", 1)
            user_id = query.from_user.id if query.from_user else None
            if not await _is_group_settings_admin(client, grp_id, user_id):
                await query.answer("Only this group's admins or owner can close the settings menu.", show_alert=True)
                return

            try:
                await query.message.delete()
            except Exception:
                await query.message.edit_reply_markup(reply_markup=None)
            await query.answer("Settings menu closed.")
        except Exception as e:
            logger.exception("Failed to close settings menu: %s", e)
            await query.answer("Could not close the settings menu.", show_alert=True)
        return

    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await _is_group_settings_admin(client, grp_id, user_id):
            await query.answer(
                "Only this group's admins or owner can change its settings.",
                show_alert=True,
            )
            return
        grpid = grp_id

        if set_type == "auto_delete_time":
            # Cycle 5 min <-> 10 min
            await save_group_settings(grpid, "auto_delete_time", 600 if str(status) == "300" else 300)
        elif status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            settings = await get_settings(grpid)
            if set_type == "is_shortlink" and not settings['shortlink']:
                return await query.answer(text = "First Add Your Shortlink Url And Api By /shortlink Command, Then Turn Me On.", show_alert = True)
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["file_secure"] else '✘ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["imdb"] else '✘ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                tmdb_poster_row(settings, str(grp_id)),
                [
                    InlineKeyboardButton('TMDB BACKDROP', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ ON' if settings['tmdb_backdrop'] else '✘ OFF', callback_data=f'setgs#tmdb_backdrop#{settings["tmdb_backdrop"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["spell_check"] else '✘ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["welcome"] else '✘ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton(f'✔ {auto_delete_minutes(settings)} Mɪɴs' if settings["auto_delete"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Dᴇʟᴇᴛᴇ Tɪᴍᴇ',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}'),
                    InlineKeyboardButton(f'{auto_delete_minutes(settings)} Mɪɴs',
                                         callback_data=f'setgs#auto_delete_time#{get_auto_delete_seconds(settings)}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["auto_ffilter"] else '✘ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✔ Oɴ' if settings["is_shortlink"] else '✘ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
            buttons.append([
                InlineKeyboardButton("✖ Close Menu", callback_data=f"close_settings#{grp_id}")
            ])
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer(MSG_ALRT)

async def auto_filter(
    client, name, msg, reply_msg, ai_search, spoll=False,
    media_type=None, metadata=None, title_year=None, series_exact=False,
    metadata_task=None, fallback_search=None,
):
    if media_type not in {"movie", "series"}:
        source_message = (
            getattr(getattr(msg, "message", None), "reply_to_message", None)
            if spoll else msg
        )
        if source_message is not None:
            return await _offer_media_type(client, source_message, reply_msg)
        return
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if not spoll:
        message = msg
        if message.text.startswith("/"): return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            search = name
            search = search.lower()
            find = search.split(" ")
            search = ""
            removes = ["in","upload", "series", "full", "horror", "thriller", "mystery", "print", "file"]
            for x in find:
                if x in removes:
                    continue
                else:
                    search = search + x + " "
            search = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|bro|bruh|broh|helo|that|find|dubbed|link|venum|iruka|pannunga|pannungga|anuppunga|anupunga|anuppungga|anupungga|film|undo|kitti|kitty|tharu|kittumo|kittum|movie|any(one)|with\ssubtitle(s)?)", "", search, flags=re.IGNORECASE)
            search = re.sub(r"\s+", " ", search).strip()
            search = search.replace("-", " ")
            search = search.replace(":", "")
            search = search.replace(".", "")
            filter_updates = {}
            if media_type in {"movie", "series"}:
                filter_updates["media"] = media_type
            if media_type == "series" and series_exact:
                filter_updates["series_exact"] = True
            if title_year:
                # A TMDB-selected movie can have untagged copies in the index.
                # Keep those with the exact release year, but exclude conflicting years.
                filter_updates["year_optional"] = title_year
            if filter_updates:
                search = make_filter_query(search, **filter_updates)
            settings = await get_settings(message.chat.id)
            try:
                files, offset, total_results = await get_search_results(
                    message.chat.id,
                    search,
                    max_results=_filter_page_size(settings),
                    offset=0,
                    filter=True,
                    fast_page=True,
                )
            except Exception:
                logger.exception("File database search failed for query: %s", search)
                try:
                    await reply_msg.edit_text(
                        "⚠️ Search is temporarily unavailable. Please try again shortly."
                    )
                except Exception:
                    logger.exception("Could not replace the search status message")
                return
            if not files and fallback_search and media_type == "movie":
                fallback_query = make_filter_query(
                    fallback_search,
                    media="movie",
                    **({"year_optional": title_year} if title_year else {}),
                )
                try:
                    files, offset, total_results = await get_search_results(
                        message.chat.id,
                        fallback_query,
                        max_results=_filter_page_size(settings),
                        offset=0,
                        filter=True,
                        fast_page=True,
                    )
                    if files:
                        search = fallback_query
                except Exception:
                    logger.exception("Fallback movie title search failed: %s", fallback_query)
            if metadata_task is not None:
                try:
                    detailed = await asyncio.wait_for(
                        asyncio.shield(metadata_task),
                        timeout=0.75,
                    )
                    if detailed:
                        metadata = detailed
                except asyncio.TimeoutError:
                    # The candidate already carries title, year, poster and overview.
                    # Do not hold the result for a slow TMDB details/images request.
                    pass
                except Exception:
                    logger.exception("TMDB metadata enrichment failed; using search result data")
            if not files:
                if metadata:
                    return await _send_metadata_fallback(
                        reply_msg, message, metadata, name,
                    )
                if media_type in {"movie", "series"}:
                    media_label = "movie" if media_type == "movie" else "series"
                    return await reply_msg.edit_text(
                        f"⚠️ No {media_label} files were found for "
                        f"“{html.escape(str(name), quote=False)}”. "
                        "No matching release information was found on TMDB.",
                        reply_markup=_google_release_markup(name, media_type=media_type),
                        parse_mode=enums.ParseMode.HTML,
                    )
                if settings["spell_check"]:
                    try:
                        return await advantage_spell_chok(
                            client, name, msg, reply_msg, ai_search
                        )
                    except Exception:
                        logger.exception("Spell-check fallback failed for query: %s", search)
                        try:
                            return await reply_msg.edit_text(
                                f"⚠️ No files found for “{name}”. "
                                "Spell check is temporarily unavailable."
                            )
                        except Exception:
                            return
                else:
                    return await reply_msg.edit_text(f"**⚠️ No File Found For Your Query - {name}**\n**Make Sure Spelling Is Correct.**")
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
        settings = await get_settings(message.chat.id)
        await msg.message.delete()
    pre = 'filep' if settings['file_secure'] else 'file'
    key = f"{message.chat.id}-{message.id}"
    req = message.from_user.id if message.from_user else 0
    FRESH[key] = search
    SEARCH_METADATA[key] = metadata
    BUTTONS.pop(key, None)
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    typed_media = parse_filter_query(search)[1].get("media")
    if typed_media:
        btn = await _typed_result_keyboard(
            files, key, search, settings, pre, total_results, offset, req,
            include_files=False, include_back=False,
        )
    else:
        if settings["button"]:
            btn = [
                [
                    InlineKeyboardButton(
                        text=_file_button_text(file), callback_data=f'{pre}#{file["file_id"]}'
                    ),
                ]
                for file in files
            ]
        else:
            btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
                InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}"),
            InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
        btn.insert(2, [InlineKeyboardButton("🗂 Combined Files", callback_data=f"combined#{key}")])
        if offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                    )
                else:
                    btn.append(
                        [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                    )
            except KeyError:
                await save_group_settings(message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}")]
                )
        else:
            btn.append([InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄", callback_data="pages")])
        btn.append([InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")])
    imdb = None
    if settings["imdb"] and metadata is None:
        try:
            imdb = await get_poster(search, file=(files[0])['file_name'])
        except Exception:
            logger.exception('IMDb lookup failed for %r; falling back to TMDB metadata', search)
        if not imdb:
            logger.info('IMDb metadata unavailable for %r; falling back to TMDB metadata', search)
    tmdb_backdrop_image = None
    tmdb_visuals_on = tmdb_visuals_enabled(settings)
    # A title chosen from TMDB already has useful metadata. Keep that data for
    # the result card even when poster/backdrop visuals are switched off.
    tmdb_match = metadata
    tmdb_backdrop_enabled = bool(settings.get('tmdb_backdrop', False))
    # TMDB is needed for the backdrop setting, and as the fallback when IMDb is on
    # but returned no metadata or no poster. Without it the card had no poster and
    # no runtime, language or genre.
    need_tmdb = tmdb_visuals_on and not tmdb_match and (tmdb_backdrop_enabled or (
        bool(settings["imdb"]) and (not imdb or not imdb.get("poster"))
    ))
    if need_tmdb:
        try:
            tmdb_title, selected_filters = parse_filter_query(search)
            sample_name = str(files[0].get("file_name", ""))
            is_tv = bool(
                selected_filters.get("season")
                or selected_filters.get("episode")
                or re.search(
                    r"(?i)(?<![a-z0-9])(?:s|season)[ ._-]*0*\d{1,3}[ ._-]*(?:(?:e|ep|episode)[ ._-]*0*\d{1,4})",
                    sample_name,
                )
                or re.search(
                    r"(?i)(?<![a-z0-9])(?:e|ep|episode)[ ._-]*0*\d{1,4}(?!\d)",
                    sample_name,
                )
            )
            if is_tv:
                tmdb_match = await get_tmdb_tv(tmdb_title or search, file=sample_name)
            else:
                # Movie or series? Let TMDB's multi search decide (reference-style scoring).
                tmdb_match = await get_tmdb_any(tmdb_title or search, file=sample_name)
        except Exception:
            logger.exception('TMDB canonical backdrop lookup failed; continuing with existing poster fallback')
    # Backdrop artwork is fetched whenever TMDB information is in use and the switch is on.
    # It is kept outside the lookup block above, because the metadata chosen in the
    # Movie/Series step already fills tmdb_match and that block would then never run.
    if tmdb_match and tmdb_backdrop_enabled and not tmdb_backdrop_image:
        try:
            candidates = []
            for url in [tmdb_match.get("backdrop")] + list((tmdb_match.get("images") or {}).get("backdrops") or []) \
                    + [image_url(tmdb_match.get("backdrop_path"), "w1280")]:
                if url and url not in candidates:
                    candidates.append(url)
            image_deadline = asyncio.get_running_loop().time() + 4
            for url in candidates[:3]:
                remaining = image_deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    tmdb_backdrop_image = await asyncio.wait_for(
                        fetch_tmdb_image(url, backdrop=True),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    logger.info("Backdrop image lookup timed out; continuing without it")
                    break
                if tmdb_backdrop_image:
                    break
        except Exception:
            logger.exception('TMDB backdrop fetch failed; continuing without a backdrop image')
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
    remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
    TEMPLATE = script.IMDB_TEMPLATE_TXT
    if imdb:
        file_names = " ".join(str(item.get("file_name", "")) for item in files).lower()
        quality = " • ".join(
            item for item in ("2160p", "1080p", "720p", "480p") if item in file_names
        ) or "Not specified"
        cap = TEMPLATE.format(
            qurey=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
        temp.IMDB_CAP[message.from_user.id] = cap
        cap += (
            f"\n{SEPARATOR}\n"
            f"👤 <b>Requested by:</b> {message.from_user.mention if message.from_user else 'User'}\n"
            f"📢 <b>Powered by:</b> {html.escape(message.chat.title or temp.B_NAME, quote=False)}"
        )
        if typed_media or not settings["button"]:
            file_heading = (
                "Your Series Files"
                if media_type == "series" or (tmdb_match and tmdb_match.get("media_type") == "tv")
                else "Your Movie Files"
            )
            cap += f"<b>\n\n<u>🍿 {file_heading} 👇</u></b>\n"
            for file in files:
                cap += f"<b>\n\n📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {_filter_filename(file)}\n</a></b>"
    else:
        # Keep the same metadata layout even if IMDb/TMDB data is unavailable.
        requester = message.from_user.mention if message.from_user else "User"
        cap = build_tmdb_card(
            {"title": search, "media_type": "tv" if media_type == "series" else "movie"},
            files,
            search,
            requester,
            remaining_seconds,
            message.chat.title or temp.B_NAME,
        )
        if typed_media or not settings["button"]:
            file_heading = (
                "Your Series Files"
                if media_type == "series" or (tmdb_match and tmdb_match.get("media_type") == "tv")
                else "Your Movie Files"
            )
            cap += f"\n\n<b><u>🍿 {file_heading} 👇</u></b>\n\n"
            for file in files:
                cap += (
                    f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>"
                    f"[{get_size(file['file_size'])}] {_filter_filename(file)}\n\n</a></b>"
                )

    result_message = None
    extra_messages = []
    markup = InlineKeyboardMarkup(btn)
    if tmdb_match or imdb:
        requester = message.from_user.mention if message.from_user else "User"
        card_data = dict(tmdb_match or {})
        if not tmdb_match:
            runtime_text = str(imdb.get("runtime") or "")
            runtime_match = re.search(r"\d+", runtime_text)
            languages = [item.strip() for item in str(imdb.get("languages") or "").split(",") if item.strip()]
            imdb_rating_match = re.search(r"\d+(?:\.\d+)?", str(imdb.get("rating") or ""))
            card_data = {
                "title": imdb.get("title") or search,
                "year": imdb.get("year"),
                "rating": float(imdb_rating_match.group()) if imdb_rating_match else 0,
                "votes": imdb.get("votes") or 0,
                "genres": imdb.get("genres") or "",
                "languages": languages,
                "runtime": int(runtime_match.group()) if runtime_match else 0,
                "media_type": "tv" if media_type == "series" else "movie",
            }
        elif imdb:
            imdb_rating_match = re.search(r"\d+(?:\.\d+)?", str(imdb.get("rating") or ""))
            if imdb_rating_match:
                card_data["rating"] = float(imdb_rating_match.group())
                card_data["votes"] = imdb.get("votes") or card_data.get("votes", 0)

        # Keep poster, full metadata, complete filenames and filter controls in one
        # photo message. The per-page file count yields to Telegram's caption limit.
        ratings = None
        # Always look up IMDb / Rotten Tomatoes scores (also when the title was picked
        # from the Movie/Series chooser, where `metadata` is already filled).
        try:
            omdb_imdb_id = (imdb or {}).get("imdb_id") or card_data.get("imdb_id")
            if not omdb_imdb_id and card_data.get("id"):
                try:
                    omdb_imdb_id = await asyncio.wait_for(
                        get_tmdb_imdb_id(
                            card_data.get("id"),
                            "tv" if card_data.get("media_type") == "tv" else "movie",
                        ),
                        timeout=3,
                    )
                except Exception:
                    omdb_imdb_id = None
            ratings = await asyncio.wait_for(
                get_omdb_ratings(
                    imdb_id=omdb_imdb_id,
                    title=card_data.get("title"),
                    year=card_data.get("year"),
                ),
                timeout=6,
            )
            if not ratings:
                logger.warning(
                    "OMDb returned no ratings for %r (%s) imdb_id=%s",
                    card_data.get("title"), card_data.get("year"), omdb_imdb_id,
                )
        except asyncio.TimeoutError:
            logger.warning("OMDb ratings lookup timed out; continuing without ratings")
        except Exception:
            logger.exception("Optional OMDb ratings lookup failed")
        card = build_tmdb_card(
            card_data,
            files,
            search,
            requester,
            remaining_seconds,
            message.chat.title or temp.B_NAME,
            ratings=ratings,
        )
        # TMDB-selected Movie/Series searches show a linked text list so full
        # filenames are not lost to Telegram's 64-character button labels.
        text_mode = not settings["button"] and not typed_media
        files_text = ""
        overflow_files = []
        if text_mode:
            file_heading = (
                "Your Series Files"
                if media_type == "series" or card_data.get("media_type") == "tv"
                else "Your Movie Files"
            )
            heading_text = f"<b><u>🍿 {file_heading} 👇</u></b>"

            def _file_line(file, name_limit):
                title = _filter_filename(file)
                if name_limit and len(title) > name_limit:
                    title = title[: name_limit - 1].rstrip() + "…"
                title = html.escape(title, quote=False)
                size = html.escape(get_size(file.get("file_size", 0)), quote=False)
                file_url = html.escape(
                    f"https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}",
                    quote=True,
                )
                return f"\n\n📁 <a href='{file_url}'>[{size}] {title}</a>"

            def _visible(text):
                return len(html.unescape(re.sub(r"<[^>]*>", "", text)))

            # Try full names first, then shorter names, so every file stays in the main text.
            for name_limit in (None, 40, 28):
                trial = heading_text
                overflow_files = []
                for file in files:
                    line = _file_line(file, name_limit)
                    if _visible(card + "\n\n" + trial + line) <= 1024:
                        trial += line
                    else:
                        overflow_files.append(file)
                files_text = trial
                if not overflow_files:
                    break
            # Last resort only, when even the shortest names do not fit.
            if overflow_files:
                for file in overflow_files:
                    btn.append([
                        InlineKeyboardButton(
                            _file_button_text(file),
                            callback_data=f'{pre}#{file["file_id"]}',
                        )
                    ])
                markup = InlineKeyboardMarkup(btn)

        card_caption = card + ("\n\n" + files_text if text_mode else "")
        card_photo = (
            tmdb_backdrop_image
            or (imdb.get("poster") if imdb else None)
            or (tmdb_match.get("poster") if tmdb_match and settings.get("tmdb_poster") else None)
        )
        text_files, text_offset, text_total = files, offset, total_results
        text_markup = markup
        compact_photo = False
        if typed_media and card_photo:
            try:
                for photo_page_size in range(_FULL_NAME_PHOTO_PAGE_SIZE, 0, -1):
                    photo_files, photo_offset, photo_total = await get_search_results(
                        message.chat.id,
                        search,
                        max_results=photo_page_size,
                        offset=0,
                        filter=True,
                        fast_page=True,
                    )
                    if not photo_files:
                        break
                    try:
                        photo_caption = _photo_caption(
                            card, photo_files, search,
                        )
                    except ValueError:
                        continue
                    photo_rows = await _typed_result_keyboard(
                        photo_files, key, search, settings, pre, photo_total,
                        photo_offset, req, page_size=photo_page_size,
                        include_files=False, include_back=False,
                    )
                    files, offset, total_results = photo_files, photo_offset, photo_total
                    temp.GETALL[key] = files
                    markup = InlineKeyboardMarkup(photo_rows)
                    card_caption = photo_caption
                    PHOTO_PAGE_SIZES[key] = photo_page_size
                    compact_photo = True
                    break
                if not compact_photo:
                    raise RuntimeError("Full filenames do not fit in a poster caption")
            except Exception:
                logger.exception("Could not prepare full-name poster caption; using text fallback")
                card_photo = None
        if card_photo:
            try:
                result_message = await message.reply_photo(
                    photo=card_photo,
                    caption=card_caption,
                    reply_markup=markup,
                )
            except Exception:
                logger.exception("Movie card image send failed; keeping result in text")
                if compact_photo:
                    files, offset, total_results = text_files, text_offset, text_total
                    temp.GETALL[key] = files
                    markup = text_markup
        if result_message is None:
            try:
                fallback_text = (
                    f"{card}\n\n{_full_filename_list(search, files)}"
                    if typed_media else card_caption
                )
                result_message = await reply_msg.edit_text(
                    text=fallback_text,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )
            except Exception:
                logger.exception("Movie card text fallback failed")

    if result_message is None:
        try:
            result_message = await reply_msg.edit_text(
                text=cap, reply_markup=markup, disable_web_page_preview=True
            )
        except Exception:
            logger.exception("Could not render the file search result")
            return

    _remember_result_page_size(
        key, files, offset, fallback=_filter_page_size(settings),
    )
    await _finish_auto_filter_result(
        result_message, message, reply_msg, settings, extra_messages,
        client=client,
    )

async def advantage_spell_chok(client, name, msg, reply_msg, vj_search):
    mv_id = msg.id
    mv_rqst = name
    reqstr1 = msg.from_user.id if msg.from_user else 0
    reqstr = await client.get_users(reqstr1)
    settings = await get_settings(msg.chat.id)
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)  # plis contribute some common words
    query = query.strip() + " movie"
    try:
        movies = await get_poster(mv_rqst, bulk=True)
    except Exception as e:
        logger.exception(e)
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if NO_RESULTS_MSG:
            await client.send_message(chat_id=LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    movielist = []
    if not movies:
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if NO_RESULTS_MSG:
            await client.send_message(chat_id=LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    movielist += [movie.get('title') for movie in movies]
    movielist += [f"{movie.get('title')} {movie.get('year')}" for movie in movies]
    SPELL_CHECK[mv_id] = movielist
    if AI_SPELL_CHECK == True and vj_search == True:
        vj_search_new = False
        vj_ai_msg = await reply_msg.edit_text("<b><i>I Am Trying To Find Your Movie With Your Wrong Spelling.</i></b>")
        movienamelist = []
        movienamelist += [movie.get('title') for movie in movies]
        for techvj in movienamelist:
            try:
                mv_rqst = mv_rqst.capitalize()
            except:
                pass
            if mv_rqst.startswith(techvj[0]):
                await auto_filter(client, techvj, msg, reply_msg, vj_search_new)
                break
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if NO_RESULTS_MSG:
            await client.send_message(chat_id=LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=movie_name.strip(),
                    callback_data=f"spol#{reqstr1}#{k}",
                )
            ]
            for k, movie_name in enumerate(movielist)
        ]
        btn.append([InlineKeyboardButton(text="Close", callback_data=f'spol#{reqstr1}#close_spellcheck')])
        spell_check_del = await reply_msg.edit_text(
            text=script.CUDNT_FND.format(mv_rqst),
            reply_markup=InlineKeyboardMarkup(btn)
        )
        # "Did you mean" suggestions: use the configured Auto Delete time through the persistent
        # scheduler (this used to block the handler with a hard-coded sleep(600)).
        if settings.get('auto_delete', True):
            await schedule_delete(
                client, spell_check_del.chat.id, [spell_check_del.id],
                get_auto_delete_seconds(settings), reason="spell-check",
            )

async def manual_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            joelkb = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)

                        else:
                            button = eval(btn)
                            joelkb = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                    elif btn == "[]":
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            protect_content=True if settings["file_secure"] else False,
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                        except KeyError:
                            grpid = await active_connection(str(message.from_user.id))
                            await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                    else:
                        button = eval(btn)
                        joelkb = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                        except KeyError:
                            grpid = await active_connection(str(message.from_user.id))
                            await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)

                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False


# These group -1 handlers intentionally supersede the older, overlapping
# callback handlers above. The previous language/quality callbacks both used
# "fl#", rewrote spaces to underscores, and queried raw suffixes; that broke
# alias matching, navigation, and quality buttons. Keep one typed state path.
_FILTER_HANDLERS = r"^(?:years#|qualities#|episodes#|languages#|fy#|fe#|fl#|seasons#|fs#|fq#|combined#|combinedoff#|fh#|epage#|fback#)"
_EPISODE_MENU_SIZE = 24
def _same_message(a, b):
    """True when both objects point at the same Telegram message.

    ``reply_msg.edit_text()`` returns a *new* Message object for the very same
    Telegram message, so identity (``is``) is not enough: compare chat + id.
    """
    if a is None or b is None:
        return False
    if a is b:
        return True
    a_id, b_id = getattr(a, "id", None), getattr(b, "id", None)
    a_chat = getattr(getattr(a, "chat", None), "id", None)
    b_chat = getattr(getattr(b, "chat", None), "id", None)
    return a_id is not None and a_id == b_id and a_chat == b_chat


async def _finish_auto_filter_result(result_message, request_message, spinner, settings,
                                     extra_messages=(), client=None):
    """Remove the spinner and schedule cleanup of every message that belongs to this result.

    Cleanup goes through ``utils.schedule_delete`` (persistent queue + one background
    worker) instead of a fire-and-forget ``asyncio.create_task`` timer, which could be
    garbage-collected, was lost on every restart, and hid all errors.
    """
    # Only remove the "Searching..." spinner when the result is a DIFFERENT message (photo
    # reply). When the result was produced by editing the spinner itself, deleting it here
    # would wipe the result right away.
    if not _same_message(result_message, spinner):
        try:
            await spinner.delete()
        except Exception as error:
            logger.warning("Could not delete the 'Searching' message: %s: %s", type(error).__name__, error)

    if not settings.get("auto_delete", True):
        logger.info("Auto-delete is OFF for this chat; search results will not be removed automatically")
        return

    delay = get_auto_delete_seconds(settings)

    client = client or getattr(result_message, "_client", None)
    by_chat = {}
    for item in (result_message, request_message, *extra_messages):
        if item is None:
            continue
        chat_id = getattr(getattr(item, "chat", None), "id", None)
        message_id = getattr(item, "id", None)
        if chat_id is None or message_id is None:
            logger.warning("Auto-delete: skipped a message without chat/message id")
            continue
        by_chat.setdefault(chat_id, []).append(message_id)
    for chat_id, message_ids in by_chat.items():
        try:
            await schedule_delete(client, chat_id, message_ids, delay, reason="search-result")
        except Exception:
            logger.exception("Auto-delete scheduling failed for chat=%s (the result stays visible)", chat_id)


def _is_card_message(message):
    """True for the unified TMDB card (photo whose caption carries the card layout)."""
    caption = getattr(message, "caption", None) or ""
    return bool(getattr(message, "photo", None)) and SEPARATOR in caption


def _effective_settings(settings, message):
    """Keep the card's file list in its photo caption rather than a second text post."""
    if _is_card_message(message):
        return {**settings, "button": True}
    return settings


def _filter_page_size(settings):
    """Files per result page for movie and series text lists."""
    return 15


def _remember_result_page_size(key, files, next_offset, fallback=15):
    """Keep the initial page size for the lifetime of a search result.

    `next_offset` is the first page's size when a next page exists. Inferring it
    once avoids recalculating later pages from a different display mode or group
    setting (for example, a 5-file poster page being fetched as 15 files).
    """
    try:
        page_size = int(next_offset) if next_offset not in ("", None) else 0
    except (TypeError, ValueError):
        page_size = 0
    if page_size <= 0:
        try:
            page_size = len(files or [])
        except TypeError:
            page_size = 0
    if page_size <= 0:
        try:
            page_size = int(fallback or 15)
        except (TypeError, ValueError):
            page_size = 15
    page_size = max(1, page_size)
    RESULT_PAGE_SIZES[key] = page_size
    return page_size


def _get_result_page_size(key, settings=None, current_files=None, fallback=15):
    """Use one stable page size for forward, back, and filtered result pages."""
    try:
        page_size = int(RESULT_PAGE_SIZES.get(key, 0) or 0)
    except (TypeError, ValueError):
        page_size = 0
    if page_size > 0:
        return page_size
    try:
        page_size = len(current_files or [])
    except TypeError:
        page_size = 0
    if page_size > 0:
        RESULT_PAGE_SIZES[key] = page_size
        return page_size
    try:
        page_size = int(fallback or 15)
    except (TypeError, ValueError):
        page_size = 15
    page_size = max(1, page_size)
    RESULT_PAGE_SIZES[key] = page_size
    return page_size


def _filter_filename(file):
    return clean_display_filename(file.get("file_name", ""))


def _file_button_text(file):
    name = " ".join(
        word for word in _filter_filename(file).split()
        if not word.startswith(("[", "@")) and not word.startswith("www.")
    )
    label = f"[{get_size(file.get('file_size', 0))}] {name}".strip()
    # Telegram clients enforce a short inline-button label; keep callback data
    # intact and truncate only the display text.
    return label if len(label) <= 64 else label[:61].rstrip() + "…"


def _filtered_result_keyboard(files, key, settings, pre, total, next_offset, user_id, offset=0, page_size=None):
    rows = [
        [
            InlineKeyboardButton("📦 Send All", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🌐 Languages", callback_data=f"languages#{key}"),
            InlineKeyboardButton("📅 Years", callback_data=f"years#{key}"),
        ],
        [
            InlineKeyboardButton("🎞 Quality", callback_data=f"qualities#{key}"),
            InlineKeyboardButton("🎬 Episodes", callback_data=f"episodes#{key}"),
            InlineKeyboardButton("📺 Seasons", callback_data=f"seasons#{key}"),
        ],
    ]
    _, active_filters = parse_filter_query(BUTTONS.get(key) or FRESH.get(key) or "")
    rows.append([
        InlineKeyboardButton(
            "📂 All Files" if active_filters.get("combined") else "🗂 Combined Files",
            callback_data=f"combinedoff#{key}" if active_filters.get("combined") else f"combined#{key}",
        )
    ])
    if settings.get("button"):
        rows.extend([
            [InlineKeyboardButton(_file_button_text(file), callback_data=f"{pre}#{file['file_id']}")]
            for file in files
        ])

    page_size = page_size or _filter_page_size(settings)
    pages = max(1, math.ceil(int(total or 0) / page_size))
    current_page = offset // page_size + 1
    if next_offset not in ("", None):
        nav = [
            InlineKeyboardButton("PAGE", callback_data="pages"),
            InlineKeyboardButton(f"{current_page}/{pages}", callback_data="pages"),
            InlineKeyboardButton("NEXT ➢", callback_data=f"next_{user_id}_{key}_{next_offset}"),
        ]
        if offset > 0:
            nav.insert(0, InlineKeyboardButton("BACK", callback_data=f"next_{user_id}_{key}_{max(0, offset - page_size)}"))
    else:
        nav = [InlineKeyboardButton("NO MORE PAGES", callback_data="pages")]
    rows.append(nav)
    rows.append([InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")])
    return rows


def _filter_menu_rows(kind, key, page=0, values=None, episode_counts=None):
    labels = {
        "language": "Select a language",
        "year": "Select a year",
        "quality": "Select a quality",
        "season": "Select a season",
        "episode": "Select an episode",
    }
    values = values or {}
    rows = [[InlineKeyboardButton(labels[kind], callback_data="ident")]]
    values_key = {
        "language": "languages",
        "year": "years",
        "quality": "qualities",
        "season": "seasons",
        "episode": "episodes",
    }[kind]
    choices = list(values.get(values_key) or [])
    if not choices:
        rows.append([InlineKeyboardButton("No matching values found", callback_data="ident")])
    elif kind == "episode":
        page_count = max(1, math.ceil(len(choices) / _EPISODE_MENU_SIZE))
        page = min(max(0, int(page)), page_count - 1)
        start = page * _EPISODE_MENU_SIZE
        page_values = choices[start:start + _EPISODE_MENU_SIZE]
        for index in range(0, len(page_values), 4):
            rows.append([
                InlineKeyboardButton(
                    f"E{int(value):02d}",
                    callback_data=f"fe#{int(value)}#{key}",
                )
                for value in page_values[index:index + 4]
            ])
        if page_count > 1:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton("‹ Prev", callback_data=f"epage#{page - 1}#{key}"))
            nav.append(InlineKeyboardButton(f"{page + 1}/{page_count}", callback_data="ident"))
            if page + 1 < page_count:
                nav.append(InlineKeyboardButton("Next ›", callback_data=f"epage#{page + 1}#{key}"))
            rows.append(nav)
    else:
        row_size = 2 if kind in {"language", "quality", "season"} else 4
        for index in range(0, len(choices), row_size):
            row = []
            for value in choices[index:index + row_size]:
                if kind == "language":
                    language_labels = {
                        "hin": "Hindi", "eng": "English", "tam": "Tamil", "tel": "Telugu",
                        "mal": "Malayalam", "kan": "Kannada", "bangla": "Bengali",
                        "urdu": "Urdu", "mar": "Marathi", "pun": "Punjabi",
                        "guj": "Gujarati", "bhojpuri": "Bhojpuri", "oriya": "Odia",
                        "asm": "Assamese", "kor": "Korean", "chi": "Chinese",
                        "jap": "Japanese", "ara": "Arabic", "spa": "Spanish",
                        "fre": "French", "ger": "German", "por": "Portuguese",
                        "rus": "Russian", "dual": "Dual Audio", "multi": "Multi Audio",
                    }
                    label = language_labels.get(str(value), str(value).title())
                    callback = f"fl#{str(value).lower()}#{key}"
                elif kind == "year":
                    label, callback = str(value), f"fy#{value}#{key}"
                elif kind == "quality":
                    label, callback = str(value).upper(), f"fq#{str(value).lower()}#{key}"
                else:
                    label, callback = f"Season {int(value):02d}", f"fs#{int(value)}#{key}"
                row.append(InlineKeyboardButton(label, callback_data=callback))
            if row:
                rows.append(row)
    if kind == "season":
        # Choosing a season keeps the current result and its other filters. All Seasons
        # clears only the season, and Back returns to the same result.
        rows.append([InlineKeyboardButton("All Seasons", callback_data=f"fs#all#{key}")])
        rows.append([InlineKeyboardButton("↩ Back to Results", callback_data=f"fback#{key}")])
    else:
        rows.append([InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")])
    return rows


def _filter_loading_markup(key, label="⏳ Loading…"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="ident")],
        [InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")],
    ])


def _merge_filter_values(available, files):
    """Combine database discovery with values visible in the current result page."""
    available = available or {}
    list_keys = ("languages", "qualities", "years", "seasons", "episodes")
    merged = {name: set(available.get(name) or []) for name in list_keys}
    combined = bool(available.get("combined"))
    for file in files or []:
        for field in ("file_name", "caption"):
            values = extract_filter_values(file.get(field, ""))
            for name in list_keys:
                merged[name].update(values.get(name) or [])
            combined = combined or bool(values.get("combined"))

    quality_order = {
        "360p": 0, "480p": 1, "720p": 2, "1080p": 3, "1440p": 4, "2160p": 5,
    }
    return {
        "languages": sorted(merged["languages"]),
        "qualities": sorted(
            merged["qualities"],
            key=lambda value: quality_order.get(value, 99),
        ),
        "years": sorted(merged["years"]),
        "seasons": sorted(merged["seasons"]),
        "episodes": sorted(merged["episodes"]),
        "combined": combined,
    }


async def _typed_result_keyboard(
    files, key, search, settings, pre, total, next_offset, user_id,
    offset=0, page_size=None, include_files=True, include_back=True,
):
    """Build a fast Movie/Series keyboard; warm the first filter scan in the background."""
    _, selected = parse_filter_query(search)
    media = selected.get("media")
    available = get_cached_filter_values(
        search, max_scan=_FILTER_VALUE_SCAN_LIMIT,
    )
    pending = available is None
    if pending:
        _schedule_filter_value_warmup(search)
    available = _merge_filter_values(available, files)
    rows = []
    if files:
        rows.append([InlineKeyboardButton("📦 Send All", callback_data=f"sendfiles#{key}")])

    quality_button = (
        InlineKeyboardButton("🎞 Quality", callback_data=f"qualities#{key}")
        if pending or available["qualities"] else None
    )
    language_button = (
        InlineKeyboardButton("🌐 Language", callback_data=f"languages#{key}")
        if pending or available["languages"] else None
    )
    year_button = (
        InlineKeyboardButton("📅 Year", callback_data=f"years#{key}")
        if pending or available["years"] else None
    )
    if media == "movie":
        # Movie: Quality, Language, Year in one row. No Season, Episode or Combined.
        top = [button for button in (quality_button, language_button, year_button) if button]
        if top:
            rows.append(top)
    else:
        # Series: Season and Episode first, then Quality, then Year and Language.
        # Episode is always listed when the database has episodes. Choosing it before a
        # season is picked asks for a season first (see episodes_cb_handler).
        series_filters = []
        if pending or available["seasons"]:
            chosen = selected.get("season")
            season_label = f"📺 Season {int(chosen):02d}" if chosen and str(chosen).isdigit() else "📺 Season"
            series_filters.append(InlineKeyboardButton(season_label, callback_data=f"seasons#{key}"))
        if pending or available["episodes"]:
            series_filters.append(InlineKeyboardButton("🎬 Episode", callback_data=f"episodes#{key}"))
        if series_filters:
            rows.append(series_filters)
        if quality_button:
            rows.append([quality_button])
        second = [button for button in (year_button, language_button) if button]
        if second:
            rows.append(second)
        if pending or available["combined"]:
            label = "📂 All Files" if selected.get("combined") else "🗂 Combined File"
            action = "combinedoff" if selected.get("combined") else "combined"
            rows.append([InlineKeyboardButton(label, callback_data=f"{action}#{key}")])

    if include_files and settings.get("button", True):
        rows.extend([
            [InlineKeyboardButton(_file_button_text(file), callback_data=f"{pre}#{file['file_id']}")]
            for file in files
        ])

    page_size = page_size or _filter_page_size(settings)
    try:
        current_offset = max(0, int(offset or 0))
    except (TypeError, ValueError):
        current_offset = 0
    try:
        next_value = int(next_offset) if next_offset not in ("", None) else None
    except (TypeError, ValueError):
        next_value = None
    current_page = current_offset // page_size + 1
    nav = []
    if current_offset > 0:
        nav.append(InlineKeyboardButton(
            "⌫ Back",
            callback_data=f"next_{user_id}_{key}_{max(0, current_offset - page_size)}",
        ))
    nav.append(InlineKeyboardButton(f"Page {current_page}", callback_data="pages"))
    if next_value is not None:
        nav.append(InlineKeyboardButton(
            "Next ➢",
            callback_data=f"next_{user_id}_{key}_{next_value}",
        ))
    else:
        nav.append(InlineKeyboardButton("No more pages", callback_data="pages"))
    rows.append(nav)
    if include_back:
        rows.append([InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")])
    return rows


def _prune_media_searches():
    now = time.time()
    for key, state in list(MEDIA_SEARCH.items()):
        if now - state.get("created", 0) > 1800:
            MEDIA_SEARCH.pop(key, None)


def _media_search_source_ids(key):
    """The search key contains the originating Telegram chat and message ids."""
    try:
        chat_id, message_id = str(key).rsplit("-", 1)
        return int(chat_id), int(message_id)
    except (TypeError, ValueError):
        return None, None


async def _load_media_search_state(client, key, prompt_message=None):
    """Load an in-memory search, or rebuild it from the original user message.

    Heroku restarts (and private-message prompts that are not Telegram replies) can
    leave a valid callback without its process-local state or reply_to_message.
    """
    now = time.time()
    state = MEDIA_SEARCH.get(key)
    if state:
        try:
            if now - float(state.get("created", now)) <= 1800:
                return state
        except (TypeError, ValueError):
            return state
        MEDIA_SEARCH.pop(key, None)

    source = getattr(prompt_message, "reply_to_message", None)
    chat_id, message_id = _media_search_source_ids(key)
    if source is None and chat_id is not None and message_id is not None:
        try:
            source = await client.get_messages(chat_id, message_id)
        except Exception:
            logger.debug("Could not restore media-search source %s", key, exc_info=True)
            return None
    if not source or not getattr(source, "from_user", None) or not getattr(source, "text", None):
        return None

    created = now
    source_date = getattr(source, "date", None)
    if source_date is not None:
        try:
            created = float(source_date.timestamp())
        except (AttributeError, TypeError, ValueError, OSError):
            pass
    if now - created > 1800 or created > now + 60:
        return None

    source_chat = getattr(source, "chat", None)
    state = {
        "query": str(source.text).strip(),
        "owner_id": source.from_user.id,
        "created": created,
        "media_type": None,
        "candidates": [],
        "source_chat_id": getattr(source_chat, "id", chat_id),
        "source_message_id": getattr(source, "id", message_id),
    }
    MEDIA_SEARCH[key] = state
    return state


async def _get_media_search_source(client, key, state, prompt_message=None):
    """Find the original query even when the bot prompt is not a reply in PM."""
    source = getattr(prompt_message, "reply_to_message", None)
    if source is not None:
        return source

    chat_id = state.get("source_chat_id")
    message_id = state.get("source_message_id")
    if chat_id is None or message_id is None:
        chat_id, message_id = _media_search_source_ids(key)
    if chat_id is None or message_id is None:
        return None
    try:
        return await client.get_messages(chat_id, message_id)
    except Exception:
        logger.debug("Could not fetch original media-search message %s", key, exc_info=True)
        return None


async def _offer_media_type(client, message, reply_message=None):
    """Ask the requester to choose Movie or Series before searching indexed files."""
    if not getattr(message, "from_user", None) or not getattr(message, "text", None):
        return
    query_text = str(message.text).strip()
    if (
        not query_text
        or len(query_text) > 100
        or query_text.startswith("/")
        or re.findall(r"((^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", query_text)
    ):
        return

    _prune_media_searches()
    key = f"{message.chat.id}-{message.id}"
    MEDIA_SEARCH[key] = {
        "query": query_text,
        "owner_id": message.from_user.id,
        "created": time.time(),
        "media_type": None,
        "candidates": [],
        "source_chat_id": message.chat.id,
        "source_message_id": message.id,
    }
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Movie", callback_data=f"mt#movie#{key}"),
            InlineKeyboardButton("📺 Series", callback_data=f"mt#series#{key}"),
        ]
    ])
    if reply_message is not None:
        try:
            return await _edit_quietly(
                reply_message.edit_text,
                text="Choose what you want to search for:",
                reply_markup=markup,
            )
        except Exception:
            logger.exception("Could not update search prompt; sending a new prompt")
    return await message.reply_text("Choose what you want to search for:", reply_markup=markup)


def _candidate_year(candidate, media_type):
    date_value = candidate.get("release_date" if media_type == "movie" else "first_air_date") or ""
    return str(date_value)[:4] if str(date_value)[:4].isdigit() else ""


def _candidate_file_year(candidate, media_type):
    """Only a movie's release year should constrain the filename search.

    A TV show's first-air year is metadata for the series, not a filename year
    shared by every episode or season.
    """
    if media_type != "movie":
        return None
    return _candidate_year(candidate, media_type) or None


def _candidate_label(candidate, media_type):
    title = candidate.get("title" if media_type == "movie" else "name")
    original = candidate.get("original_title" if media_type == "movie" else "original_name")
    title = str(title or original or "Untitled")
    original = str(original or "")
    year = _candidate_year(candidate, media_type)
    label = title
    if year:
        label += f" ({year})"
    if original and original.casefold() != title.casefold():
        label += f" · {original}"
    return label[:60]


def _rank_title_candidates(candidates, query, media_type):
    wanted = re.sub(r"[^a-z0-9]+", "", str(query or "").casefold())

    def score(item):
        names = [
            str(item.get(field) or "").casefold()
            for field in (
                ("title", "original_title")
                if media_type == "movie"
                else ("name", "original_name")
            )
        ]
        normalized = [re.sub(r"[^a-z0-9]+", "", name) for name in names]
        best = max(
            (
                1000 if name == wanted else
                600 if name.startswith(wanted) or wanted.startswith(name) else
                300 if wanted and wanted in name else 0
            )
            for name in normalized if name
        ) if any(normalized) else 0
        year = re.search(r"\b(?:19|20)\d{2}\b", str(query or ""))
        date_year = _candidate_year(item, media_type)
        if year and date_year == year.group(0):
            best += 500
        return best + min(int(item.get("vote_count") or 0), 500)

    return sorted(
        (item for item in (candidates or []) if item.get("id")),
        key=score,
        reverse=True,
    )[:6]


_TITLE_METADATA_TASKS = set()


async def _fetch_title_details(candidate_id, media_type):
    try:
        if media_type == "movie":
            return await get_tmdb_movie(candidate_id, id=True)
        return await get_tmdb_tv(candidate_id, id=True)
    except Exception:
        logger.exception("TMDB title details lookup failed")
        return None


def _schedule_title_details(candidate_id, media_type):
    task = asyncio.create_task(_fetch_title_details(candidate_id, media_type))
    _TITLE_METADATA_TASKS.add(task)
    task.add_done_callback(_TITLE_METADATA_TASKS.discard)
    return task


def _candidate_metadata(candidate, media_type):
    year = _candidate_year(candidate, media_type)
    title = candidate.get("title" if media_type == "movie" else "name")
    original = candidate.get("original_title" if media_type == "movie" else "original_name")
    media_label = "movie" if media_type == "movie" else "tv"
    poster_path = candidate.get("poster_path")
    backdrop_path = candidate.get("backdrop_path")
    return {
        "id": candidate.get("id"),
        "title": title or original or "Unknown",
        "original_title": original or title or "Unknown",
        "year": year or "N/A",
        "release_date": (
            candidate.get("release_date") if media_type == "movie"
            else candidate.get("first_air_date")
        ) or "N/A",
        "status": candidate.get("status") or "",
        "genres": "N/A",
        "rating": candidate.get("vote_average") or 0,
        "votes": candidate.get("vote_count") or 0,
        "runtime": 0,
        "overview": candidate.get("overview") or "",
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "poster": image_url(poster_path, "w780"),
        "backdrop": image_url(backdrop_path, "w1280"),
        "url": f"https://www.themoviedb.org/{media_label}/{candidate.get('id')}",
        "images": {"posters": [], "backdrops": []},
        "media_type": "movie" if media_type == "movie" else "tv",
        "languages": [],
    }


def _google_release_markup(search, metadata=None, media_type=None):
    metadata = metadata or {}
    title = str(metadata.get("title") or search or "").strip()
    year = str(metadata.get("year") or "").strip()
    kind = "TV series" if metadata.get("media_type") == "tv" or media_type == "series" else "movie"
    query = " ".join(part for part in (title, year, kind, "release date") if part)
    url = f"https://www.google.com/search?q={quote_plus(query[:300])}"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔎 Verify on Google", url=url)
    ]])


async def _send_metadata_fallback(reply_msg, request_message, metadata, search):
    requester = request_message.from_user.mention if request_message.from_user else "User"
    chat_title = getattr(request_message.chat, "title", None) or temp.B_NAME
    card = build_tmdb_card(metadata, [], search, requester, "0.00", chat_title)
    status = release_status_label(metadata)
    overview = re.sub(r"\s+", " ", str(metadata.get("overview") or "")).strip()
    content_label = "series" if metadata.get("media_type") == "tv" else "movie"
    if status.startswith(("Upcoming", "Not yet")):
        database_note = (
            f"<b>📂 Bot database:</b> This {content_label} is not released yet; no files in the database."
        )
    elif status in {"Released", "Aired", "Ended", "Currently airing"}:
        database_note = (
            f"<b>📂 Bot database:</b> This {content_label} is released, but there are no files in the database."
        )
    elif status == "Canceled":
        database_note = (
            f"<b>📂 Bot database:</b> No files; TMDB lists this {content_label} as canceled."
        )
    else:
        database_note = (
            f"<b>📂 Bot database:</b> No files; the release status of this {content_label} could not be confirmed."
        )
    body = card + "\n\n" + database_note
    if overview:
        overview_line = f"\n\n<b>Overview:</b> {html.escape(overview[:240], quote=False)}"
        if len(body) + len(overview_line) <= 1024:
            body += overview_line

    if len(body) > 1024:
        title = html.escape(str(metadata.get("title") or search or "Unknown")[:140], quote=False)
        year = str(metadata.get("year") or "").strip()
        release_date = str(metadata.get("release_date") or "").strip()
        rating = str(metadata.get("rating") or "").strip()
        year_suffix = f" ({html.escape(year, quote=False)})" if year and year != "N/A" else ""
        compact = [f"🎬 <b>{title}{year_suffix}</b>"]
        if release_date and release_date != "N/A":
            compact.append(f"📅 <b>Release date:</b> {html.escape(release_date[:32], quote=False)}")
        compact.extend([
            f"📌 <b>Status:</b> {html.escape(status[:80], quote=False)}",
            f"⭐ <b>TMDB rating:</b> {html.escape(rating[:16], quote=False) if rating else 'Not rated'}",
            database_note,
        ])
        source_url = str(metadata.get("url") or "").strip()
        if source_url.startswith("https://www.themoviedb.org/"):
            compact.append(
                f"ℹ️ <b>Source:</b> <a href='{html.escape(source_url, quote=True)}'>TMDB</a>"
            )
        body = "\n".join(compact)

    try:
        sent = await reply_photo_or_text(
            request_message,
            photo=metadata.get("poster") or image_url(metadata.get("poster_path"), "w780"),
            caption=body,
            reply_markup=_google_release_markup(search, metadata),
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        logger.exception("Could not send TMDB information-only result")
        return await reply_msg.edit_text(
            text=body,
            reply_markup=_google_release_markup(search, metadata),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
    try:
        await reply_msg.delete()
    except Exception:
        logger.debug("Could not delete the metadata loading message", exc_info=True)
    return sent


@Client.on_callback_query(filters.regex(r"^mt#"), group=-1)
async def select_media_type(client: Client, query: CallbackQuery):
    parts = str(query.data or "").split("#", 2)
    if len(parts) != 3 or parts[1] not in {"movie", "series"}:
        await query.answer("Invalid content type.", show_alert=True)
        raise StopPropagation
    _, media_type, key = parts
    state = await _load_media_search_state(client, key, query.message)
    if not state:
        MEDIA_SEARCH.pop(key, None)
        await query.answer("This search expired. Send the title again.", show_alert=True)
        raise StopPropagation
    if query.from_user and query.from_user.id != state.get("owner_id"):
        await query.answer("This search belongs to another user.", show_alert=True)
        raise StopPropagation

    state["media_type"] = media_type
    await query.answer()
    await _edit_quietly(
        query.message.edit_text,
        text="Searching for matching titles…",
        disable_web_page_preview=True,
    )
    try:
        candidates = (
            await search_tmdb_movie(state["query"], bulk=True)
            if media_type == "movie"
            else await search_tmdb_tv(state["query"], bulk=True)
        )
    except Exception:
        logger.exception("TMDB title search failed")
        candidates = []
    candidates = _rank_title_candidates(candidates, state["query"], media_type)
    if candidates:
        state["candidates"] = candidates
        rows = [
            [InlineKeyboardButton(
                _candidate_label(candidate, media_type),
                callback_data=f"mtitle#{index}#{key}",
            )]
            for index, candidate in enumerate(candidates)
        ]
        rows.append([InlineKeyboardButton("↩ Change content type", callback_data=f"mtback#{key}")])
        await _edit_quietly(
            query.message.edit_text,
            text=f"Select the matching {'movie' if media_type == 'movie' else 'TV series'}:",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        raise StopPropagation

    source_message = await _get_media_search_source(client, key, state, query.message)
    if not source_message:
        await query.message.edit_text("I couldn't retrieve the original search. Please send the title again.")
        raise StopPropagation
    try:
        await auto_filter(
            client,
            state["query"],
            source_message,
            query.message,
            True,
            media_type=media_type,
        )
    except Exception:
        logger.exception("Typed media search failed")
        await _edit_quietly(
            query.message.edit_text,
            text="⚠️ Search is temporarily unavailable. Please try again shortly.",
        )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^mtback#"), group=-1)
async def change_media_type(client: Client, query: CallbackQuery):
    key = str(query.data or "").split("#", 1)[-1]
    state = await _load_media_search_state(client, key, query.message)
    if not state:
        MEDIA_SEARCH.pop(key, None)
        await query.answer("This search expired. Send the title again.", show_alert=True)
        raise StopPropagation
    if query.from_user and query.from_user.id != state.get("owner_id"):
        await query.answer("This search belongs to another user.", show_alert=True)
        raise StopPropagation
    state["media_type"] = None
    state["candidates"] = []
    await query.answer()
    await _edit_quietly(
        query.message.edit_text,
        text="Choose what you want to search for:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 Movie", callback_data=f"mt#movie#{key}"),
            InlineKeyboardButton("📺 Series", callback_data=f"mt#series#{key}"),
        ]]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^mtitle#"), group=-1)
async def select_tmdb_title(client: Client, query: CallbackQuery):
    parts = str(query.data or "").split("#", 2)
    if len(parts) != 3:
        await query.answer("Invalid title selection.", show_alert=True)
        raise StopPropagation
    _, index_text, key = parts
    state = await _load_media_search_state(client, key, query.message)
    if not state:
        MEDIA_SEARCH.pop(key, None)
        await query.answer("This search expired. Send the title again.", show_alert=True)
        raise StopPropagation
    if query.from_user and query.from_user.id != state.get("owner_id"):
        await query.answer("This search belongs to another user.", show_alert=True)
        raise StopPropagation
    try:
        candidate = state["candidates"][int(index_text)]
    except (IndexError, KeyError, TypeError, ValueError):
        await query.answer("That title is no longer available.", show_alert=True)
        raise StopPropagation

    media_type = state.get("media_type")
    if media_type not in {"movie", "series"}:
        await query.answer("Choose Movie or Series again.", show_alert=True)
        raise StopPropagation
    await query.answer()
    await _edit_quietly(query.message.edit_text, text="Searching files…")
    source_message = await _get_media_search_source(client, key, state, query.message)
    if not source_message:
        await query.message.edit_text("I couldn't retrieve the original search. Please send the title again.")
        raise StopPropagation
    metadata = _candidate_metadata(candidate, media_type)
    metadata_task = _schedule_title_details(candidate["id"], media_type)
    selected_search = str(
        candidate.get("title" if media_type == "movie" else "name")
        or candidate.get("original_title" if media_type == "movie" else "original_name")
        or state["query"]
    )
    title_year = _candidate_file_year(candidate, media_type)
    try:
        await auto_filter(
            client,
            selected_search,
            source_message,
            query.message,
            True,
            media_type=media_type,
            metadata=metadata,
            title_year=title_year,
            series_exact=media_type == "series",
            metadata_task=metadata_task,
            fallback_search=state["query"] if media_type == "movie" else None,
        )
    except Exception:
        logger.exception("Selected-title search failed")
        await _edit_quietly(
            query.message.edit_text,
            text="⚠️ Search is temporarily unavailable. Please try again shortly.",
        )
    raise StopPropagation


_CAPTION_LIMIT = 1024
_PHOTO_PAGE_SIZE = 10
_FULL_NAME_PHOTO_PAGE_SIZE = 5


def _caption_html(message):
    caption = getattr(message, "caption", None) or ""
    return getattr(caption, "html", None) or str(caption)


def _card_header(caption_html):
    """Everything in a card caption above its file section, with balanced HTML tags."""
    caption_html = caption_html or ""
    markers = [
        idx for text in ("Your Movie Files", "Your Series Files", "Your Files")
        if (idx := caption_html.find(text)) >= 0
    ]
    head = caption_html if not markers else caption_html[:min(markers)]
    marker = head.rfind("🍿")
    if marker != -1 and marker > len(head) - 40:
        head = head[:marker]
    # Drop only the opening tags and whitespace left by the marker, so closed tags stay closed.
    while True:
        stripped = head.rstrip()
        for tag in ("<b>", "<u>", "<i>"):
            if stripped.endswith(tag):
                stripped = stripped[: -len(tag)]
                break
        if stripped == head.rstrip():
            return stripped
        head = stripped


def _photo_caption(header, files, search=None):
    """Header plus linked file names, kept within Telegram's caption limit."""
    import html as _html
    selected = parse_filter_query(search)[1] if search else {}
    typed_media = selected.get("media")
    if typed_media == "series":
        file_heading = "Your Series Files"
    elif typed_media == "movie":
        file_heading = "Your Movie Files"
    else:
        file_heading = "Your Files"
    caption = f"{header}\n\n<b><u>🍿 {file_heading} 👇</u></b>"
    entries = []
    for file in files:
        name = clean_display_filename(file.get("file_name") or "")
        if not typed_media:
            name = name[:36]
        name = _html.escape(name, quote=False)
        size = _html.escape(get_size(file.get("file_size") or 0), quote=False)
        file_id = file.get("file_id")
        username = getattr(temp, "U_NAME", None)
        if file_id and username:
            url = _html.escape(
                f"https://telegram.me/{username}?start=files_{file_id}",
                quote=True,
            )
            entry = f"📁 <b><a href='{url}'>[{size}] {name}</a></b>"
        else:
            entry = f"📁 <b>[{size}] {name}</b>"
        entries.append(entry)

    visible_caption = caption
    included = 0
    for entry in entries:
        candidate = f"{visible_caption}\n\n{entry}"
        plain_text = _html.unescape(re.sub(r"<[^>]*>", "", candidate))
        # Telegram's caption limit is measured on the visible text, not HTML markup.
        if len(plain_text.encode("utf-16-le")) // 2 > _CAPTION_LIMIT:
            break
        visible_caption = candidate
        included += 1
    if typed_media and included != len(entries):
        raise ValueError("Full filenames do not fit in the photo caption")
    return visible_caption


def _full_filename_list(search, files):
    """Render complete, clickable file names in a text message."""
    title, selected = parse_filter_query(search)
    media = selected.get("media")
    heading = "Your Series Files" if media == "series" else "Your Movie Files"
    rows = [
        f"🎬 <b>{html.escape(title, quote=False)}</b>",
        f"<b><u>🍿 {heading} 👇</u></b>",
    ]
    username = getattr(temp, "U_NAME", None)
    for file in files:
        name = html.escape(_filter_filename(file), quote=False)
        size = html.escape(get_size(file.get("file_size", 0)), quote=False)
        file_id = file.get("file_id")
        if file_id and username:
            url = html.escape(
                f"https://telegram.me/{username}?start=files_{file_id}",
                quote=True,
            )
            rows.append(f"📁 <a href='{url}'>[{size}] {name}</a>")
        else:
            rows.append(f"📁 [{size}] {name}")
    return "\n\n".join(rows)


# key -> filter query, set while a filtered result is shown. next_page uses it to keep
# page turns inside the same filter. Cleared by Back to Files.
FILTER_PAGER = {}
PHOTO_PAGE_SIZES = {}


async def _show_filter_results(
    query, key, search, offset=0, callback_answered=False, show_loading=True,
    loading_label="⏳ Applying filter…",
):
    chat_id = query.message.chat.id
    settings = _effective_settings(await get_settings(chat_id), query.message)
    message = query.message
    is_photo = _is_card_message(message) or bool(getattr(message, "photo", None))
    typed_media = parse_filter_query(search)[1].get("media")
    if is_photo and typed_media:
        fallback_page_size = max(
            1, int(PHOTO_PAGE_SIZES.get(key, _FULL_NAME_PHOTO_PAGE_SIZE)),
        )
    else:
        fallback_page_size = _PHOTO_PAGE_SIZE if is_photo else _filter_page_size(settings)
    page_size = _get_result_page_size(
        key, settings, temp.GETALL.get(key), fallback=fallback_page_size,
    )
    started_at = asyncio.get_running_loop().time()
    answered = {"done": bool(callback_answered)}

    async def _ack():
        """Answer the callback once (needed when the caller left it open for a popup)."""
        if not answered["done"]:
            answered["done"] = True
            try:
                await query.answer()
            except Exception:
                pass

    if callback_answered and show_loading:
        await _edit_quietly(
            message.edit_reply_markup,
            reply_markup=_filter_loading_markup(key, loading_label),
        )
    files, next_offset, total = await get_search_results(
        chat_id,
        search,
        max_results=page_size,
        offset=offset,
        filter=True,
        fast_page=bool(typed_media),
    )
    photo_caption = None
    while files and is_photo and typed_media:
        try:
            photo_caption = _photo_caption(
                _card_header(_caption_html(message)), files, search,
            )
            PHOTO_PAGE_SIZES[key] = page_size
            break
        except ValueError:
            if page_size <= 1:
                await query.answer(
                    "This filename is too long to fit beside the poster.",
                    show_alert=True,
                )
                return False
            page_size -= 1
            PHOTO_PAGE_SIZES[key] = page_size
            files, next_offset, total = await get_search_results(
                chat_id,
                search,
                max_results=page_size,
                offset=offset,
                filter=True,
                fast_page=True,
            )
    RESULT_PAGE_SIZES[key] = max(1, int(page_size))
    if not files:
        if not answered["done"]:
            # Popup only: the current menu/results stay untouched, so the user can
            # simply pick another value (no dead-end button, no Back needed).
            answered["done"] = True
            await query.answer(
                "🚫 No files match this filter.\nPlease choose another option.",
                show_alert=True,
            )
        else:
            # Callback was already answered (page turn etc.): keep a Back button.
            await _edit_quietly(
                query.message.edit_reply_markup,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚫 No files match this filter", callback_data="ident")],
                    [InlineKeyboardButton("↩ Back to Files", callback_data=f"fh#{key}")],
                ]),
            )
        return False

    await _ack()
    BUTTONS[key] = search
    FILTER_PAGER[key] = search
    temp.GETALL[key] = files
    if query.from_user:
        temp.SHORT[query.from_user.id] = chat_id
    pre = "filep" if settings.get("file_secure") else "file"
    user_id = query.from_user.id if query.from_user else 0
    typed_rows = None
    if parse_filter_query(search)[1].get("media"):
        typed_rows = await _typed_result_keyboard(
            files, key, search, settings, pre, total, next_offset, user_id,
            offset=offset, page_size=page_size, include_files=False,
            include_back=False,
        )
    if is_photo:
        # Full names for typed Movie/Series results stay in the same poster caption.
        markup = InlineKeyboardMarkup(
            typed_rows if typed_rows is not None else
            _filtered_result_keyboard(files, key, {**settings, "button": False}, pre, total, next_offset, user_id, offset, page_size)
        )
        caption = photo_caption or _photo_caption(
            _card_header(_caption_html(message)), files, search,
        )
        await _edit_quietly(message.edit_caption, caption=caption, reply_markup=markup)
        return True

    # Text results: the filtered files replace the previous list inside the main text.
    # The keyboard keeps only the rules and pager, so the files do not drop below
    # the rules as a second button list.
    markup = InlineKeyboardMarkup(
        typed_rows if typed_rows is not None else
        _filtered_result_keyboard(files, key, {**settings, "button": False}, pre, total, next_offset, user_id, offset, page_size)
    )
    caption = await get_cap(
        settings,
        f"{asyncio.get_running_loop().time() - started_at:.2f}",
        files,
        query,
        total,
        search,
        list_files=True,
        fetch_metadata=False,
    )
    await _edit_quietly(
        message.edit_text, text=caption, reply_markup=markup, disable_web_page_preview=True,
    )
    return True


async def _edit_quietly(edit, **kwargs):
    """Run a Telegram edit, ignoring 'message is not modified' (same content pressed twice)."""
    try:
        await edit(**kwargs)
    except Exception as exc:
        text = str(exc).upper()
        if "MESSAGE_NOT_MODIFIED" in text or "NOT MODIFIED" in text:
            return
        raise


_FILTER_WARM_TASKS = set()


async def _warm_filter_values(query):
    try:
        await get_available_filter_values(
            query, max_scan=_FILTER_VALUE_SCAN_LIMIT,
        )
    except Exception:
        logger.exception("Could not prewarm filter values")


def _schedule_filter_value_warmup(query):
    task = asyncio.create_task(_warm_filter_values(query))
    _FILTER_WARM_TASKS.add(task)
    task.add_done_callback(_FILTER_WARM_TASKS.discard)


@Client.on_callback_query(filters.regex(_FILTER_HANDLERS), group=-1)
async def reliable_filter_callbacks(client: Client, query: CallbackQuery):
    """Single, stateful route for every language/year/quality/season/episode action."""
    try:
        parts = str(query.data or "").split("#")
        action = parts[0]
        key = parts[-1] if len(parts) > 1 else ""
        reply_to = getattr(query.message, "reply_to_message", None)
        owner = getattr(getattr(reply_to, "from_user", None), "id", None)
        if owner not in (None, 0) and query.from_user and query.from_user.id != owner:
            await query.answer(
                f"⚠️ Hello {query.from_user.first_name}, this is not your movie request.",
                show_alert=True,
            )
            raise StopPropagation

        original = FRESH.get(key)
        active = BUTTONS.get(key) or original
        if not active:
            await query.answer("This search has expired. Please search again.", show_alert=True)
            raise StopPropagation

        allowed_actions = {
            "years", "qualities", "episodes", "languages", "seasons", "epage",
            "fh", "fy", "fe", "fl", "fs", "fq", "combined", "combinedoff", "fback",
        }
        if action not in allowed_actions:
            await query.answer("Unknown filter action.", show_alert=True)
            raise StopPropagation

        if action in {"years", "qualities", "episodes", "languages", "seasons"}:
            menu_kind = {
                "years": "year",
                "qualities": "quality",
                "episodes": "episode",
                "languages": "language",
                "seasons": "season",
            }[action]
            _, active_filters = parse_filter_query(active)
            if (
                menu_kind == "episode"
                and active_filters.get("media") == "series"
                and not active_filters.get("season")
            ):
                await query.answer("Choose a season first to see its uploaded episodes.", show_alert=True)
                raise StopPropagation
            # Database discovery and rendering can take several seconds. Answer the
            # Telegram callback now; never wait until after Mongo/IMDb work.
            await query.answer("Loading filter options…")
            await _edit_quietly(
                query.message.edit_reply_markup,
                reply_markup=_filter_loading_markup(key, "⏳ Loading filter options…"),
            )
            available = await get_available_filter_values(
                active, max_scan=_FILTER_VALUE_SCAN_LIMIT,
            )
            available = _merge_filter_values(available, temp.GETALL.get(key, []))
            menu_markup = InlineKeyboardMarkup(
                _filter_menu_rows(menu_kind, key, values=available)
            )
            msg = query.message
            if _is_card_message(msg) or getattr(msg, "photo", None):
                await _edit_quietly(
                    msg.edit_caption, caption=_card_header(_caption_html(msg)), reply_markup=menu_markup,
                )
            else:
                # Text result: show only the header while the menu is open, so the menu
                # sits right under the main text instead of far below the file list.
                # Choosing a value shows the filtered files in the main text again.
                settings = _effective_settings(await get_settings(msg.chat.id), msg)
                header = await get_cap(
                    settings,
                    "0.00",
                    temp.GETALL.get(key, []),
                    query,
                    0,
                    active,
                    list_files=False,
                    fetch_metadata=False,
                )
                await _edit_quietly(
                    msg.edit_text, text=header, reply_markup=menu_markup, disable_web_page_preview=True,
                )
            raise StopPropagation

        if action == "epage":
            page = int(parts[1])
            await query.answer("Loading episodes…")
            await _edit_quietly(
                query.message.edit_reply_markup,
                reply_markup=_filter_loading_markup(key, "⏳ Loading episodes…"),
            )
            available = await get_available_filter_values(
                active, max_scan=_FILTER_VALUE_SCAN_LIMIT,
            )
            available = _merge_filter_values(available, temp.GETALL.get(key, []))
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(
                    _filter_menu_rows("episode", key, page, values=available)
                )
            )
            raise StopPropagation

        if action == "fh":
            FILTER_PAGER.pop(key, None)
        if action in {"fh"} or (action in {"fy", "fe", "fl", "fs", "fq"} and len(parts) > 1 and parts[1] == "homepage"):
            search = original
        elif action == "combined":
            search = make_filter_query(active, combined="1")
        elif action == "combinedoff":
            search = make_filter_query(active, combined=None)
        elif action == "fback":
            search = active
        else:
            value = parts[1] if len(parts) > 1 else ""
            key = parts[2] if len(parts) > 2 else key
            if action == "fy":
                search = make_filter_query(active, year=value)
            elif action == "fe":
                search = make_filter_query(active, episode=value)
            elif action == "fs":
                search = make_filter_query(active, season=None if value == "all" else value)
            elif action == "fq" or (action == "fl" and re.fullmatch(r"\d{3,4}p?", value, re.I)):
                search = make_filter_query(active, quality=value)
            elif action == "fl":
                search = make_filter_query(active, language=value)

        if action in {"fh", "fback"} or (
            action in {"fy", "fe", "fl", "fs", "fq"} and len(parts) > 1 and parts[1] == "homepage"
        ):
            await query.answer("Applying filter…")
            await _show_filter_results(query, key, search, callback_answered=True)
        else:
            # Do not answer yet: if nothing matches, the answer becomes a popup alert
            # and the filter menu stays on screen.
            await _show_filter_results(
                query, key, search, callback_answered=False, show_loading=False,
            )
    except StopPropagation:
        raise
    except Exception:
        logger.exception("Filter callback failed")
        try:
            await query.answer("The filter could not be applied. Please try again.", show_alert=True)
        except Exception:
            pass
    raise StopPropagation

async def global_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_gfilters('gfilters')
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_gfilter('gfilters', keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            joelkb = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if manual == False:
                                settings = await get_settings(message.chat.id)
                                try:
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                                        try:
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                    else:
                                        try:
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_ffilter', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search) 
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            
                        else:
                            button = eval(btn)
                            joelkb = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if manual == False:
                                settings = await get_settings(message.chat.id)
                                try:
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                                        try:
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                    else:
                                        try:
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_ffilter', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()

                    elif btn == "[]":
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if manual == False:
                            settings = await get_settings(message.chat.id)
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search) 
                        else:
                            try:
                                if settings['auto_delete']:
                                    await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_delete', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_delete']:
                                    await joelkb.delete()

                    else:
                        button = eval(btn)
                        joelkb = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if manual == False:
                            settings = await get_settings(message.chat.id)
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                        else:
                            try:
                                if settings['auto_delete']:
                                    await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_delete', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_delete']:
                                    await joelkb.delete()

                                
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False

