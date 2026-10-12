"""Repository-wide Telegram primary button styling for Pyrofork.

Telegram added colored inline buttons in API layer 223.  Pyrofork 2.3.45
predates the high-level ``style`` argument, so this module supplies the three
styled MTProto constructors used by this project and patches the shared
``InlineKeyboardButton.write`` method once at startup.
"""

from io import BytesIO

from pyrogram import raw
from pyrogram.raw.all import objects
from pyrogram.raw.core import Bytes, Int, String, TLObject, Vector
from pyrogram.types import InlineKeyboardButton


_STYLE_FLAG = 1 << 10
_ORIGINAL_WRITE = InlineKeyboardButton.write


class _PrimaryButtonStyle(TLObject):
    """keyboardButtonStyle with Telegram's primary (blue) background."""

    ID = 0x4FDD3430
    QUALNAME = "types.KeyboardButtonStyle"
    __slots__ = ["bg_primary", "bg_danger", "bg_success", "icon"]

    def __init__(
        self,
        *,
        bg_primary=True,
        bg_danger=False,
        bg_success=False,
        icon=None,
    ):
        self.bg_primary = bg_primary
        self.bg_danger = bg_danger
        self.bg_success = bg_success
        self.icon = icon

    @staticmethod
    def read(data, *args):
        flags = Int.read(data)
        return _PrimaryButtonStyle(
            bg_primary=bool(flags & (1 << 0)),
            bg_danger=bool(flags & (1 << 1)),
            bg_success=bool(flags & (1 << 2)),
            icon=None if not flags & (1 << 3) else int.from_bytes(
                data.read(8),
                "little",
                signed=True,
            ),
        )

    def write(self, *args):
        data = BytesIO()
        data.write(Int(self.ID, False))
        flags = 0
        flags |= 1 << 0 if self.bg_primary else 0
        flags |= 1 << 1 if self.bg_danger else 0
        flags |= 1 << 2 if self.bg_success else 0
        flags |= 1 << 3 if self.icon is not None else 0
        data.write(Int(flags))
        if self.icon is not None:
            data.write(int(self.icon).to_bytes(8, "little", signed=True))
        return data.getvalue()


def _style_for_text(text):
    """Map common button labels to Telegram's supported danger/success/primary styles."""
    label = (text or "").casefold()
    # Danger/red actions: destructive or restrictive filter controls.
    if any(word in label for word in ("close", "cancel", "delete", "abort", "remove", "quality", "seasons", "no more pages", "❌", "🗑", "🔴")):
        return "danger"
    # Success/green actions: positive actions and selected filter controls.
    if any(word in label for word in ("send all", "confirm", "success", "episodes", "years", "download", "back", "prev", "previous", "languages", "✅", "🟢")):
        return "success"
    # Next, continue, verify, help, menus and other actions use primary blue.
    return "primary"


def _button_style(text):
    kind = _style_for_text(text)
    return _PrimaryButtonStyle(
        bg_primary=(kind == "primary"),
        bg_danger=(kind == "danger"),
        bg_success=(kind == "success"),
    )


class _PrimaryCallbackButton(raw.types.KeyboardButtonCallback):
    ID = 0xE62BC960

    @staticmethod
    def read(data, *args):
        flags = Int.read(data)
        if flags & _STYLE_FLAG:
            TLObject.read(data)
        text = String.read(data)
        payload = Bytes.read(data)
        return _PrimaryCallbackButton(
            text=text,
            data=payload,
            requires_password=bool(flags & (1 << 0)),
        )

    def write(self, *args):
        data = BytesIO()
        data.write(Int(self.ID, False))
        flags = _STYLE_FLAG
        flags |= 1 << 0 if self.requires_password else 0
        data.write(Int(flags))
        data.write(_button_style(self.text).write())
        data.write(String(self.text))
        data.write(Bytes(self.data))
        return data.getvalue()


class _PrimaryUrlButton(raw.types.KeyboardButtonUrl):
    ID = 0xD80C25EC

    @staticmethod
    def read(data, *args):
        flags = Int.read(data)
        if flags & _STYLE_FLAG:
            TLObject.read(data)
        return _PrimaryUrlButton(
            text=String.read(data),
            url=String.read(data),
        )

    def write(self, *args):
        data = BytesIO()
        data.write(Int(self.ID, False))
        data.write(Int(_STYLE_FLAG))
        data.write(_button_style(self.text).write())
        data.write(String(self.text))
        data.write(String(self.url))
        return data.getvalue()


class _PrimarySwitchInlineButton(raw.types.KeyboardButtonSwitchInline):
    ID = 0x991399FC

    @staticmethod
    def read(data, *args):
        flags = Int.read(data)
        if flags & _STYLE_FLAG:
            TLObject.read(data)
        text = String.read(data)
        query = String.read(data)
        peer_types = TLObject.read(data) if flags & (1 << 1) else []
        return _PrimarySwitchInlineButton(
            text=text,
            query=query,
            same_peer=bool(flags & (1 << 0)),
            peer_types=peer_types,
        )

    def write(self, *args):
        data = BytesIO()
        data.write(Int(self.ID, False))
        flags = _STYLE_FLAG
        flags |= 1 << 0 if self.same_peer else 0
        flags |= 1 << 1 if self.peer_types else 0
        data.write(Int(flags))
        data.write(_button_style(self.text).write())
        data.write(String(self.text))
        data.write(String(self.query))
        if self.peer_types:
            data.write(Vector(self.peer_types))
        return data.getvalue()


async def _write_primary_button(button, client):
    raw_button = await _ORIGINAL_WRITE(button, client)
    if isinstance(raw_button, raw.types.KeyboardButtonCallback):
        return _PrimaryCallbackButton(
            text=raw_button.text,
            data=raw_button.data,
            requires_password=raw_button.requires_password,
        )
    if isinstance(raw_button, raw.types.KeyboardButtonUrl):
        return _PrimaryUrlButton(
            text=raw_button.text,
            url=raw_button.url,
        )
    if isinstance(raw_button, raw.types.KeyboardButtonSwitchInline):
        return _PrimarySwitchInlineButton(
            text=raw_button.text,
            query=raw_button.query,
            same_peer=raw_button.same_peer,
            peer_types=raw_button.peer_types,
        )
    return raw_button


def enable_primary_buttons():
    """Enable per-label danger (red), success (green), and primary (blue) styles."""

    if getattr(InlineKeyboardButton, "_rdx_primary_buttons", False):
        return

    objects[_PrimaryButtonStyle.ID] = _PrimaryButtonStyle
    objects[_PrimaryCallbackButton.ID] = _PrimaryCallbackButton
    objects[_PrimaryUrlButton.ID] = _PrimaryUrlButton
    objects[_PrimarySwitchInlineButton.ID] = _PrimarySwitchInlineButton
    InlineKeyboardButton.write = _write_primary_button
    InlineKeyboardButton._rdx_primary_buttons = True

