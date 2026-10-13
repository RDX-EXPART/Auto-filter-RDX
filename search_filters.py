"""Alias-aware filename search helpers used by the inline filter buttons."""

import re


_MARKER = re.compile(
    r"\[\[(language|season|episode|quality|year|combined):([^\]]+)\]\]",
    re.IGNORECASE,
)
_SEP = r"[\W_]*"

LANGUAGES = {
    "hin": r"(?<![a-z0-9])(?:hin(?:di)?)(?![a-z0-9])",
    "eng": r"(?<![a-z0-9])(?:eng(?:lish)?)(?![a-z0-9])",
    "tam": r"(?<![a-z0-9])(?:tam(?:il)?)(?![a-z0-9])",
    "tel": r"(?<![a-z0-9])(?:tel(?:ugu)?)(?![a-z0-9])",
    "mal": r"(?<![a-z0-9])(?:mal(?:ayalam)?)(?![a-z0-9])",
    "kan": r"(?<![a-z0-9])(?:kan(?:nada)?)(?![a-z0-9])",
    "bangla": r"(?<![a-z0-9])(?:bangla|bengali|bangali|bengoli|ben)(?![a-z0-9])",
    "urdu": r"(?<![a-z0-9])(?:urd(?:u)?)(?![a-z0-9])",
    "mar": r"(?<![a-z0-9])(?:mar(?:athi)?)(?![a-z0-9])",
    "pun": r"(?<![a-z0-9])(?:pun(?:jabi)?)(?![a-z0-9])",
    "guj": r"(?<![a-z0-9])(?:guj(?:arati|rati)?)(?![a-z0-9])",
    "bhojpuri": r"(?<![a-z0-9])bhoj(?:puri)?(?![a-z0-9])",
    "oriya": r"(?<![a-z0-9])(?:odia|oriya)(?![a-z0-9])",
    "asm": r"(?<![a-z0-9])(?:asm(?:assamese)?|assamese)(?![a-z0-9])",
    "kor": r"(?<![a-z0-9])(?:kor(?:ean)?)(?![a-z0-9])",
    "chi": r"(?<![a-z0-9])(?:chi(?:nese)?)(?![a-z0-9])",
    "jap": r"(?<![a-z0-9])(?:jap(?:anese)?|jpn)(?![a-z0-9])",
    "ara": r"(?<![a-z0-9])(?:ara(?:bic)?)(?![a-z0-9])",
    "spa": r"(?<![a-z0-9])(?:spa(?:nish)?)(?![a-z0-9])",
    "fre": r"(?<![a-z0-9])(?:fre(?:nch)?|fra)(?![a-z0-9])",
    "ger": r"(?<![a-z0-9])(?:ger(?:man)?|deu)(?![a-z0-9])",
    "por": r"(?<![a-z0-9])(?:por(?:tuguese)?)(?![a-z0-9])",
    "rus": r"(?<![a-z0-9])(?:rus(?:sian)?)(?![a-z0-9])",
    "dual": rf"(?<![a-z0-9])dual(?:{_SEP}audio)?(?![a-z0-9])",
    "multi": rf"(?<![a-z0-9])multi(?:ple)?(?:{_SEP}audio)?(?![a-z0-9])",
}

_LANGUAGE_ALIASES = {
    "hindi": "hin", "hin": "hin",
    "english": "eng", "eng": "eng",
    "tamil": "tam", "tam": "tam",
    "telugu": "tel", "tel": "tel",
    "malayalam": "mal", "mal": "mal",
    "kannada": "kan", "kan": "kan",
    "bengali": "bangla", "bengoli": "bangla", "bangali": "bangla",
    "bangla": "bangla", "ben": "bangla",
    "urdu": "urdu", "urd": "urdu",
    "marathi": "mar", "mar": "mar",
    "punjabi": "pun", "pun": "pun",
    "gujarati": "guj", "guj": "guj", "gujrati": "guj",
    "bhojpuri": "bhojpuri", "odia": "oriya", "oriya": "oriya",
    "assamese": "asm", "asm": "asm",
    "korean": "kor", "kor": "kor",
    "chinese": "chi", "chi": "chi",
    "japanese": "jap", "jap": "jap", "jpn": "jap",
    "arabic": "ara", "ara": "ara",
    "spanish": "spa", "spa": "spa",
    "french": "fre", "fre": "fre", "fra": "fre",
    "german": "ger", "ger": "ger", "deu": "ger",
    "portuguese": "por", "por": "por",
    "russian": "rus", "rus": "rus",
    "dual audio": "dual", "dual": "dual",
    "multi audio": "multi", "multi": "multi",
}

_QUALITY = {
    "360p": r"(?<!\d)360[\W_]*p(?![a-z0-9])",
    "480p": r"(?<!\d)480[\W_]*p(?![a-z0-9])",
    "720p": r"(?<!\d)720[\W_]*p(?![a-z0-9])",
    "1080p": r"(?<!\d)1080[\W_]*p(?![a-z0-9])",
    "1440p": r"(?<!\d)(?:1440[\W_]*p|2[\W_]*k)(?![a-z0-9])",
    "2160p": r"(?<!\d)(?:2160[\W_]*p|4[\W_]*k|uhd)(?![a-z0-9])",
}

_COMBINED_LABEL = r"(?<![a-z0-9])(?:combined|complete|pack)(?![a-z0-9])"
_EP_TOKEN = r"(?:episode|ep|e)"
_COMBINED_RANGE = (
    rf"(?<![a-z0-9])(?:(?:s|season){_SEP}0*\d{{1,3}}{_SEP})?"
    rf"{_EP_TOKEN}{_SEP}0*\d{{1,3}}"
    rf"\s*(?:-|–|—|to|through|thru|&|/|_)\s*"
    rf"(?:{_EP_TOKEN}{_SEP})?0*\d{{1,3}}(?!\d)"
)
COMBINED_PATTERN = rf"(?:{_COMBINED_LABEL}|{_COMBINED_RANGE})"

_LABELS = {
    "hin": "Hindi", "eng": "English", "tam": "Tamil", "tel": "Telugu",
    "mal": "Malayalam", "kan": "Kannada", "bangla": "Bengali",
    "urdu": "Urdu", "mar": "Marathi", "pun": "Punjabi",
    "guj": "Gujarati", "bhojpuri": "Bhojpuri", "oriya": "Odia",
    "asm": "Assamese", "kor": "Korean", "chi": "Chinese",
    "jap": "Japanese", "ara": "Arabic", "spa": "Spanish",
    "fre": "French", "ger": "German", "por": "Portuguese",
    "rus": "Russian", "dual": "Dual Audio", "multi": "Multi Audio",
}


def _canonical_language(value):
    value = str(value or "").strip().lower()
    return _LANGUAGE_ALIASES.get(value, value)


def _number(value):
    match = re.search(r"\d{1,4}", str(value or ""))
    return int(match.group()) if match else None


def _canonical_quality(value):
    value = re.sub(r"[\W_]+", "", str(value or "").strip().lower())
    aliases = {
        "360": "360p", "480": "480p", "720": "720p",
        "1080": "1080p", "1440": "1440p", "2k": "1440p",
        "2160": "2160p", "4k": "2160p", "uhd": "2160p",
    }
    return aliases.get(value, value)


def parse_filter_query(query):
    """Split a user-visible title query from its internal filter state."""
    filters = {}

    def collect(match):
        filters[match.group(1).lower()] = match.group(2).strip()
        return " "

    base = _MARKER.sub(collect, str(query or ""))
    return re.sub(r"\s+", " ", base).strip(), filters


def _strip_episode(text):
    text = re.sub(
        rf"(?i)((?:s|season){_SEP}0*\d{{1,3}}){_SEP}"
        rf"{_EP_TOKEN}{_SEP}0*\d{{1,4}}",
        r"\1",
        text,
    )
    return re.sub(
        rf"(?i)(?<![a-z0-9]){_EP_TOKEN}{_SEP}0*\d{{1,4}}(?!\d)",
        " ",
        text,
    )


def _strip_season(text):
    return re.sub(
        rf"(?i)(?<![a-z0-9])(?:s|season){_SEP}0*\d{{1,3}}"
        rf"(?:{_SEP}{_EP_TOKEN}{_SEP}0*\d{{1,4}})?",
        " ",
        text,
    )


def _strip_language(text):
    for pattern in set(LANGUAGES.values()):
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _strip_quality(text):
    for pattern in _QUALITY.values():
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _strip_year(text):
    return re.sub(r"(?<!\d)(?:19|20)\d{2}(?!\d)", " ", text)


def make_filter_query(query, **updates):
    """Add/replace filter markers while retaining the title and other filters."""
    base, filters = parse_filter_query(query)
    stripters = {
        "language": _strip_language,
        "season": _strip_season,
        "episode": _strip_episode,
        "quality": _strip_quality,
        "year": _strip_year,
        "combined": lambda value: re.sub(_COMBINED_LABEL, " ", value, flags=re.I),
    }
    for kind, value in updates.items():
        if kind not in {"language", "season", "episode", "quality", "year", "combined"}:
            continue
        if value is not None:
            base = stripters[kind](base)
        if value is None:
            filters.pop(kind, None)
        elif kind == "language":
            filters[kind] = _canonical_language(value)
        elif kind == "quality":
            filters[kind] = _canonical_quality(value)
        elif kind == "combined":
            filters[kind] = "1" if str(value).strip().lower() not in {"", "0", "false", "off", "no"} else ""
            if not filters[kind]:
                filters.pop(kind, None)
        else:
            number = _number(value)
            if number is not None:
                filters[kind] = str(number)

    base = re.sub(r"\s+", " ", base).strip()
    markers = " ".join(
        f"[[{kind}:{filters[kind]}]]"
        for kind in ("language", "season", "episode", "quality", "year", "combined")
        if filters.get(kind)
    )
    return f"{base} {markers}".strip()


def _base_pattern(text):
    text = re.sub(r"[_\-.+:/\\()\[\]{}]+", " ", str(text or ""))
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    return r".*?".join(re.escape(token) for token in tokens) if tokens else None


def _season_pattern(number):
    number = _number(number)
    return (
        rf"(?<![a-z0-9])(?:s|season){_SEP}0*{number}(?!\d)"
        if number is not None else None
    )


def _episode_pattern(number):
    number = _number(number)
    if number is None:
        return None
    return (
        rf"(?<![a-z0-9])(?:(?:s|season){_SEP}0*\d{{1,3}}{_SEP})?"
        rf"{_EP_TOKEN}{_SEP}0*{number}(?!\d)"
    )


def _year_pattern(number):
    number = _number(number)
    return rf"(?<!\d){number}(?!\d)" if number is not None else None


def _find_number(pattern, text):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_episode_numbers(text):
    """Extract episodes, including every episode covered by a combined range."""
    text = str(text or "")
    numbers = set()
    range_pattern = re.compile(
        rf"(?i)(?<![a-z0-9])(?:(?:s|season){_SEP}0*\d{{1,3}}{_SEP})?"
        rf"{_EP_TOKEN}{_SEP}0*(\d{{1,4}})"
        rf"\s*(?:-|–|—|to|through|thru|&|/)\s*"
        rf"(?:{_EP_TOKEN}{_SEP})?0*(\d{{1,4}})(?!\d)"
    )
    for match in range_pattern.finditer(text):
        start, end = int(match.group(1)), int(match.group(2))
        if 0 < start <= end <= 999 and end - start <= 200:
            numbers.update(range(start, end + 1))
    for match in re.finditer(
        rf"(?i)(?<![a-z0-9])(?:(?:s|season){_SEP}0*\d{{1,3}}{_SEP})?"
        rf"{_EP_TOKEN}{_SEP}0*(\d{{1,4}})(?!\d)",
        text,
    ):
        number = int(match.group(1))
        if number > 0:
            numbers.add(number)
    return numbers


def build_search_pattern(query):
    """Build a Mongo-compatible regex for titles and optional filter markers."""
    base, filters = parse_filter_query(query)
    if filters.get("language"):
        base = _strip_language(base)
    if filters.get("quality"):
        base = _strip_quality(base)
    if filters.get("year"):
        base = _strip_year(base)
    if filters.get("combined"):
        base = re.sub(_COMBINED_LABEL, " ", base, flags=re.I)

    direct_season = _find_number(
        r"(?<![a-z0-9])(?:s|season)[\W_]*0*(\d{1,3})", base
    )
    direct_episode = _find_number(
        rf"(?<![a-z0-9]){_EP_TOKEN}{_SEP}0*(\d{{1,4}})(?!\d)", base
    )
    season = _number(filters.get("season")) or direct_season
    episode = _number(filters.get("episode")) or direct_episode
    if season is not None:
        base = _strip_season(base)
    elif episode is not None:
        base = _strip_episode(base)

    constraints = []
    title_pattern = _base_pattern(base)
    if title_pattern:
        constraints.append(title_pattern)
    language = _canonical_language(filters.get("language"))
    if language:
        constraints.append(LANGUAGES.get(language, re.escape(language)))
    quality = _canonical_quality(filters.get("quality"))
    if quality:
        constraints.append(_QUALITY.get(quality, re.escape(quality)))
    if filters.get("combined"):
        constraints.append(COMBINED_PATTERN)
    if filters.get("year"):
        constraints.append(_year_pattern(filters.get("year")))
    if season is not None:
        constraints.append(_season_pattern(season))
    if episode is not None:
        constraints.append(_episode_pattern(episode))

    constraints = [item for item in constraints if item]
    return "^" + "".join(f"(?=.*{item})" for item in constraints) + ".*$" if constraints else "."


def matches_filter(text, query):
    """Apply episode-number semantics to combined-file ranges."""
    _, filters = parse_filter_query(query)
    episode = _number(filters.get("episode"))
    if episode is not None and episode not in extract_episode_numbers(text):
        return False
    candidate_query = make_filter_query(query, episode=None) if episode is not None else query
    return bool(re.search(build_search_pattern(candidate_query), str(text or ""), re.I))


def display_filter_query(query):
    """Return a readable title/filter label without internal markers."""
    base, filters = parse_filter_query(query)
    if filters.get("language"):
        base = _strip_language(base)
    if filters.get("season"):
        base = _strip_season(base)
    if filters.get("episode"):
        base = _strip_episode(base)
    if filters.get("quality"):
        base = _strip_quality(base)
    if filters.get("year"):
        base = _strip_year(base)
    if filters.get("combined"):
        base = re.sub(_COMBINED_LABEL, " ", base, flags=re.I)
    base = re.sub(r"\s+", " ", base).strip()
    labels = []
    language = _canonical_language(filters.get("language"))
    if language:
        labels.append(_LABELS.get(language, language.title()))
    season = _number(filters.get("season"))
    episode = _number(filters.get("episode"))
    if season is not None:
        labels.append(f"Season {season:02d}")
    if episode is not None:
        labels.append(f"Episode {episode:02d}")
    quality = _canonical_quality(filters.get("quality"))
    if quality:
        labels.append(quality)
    if filters.get("year"):
        labels.append(str(filters["year"]))
    if filters.get("combined"):
        labels.append("Combined")
    suffix = " • ".join(labels)
    return f"{base} — {suffix}" if base and suffix else (base or suffix)


def clean_display_filename(filename):
    """Hide the legacy branding prefix without changing the stored filename."""
    return re.sub(
        r"(?i)^\s*RDX[\s_-]+AUTO[\s_-]+FILTER\s*",
        "",
        str(filename or ""),
    ).strip()
