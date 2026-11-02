"""
Compatibility layer for Kurigram >= 2.2.26.

Newer Kurigram removed the old keyword arguments this bot still uses:
    quote=True                      -> reply_parameters=ReplyParameters(message_id=...)
    reply_to_message_id=<id>        -> reply_parameters=ReplyParameters(message_id=<id>)
    disable_web_page_preview=True   -> link_preview_options=LinkPreviewOptions(is_disabled=True)

This module wraps the send/reply/edit methods so the old keywords keep working.
It only changes a keyword when the installed Kurigram does NOT accept it, so on
older versions (e.g. 2.2.24) it does nothing.
"""
import inspect
from functools import wraps

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

try:
    from pyrogram.types import LinkPreviewOptions, ReplyParameters
except Exception:  # very old build, nothing to translate
    LinkPreviewOptions = ReplyParameters = None


def _translate(self, kw, params):
    """Rewrite legacy keywords in `kw` (in place) according to the real signature `params`."""
    if 'quote' in kw and 'quote' not in params:
        quote = kw.pop('quote')
        if (quote and isinstance(self, Message) and ReplyParameters
                and 'reply_parameters' in params
                and 'reply_parameters' not in kw
                and 'reply_to_message_id' not in kw):
            kw['reply_parameters'] = ReplyParameters(message_id=self.id)

    if 'reply_to_message_id' in kw and 'reply_to_message_id' not in params:
        rid = kw.pop('reply_to_message_id')
        if rid and ReplyParameters and 'reply_parameters' in params and 'reply_parameters' not in kw:
            kw['reply_parameters'] = ReplyParameters(message_id=rid)

    if 'disable_web_page_preview' in kw and 'disable_web_page_preview' not in params:
        disable = kw.pop('disable_web_page_preview')
        if (disable and LinkPreviewOptions
                and 'link_preview_options' in params
                and 'link_preview_options' not in kw):
            kw['link_preview_options'] = LinkPreviewOptions(is_disabled=True)


def _wrap(cls, name):
    orig = getattr(cls, name, None)
    if orig is None or getattr(orig, '_pyro_compat', False) or not callable(orig):
        return
    try:
        params = inspect.signature(orig).parameters
    except (TypeError, ValueError):
        return
    legacy = ('quote', 'reply_to_message_id', 'disable_web_page_preview')
    if all(p in params for p in legacy):
        return  # this build still accepts everything, no need to wrap

    @wraps(orig)
    def wrapper(self, *args, **kwargs):
        _translate(self, kwargs, params)
        return orig(self, *args, **kwargs)

    wrapper._pyro_compat = True
    setattr(cls, name, wrapper)


def apply():
    for name in dir(Client):
        if name.startswith(('send_', 'edit_message_', 'copy_message')):
            _wrap(Client, name)
    for name in dir(Message):
        if name.startswith(('reply', 'edit', 'copy')):
            _wrap(Message, name)
    for name in dir(CallbackQuery):
        if name.startswith('edit_message'):
            _wrap(CallbackQuery, name)


apply()
