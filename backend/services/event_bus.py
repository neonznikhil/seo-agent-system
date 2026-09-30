"""In-process async event bus powering all Server-Sent Events streams.

Channels are simple string keys (e.g. "writer:{content_id}", "dashboard:{website_id}",
"agent:{agent_name}:thoughts"). Any coroutine can subscribe and receive dicts as
they are published. History is kept so late subscribers can replay what they missed.

Publishers and subscribers do not necessarily share an event loop: background
automation runs on a dedicated loop (see services.background_runtime) while SSE
streams are served from the API loop. An ``asyncio.Queue`` may only be touched
from the loop that created it, so delivery is routed through each subscriber's
own loop with ``call_soon_threadsafe`` instead of ``put_nowait``.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional

logger = logging.getLogger("backend.services.event_bus")

_MAX_HISTORY = 200

_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY))
# The API loop and the background loop both touch this registry, so guard it.
_registry_lock = threading.Lock()


def _deliver(q: asyncio.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except Exception:
        pass


def publish(channel: str, event: dict) -> None:
    """Publish an event to a channel. Never blocks, never raises."""
    event = {"ts": time.time(), **event}
    with _registry_lock:
        _history[channel].append(event)
        queues = list(_subscribers.get(channel, []))
    for q in queues:
        loop = getattr(q, "_rankforge_loop", None)
        try:
            if loop is not None and loop.is_running():
                # Hop onto the subscriber's loop; a Queue is not thread-safe.
                loop.call_soon_threadsafe(_deliver, q, event)
            else:
                q.put_nowait(event)
        except Exception:
            pass


async def subscribe(channel: str) -> asyncio.Queue:
    """Subscribe to a channel; returns an awaitable queue of events."""
    q: asyncio.Queue = asyncio.Queue()
    try:
        q._rankforge_loop = asyncio.get_running_loop()  # type: ignore[attr-defined]
    except RuntimeError:
        pass
    with _registry_lock:
        # Replay history so the client immediately sees prior progress
        for evt in list(_history.get(channel, [])):
            q.put_nowait(evt)
        _subscribers[channel].append(q)
    return q


def unsubscribe(channel: str, q: asyncio.Queue) -> None:
    with _registry_lock:
        if q in _subscribers.get(channel, []):
            _subscribers[channel].remove(q)
        if not _subscribers.get(channel):
            _subscribers.pop(channel, None)
            _history.pop(channel, None)


async def stream(channel: str, poll_interval: float = 1.0):
    """Async generator yielding events until the client disconnects."""
    q = await subscribe(channel)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=poll_interval)
                yield event
            except asyncio.TimeoutError:
                # Keepalive comment keeps proxies from closing idle streams
                yield {"keepalive": True}
    except asyncio.CancelledError:
        pass
    finally:
        unsubscribe(channel, q)


def get_history(channel: str) -> List[dict]:
    return list(_history.get(channel, []))
