"""TMDB metadata, poster and backdrop helpers.

Uses the TMDB-compatible proxy supplied by the bot owner.  The bot never
needs a TMDB API key; the proxy exposes the v3-style endpoints used here.
"""

import asyncio
import html
import logging
import os
import re
from io import BytesIO

import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)

_TMDB_BASE = "https://tmdbapi.the-zake.workers.dev/3"
_TMDB_HEADERS = {"accept": "application/json"}
TMDB_IMG = "https://image.tmdb.org/t/p/"

# Request formats that Pillow 9.x can decode reliably.  The previous header
# advertised AVIF/WebP first; some CDNs then returned AVIF, which made
# Image.open() fail on deployments using the bundled Pillow version.
_POSTER_HEADERS = {
    "Accept": "image/jpeg,image/png,image/webp;q=0.8,*/*;q=0.5",
    "Referer": "https://www.themoviedb.org/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}
_MAX_POSTER_BYTES = 25 * 1024 * 1024

_CACHE = {}
_CACHE_LOCK = asyncio.Lock()
_CACHE_TTL = 60 * 30


def _extract_year(text):
    years = re.findall(r"\b(19|20)\d{2}\b", text or "")
    if not years:
        return None
    match = re.search(r"\b((?:19|20)\d{2})\b", text or "")
    return match.group(1) if match else None


def _clean_query(query, remove_year=True):
    query = re.sub(r"[._\-:]+", " ", query or "")
    if remove_year:
        # TMDB accepts the release year separately. Keeping it inside the
        # title query can make otherwise valid searches such as
        # "RRR 2022" or "Spider-Man Brand New Day 2026" return no match.
        query = re.sub(r"\b(?:19|20)\d{2}\b", " ", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query


def image_url(path, size="w1280"):
    if not path:
        return None
    return f"{TMDB_IMG}{size}{path}"


# "original" gives the sharpest artwork (Telegram re-compresses anyway); set
# TMDB_BACKDROP_SIZE=w1280 for faster/lighter downloads.
_BACKDROP_SIZE = os.environ.get("TMDB_BACKDROP_SIZE", "original")
if _BACKDROP_SIZE not in ("original", "w1280", "w780"):
    _BACKDROP_SIZE = "original"
_BACKDROP_LANGS = "en,null,hi,ta,te,ml,kn,bn,mr,gu,pa,ur,ko,ja,zh,fr,es,de,it,pt,ru,tr,ar,th,id"


def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _pick_best(results, title, year=None):
    """Choose the most plausible TMDB result instead of blindly taking the first one."""
    if not results:
        return None
    wanted = _norm(title)
    best, best_score = None, -1
    for item in results:
        names = [_norm(item.get(k)) for k in ("title", "name", "original_title", "original_name") if item.get(k)]
        score = 0
        if wanted:
            if wanted in names:
                score += 5000
            elif any(n.startswith(wanted) or wanted.startswith(n) for n in names if n):
                score += 2500
            elif any(wanted in n for n in names):
                score += 1500
        date = str(item.get("release_date") or item.get("first_air_date") or "")
        if year and date[:4] == str(year):
            score += 3000
        score += min(int(item.get("vote_count") or 0), 2000)
        score += min(float(item.get("popularity") or 0), 300) * 5
        if item.get("backdrop_path"):
            score += 50
        if score > best_score:
            best, best_score = item, score
    return best


def _rank_backdrops(backdrops, original_language=None, size=None):
    """Order backdrops so the artwork WITH the title/logo comes first.

    TMDB tags the title-card style backdrops with a language (en, hi, ta ...), while the
    plain scene screenshots have no language (null). The details endpoint's default
    ``backdrop_path`` is usually such a screenshot, which is why the bot kept showing
    screenshots. Priority: English > the movie's original language > any other language
    > no language; inside a group the most voted image wins.
    """
    size = size or _BACKDROP_SIZE
    items = [x for x in (backdrops or []) if x.get("file_path")]

    def aspect(item):
        try:
            value = float(item.get("aspect_ratio") or 0)
        except (TypeError, ValueError):
            value = 0.0
        return value or (int(item.get("width") or 0) / max(int(item.get("height") or 1), 1))

    # Real backdrops are ~16:9 (1.78); anything narrower is a poster-like or odd crop.
    landscape = [x for x in items if aspect(x) >= 1.6]
    items = landscape or items
    original_language = (original_language or "").lower() or None

    def rank(item):
        lang = (item.get("iso_639_1") or "").lower() or None
        if lang == "en":
            group = 3
        elif lang and lang == original_language:
            group = 2
        elif lang:
            group = 1
        else:
            group = 0
        return (
            group,
            int(item.get("vote_count") or 0),
            float(item.get("vote_average") or 0),
            int(item.get("width") or 0),
        )

    items.sort(key=rank, reverse=True)
    return [image_url(x["file_path"], size) for x in items]


def _fmt_runtime(minutes):
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


def _fmt_votes(votes):
    try:
        votes = int(votes or 0)
    except (TypeError, ValueError):
        return "0"
    if votes >= 1000000:
        return f"{votes / 1000000:.1f}M"
    if votes >= 1000:
        return f"{votes / 1000:.1f}K"
    return str(votes)


async def _request_json(endpoint, params=None):
    url = f"{_TMDB_BASE.rstrip('/')}/{endpoint.lstrip('/')}"
    timeout = aiohttp.ClientTimeout(total=12)
    try:
        async with aiohttp.ClientSession(headers=_TMDB_HEADERS, timeout=timeout) as session:
            async with session.get(url, params=params or {}) as response:
                if response.status != 200:
                    logger.warning("TMDB API returned HTTP %s for %s", response.status, endpoint)
                    return None
                return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.warning("TMDB request failed for %s: %s", endpoint, exc)
    except Exception:
        logger.exception("Unexpected TMDB error for %s", endpoint)
    return None


async def search_tmdb(query, bulk=False, file=None):
    """Search TMDB movies and optionally return a single best match."""
    raw = query or ""
    title = _clean_query(raw)
    year = _extract_year(raw)
    if not year and file:
        year = _extract_year(file)

    params = {
        "query": title,
        "include_adult": "false",
        "language": "en-US",
        "page": 1,
    }
    if year:
        params["year"] = year

    data = await _request_json("search/movie", params)
    results = (data or {}).get("results") or []
    if not results and year:
        params.pop("year", None)
        data = await _request_json("search/movie", params)
        results = (data or {}).get("results") or []

    results = [item for item in results if item.get("id")]
    if bulk:
        return results
    return _pick_best(results, title, year)


async def get_tmdb_images(media_id, kind="movie", original_language=None):
    """Return ranked official TMDB posters/backdrops for a movie or TV series.

    Backdrops are ranked with :func:`_rank_backdrops` (title-card artwork first).
    Posters keep the portrait-only filter so a still is never used as a poster.
    """
    data = await _request_json(
        f"{kind}/{media_id}/images",
        {"include_image_language": _BACKDROP_LANGS},
    )
    if not data:
        return {"posters": [], "backdrops": []}

    def poster_score(item):
        vote = float(item.get("vote_average") or 0)
        votes = int(item.get("vote_count") or 0)
        lang = item.get("iso_639_1")
        language_bonus = 3 if lang == "en" else (2 if lang is None else 0)
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        ratio = (width / height) if height else 0
        if ratio < 0.58 or ratio > 0.82:
            return -1
        return (language_bonus * 1000000) + (vote * 10000) + min(votes, 9999) + min(width, 4000) / 10000

    posters = [x for x in (data.get("posters") or []) if x.get("file_path")]
    posters = [x for x in posters if poster_score(x) >= 0]
    posters.sort(key=poster_score, reverse=True)

    return {
        "posters": [image_url(x["file_path"], "w780") for x in posters[:6]],
        "backdrops": _rank_backdrops(data.get("backdrops"), original_language)[:8],
    }


def _finalize_backdrops(result):
    """Put the best title-card backdrop first; keep TMDB's default as a fallback."""
    default = result.get("backdrop")
    ranked = list(result["images"].get("backdrops") or [])
    if ranked:
        result["backdrop"] = ranked[0]
        if default and default not in ranked:
            ranked.append(default)
    elif default:
        ranked = [default]
    result["images"]["backdrops"] = ranked


async def get_tmdb_movie(query, id=False, file=None):
    """Return normalized TMDB movie details for search/result rendering."""
    if id:
        movie_id = str(query)
        cache_key = f"id:{movie_id}"
        search_item = None
    else:
        search_item = await search_tmdb(query, bulk=False, file=file)
        if not search_item:
            return None
        movie_id = str(search_item.get("id"))
        cache_key = f"id:{movie_id}"

    now = asyncio.get_running_loop().time()
    async with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

    details = await _request_json(f"movie/{movie_id}", {"language": "en-US"})
    if not details:
        details = search_item or {}

    # The search result already contains the important image paths.  Keep
    # them when the details endpoint omits them.
    if search_item:
        for key in ("poster_path", "backdrop_path", "title", "release_date", "vote_average", "overview"):
            if not details.get(key) and search_item.get(key):
                details[key] = search_item[key]

    release_date = details.get("release_date") or ""
    year = release_date[:4] if release_date else "N/A"
    genres = ", ".join(g.get("name", "") for g in (details.get("genres") or []) if g.get("name"))
    if not genres:
        genres = "N/A"

    result = {
        "id": details.get("id", movie_id),
        "title": details.get("title") or details.get("original_title") or "Unknown",
        "original_title": details.get("original_title") or details.get("title") or "Unknown",
        "year": year,
        "release_date": release_date or "N/A",
        "genres": genres,
        "rating": f"{float(details.get('vote_average') or 0):.1f}",
        "votes": details.get("vote_count") or 0,
        "runtime": details.get("runtime") or 0,
        "overview": details.get("overview") or "",
        "poster_path": details.get("poster_path"),
        "backdrop_path": details.get("backdrop_path"),
        "poster": image_url(details.get("poster_path"), "w780"),
        "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        "url": f"https://www.themoviedb.org/movie/{details.get('id', movie_id)}",
        "images": {"posters": [], "backdrops": []},
        "media_type": "movie",
        "original_language": details.get("original_language"),
        "languages": [l.get("english_name") or l.get("name") for l in (details.get("spoken_languages") or []) if l.get("english_name") or l.get("name")],
    }

    try:
        result["images"] = await get_tmdb_images(movie_id, "movie", details.get("original_language"))
    except Exception:
        logger.exception("TMDB image list lookup failed for movie id=%s", movie_id)

    # Keep the details endpoint's main poster/backdrop at the front, then add
    # alternate official artwork. Duplicates are removed while preserving order.
    if result.get("poster"):
        result["images"]["posters"] = [result["poster"]] + [
            x for x in result["images"]["posters"] if x != result["poster"]
        ]
    _finalize_backdrops(result)

    async with _CACHE_LOCK:
        _CACHE[cache_key] = (now, result)
    return result



async def search_tmdb_any(query, file=None):
    """Search movies AND series at once and return the best (media_type, id)."""
    raw = query or ""
    title = _clean_query(raw)
    year = _extract_year(raw) or (_extract_year(file) if file else None)
    data = await _request_json(
        "search/multi",
        {"query": title, "include_adult": "false", "language": "en-US", "page": 1},
    )
    results = [
        item for item in ((data or {}).get("results") or [])
        if item.get("id") and item.get("media_type") in ("movie", "tv")
    ]
    if year:
        same_year = [
            item for item in results
            if str(item.get("release_date") or item.get("first_air_date") or "")[:4] == str(year)
        ]
        results = same_year or results
    best = _pick_best(results, title, year)
    return (best.get("media_type"), best.get("id")) if best else (None, None)


async def get_tmdb_any(query, file=None):
    """Return normalized TMDB details for the best movie/series match (or None)."""
    media_type, media_id = await search_tmdb_any(query, file=file)
    if not media_id:
        return None
    lookup = get_tmdb_tv if media_type == "tv" else get_tmdb_movie
    return await lookup(media_id, id=True, file=file)


async def search_tmdb_tv(query, bulk=False, file=None):
    """Search TMDB TV series, keeping a trailing year only as a filter."""
    raw = query or ""
    title = _clean_query(raw)
    year = _extract_year(raw)
    if not year and file:
        year = _extract_year(file)
    params = {
        "query": title,
        "include_adult": "false",
        "language": "en-US",
        "page": 1,
    }
    if year:
        params["first_air_date_year"] = year
    data = await _request_json("search/tv", params)
    results = (data or {}).get("results") or []
    if not results and year:
        params.pop("first_air_date_year", None)
        data = await _request_json("search/tv", params)
        results = (data or {}).get("results") or []
    results = [item for item in results if item.get("id")]
    return results if bulk else _pick_best(results, title, year)


async def get_tmdb_tv(query, id=False, file=None):
    """Return normalized TMDB TV metadata and the series' main artwork."""
    if id:
        series_id = str(query)
        search_item = None
    else:
        search_item = await search_tmdb_tv(query, bulk=False, file=file)
        if not search_item:
            return None
        series_id = str(search_item.get("id"))

    now = asyncio.get_running_loop().time()
    cache_key = f"tv:{series_id}"
    async with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

    details = await _request_json(f"tv/{series_id}", {"language": "en-US"})
    if not details:
        details = search_item or {}
    if search_item:
        for key in ("poster_path", "backdrop_path", "name", "first_air_date", "vote_average", "overview"):
            if not details.get(key) and search_item.get(key):
                details[key] = search_item[key]

    release_date = details.get("first_air_date") or ""
    year = release_date[:4] if release_date else "N/A"
    genres = ", ".join(g.get("name", "") for g in (details.get("genres") or []) if g.get("name")) or "N/A"
    result = {
        "id": details.get("id", series_id),
        "title": details.get("name") or details.get("original_name") or "Unknown",
        "original_title": details.get("original_name") or details.get("name") or "Unknown",
        "year": year,
        "release_date": release_date or "N/A",
        "genres": genres,
        "rating": f"{float(details.get('vote_average') or 0):.1f}",
        "votes": details.get("vote_count") or 0,
        "runtime": ((details.get("episode_run_time") or [0])[0] if details.get("episode_run_time") else 0),
        "overview": details.get("overview") or "",
        "poster_path": details.get("poster_path"),
        "backdrop_path": details.get("backdrop_path"),
        "poster": image_url(details.get("poster_path"), "w780"),
        "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        "url": f"https://www.themoviedb.org/tv/{details.get('id', series_id)}",
        "images": {"posters": [], "backdrops": []},
        "media_type": "tv",
        "original_language": details.get("original_language"),
        "languages": [l.get("english_name") or l.get("name") for l in (details.get("spoken_languages") or []) if l.get("english_name") or l.get("name")],
    }

    try:
        result["images"] = await get_tmdb_images(series_id, "tv", details.get("original_language"))
    except Exception:
        logger.exception("TMDB TV image list lookup failed for id=%s", series_id)

    if result.get("poster"):
        result["images"]["posters"] = [result["poster"]] + [x for x in result["images"]["posters"] if x != result["poster"]]
    _finalize_backdrops(result)

    async with _CACHE_LOCK:
        _CACHE[cache_key] = (now, result)
    return result


_LANGUAGE_ALIASES = {
    "Hindi": ("hindi", "hin"), "English": ("english", "eng"), "Tamil": ("tamil", "tam"),
    "Telugu": ("telugu", "tel"), "Malayalam": ("malayalam", "mal"), "Kannada": ("kannada", "kan"),
    "Bengali": ("bengali", "ben"), "Punjabi": ("punjabi", "pun"), "Marathi": ("marathi", "mar"),
    "Korean": ("korean", "kor"), "Japanese": ("japanese", "jpn"), "Chinese": ("chinese", "chi"),
}
CAPTION_LIMIT = 1024


def _detect_from_files(files):
    """Languages, qualities and audio found in the matching file names."""
    blob = " ".join(str(f.get("file_name", "")) for f in (files or [])[:10]).lower()
    languages = [
        name for name, aliases in _LANGUAGE_ALIASES.items()
        if any(re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", blob) for a in aliases)
    ]
    qualities = [q for q in ("2160p", "1080p", "720p", "480p") if q in blob]
    audio = next((a for a in ("Atmos", "DDP 5.1", "DDP5.1", "DD 5.1", "DTS", "AAC") if a.lower() in blob), None)
    return languages, qualities, audio


SEPARATOR = "━━━━━━━━━━━━━━━━━━"


def build_tmdb_card(match, files, search, requester, seconds=None, chat_title="", notice=None):
    """Build a movie metadata caption without a synopsis or auto-delete notice."""
    esc = lambda value: html.escape(str(value or ""), quote=False)
    icon = "📺" if match.get("media_type") == "tv" else "🎬"
    title = esc(match.get("title") or search)
    year = match.get("year")
    heading = f"{icon} <b>{title}"
    if year and str(year) != "N/A":
        heading += f" ({esc(year)})"
    heading += "</b>"

    try:
        rating = float(match.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0.0
    try:
        votes = int(match.get("votes") or 0)
    except (TypeError, ValueError):
        votes = 0

    info = []
    if rating > 0:
        vote_text = f" ({_fmt_votes(votes)} {'Vote' if votes == 1 else 'Votes'})" if votes else ""
        info.append(f"⭐ <b>{rating:.1f}/10</b>{vote_text}")

    genres = [
        genre.strip()
        for genre in str(match.get("genres") or "").split(",")
        if genre.strip() and genre.strip().casefold() != "n/a"
    ]
    if genres:
        info.append("🎭 <b>Genre:</b> " + " • ".join(esc(genre) for genre in genres[:4]))

    file_languages, qualities, _audio = _detect_from_files(files)
    languages = file_languages or [l for l in (match.get("languages") or []) if l][:4]
    if languages:
        info.append("🌐 <b>Language:</b> " + " • ".join(esc(l) for l in languages[:5]))
    runtime = _fmt_runtime(match.get("runtime"))
    if runtime:
        info.append(f"⏱️ <b>Runtime:</b> {runtime}")
    if qualities:
        info.append("🎞️ <b>Quality:</b> " + " • ".join(qualities))

    footer = [
        f"👤 <b>Requested by:</b> {requester or 'User'}",
        f"📢 <b>Powered by:</b> {esc(chat_title)}" if chat_title else "",
    ]
    lines = [heading, SEPARATOR, *info, SEPARATOR, *[line for line in footer if line]]
    return "\n".join(lines)


async def fetch_tmdb_image(url, backdrop=False):
    """Download a TMDB image and return a Telegram-safe JPEG buffer.

    If the requested size cannot be fetched/decoded, smaller TMDB sizes of the same
    file are tried before giving up.
    """
    if not url:
        return None
    candidates = [url]
    match = re.match(r"^(https://image\.tmdb\.org/t/p/)([^/]+)(/.+)$", url)
    if match:
        for size in ("w1280", "w780", "w500"):
            alt = f"{match.group(1)}{size}{match.group(3)}"
            if alt not in candidates:
                candidates.append(alt)
    for candidate in candidates:
        buffer = await _download_tmdb_image(candidate, backdrop)
        if buffer is not None:
            return buffer
    return None


async def _download_tmdb_image(url, backdrop=False):
    timeout = aiohttp.ClientTimeout(total=25)
    try:
        async with aiohttp.ClientSession(headers=_POSTER_HEADERS, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if response.status != 200:
                    logger.warning("TMDB image HTTP %s: %s", response.status, url)
                    return None
                content = await response.read()
                if not content or len(content) > _MAX_POSTER_BYTES:
                    logger.warning("TMDB image empty/too large (%s bytes): %s", len(content or b""), url)
                    return None

        try:
            image = Image.open(BytesIO(content))
            image.load()
        except Exception:
            logger.warning(
                "TMDB image could not be decoded (content-type=%s, bytes=%s): %s",
                content_type, len(content), url,
            )
            return None

        image = image.convert("RGB")
        max_size = (1920, 1080) if backdrop else (1000, 1500)
        image.thumbnail(max_size, Image.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        output.seek(0)
        output.name = "tmdb_backdrop.jpg" if backdrop else "tmdb_poster.jpg"
        logger.info("TMDB %s image prepared successfully", "backdrop" if backdrop else "poster")
        return output
    except Exception as exc:
        logger.exception("TMDB image fetch failed: %s", exc)
        return None
