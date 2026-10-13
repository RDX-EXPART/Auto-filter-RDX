# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, base64, json
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN
from search_filters import build_search_pattern, clean_display_filename, extract_episode_numbers, make_filter_query, matches_filter, parse_filter_query

# First Database For File Saving 
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

# Second Database For File Saving
sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]


async def save_file(media, source_message=None):
    """Save indexed media plus source-message and thumbnail metadata."""
    
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

    existing = col.find_one({'file_id': file_id}) or sec_col.find_one({'file_id': file_id})
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
            collection = col if col.find_one({'file_id': file_id}) else sec_col
            collection.update_one(
                {'_id': existing['_id']},
                {'$set': missing_metadata},
            )
        return False, 0
    if is_file_already_saved(file_id, file_name):
        return False, 0

    try:
        col.insert_one(file)
        print(f"{file_name} is successfully saved.")
        return True, 1
    except DuplicateKeyError:
        print(f"{file_name} is already saved.")
        return False, 0
    except:
        if MULTIPLE_DATABASE:
            try:
                sec_col.insert_one(file)
                print(f"{file_name} is successfully saved.")
                return True, 1
            except DuplicateKeyError:
                print(f"{file_name} is already saved.")
                return False, 0
        else:
            print("Your Current File Database Is Full, Turn On Multiple Database Feature And Add Second File Mongodb To Save File.")

def clean_file_name(file_name):
    """Clean and format the file name."""
    file_name = clean_display_filename(file_name)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name)) 
    unwanted_chars = ['[', ']', '(', ')', '{', '}']
    
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')
        
    old_file_name = ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))
    new_file_name = add_space_between_e_and_number(old_file_name)
    return new_file_name

def add_space_between_e_and_number(input_string):
    # Use regex to find 'e' or 'E' followed by a digit and add a space
    output_string = re.sub(r'(e|E)([0-9])', r'\1 \2', input_string)
    return output_string
    
def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in either collection."""
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}

    for collection in [col, sec_col]:
        if collection.find_one(found1) or collection.find_one(found):
            print(f"{file_name} is already saved.")
            return True
            
    return False

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Return a stable page of matching records from one or both file databases."""
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

    collections = [col, sec_col] if MULTIPLE_DATABASE else [col]
    if selected.get("episode"):
        all_records = []
        for collection in collections:
            all_records.extend(collection.find(criteria).sort("$natural", -1))
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
        total_results = sum(collection.count_documents(criteria) for collection in collections)
        remaining_skip = offset
        remaining_limit = max_results
        page = []
        for collection in collections:
            collection_count = collection.count_documents(criteria)
            local_skip = min(remaining_skip, collection_count)
            remaining_skip -= local_skip
            if remaining_limit <= 0:
                break
            records = list(
                collection.find(criteria)
                .sort("$natural", -1)
                .skip(local_skip)
                .limit(remaining_limit)
            )
            page.extend(records)
            remaining_limit -= len(records)

    # Return copies to callers so the legacy database prefix is not displayed
    # in file buttons/captions, while keeping existing Mongo documents intact.
    files = []
    for record in page:
        visible = dict(record)
        visible["file_name"] = clean_display_filename(visible.get("file_name"))
        files.append(visible)
    next_offset = "" if offset + len(page) >= total_results else offset + len(page)
    return files, next_offset, total_results


async def get_episode_counts(query, max_scan=5000):
    """Count episodes in matching files across all configured file databases."""
    query = make_filter_query(query, episode=None)
    try:
        regex = re.compile(build_search_pattern(query), flags=re.IGNORECASE)
    except re.error:
        return {}
    criteria = {"file_name": regex}
    if USE_CAPTION_FILTER:
        criteria = {"$or": [{"file_name": regex}, {"caption": regex}]}
    collections = [col, sec_col] if MULTIPLE_DATABASE else [col]
    counts = {}
    for collection in collections:
        cursor = collection.find(
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

async def get_bad_files(query, file_type=None, use_filter=False):
    """For given query return (results, next_offset)"""
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

    def count_documents(collection):
        return collection.count_documents(filter_criteria)

    total_results = (count_documents(col) + count_documents(sec_col) if MULTIPLE_DATABASE else count_documents(col))

    def find_documents(collection):
        return list(collection.find(filter_criteria))

    files = (find_documents(col) + find_documents(sec_col) if MULTIPLE_DATABASE else find_documents(col))

    return files, total_results

async def get_file_details(query):
    return col.find_one({'file_id': query}) or sec_col.find_one({'file_id': query})


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

    for collection in (col, sec_col):
        result = collection.update_one(
            {"file_id": file_id},
            {"$set": metadata},
        )
        if getattr(result, "matched_count", 0):
            return True
    return False


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
    

