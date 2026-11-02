# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, asyncio, os, re, random, pytz, aiohttp, requests, string, json, http.client, html
from info import *
from imdb import Cinemagoer 
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import enums
from pyrogram.errors import *
from typing import Union
from Script import script
from datetime import datetime, date, timedelta
from typing import List
from database.users_chats_db import db
from database.join_reqs import JoinReqs
from bs4 import BeautifulSoup
from shortzy import Shortzy
from search_filters import clean_display_filename, display_filter_query, parse_filter_query
from media_delivery import send_media_preserve_thumb

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
join_db = JoinReqs
BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))")

# Pin a pre-2026 Cinemagoer release in requirements.txt; it supports IMDb's HTTP access system.
imdb = Cinemagoer(accessSystem='http')

TOKENS = {}
VERIFIED = {}
BANNED = {}
SECOND_SHORTENER = {}
SMART_OPEN = '“'
SMART_CLOSE = '”'
START_CHAR = ('\'', '"', SMART_OPEN)

# temp db for banned 
class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    BOT = None
    CURRENT=int(os.environ.get("SKIP", 2))
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    GETALL = {}
    SHORT = {}
    SETTINGS = {}
    IMDB_CAP = {}


async def pub_is_subscribed(bot, query, channel):
    btn = []
    for id in channel:
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(id, query.from_user.id)
        except UserNotParticipant:
            btn.append(
                [InlineKeyboardButton(f'Join {chat.title}', url=chat.invite_link)]
            )
        except Exception as e:
            pass
    return btn

async def is_subscribed(bot, query):
    if REQUEST_TO_JOIN_MODE == True and join_db().isActive():
        try:
            user = await join_db().get_user(query.from_user.id)
            if user and user["user_id"] == query.from_user.id:
                return True
            else:
                try:
                    user_data = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
                except UserNotParticipant:
                    pass
                except Exception as e:
                    logger.exception(e)
                else:
                    if user_data.status != enums.ChatMemberStatus.BANNED:
                        return True
        except Exception as e:
            logger.exception(e)
            return False
    else:
        try:
            user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
        except UserNotParticipant:
            pass
        except Exception as e:
            logger.exception(e)
        else:
            if user.status != enums.ChatMemberStatus.BANNED:
                return True
        return False

async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1]) 
        else:
            year = None
        try:
            movieid = await asyncio.wait_for(
                asyncio.to_thread(imdb.search_movie, title.lower(), results=10), timeout=6
            )
        except asyncio.TimeoutError:
            movieid = None
        if not movieid:
            return None
        if year:
            filtered=list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid=list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid:
            movieid = filtered
        if bulk:
            return movieid
        movieid = movieid[0].movieID
    else:
        movieid = query
    try:
        movie = await asyncio.wait_for(asyncio.to_thread(imdb.get_movie, movieid), timeout=8)
    except asyncio.TimeoutError:
        movie = None
    if not movie:
        return None
    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"
    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer":list_to_str(movie.get("writer")),
        "producer":list_to_str(movie.get("producer")),
        "composer":list_to_str(movie.get("composer")) ,
        "cinematographer":list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_str(movie.get("genres")),
        'poster': movie.get('full-size cover url'),
        'plot': plot,
        'rating': str(movie.get("rating")),
        'url':f'https://www.imdb.com/title/tt{movieid}'
    }

async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id}-Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} -Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception as e:
        return False, "Error"

async def broadcast_messages_group(chat_id, message):
    try:
        kd = await message.copy(chat_id=chat_id)
        try:
            await kd.pin()
        except:
            pass
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await broadcast_messages_group(chat_id, message)
    except Exception as e:
        return False, "Error"
    
async def search_gagala(text):
    usr_agent = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/61.0.3163.100 Safari/537.36'
        }
    text = text.replace(" ", '+')
    url = f'https://www.google.com/search?q={text}'
    response = requests.get(url, headers=usr_agent)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    titles = soup.find_all( 'h3' )
    return [title.getText() for title in titles]

def tmdb_poster_row(settings, grp_id):
    """Settings row: TMDB POSTER on/off. Poster images from TMDB appear only when it is on."""
    value = bool(settings.get('tmdb_poster'))
    return [
        InlineKeyboardButton('TMDB POSTER', callback_data=f'setgs#tmdb_poster#{value}#{grp_id}'),
        InlineKeyboardButton('✔ ON' if value else '✘ OFF', callback_data=f'setgs#tmdb_poster#{value}#{grp_id}'),
    ]


def tmdb_visuals_enabled(settings):
    """True when TMDB information may be used for a result card (poster or backdrop switched on)."""
    return bool(settings.get('tmdb_poster') or settings.get('tmdb_backdrop'))


async def get_settings(group_id):
    settings = await db.get_settings(group_id)
    # Backward-compatible defaults for settings added by RDX integration.
    if not isinstance(settings, dict):
        settings = {}
    settings.setdefault('tmdb_backdrop', TMDB_BACKDROP)
    settings.setdefault('tmdb_poster', TMDB_POSTER)
    return settings
    
async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current.update({key: value})
    await db.update_settings(group_id, current)
    
def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def split_list(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]  

def get_file_id(msg: Message):
    if msg.media:
        for message_type in (
            "photo",
            "animation",
            "audio",
            "document",
            "video",
            "video_note",
            "voice",
            "sticker"
        ):
            obj = getattr(msg, message_type)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj

def extract_user(message: Message) -> Union[int, str]:
    user_id = None
    user_first_name = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_first_name = message.reply_to_message.from_user.first_name

    elif len(message.command) > 1:
        if (
            len(message.entities) > 1 and
            message.entities[1].type == enums.MessageEntityType.TEXT_MENTION
        ):
           
            required_entity = message.entities[1]
            user_id = required_entity.user.id
            user_first_name = required_entity.user.first_name
        else:
            user_id = message.command[1]
            # don't want to make a request -_-
            user_first_name = user_id
        try:
            user_id = int(user_id)
        except ValueError:
            pass
    else:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
    return (user_id, user_first_name)

def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif MAX_LIST_ELM:
        k = k[:int(MAX_LIST_ELM)]
        return ' '.join(f'{elem}, ' for elem in k)
    else:
        return ' '.join(f'{elem}, ' for elem in k)

def last_online(from_user):
    time = ""
    if from_user.is_bot:
        time += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        time += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return time

def split_quotes(text: str) -> List:
    if not any(text.startswith(char) for char in START_CHAR):
        return text.split(None, 1)
    counter = 1  # ignore first char -> is some kind of quote
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
            break
        counter += 1
    else:
        return text.split(None, 1)

    # 1 to avoid starting quote, and counter is exclusive so avoids ending
    key = remove_escapes(text[1:counter].strip())
    # index will be in range, or `else` would have been executed and returned
    rest = text[counter + 1:].strip()
    if not key:
        key = text[0] + text[0]
    return list(filter(None, [key, rest]))

def gfilterparser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a thruple with button label, url, and newline status
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

def parser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a thruple with button label, url, and newline status
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

def remove_escapes(text: str) -> str:
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'



async def get_clone_shortlink(link, url, api):
    shortzy = Shortzy(api_key=api, base_site=url)
    link = await shortzy.convert(link)
    return link
                           
async def get_shortlink(chat_id, link):
    settings = await get_settings(chat_id) #fetching settings for group
    if 'shortlink' in settings.keys():
        URL = settings['shortlink']
        API = settings['shortlink_api']
    else:
        URL = SHORTLINK_URL
        API = SHORTLINK_API
    if URL.startswith("shorturllink") or URL.startswith("terabox.in") or URL.startswith("urlshorten.in"):
        URL = SHORTLINK_URL
        API = SHORTLINK_API
    if URL == "api.shareus.io":
        url = f'https://{URL}/easy_api'
        params = {
            "key": API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
        shortzy = Shortzy(api_key=API, base_site=URL)
        link = await shortzy.convert(link)
        return link
    
async def get_tutorial(chat_id):
    settings = await get_settings(chat_id) #fetching settings for group
    return settings['tutorial']
        
async def get_verify_shorted_link(link, url, api):
    API = api
    URL = url
    if URL == "api.shareus.io":
        url = f'https://{URL}/easy_api'
        params = {
            "key": API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
        shortzy = Shortzy(api_key=API, base_site=URL)
        link = await shortzy.convert(link)
        return link
        
async def check_token(bot, userid, token):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    if user.id in TOKENS.keys():
        TKN = TOKENS[user.id]
        if token in TKN.keys():
            is_used = TKN[token]
            if is_used == True:
                return False
            else:
                return True
    else:
        return False

def _is_valid_button_url(url):
    """Telegram rejects inline-button URLs that are empty or not http(s)/tg."""
    url = str(url or "").strip()
    return bool(url) and not re.search(r"\s", url) and url.lower().startswith(("http://", "https://", "tg://"))


async def get_token(bot, userid, link):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[user.id] = {token: False}
    link = f"{link}verify-{user.id}-{token}"
    try:
        shortened_verify_url = await get_verify_shorted_link(link, VERIFY_SHORTLINK_URL, VERIFY_SHORTLINK_API)
        if VERIFY_SECOND_SHORTNER == True:
            shortened_verify_url = await get_verify_shorted_link(shortened_verify_url, VERIFY_SND_SHORTLINK_URL, VERIFY_SND_SHORTLINK_API)
    except Exception:
        logger.exception("Verify shortener failed; using the direct verify link")
        shortened_verify_url = link
    shortened_verify_url = str(shortened_verify_url or "").strip()
    if not _is_valid_button_url(shortened_verify_url):
        logger.error("Verify shortener returned an invalid URL (%r); using the direct verify link", shortened_verify_url)
        return link
    return shortened_verify_url


async def build_verify_buttons(bot, userid):
    """Verify button (+ tutorial button only when VERIFY_TUTORIAL is a valid URL).

    An empty VERIFY_TUTORIAL used to make Telegram answer BUTTON_URL_INVALID,
    so the bot never sent anything when a user clicked a file.
    """
    rows = [[InlineKeyboardButton("ᴠᴇʀɪғʏ", url=await get_token(bot, userid, f"https://telegram.me/{temp.U_NAME}?start="))]]
    tutorial = str(VERIFY_TUTORIAL or "").strip()
    if _is_valid_button_url(tutorial):
        rows.append([InlineKeyboardButton("ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ", url=tutorial)])
    return rows

VERIFY_HOUR_OPTIONS = (10, 12, 24, 48)
_VERIFY_HOURS_CACHE = {"hours": None}


async def _get_bot_setting(key, default=None):
    doc = await db.db.bot_settings.find_one({"_id": key})
    return doc.get("value", default) if doc else default


async def _set_bot_setting(key, value):
    await db.db.bot_settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)


async def _get_verified_until(user_id):
    doc = await db.users.find_one({"id": user_id}, {"verified_until": 1})
    return doc.get("verified_until") if doc else None


async def _set_verified_until(user_id, until):
    await db.users.update_one({"id": user_id}, {"$set": {"verified_until": until}}, upsert=True)


async def get_verify_hours():
    """How many hours one verification lasts (admin setting, falls back to VERIFY_HOURS)."""
    hours = _VERIFY_HOURS_CACHE["hours"]
    if hours is None:
        try:
            stored = await _get_bot_setting("verify_hours", None)
        except Exception:
            logger.exception("Could not read the verification time setting")
            stored = None
        try:
            hours = int(stored) if stored is not None else int(VERIFY_HOURS)
        except (TypeError, ValueError):
            hours = 24
        if hours <= 0:
            hours = 24
        _VERIFY_HOURS_CACHE["hours"] = hours
    return hours


async def set_verify_hours(hours):
    hours = int(hours)
    await _set_bot_setting("verify_hours", hours)
    _VERIFY_HOURS_CACHE["hours"] = hours
    return hours


async def verify_prompt_text():
    """Text shown when a user must verify. Keeps one '{}' for the user's mention."""
    hours = await get_verify_hours()
    return (
        "<b>ʜᴇʏ {} 👋,\n\nʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪғɪᴇᴅ, ᴘʟᴇᴀꜱᴇ ᴄʟɪᴄᴋ ᴏɴ ᴠᴇʀɪғʏ & ɢᴇᴛ ᴜɴʟɪᴍɪᴛᴇᴅ ᴀᴄᴄᴇꜱꜱ"
        f"\n\n⏳ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴠᴀʟɪᴅ ғᴏʀ : {hours} ʜᴏᴜʀꜱ\n\n</b>"
    )


async def verify_done_text():
    """Text shown right after a successful verification. Keeps one '{}' for the mention."""
    hours = await get_verify_hours()
    until = datetime.utcnow() + timedelta(hours=hours)
    return (
        "<b>ʜᴇʏ {} 👋,\n\n✅ ʏᴏᴜ ʜᴀᴠᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ᴛʜᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ..."
        f"\n\n⏳ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴠᴀʟɪᴅ ғᴏʀ : {hours} ʜᴏᴜʀꜱ"
        f"\n🕒 ᴇxᴘɪʀᴇꜱ ᴀᴛ : {until.strftime('%d %b %Y, %I:%M %p')} UTC"
        "\n\nɴᴏᴡ ʏᴏᴜ ʜᴀᴠᴇ ᴜɴʟɪᴍɪᴛᴇᴅ ᴀᴄᴄᴇss ᴜɴᴛɪʟ ᴛʜᴀᴛ ᴛɪᴍᴇ, ɴᴏᴡ ᴇɴᴊᴏʏ\n\n</b>"
    )


async def verify_user(bot, userid, token):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    TOKENS[user.id] = {token: True}
    hours = await get_verify_hours()
    until = datetime.utcnow() + timedelta(hours=hours)
    VERIFIED[user.id] = until
    try:
        await _set_verified_until(user.id, until)
    except Exception:
        logger.exception("Could not save the verification expiry")


async def check_verification(bot, userid):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    until = VERIFIED.get(user.id)
    if until is None:
        try:
            until = await _get_verified_until(user.id)
        except Exception:
            logger.exception("Could not read the saved verification expiry")
            until = None
        if until is not None:
            VERIFIED[user.id] = until
    return isinstance(until, datetime) and until > datetime.utcnow()  
    
async def send_all(bot, userid, files, ident, chat_id, user_name, query):
    settings = await get_settings(chat_id)
    if 'is_shortlink' in settings.keys():
        ENABLE_SHORTLINK = settings['is_shortlink']
    else:
        await save_group_settings(message.chat.id, 'is_shortlink', False)
        ENABLE_SHORTLINK = False
    try:
        if ENABLE_SHORTLINK:
            for file in files:
                title = file["file_name"]
                size = get_size(file["file_size"])
                if not await db.has_premium_access(userid) and SHORTLINK_MODE == True:
                    await bot.send_message(chat_id=userid, text=f"<b>Hᴇʏ ᴛʜᴇʀᴇ {user_name} 👋🏽 \n\n✅ Sᴇᴄᴜʀᴇ ʟɪɴᴋ ᴛᴏ ʏᴏᴜʀ ғɪʟᴇ ʜᴀs sᴜᴄᴄᴇssғᴜʟʟʏ ʙᴇᴇɴ ɢᴇɴᴇʀᴀᴛᴇᴅ ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴅᴏᴡɴʟᴏᴀᴅ ʙᴜᴛᴛᴏɴ\n\n🗃️ Fɪʟᴇ Nᴀᴍᴇ : {title}\n🔖 Fɪʟᴇ Sɪᴢᴇ : {size}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Dᴏᴡɴʟᴏᴀᴅ 📥", url=await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}"))]]))
        else:
            for file in files:
                f_caption = file["caption"]
                title = file["file_name"]
                size = get_size(file["file_size"])
                if CUSTOM_FILE_CAPTION:
                    try:
                        f_caption = CUSTOM_FILE_CAPTION.format(
                            file_name='' if title is None else title,
                            file_size='' if size is None else size,
                            file_caption='' if f_caption is None else f_caption
                        )
                    except Exception as e:
                        print(e)
                        f_caption = f_caption
                if f_caption is None:
                    f_caption = f"{title}"
                await send_media_preserve_thumb(
                    bot,
                    chat_id=userid,
                    file_id=file["file_id"],
                    media_record=file,
                    caption=f_caption,
                    protect_content=True if ident == "filep" else False,
                    reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url=GRP_LNK),
                            InlineKeyboardButton('Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ', url=CHNL_LNK)
                        ],[
                            InlineKeyboardButton("Bᴏᴛ Oᴡɴᴇʀ", url=OWNER_LNK)
                        ]]
                    )
                )
    except UserIsBlocked:
        await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
    except PeerIdInvalid:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)
    except Exception as e:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)
        
async def _legacy_get_cap(settings, remaining_seconds, files, query, total_results, search):
    if settings["imdb"]:
        IMDB_CAP = temp.IMDB_CAP.get(query.from_user.id)
        if IMDB_CAP:
            cap = IMDB_CAP
            cap+="<b>\n\n<u>🍿 Your Movie Files 👇</u></b>\n\n"
            for file in files:
                cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
        else:
            imdb = await get_poster(search, file=(files[0])["file_name"]) if settings["imdb"] else None
            if imdb:
                TEMPLATE = script.IMDB_TEMPLATE_TXT
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
                cap+="<b>\n\n<u>🍿 Your Movie Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
            else:
                cap = f"🎬 <b>{search}</b>"
                cap+="<b><u>🍿 Your Movie Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
    else:
        cap = f"🎬 <b>{search}</b>"
        cap+="<b><u>🍿 Your Movie Files 👇</u></b>\n\n"
        for file in files:
            cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
    return cap


async def get_cap(
    settings, remaining_seconds, files, query, total_results, search,
    list_files=True, fetch_metadata=True,
):
    """Build a result caption with clean file names and available quality metadata."""
    display_search = display_filter_query(search)
    imdb_query, _ = parse_filter_query(search)

    def add_file_links(text):
        file_names = " ".join(str(file.get("file_name", "")) for file in files).lower()
        qualities = [item for item in ("2160p", "1080p", "720p", "480p") if item in file_names]
        if "Quality:</b>" not in text:
            text += f"\n🎞️ <b>Quality:</b> {' • '.join(qualities) if qualities else 'Not specified'}"
        requester = query.from_user.mention if query.from_user else "User"
        chat_title = getattr(query.message.chat, "title", "") or temp.B_NAME
        if "Requested by:" not in text:
            text += (
                f"\n━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Requested by:</b> {requester}\n"
                f"📢 <b>Powered by:</b> {html.escape(str(chat_title), quote=False)}"
            )
        if not list_files:
            return text
        text += "<b>\n\n<u>🍿 Your Movie Files 👇</u></b>\n"
        for file in files:
            title = clean_display_filename(file.get("file_name", ""))
            text += (
                f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>"
                f"[{get_size(file['file_size'])}] {title}\n</a></b>"
            )
        return text

    cap = None
    file_names = " ".join(str(item.get("file_name", "")) for item in files).lower()
    quality = " • ".join(
        item for item in ("2160p", "1080p", "720p", "480p") if item in file_names
    ) or "Not specified"
    if settings.get("imdb"):
        cached_cap = temp.IMDB_CAP.get(query.from_user.id) if query.from_user else None
        if cached_cap:
            cap = add_file_links(cached_cap)
        elif files and fetch_metadata:
            imdb_data = await get_poster(imdb_query, file=files[0].get("file_name", ""))
            if imdb_data:
                cap = script.IMDB_TEMPLATE_TXT.format(
                    qurey=display_search,
                    title=imdb_data["title"],
                    votes=imdb_data["votes"],
                    aka=imdb_data["aka"],
                    seasons=imdb_data["seasons"],
                    box_office=imdb_data["box_office"],
                    localized_title=imdb_data["localized_title"],
                    kind=imdb_data["kind"],
                    imdb_id=imdb_data["imdb_id"],
                    cast=imdb_data["cast"],
                    runtime=imdb_data["runtime"],
                    countries=imdb_data["countries"],
                    certificates=imdb_data["certificates"],
                    languages=imdb_data["languages"],
                    director=imdb_data["director"],
                    writer=imdb_data["writer"],
                    producer=imdb_data["producer"],
                    composer=imdb_data["composer"],
                    cinematographer=imdb_data["cinematographer"],
                    music_team=imdb_data["music_team"],
                    distributors=imdb_data["distributors"],
                    release_date=imdb_data["release_date"],
                    year=imdb_data["year"],
                    genres=imdb_data["genres"],
                    poster=imdb_data["poster"],
                    plot=imdb_data["plot"],
                    rating=imdb_data["rating"],
                    url=imdb_data["url"],
                    **locals(),
                )
                cap = add_file_links(cap)

    if cap is None:
        cap = f"🎬 <b>{display_search}</b>"
        cap = add_file_links(cap)

    return cap


def get_auto_delete_seconds(settings):
    """Auto-delete delay (seconds) for a group; only 5 or 10 minutes are valid."""
    try:
        value = int((settings or {}).get("auto_delete_time", 300))
    except (TypeError, ValueError):
        value = 300
    return value if value in (300, 600) else 300


def auto_delete_minutes(settings):
    return get_auto_delete_seconds(settings) // 60


async def reply_photo_or_text(message, *, photo=None, caption="", reply_markup=None, **kwargs):
    """Reply with a photo; if Telegram cannot use it, reply with the text only.

    Image URLs (graph.org, catbox, ...) can die or block Telegram's servers, which
    raises WEBPAGE_CURL_FAILED / WEBPAGE_MEDIA_EMPTY and silently killed commands
    such as /plan and /start. The text (and buttons) still go out in that case.
    """
    if photo:
        try:
            return await message.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup, **kwargs)
        except Exception as e:
            logger.warning("Photo send failed (%s); sending text only", e)
    return await message.reply_text(caption, reply_markup=reply_markup, disable_web_page_preview=True, **kwargs)


async def get_seconds(time_string):
    def extract_value_and_unit(ts):
        value = ""
        unit = ""
        index = 0
        while index < len(ts) and ts[index].isdigit():
            value += ts[index]
            index += 1
        unit = ts[index:]
        if value:
            value = int(value)
        return value, unit
    value, unit = extract_value_and_unit(time_string)
    if unit == 's':
        return value
    elif unit == 'min':
        return value * 60
    elif unit == 'hour':
        return value * 3600
    elif unit == 'day':
        return value * 86400
    elif unit == 'month':
        return value * 86400 * 30
    elif unit == 'year':
        return value * 86400 * 365
    else:
        return 0


# ===== AUTO DELETE SCHEDULER (begin) =====================================================
# Why: the old fire-and-forget ``asyncio.create_task(expire())`` timer had no strong reference
# (Python may garbage-collect such a task), lived only in memory (lost on every Heroku
# restart/deploy) and swallowed every error. Now each deletion is stored in MongoDB
# (collection ``auto_delete_queue``) and ONE background worker deletes due messages, logging
# every attempt, success and failure reason. Duplicate scheduling of a message is impossible
# (document id = "<chat_id>:<message_id>"), and database channels (CHANNELS) are never touched.
import time as _ad_time

AD_POLL_SECONDS = 10          # how often the worker looks for due messages
AD_RETRY_SECONDS = 30         # delay before retrying a temporary failure
AD_MAX_ATTEMPTS = 5
AD_BATCH_SIZE = 50

# Telegram errors that will never succeed on retry: drop the item and log why.
_AD_PERMANENT_ERRORS = {
    "MessageDeleteForbidden",   # no permission (bot is not admin / message too old)
    "MessageIdInvalid",         # already deleted
    "ChatAdminRequired",
    "ChannelInvalid",
    "ChannelPrivate",
    "PeerIdInvalid",
    "ChatIdInvalid",
    "UserNotParticipant",
    "ChatWriteForbidden",
}

_ad_worker_task = None
_ad_worker_client = None
_ad_fallback_tasks = set()
_ad_index_ready = False


def _ad_collection():
    return db.db.auto_delete_queue


def _ad_doc_id(chat_id, message_id):
    return f"{chat_id}:{message_id}"


async def _ad_ensure_index():
    global _ad_index_ready
    if _ad_index_ready:
        return
    try:
        await _ad_collection().create_index("delete_at")
        _ad_index_ready = True
    except Exception:
        logger.exception("Could not create the auto-delete queue index (continuing without it)")


async def schedule_delete(client, chat_id, message_ids, delay_seconds, reason="search-result"):
    """Queue messages for deletion ``delay_seconds`` from now. Returns how many were newly queued."""
    try:
        delay = max(0, int(delay_seconds))
    except (TypeError, ValueError):
        delay = 300
    if chat_id in (CHANNELS or []):
        logger.warning("Refusing to auto-delete messages in a database channel (chat=%s)", chat_id)
        return 0
    ids = sorted({int(mid) for mid in message_ids if mid})
    if not ids:
        return 0

    await _ad_ensure_index()
    now = _ad_time.time()
    queued = 0
    for mid in ids:
        try:
            result = await _ad_collection().update_one(
                {"_id": _ad_doc_id(chat_id, mid)},
                {"$setOnInsert": {
                    "chat_id": chat_id, "message_id": mid, "delete_at": now + delay,
                    "attempts": 0, "reason": reason, "created_at": now,
                }},
                upsert=True,
            )
            if getattr(result, "upserted_id", None) is not None:
                queued += 1
                logger.info("Auto-delete scheduled: chat=%s msg=%s in %ss (%s)", chat_id, mid, delay, reason)
            else:
                logger.info("Auto-delete already scheduled: chat=%s msg=%s", chat_id, mid)
        except Exception:
            logger.exception("Queue write failed for chat=%s msg=%s; using an in-memory timer", chat_id, mid)
            _ad_start_memory_timer(client, chat_id, mid, delay)
            queued += 1
    ad_ensure_worker(client)
    return queued


def _ad_start_memory_timer(client, chat_id, message_id, delay):
    async def run():
        await asyncio.sleep(delay)
        try:
            logger.info("Auto-delete (memory timer) attempt: chat=%s msg=%s", chat_id, message_id)
            await client.delete_messages(chat_id, message_id)
            logger.info("Auto-delete (memory timer) done: chat=%s msg=%s", chat_id, message_id)
        except Exception as error:
            logger.warning("Auto-delete (memory timer) failed: chat=%s msg=%s: %s: %s",
                           chat_id, message_id, type(error).__name__, error)

    task = asyncio.get_running_loop().create_task(run())
    _ad_fallback_tasks.add(task)               # strong reference: never garbage-collected
    task.add_done_callback(_ad_fallback_tasks.discard)


def ad_ensure_worker(client):
    """Start the single background worker if it is not running (keeps a strong reference)."""
    global _ad_worker_task, _ad_worker_client
    if client is not None:
        _ad_worker_client = client
    if _ad_worker_client is None:
        return
    if _ad_worker_task is None or _ad_worker_task.done():
        _ad_worker_task = asyncio.get_running_loop().create_task(_ad_worker())
        logger.info("Auto-delete worker started (poll every %ss)", AD_POLL_SECONDS)


async def start_auto_delete_worker(client):
    """Call once at bot start-up so deletions queued before a restart are still carried out."""
    ad_ensure_worker(client)


async def stop_auto_delete_worker():
    global _ad_worker_task
    task, _ad_worker_task = _ad_worker_task, None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


async def _ad_worker():
    while True:
        try:
            await ad_process_due()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-delete worker iteration failed")
        await asyncio.sleep(AD_POLL_SECONDS)


async def ad_process_due(now=None):
    """Delete every queued message that is due. Returns the number of queue items handled."""
    now = _ad_time.time() if now is None else now
    docs = await (
        _ad_collection().find({"delete_at": {"$lte": now}}).sort("delete_at", 1).limit(AD_BATCH_SIZE)
    ).to_list(length=AD_BATCH_SIZE)
    for doc in docs:
        await _ad_delete_one(_ad_worker_client, doc)
    return len(docs)


async def _ad_delete_one(client, doc):
    chat_id, mid = doc["chat_id"], doc["message_id"]
    attempt = int(doc.get("attempts", 0)) + 1
    logger.info("Auto-delete attempt: chat=%s msg=%s (attempt %s)", chat_id, mid, attempt)
    try:
        deleted = await client.delete_messages(chat_id, mid)
    except Exception as error:
        name = type(error).__name__
        if name.startswith("FloodWait"):
            wait = int(getattr(error, "value", 0) or 5)
            logger.warning("Auto-delete rate limited (wait %ss): chat=%s msg=%s", wait, chat_id, mid)
            await _ad_reschedule(doc, max(wait, 5), count_attempt=False)
        elif name in _AD_PERMANENT_ERRORS:
            logger.warning("Auto-delete NOT done (%s: %s): chat=%s msg=%s", name, error, chat_id, mid)
            await _ad_forget(doc)
        elif attempt >= AD_MAX_ATTEMPTS:
            logger.error("Auto-delete gave up after %s attempts (%s: %s): chat=%s msg=%s",
                         attempt, name, error, chat_id, mid)
            await _ad_forget(doc)
        else:
            logger.warning("Auto-delete failed, will retry (%s: %s): chat=%s msg=%s", name, error, chat_id, mid)
            await _ad_reschedule(doc, AD_RETRY_SECONDS)
        return
    if deleted:
        logger.info("Auto-delete done: chat=%s msg=%s", chat_id, mid)
    else:
        # Telegram answered but reported 0 deleted messages: it was already gone. Do not claim success.
        logger.info("Auto-delete: Telegram deleted nothing (already gone?): chat=%s msg=%s", chat_id, mid)
    await _ad_forget(doc)


async def _ad_forget(doc):
    try:
        await _ad_collection().delete_one({"_id": doc["_id"]})
    except Exception:
        logger.exception("Could not remove %s from the auto-delete queue", doc.get("_id"))


async def _ad_reschedule(doc, delay, count_attempt=True):
    try:
        update = {"$set": {"delete_at": _ad_time.time() + delay}}
        if count_attempt:
            update["$inc"] = {"attempts": 1}
        await _ad_collection().update_one({"_id": doc["_id"]}, update)
    except Exception:
        logger.exception("Could not reschedule %s", doc.get("_id"))

# ===== AUTO DELETE SCHEDULER (end) =======================================================
