# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import jinja2
from info import *
from RDX.bot import TechVJBot
from RDX.util.human_readable import humanbytes
from RDX.util.file_properties import get_file_ids
from RDX.server.exceptions import InvalidHash
import urllib.parse
import logging
import aiohttp
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape


async def render_page(id, secure_hash, src=None):
    file = await TechVJBot.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(TechVJBot, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote_plus(file_data.file_name)}?hash={secure_hash}",
    )

    tag = file_data.mime_type.split("/")[0].strip()
    file_size = humanbytes(file_data.file_size)
    if tag in ["video", "audio"]:
        template_file = "req.html"
    else:
        template_file = "dl.html"
        async with aiohttp.ClientSession() as s:
            async with s.get(src) as u:
                file_size = humanbytes(int(u.headers.get("Content-Length")))

    template_dir = Path(__file__).resolve().parents[1] / "template"
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = environment.get_template(template_file)

    file_name = file_data.file_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
    )

