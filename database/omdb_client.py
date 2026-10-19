# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

"""IMDb and Rotten Tomatoes scores from OMDb.

Uses OMDB_API_KEY from info.py (a Heroku Config Var). If the key is empty or OMDb is
unavailable, every lookup returns {} and the card simply shows the TMDB rating.
The key is never logged, and neither is the request URL, because it contains the key.
"""

import logging
import time

import aiohttp

from info import OMDB_API_KEY

logger = logging.getLogger(__name__)

OMDB_URL = "https://www.omdbapi.com/"
_CACHE_TTL = 6 * 3600        # successful lookups: 6 hours
_MISS_TTL = 30 * 60          # not found / failed: 30 minutes, avoids hammering the daily limit
_cache = {}


def parse_omdb_ratings(data):
    """Pull the IMDb score and the Rotten Tomatoes percentage out of an OMDb response."""
    if not isinstance(data, dict) or data.get("Response") != "True":
        return {}
    ratings = {}
    imdb = str(data.get("imdbRating") or "").strip()
    if imdb and imdb != "N/A":
        ratings["imdb"] = imdb
    for item in data.get("Ratings") or []:
        if item.get("Source") == "Rotten Tomatoes":
            value = str(item.get("Value") or "").strip()
            if value and value != "N/A":
                ratings["rt"] = value
    return ratings


async def get_omdb_ratings(imdb_id=None, title=None, year=None):
    """Return {"imdb": "6.4", "rt": "80%"} with any value that is available, else {}."""
    if not OMDB_API_KEY:
        return {}
    if imdb_id:
        params = {"i": imdb_id}
        cache_key = f"id:{imdb_id}"
    elif title:
        params = {"t": title}
        if year and str(year) != "N/A":
            params["y"] = str(year)
        cache_key = f"t:{title.casefold()}|{params.get('y', '')}"
    else:
        return {}

    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return dict(cached[1])

    params["apikey"] = OMDB_API_KEY
    ratings = {}
    ttl = _MISS_TTL
    try:
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(OMDB_URL, params=params) as response:
                data = await response.json(content_type=None)
        ratings = parse_omdb_ratings(data)
        if ratings:
            ttl = _CACHE_TTL
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        # Log only the exception type: its message can contain the request URL.
        logger.info("OMDb lookup skipped: %s", type(exc).__name__)

    _cache[cache_key] = (time.time() + ttl, dict(ratings))
    return ratings
