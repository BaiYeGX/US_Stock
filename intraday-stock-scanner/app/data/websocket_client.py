from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable


class WebsocketClient:
    """Generic resilient websocket client with auto reconnect.

    The caller provides connect/send/recv behavior through the websocket library.
    """

    def __init__(self, reconnect_delay_seconds: float = 1.0, max_reconnect_delay_seconds: float = 30.0) -> None:
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.max_reconnect_delay_seconds = max_reconnect_delay_seconds

    async def connect_forever(
        self,
        connect_coro: Callable[[], Awaitable[object]],
        on_connect: Callable[[object], Awaitable[None]],
        on_message: Callable[[dict], Awaitable[None]],
        on_disconnect: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        delay = self.reconnect_delay_seconds
        while True:
            ws = None
            try:
                ws = await connect_coro()
                await on_connect(ws)
                delay = self.reconnect_delay_seconds
                while True:
                    raw = await ws.recv()  # type: ignore[attr-defined]
                    data = json.loads(raw)
                    if isinstance(data, list):
                        for item in data:
                            await on_message(item)
                    elif isinstance(data, dict):
                        await on_message(data)
            except Exception:
                if on_disconnect is not None:
                    await on_disconnect()
                await asyncio.sleep(delay)
                delay = min(delay * 2.0, self.max_reconnect_delay_seconds)
            finally:
                if ws is not None:
                    close_fn = getattr(ws, "close", None)
                    if close_fn is not None:
                        try:
                            await close_fn()
                        except Exception:
                            pass
