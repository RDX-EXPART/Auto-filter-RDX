"""TMDB metadata, poster and backdrop helpers.

Uses the TMDB-compatible proxy supplied by the bot owner.  The bot never
needs a TMDB API key; the proxy exposes the v3-style endpoints used here.
"""

import asyncio
import logging
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
    return results[0] if results else None


async def get_tmdb_images(movie_id):
    """Return ranked official TMDB posters/backdrops for a movie.

    Posters are kept strictly in poster orientation, while backdrops are
    kept in landscape orientation. This prevents a random-looking still from
    being selected as the primary poster. TMDB's own vote metadata is used
    to put the most established/main artwork first.
    """
    data = await _request_json(
        f"movie/{movie_id}/images",
        {"include_image_language": "en,null", "language": "en-US"},
    )
    if not data:
        return {"posters": [], "backdrops": []}

    def score(item, poster=False):
        vote = float(item.get("vote_average") or 0)
        votes = int(item.get("vote_count") or 0)
        lang = item.get("iso_639_1")
        language_bonus = 3 if lang == "en" else (2 if lang is None else 0)
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        ratio = (width / height) if height else 0
        if poster:
            # A genuine poster is portrait; reject landscape artwork even if
            # the API happens to classify it as a poster.
            if ratio < 0.58 or ratio > 0.82:
                return -1
        else:
            # A genuine backdrop is landscape. Very narrow/portrait images
            # are usually unsuitable stills for the result card.
            if ratio < 1.45:
                return -1
        return (language_bonus * 1000000) + (vote * 10000) + min(votes, 9999) + min(width, 4000) / 10000

    posters = [x for x in (data.get("posters") or []) if x.get("file_path")]
    backdrops = [x for x in (data.get("backdrops") or []) if x.get("file_path")]
    posters = [x for x in posters if score(x, True) >= 0]
    backdrops = [x for x in backdrops if score(x, False) >= 0]
    posters.sort(key=lambda x: score(x, True), reverse=True)
    backdrops.sort(key=lambda x: score(x, False), reverse=True)

    return {
        "posters": [image_url(x["file_path"], "w780") for x in posters[:6]],
        "backdrops": [image_url(x["file_path"], "w1280") for x in backdrops[:6]],
    }


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
    }

    try:
        result["images"] = await get_tmdb_images(movie_id)
    except Exception:
        logger.exception("TMDB image list lookup failed for movie id=%s", movie_id)

    # Keep the details endpoint's main poster/backdrop at the front, then add
    # alternate official artwork. Duplicates are removed while preserving order.
    if result.get("poster"):
        result["images"]["posters"] = [result["poster"]] + [
            x for x in result["images"]["posters"] if x != result["poster"]
        ]
    if result.get("backdrop"):
        result["images"]["backdrops"] = [result["backdrop"]] + [
            x for x in result["images"]["backdrops"] if x != result["backdrop"]
        ]

    async with _CACHE_LOCK:
        _CACHE[cache_key] = (now, result)
    return result



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
    return results if bulk else (results[0] if results else None)


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
    }

    # For series, the /tv/{id} detail backdrop_path is the canonical main
    # backdrop. Do not replace it with episode stills or a ranked random image.
    try:
        data = await _request_json(
            f"tv/{series_id}/images",
            {"include_image_language": "en,null", "language": "en-US"},
        )
        if data:
            result["images"] = {
                "posters": [image_url(x["file_path"], "w780") for x in (data.get("posters") or []) if x.get("file_path")],
                "backdrops": [image_url(x["file_path"], "w1280") for x in (data.get("backdrops") or []) if x.get("file_path")],
            }
    except Exception:
        logger.exception("TMDB TV image list lookup failed for id=%s", series_id)

    if result.get("poster"):
        result["images"]["posters"] = [result["poster"]] + [x for x in result["images"]["posters"] if x != result["poster"]]
    if result.get("backdrop"):
        result["images"]["backdrops"] = [result["backdrop"]] + [x for x in result["images"]["backdrops"] if x != result["backdrop"]]

    async with _CACHE_LOCK:
        _CACHE[cache_key] = (now, result)
    return result

async def fetch_tmdb_image(url, backdrop=False):
    """Download a TMDB image and return a Telegram-safe JPEG buffer."""
    if not url:
        return None

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
