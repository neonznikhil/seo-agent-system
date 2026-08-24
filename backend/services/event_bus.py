"""In-process async event bus powering all Server-Sent Events streams.

Channels are simple string keys (e.g. "writer:{content_id}", "dashboard:{website_id}",
"agent:{agent_name}:thoughts"). Any coroutine can subscribe and receive dicts as
they are published. History is kept so late subscribers can replay what they missed.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional

logger = logging.getLogger("backend.services.event_bus")

_MAX_HISTORY = 200

_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY))


def publish(channel: str, event: dict) -> None:
    """Publish an event to a channel. Never blocks, never raises."""
    event = {"ts": time.time(), **event}
    _history[channel].append(event)
    queues = list(_subscribers.get(channel, []))
    for q in queues:
        try:
            q.put_nowait(event)
        except Exception:
            pass


async def subscribe(channel: str) -> asyncio.Queue:
    """Subscribe to a channel; returns an awaitable queue of events."""
    q: asyncio.Queue = asyncio.Queue()
    # Replay history so the client immediately sees prior progress
    for evt in list(_history.get(channel, [])):
        q.put_nowait(evt)
    _subscribers[channel].append(q)
    return q


def unsubscribe(channel: str, q: asyncio.Queue) -> None:
    try:
        if q in _subscribers.get(channel, []):
            _subscribers[channel].remove(q)
        if not _subscribers.get(channel):
            _subscribers.pop(channel, None)
            _history.pop(channel, None)
    except Exception:
        pass


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
