# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import asyncio, logging, re, base64, json, time
from threading import Lock
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER, MAX_B_TN
from search_filters import (
    build_search_pattern,
    clean_display_filename,
    extract_episode_numbers,
    extract_filter_values,
    extract_individual_episode_numbers,
    extract_season_numbers,
    is_series_file,
    make_filter_query,
    matches_filter,
    parse_filter_query,
)

# The bot uses exactly one MongoDB database. Every file record, search, stats
# count, duplicate check and delete goes through this single collection.
client = MongoClient(DATABASE_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

logger = logging.getLogger(__name__)
_file_indexes_ready = False
_file_indexes_lock = Lock()
_SEARCH_PAGE_CACHE = {}
_SEARCH_PAGE_CACHE_TTL = 60
_SEARCH_PAGE_CACHE_MAX = 400


def ensure_file_indexes():
    """Create non-unique lookup indexes on file_id and file_name, once per process.

    Existing indexes and documents are never dropped or rebuilt here; a missing
    index is only added.
    """
    global _file_indexes_ready
    if _file_indexes_ready:
        return

    with _file_indexes_lock:
        if _file_indexes_ready:
            return

        try:
            existing_keys = {
                tuple(index["key"].items())
                for index in col.list_indexes()
            }
            for field in ("file_id", "file_name"):
                key_pattern = ((field, 1),)
                if key_pattern not in existing_keys:
                    col.create_index([(field, 1)])
                    existing_keys.add(key_pattern)
                    logger.info("Created file lookup index %s on %s", field, col.full_name)
        except Exception:
            # Lookups still work without these indexes (only slower). Keep indexing
            # running and log once per process instead of failing every save.
            logger.exception("Could not ensure file lookup indexes; continuing with existing indexes")

        _file_indexes_ready = True


async def save_file(media, source_message=None):
    """Save indexed media plus source-message and thumbnail metadata.

    Returns (saved: bool, code: int) where code is 1 for saved, 0 for duplicate
    and 2 for a non-database error. Transient MongoDB errors (PyMongoError) are
    re-raised so the caller can retry the batch instead of skipping the file.
    """
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)
    # Keep indexed titles clean; older records are cleaned only for display.
    new_file_name = clean_display_filename(file_name)

    # Keep the best available Telegram thumbnail and source message for lossless copy.
    # Pyrogram exposes thumbnails on the media object; some channel posts expose
    # them only through the media attached to the original Message.
    thumbs = []
    for _holder in (media, getattr(source_message, getattr(getattr(source_message, "media", None), "value", "") or "", None)):
        for _name in ("video_cover", "cover", "covers", "video_thumbs", "thumbs"):
            _value = getattr(_holder, _name, None) if _holder is not None else None
            if _value:
                thumbs.extend(_value if isinstance(_value, (list, tuple)) else [_value])
    thumb = max(
        thumbs,
        key=lambda item: (
            (getattr(item, "width", 0) or 0) * (getattr(item, "height", 0) or 0),
            getattr(item, "file_size", 0) or 0,
        ),
        default=None,
    )
    thumb_file_id = getattr(thumb, "file_id", None) if thumb else None
    source_chat = getattr(source_message, "chat", None)
    source_media_type = getattr(getattr(source_message, "media", None), "value", None)
    file = {
        'file_id': file_id,
        'file_name': new_file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None,
        'thumb_file_id': thumb_file_id,
        'source_chat_id': getattr(source_chat, "id", None),
        'source_message_id': getattr(source_message, "id", None),
        'file_type': source_media_type or ('video' if getattr(media, 'width', None) else 'document'),
    }

    # PyMongo is synchronous: run every DB touch in a worker thread so the event
    # loop (and the rest of the bot) keeps serving updates while we write.
    await asyncio.to_thread(ensure_file_indexes)

    try:
        saved_result = await asyncio.to_thread(_save_file_db, file, file_name, file_id)
        if saved_result[0]:
            clear_filter_discovery_cache()
        return saved_result
    except PyMongoError:
        raise
    except Exception:
        logger.exception("Unexpected error while saving %s", file_name)
        return False, 2


def _save_file_db(file, file_name, file_id):
    """Synchronous part of save_file. Runs in a worker thread."""
    existing = col.find_one({'file_id': file_id})
    if existing:
        # Backfill source-message/thumbnail details when an older indexed entry
        # is encountered again; this upgrades lossless delivery without adding
        # a duplicate database row.
        missing_metadata = {
            key: value
            for key, value in file.items()
            if value is not None and existing.get(key) in (None, "")
        }
        if missing_metadata:
            col.update_one(
                {'_id': existing['_id']},
                {'$set': missing_metadata},
            )
        return False, 0
    if is_file_already_saved(file_name):
        return False, 0

    try:
        col.insert_one(file)
        print(f"{file_name} is successfully saved.")
        return True, 1
    except DuplicateKeyError:
        print(f"{file_name} is already saved.")
        return False, 0


def clean_file_name(file_name):
    """Clean and format the file name."""
    file_name = clean_display_filename(file_name)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name))
    unwanted_chars = ['[', ']', '(', ')', '{', '}']

    for char in unwanted_chars:
        file_name = file_name.replace(char, '')

    old_file_name = ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))
    # Keep episode markers such as S01E01 intact (they used to become "S01E 01").
    return old_file_name

def add_space_between_e_and_number(input_string):
    # Use regex to find 'e' or 'E' followed by a digit and add a space
    output_string = re.sub(r'(e|E)([0-9])', r'\1 \2', input_string)
    return output_string

def is_file_already_saved(file_name):
    """Check duplicate names after the file_id lookup has already failed."""
    if col.find_one({'file_name': file_name}, {'_id': 0, 'file_name': 1}):
        print(f"{file_name} is already saved.")
        return True
    return False

def _get_search_results_sync(
    chat_id, query, file_type=None, max_results=10, offset=0, filter=False,
    fast_page=False,
):
    """Return a stable page of matching records from the configured file collection."""
    query = str(query or "").strip()
    try:
        offset = max(0, int(offset or 0))
        max_results = max(1, int(max_results or 10))
    except (TypeError, ValueError):
        offset, max_results = 0, 10

    base_query, selected = parse_filter_query(query)
    # Episode ranges (e.g. E13-E16) must match each episode they contain. Fetch
    # candidates using the title and all other constraints, then test episodes.
    candidate_query = make_filter_query(query, episode=None) if selected.get("episode") else query
    try:
        regex = re.compile(build_search_pattern(candidate_query), flags=re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(base_query or "."), flags=re.IGNORECASE)
    criteria = {"file_name": regex}
    if USE_CAPTION_FILTER:
        criteria = {"$or": [{"file_name": regex}, {"caption": regex}]}
    if file_type:
        criteria = {"$and": [criteria, {"file_type": file_type}]}

    if fast_page and not selected.get("episode"):
        # The exact count would scan the same regex-matched collection again.
        # Fetch one extra row instead: it tells the pager whether a next page
        # exists without blocking on count_documents for large Mongo collections.
        page_plus_one = list(
            col.find(criteria)
            .sort("$natural", -1)
            .skip(offset)
            .limit(max_results + 1)
        )
        has_more = len(page_plus_one) > max_results
        page = page_plus_one[:max_results]
        total_results = offset + len(page) + (1 if has_more else 0)
    elif selected.get("episode"):
        all_records = list(col.find(criteria).sort("$natural", -1))
        matching = [
            record for record in all_records
            if matches_filter(
                " ".join(
                    str(value) for value in (
                        record.get("file_name", ""),
                        record.get("caption", ""),
                    ) if value
                ),
                query,
            )
        ]
        total_results = len(matching)
        page = matching[offset:offset + max_results]
    else:
        total_results = col.count_documents(criteria)
        page = list(
            col.find(criteria)
            .sort("$natural", -1)
            .skip(offset)
            .limit(max_results)
        )

    # Return copies to callers so the stored name is cleaned for display only;
    # the Mongo documents themselves are left untouched.
    files = []
    for record in page:
        visible = dict(record)
        visible["file_name"] = clean_display_filename(visible.get("file_name"))
        files.append(visible)
    next_offset = "" if offset + len(page) >= total_results else offset + len(page)
    return files, next_offset, total_results



async def get_search_results(
    chat_id, query, file_type=None, max_results=10, offset=0, filter=False,
    fast_page=False,
):
    cache_key = None
    try:
        page_offset = max(0, int(offset or 0))
        page_size = max(1, int(max_results or 10))
    except (TypeError, ValueError):
        page_offset, page_size = 0, 10

    if fast_page:
        cache_key = (
            chat_id, str(query or "").strip().casefold(), file_type,
            page_size, page_offset,
        )
        cached = _SEARCH_PAGE_CACHE.get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            files, next_offset, total = cached[1]
            return [dict(file) for file in files], next_offset, total
        if cached:
            _SEARCH_PAGE_CACHE.pop(cache_key, None)

    started_at = time.monotonic()
    result = await asyncio.to_thread(
        _get_search_results_sync,
        chat_id,
        query,
        file_type,
        max_results,
        offset,
        filter,
        fast_page,
    )
    if cache_key is not None:
        if len(_SEARCH_PAGE_CACHE) >= _SEARCH_PAGE_CACHE_MAX:
            now = time.monotonic()
            expired = [
                key for key, value in _SEARCH_PAGE_CACHE.items()
                if value[0] <= now
            ]
            for key in expired:
                _SEARCH_PAGE_CACHE.pop(key, None)
            if len(_SEARCH_PAGE_CACHE) >= _SEARCH_PAGE_CACHE_MAX:
                _SEARCH_PAGE_CACHE.clear()
        _SEARCH_PAGE_CACHE[cache_key] = (
            time.monotonic() + _SEARCH_PAGE_CACHE_TTL,
            result,
        )
    elapsed = time.monotonic() - started_at
    if elapsed >= 2:
        logger.warning(
            "Slow file search: %.2fs (query length=%s, page size=%s)",
            elapsed,
            len(str(query or "")),
            max_results,
        )
    return result


def _get_episode_counts_sync(query, max_scan=5000):
    """Count episodes in matching files in the configured file collection."""
    query = make_filter_query(query, episode=None)
    try:
        regex = re.compile(build_search_pattern(query), flags=re.IGNORECASE)
    except re.error:
        return {}
    criteria = {"file_name": regex}
    if USE_CAPTION_FILTER:
        criteria = {"$or": [{"file_name": regex}, {"caption": regex}]}
    counts = {}
    cursor = col.find(
        criteria,
        {"file_name": 1, "caption": 1},
    ).sort("$natural", -1).limit(max_scan)
    for record in cursor:
        text = " ".join(
            str(value) for value in (
                record.get("file_name", ""),
                record.get("caption", ""),
            ) if value
        )
        for episode in extract_episode_numbers(text):
            if episode <= 100:
                counts[episode] = counts.get(episode, 0) + 1
    return dict(sorted(counts.items()))



async def get_episode_counts(query, max_scan=5000):
    return await asyncio.to_thread(_get_episode_counts_sync, query, max_scan)


def _discover_filter_values(query, max_scan):
    """Read a bounded set of title-matching records and derive real filter values."""
    base_query = make_filter_query(
        query,
        language=None,
        season=None,
        episode=None,
        quality=None,
        year=None,
        combined=None,
    )
    try:
        regex = re.compile(build_search_pattern(base_query), flags=re.IGNORECASE)
    except re.error:
        return {
            "languages": [], "qualities": [], "years": [],
            "seasons": [], "episodes": [], "combined": False,
        }

    criteria = {"file_name": regex}
    if USE_CAPTION_FILTER:
        criteria = {"$or": [{"file_name": regex}, {"caption": regex}]}

    _, selected = parse_filter_query(query)
    found = {
        "languages": set(),
        "qualities": set(),
        "years": set(),
        "seasons": set(),
        "episodes": set(),
        "combined": False,
    }
    scoped_queries = {
        kind: make_filter_query(query, **{kind: None})
        for kind in ("language", "quality", "year", "season", "episode", "combined")
    }
    cursor = (
        col.find(criteria, {"file_name": 1, "caption": 1, "_id": 0})
        .sort("$natural", -1)
        .limit(max_scan)
    )
    records = list(cursor)

    for record in records:
        filename = str(record.get("file_name") or "")
        caption = str(record.get("caption") or "")
        text = " ".join(
            value for value in (filename, caption) if value
        )
        series_record = is_series_file(filename) or is_series_file(caption)
        if selected.get("media") == "series" and not series_record:
            continue
        if selected.get("media") == "movie" and series_record:
            continue

        filename_series = is_series_file(filename)
        values = extract_filter_values(filename)
        caption_values = extract_filter_values(caption)
        for kind in ("languages", "qualities", "years"):
            if not values[kind]:
                values[kind] = caption_values[kind]
        if not filename_series and series_record:
            values["seasons"] = caption_values["seasons"]
            values["episodes"] = caption_values["episodes"]
            values["combined"] = caption_values["combined"]
        for kind, scoped_query in scoped_queries.items():
            if not matches_filter(text, scoped_query):
                continue
            if kind == "language":
                found["languages"].update(values["languages"])
            elif kind == "quality":
                found["qualities"].update(values["qualities"])
            elif kind == "year":
                found["years"].update(values["years"])
            elif kind == "season":
                found["seasons"].update(values["seasons"])
            elif kind == "episode":
                found["episodes"].update(values["episodes"])
            elif kind == "combined" and values["combined"]:
                found["combined"] = True

    quality_order = {"360p": 0, "480p": 1, "720p": 2, "1080p": 3, "1440p": 4, "2160p": 5}
    return {
        "languages": sorted(found["languages"]),
        "qualities": sorted(found["qualities"], key=lambda value: quality_order.get(value, 99)),
        "years": sorted(found["years"]),
        "seasons": sorted(found["seasons"]),
        "episodes": sorted(value for value in found["episodes"] if value > 0),
        "combined": found["combined"],
    }


def _episode_values_for_season(query, season, max_scan):
    """Episode numbers that uploaded files of one season actually have."""
    base_query = make_filter_query(
        query, language=None, season=None, episode=None, quality=None, year=None, combined=None,
    )
    try:
        regex = re.compile(build_search_pattern(base_query), flags=re.IGNORECASE)
    except re.error:
        return []
    criteria = {'file_name': regex}
    if USE_CAPTION_FILTER:
        criteria = {'$or': [criteria, {'caption': regex}]}
    episodes = set()
    cursor = col.find(criteria, {'file_name': 1, 'caption': 1}).sort('$natural', -1).limit(max_scan)
    for record in cursor:
        text = " ".join(
            str(value) for value in (record.get('file_name', ''), record.get('caption', '')) if value
        )
        if season in extract_season_numbers(text):
            episodes.update(n for n in extract_individual_episode_numbers(text) if 0 < n <= 999)
    return sorted(episodes)


async def get_episode_values(query, season, max_scan=10000):
    """Episodes available for one season of a series. Never guesses from metadata."""
    try:
        season = int(season)
        max_scan = min(max(1, int(max_scan)), 20000)
    except (TypeError, ValueError):
        return []
    return await asyncio.to_thread(_episode_values_for_season, query, season, max_scan)


_DISCOVERY_CACHE = {}
_DISCOVERY_TTL = 120  # seconds. Repeated button presses reuse one scan; new uploads appear within 2 minutes.
_DISCOVERY_INFLIGHT = {}


def get_cached_filter_values(query, max_scan=10000):
    """Return cached filter values without starting or waiting for a Mongo scan."""
    try:
        max_scan = min(max(1, int(max_scan)), 20000)
    except (TypeError, ValueError):
        max_scan = 10000
    cache_key = (str(query or "").strip().casefold(), max_scan)
    cached = _DISCOVERY_CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]
    return None


def clear_filter_discovery_cache():
    """Invalidate per-process filter and page caches after file-index changes."""
    _DISCOVERY_CACHE.clear()
    _SEARCH_PAGE_CACHE.clear()


async def get_available_filter_values(query, max_scan=10000):
    """Return database-backed filters, without loading the whole media collection.

    The scan runs in a worker thread and its result is cached briefly, so pressing
    Quality, Language, Season or Next does not rescan the collection each time.
    """
    try:
        max_scan = min(max(1, int(max_scan)), 20000)
    except (TypeError, ValueError):
        max_scan = 10000
    cache_key = (str(query or "").strip().casefold(), max_scan)
    cached = get_cached_filter_values(query, max_scan)
    if cached is not None:
        return cached

    task = _DISCOVERY_INFLIGHT.get(cache_key)
    started_scan = task is None
    if task is None:
        task = asyncio.create_task(
            asyncio.to_thread(_discover_filter_values, query, max_scan)
        )
        _DISCOVERY_INFLIGHT[cache_key] = task
    started_at = time.monotonic()
    try:
        result = await task
    finally:
        if task.done() and _DISCOVERY_INFLIGHT.get(cache_key) is task:
            _DISCOVERY_INFLIGHT.pop(cache_key, None)
    if started_scan:
        elapsed = time.monotonic() - started_at
        if elapsed >= 2:
            logger.warning(
                "Slow filter-value discovery: %.2fs (scan cap=%s)",
                elapsed,
                max_scan,
            )
    if len(_DISCOVERY_CACHE) > 500:
        _DISCOVERY_CACHE.clear()
    _DISCOVERY_CACHE[cache_key] = (time.time() + _DISCOVERY_TTL, result)
    return result


async def get_bad_files(query, file_type=None, use_filter=False):
    """For given query return (results, total_results)."""
    query = query.strip()

    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){query}(\b|[.+-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[s.+-_]')

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        return [], 0

    filter_criteria = {'file_name': regex}
    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}

    total_results = col.count_documents(filter_criteria)
    files = list(col.find(filter_criteria))
    return files, total_results

def _get_file_details_sync(query):
    record = col.find_one({'file_id': query})
    if record and record.get("file_name"):
        record["file_name"] = clean_display_filename(record["file_name"])
    return record



async def get_file_details(query):
    return await asyncio.to_thread(_get_file_details_sync, query)


async def update_file_source(file_id, source_message):
    """Persist a source message recovered by media_delivery for future copies."""
    source_chat = getattr(source_message, "chat", None)
    media_type = getattr(getattr(source_message, "media", None), "value", None)
    media_type = str(media_type).lower() if media_type else None
    media = getattr(source_message, media_type, None) if media_type else None
    thumbs = []
    for name in ("video_cover", "cover", "covers", "video_thumbs", "thumbs"):
        value = getattr(media, name, None)
        if value:
            thumbs.extend(value if isinstance(value, (list, tuple)) else [value])
    thumb = max(
        thumbs,
        key=lambda item: (
            (getattr(item, "width", 0) or 0) * (getattr(item, "height", 0) or 0),
            getattr(item, "file_size", 0) or 0,
        ),
        default=None,
    )
    metadata = {
        "source_chat_id": getattr(source_chat, "id", None),
        "source_message_id": getattr(source_message, "id", None),
        "file_type": media_type or "document",
    }
    if thumb and getattr(thumb, "file_id", None):
        metadata["thumb_file_id"] = thumb.file_id
    metadata = {key: value for key, value in metadata.items() if value is not None}

    result = col.update_one(
        {"file_id": file_id},
        {"$set": metadata},
    )
    return bool(getattr(result, "matched_count", 0))


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    """Return file_id"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id
