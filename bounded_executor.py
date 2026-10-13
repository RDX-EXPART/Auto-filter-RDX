"""Small bounded async wrapper for APIs whose Python clients are synchronous."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

logger = logging.getLogger(__name__)


class BoundedExecutor:
    """Run blocking functions without blocking the event loop or queue buildup."""

    def __init__(self, max_workers=2):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bounded-lookup",
        )
        self._slots = BoundedSemaphore(max_workers)

    async def run(self, function, *args, timeout=6, **kwargs):
        if not self._slots.acquire(blocking=False):
            logger.warning("Blocking lookup skipped: all worker slots are busy")
            return None

        try:
            future = self._executor.submit(function, *args, **kwargs)
        except Exception:
            self._slots.release()
            logger.exception("Could not submit blocking lookup")
            return None

        # Release the slot only when the actual worker exits. Cancelling the
        # asyncio wait cannot stop a running synchronous network call.
        future.add_done_callback(lambda _future: self._slots.release())
        try:
            return await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=max(0.1, float(timeout)),
            )
        except asyncio.TimeoutError:
            logger.warning("Blocking lookup timed out after %s seconds", timeout)
        except Exception:
            logger.exception("Blocking lookup failed")
        return None

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
