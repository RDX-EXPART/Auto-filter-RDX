"""Rich look for the search-result message (Telegram Bot API 10.3 buttons inside the message).

How it works
------------
The bot code is NOT rewritten.  A few Kurigram methods are wrapped:

  * Message.reply_text / Message.reply          (first result sent as a new message)
  * Message.reply_photo / edit_caption             (poster / backdrop card -> image + text + buttons in ONE rich message)
  * Message.edit_text / Message.edit_reply_markup  (result produced by editing "Searching...",
                                                    page changes, filter menus, loading state)
  * CallbackQuery.edit_message_text / edit_message_reply_markup

When the keyboard belongs to a search result (it contains the Send All / Quality / Next ...
callbacks) the text + buttons are sent as ONE rich message instead.  Every other message
(start, settings, photo cards, ...) goes through the original method untouched.

Safety
------
* Off switch: RICH_RESULTS=False (env var or info.py).
* Anything unexpected (richgram missing, unsupported button, Telegram rejects the rich
  message, ...) -> the original plain message + inline keyboard is used instead.
* Photo / caption results are never touched.
"""
import html as _html
import logging
import os
import re
from collections import OrderedDict
from contextvars import ContextVar

from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from button_style import _style_for_text

logger = logging.getLogger(__name__)

try:
    from richgram import RICH_AVAILABLE, rich_button, rich_button_row, rich_edit, rich_reply
except Exception as exc:  # richgram not installed
    RICH_AVAILABLE = False
    logger.warning("richgram not available, rich results disabled: %s", exc)

try:
    import info as _info
    _FLAG = getattr(_info, "RICH_RESULTS", None)
except Exception:
    _FLAG = None
if _FLAG is None:
    _FLAG = os.environ.get("RICH_RESULTS", "True")
ENABLED = bool(RICH_AVAILABLE) and str(_FLAG).lower() == "true"

try:
    _IMG_FLAG = getattr(_info, "RICH_IMAGE", None)
except Exception:
    _IMG_FLAG = None
if _IMG_FLAG is None:
    _IMG_FLAG = os.environ.get("RICH_IMAGE", "True")
# poster/backdrop inside the rich message (needs a public image URL)
IMAGE_ENABLED = ENABLED and str(_IMG_FLAG).lower() == "true"

# A keyboard that contains one of these callbacks belongs to a search result.
_RESULT_PREFIXES = (
    "sendfiles#", "next_", "languages#", "years#", "qualities#",
    "seasons#", "episodes#", "combined#", "combinedoff#",
)
_LINE_BREAK = "<br>"
_MAX_CACHE = 3000

_registry = OrderedDict()          # (chat_id, message_id) -> {"html": caption/text html, "img": image url or None}
_inside_rich = ContextVar("rdx_inside_rich", default=False)


# ---------------------------------------------------------------- helpers
def _key(message):
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "id", None)
    if chat_id is None or message_id is None:
        return None
    return (chat_id, message_id)


def _remember(message, html, img=None):
    key = _key(message)
    if key is None:
        return
    if img is None and key in _registry:
        img = _registry[key].get("img")      # keep the poster when only the text changes
    _registry[key] = {"html": html, "img": img}
    _registry.move_to_end(key)
    while len(_registry) > _MAX_CACHE:
        _registry.popitem(last=False)


def _callbacks(markup):
    for row in getattr(markup, "inline_keyboard", None) or []:
        for button in row:
            data = getattr(button, "callback_data", None)
            if isinstance(data, bytes):
                data = data.decode("utf-8", "ignore")
            if data:
                yield str(data)


def _is_result_markup(markup):
    return isinstance(markup, InlineKeyboardMarkup) and any(
        data.startswith(_RESULT_PREFIXES) for data in _callbacks(markup)
    )


def _plain_parse_mode(kwargs):
    mode = kwargs.get("parse_mode")
    return mode is None or mode == ParseMode.HTML


# Score line written by build_tmdb_card:  🍅 <b>95%</b> • IMDb <b>7.9/10</b> • TMDB <b>7.7/10</b>
_SCORE_PART = r"(?:🍅 <b>[^<]+</b>|IMDb <b>[^<]+</b>|TMDB <b>[^<]+</b>)"
_SCORE_LINE_RE = re.compile(rf"^{_SCORE_PART}(?: • {_SCORE_PART})*$", re.M)


def _score_pills(line):
    """'🍅 <b>95%</b> • IMDb <b>7.9/10</b> • TMDB <b>7.7/10</b>' -> row of coloured, non-clickable pills."""
    buttons = []
    for part in line.split(" • "):
        value = _html.unescape(re.sub(r"<[^>]+>", "", part)).strip()
        if part.startswith("🍅"):
            buttons.append(rich_button(value, callback_data="pages", style="danger"))
        elif part.startswith("IMDb"):
            buttons.append(rich_button("⭐ " + value.replace("/10", ""), callback_data="pages", style="primary"))
        elif part.startswith("TMDB"):
            buttons.append(rich_button(value.replace("/10", ""), callback_data="pages", style="success"))
    return rich_button_row(*buttons) if buttons else None


def _text_to_rich(text):
    text = str(text or "").replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)          # never more than one blank line
    if ENABLED:
        match = _SCORE_LINE_RE.search(text)
        if match:
            try:
                pills = _score_pills(match.group(0))
            except Exception:
                logger.exception("rating pills failed, keeping the text line")
                pills = None
            if pills:
                before = text[:match.start()].rstrip("\n")
                after = text[match.end():].lstrip("\n")
                return (before.replace("\n", _LINE_BREAK) + pills
                        + after.replace("\n", _LINE_BREAK))
    return text.replace("\n", _LINE_BREAK)


def _img_block(url):
    return f'<img src="{_html.escape(url, quote=True)}"/>' if url else ""


def _compose(key, html, buttons):
    entry = _registry.get(key) or {}
    return _img_block(entry.get("img")) + _text_to_rich(html) + buttons


def _photo_url(photo):
    """Public https URL of a poster/backdrop, or None (uploads/bytes cannot go into a rich message)."""
    url = photo if isinstance(photo, str) else getattr(photo, "source_url", None)
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return re.sub(r"/t/p/original/", "/t/p/w1280/", url)
    return None


class _FakePhoto:
    """Truthy stand-in so the card code keeps treating the rich message as a poster card."""
    file_id = "rich-image"
    file_unique_id = "rich-image"


class _Caption(str):
    """str + .html, like pyrogram's caption objects."""
    @property
    def html(self):
        return str(self)


def impersonate_photo(message):
    """Called before every callback: make a rich+image message look like a photo card to the bot code."""
    key = _key(message)
    entry = _registry.get(key) if key else None
    if entry and entry.get("img"):
        message.photo = _FakePhoto()
        message.caption = _Caption(entry.get("html") or "")


_KIND_BY_PREFIX = (
    ("sendfiles#", "send"), ("seasons#", "season"), ("episodes#", "episode"),
    ("qualities#", "quality"), ("years#", "year"), ("languages#", "language"),
    ("combined#", "combined"), ("combinedoff#", "combined"),
)


def _kind(button):
    data = getattr(button, "callback_data", None)
    if isinstance(data, bytes):
        data = data.decode("utf-8", "ignore")
    data = str(data or "")
    for prefix, kind in _KIND_BY_PREFIX:
        if data.startswith(prefix):
            return kind
    return None


def _relayout(rows):
    """Series results: Send All on top, then a tidy 2-column grid
         Season  | Episode
         Quality | Year
         Language| Combined
    Movie results keep their rows (only Send All becomes full width)."""
    flat = [(button, _kind(button)) for row in rows for button in row]
    by_kind = {}
    for button, kind in flat:
        if kind and kind not in by_kind:
            by_kind[kind] = button
    if "season" not in by_kind and "episode" not in by_kind:
        return rows
    used = set()
    new_rows = []
    if "send" in by_kind:
        new_rows.append([by_kind["send"]])
        used.add("send")
    grid = [by_kind[k] for k in ("season", "episode", "quality", "year", "language", "combined") if k in by_kind]
    used.update(k for k in ("season", "episode", "quality", "year", "language", "combined") if k in by_kind)
    for i in range(0, len(grid), 2):
        new_rows.append(grid[i:i + 2])
    for row in rows:                       # everything else (file buttons, pages, back) keeps its order
        rest = [b for b in row if _kind(b) is None or b is not by_kind.get(_kind(b))]
        if rest:
            new_rows.append(rest)
    return new_rows


def markup_to_rich(markup):
    """InlineKeyboardMarkup -> rich button rows (None if a button type is unsupported)."""
    rows = [list(row) for row in (getattr(markup, "inline_keyboard", None) or [])]
    rows = _relayout(rows)
    html = ""
    for row in rows:
        buttons = []
        for button in row:
            unsupported = (
                getattr(button, "web_app", None), getattr(button, "login_url", None),
                getattr(button, "switch_inline_query", None),
                getattr(button, "switch_inline_query_current_chat", None),
                getattr(button, "copy_text", None),
            )
            if any(unsupported):
                return None
            style = _style_for_text(button.text)
            url = getattr(button, "url", None)
            data = getattr(button, "callback_data", None)
            if isinstance(data, bytes):
                data = data.decode("utf-8", "ignore")
            if url:
                buttons.append(rich_button(button.text, url=url, style=style))
            elif data:
                buttons.append(rich_button(button.text, callback_data=str(data), style=style))
            else:
                return None
        if not buttons:
            continue
        if len(buttons) == 1 and _kind(row[0]) == "send":
            html += rich_button_row(*buttons)                      # Send All: full width
        elif len(buttons) == 1:
            html += rich_button_row(*buttons, align="center")      # other lone buttons: small centered pill
        else:
            html += rich_button_row(*buttons)                      # several buttons share the row
    return html


async def _run_rich(coro_factory):
    token = _inside_rich.set(True)
    try:
        return await coro_factory()
    finally:
        _inside_rich.reset(token)


# ---------------------------------------------------------------- wrappers
def _degraded(sent):
    """True when richgram had to fall back to a plain text message (Telegram rejected the rich one)."""
    return (hasattr(type(sent), "rich_message") and getattr(sent, "rich_message", None) is None
            and bool(getattr(sent, "text", None)))


def _patch():
    orig_reply = Message.reply_text
    orig_reply_photo = Message.reply_photo
    orig_edit_text = Message.edit_text
    orig_edit_caption = Message.edit_caption
    orig_edit_markup = Message.edit_reply_markup
    orig_cb_edit_text = CallbackQuery.edit_message_text
    orig_cb_edit_markup = CallbackQuery.edit_message_reply_markup

    async def reply_text(self, text, *args, **kwargs):
        markup = kwargs.get("reply_markup")
        if (ENABLED and not _inside_rich.get() and _is_result_markup(markup)
                and _plain_parse_mode(kwargs) and "reply_parameters" not in kwargs):
            try:
                buttons = markup_to_rich(markup)
                if buttons is not None:
                    sent = await _run_rich(lambda: rich_reply(self, _text_to_rich(text) + buttons))
                    if sent:
                        _remember(sent, str(text))
                        return sent
            except Exception:
                logger.exception("rich reply failed, using the normal message")
        return await orig_reply(self, text, *args, **kwargs)

    async def reply_photo(self, photo, *args, **kwargs):
        """Poster/backdrop card: send image + caption + buttons as ONE rich message when possible."""
        markup = kwargs.get("reply_markup")
        caption = kwargs.get("caption")
        url = _photo_url(photo) if IMAGE_ENABLED else None
        if (url and caption and not _inside_rich.get() and _is_result_markup(markup)
                and _plain_parse_mode(kwargs) and "reply_parameters" not in kwargs):
            try:
                buttons = markup_to_rich(markup)
                if buttons is not None:
                    sent = await _run_rich(
                        lambda: rich_reply(self, _img_block(url) + _text_to_rich(caption) + buttons))
                    if sent and _degraded(sent):
                        logger.warning("Telegram rejected the rich image message; using the normal photo card")
                        try:
                            await sent.delete()
                        except Exception:
                            pass
                    elif sent:
                        _remember(sent, str(caption), img=url)
                        return sent
            except Exception:
                logger.exception("rich image reply failed, using the normal photo card")
        return await orig_reply_photo(self, photo, *args, **kwargs)

    async def _rich_update(self, html, markup):
        """Edit a registered rich message (keeps its poster).  Returns the result or None to fall back."""
        key = _key(self)
        buttons = markup_to_rich(markup) if markup is not None else ""
        if buttons is None:
            return None
        result = await _run_rich(lambda: rich_edit(self, _compose(key, html, buttons)))
        _remember(self, html)
        return result if getattr(result, "id", None) else self

    async def edit_text(self, text, *args, **kwargs):
        if ENABLED and not _inside_rich.get() and "rich_message" not in kwargs and _plain_parse_mode(kwargs):
            markup = kwargs.get("reply_markup")
            key = _key(self)
            if key in _registry or _is_result_markup(markup):
                try:
                    done = await _rich_update(self, str(text), markup)
                    if done is not None:
                        return done
                except Exception as exc:
                    if "MESSAGE_NOT_MODIFIED" in str(exc).upper():
                        return self
                    logger.exception("rich edit failed, using the normal edit")
        return await orig_edit_text(self, text, *args, **kwargs)

    async def edit_caption(self, caption, *args, **kwargs):
        # a rich+image message is edited through the "photo card" code path of the bot
        key = _key(self)
        if (ENABLED and not _inside_rich.get() and key in _registry
                and _registry[key].get("img") and _plain_parse_mode(kwargs)):
            try:
                done = await _rich_update(self, str(caption), kwargs.get("reply_markup"))
                if done is not None:
                    return done
            except Exception as exc:
                if "MESSAGE_NOT_MODIFIED" in str(exc).upper():
                    return self
                logger.exception("rich caption edit failed, using the normal edit")
        return await orig_edit_caption(self, caption, *args, **kwargs)

    async def edit_reply_markup(self, reply_markup=None, *args, **kwargs):
        if ENABLED and not _inside_rich.get():
            key = _key(self)
            entry = _registry.get(key) if key else None
            if entry is not None:
                try:
                    done = await _rich_update(self, entry["html"], reply_markup)
                    if done is not None:
                        return done
                except Exception as exc:
                    if "MESSAGE_NOT_MODIFIED" in str(exc).upper():
                        return self
                    logger.exception("rich markup edit failed, using the normal edit")
        return await orig_edit_markup(self, reply_markup, *args, **kwargs)

    async def cb_edit_text(self, text, *args, **kwargs):
        message = getattr(self, "message", None)
        if (ENABLED and message is not None and not _inside_rich.get()
                and (_key(message) in _registry or _is_result_markup(kwargs.get("reply_markup")))):
            return await message.edit_text(text, *args, **kwargs)
        return await orig_cb_edit_text(self, text, *args, **kwargs)

    async def cb_edit_markup(self, reply_markup=None, *args, **kwargs):
        message = getattr(self, "message", None)
        if ENABLED and message is not None and not _inside_rich.get() and _key(message) in _registry:
            return await message.edit_reply_markup(reply_markup)
        return await orig_cb_edit_markup(self, reply_markup, *args, **kwargs)

    Message.reply_text = reply_text
    Message.reply = reply_text
    Message.reply_photo = reply_photo
    Message.edit_text = edit_text
    Message.edit = edit_text
    Message.edit_caption = edit_caption
    Message.edit_reply_markup = edit_reply_markup
    CallbackQuery.edit_message_text = cb_edit_text
    CallbackQuery.edit_message_reply_markup = cb_edit_markup


if ENABLED:
    _patch()
    logger.info("Rich search results are ON (RICH_RESULTS=True, RICH_IMAGE=%s)", IMAGE_ENABLED)
else:
    logger.info("Rich search results are OFF (RICH_RESULTS=False or richgram missing)")
