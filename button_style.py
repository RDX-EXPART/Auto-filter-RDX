"""Button colors (primary blue / success green / danger red) chosen from the button label.

Works on both libraries:
  * Kurigram >= 2.2.26 : InlineKeyboardButton has a native ``style`` argument, so we only
    fill it in automatically when the code did not pass one.
  * Pyrofork 2.3.45    : no ``style`` argument, so the old raw-API patch in
    ``button_style_legacy.py`` is used (unchanged behaviour).
"""

import inspect
import unicodedata
from functools import wraps

_SMALL_CAP_TRANSLATION = str.maketrans({
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e",
    "ꜰ": "f", "ɢ": "g", "ʜ": "h", "ɪ": "i", "ᴊ": "j",
    "ᴋ": "k", "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o",
    "ᴘ": "p", "ǫ": "q", "ʀ": "r", "ꜱ": "s", "ᴛ": "t",
    "ᴜ": "u", "ᴠ": "v", "ᴡ": "w", "ʏ": "y", "ᴢ": "z",
})


def _style_for_text(text):
    """Map common button labels to danger / success / primary."""
    label = unicodedata.normalize("NFKC", str(text or "")).casefold()
    label = label.translate(_SMALL_CAP_TRANSLATION)
    label = " ".join(label.split())
    # Danger/red: destructive controls and the Combined Files toggle (Quality/Season/Episode stay blue).
    if any(word in label for word in ("close", "cancel", "delete", "abort", "remove", "combined", "all files", "❌", "🗑", "🔴")):
        return "danger"
    # Success/green: positive actions.
    if any(word in label for word in ("send all", "confirm", "success", "download", "back", "prev", "previous", "✅", "🟢")):
        return "success"
    return "primary"


def enable_primary_buttons():
    """Enable per-label button colors once at startup."""
    from pyrogram.types import InlineKeyboardButton

    if getattr(InlineKeyboardButton, "_rdx_primary_buttons", False):
        return

    original_init = InlineKeyboardButton.__init__
    if "style" in inspect.signature(original_init).parameters:
        from pyrogram.enums import ButtonStyle

        styles = {
            "danger": getattr(ButtonStyle, "DANGER", None),
            "success": getattr(ButtonStyle, "SUCCESS", None),
            "primary": getattr(ButtonStyle, "PRIMARY", None),
        }

        @wraps(original_init)
        def init(self, *args, **kwargs):
            if kwargs.get("style") is None:
                text = args[0] if args else kwargs.get("text")
                style = styles.get(_style_for_text(text))
                if style is not None:
                    kwargs["style"] = style
            original_init(self, *args, **kwargs)

        InlineKeyboardButton.__init__ = init
        InlineKeyboardButton._rdx_primary_buttons = True
    else:
        from button_style_legacy import enable_primary_buttons as enable_legacy_buttons

        enable_legacy_buttons()  # sets the _rdx_primary_buttons flag itself
