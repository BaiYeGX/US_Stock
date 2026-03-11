from __future__ import annotations


class WebsocketClient:
    async def connect_forever(self, uri: str, handler) -> None:
        await handler(None)
