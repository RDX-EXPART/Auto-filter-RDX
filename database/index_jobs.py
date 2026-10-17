# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

"""Resumable /index jobs.

Every indexing run is stored in the ``index_jobs`` collection of the same
MongoDB database as the file records. After each batch of Telegram messages the
engine writes the cursor (last fully processed message id) and the counters in
one update. If the dyno restarts, unfinished ``running`` jobs are picked up again
from that cursor. Batches are replayed safely because ``save_file`` is idempotent
(file_id / file_name lookup), so a replayed batch never creates a second record.

Channel exclusivity uses a lease document (``_id = "lock:<channel>"``) with an
expiry time. A lease held by a dead process expires on its own and is then taken
over, so a stale lock never blocks indexing forever.

This module has no pyrogram or pymongo import at module level. Telegram and
MongoDB access are injected through ``Deps`` and the store object, which keeps
the logic testable without a live bot or database.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

JOB_COLLECTION = "index_jobs"
LOCK_PREFIX = "lock:"
BATCH_SIZE = 100          # message ids per get_messages call (Telegram allows up to 200)
LEASE_SECONDS = 90.0      # channel lease length; renewed at every checkpoint and during waits
MAX_BATCH_RETRIES = 5     # non-FloodWait failures per batch before the job is marked failed
RETRY_BASE_SECONDS = 2.0
RESUME_SCAN_SECONDS = 20.0
COUNTER_KEYS = ("saved", "duplicate", "deleted", "no_media", "unsupported", "errors")
MEDIA_KINDS = ("video", "audio", "document")

# Process-local bookkeeping. Cross-process safety comes from the lease in MongoDB.
INSTANCE_ID = uuid.uuid4().hex
_OWNED_JOBS = set()       # job ids this process is driving or has scheduled
_ACTIVE_CHANNELS = set()  # channel keys this process is currently indexing


class ChannelBusy(Exception):
    """Another live job already holds the lease for this channel."""


class JobStopped(Exception):
    """The job must stop without marking it failed.

    notify_phase tells the caller what status text to show, or None to stay silent.
    """

    def __init__(self, reason, notify_phase=None):
        super().__init__(reason)
        self.notify_phase = notify_phase


class JobFailed(Exception):
    """Retries are exhausted. The job is marked failed and is not auto-resumed."""


@dataclass
class Deps:
    store: Any
    owner: str
    fetch: Callable[[Any, list], Awaitable[list]]
    save: Callable[[Any, Any], Awaitable[tuple]]
    notify: Optional[Callable[[dict, str], Awaitable[None]]] = None
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    batch_size: int = BATCH_SIZE
    lease_seconds: float = LEASE_SECONDS
    max_retries: int = MAX_BATCH_RETRIES
    retry_base: float = RETRY_BASE_SECONDS
    resume_interval: float = RESUME_SCAN_SECONDS


def channel_key(chat):
    """Stable key for a channel: numeric id, or lowercase username."""
    if isinstance(chat, int) or (isinstance(chat, str) and chat.lstrip("-").isdigit()):
        return f"id:{int(chat)}"
    return f"user:{str(chat).lstrip('@').lower()}"


def initial_cursor(skip):
    """The skip number is the last message id that is treated as already done.

    Indexing starts at skip + 1, so skip=2 processes messages 3, 4, 5 and so on.
    """
    return max(0, int(skip or 0))


def _utc_iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _is_flood_wait(exc):
    return type(exc).__name__ == "FloodWait" and isinstance(getattr(exc, "value", None), (int, float))


# ---------------------------------------------------------------------------
# Lease helpers
# ---------------------------------------------------------------------------

async def _call(fn, *args):
    return await asyncio.to_thread(fn, *args)


async def _heartbeat(deps, ckey):
    now = deps.clock()
    ok = await _call(deps.store.renew_lock, ckey, deps.owner, now, now + deps.lease_seconds)
    if not ok:
        raise JobStopped("channel lease lost to another worker")


async def _sleep_with_heartbeat(deps, ckey, seconds):
    """Sleep without letting the lease expire, even for long FloodWait waits."""
    step = max(1.0, deps.lease_seconds / 3)
    remaining = float(seconds)
    while remaining > 0:
        chunk = min(step, remaining)
        await deps.sleep(chunk)
        remaining -= chunk
        await _heartbeat(deps, ckey)


async def _notify(deps, job, phase):
    if deps.notify is None:
        return
    try:
        await deps.notify(job, phase)
    except Exception:  # a failed status edit must never stop indexing
        logger.warning("Could not update index status message", exc_info=True)


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

async def _process_message(msg, deps):
    """Handle one message and return its outcome (a key of COUNTER_KEYS)."""
    if msg is None or getattr(msg, "empty", False):
        return "deleted"
    kind = getattr(getattr(msg, "media", None), "value", None)
    if not kind:
        return "no_media"
    if kind not in MEDIA_KINDS:
        return "unsupported"
    media = getattr(msg, kind, None)
    if not media:
        return "unsupported"
    media.caption = msg.caption
    saved, code = await deps.save(media, msg)
    if saved:
        return "saved"
    if code == 0:
        return "duplicate"
    return "errors"


async def _run_batch(ids, job, base_counters, deps, ckey):
    """Process one id range and return the new counters.

    Each message's outcome is kept across retries of the same batch, so a message
    saved on a failed attempt is counted once as "saved" and never again as a
    duplicate. Records are idempotent, so reprocessing is safe either way.
    """
    attempt = 0
    floods = 0
    outcomes = {}
    while True:
        try:
            await _heartbeat(deps, ckey)
            pending = [mid for mid in ids if mid not in outcomes]
            if pending:
                messages = await deps.fetch(job["channel"], pending)
                by_id = {getattr(m, "id", None): m for m in (messages or []) if m is not None}
                for mid in pending:
                    outcomes[mid] = await _process_message(by_id.get(mid), deps)
            counters = dict(base_counters)
            for mid in ids:
                counters[outcomes[mid]] += 1
            return counters
        except JobStopped:
            raise
        except Exception as exc:
            if _is_flood_wait(exc) and floods < 20:
                floods += 1
                wait = int(exc.value) + 1
                logger.warning("FloodWait on batch %s-%s, sleeping %ss", ids[0], ids[-1], wait)
                await _sleep_with_heartbeat(deps, ckey, wait)
                continue
            attempt += 1
            if attempt >= deps.max_retries:
                raise JobFailed(f"batch {ids[0]}-{ids[-1]} failed after {attempt} attempts: {exc}") from exc
            delay = min(60.0, deps.retry_base * (2 ** attempt))
            logger.warning("Batch %s-%s failed (attempt %s), retrying in %ss: %s",
                           ids[0], ids[-1], attempt, delay, exc)
            await _sleep_with_heartbeat(deps, ckey, delay)


# ---------------------------------------------------------------------------
# Job driver
# ---------------------------------------------------------------------------

async def _drive(job_id, deps, job):
    """Run a job from its stored cursor to its target. The caller holds the lease."""
    ckey = job["channel_key"]
    counters = {key: int(job.get(key) or 0) for key in COUNTER_KEYS}
    last = int(job["last_processed_message_id"])
    target = int(job["target_message_id"])
    view = dict(job)
    try:
        while last < target:
            ids = list(range(last + 1, min(last + deps.batch_size, target) + 1))
            batch = await _run_batch(ids, job, counters, deps, ckey)

            now = deps.clock()
            await _heartbeat(deps, ckey)
            fields = dict(batch)
            fields.update({
                "last_processed_message_id": ids[-1],
                "updated_at": now,
                "lease_owner": deps.owner,
            })
            if not await _call(deps.store.checkpoint, job_id, fields):
                raise JobStopped("job is no longer running (cancelled)", notify_phase="cancelled")

            counters = batch
            last = ids[-1]
            view.update(counters)
            view["last_processed_message_id"] = last
            await _notify(deps, view, "running")

        now = deps.clock()
        if not await _call(deps.store.set_job_status, job_id, "completed", {"finished_at": now, "updated_at": now}):
            raise JobStopped("job was cancelled just before completion", notify_phase="cancelled")
        view["status"] = "completed"
        await _notify(deps, view, "completed")
        return "completed"

    except JobStopped as stop:
        logger.info("Index job %s stopped: %s", job_id, stop)
        if stop.notify_phase:
            view["status"] = stop.notify_phase
            await _notify(deps, view, stop.notify_phase)
        return stop.notify_phase or "stopped"

    except (JobFailed, Exception) as failure:
        # Unexpected errors are also marked failed. Otherwise the resume loop would
        # restart the same broken job on every scan.
        logger.error("Index job %s failed: %s", job_id, failure, exc_info=not isinstance(failure, JobFailed))
        now = deps.clock()
        try:
            await _call(deps.store.set_job_status, job_id, "failed",
                        {"last_error": str(failure)[:300], "updated_at": now})
        except Exception:
            logger.exception("Could not persist failed status for %s", job_id)
        view["status"] = "failed"
        view["last_error"] = str(failure)[:300]
        await _notify(deps, view, "failed")
        return "failed"

    finally:
        # Release on normal exit, on cancel and on SIGTERM. A hard kill (SIGKILL)
        # skips this, and the lease then expires on its own.
        try:
            deps.store.release_lock(ckey, deps.owner, deps.clock())
        except Exception:
            logger.exception("Could not release channel lease for %s", ckey)


async def start_job(*, channel, owner_id, start_id, target_id, status_chat_id, status_message_id, deps):
    """Start a new job for a channel and run it to completion or stop.

    Raises ChannelBusy if another live job already holds this channel.
    """
    ckey = channel_key(channel)
    if ckey in _ACTIVE_CHANNELS:
        raise ChannelBusy(ckey)

    job_id = uuid.uuid4().hex
    now = deps.clock()
    if not await _call(deps.store.claim_lock, ckey, deps.owner, job_id, now, now + deps.lease_seconds):
        raise ChannelBusy(ckey)

    _ACTIVE_CHANNELS.add(ckey)
    _OWNED_JOBS.add(job_id)
    try:
        job = {
            "_id": job_id,
            "kind": "job",
            "channel": channel,
            "channel_key": ckey,
            "owner_id": owner_id,
            "status": "running",
            "start_message_id": int(start_id),
            "target_message_id": int(target_id),
            "last_processed_message_id": int(start_id) - 1,
            "status_chat_id": status_chat_id,
            "status_message_id": status_message_id,
            "lease_owner": deps.owner,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
            **{key: 0 for key in COUNTER_KEYS},
        }
        try:
            await _call(deps.store.create_job, job)
        except Exception:
            deps.store.release_lock(ckey, deps.owner, deps.clock())
            raise
        await _drive(job_id, deps, job)
        return job_id
    finally:
        _ACTIVE_CHANNELS.discard(ckey)
        _OWNED_JOBS.discard(job_id)


async def resume_job(job_id, deps, wait_for_lease=True):
    """Claim and continue a running job after a restart.

    Returns None if the job is not running any more (completed, cancelled or failed).
    With wait_for_lease, a lease still held by a dead process is waited out.
    """
    if job_id in _OWNED_JOBS:
        return None
    _OWNED_JOBS.add(job_id)
    try:
        while True:
            job = await _call(deps.store.get_job, job_id)
            if not job or job.get("status") != "running":
                return None
            ckey = job["channel_key"]
            if ckey in _ACTIVE_CHANNELS:
                if not wait_for_lease:
                    raise ChannelBusy(ckey)
            else:
                now = deps.clock()
                if await _call(deps.store.claim_lock, ckey, deps.owner, job_id, now, now + deps.lease_seconds):
                    job = await _call(deps.store.get_job, job_id)
                    if not job or job.get("status") != "running":
                        deps.store.release_lock(ckey, deps.owner, deps.clock())
                        return None
                    _ACTIVE_CHANNELS.add(ckey)
                    try:
                        logger.info("Resuming index job %s from message %s",
                                    job_id, int(job["last_processed_message_id"]) + 1)
                        return await _drive(job_id, deps, job)
                    finally:
                        _ACTIVE_CHANNELS.discard(ckey)
                if not wait_for_lease:
                    raise ChannelBusy(ckey)
            await deps.sleep(max(1.0, deps.lease_seconds / 3))
    finally:
        _OWNED_JOBS.discard(job_id)


def _spawn_resume(job_id, deps):
    if job_id in _OWNED_JOBS:
        return

    async def runner():
        try:
            await resume_job(job_id, deps)
        except Exception:
            logger.exception("Resuming index job %s failed", job_id)

    asyncio.create_task(runner())


async def resume_unfinished_jobs(deps):
    """Background loop: resume every running job that no live worker owns.

    Runs once at startup, then periodically. Cancelled, paused, completed and
    failed jobs are never picked up.
    """
    try:
        await _call(deps.store.ensure_indexes)
    except Exception:
        logger.exception("Could not ensure index_jobs indexes; continuing")
    while True:
        try:
            for job in await _call(deps.store.list_running):
                _spawn_resume(job["_id"], deps)
        except Exception:
            logger.exception("Index job resume scan failed")
        await deps.sleep(deps.resume_interval)


async def cancel_running_jobs(deps):
    """Mark every running job cancelled. The driving task stops at its next checkpoint."""
    return await _call(deps.store.cancel_running, deps.clock())


# ---------------------------------------------------------------------------
# Status text
# ---------------------------------------------------------------------------

def _counts_line(job):
    skipped = int(job.get("no_media") or 0) + int(job.get("unsupported") or 0)
    return (
        f"Total messages saved: <code>{int(job.get('saved') or 0)}</code>\n"
        f"Duplicate Files Skipped: <code>{int(job.get('duplicate') or 0)}</code>\n"
        f"Deleted Messages Skipped: <code>{int(job.get('deleted') or 0)}</code>\n"
        f"Non-Media messages skipped: <code>{skipped}</code>"
        f"(Unsupported Media - `{int(job.get('unsupported') or 0)}` )\n"
        f"Errors Occurred: <code>{int(job.get('errors') or 0)}</code>"
    )


def format_progress(job, phase):
    last = int(job.get("last_processed_message_id") or 0)
    target = int(job.get("target_message_id") or 0)
    start = int(job.get("start_message_id") or 0)
    processed = max(0, last - start + 1)
    if phase == "running":
        return (
            f"Indexing <code>{processed}</code> messages so far (last message ID <code>{last}</code> of <code>{target}</code>)\n"
            + _counts_line(job)
        )
    if phase == "completed":
        return "Successfully saved all messages to the database!\n" + _counts_line(job)
    if phase == "cancelled":
        return "Successfully Cancelled!!\n\n" + _counts_line(job) + (
            f"\n\nStopped at message ID <code>{last}</code>. Restarting /index is safe, "
            "already-saved files are skipped."
        )
    if phase == "failed":
        return (
            "Indexing stopped because of an error and was not resumed automatically.\n"
            f"Last error: <code>{job.get('last_error') or 'unknown'}</code>\n\n"
            + _counts_line(job)
            + "\n\nRun /index again to continue. Already-saved files are skipped."
        )
    return _counts_line(job)


def format_job_summary(job):
    last = int(job.get("last_processed_message_id") or 0)
    target = int(job.get("target_message_id") or 0)
    updated = job.get("updated_at")
    updated_text = _utc_iso(updated) if isinstance(updated, (int, float)) else "unknown"
    return (
        f"Job <code>{str(job.get('_id'))[:8]}</code> | <b>{job.get('status')}</b>\n"
        f"Channel: <code>{job.get('channel_key')}</code>\n"
        f"Cursor: message <code>{last}</code> of <code>{target}</code>\n"
        f"Saved <code>{int(job.get('saved') or 0)}</code> | "
        f"Duplicate <code>{int(job.get('duplicate') or 0)}</code> | "
        f"Deleted <code>{int(job.get('deleted') or 0)}</code> | "
        f"No media <code>{int(job.get('no_media') or 0)}</code> | "
        f"Unsupported <code>{int(job.get('unsupported') or 0)}</code> | "
        f"Errors <code>{int(job.get('errors') or 0)}</code>\n"
        f"Updated: {updated_text}"
        + (f"\nLast error: <code>{job.get('last_error')}</code>" if job.get("last_error") else "")
    )


# ---------------------------------------------------------------------------
# MongoDB store and Telegram wiring (imported lazily at runtime)
# ---------------------------------------------------------------------------

class MongoJobStore:
    """Blocking store. Engine code calls it through asyncio.to_thread."""

    def __init__(self, database):
        self.jobs = database[JOB_COLLECTION]

    def ensure_indexes(self):
        # Non-unique helper indexes only. The collection is small.
        self.jobs.create_index([("kind", 1), ("status", 1)])
        self.jobs.create_index([("channel_key", 1), ("status", 1)])

    def create_job(self, doc):
        self.jobs.insert_one(doc)

    def get_job(self, job_id):
        return self.jobs.find_one({"_id": job_id})

    def list_running(self):
        return list(self.jobs.find({"kind": "job", "status": "running"}))

    def recent_jobs(self, limit=3):
        return list(self.jobs.find({"kind": "job"}).sort("created_at", -1).limit(limit))

    def claim_lock(self, channel_key, owner, job_id, now, lease_until):
        from pymongo.errors import DuplicateKeyError
        try:
            self.jobs.update_one(
                {"_id": LOCK_PREFIX + channel_key,
                 "$or": [{"lease_until": {"$lt": now}}, {"owner": owner}]},
                {"$set": {"kind": "lock", "channel_key": channel_key, "owner": owner,
                          "job_id": job_id, "lease_until": lease_until}},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            return False

    def renew_lock(self, channel_key, owner, now, lease_until):
        res = self.jobs.update_one(
            {"_id": LOCK_PREFIX + channel_key, "owner": owner},
            {"$set": {"lease_until": lease_until}},
        )
        return res.matched_count == 1

    def release_lock(self, channel_key, owner, now):
        self.jobs.update_one(
            {"_id": LOCK_PREFIX + channel_key, "owner": owner},
            {"$set": {"lease_until": 0}},
        )

    def checkpoint(self, job_id, fields):
        res = self.jobs.update_one({"_id": job_id, "status": "running"}, {"$set": fields})
        return res.matched_count == 1

    def set_job_status(self, job_id, status, fields):
        res = self.jobs.update_one(
            {"_id": job_id, "status": "running"},
            {"$set": {"status": status, **fields}},
        )
        return res.matched_count == 1

    def cancel_running(self, now):
        res = self.jobs.update_many(
            {"kind": "job", "status": "running"},
            {"$set": {"status": "cancelled", "cancelled_at": now, "updated_at": now}},
        )
        return res.modified_count


_store = None


def get_store():
    global _store
    if _store is None:
        from database.ia_filterdb import db  # the single configured database
        _store = MongoJobStore(db)
    return _store


def make_default_notify(bot):
    async def notify(job, phase):
        chat_id = job.get("status_chat_id")
        message_id = job.get("status_message_id")
        if not chat_id or not message_id:
            return
        markup = None
        if phase == "running":
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Cancel", callback_data="index_cancel")]]
            )
        try:
            await bot.edit_message_text(chat_id, message_id, format_progress(job, phase), reply_markup=markup)
        except Exception as exc:
            if "not modified" not in str(exc).lower():
                logger.warning("Status edit failed: %s", exc)
    return notify


def make_telegram_deps(bot, notify=None):
    from database.ia_filterdb import save_file

    async def fetch(chat, ids):
        return await bot.get_messages(chat, message_ids=ids)

    async def save(media, message):
        return await save_file(media, source_message=message)

    return Deps(
        store=get_store(),
        owner=INSTANCE_ID,
        fetch=fetch,
        save=save,
        notify=notify or make_default_notify(bot),
    )
