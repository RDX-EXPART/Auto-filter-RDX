import asyncio
import inspect
import ipaddress
import logging
import os
import re
import socket
import tempfile
from urllib.parse import urlparse

try:
    import aiohttp
except ImportError:  # URL thumbnails are optional; Telegram file IDs still work.
    aiohttp = None
from pyrogram.errors import FloodWait


logger = logging.getLogger(__name__)


def _record_value(record, name, default=None):
    if record is None:
        return default
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _media_type(value):
    value = getattr(value, "value", value)
    return str(value or "document").lower()


def _best_thumb(media):
    candidates = []
    for attribute in ("video_cover", "cover", "covers", "video_thumbs", "thumbs"):
        value = getattr(media, attribute, None)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            candidates.extend(value)
        else:
            candidates.append(value)
    if not candidates:
        return None
    thumb = max(
        candidates,
        key=lambda item: (
            (getattr(item, "width", 0) or 0)
            * (getattr(item, "height", 0) or 0),
            getattr(item, "file_size", 0) or 0,
        ),
    )
    return thumb if isinstance(thumb, str) else getattr(thumb, "file_id", None)


def _supports_parameter(method, parameter):
    """Feature-detect Pyrofork/Kurigram parameters across fork versions."""
    try:
        values = inspect.signature(method).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        value.name == parameter or value.kind == inspect.Parameter.VAR_KEYWORD
        for value in values
    )


def _message_media(message):
    """Return ``(type, media)`` for a Telegram media message."""
    if not message or getattr(message, "empty", False):
        return None, None
    media_type = _media_type(getattr(message, "media", None))
    media = getattr(message, media_type, None)
    if media is None:
        for fallback_type in ("video", "document", "audio"):
            media = getattr(message, fallback_type, None)
            if media is not None:
                return fallback_type, media
    return media_type, media


def _normalise_name(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _source_search_queries(file_name):
    """Build progressively broader channel queries for a database filename."""
    tokens = _normalise_name(file_name).split()
    if not tokens:
        return []

    # Title words plus season/episode markers are more reliable than a long
    # technical filename in Telegram's channel search.
    technical = {
        "mkv", "mp4", "avi", "web", "dl", "webrip", "hdrip", "bluray",
        "x264", "x265", "h264", "h265", "aac", "ddp", "atmos", "rdx",
        "480p", "720p", "1080p", "2160p",
    }
    title = [
        token
        for token in tokens
        if token not in technical and not re.fullmatch(r"\d{3,4}p", token)
    ][:4]
    markers = [
        token
        for token in tokens
        if re.fullmatch(r"(?:s|e|ep)\d{1,3}", token)
    ][:2]
    queries = []
    candidates = (
        title + markers,
        title[:2] + markers,
        markers,
        title[:2],
    )
    for candidate in candidates:
        query_tokens = []
        for token in candidate:
            if token not in query_tokens:
                query_tokens.append(token)
        query = " ".join(query_tokens)
        if query and query not in queries:
            queries.append(query)
    return queries or [" ".join(tokens[:4])]


async def _candidate_is_same_file(media, file_id, media_record):
    """Match a channel-search result to the indexed Telegram media."""
    candidate_file_id = getattr(media, "file_id", None)
    if not candidate_file_id:
        return False
    if candidate_file_id == file_id:
        return True

    # Database IDs are shortened Pyrogram file IDs. Recreate that ID from the
    # source candidate for a deterministic comparison whenever possible.
    try:
        from database.ia_filterdb import unpack_new_file_id

        candidate_db_id, _ = unpack_new_file_id(candidate_file_id)
        if candidate_db_id == file_id:
            return True
    except Exception as error:
        logger.debug("Source candidate file-id comparison skipped: %s", error)

    # A conservative compatibility fallback for tests/older Pyrogram forks.
    wanted_size = _record_value(media_record, "file_size")
    candidate_size = getattr(media, "file_size", None)
    if not wanted_size or not candidate_size or int(wanted_size) != int(candidate_size):
        return False
    wanted_tokens = set(_normalise_name(_record_value(media_record, "file_name")).split())
    candidate_tokens = set(_normalise_name(getattr(media, "file_name", None)).split())
    if len(wanted_tokens) < 3 or len(candidate_tokens) < 3:
        return False
    overlap = len(wanted_tokens & candidate_tokens)
    return overlap >= max(3, int(min(len(wanted_tokens), len(candidate_tokens)) * 0.8))


async def _iter_search_messages(client, chat_id, query):
    """Support Pyrogram/Pyrofork search results and lightweight test fakes."""
    results = client.search_messages(chat_id, query=query, limit=100)
    if inspect.isawaitable(results):
        results = await results
    if hasattr(results, "__aiter__"):
        async for message in results:
            yield message
    else:
        for message in results or []:
            yield message


async def _recover_source_message(
    client,
    file_id,
    media_record,
    skipped_source=None,
):
    """Find an old indexed file in configured channels without re-indexing."""
    file_name = _record_value(media_record, "file_name")
    queries = _source_search_queries(file_name)
    if not queries or not hasattr(client, "search_messages"):
        return None

    try:
        from info import CHANNELS
    except Exception as error:
        logger.debug("Index-channel list unavailable for source recovery: %s", error)
        return None

    channels = CHANNELS if isinstance(CHANNELS, (list, tuple, set)) else [CHANNELS]
    seen_channels = set()
    for channel_id in channels:
        if channel_id in seen_channels:
            continue
        seen_channels.add(channel_id)
        seen_messages = set()
        for query in queries:
            try:
                async for message in _iter_search_messages(client, channel_id, query):
                    message_chat_id = getattr(getattr(message, "chat", None), "id", None)
                    message_id = getattr(message, "id", None)
                    message_key = (message_chat_id, message_id)
                    if message_key in seen_messages or skipped_source == message_key:
                        continue
                    seen_messages.add(message_key)
                    _, media = _message_media(message)
                    if media and await _candidate_is_same_file(media, file_id, media_record):
                        logger.info(
                            "Recovered original indexed message %s/%s for %s",
                            message_chat_id,
                            message_id,
                            file_id,
                        )
                        return message
            except Exception as error:
                logger.warning(
                    "Source recovery search failed in channel %s: %s",
                    channel_id,
                    error,
                )
    return None


async def _remember_source(file_id, source_message):
    """Persist recovered source metadata so later deliveries copy immediately."""
    try:
        from database.ia_filterdb import update_file_source

        await update_file_source(file_id, source_message)
    except Exception as error:
        logger.warning("Recovered source metadata could not be saved: %s", error)


async def _copy_source(
    client,
    chat_id,
    source_chat_id,
    source_message_id,
    caption,
    protect_content,
    reply_markup,
):
    # Pyrofork 2.3.x implements copy_message by downloading the source message
    # metadata and calling send_cached_media. That path can replace an HD video
    # cover with Telegram's legacy 320px thumbnail. forward_messages with
    # drop_author=True uses raw messages.ForwardMessages and performs a real
    # server-side copy, preserving the exact media and cover.
    if hasattr(client, "forward_messages"):
        try:
            copied = await _retry_flood_wait(
                lambda: client.forward_messages(
                    chat_id=chat_id,
                    from_chat_id=int(source_chat_id),
                    message_ids=int(source_message_id),
                    protect_content=protect_content,
                    drop_author=True,
                )
            )
        except Exception as error:
            logger.warning("Raw HD source copy failed; trying cached copy: %s", error)
            copied = None
        if isinstance(copied, (list, tuple)):
            copied = copied[0] if copied else None
        if copied is not None:
            copied_id = getattr(copied, "id", None)
            try:
                if caption is not None and copied_id and hasattr(
                    client, "edit_message_caption"
                ):
                    edited = await client.edit_message_caption(
                        chat_id=chat_id,
                        message_id=copied_id,
                        caption=caption,
                        reply_markup=reply_markup,
                    )
                    return edited or copied
                if reply_markup is not None and copied_id and hasattr(
                    client, "edit_message_reply_markup"
                ):
                    edited = await client.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=copied_id,
                        reply_markup=reply_markup,
                    )
                    return edited or copied
                if caption is not None and hasattr(copied, "edit_caption"):
                    edited = await copied.edit_caption(
                        caption,
                        reply_markup=reply_markup,
                    )
                    return edited or copied
            except Exception as error:
                # The exact HD media copy already succeeded. Keep it instead of
                # sending a second lower-quality cached copy.
                logger.warning("HD source copy caption edit failed: %s", error)
            return copied

    kwargs = {
        "chat_id": chat_id,
        "from_chat_id": int(source_chat_id),
        "message_id": int(source_message_id),
        "caption": caption,
        "protect_content": protect_content,
        "reply_markup": reply_markup,
    }
    # Modern Pyrofork/Kurigram can preserve the source video's HD cover when
    # video_cover is explicitly left as None.
    if _supports_parameter(client.copy_message, "video_cover"):
        kwargs["video_cover"] = None
    return await _retry_flood_wait(
        lambda: client.copy_message(**kwargs)
    )


async def _retry_flood_wait(call):
    try:
        return await call()
    except FloodWait as error:
        delay = getattr(error, "value", getattr(error, "x", 0))
        await asyncio.sleep(delay)
        return await call()


async def _send_with_thumb(
    client,
    chat_id,
    file_id,
    file_type,
    thumb,
    caption,
    protect_content,
    reply_markup,
):
    common = {
        "chat_id": chat_id,
        "caption": caption,
        "protect_content": protect_content,
        "reply_markup": reply_markup,
    }
    if file_type == "video":
        # video_cover is the HD cover path exposed by modern Telegram layers.
        # Older forks only support the legacy small `thumb` parameter.
        if _supports_parameter(client.send_video, "video_cover"):
            common["video_cover"] = thumb
        else:
            common["thumb"] = thumb
        return await _retry_flood_wait(
            lambda: client.send_video(
                video=file_id,
                supports_streaming=True,
                **common,
            )
        )
    if file_type == "audio":
        common["thumb"] = thumb
        return await _retry_flood_wait(
            lambda: client.send_audio(audio=file_id, **common)
        )
    common["thumb"] = thumb
    return await _retry_flood_wait(
        lambda: client.send_document(document=file_id, **common)
    )


async def _download_thumb(client, thumb_file_id, directory):
    """Download a Telegram thumbnail so it can be uploaded as a fresh JPEG."""
    if not thumb_file_id:
        return None
    if isinstance(thumb_file_id, str) and os.path.isfile(thumb_file_id):
        return thumb_file_id

    target = os.path.join(directory, "thumb.jpg")
    if isinstance(thumb_file_id, str) and thumb_file_id.startswith(
        ("http://", "https://")
    ):
        if aiohttp is None:
            raise RuntimeError(
                "Remote thumbnail URLs require the aiohttp dependency"
            )
        parsed = urlparse(thumb_file_id)
        if parsed.scheme != "https" or not await _public_host(parsed.hostname):
            raise RuntimeError("Remote thumbnail URL is not a public HTTPS URL")
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                thumb_file_id,
                allow_redirects=False,
            ) as response:
                response.raise_for_status()
                content = await response.read()
        if not content or len(content) > 10 * 1024 * 1024:
            return None
        with open(target, "wb") as output:
            output.write(content)
        return target

    downloaded = await _retry_flood_wait(
        lambda: client.download_media(
            message=thumb_file_id,
            file_name=target,
        )
    )
    downloaded = downloaded or target
    return downloaded if os.path.isfile(downloaded) else None


async def _public_host(hostname):
    hostname = str(hostname or "").strip().lower()
    if not hostname or hostname == "localhost" or hostname.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
        return address.is_global
    except ValueError:
        pass
    try:
        loop = asyncio.get_running_loop()
        results = await loop.getaddrinfo(
            hostname,
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in results
        }
        return bool(addresses) and all(address.is_global for address in addresses)
    except Exception:
        return False


async def _send_with_fresh_thumb(
    client,
    chat_id,
    file_id,
    file_type,
    thumb_file_id,
    caption,
    protect_content,
    reply_markup,
):
    # Telegram does not reliably reuse an existing thumbnail file_id when a
    # cached video/document is sent. Download and upload it as a new JPEG.
    with tempfile.TemporaryDirectory(prefix="rdx_thumb_") as directory:
        thumb_path = await _download_thumb(client, thumb_file_id, directory)
        if not thumb_path:
            raise RuntimeError("Unable to download the indexed thumbnail")
        return await _send_with_thumb(
            client,
            chat_id,
            file_id,
            file_type,
            thumb_path,
            caption,
            protect_content,
            reply_markup,
        )


async def send_media_preserve_thumb(
    client,
    chat_id,
    file_id,
    media_record=None,
    caption=None,
    protect_content=False,
    reply_markup=None,
):
    """Send indexed media without replacing its custom Telegram thumbnail.

    Copying the source message is the only lossless path for a custom thumbnail.
    Explicit thumbnail and cached-media sends are kept as safe fallbacks for old
    database rows or inaccessible source channels.
    """
    source_chat_id = _record_value(media_record, "source_chat_id")
    source_message_id = _record_value(media_record, "source_message_id")
    stored_thumb = _record_value(media_record, "thumb_file_id")
    file_type = _media_type(_record_value(media_record, "file_type"))

    # Search pages may contain an older duplicate from the other MongoDB.
    # Resolve the best matching record before giving up on source-copy mode.
    if not (source_chat_id and source_message_id):
        try:
            from database.ia_filterdb import get_file_details

            details = await get_file_details(file_id)
            if details:
                best_record = details[0]
                source_chat_id = _record_value(
                    best_record,
                    "source_chat_id",
                    source_chat_id,
                )
                source_message_id = _record_value(
                    best_record,
                    "source_message_id",
                    source_message_id,
                )
                stored_thumb = _record_value(
                    best_record,
                    "thumb_file_id",
                    stored_thumb,
                )
                file_type = _media_type(
                    _record_value(best_record, "file_type", file_type)
                )
        except Exception as error:
            logger.debug("Source metadata lookup skipped: %s", error)

    if source_chat_id and source_message_id:
        try:
            copied = await _copy_source(
                client,
                chat_id,
                source_chat_id,
                source_message_id,
                caption,
                protect_content,
                reply_markup,
            )
            logger.info(
                "Copied original indexed message %s/%s to %s",
                source_chat_id,
                source_message_id,
                chat_id,
            )
            return copied
        except Exception as error:
            logger.warning(
                "Source message copy failed for %s/%s: %s",
                source_chat_id,
                source_message_id,
                error,
            )

    # Older rows have no source IDs. Search the configured index channels,
    # compare the actual Telegram file ID, and copy the original post exactly.
    # A successful recovery is stored in MongoDB, so this search happens once.
    recovery_record = media_record
    if not _record_value(recovery_record, "file_name"):
        try:
            from database.ia_filterdb import get_file_details

            details = await get_file_details(file_id)
            if details:
                recovery_record = details[0]
        except Exception as error:
            logger.debug("Recovery metadata lookup skipped: %s", error)

    recovered_message = await _recover_source_message(
        client,
        file_id,
        recovery_record,
        skipped_source=(
            (int(source_chat_id), int(source_message_id))
            if source_chat_id and source_message_id
            else None
        ),
    )
    if recovered_message is not None:
        recovered_chat_id = getattr(
            getattr(recovered_message, "chat", None),
            "id",
            None,
        )
        recovered_message_id = getattr(recovered_message, "id", None)
        _, recovered_media = _message_media(recovered_message)
        if recovered_media:
            stored_thumb = _best_thumb(recovered_media) or stored_thumb
            file_type = _media_type(
                getattr(recovered_message, "media", file_type)
            )
        if recovered_chat_id and recovered_message_id:
            await _remember_source(file_id, recovered_message)
            try:
                return await _copy_source(
                    client,
                    chat_id,
                    recovered_chat_id,
                    recovered_message_id,
                    caption,
                    protect_content,
                    reply_markup,
                )
            except Exception as error:
                logger.warning(
                    "Recovered source copy failed for %s/%s: %s",
                    recovered_chat_id,
                    recovered_message_id,
                    error,
                )

    if source_chat_id and source_message_id:
        try:
            source_message = await _retry_flood_wait(
                lambda: client.get_messages(
                    int(source_chat_id),
                    int(source_message_id),
                )
            )
            if source_message and not source_message.empty and source_message.media:
                source_type = _media_type(source_message.media)
                source_media = getattr(source_message, source_type, None)
                if source_media:
                    fresh_file_id = getattr(source_media, "file_id", None) or file_id
                    fresh_thumb = _best_thumb(source_media) or stored_thumb
                    if fresh_thumb:
                        return await _send_with_fresh_thumb(
                            client,
                            chat_id,
                            fresh_file_id,
                            source_type,
                            fresh_thumb,
                            caption,
                            protect_content,
                            reply_markup,
                        )
        except Exception as error:
            logger.warning(
                "Fresh source thumbnail fallback failed for %s/%s: %s",
                source_chat_id,
                source_message_id,
                error,
            )

    if stored_thumb:
        try:
            return await _send_with_fresh_thumb(
                client,
                chat_id,
                file_id,
                file_type,
                stored_thumb,
                caption,
                protect_content,
                reply_markup,
            )
        except Exception as error:
            logger.warning("Stored thumbnail fallback failed: %s", error)

    return await _retry_flood_wait(
        lambda: client.send_cached_media(
            chat_id=chat_id,
            file_id=file_id,
            caption=caption,
            protect_content=protect_content,
            reply_markup=reply_markup,
        )
    )
