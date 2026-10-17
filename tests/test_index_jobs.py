"""Tests for resumable /index jobs and the single-database cleanup.

Run from the repository root:  python3 -m unittest discover -s tests -t . -v
These tests use an in-memory store and a fake Telegram client, so they need no
MongoDB, no Telegram account and no network access.
"""

import asyncio
import os
import unittest

from database import index_jobs
from database.index_jobs import (
    BATCH_SIZE, ChannelBusy, Deps, LEASE_SECONDS, channel_key, format_progress,
    initial_cursor, resume_job, resume_unfinished_jobs, start_job, cancel_running_jobs,
)


class KillSignal(BaseException):
    """Simulates the process being killed. It is not an Exception, so it is not caught."""


class FloodWait(Exception):
    def __init__(self, value):
        super().__init__(f"FloodWait {value}")
        self.value = value


class TransientDbError(Exception):
    pass


class FakeStore:
    """Mirrors the MongoJobStore semantics: conditional updates and leases."""

    def __init__(self):
        self.jobs = {}
        self.locks = {}

    def ensure_indexes(self):
        pass

    def create_job(self, doc):
        assert doc["_id"] not in self.jobs
        self.jobs[doc["_id"]] = dict(doc)

    def get_job(self, job_id):
        job = self.jobs.get(job_id)
        return dict(job) if job else None

    def list_running(self):
        return [dict(j) for j in self.jobs.values() if j.get("kind") == "job" and j["status"] == "running"]

    def recent_jobs(self, limit=3):
        return [dict(j) for j in self.jobs.values()][-limit:]

    def claim_lock(self, ckey, owner, job_id, now, lease_until):
        lock = self.locks.get(ckey)
        if lock is None or lock["lease_until"] < now or lock["owner"] == owner:
            self.locks[ckey] = {"owner": owner, "job_id": job_id, "lease_until": lease_until}
            return True
        return False

    def renew_lock(self, ckey, owner, now, lease_until):
        lock = self.locks.get(ckey)
        if lock and lock["owner"] == owner:
            lock["lease_until"] = lease_until
            return True
        return False

    def release_lock(self, ckey, owner, now):
        lock = self.locks.get(ckey)
        if lock and lock["owner"] == owner:
            lock["lease_until"] = 0

    def checkpoint(self, job_id, fields):
        job = self.jobs.get(job_id)
        if job and job["status"] == "running":
            job.update(fields)
            return True
        return False

    def set_job_status(self, job_id, status, fields):
        job = self.jobs.get(job_id)
        if job and job["status"] == "running":
            job.update({"status": status, **fields})
            return True
        return False

    def cancel_running(self, now):
        count = 0
        for job in self.jobs.values():
            if job.get("kind") == "job" and job["status"] == "running":
                job.update({"status": "cancelled", "cancelled_at": now})
                count += 1
        return count


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def now(self):
        return self.t

    async def sleep(self, seconds):
        self.t += seconds


class Media:
    def __init__(self, file_id):
        self.file_id = file_id
        self.file_size = 100
        self.file_name = f"{file_id}.mkv"
        self.caption = None


class MediaType:
    def __init__(self, value):
        self.value = value


class Msg:
    def __init__(self, msg_id, kind=None, file_id=None, empty=False):
        self.id = msg_id
        self.empty = empty
        self.caption = None
        self.media = MediaType(kind) if kind else None
        if kind:
            setattr(self, kind, Media(file_id or f"f{msg_id}"))


class FakeTelegram:
    """Fake get_messages and save. Records every fetch and save so tests can assert on them."""

    def __init__(self, messages):
        self.messages = messages      # id -> Msg, or None for a deleted message
        self.records = {}             # file_id -> message id (the "database")
        self.fetch_calls = []         # list of id lists, in order
        self.fetch_failures = []      # exceptions to raise before the next fetch succeeds
        self.save_failures = {}       # msg_id -> number of TransientDbError to raise
        self.kill_on_save = None      # msg_id: raise KillSignal once during save
        self.cancel_on_fetch = None   # (ids_start, callback)

    async def fetch(self, chat, ids):
        self.fetch_calls.append(list(ids))
        if self.cancel_on_fetch and ids[0] == self.cancel_on_fetch[0]:
            self.cancel_on_fetch[1]()
        if self.fetch_failures:
            raise self.fetch_failures.pop(0)
        return [self.messages.get(i) for i in ids]

    async def save(self, media, message):
        if self.save_failures.get(message.id, 0) > 0:
            self.save_failures[message.id] -= 1
            raise TransientDbError("temporary mongo error")
        if self.kill_on_save == message.id:
            self.kill_on_save = None
            raise KillSignal()
        if media.file_id in self.records:
            return False, 0
        self.records[media.file_id] = message.id
        return True, 1

    def fetched_ids(self):
        return [i for call in self.fetch_calls for i in call]


def make_deps(store, clock, tg, owner, **kwargs):
    return Deps(store=store, owner=owner, fetch=tg.fetch, save=tg.save,
                clock=clock.now, sleep=clock.sleep, **kwargs)


def build_messages(total):
    """Mixed channel: media, deleted, non-media, unsupported and one duplicate."""
    messages = {}
    for i in range(1, total + 1):
        if i % 10 == 0:
            messages[i] = None                              # deleted
        elif i % 7 == 0:
            messages[i] = Msg(i)                            # text, no media
        elif i % 13 == 0:
            messages[i] = Msg(i, kind="photo")              # unsupported media
        elif i == 50:
            messages[i] = Msg(i, kind="document", file_id="f49")  # duplicate of 49
        else:
            messages[i] = Msg(i, kind="document")
    return messages


def expected_counters(messages, total):
    seen, counts = set(), {k: 0 for k in index_jobs.COUNTER_KEYS}
    for i in range(1, total + 1):
        msg = messages.get(i)
        if msg is None:
            counts["deleted"] += 1
        elif not msg.media:
            counts["no_media"] += 1
        elif msg.media.value not in index_jobs.MEDIA_KINDS:
            counts["unsupported"] += 1
        else:
            fid = getattr(msg, msg.media.value).file_id
            if fid in seen:
                counts["duplicate"] += 1
            else:
                seen.add(fid)
                counts["saved"] += 1
    return counts


class IndexJobsTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        index_jobs._OWNED_JOBS.clear()
        index_jobs._ACTIVE_CHANNELS.clear()
        self.store = FakeStore()
        self.clock = Clock()

    async def start(self, tg, total, owner="instance-1", start_id=1, **deps_kwargs):
        deps = make_deps(self.store, self.clock, tg, owner, **deps_kwargs)
        return await start_job(
            channel=-1001234567890, owner_id=1, start_id=start_id, target_id=total,
            status_chat_id=10, status_message_id=20, deps=deps,
        )

    def only_job(self):
        jobs = [j for j in self.store.jobs.values() if j.get("kind") == "job"]
        self.assertEqual(len(jobs), 1)
        return jobs[0]


class TestFullRun(IndexJobsTestBase):
    async def test_full_run_visits_every_message_once_and_counts_match(self):
        total = 250
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        job_id = await self.start(tg, total)

        self.assertEqual(tg.fetched_ids(), list(range(1, total + 1)))
        job = self.store.jobs[job_id]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["last_processed_message_id"], total)
        expected = expected_counters(messages, total)
        for key in index_jobs.COUNTER_KEYS:
            self.assertEqual(job[key], expected[key], key)
        self.assertEqual(sum(job[k] for k in index_jobs.COUNTER_KEYS), total)
        self.assertEqual(len(tg.records), expected["saved"])
        self.assertNotIn(f"lock:{channel_key(-1001234567890)}", [k for k, v in self.store.locks.items() if v["lease_until"] > self.clock.now()])

    async def test_batches_are_bounded(self):
        tg = FakeTelegram(build_messages(250))
        await self.start(tg, 250)
        self.assertTrue(all(len(call) <= BATCH_SIZE for call in tg.fetch_calls))
        self.assertEqual(len(tg.fetch_calls), 3)


class TestRestartResume(IndexJobsTestBase):
    async def test_restart_after_checkpoint_continues_from_next_message(self):
        total = 250
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        # Kill the process at the start of batch 3 (ids 201..250). The first two
        # batches have been checkpointed by then.
        original_fetch = tg.fetch

        async def killing_fetch(chat, ids):
            if ids[0] == 201:
                raise KillSignal()
            return await original_fetch(chat, ids)

        tg.fetch = killing_fetch
        with self.assertRaises(KillSignal):
            await self.start(tg, total, owner="instance-1")

        job = self.only_job()
        self.assertEqual(job["status"], "running")
        self.assertEqual(job["last_processed_message_id"], 200)

        # New process: fresh owner, same database.
        index_jobs._OWNED_JOBS.clear()
        index_jobs._ACTIVE_CHANNELS.clear()
        tg2 = FakeTelegram(messages)
        tg2.records = tg.records
        deps2 = make_deps(self.store, self.clock, tg2, "instance-2")
        await resume_job(job["_id"], deps2)

        self.assertEqual(tg2.fetch_calls[0][0], 201)              # next message after checkpoint
        self.assertEqual(tg2.fetched_ids(), list(range(201, total + 1)))
        job = self.store.jobs[job["_id"]]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(sum(job[k] for k in index_jobs.COUNTER_KEYS), total)
        expected = expected_counters(messages, total)
        self.assertEqual(job["saved"], expected["saved"])
        self.assertEqual(len(tg2.records), expected["saved"])

    async def test_kill_between_save_and_checkpoint_replays_without_duplicates(self):
        total = 250
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        tg.kill_on_save = 205         # some of batch 3 is already written when the kill happens
        with self.assertRaises(KillSignal):
            await self.start(tg, total, owner="instance-1")
        records_before_kill = len(tg.records)
        self.assertGreater(records_before_kill, 0)

        index_jobs._OWNED_JOBS.clear()
        index_jobs._ACTIVE_CHANNELS.clear()
        tg2 = FakeTelegram(messages)
        tg2.records = tg.records
        await resume_job(self.only_job()["_id"], make_deps(self.store, self.clock, tg2, "instance-2"))

        self.assertEqual(tg2.fetch_calls[0][0], 201)              # replay starts at the uncommitted batch
        expected = expected_counters(messages, total)
        self.assertEqual(len(tg2.records), expected["saved"])     # no duplicate file records
        job = self.only_job()
        self.assertEqual(job["status"], "completed")
        self.assertEqual(sum(job[k] for k in index_jobs.COUNTER_KEYS), total)

    async def test_hard_kill_leaves_lease_until_it_expires(self):
        total = 250
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        original_fetch = tg.fetch

        async def killing_fetch(chat, ids):
            if ids[0] == 101:
                raise KillSignal()
            return await original_fetch(chat, ids)

        tg.fetch = killing_fetch
        # SIGKILL: no finally block runs, so the lease is not released.
        self.store.release_lock = lambda *args: None
        with self.assertRaises(KillSignal):
            await self.start(tg, total, owner="instance-1")
        del self.store.release_lock

        index_jobs._OWNED_JOBS.clear()
        index_jobs._ACTIVE_CHANNELS.clear()
        job_id = self.only_job()["_id"]
        tg2 = FakeTelegram(messages)
        tg2.records = tg.records
        deps2 = make_deps(self.store, self.clock, tg2, "instance-2")

        with self.assertRaises(ChannelBusy):
            await resume_job(job_id, deps2, wait_for_lease=False)

        self.clock.t += LEASE_SECONDS + 1          # the dead process's lease has expired
        await resume_job(job_id, deps2, wait_for_lease=False)
        self.assertEqual(self.store.jobs[job_id]["status"], "completed")
        self.assertEqual(tg2.fetched_ids(), list(range(101, total + 1)))

    async def test_waiting_resume_takes_over_after_lease_expiry(self):
        total = 150
        tg = FakeTelegram(build_messages(total))
        self.store.locks[channel_key(-1001234567890)] = {
            "owner": "dead-instance", "job_id": "x", "lease_until": self.clock.now() + 30,
        }
        job_id = "job-stale"
        self.store.create_job({
            "_id": job_id, "kind": "job", "channel": -1001234567890,
            "channel_key": channel_key(-1001234567890), "status": "running",
            "start_message_id": 1, "target_message_id": total,
            "last_processed_message_id": 0, **{k: 0 for k in index_jobs.COUNTER_KEYS},
        })
        await resume_job(job_id, make_deps(self.store, self.clock, tg, "instance-2"))
        self.assertEqual(self.store.jobs[job_id]["status"], "completed")
        self.assertEqual(tg.fetched_ids(), list(range(1, total + 1)))


class TestCancelAndStatus(IndexJobsTestBase):
    async def test_cancelled_job_is_persisted_and_never_auto_resumed(self):
        total = 250
        tg = FakeTelegram(build_messages(total))
        tg.cancel_on_fetch = (101, lambda: self.store.cancel_running(self.clock.now()))
        job_id = await self.start(tg, total)

        job = self.store.jobs[job_id]
        self.assertEqual(job["status"], "cancelled")
        self.assertEqual(job["last_processed_message_id"], 100)  # stopped at the batch boundary
        calls_before = len(tg.fetch_calls)

        self.assertEqual(self.store.list_running(), [])
        self.assertIsNone(await resume_job(job_id, make_deps(self.store, self.clock, tg, "instance-2")))
        self.assertEqual(len(tg.fetch_calls), calls_before)      # nothing was fetched again

    async def test_scanner_skips_cancelled_and_completed_jobs(self):
        total = 120
        tg = FakeTelegram(build_messages(total))
        done_id = await self.start(tg, total)
        self.assertEqual(self.store.jobs[done_id]["status"], "completed")

        scans = {"n": 0}

        class _StopScan(Exception):
            pass

        async def stop_after_one_scan(seconds):
            scans["n"] += 1
            raise _StopScan()

        deps = make_deps(self.store, self.clock, tg, "instance-2", resume_interval=1)
        deps.sleep = stop_after_one_scan
        calls_before = len(tg.fetch_calls)
        with self.assertRaises(_StopScan):
            await resume_unfinished_jobs(deps)
        for _ in range(5):
            await asyncio.sleep(0)
        self.assertEqual(len(tg.fetch_calls), calls_before)

    async def test_cancel_running_jobs_reports_count(self):
        deps = make_deps(self.store, self.clock, FakeTelegram({}), "instance-1")
        self.store.create_job({"_id": "a", "kind": "job", "status": "running"})
        self.store.create_job({"_id": "b", "kind": "job", "status": "completed"})
        self.assertEqual(await cancel_running_jobs(deps), 1)
        self.assertEqual(self.store.jobs["a"]["status"], "cancelled")
        self.assertEqual(self.store.jobs["b"]["status"], "completed")


class TestLeases(IndexJobsTestBase):
    async def test_live_lease_from_another_worker_blocks_new_job(self):
        self.store.locks[channel_key(-1001234567890)] = {
            "owner": "other-live", "job_id": "x", "lease_until": self.clock.now() + 60,
        }
        tg = FakeTelegram(build_messages(10))
        with self.assertRaises(ChannelBusy):
            await self.start(tg, 10)
        self.assertEqual(self.store.jobs, {})
        self.assertEqual(tg.fetch_calls, [])

    async def test_stale_lease_is_recovered_for_new_job(self):
        self.store.locks[channel_key(-1001234567890)] = {
            "owner": "dead", "job_id": "x", "lease_until": self.clock.now() - 1,
        }
        tg = FakeTelegram(build_messages(10))
        job_id = await self.start(tg, 10)
        self.assertEqual(self.store.jobs[job_id]["status"], "completed")

    async def test_lease_is_released_after_completion(self):
        tg = FakeTelegram(build_messages(10))
        await self.start(tg, 10)
        lock = self.store.locks[channel_key(-1001234567890)]
        self.assertLessEqual(lock["lease_until"], 0)

    def test_channel_key_normalises_id_and_username(self):
        self.assertEqual(channel_key(-1001), "id:-1001")
        self.assertEqual(channel_key("-1001"), "id:-1001")
        self.assertEqual(channel_key("@Some_Channel"), channel_key("some_channel"))


class TestRetries(IndexJobsTestBase):
    async def test_flood_wait_sleeps_and_retries_without_duplicates(self):
        total = 120
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        tg.fetch_failures = [FloodWait(3)]
        slept = []

        async def record_sleep(seconds):
            slept.append(seconds)
            self.clock.t += seconds

        deps = make_deps(self.store, self.clock, tg, "instance-1")
        deps.sleep = record_sleep
        job_id = await start_job(channel=-1001234567890, owner_id=1, start_id=1, target_id=total,
                                 status_chat_id=1, status_message_id=2, deps=deps)

        self.assertIn(4, slept)                                    # FloodWait 3 plus one second
        self.assertEqual(self.store.jobs[job_id]["status"], "completed")
        expected = expected_counters(messages, total)
        self.assertEqual(len(tg.records), expected["saved"])
        self.assertEqual(self.store.jobs[job_id]["saved"], expected["saved"])

    async def test_transient_save_error_is_retried_and_counted_once(self):
        total = 30
        messages = build_messages(total)
        tg = FakeTelegram(messages)
        tg.save_failures = {3: 2}                                  # fails twice, then succeeds
        job_id = await self.start(tg, total)

        self.assertEqual(self.store.jobs[job_id]["status"], "completed")
        expected = expected_counters(messages, total)
        job = self.store.jobs[job_id]
        self.assertEqual(job["saved"], expected["saved"])
        self.assertEqual(sum(job[k] for k in index_jobs.COUNTER_KEYS), total)
        self.assertEqual(len(tg.records), expected["saved"])

    async def test_exhausted_retries_mark_job_failed_and_do_not_resume(self):
        total = 30
        tg = FakeTelegram(build_messages(total))
        tg.save_failures = {3: 10_000}                             # never recovers
        job_id = await self.start(tg, total)

        job = self.store.jobs[job_id]
        self.assertEqual(job["status"], "failed")
        self.assertIn("batch", job["last_error"])
        self.assertEqual(self.store.list_running(), [])


class TestCursorBoundaries(IndexJobsTestBase):
    def test_skip_number_is_the_last_done_message(self):
        self.assertEqual(initial_cursor(2) + 1, 3)
        self.assertEqual(initial_cursor(0) + 1, 1)
        self.assertEqual(initial_cursor(-5), 0)
        self.assertEqual(initial_cursor(None), 0)

    async def test_skip_two_starts_at_message_three(self):
        tg = FakeTelegram(build_messages(5))
        await self.start(tg, 5, start_id=3)
        self.assertEqual(tg.fetched_ids(), [3, 4, 5])

    async def test_skip_at_or_past_target_completes_without_fetching(self):
        tg = FakeTelegram(build_messages(5))
        job_id = await self.start(tg, 5, start_id=6)
        self.assertEqual(tg.fetch_calls, [])
        self.assertEqual(self.store.jobs[job_id]["status"], "completed")

    async def test_single_message_job(self):
        tg = FakeTelegram({7: Msg(7, kind="document")})
        job_id = await self.start(tg, 7, start_id=7)
        self.assertEqual(tg.fetched_ids(), [7])
        self.assertEqual(self.store.jobs[job_id]["saved"], 1)


class TestStatusText(unittest.TestCase):
    def test_progress_and_final_messages_show_counts(self):
        job = {"start_message_id": 1, "last_processed_message_id": 50, "target_message_id": 100,
               "saved": 5, "duplicate": 2, "deleted": 1, "no_media": 3, "unsupported": 4, "errors": 0}
        running = format_progress(job, "running")
        self.assertIn("<code>50</code> of <code>100</code>", running)
        self.assertIn("Total messages saved: <code>5</code>", running)
        self.assertIn("Non-Media messages skipped: <code>7</code>", running)
        self.assertIn("Successfully Cancelled", format_progress(job, "cancelled"))
        self.assertIn("Successfully saved", format_progress(job, "completed"))


class TestSingleDatabaseCleanup(unittest.TestCase):
    """No multiple-database option, URI or second collection may remain in the code."""

    FORBIDDEN = (
        "MULTIPLE_DATABASE", "O_DB_URI", "F_DB_URI", "S_DB_URI", "SEC_FILE_DB_URI",
        "FILE_DB_URI", "OTHER_DB_URI", "USER_DB_URI", "sec_col", "sec_client",
        "sec_db", "sec_collection", "multiple database",
    )

    def test_no_multi_database_references_remain(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "tests")]
            for name in filenames:
                if not name.endswith((".py", ".md", ".yml", ".yaml", ".txt", ".json", ".conf")):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read().lower()
                for token in self.FORBIDDEN:
                    if token.lower() in text:
                        hits.append(f"{os.path.relpath(path, root)}: {token}")
        self.assertEqual(hits, [])

    def test_info_parses_database_settings_without_multi_db(self):
        info_path = os.path.join(os.path.dirname(__file__), "..", "info.py")
        with open(info_path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("DATABASE_URI = environ.get('DATABASE_URI'", text)
        self.assertIn("COLLECTION_NAME = environ.get('COLLECTION_NAME', 'rdxcollection')", text)


if __name__ == "__main__":
    unittest.main()
