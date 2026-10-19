# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01


import re
from os import environ
from Script import script

id_pattern = re.compile(r'^.\d+$')

# Bot information
SESSION = environ.get('SESSION', 'RDX')
API_ID = int(environ.get('API_ID', '34508826'))
API_HASH = environ.get('API_HASH', 'de91472f471dd5e00771b26d3e149ffd')
BOT_TOKEN = environ.get('BOT_TOKEN', '8508977137:AAEb7bW6oRaJzrYvefoqGJxadcbazmYoRbo')


# This Pictures Is For Start Message Picture, You Can Add Multiple By Giving One Space Between Each.
PICS = (environ.get('PICS', 'https://files.catbox.moe/3pvlfg.jpg')).split()


# Admins & Users
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '8594314148').split()]  # For Multiple Id Use One Space Between Each.
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]  # For Multiple Id Use One Space Between Each.
AUTH_USERS = (auth_users + ADMINS) if auth_users else []

# This Channel Is For When User Start Your Bot Then Bot Send That User Name And Id In This Log Channel, Same For Group Also.
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-1002356425836'))

# This Is File Channel Where You Upload Your File Then Bot Automatically Save It In Database
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-1003243048523 -1002739310563').split()]  # For Multiple Id Use One Space Between Each.

# auth_channel means force subscribe channel.
# if REQUEST_TO_JOIN_MODE is true then force subscribe work like request to join fsub, else if false then work like normal fsub.
REQUEST_TO_JOIN_MODE = bool(environ.get('REQUEST_TO_JOIN_MODE', False))  # Set True Or False
TRY_AGAIN_BTN = bool(environ.get('TRY_AGAIN_BTN', False))  # Set True Or False (This try again button is only for request to join fsub not for normal fsub)

# This Is Force Subscribe Channel, also known as Auth Channel
auth_channel = environ.get('AUTH_CHANNEL', '')  # give your force subscribe channel id here else leave it blank
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None

# This Channel Is For When Bot Requests Any File Name With command or hashtag like - /request or #request
reqst_channel = environ.get('REQST_CHANNEL', '-1002356425836')
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None

# This Channel Is For Index Request
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
# RDX bin channel (used for source file copies/log delivery).
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-1004411706616'))

# This Is Your Bot Support Group Id. Here Bot Will Not Give File Because This Is Support Group.
support_chat_id = environ.get('SUPPORT_CHAT_ID', '')
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None

# This Channel Is For /batch command file store.
FILE_STORE_CHANNEL = [int(ch) for ch in (environ.get('FILE_STORE_CHANNEL', '')).split()]  # For Multiple Id Use One Space Between Each.

# This Channel Is For Delete Index File. Forward Your File In This Channel Which You Want To Delete From The Database.
DELETE_CHANNELS = [int(dch) if id_pattern.search(dch) else dch for dch in environ.get('DELETE_CHANNELS', '0').split()]  # For Multiple Id Use One Space Between Each.


# MongoDB information
# One MongoDB database holds everything: users, filters, connections, indexed files
# (COLLECTION_NAME) and index job state. Set DATABASE_NAME to the database that already
# contains your existing rdxcollection; the default below is only a fallback.
DATABASE_URI = environ.get('DATABASE_URI', 'mongodb+srv://Filter:Filter@cluster0.9kke2jw.mongodb.net/?appName=Cluster0')
DATABASE_NAME = environ.get('DATABASE_NAME', "rdxfilterbot")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'rdxcollection')


# Premium And Referal Settings
PREMIUM_AND_REFERAL_MODE = bool(environ.get('PREMIUM_AND_REFERAL_MODE', True))  # Set True Or False

# If PREMIUM_AND_REFERAL_MODE is True Then Fill Below Variable, If False Then No Need To Fill.
REFERAL_COUNT = int(environ.get('REFERAL_COUNT', '20'))  # number of referal count
REFERAL_PREMEIUM_TIME = environ.get('REFERAL_PREMEIUM_TIME', '1month')  # time in week, day, month.
# Telegram Stars (XTR) subscription prices. Change the numbers or set the env vars.
# Silver = 1 day, Gold = 15 days, Platinum = 30 days (monthly), Diamond = lifetime.
def _stars_price(name, default):
    try:
        value = int(environ.get(name, default))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


STARS_PRICE_1DAY = _stars_price('STARS_PRICE_1DAY', 15)
STARS_PRICE_15DAYS = _stars_price('STARS_PRICE_15DAYS', 100)
STARS_PRICE_30DAYS = _stars_price('STARS_PRICE_30DAYS', 180)
STARS_PRICE_LIFETIME = _stars_price('STARS_PRICE_LIFETIME', 1000)


# Clone Information: If Clone Mode Is True Then Bot Clones Other Bots.
CLONE_MODE = bool(environ.get('CLONE_MODE', False))  # Set True Or False
CLONE_DATABASE_URI = environ.get('CLONE_DATABASE_URI', "")  # Necessary If clone mode is true
PUBLIC_FILE_CHANNEL = environ.get('PUBLIC_FILE_CHANNEL', '')  # Public Channel Username Without @ or without https://t.me/ and Bot Is Admin With Full Right.


# Links
GRP_LNK = environ.get('GRP_LNK', 'https://t.me/movie_search_group1')
CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/rdxmovie_hd')
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'movie_search_group1')  # Support Chat Link Without https:// or @
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/Ordinary_helper')

# True Or False
AI_SPELL_CHECK = bool(environ.get('AI_SPELL_CHECK', True))
PM_SEARCH = bool(environ.get('PM_SEARCH', True))
BUTTON_MODE = bool(environ.get('BUTTON_MODE', True))
MAX_BTN = bool(environ.get('MAX_BTN', True))
IS_TUTORIAL = bool(environ.get('IS_TUTORIAL', False))
IMDB = bool(environ.get('IMDB', False))
# Optional OMDb key for IMDb and Rotten Tomatoes scores. Leave empty to disable.
OMDB_API_KEY = environ.get('OMDB_API_KEY', '579a3919')
# Optional TMDB v3 API key for movie/series metadata and posters.
# Set the actual key in Heroku Config Vars or another deployment Secrets manager.
TMDB_API_KEY = environ.get('TMDB_API_KEY', 'bc2801029c5e65c3fb2fe7171fd23d41').strip()
TMDB_BACKDROP = str(environ.get('TMDB_BACKDROP', 'False')).strip().lower() in ('1', 'true', 'yes', 'on')
TMDB_POSTER = str(environ.get('TMDB_POSTER', 'False')).strip().lower() in ('1', 'true', 'yes', 'on')
AUTO_FFILTER = bool(environ.get('AUTO_FFILTER', True))
AUTO_DELETE = bool(environ.get('AUTO_DELETE', True))
# Auto-delete delay in seconds. Only 300 (5 min) and 600 (10 min) are selectable from /settings.
try:
    AUTO_DELETE_TIME = int(environ.get('AUTO_DELETE_TIME', 300))
except (TypeError, ValueError):
    AUTO_DELETE_TIME = 300
if AUTO_DELETE_TIME not in (300, 600):
    AUTO_DELETE_TIME = 300
LONG_IMDB_DESCRIPTION = bool(environ.get("LONG_IMDB_DESCRIPTION", False))
SPELL_CHECK_REPLY = bool(environ.get("SPELL_CHECK_REPLY", True))
MELCOW_NEW_USERS = bool(environ.get('MELCOW_NEW_USERS', True))
PROTECT_CONTENT = bool(environ.get('PROTECT_CONTENT', False))
PUBLIC_FILE_STORE = bool(environ.get('PUBLIC_FILE_STORE', True))
NO_RESULTS_MSG = bool(environ.get("NO_RESULTS_MSG", False))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', True))


# Token Verification Info:
# NOTE: bool('False') is True in Python, so parse the text properly. Setting VERIFY=False
# (or 0/no/off) in the hosting config now really turns verification off.
VERIFY = str(environ.get('VERIFY', 'False')).strip().lower() in ('1', 'true', 'yes', 'on')
VERIFY_SHORTLINK_URL = environ.get('VERIFY_SHORTLINK_URL', 'shortxlinks.com')
VERIFY_SHORTLINK_API = environ.get('VERIFY_SHORTLINK_API', '232bab9ce253c4913085f9e879ad95f216c4c525')
VERIFY_TUTORIAL = environ.get('VERIFY_TUTORIAL', '')
# Default verification validity in hours. Admins can change it with /set_verify_time (10, 12, 24 or 48).
try:
    VERIFY_HOURS = int(environ.get('VERIFY_HOURS', 24))
except (TypeError, ValueError):
    VERIFY_HOURS = 24
if VERIFY_HOURS <= 0:
    VERIFY_HOURS = 24

# If You Fill Second Shortner Then Bot Attach Both First And Second Shortner And Use It For Verify.
VERIFY_SECOND_SHORTNER = bool(environ.get('VERIFY_SECOND_SHORTNER', False))
# if VERIFY_SECOND_SHORTNER is True then fill below URL and API key
VERIFY_SND_SHORTLINK_URL = environ.get('VERIFY_SND_SHORTLINK_URL', '')
VERIFY_SND_SHORTLINK_API = environ.get('VERIFY_SND_SHORTLINK_API', '')


# Shortlink Info
SHORTLINK_MODE = bool(environ.get('SHORTLINK_MODE', False))  # Set True Or False
SHORTLINK_URL = environ.get('SHORTLINK_URL', '')
SHORTLINK_API = environ.get('SHORTLINK_API', '')
TUTORIAL = environ.get('TUTORIAL', '')  # How Open Shortner Link Video Link, Channel Link Where You Upload Your Video.


# Others
CACHE_TIME = int(environ.get('CACHE_TIME', 1800))
# Files per result page. Fixed at 10 for movie and series results.
MAX_B_TN = "10"
PORT = environ.get("PORT", "8080")
MSG_ALRT = environ.get('MSG_ALRT', 'Hello My Dear Friends ❤️')
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", f"{script.IMDB_TEMPLATE_TXT}")
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)


# Choose Option Settings
LANGUAGES = ["malayalam", "mal", "tamil", "tam", "english", "eng", "hindi", "hin", "telugu", "tel", "kannada", "kan", "bengali", "bangla", "bengoli", "urdu", "marathi", "mar", "punjabi", "pun", "gujarati", "gujrati", "guj", "bhojpuri", "odia", "oriya", "assamese", "asm", "korean", "kor", "chinese", "chi", "japanese", "jap", "arabic", "ara", "spanish", "spa", "french", "fre", "german", "ger", "portuguese", "por", "russian", "rus", "dual audio", "dual", "multi audio", "multi"]
SEASONS = ["season 1", "season 2", "season 3", "season 4", "season 5", "season 6", "season 7", "season 8", "season 9", "season 10"]
EPISODES = [f"E{episode:02d}" for episode in range(1, 101)]
QUALITIES = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
YEARS = ["1900", "1991", "1992", "1993", "1994", "1995", "1996", "1997", "1998", "1999", "2000", "2001", "2002", "2003", "2004", "2005", "2006", "2007", "2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]


# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01


# Online Stream and Download
STREAM_MODE = bool(environ.get('STREAM_MODE', True))  # Set True or False

# If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
MULTI_CLIENT = False
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
ON_HEROKU = 'DYNO' in environ
URL = (environ.get("URL", "") or "").strip()
if URL:
    # URL is joined directly with /watch and /<message_id> in stream links.
    # Normalize it once so a host-only value cannot produce hostwatch/... URLs.
    URL = URL.rstrip("/") + "/"


# Rename Info: If True Then Bot Renames File, Else Not.
RENAME_MODE = bool(environ.get('RENAME_MODE', False))


# Auto Approve Info: If True Then Bot Approves New Upcoming Join Requests.
AUTO_APPROVE_MODE = bool(environ.get('AUTO_APPROVE_MODE', False))


# Start Command Reactions
REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"]  # don't add any emoji because Telegram may not support all reactions


# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01
