# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, re, asyncio
from utils import temp
from info import ADMINS
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database import index_jobs
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_resume#'):
        job_id = query.data.split('#', 1)[1]
        deps = index_jobs.make_telegram_deps(bot)
        job = await asyncio.to_thread(deps.store.get_job, job_id)
        if not job or job.get('status') != 'running':
            return await query.answer("This job is no longer running.", show_alert=True)
        await query.answer("Resuming indexing")
        asyncio.create_task(_resume_in_background(job_id, deps))
        return
    if query.data.startswith('index_discard#'):
        job_id = query.data.split('#', 1)[1]
        deps = index_jobs.make_telegram_deps(bot)
        stopped = await index_jobs.discard_job(job_id, deps)
        await query.answer("Job discarded" if stopped else "Job already stopped")
        try:
            await query.message.edit_text(query.message.text + "\n\n🗑 Discarded by admin.")
        except Exception:
            pass
        return
    if query.data.startswith('index_cancel'):
        await index_jobs.cancel_running_jobs(index_jobs.make_telegram_deps(bot))
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been decliened by our moderators.',
            reply_to_message_id=int(lst_msg_id)
        )
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
            reply_to_message_id=int(lst_msg_id)
        )
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot, owner_id=int(from_user))


@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):
    vj = await bot.ask(message.chat.id, "**Now Send Me Your Channel Last Post Link Or Forward A Last Message From Your Index Channel.\n\nAnd You Can Set Skip Number By - /setskip yourskipnumber**")
    if vj.forward_from_chat and vj.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = vj.forward_from_message_id
        chat_id = vj.forward_from_chat.username or vj.forward_from_chat.id
    elif vj.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(vj.text)
        if not match:
            return await vj.reply('Invalid link\n\nTry again by /index')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await vj.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await vj.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await vj.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [[
            InlineKeyboardButton('Yes', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],[
            InlineKeyboardButton('close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup
        )

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [[
        InlineKeyboardButton('Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
    ],[
        InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(
        LOG_CHANNEL,
        f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
        reply_markup=reply_markup
    )
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")


async def index_files_to_db(lst_msg_id, chat, msg, bot, owner_id=None):
    """Run one resumable indexing job. Progress is checkpointed in MongoDB."""
    start_id = index_jobs.initial_cursor(temp.CURRENT) + 1
    deps = index_jobs.make_telegram_deps(bot)
    async with lock:
        try:
            await index_jobs.start_job(
                channel=chat,
                owner_id=owner_id,
                start_id=start_id,
                target_id=lst_msg_id,
                status_chat_id=msg.chat.id,
                status_message_id=msg.id,
                deps=deps,
            )
        except index_jobs.ChannelBusy:
            await msg.edit(
                "Another indexing job is already running for this channel.\n\nUse /index_status to check it, or /cancel to stop it."
            )
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')


async def _resume_in_background(job_id, deps):
    try:
        await index_jobs.resume_job(job_id, deps)
    except Exception:
        logger.exception("Resuming index job %s failed", job_id)


@Client.on_message(filters.command('cancel') & filters.user(ADMINS))
async def cancel_index_command(bot, message):
    """Cancel every running indexing job. The state is saved, so it is not resumed after a restart."""
    deps = index_jobs.make_telegram_deps(bot)
    count = await index_jobs.cancel_running_jobs(deps)
    if count:
        await message.reply(f"Cancelled {count} running indexing job(s). They will not resume automatically.")
    else:
        await message.reply("No indexing job is running.")


@Client.on_message(filters.command('index_status') & filters.user(ADMINS))
async def index_status_command(bot, message):
    """Show the latest indexing jobs and their saved progress."""
    jobs = await asyncio.to_thread(index_jobs.get_store().recent_jobs, 3)
    if not jobs:
        return await message.reply("No indexing job has been started yet.")
    text = "\n\n".join(index_jobs.format_job_summary(job) for job in jobs)
    await message.reply(text)
